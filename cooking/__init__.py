"""
Cooking Ideas - Blueprint + Routes
Single module pattern (matches pronunciation_bp.py)
"""
import json, re, os, secrets, random
import requests as req
from flask import Blueprint, render_template, request, jsonify

cooking_bp = Blueprint('cooking', __name__, template_folder='../templates/cooking', static_folder='../static/cooking')

MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '').strip()
MINIMAX_URL = 'https://api.minimax.io/v1/text/chatcompletion_v2?GroupId=2043608871905276295'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = 'gemini-2.5-flash-lite'
GEMINI_URL = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'
PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY', '').strip()

# Lazy import to avoid circular imports
def _get_db():
    from cooking.models import get_db
    return get_db()

def _init_db():
    try:
        from cooking.models import init_db
        init_db()
    except Exception as e:
        print(f"[Cooking] DB init failed: {e}")

_init_db()

def _get_user_key():
    """Extract user_key from request body, default 'default'."""
    data = request.get_json(silent=True) or {}
    return data.get('user_key', 'default')

def _get_user_key():
    """Extract user_key from request body, default 'default'."""
    data = request.get_json(silent=True) or {}
    return data.get('user_key', 'default')

def _ensure_user_key_columns():
    """Lazy migration: add user_key columns if missing (v11→v12)."""
    try:
        conn = _get_db()
        c = conn.cursor()
        # Check if column exists
        try:
            c.execute('SELECT user_key FROM bookmarks LIMIT 0')
        except:
            c.execute("ALTER TABLE bookmarks ADD COLUMN user_key TEXT DEFAULT 'default'")
            c.execute("UPDATE bookmarks SET user_key = 'default' WHERE user_key IS NULL")
            try:
                c.execute('DROP INDEX IF EXISTS sqlite_autoindex_bookmarks_1')
            except:
                pass
            c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_bookmarks_recipe_user ON bookmarks(recipe_id, user_key)')
        try:
            c.execute('SELECT user_key FROM user_recipes LIMIT 0')
        except:
            c.execute("ALTER TABLE user_recipes ADD COLUMN user_key TEXT DEFAULT 'default'")
            c.execute("UPDATE user_recipes SET user_key = 'default' WHERE user_key IS NULL")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'[Cooking] user_key migration: {e}')

@cooking_bp.route('/manifest.json')
def dynamic_manifest():
    """Dynamic PWA manifest with user-specific start_url."""
    user_key = request.args.get('user', 'default')
    start = f'/cooking-ideas/{user_key}' if user_key != 'default' else '/cooking-ideas'
    return jsonify({
        'name': f'Cooking Ideas - {user_key}',
        'short_name': 'Cooking Ideas',
        'description': '隨機生成家常菜式食譜',
        'start_url': start,
        'scope': '/cooking-ideas/',
        'display': 'standalone',
        'display_override': ['window-controls-overlay'],
        'background_color': '#3c1e0a',
        'theme_color': '#3c1e0a',
        'icons': [
            {'src': '/static/cooking/icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any maskable'},
            {'src': '/static/cooking/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'}
        ]
    })

@cooking_bp.route('/')
@cooking_bp.route('/<user_key>')
def index(user_key='default'):
    _ensure_user_key_columns()
    # Check if user is allowed
    if user_key != 'default':
        conn = _get_db()
        c = conn.cursor()
        c.execute('SELECT id FROM allowed_users WHERE user_key = ?', [user_key])
        if not c.fetchone():
            conn.close()
            from flask import abort
            abort(404)
        conn.close()
    return render_template('cooking/index.html', user_key=user_key)

