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

@cooking_bp.route('/')
def index():
    return render_template('cooking/index.html')

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
        allergy_list = [x.strip().lower() for x in re.split(r'[,，、\s]+', allergies) if x.strip()]
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
        have_list = [x.strip().lower() for x in re.split(r'[,，、\s]+', have_ingredients) if x.strip()]
    
    c.execute(query, params)
    all_candidates = [dict(r) for r in c.fetchall()]
    
    if not all_candidates:
        conn.close()
        return jsonify({'success': False, 'error': '未找到符合條件嘅食譜，試下放寬篩選條件。'})
    
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
        return jsonify({'success': False, 'error': '未找到符合條件嘅食譜，試下放寬篩選條件。'})
    
    # Build meal plan: distribute nutrition across dishes
    selected = []
    used_nutrition = set()
    
    # Step 1: Pick soup if requested
    if wants_soup:
        soups = [r for r in all_candidates if r['has_soup'] == 1 and r['id'] not in {s['id'] for s in selected}]
        if soups:
            soups.sort(key=lambda r: r.get('_score', 0), reverse=True)
            selected.append(soups[0])
            # Don't pick another soup for remaining slots
            all_candidates = [r for r in all_candidates if r['has_soup'] == 0 or r['id'] == soups[0]['id']]
    
    # Step 2: Pick cold dish if requested
    if wants_cold:
        colds = [r for r in all_candidates if r['has_cold_dish'] == 1 and r['id'] not in {s['id'] for s in selected}]
        if colds:
            colds.sort(key=lambda r: r.get('_score', 0), reverse=True)
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
        
        if not candidates:
            continue  # skip if no match
        
        # Sort by score and avoid already-used nutrition when possible
        candidates.sort(key=lambda r: r.get('_score', 0), reverse=True)
        
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
        return jsonify({'success': False, 'error': '未能組合出合適嘅餐單，試下放寬篩選條件。'})
    
    # Pure vegetable rule: when total dishes ≤ 4, at most 1 pure vegetable dish
    # Pure veg = nutrition_tags exactly '菜' (蕃茄/番茄 NOT pure veg)
    if count <= 4:
        TOMATO_KW = ['蕃茄', '番茄']
        def _is_pure_veg(dish):
            name = dish.get('name', '')
            nt = dish.get('nutrition_tags', '').strip()
            if nt != '菜':
                return False
            for tk in TOMATO_KW:
                if tk in name:
                    return False
            return True
        pv_indices = [i for i, d in enumerate(selected) if _is_pure_veg(d)]
        if len(pv_indices) > 1:
            # Keep first pure veg, replace others with non-pure-veg alternatives
            for pvi in pv_indices[1:]:
                alt = [r for r in all_candidates
                       if r['id'] not in {s['id'] for s in selected}
                       and not _is_pure_veg(r)]
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
        allergy_list = [x.strip().lower() for x in re.split(r'[,，、\s]+', allergies) if x.strip()]
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
        have_list = [x.strip().lower() for x in re.split(r'[,，、\s]+', have_ingredients) if x.strip()]
    
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
    
    # Pure vegetable: nutrition_tags is exactly '菜' (no protein/starch tags)
    # 蕃茄/番茄 dishes are NOT pure veg even if tags='菜'
    TOMATO_KW = ['蕃茄', '番茄']
    def _is_pure_veg(dish):
        name = dish.get('name', '')
        nt = dish.get('nutrition_tags', '').strip()
        if nt != '菜':
            return False
        for tk in TOMATO_KW:
            if tk in name:
                return False
        return True
    
    # Count pure veg in current dishes (excluding the one being replaced)
    pv_count_others = 0
    for i, rid in enumerate(current_ids):
        if i == replace_idx:
            continue
        for r in all_candidates:
            if r['id'] == rid:
                if _is_pure_veg(r):
                    pv_count_others += 1
                break
    
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
        # Prefer same dish type: 湯→湯, pure veg→pure veg, 澱粉質→澱粉質
        if replaced_dish:
            if _is_pure_veg(replaced_dish) and _is_pure_veg(c):
                score += 4
            replaced_starch = '澱粉質' in replaced_dish.get('nutrition_tags', '')
            cand_starch = '澱粉質' in c.get('nutrition_tags', '')
            if replaced_starch and cand_starch:
                score += 4
        # Avoid new dish being pure veg if we already have one
        if count <= 4 and _is_pure_veg(c) and pv_count_others >= 1:
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
    # (recycling is OK — A→B→C→A — just avoid immediate A→B→A bounce)
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

    prompt = f"""Generate a complete recipe for "{dish_name}" in Traditional Chinese (繁體中文).

Output ONLY valid JSON, no markdown, no explanation:

{{
  "name": "菜名",
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
}}

Rules:
- ALL text MUST be Traditional Chinese (繁體中文)
- Steps numbered, separated by \\n
- Give realistic home-cooking recipes
- kid_friendly=1 if non-spicy AND no alcohol (酒/清酒/味醂/紹興酒/料酒) in ingredients, otherwise 0
- Output ONLY the JSON, nothing else"""

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
                return jsonify({'success': False, 'error': f'內容被攔截：{block_reason}。請嘗試其他菜式名稱。'})
            return jsonify({'success': False, 'error': 'No response from AI.'})

        content = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')

        if not content:
            finish_reason = candidates[0].get('finishReason', 'unknown')
            if finish_reason == 'SAFETY':
                return jsonify({'success': False, 'error': 'AI 無法生成此食譜（安全限制）。請嘗試其他菜式名稱。'})
            return jsonify({'success': False, 'error': 'AI 未返回內容，請再試。'})

        # Clean JSON
        content = re.sub(r'```json', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content, flags=re.IGNORECASE)
        content = content.strip()
        start = content.find('{')
        end = content.rfind('}') + 1
        if start == -1 or end == 0:
            return jsonify({'success': False, 'error': 'AI response format error.'})

        recipe = json.loads(content[start:end])
        recipe['source'] = 'ai_search'
        recipe['from_ai'] = True

        return jsonify({'success': True, 'recipe': recipe})

    except req.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'AI 搜尋超時（35秒），請用更簡單嘅菜式名再試。'})
    except req.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': f'網絡錯誤，請再試。'})
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'AI 回覆格式錯誤，請再試。'})
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
             prep_time_min, can_prep_early, is_spicy, kid_friendly, ingredients, steps, tips, source, servings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ai_custom', ?)
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
            data.get('servings', 4)
        ))
        conn.commit()
        new_id = c.lastrowid
        
        c.execute('INSERT INTO custom_dishes (name, recipe_id) VALUES (?, ?)',
                  (data['name'], new_id))
        conn.commit()
        
        conn.close()
        return jsonify({'success': True, 'id': new_id, 'message': '已儲存！'})
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
        return jsonify({'success': True, 'message': '已更新！'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/recipe/<int:recipe_id>/delete', methods=['POST'])
def delete_recipe(recipe_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT id, source, name FROM recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    if r['source'] == 'seed':
        conn.close()
        return jsonify({'success': False, 'error': '不能刪除內置食譜，只可以刪除 AI 加入嘅食譜。'})
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
    data = request.get_json() or {}
    recipe_id = data.get('recipe_id')
    if not recipe_id:
        return jsonify({'success': False, 'error': 'Recipe ID required.'})
    conn = _get_db()
    c = conn.cursor()
    try:
        c.execute('SELECT id FROM bookmarks WHERE recipe_id = ?', [recipe_id])
        existing = c.fetchone()
        if existing:
            c.execute('DELETE FROM bookmarks WHERE recipe_id = ?', [recipe_id])
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'bookmarked': False, 'message': '已移除收藏'})
        else:
            c.execute('INSERT INTO bookmarks (recipe_id) VALUES (?)', [recipe_id])
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'bookmarked': True, 'message': '已收藏！'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/bookmarks', methods=['GET'])
def list_bookmarks():
    conn = _get_db()
    c = conn.cursor()
    c.execute('''
        SELECT r.*, b.created_at as bookmarked_at
        FROM bookmarks b
        JOIN recipes r ON b.recipe_id = r.id
        ORDER BY b.created_at DESC
    ''')
    recipes = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'bookmarks': recipes})

