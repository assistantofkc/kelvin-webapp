"""
Cooking Ideas - Blueprint + Routes
Single module pattern (matches pronunciation_bp.py)
"""
import json, re, os, secrets
import requests as req
from flask import Blueprint, render_template, request, jsonify

cooking_bp = Blueprint('cooking', __name__, template_folder='../templates/cooking', static_folder='../static/cooking')

MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '').strip()
MINIMAX_URL = 'https://api.minimax.io/v1/text/chatcompletion_v2?GroupId=2043608871905276295'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
GEMINI_MODEL = 'gemini-2.5-flash-lite'
GEMINI_URL = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent'

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
    if spicy == 'yes':
        query += ' AND is_spicy = 1'
    elif spicy == 'no':
        query += ' AND is_spicy = 0'
    
    nutrition = data.get('nutrition', [])
    for n in nutrition:
        query += ' AND nutrition_tags LIKE ?'
        params.append(f'%{n}%')
    
    max_time = data.get('max_time', 60)
    query += ' AND prep_time_min <= ?'
    params.append(max_time)
    
    prep_early = data.get('prep_early')
    if prep_early == 'yes':
        query += ' AND can_prep_early = 1'
    
    count = min(int(data.get('count', 3)), 10)
    
    # Existing ingredients - parse and score recipes by ingredient overlap
    have_ingredients = data.get('ingredients', '').strip()
    have_list = []
    if have_ingredients:
        have_list = [x.strip().lower() for x in re.split(r'[,，、\s]+', have_ingredients) if x.strip()]
    
    c.execute(query, params)
    all_candidates = [dict(r) for r in c.fetchall()]
    
    if not all_candidates:
        conn.close()
        return jsonify({'success': False, 'error': '未找到符合條件嘅食譜，試下放寬篩選條件。'})
    
    # Score & sort by ingredient overlap if user provided ingredients
    if have_list:
        for r in all_candidates:
            recipe_ingredients = r['ingredients'].lower()
            score = sum(1 for item in have_list if item in recipe_ingredients)
            r['_score'] = score
        all_candidates.sort(key=lambda r: r.get('_score', 0), reverse=True)
        # Only keep recipes that match at least 1 ingredient (if >0 matches exist)
        has_matches = [r for r in all_candidates if r.get('_score', 0) > 0]
        if has_matches:
            all_candidates = has_matches
    
    selected = []
    remaining = list(all_candidates)
    
    wants_soup = data.get('include_soup', False)
    wants_cold = data.get('include_cold', False)
    
    if wants_soup:
        soups = [r for r in remaining if r['has_soup'] == 1]
        if soups:
            chosen = secrets.choice(soups)
            selected.append(chosen)
            remaining.remove(chosen)
    
    if wants_cold:
        colds = [r for r in remaining if r['has_cold_dish'] == 1]
        if colds:
            chosen = secrets.choice(colds)
            selected.append(chosen)
            remaining.remove(chosen)
    
    for _ in range(count - len(selected)):
        if not remaining:
            break
        chosen = secrets.choice(remaining)
        selected.append(chosen)
        remaining.remove(chosen)
    
    result = [{k: r[k] for k in r.keys() if not k.startswith('_')} for r in selected]
    conn.close()
    return jsonify({'success': True, 'dishes': result})

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
             prep_time_min, can_prep_early, is_spicy, ingredients, steps, tips, source, servings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ai_custom', ?)
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

@cooking_bp.route('/api/recipe/<int:recipe_id>')
def get_recipe(recipe_id):
    conn = _get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    conn.close()
    
    if r:
        return jsonify({'success': True, 'recipe': dict(r)})
    return jsonify({'success': False, 'error': 'Recipe not found.'})

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