@cooking_bp.route('/api/random', methods=['POST'])
def random_recipes():
    data = request.get_json() or {}
    conn = _get_db()
    c = conn.cursor()

    query = 'SELECT * FROM recipes WHERE 1=1'
    params = []

    cuisines = data.get('cuisines', [])
    if cuisines:
        placeholders = ','.join(['?'] * len(cuisines))
        query += f' AND cuisine IN ({placeholders})'
        params.extend(cuisines)
    else:
        cuisines = ['中式', '西式', '日式', '東南亞']  # Default all

    methods = data.get('methods', [])
    if methods:
        placeholders = ','.join(['?'] * len(methods))
        query += f' AND cooking_method IN ({placeholders})'
        params.extend(methods)

    tastes = data.get('tastes', [])
    if tastes:
        taste_conditions = []
        for t in tastes:
            taste_conditions.append('taste = ?')
            params.append(t)
        query += f' AND ({" OR ".join(taste_conditions)})'

    allergies = data.get('allergies', '').strip()
    if allergies:
        allergy_list = [x.strip().lower() for x in re.split(r'[,,、\s]+', allergies) if x.strip()]
        for allergen in allergy_list:
            query += ' AND ingredients NOT LIKE ?'
            params.append(f'%{allergen}%')

    # Kid filter: age < 9 → no alcohol ever, no spicy unless user explicitly chose 辣
    spicy = data.get('spicy')
    has_kid = data.get('has_kid', False)
    kid_age = int(data.get('kid_age', 0)) if data.get('kid_age') else 0
    if has_kid and kid_age < 9:
        ALCOHOL_KW = ['%酒%', '%味醂%', '%清酒%', '%花雕%', '%米酒%', '%啤酒%', '%紹興%', '%料酒%']
        for kw in ALCOHOL_KW:
            query += ' AND ingredients NOT LIKE ? AND steps NOT LIKE ?'
            params.extend([kw, kw])
        if spicy != 'yes':
            query += ' AND is_spicy = 0'
            spicy = None

    if spicy == 'yes':
        query += ' AND is_spicy = 1'
    elif spicy == 'no':
        query += ' AND is_spicy = 0'

    nutrition = data.get('nutrition', [])
    # Default: exclude 澱粉質 dishes unless user explicitly selected 澱粉質
    if '澱粉質' not in nutrition:
        query += ' AND nutrition_tags NOT LIKE ?'
        params.append('%澱粉質%')
    # Nutrition is handled in meal planning, not as SQL filter (except 澱粉質 exclusion above)
    # We just fetch all matching recipes and plan from them

    max_time = data.get('max_time', 120)  # TOTAL time for all dishes (default generous)

    prep_early = data.get('prep_early')
    if prep_early == 'yes':
        query += ' AND can_prep_early = 1'

    count = min(int(data.get('count', 3)), 10)
    wants_soup = data.get('include_soup', False)
    wants_cold = data.get('include_cold', False)

    have_ingredients = data.get('ingredients', '').strip()
    have_list = []
    if have_ingredients:
        have_list = [x.strip().lower() for x in re.split(r'[,,、\s]+', have_ingredients) if x.strip()]

    c.execute(query, params)
    all_candidates = [dict(r) for r in c.fetchall()]

    if not all_candidates:
        conn.close()
        return jsonify({'success': False, 'error': '未找到符合條件嘅食譜,試下放寬篩選條件。'})

    # Score by ingredient overlap if provided
    if have_list:
        for r in all_candidates:
            recipe_ingredients = r['ingredients'].lower()
            r['_score'] = sum(1 for item in have_list if item in recipe_ingredients)
        all_candidates.sort(key=lambda r: r.get('_score', 0), reverse=True)
        has_matches = [r for r in all_candidates if r.get('_score', 0) > 0]
        if has_matches:
            all_candidates = has_matches

    # === MEAL PLANNING ALGORITHM ===
    # Nutrition types to cover (one dish per type, no duplicates)
    required_nutrition = list(nutrition) if nutrition else ['菜', '蛋白質']  # default

    # Remove soup/cold from candidates if not wanted
    if not wants_soup:
        all_candidates = [r for r in all_candidates if r['has_soup'] == 0]
    if not wants_cold:
        all_candidates = [r for r in all_candidates if r['has_cold_dish'] == 0]

    if not all_candidates:
        conn.close()
        return jsonify({'success': False, 'error': '未找到符合條件嘅食譜,試下放寬篩選條件。'})

    # Build meal plan: distribute nutrition across dishes
    selected = []
    used_nutrition = set()

    # Step 1: Pick soup if requested
    if wants_soup:
        soups = [r for r in all_candidates if r['has_soup'] == 1 and r['id'] not in {s['id'] for s in selected}]
        if soups:
            soups.sort(key=lambda r: r.get('_score', 0), reverse=True)
            # Shuffle top-score tier to avoid always picking same soup
            if len(soups) > 1:
                top_score = soups[0].get('_score', 0)
                tie_count = sum(1 for s in soups if s.get('_score', 0) == top_score)
                if tie_count > 1:
                    tied = soups[:tie_count]
                    random.shuffle(tied)
                    soups[:tie_count] = tied
            selected.append(soups[0])
            # Don't pick another soup for remaining slots
            all_candidates = [r for r in all_candidates if r['has_soup'] == 0 or r['id'] == soups[0]['id']]

    # Step 2: Pick cold dish if requested
    if wants_cold:
        colds = [r for r in all_candidates if r['has_cold_dish'] == 1 and r['id'] not in {s['id'] for s in selected}]
        if colds:
            colds.sort(key=lambda r: r.get('_score', 0), reverse=True)
            # Shuffle top-score tier to avoid always picking same cold dish
            if len(colds) > 1:
                top_score = colds[0].get('_score', 0)
                tie_count = sum(1 for c in colds if c.get('_score', 0) == top_score)
                if tie_count > 1:
                    tied = colds[:tie_count]
                    random.shuffle(tied)
                    colds[:tie_count] = tied
            selected.append(colds[0])
            # Don't pick another cold dish for remaining slots
            all_candidates = [r for r in all_candidates if r['has_cold_dish'] == 0 or r['id'] == colds[0]['id']]

    # Step 3: Fill remaining slots with dishes covering remaining nutrition needs
    dishes_needed = count - len(selected)
    remaining_nutrition = [n for n in required_nutrition if n not in used_nutrition]

    # Distribute remaining nutrition across remaining slots
    # Shuffle to avoid always picking same order
    if remaining_nutrition:
        random.shuffle(remaining_nutrition)

    # Assign nutrition to slots (round-robin if more slots than nutrition)
    slot_nutrition = []
    for i in range(dishes_needed):
        if remaining_nutrition:
            slot_nutrition.append(remaining_nutrition[i % len(remaining_nutrition)])
        else:
            slot_nutrition.append(None)  # any dish fine

    # Also distribute cuisines roughly evenly
    shuffled_cuisines = list(cuisines)
    random.shuffle(shuffled_cuisines)
    cuisine_cycle = shuffled_cuisines * 5  # repeat enough times

    for slot_idx in range(dishes_needed):
        target_nut = slot_nutrition[slot_idx]
        target_cuisine = cuisine_cycle[slot_idx % len(shuffled_cuisines)]

        # Find candidates covering this nutrition and cuisine
        candidates = [r for r in all_candidates
                     if r['id'] not in {s['id'] for s in selected}
                     and r['cuisine'] == target_cuisine]

        # If no match with specific cuisine, try without cuisine constraint
        if not candidates:
            candidates = [r for r in all_candidates
                         if r['id'] not in {s['id'] for s in selected}]

        # If target is 菜, prefer pure vegetable dishes (no tomato/egg/meat in name)
        if target_nut == '菜' and candidates:
            VEG_PROTEIN_KW = ['蛋', '肉', '魚', '蝦', '蟹', '雞', '豬', '牛', '羊']
            VEG_TOMATO_KW = ['蕃茄', '番茄']
            pure_veg = [c for c in candidates
                        if not any(tk in c['name'] for tk in VEG_TOMATO_KW)
                        and not any(pk in c['name'] for pk in VEG_PROTEIN_KW)]
            if pure_veg:
                candidates = pure_veg

        if not candidates:
            continue  # skip if no match

        # Sort by score and avoid already-used nutrition when possible
        candidates.sort(key=lambda r: r.get('_score', 0), reverse=True)
        # Shuffle top-score tier to avoid deterministic first-pick bias
        # (e.g. 蕃茄炒蛋 was always picked first because it's the first DB record)
        if len(candidates) > 1:
            top_score = candidates[0].get('_score', 0)
            tie_count = sum(1 for c in candidates if c.get('_score', 0) == top_score)
            if tie_count > 1:
                tied = candidates[:tie_count]
                random.shuffle(tied)
                candidates[:tie_count] = tied

        # Pick best candidate whose nutrition doesn't overlap too much with used
        best = None
        for c in candidates:
            c_nuts = set(c['nutrition_tags'].split(','))
            new_nuts = [n for n in required_nutrition if any(n in cn for cn in c_nuts) and n not in used_nutrition]
            if new_nuts or not remaining_nutrition:
                best = c
                for n in new_nuts:
                    used_nutrition.add(n)
                break

        if not best:
            best = candidates[0]  # fallback: pick top scorer
            for n in required_nutrition:
                if any(n in cn for cn in best['nutrition_tags'].split(',')):
                    used_nutrition.add(n)

        selected.append(best)

    # Step 4: Check total time constraint
    total_time = sum(r['prep_time_min'] for r in selected)
    if total_time > max_time and len(selected) > 1:
        # Try to swap in faster alternatives (but keep soup/cold if requested)
        skip_indices = set()
        if wants_soup:
            skip_indices.add(0)  # soup is first
        if wants_cold:
            skip_indices.add(len(skip_indices))  # cold is after soup
        for i in range(len(selected) - 1, -1, -1):
            if i in skip_indices:
                continue
            if len(selected) - len(skip_indices) <= 1:
                break
            current = selected[i]
            alt_candidates = [r for r in all_candidates
                             if r['id'] not in {s['id'] for s in selected}
                             and r['prep_time_min'] < current['prep_time_min']]
            if alt_candidates:
                alt_candidates.sort(key=lambda r: r['prep_time_min'])
                selected[i] = alt_candidates[0]
            total_time = sum(r['prep_time_min'] for r in selected)
            if total_time <= max_time:
                break

    if not selected:
        conn.close()
        return jsonify({'success': False, 'error': '未能組合出合適嘅餐單,試下放寬篩選條件。'})

    # Pure vegetable rule: when total dishes ≤ 4, at most 1 vegetable-primary dish
    # Veg dish = has '菜' in nutrition_tags, no 蕃茄/番茄 in name, no protein keyword in name
    if count <= 4:
        PROTEIN_KW = ['蛋', '肉', '魚', '蝦', '蟹', '雞', '豬', '牛', '羊']
        TOMATO_KW = ['蕃茄', '番茄']
        def _is_veg_dish(dish):
            name = dish.get('name', '')
            nt = dish.get('nutrition_tags', '')
            if '菜' not in nt:
                return False
            for tk in TOMATO_KW:
                if tk in name:
                    return False
            for pk in PROTEIN_KW:
                if pk in name:
                    return False
            return True
        pv_indices = [i for i, d in enumerate(selected) if _is_veg_dish(d)]
        if len(pv_indices) > 1:
            # Keep first veg dish, replace others with non-veg alternatives
            for pvi in pv_indices[1:]:
                alt = [r for r in all_candidates
                       if r['id'] not in {s['id'] for s in selected}
                       and not _is_veg_dish(r)]
                if alt:
                    alt.sort(key=lambda r: r.get('_score', 0), reverse=True)
                    # Prefer fast dishes if time is tight
                    total_remaining = sum(d['prep_time_min'] for i, d in enumerate(selected) if i != pvi)
                    if total_remaining + alt[0]['prep_time_min'] > max_time:
                        alt.sort(key=lambda r: r['prep_time_min'])
                    selected[pvi] = alt[0]

    # Soup dedup safety net: at most 1 soup dish (should already be guaranteed by algorithm)
    if wants_soup:
        soup_indices = [i for i, d in enumerate(selected) if d.get('has_soup') == 1]
        if len(soup_indices) > 1:
            for si in soup_indices[1:]:
                alt = [r for r in all_candidates
                       if r['id'] not in {s['id'] for s in selected}
                       and r.get('has_soup') == 0]
                if alt:
                    alt.sort(key=lambda r: r.get('_score', 0), reverse=True)
                    total_remaining = sum(d['prep_time_min'] for i, d in enumerate(selected) if i != si)
                    if total_remaining + alt[0]['prep_time_min'] > max_time:
                        alt.sort(key=lambda r: r['prep_time_min'])
                    selected[si] = alt[0]

    random.shuffle(selected)
    result = [{k: r[k] for k in r.keys() if not k.startswith('_')} for r in selected]
    conn.close()
    return jsonify({'success': True, 'dishes': result, 'total_time': sum(r['prep_time_min'] for r in selected)})