@cooking_bp.route('/api/bookmark/status', methods=['POST'])
def bookmark_status():
    """Batch check bookmark status for a list of recipe IDs."""
    data = request.get_json() or {}
    recipe_ids = data.get('recipe_ids', [])
    if not recipe_ids:
        return jsonify({'success': True, 'bookmarked': {}})
    conn = _get_db()
    c = conn.cursor()
    placeholders = ','.join(['?'] * len(recipe_ids))
    c.execute(f'SELECT recipe_id FROM bookmarks WHERE recipe_id IN ({placeholders})', recipe_ids)
    bookmarked = {str(r['recipe_id']): True for r in c.fetchall()}
    conn.close()
    return jsonify({'success': True, 'bookmarked': bookmarked})

@cooking_bp.route('/api/search-db', methods=['POST'])
def search_db():
    """Search recipes in the database by name or ingredients."""
    data = request.get_json() or {}
    query = data.get('q', '').strip()
    if not query:
        return jsonify({'success': False, 'error': '請輸入搜尋關鍵字。'})
    
    conn = _get_db()
    c = conn.cursor()
    # Search in name, ingredients, and cuisine
    like = f'%{query}%'
    c.execute('''
        SELECT * FROM recipes 
        WHERE name LIKE ? OR ingredients LIKE ? OR cuisine LIKE ?
        ORDER BY 
            CASE WHEN name LIKE ? THEN 0 ELSE 1 END,
            name
        LIMIT 20
    ''', (like, like, like, like))
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
        
        return jsonify({'success': True, 'recipe': recipe})

    except req.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'AI 搜尋超時，請再試。'})
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'AI 回覆格式錯誤，請再試。'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


    except req.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'AI 搜尋超時，請再試。'})
    except json.JSONDecodeError as e:
        return jsonify({'success': False, 'error': f'AI 回覆格式錯誤，請再試。'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ===== USER RECIPES (創建菜式) =====

@cooking_bp.route('/api/user-recipes', methods=['GET', 'POST'])
def user_recipes():
    if request.method == 'GET':
        conn = _get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM user_recipes ORDER BY created_at DESC')
        recipes = [dict(r) for r in c.fetchall()]
        conn.close()
        return jsonify({'success': True, 'recipes': recipes})
    elif request.method == 'POST':
        data = request.get_json() or {}
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Recipe name required.'})
        conn = _get_db()
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO user_recipes (name, cuisine, cooking_method, taste, nutrition_tags,
                    prep_time_min, ingredients, steps, tips, servings, creator, image_base64, is_spicy, can_prep_early, kid_friendly)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['name'], data.get('cuisine', '中式'), data.get('cooking_method', '炒'),
                data.get('taste', '清淡'), data.get('nutrition_tags', ''),
                data.get('prep_time_min', 30), data.get('ingredients', ''),
                data.get('steps', ''), data.get('tips', ''),
                data.get('servings', 4), data.get('creator', ''),
                data.get('image_base64', ''), data.get('is_spicy', 0), data.get('can_prep_early', 0),
                data.get('kid_friendly', 1)
            ))
            conn.commit()
            new_id = c.lastrowid
            conn.close()
            return jsonify({'success': True, 'id': new_id, 'message': '已創建！'})
        except Exception as e:
            conn.close()
            return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/user-recipes/<int:recipe_id>/edit', methods=['POST'])
