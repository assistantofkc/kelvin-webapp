"""
Cooking Ideas - Routes
"""
import json, re, os, secrets
import requests as req
from flask import render_template, request, jsonify
from .models import get_db, init_db

MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '').strip()
MINIMAX_URL = 'https://api.minimax.io/v1/text/chatcompletion_v2?GroupId=2043608871905276295'

def _init():
    """Initialize database on first load."""
    try:
        init_db()
    except:
        pass

_init()

@cooking_bp.route('/')
def index():
    return render_template('cooking/index.html')

@cooking_bp.route('/api/random', methods=['POST'])
def random_recipes():
    """Generate random dishes based on user preferences."""
    data = request.get_json() or {}
    
    conn = get_db()
    c = conn.cursor()
    
    query = 'SELECT * FROM recipes WHERE 1=1'
    params = []
    
    # Cuisine filter
    cuisines = data.get('cuisines', [])
    if cuisines:
        placeholders = ','.join(['?'] * len(cuisines))
        query += f' AND cuisine IN ({placeholders})'
        params.extend(cuisines)
    
    # Cooking method filter
    methods = data.get('methods', [])
    if methods:
        placeholders = ','.join(['?'] * len(methods))
        query += f' AND cooking_method IN ({placeholders})'
        params.extend(methods)
    
    # Taste filter
    tastes = data.get('tastes', [])
    if tastes:
        taste_conditions = []
        for t in tastes:
            taste_conditions.append('taste = ?')
            params.append(t)
        query += f' AND ({" OR ".join(taste_conditions)})'
    
    # Spicy filter
    spicy = data.get('spicy')
    if spicy == 'yes':
        query += ' AND is_spicy = 1'
    elif spicy == 'no':
        query += ' AND is_spicy = 0'
    
    # Nutrition filter
    nutrition = data.get('nutrition', [])
    for n in nutrition:
        query += ' AND nutrition_tags LIKE ?'
        params.append(f'%{n}%')
    
    # Prep time filter
    max_time = data.get('max_time', 60)
    query += ' AND prep_time_min <= ?'
    params.append(max_time)
    
    # Prep early filter
    prep_early = data.get('prep_early')
    if prep_early == 'yes':
        query += ' AND can_prep_early = 1'
    
    # Number of dishes
    count = min(int(data.get('count', 3)), 10)
    
    c.execute(query, params)
    all_candidates = [dict(r) for r in c.fetchall()]
    
    if not all_candidates:
        conn.close()
        return jsonify({'success': False, 'error': '未找到符合條件嘅食譜，試下放寬篩選條件。'})
    
    # Random selection
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
    
    result = [{k: r[k] for k in r.keys()} for r in selected]
    
    conn.close()
    return jsonify({'success': True, 'dishes': result})

@cooking_bp.route('/api/search', methods=['POST'])
def ai_search():
    """AI recipe search using MiniMax."""
    data = request.get_json() or {}
    dish_name = data.get('dish_name', '').strip()
    
    if not dish_name:
        return jsonify({'success': False, 'error': '請輸入菜式名稱。'})
    
    if not MINIMAX_API_KEY:
        return jsonify({'success': False, 'error': 'AI search not configured.'})
    
    prompt = f"""Please provide a complete recipe for "{dish_name}" in Traditional Chinese (繁體中文).

Output ONLY valid JSON, no other text:
{{
  "name": "菜名",
  "name_en": "English name",
  "cuisine": "中式/西式/日式/東南亞",
  "cooking_method": "蒸/炒/炆/燉/煎/焗/炸",
  "taste": "清淡/濃味/辣",
  "nutrition_tags": "營養標籤 (e.g. 菜,魚,白肉,紅肉,澱粉質,蛋白質)",
  "prep_time_min": 數字(分鐘),
  "can_prep_early": 0或1,
  "is_spicy": 0或1,
  "ingredients": "材料列表(每項用逗號分隔)",
  "steps": "步驟(每步用換行分隔)",
  "tips": "小貼士",
  "servings": 4
}}

Rules:
- ALL text must be Traditional Chinese (繁體中文)
- Steps should be numbered with newlines
- Give realistic, practical recipes"""

    try:
        headers = {
            'Authorization': f'Bearer {MINIMAX_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'MiniMax-M2.7',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.3,
            'max_tokens': 2000
        }
        
        response = req.post(MINIMAX_URL, headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            return jsonify({'success': False, 'error': f'AI API error: {response.status_code}'})
        
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if not content:
            return jsonify({'success': False, 'error': 'No response from AI.'})
        
        # Parse JSON
        content = re.sub(r'```json', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content, flags=re.IGNORECASE)
        start = content.find('{')
        end = content.rfind('}') + 1
        if start == -1 or end == 0:
            return jsonify({'success': False, 'error': 'AI response format error.'})
        
        recipe = json.loads(content[start:end])
        recipe['source'] = 'ai_search'
        recipe['from_ai'] = True
        
        return jsonify({'success': True, 'recipe': recipe})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@cooking_bp.route('/api/save', methods=['POST'])
def save_recipe():
    """Save an AI-generated recipe to the database."""
    data = request.get_json() or {}
    
    if not data.get('name'):
        return jsonify({'success': False, 'error': 'Recipe name required.'})
    
    conn = get_db()
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
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM recipes WHERE id = ?', [recipe_id])
    r = c.fetchone()
    conn.close()
    
    if r:
        return jsonify({'success': True, 'recipe': dict(r)})
    return jsonify({'success': False, 'error': 'Recipe not found.'})