@cooking_bp.route('/api/replace', methods=['POST'])
def replace_dish():
    """Replace a single dish in the current meal plan while respecting overall composition."""
    data = request.get_json() or {}
    conn = _get_db()
    c = conn.cursor()

    current_ids = data.get('current_ids', [])
    replace_idx = data.get('replace_index', 0)

    if not current_ids:
        conn.close()
        return jsonify({'success': False, 'error': '缺少當前餐單資料。'})

    # Build same filters as random_recipes
    query = 'SELECT * FROM recipes WHERE 1=1'
    params = []

    cuisines = data.get('cuisines', [])
    if cuisines:
        placeholders = ','.join(['?'] * len(cuisines))
        query += f' AND cuisine IN ({placeholders})'
        params.extend(cuisines)
    else:
        cuisines = ['中式', '西式', '日式', '東南亞']

    methods = data.get('methods', [])
    if methods:
        placeholders = ','.join(['?'] * len(methods))
        query += f' AND cooking_method IN ({placeholders})'
        params.extend(methods)

    tastes = data.get('tastes', [])
    if tastes:
        taste_conditions = []
        for t in tastes:
            taste_conditions.append('taste = ?')
            params.append(t)
        query += f' AND ({" OR ".join(taste_conditions)})'

    spicy = data.get('spicy')

    # Kid filter: age < 9 → no alcohol ever, no spicy unless user explicitly chose 辣
    has_kid = data.get('has_kid', False)
    kid_age = int(data.get('kid_age', 0)) if data.get('kid_age') else 0
    if has_kid and kid_age < 9:
        ALCOHOL_KW = ['%酒%', '%味醂%', '%清酒%', '%花雕%', '%米酒%', '%啤酒%', '%紹興%', '%料酒%']
        for kw in ALCOHOL_KW:
            query += ' AND ingredients NOT LIKE ? AND steps NOT LIKE ?'
            params.extend([kw, kw])
        if spicy != 'yes':
            query += ' AND is_spicy = 0'
            spicy = None

    if spicy == 'yes':
        query += ' AND is_spicy = 1'
    elif spicy == 'no':
        query += ' AND is_spicy = 0'

    allergies = data.get('allergies', '').strip()
    if allergies:
        allergy_list = [x.strip().lower() for x in re.split(r'[,,、\s]+', allergies) if x.strip()]
        for allergen in allergy_list:
            query += ' AND ingredients NOT LIKE ?'
            params.append(f'%{allergen}%')

    max_time = data.get('max_time', 120)
    prep_early = data.get('prep_early')
    if prep_early == 'yes':
        query += ' AND can_prep_early = 1'

    count = min(int(data.get('count', 3)), 10)
    wants_soup = data.get('include_soup', False)
    wants_cold = data.get('include_cold', False)
    nutrition = data.get('nutrition', ['菜', '蛋白質'])
    # Default: exclude 澱粉質 dishes unless user explicitly selected 澱粉質
    if '澱粉質' not in nutrition:
        query += ' AND nutrition_tags NOT LIKE ?'
        params.append('%澱粉質%')

    have_ingredients = data.get('ingredients', '').strip()
    have_list = []
    if have_ingredients:
        have_list = [x.strip().lower() for x in re.split(r'[,,、\s]+', have_ingredients) if x.strip()]

    c.execute(query, params)
    all_candidates = [dict(r) for r in c.fetchall()]

    if not all_candidates:
        conn.close()
        return jsonify({'success': False, 'error': '未找到符合條件嘅食譜。'})

    # Score by ingredient overlap
    if have_list:
        for r in all_candidates:
            recipe_ingredients = r['ingredients'].lower()
            r['_score'] = sum(1 for item in have_list if item in recipe_ingredients)

    # Exclude current dishes
    exclude_ids = set(current_ids)
    candidates = [r for r in all_candidates if r['id'] not in exclude_ids]

    # Also remove soup/cold if not wanted
    if not wants_soup:
        candidates = [r for r in candidates if r['has_soup'] == 0]
    if not wants_cold:
        candidates = [r for r in candidates if r['has_cold_dish'] == 0]

    # If soup/cold is included, non-soup/cold slots should NOT get soup/cold replacements
    # Detect actual soup/cold positions from current dishes (may be shuffled)
    soup_slot = -1
    cold_slot = -1
    for i, rid in enumerate(current_ids):
        for r in all_candidates:
            if r['id'] == rid:
                if r.get('has_soup') == 1:
                    soup_slot = i
                if r.get('has_cold_dish') == 1:
                    cold_slot = i
                break
    if wants_soup and replace_idx != soup_slot:
        candidates = [r for r in candidates if r['has_soup'] == 0]
    if wants_cold and replace_idx != cold_slot:
        candidates = [r for r in candidates if r['has_cold_dish'] == 0]

    # Match type of replaced dish: if replacing soup/cold slot, must be same type
    if wants_soup and replace_idx == soup_slot:
        candidates = [r for r in candidates if r['has_soup'] == 1]
    if wants_cold and replace_idx == cold_slot:
        candidates = [r for r in candidates if r['has_cold_dish'] == 1]

    if not candidates:
        conn.close()
        return jsonify({'success': False, 'error': '冇其他合適嘅菜式可以替換。'})

    # Determine what the replaced dish was covering (nutrition, cuisine)
    replaced_id = current_ids[replace_idx] if replace_idx < len(current_ids) else None
    replaced_dish = None
    for r in all_candidates:
        if r['id'] == replaced_id:
            replaced_dish = r
            break

    # Veg dish = has '菜' in nutrition_tags, no 蕃茄/番茄 in name, no protein keyword in name
    PROTEIN_KW = ['蛋', '肉', '魚', '蝦', '蟹', '雞', '豬', '牛', '羊']
    TOMATO_KW = ['蕃茄', '番茄']
    def _is_veg_dish(dish):
        name = dish.get('name', '')
        nt = dish.get('nutrition_tags', '')
        if '菜' not in nt:
            return False
        for tk in TOMATO_KW:
            if tk in name:
                return False
        for pk in PROTEIN_KW:
            if pk in name:
                return False
        return True

    # Count veg dishes in current dishes (excluding the one being replaced)
    pv_count_others = 0
    for i, rid in enumerate(current_ids):
        if i == replace_idx:
            continue
        for r in all_candidates:
            if r['id'] == rid:
                if _is_veg_dish(r):
                    pv_count_others += 1
                break

    # Veg dish dedup
    replaced_is_pv = _is_veg_dish(replaced_dish) if replaced_dish else False
    if count <= 4 and pv_count_others >= 1 and not replaced_is_pv:
        candidates = [c for c in candidates if not _is_veg_dish(c)]
        if not candidates:
            conn.close()
            return jsonify({'success': False, 'error': '冇其他合適嘅菜式可以替換。'})

    # Score candidates: prefer matching nutrition, cuisine, and ingredient overlap
    scored = []
    for c in candidates:
        score = c.get('_score', 0)
        # Prefer same cuisine as replaced dish
        if replaced_dish and c['cuisine'] == replaced_dish.get('cuisine'):
            score += 2
        # Prefer similar cooking method
        if replaced_dish and c['cooking_method'] == replaced_dish.get('cooking_method'):
            score += 1
        # Prefer same dish type: 湯→湯, veg dish→veg dish, 澱粉質→澱粉質
        if replaced_dish:
            if _is_veg_dish(replaced_dish) and _is_veg_dish(c):
                score += 4
            replaced_starch = '澱粉質' in replaced_dish.get('nutrition_tags', '')
            cand_starch = '澱粉質' in c.get('nutrition_tags', '')
            if replaced_starch and cand_starch:
                score += 4
        # Avoid new dish being veg dish if we already have one
        if count <= 4 and _is_veg_dish(c) and pv_count_others >= 1:
            score -= 10  # Strong penalty
        # Respect time: remaining time budget
        remaining_time = max_time - sum(
            r['prep_time_min'] for i, rid in enumerate(current_ids)
            for r in all_candidates if r['id'] == rid and i != replace_idx
        )
        if c['prep_time_min'] > remaining_time:
            score -= 5
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Pick from top candidates randomly to avoid deterministic A↔B cycling
    # (recycling is OK - A→B→C→A - just avoid immediate A→B→A bounce)
    if scored:
        top_score = scored[0][0]
        # Take all candidates within 1 point of the best score
        top_candidates = [c for s, c in scored if top_score - s <= 1]
        best = random.choice(top_candidates)
    else:
        best = candidates[0]

    conn.close()
    result = {k: best[k] for k in best.keys() if not k.startswith('_')}
    return jsonify({'success': True, 'dish': result})