def edit_user_recipe(recipe_id):
    data = request.get_json() or {}
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM user_recipes WHERE id = ?', [recipe_id])
    if not c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
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
        return jsonify({'success': True, 'message': '已更新！'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/user-recipes/<int:recipe_id>/delete', methods=['POST'])
def delete_user_recipe(recipe_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT id, name FROM user_recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
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
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM user_recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
    if r['db_recipe_id']:
        conn.close()
        return jsonify({'success': False, 'error': '已經加入過食譜庫。'})
    try:
        c.execute('''
            INSERT INTO recipes (name, cuisine, cooking_method, taste, nutrition_tags,
                prep_time_min, can_prep_early, is_spicy, kid_friendly, ingredients, steps, tips, source, servings, image_base64)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'user_created', ?, ?)
        ''', (
            r['name'], r['cuisine'], r['cooking_method'], r['taste'],
            r['nutrition_tags'], r['prep_time_min'], r['can_prep_early'],
            r['is_spicy'], r['kid_friendly'], r['ingredients'], r['steps'], r['tips'], r['servings'],
            r['image_base64']
        ))
        new_id = c.lastrowid
        c.execute('UPDATE user_recipes SET db_recipe_id = ? WHERE id = ?', [new_id, recipe_id])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': new_id, 'message': f'「{r["name"]}」已加入食譜庫！'})
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/user-recipes/<int:recipe_id>/remove-from-db', methods=['POST'])
def remove_user_recipe_from_db(recipe_id):
    """Remove a previously added recipe from the main recipes table."""
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM user_recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'success': False, 'error': 'Recipe not found.'})
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