@cooking_bp.route('/api/search', methods=['POST'])
def ai_search():
    data = request.get_json() or {}
    dish_name = data.get('dish_name', '').strip()

    if not dish_name:
        return jsonify({'success': False, 'error': '請輸入菜式名稱。'})

    if not GEMINI_API_KEY:
        return jsonify({'success': False, 'error': 'AI search not configured.'})

    prompt = f"""Generate 3 complete recipe variations for "{dish_name}" in Traditional Chinese (繁體中文).
Each variation should use slightly different cooking methods, ingredients, or styles.

Output ONLY a valid JSON array with 3 recipe objects, no markdown, no explanation:

[
  {{
    "name": "菜名(變化一)",
    "cuisine": "中式/西式/日式/東南亞",
    "cooking_method": "蒸/炒/炆/燉/煎/焗/炸",
    "taste": "清淡/濃味/辣",
    "is_spicy": 0或1,
    "kid_friendly": 0或1,
    "ingredients": "材料列表(每項用逗號分隔)",
    "steps": "步驟(用\\n分隔每步)",
    "tips": "小貼士",
    "prep_time_min": 15,
    "can_prep_early": 0或1,
    "nutrition_tags": "營養標籤(e.g. 菜,魚,白肉,紅肉,澱粉質,蛋白質)",
    "servings": 4
  }},
  ...(total 3 recipes)
]

Rules:
- ALL text MUST be Traditional Chinese (繁體中文)
- Each recipe must be genuinely different (different cooking method, ingredient focus, or style)
- Steps numbered, separated by \\n
- Give realistic home-cooking recipes
- kid_friendly=1 if non-spicy AND no alcohol (酒/清酒/味醂/紹興酒/料酒) in ingredients, otherwise 0
- Output ONLY the JSON array, nothing else"""

    try:
        url = f'{GEMINI_URL}?key={GEMINI_API_KEY}'
        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': 0.3,
                'maxOutputTokens': 2000
            }
        }

        response = req.post(url, json=payload, timeout=35)

        if response.status_code != 200:
            err_msg = f'AI API 錯誤 ({response.status_code})。請稍後再試。'
            print(f'[Cooking] Gemini error: {response.status_code} - {response.text[:300]}')
            return jsonify({'success': False, 'error': err_msg})

        result = response.json()
        candidates = result.get('candidates', [])
        if not candidates:
            block_reason = result.get('promptFeedback', {}).get('blockReason', '')
            if block_reason:
                return jsonify({'success': False, 'error': f'內容被攔截:{block_reason}。請嘗試其他菜式名稱。'})
            return jsonify({'success': False, 'error': 'No response from AI.'})

        content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')

        if not content:
            finish_reason = candidates[0].get('finishReason', 'unknown')
            if finish_reason == 'SAFETY':
                return jsonify({'success': False, 'error': 'AI 無法生成此食譜(安全限制)。請嘗試其他菜式名稱。'})
            return jsonify({'success': False, 'error': 'AI 未返回內容,請再試。'})

        # Clean JSON
        content = re.sub(r'```json', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content, flags=re.IGNORECASE)
        content = content.strip()
        start = content.find('[')
        if start == -1:
            start = content.find('{')
        end = content.rfind(']') + 1
        if end == 0:
            end = content.rfind('}') + 1
        if start == -1 or end == 0:
            return jsonify({'success': False, 'error': 'AI response format error.'})

        parsed = json.loads(content[start:end])
        if isinstance(parsed, list):
            recipes = parsed
        else:
            recipes = [parsed]
        for r in recipes:
            r['source'] = 'ai_search'
            r['from_ai'] = True

        return jsonify({'success': True, 'recipes': recipes})

    except req.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'AI 搜尋超時(35秒),請用更簡單嘅菜式名再試。'})
    except req.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': f'網絡錯誤,請再試。'})
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'AI 回覆格式錯誤,請再試。'})
    except Exception as e:
        print(f'[Cooking] AI search error: {type(e).__name__}: {e}')
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/save', methods=['POST'])
def save_recipe():
    data = request.get_json() or {}

    if not data.get('name'):
        return jsonify({'success': False, 'error': 'Recipe name required.'})

    conn = _get_db()
    c = conn.cursor()

    try:
        c.execute('''
            INSERT INTO recipes 
            (name, name_en, cuisine, cooking_method, taste, nutrition_tags, 
             prep_time_min, can_prep_early, is_spicy, kid_friendly, ingredients, steps, tips, source, servings, owner_user_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ai_custom', ?, ?)
        ''', (
            data['name'],
            data.get('name_en', ''),
            data.get('cuisine', '中式'),
            data.get('cooking_method', '炒'),
            data.get('taste', '清淡'),
            data.get('nutrition_tags', ''),
            data.get('prep_time_min', 30),
            data.get('can_prep_early', 0),
            data.get('is_spicy', 0),
            data.get('kid_friendly', 1),
            data.get('ingredients', ''),
            data.get('steps', ''),
            data.get('tips', ''),
            data.get('servings', 4),
            data.get('user_key', 'default')
        ))
        conn.commit()
        new_id = c.lastrowid

        c.execute('INSERT INTO custom_dishes (name, recipe_id) VALUES (?, ?)',
                  (data['name'], new_id))
        conn.commit()

        conn.close()
        return jsonify({'success': True, 'id': new_id, 'message': '已儲存!'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/recipe/<int:recipe_id>', methods=['GET'])
def get_recipe(recipe_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    conn.close()
    if r:
        return jsonify({'success': True, 'recipe': dict(r)})
    return jsonify({'success': False, 'error': 'Recipe not found.'})

@cooking_bp.route('/api/recipe/<int:recipe_id>/edit', methods=['POST'])
def update_recipe(recipe_id):
    data = request.get_json() or {}
    user_key = data.get('user_key', '')
    # Allow admin or recipe owner
    if not _admin_check(request):
        conn = _get_db()
        c = conn.cursor()
        c.execute('SELECT owner_user_key FROM recipes WHERE id = ?', [recipe_id])
        row = c.fetchone()
        conn.close()
        if not row or row['owner_user_key'] != user_key:
            return jsonify({'success': False, 'error': '你只能編輯自己嘅食譜。'})
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM recipes WHERE id = ?', [recipe_id])
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    try:
        fields = ['name', 'cuisine', 'cooking_method', 'taste', 'nutrition_tags',
                  'prep_time_min', 'can_prep_early', 'is_spicy', 'kid_friendly', 'ingredients', 'steps', 'tips', 'servings']
        updates = []
        params = []
        for f in fields:
            if f in data:
                updates.append(f'{f} = ?')
                params.append(data[f])
        if not updates:
            conn.close()
            return jsonify({'success': False, 'error': 'No fields to update.'})
        params.append(recipe_id)
        sql = f'UPDATE recipes SET {", ".join(updates)} WHERE id = ?'
        c.execute(sql, params)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '已更新!'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/recipe/<int:recipe_id>/delete', methods=['POST'])
def delete_recipe(recipe_id):
    data = request.get_json() or {}
    user_key = data.get('user_key', '')
    # Allow admin or recipe owner
    if not _admin_check(request):
        conn = _get_db()
        c = conn.cursor()
        c.execute('SELECT owner_user_key FROM recipes WHERE id = ?', [recipe_id])
        row = c.fetchone()
        conn.close()
        if not row or row['owner_user_key'] != user_key:
            return jsonify({'success': False, 'error': '你只能刪除自己嘅食譜。'})
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT id, source, name FROM recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    if r['source'] == 'seed':
        conn.close()
        return jsonify({'success': False, 'error': '不能刪除內置食譜,只可以刪除 AI 加入嘅食譜。'})
    try:
        c.execute('DELETE FROM bookmarks WHERE recipe_id = ?', [recipe_id])
        c.execute('DELETE FROM custom_dishes WHERE recipe_id = ?', [recipe_id])
        c.execute('UPDATE user_recipes SET db_recipe_id = NULL WHERE db_recipe_id = ?', [recipe_id])
        c.execute('DELETE FROM recipes WHERE id = ?', [recipe_id])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'已刪除「{r["name"]}」'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/bookmark', methods=['POST'])
def toggle_bookmark():
    _ensure_user_key_columns()
    data = request.get_json() or {}
    recipe_id = data.get('recipe_id')
    user_key = data.get('user_key', 'default')
    if not recipe_id:
        return jsonify({'success': False, 'error': 'Recipe ID required.'})
    conn = _get_db()
    c = conn.cursor()
    try:
        c.execute('SELECT id FROM bookmarks WHERE recipe_id = ? AND user_key = ?', [recipe_id, user_key])
        existing = c.fetchone()
        if existing:
            c.execute('DELETE FROM bookmarks WHERE recipe_id = ? AND user_key = ?', [recipe_id, user_key])
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'bookmarked': False, 'message': '已移除收藏'})
        else:
            c.execute('INSERT INTO bookmarks (recipe_id, user_key) VALUES (?, ?)', [recipe_id, user_key])
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'bookmarked': True, 'message': '已收藏!'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/bookmarks', methods=['GET'])
def list_bookmarks():
    user_key = request.args.get('user_key', 'default')
    conn = _get_db()
    c = conn.cursor()
    c.execute('''
        SELECT r.*, b.created_at as bookmarked_at
        FROM bookmarks b
        JOIN recipes r ON b.recipe_id = r.id
        WHERE b.user_key = ?
        ORDER BY b.created_at DESC
    ''', [user_key])
    recipes = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'bookmarks': recipes})

@cooking_bp.route('/api/bookmark/status', methods=['POST'])
def bookmark_status():
    """Batch check bookmark status for a list of recipe IDs."""
    data = request.get_json() or {}
    recipe_ids = data.get('recipe_ids', [])
    user_key = data.get('user_key', 'default')
    if not recipe_ids:
        return jsonify({'success': True, 'bookmarked': {}})
    conn = _get_db()
    c = conn.cursor()
    placeholders = ','.join(['?'] * len(recipe_ids))
    params = list(recipe_ids) + [user_key]
    c.execute(f'SELECT recipe_id FROM bookmarks WHERE recipe_id IN ({placeholders}) AND user_key = ?', params)
    bookmarked = {str(r['recipe_id']): True for r in c.fetchall()}
    conn.close()
    return jsonify({'success': True, 'bookmarked': bookmarked})

@cooking_bp.route('/api/search-db', methods=['POST'])
def search_db():
    """Search recipes with text query + advanced filters."""
    data = request.get_json() or {}
    query = data.get('q', '').strip()

    conn = _get_db()
    c = conn.cursor()

    # Build query
    sql = 'SELECT * FROM recipes WHERE 1=1'
    params = []

    # Text search
    if query:
        like = f'%{query}%'
        sql += ' AND (name LIKE ? OR ingredients LIKE ? OR cuisine LIKE ?)'
        params.extend([like, like, like])

    # Cuisine filter
    cuisines = data.get('cuisines', [])
    if cuisines:
        placeholders = ','.join(['?'] * len(cuisines))
        sql += f' AND cuisine IN ({placeholders})'
        params.extend(cuisines)

    # Method filter
    methods = data.get('methods', [])
    if methods:
        placeholders = ','.join(['?'] * len(methods))
        sql += f' AND cooking_method IN ({placeholders})'
        params.extend(methods)

    # Taste filter
    tastes = data.get('tastes', [])
    if tastes:
        taste_conds = []
        for t in tastes:
            taste_conds.append('taste = ?')
            params.append(t)
        sql += f' AND ({" OR ".join(taste_conds)})'

    # Nutrition filter (dish has ANY of the selected tags)
    nutrition = data.get('nutrition', [])
    if nutrition:
        nut_conds = []
        for n in nutrition:
            nut_conds.append('nutrition_tags LIKE ?')
            params.append(f'%{n}%')
        sql += f' AND ({" OR ".join(nut_conds)})'

    # Max time
    max_time = data.get('max_time')
    if max_time:
        sql += ' AND prep_time_min <= ?'
        params.append(int(max_time))

    # Kid friendly
    kid_friendly = data.get('kid_friendly')
    if kid_friendly == 'yes':
        sql += ' AND kid_friendly = 1'
    elif kid_friendly == 'no':
        sql += ' AND kid_friendly = 0'

    # Prep early
    prep_early = data.get('prep_early')
    if prep_early == 'yes':
        sql += ' AND can_prep_early = 1'

    # Soup / cold dish
    if data.get('has_soup'):
        sql += ' AND has_soup = 1'
    if data.get('has_cold'):
        sql += ' AND has_cold_dish = 1'

    # Source filter
    sources = data.get('sources', [])
    if sources:
        placeholders = ','.join(['?'] * len(sources))
        sql += f' AND source IN ({placeholders})'
        params.extend(sources)

    # Order: by name match relevance if text query, else by name
    if query:
        like2 = f'%{query}%'
        sql += ' ORDER BY CASE WHEN name LIKE ? THEN 0 ELSE 1 END, name LIMIT 30'
        params.append(like2)
    else:
        sql += ' ORDER BY name LIMIT 30'

    c.execute(sql, params)
    results = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'results': results, 'count': len(results)})

@cooking_bp.route('/api/images', methods=['POST'])
def recipe_images():
    """Search Pexels for dish images. Translates Chinese names to English via Gemini for better results."""
    if not PEXELS_API_KEY:
        return jsonify({'success': False, 'error': 'Image search not configured.'})
    data = request.get_json() or {}
    dishes = data.get('dishes', [])
    if not dishes:
        return jsonify({'success': True, 'images': {}})

    # Batch translate Chinese dish names to English via Gemini
    search_terms = {}
    if GEMINI_API_KEY and dishes:
        try:
            names_list = '\n'.join(dishes[:6])
            prompt = f"""Translate these Chinese dish names to simple English search keywords for stock photo search. Output ONLY a JSON object mapping each original name to 2-3 English keywords:
{names_list}

Example format:
{{"番茄炒蛋": "tomato scrambled eggs", "薯仔燜雞翼": "braised chicken wings potato"}}"""
            resp = req.post(
                f'{GEMINI_URL}?key={GEMINI_API_KEY}',
                json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.1, 'maxOutputTokens': 500}},
                timeout=15
            )
            if resp.status_code == 200:
                raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
                raw = re.sub(r'```json|```', '', raw).strip()
                s = raw.find('{'); e = raw.rfind('}') + 1
                if s >= 0 and e > 0:
                    search_terms = json.loads(raw[s:e])
        except Exception:
            pass

    images = {}
    for dish in dishes[:6]:
        # Use English translation if available, otherwise original name
        query = search_terms.get(dish, dish)
        try:
            resp = req.get(
                'https://api.pexels.com/v1/search',
                headers={'Authorization': PEXELS_API_KEY},
                params={'query': f'{query} dish', 'per_page': 1, 'size': 'medium'},
                timeout=8
            )
            if resp.status_code == 200:
                photos = resp.json().get('photos', [])
                if photos:
                    src = photos[0]['src'].get('medium') or photos[0]['src'].get('small') or photos[0]['src']['original']
                    images[dish] = src
        except Exception:
            pass

    return jsonify({'success': True, 'images': images})

@cooking_bp.route('/api/expand-recipe', methods=['POST'])
def expand_recipe():
    """Use Gemini to generate a more detailed version of a recipe."""
    if not GEMINI_API_KEY:
        return jsonify({'success': False, 'error': 'AI not configured.'})
    data = request.get_json() or {}
    dish_name = data.get('name', '').strip()
    ingredients = data.get('ingredients', '').strip()
    steps = data.get('steps', '').strip()
    cuisine = data.get('cuisine', '').strip()
    if not dish_name:
        return jsonify({'success': False, 'error': 'Recipe name required.'})

    prompt = f"""Expand this recipe with much more detail in Traditional Chinese (繁體中文).

Original recipe: {dish_name} ({cuisine})
Ingredients: {ingredients}
Steps: {steps}

Provide a COMPLETE, DETAILED recipe with:
1. Ingredient list where EVERY item MUST include a specific quantity WITH A UNIT (e.g., "豬肉 200克", "雞蛋 3隻", "鹽 1茶匙", "油 2湯匙"). Never omit units.
2. Detailed numbered steps with cooking techniques explained
3. Helpful cooking tips
4. Estimated prep time

Output ONLY valid JSON:
{{"name":"{dish_name}","cuisine":"{cuisine}","ingredients":"detailed ingredients with amounts AND units","steps":"detailed numbered steps with explanations","tips":"cooking tips","prep_time_min":30}}"""

    try:
        url = f'{GEMINI_URL}?key={GEMINI_API_KEY}'
        resp = req.post(url, json={
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0.3, 'maxOutputTokens': 3000}
        }, timeout=35)

        if resp.status_code != 200:
            return jsonify({'success': False, 'error': f'AI API error ({resp.status_code})'})

        raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
        raw = re.sub(r'```json|```', '', raw).strip()
        s = raw.find('{'); e = raw.rfind('}') + 1
        if s < 0 or e <= 0:
            return jsonify({'success': False, 'error': 'AI response format error.'})

        json_str = raw[s:e]
        # Try to parse, with simple repair for unescaped newlines
        try:
            recipe = json.loads(json_str)
        except json.JSONDecodeError:
            import re as _re
            fixed = _re.sub(r'"([^"]*?[\n\r][^"]*?)"',
                lambda m: '"' + m.group(1).replace('\n', '\\n').replace('\r', '') + '"',
                json_str)
            recipe = json.loads(fixed)

        # Normalize Gemini output: convert array formats to strings
        if isinstance(recipe.get('ingredients'), list):
            items = recipe['ingredients']
            if items and isinstance(items[0], dict) and 'item' in items[0]:
                recipe['ingredients'] = '\n'.join(
                    f"{it.get('item','')} {it.get('quantity','')}{it.get('unit','')}".strip()
                    for it in items
                )
            else:
                recipe['ingredients'] = '\n'.join(str(it) for it in items)
        if isinstance(recipe.get('steps'), list):
            st = recipe['steps']
            if st and isinstance(st[0], dict):
                inst_key = 'instruction' if 'instruction' in st[0] else ('description' if 'description' in st[0] else None)
                if inst_key:
                    recipe['steps'] = '\n'.join(
                        f"{s.get('step_number',i+1)}. {s.get(inst_key,'')}"
                        for i, s in enumerate(st)
                    )
                else:
                    recipe['steps'] = '\n'.join(str(s) for s in st)
            else:
                recipe['steps'] = '\n'.join(str(s) for s in st)

        return jsonify({'success': True, 'recipe': recipe})

    except req.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'AI 搜尋超時,請再試。'})
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'AI 回覆格式錯誤,請再試。'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ===== USER PREFERENCES (設成預設) =====

@cooking_bp.route('/api/preferences/save', methods=['POST'])
def save_preferences():
    data = request.get_json() or {}
    user_key = data.get('user_key', 'default')
    preferences = data.get('preferences', {})
    if not isinstance(preferences, dict):
        return jsonify({'success': False, 'error': 'Invalid preferences format'})
    conn = _get_db()
    c = conn.cursor()
    prefs_json = json.dumps(preferences, ensure_ascii=False)
    c.execute('''
        INSERT INTO user_preferences (user_key, preferences, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(user_key) DO UPDATE SET
            preferences = excluded.preferences,
            updated_at = excluded.updated_at
    ''', [user_key, prefs_json])
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '已儲存預設'})

@cooking_bp.route('/api/preferences/theme', methods=['POST'])
def save_theme_preference():
    """Save just the theme preference for a user (lightweight, no merge needed)."""
    data = request.get_json() or {}
    user_key = data.get('user_key', 'default')
    theme = data.get('theme', 'dark')
    conn = _get_db()
    c = conn.cursor()
    # Load existing preferences, update theme, save back
    c.execute('SELECT preferences FROM user_preferences WHERE user_key = ?', [user_key])
    row = c.fetchone()
    if row:
        try:
            prefs = json.loads(row['preferences'])
        except json.JSONDecodeError:
            prefs = {}
    else:
        prefs = {}
    prefs['theme'] = theme
    prefs_json = json.dumps(prefs, ensure_ascii=False)
    c.execute('''
        INSERT INTO user_preferences (user_key, preferences, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(user_key) DO UPDATE SET
            preferences = excluded.preferences,
            updated_at = excluded.updated_at
    ''', [user_key, prefs_json])
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@cooking_bp.route('/api/preferences/load', methods=['GET'])
def load_preferences():
    user_key = request.args.get('user_key', 'default')
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT preferences FROM user_preferences WHERE user_key = ?', [user_key])
    row = c.fetchone()
    conn.close()
    if row:
        try:
            prefs = json.loads(row['preferences'])
            return jsonify({'success': True, 'preferences': prefs})
        except json.JSONDecodeError:
            return jsonify({'success': True, 'preferences': {}})
    return jsonify({'success': True, 'preferences': {}})

# ===== USER RECIPES (創建菜式) =====

@cooking_bp.route('/api/user-recipes', methods=['GET', 'POST'])
def user_recipes():
    if request.method == 'GET':
        user_key = request.args.get('user_key', 'default')
        conn = _get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM user_recipes WHERE user_key = ? ORDER BY created_at DESC', [user_key])
        recipes = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'success': True, 'recipes': recipes})
    elif request.method == 'POST':
        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Recipe name required.'})
        user_key = data.get('user_key', 'default')
        conn = _get_db()
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO user_recipes (name, cuisine, cooking_method, taste, nutrition_tags,
                    prep_time_min, ingredients, steps, tips, servings, creator, image_base64, is_spicy, can_prep_early, kid_friendly, user_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['name'], data.get('cuisine', '中式'), data.get('cooking_method', '炒'),
                data.get('taste', '清淡'), data.get('nutrition_tags', ''),
                data.get('prep_time_min', 30), data.get('ingredients', ''),
                data.get('steps', ''), data.get('tips', ''),
                data.get('servings', 4), data.get('creator', ''),
                data.get('image_base64', ''), data.get('is_spicy', 0), data.get('can_prep_early', 0),
                data.get('kid_friendly', 1), user_key
            ))
            conn.commit()
            new_id = c.lastrowid
            conn.close()
            return jsonify({'success': True, 'id': new_id, 'message': '已創建!'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/user-recipes/<int:recipe_id>/edit', methods=['POST'])
def edit_user_recipe(recipe_id):
    data = request.get_json() or {}
    user_key = data.get('user_key', 'default')
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT user_key FROM user_recipes WHERE id = ?', [recipe_id])
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    if row['user_key'] != user_key:
        conn.close()
        return jsonify({'success': False, 'error': '你只能編輯自己嘅食譜。'})
    try:
        fields = ['name', 'cuisine', 'cooking_method', 'taste', 'nutrition_tags',
                  'prep_time_min', 'ingredients', 'steps', 'tips', 'servings', 'creator', 'image_base64', 'is_spicy', 'can_prep_early', 'kid_friendly']
        updates = []
        params = []
        for f in fields:
            if f in data:
                updates.append(f'{f} = ?')
                params.append(data[f])
        if not updates:
            conn.close()
            return jsonify({'success': False, 'error': 'No fields to update.'})
        params.append(recipe_id)
        sql = f'UPDATE user_recipes SET {", ".join(updates)} WHERE id = ?'
        c.execute(sql, params)

        # If this recipe was added to the main DB, sync changes there too
        c.execute('SELECT db_recipe_id FROM user_recipes WHERE id = ?', [recipe_id])
        row = c.fetchone()
        if row and row['db_recipe_id']:
            db_fields = ['name', 'cuisine', 'cooking_method', 'taste', 'nutrition_tags',
                        'prep_time_min', 'ingredients', 'steps', 'tips', 'servings', 'image_base64', 'is_spicy', 'can_prep_early', 'kid_friendly']
            db_updates = []
            db_params = []
            for f in db_fields:
                if f in data:
                    db_updates.append(f'{f} = ?')
                    db_params.append(data[f])
            if db_updates:
                db_params.append(row['db_recipe_id'])
                db_sql = f'UPDATE recipes SET {", ".join(db_updates)} WHERE id = ?'
                c.execute(db_sql, db_params)

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '已更新!'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/user-recipes/<int:recipe_id>/delete', methods=['POST'])
def delete_user_recipe(recipe_id):
    data = request.get_json() or {}
    user_key = data.get('user_key', 'default')
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT id, name, user_key FROM user_recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    if r['user_key'] != user_key:
        conn.close()
        return jsonify({'success': False, 'error': '你只能刪除自己嘅食譜。'})
    try:
        c.execute('DELETE FROM user_recipes WHERE id = ?', [recipe_id])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'已刪除「{r["name"]}」'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/user-recipes/<int:recipe_id>/add-to-db', methods=['POST'])
def add_user_recipe_to_db(recipe_id):
    """Copy a user recipe into the main recipes table."""
    data = request.get_json() or {}
    user_key = data.get('user_key', 'default')
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM user_recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    if r['user_key'] != user_key:
        conn.close()
        return jsonify({'success': False, 'error': '你只能加入自己嘅食譜。'})
    if r['db_recipe_id']:
        conn.close()
        return jsonify({'success': False, 'error': '已經加入過食譜庫。'})
    try:
        c.execute('''
            INSERT INTO recipes (name, cuisine, cooking_method, taste, nutrition_tags,
                prep_time_min, can_prep_early, is_spicy, kid_friendly, ingredients, steps, tips, source, servings, image_base64, owner_user_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user_created', ?, ?, ?)
        ''', (
            r['name'], r['cuisine'], r['cooking_method'], r['taste'],
            r['nutrition_tags'], r['prep_time_min'], r['can_prep_early'],
            r['is_spicy'], r['kid_friendly'], r['ingredients'], r['steps'], r['tips'], r['servings'],
            r['image_base64'], user_key
        ))
        new_id = c.lastrowid
        c.execute('UPDATE user_recipes SET db_recipe_id = ? WHERE id = ?', [new_id, recipe_id])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': new_id, 'message': f'「{r["name"]}」已加入食譜庫!'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/user-recipes/<int:recipe_id>/remove-from-db', methods=['POST'])
def remove_user_recipe_from_db(recipe_id):
    """Remove a previously added recipe from the main recipes table."""
    data = request.get_json() or {}
    user_key = data.get('user_key', 'default')
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM user_recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    if r['user_key'] != user_key:
        conn.close()
        return jsonify({'success': False, 'error': '你只能移除自己嘅食譜。'})
    if not r['db_recipe_id']:
        conn.close()
        return jsonify({'success': False, 'error': '尚未加入食譜庫。'})
    try:
        db_id = r['db_recipe_id']
        c.execute('DELETE FROM bookmarks WHERE recipe_id = ?', [db_id])
        c.execute('DELETE FROM custom_dishes WHERE recipe_id = ?', [db_id])
        c.execute('DELETE FROM recipes WHERE id = ?', [db_id])
        c.execute('UPDATE user_recipes SET db_recipe_id = NULL WHERE id = ?', [recipe_id])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'「{r["name"]}」已從食譜庫移除。'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

# ===== ADMIN: User management (password-protected) =====

def _admin_check(request):
    """Verify admin password from request body. Uses COOKING_ADMIN_PASSWORD env var."""
    password = (request.get_json(silent=True) or {}).get('password', '')
    if not password:
        return False
    import bcrypt
    pw_file = os.path.join(os.path.dirname(__file__), 'admin_password.hash')
    # If hash file exists, use bcrypt verification
    if os.path.exists(pw_file):
        with open(pw_file) as f:
            stored = f.read().strip()
        if stored.startswith('$2'):
            return bcrypt.checkpw(password.encode(), stored.encode())
    # Fallback: compare with env var (and store hash for future)
    admin_pw = os.environ.get('COOKING_ADMIN_PASSWORD', '')
    if password == admin_pw:
        # Auto-generate hash for future use
        try:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            with open(pw_file, 'w') as f:
                f.write(hashed.decode())
        except:
            pass
        return True
    return False

@cooking_bp.route('/api/admin/users', methods=['POST'])
def admin_list_users():
    if not _admin_check(request):
        return jsonify({'success': False, 'error': '密碼錯誤'})
    conn = _get_db()
    c = conn.cursor()
    users = {'default': {'bookmarks': 0, 'recipes': 0}}
    c.execute("SELECT DISTINCT user_key, COUNT(*) as cnt FROM bookmarks GROUP BY user_key")
    for r in c.fetchall():
        users[r['user_key']] = {'bookmarks': r['cnt'], 'recipes': 0}
    c.execute("SELECT DISTINCT user_key, COUNT(*) as cnt FROM user_recipes GROUP BY user_key")
    for r in c.fetchall():
        uk = r['user_key']
        if uk not in users:
            users[uk] = {'bookmarks': 0, 'recipes': 0}
        users[uk]['recipes'] = r['cnt']
    # Check allowed status
    c.execute("SELECT user_key FROM allowed_users")
    allowed = {r['user_key'] for r in c.fetchall()}
    conn.close()
    result = [{'user_key': k, **v, 'allowed': k in allowed} for k, v in users.items()]
    # Also show allowed users with no data
    for uk in allowed:
        if uk not in users:
            result.append({'user_key': uk, 'bookmarks': 0, 'recipes': 0, 'allowed': True})
    return jsonify({'success': True, 'users': result})

@cooking_bp.route('/api/admin/user/add', methods=['POST'])
def admin_add_user():
    if not _admin_check(request):
        return jsonify({'success': False, 'error': '密碼錯誤'})
    data = request.get_json() or {}
    user_key = data.get('user_key', '').strip().lower()
    if not user_key or user_key == 'default':
        return jsonify({'success': False, 'error': '無效用戶名'})
    if not user_key.isalnum():
        return jsonify({'success': False, 'error': '用戶名只能包含英文字母同數字'})
    conn = _get_db()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO allowed_users (user_key) VALUES (?)', [user_key])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'已新增用戶 {user_key}', 'user_key': user_key})
    except:
        conn.close()
        return jsonify({'success': False, 'error': '用戶名已存在'})

@cooking_bp.route('/api/admin/user/<user_key>/remove', methods=['POST'])
def admin_remove_allowed(user_key):
    if not _admin_check(request):
        return jsonify({'success': False, 'error': '密碼錯誤'})
    if user_key == 'default':
        return jsonify({'success': False, 'error': '不能移除 default'})
    conn = _get_db()
    c = conn.cursor()
    c.execute('DELETE FROM allowed_users WHERE user_key = ?', [user_key])
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': f'已停用 {user_key}'})

@cooking_bp.route('/api/admin/user/<user_key>/delete', methods=['POST'])
def admin_delete_user(user_key):
    if not _admin_check(request):
        return jsonify({'success': False, 'error': '密碼錯誤'})
    if user_key == 'default':
        return jsonify({'success': False, 'error': '不能刪除 default user'})
    conn = _get_db()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM bookmarks WHERE user_key = ?', [user_key])
        bm = c.rowcount
        c.execute('DELETE FROM user_recipes WHERE user_key = ?', [user_key])
        ur = c.rowcount
        c.execute('DELETE FROM allowed_users WHERE user_key = ?', [user_key])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'已刪除 {user_key}({bm} bookmarks, {ur} recipes)'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

# ===== ADMIN: Recipe database management =====

@cooking_bp.route('/api/admin/recipes', methods=['POST'])
def admin_list_recipes():
    """List all user-contributed recipes in the shared DB (admin only)."""
    if not _admin_check(request):
        return jsonify({'success': False, 'error': '密碼錯誤'})
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM recipes WHERE source != 'seed' ORDER BY created_at DESC")
    recipes = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'recipes': recipes})

@cooking_bp.route('/api/admin/recipes/<int:recipe_id>/edit', methods=['POST'])
def admin_edit_recipe(recipe_id):
    """Admin edit any recipe in the shared DB."""
    if not _admin_check(request):
        return jsonify({'success': False, 'error': '密碼錯誤'})
    data = request.get_json() or {}
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM recipes WHERE id = ?', [recipe_id])
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    try:
        fields = ['name', 'cuisine', 'cooking_method', 'taste', 'nutrition_tags',
                  'prep_time_min', 'ingredients', 'steps', 'tips', 'servings',
                  'is_spicy', 'can_prep_early', 'kid_friendly']
        updates = []
        params = []
        for f in fields:
            if f in data:
                updates.append(f'{f} = ?')
                params.append(data[f])
        if not updates:
            conn.close()
            return jsonify({'success': False, 'error': 'No fields to update.'})
        params.append(recipe_id)
        sql = f'UPDATE recipes SET {", ".join(updates)} WHERE id = ?'
        c.execute(sql, params)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '已更新!'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/admin/recipes/<int:recipe_id>/delete', methods=['POST'])
def admin_delete_recipe(recipe_id):
    """Admin delete any recipe from the shared DB (keeps original in user_recipes)."""
    if not _admin_check(request):
        return jsonify({'success': False, 'error': '密碼錯誤'})
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT id, name FROM recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    try:
        # Clear references from user_recipes
        c.execute('UPDATE user_recipes SET db_recipe_id = NULL WHERE db_recipe_id = ?', [recipe_id])
        # Remove bookmarks
        c.execute('DELETE FROM bookmarks WHERE recipe_id = ?', [recipe_id])
        # Delete the recipe
        c.execute('DELETE FROM recipes WHERE id = ?', [recipe_id])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'已從食譜庫刪除「{r["name"]}」'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})
