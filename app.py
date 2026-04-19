"""
Personal Homepage with Chinese Vocabulary Test
Flask Web App for PythonAnywhere
"""
from flask import Flask, render_template, request, jsonify
import requests
import random
import json
import os
import re

app = Flask(__name__)

# Import config (contains API keys - server-side only)
try:
    from config import MINIMAX_API_KEY, MINIMAX_API_URL
except ImportError:
    MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '').strip()
    MINIMAX_API_URL = os.environ.get('MINIMAX_API_URL', 'https://api.minimax.io/v1/text/chatcompletion_v2')

# App version
APP_VERSION = 'v2.18'


def generate_quiz_questions(vocabularies, max_retries=3):
    """最終穩定版"""
    print(f"[DEBUG] generate_quiz_questions called")
    
    if not vocabularies:
        return []
    
    vocab_list = [v.strip() for v in re.split(r'[\n\s]+', vocabularies) if v.strip()]
    print(f"[DEBUG] Split into {len(vocab_list)} vocabularies")
    
    if not vocab_list:
        return []
    
    all_questions = []
    batch_size = 4
    headers = {
        'Authorization': f'Bearer {MINIMAX_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    mini_max_url = 'https://api.minimax.io/v1/text/chatcompletion_v2?GroupId=2043608871905276295'
    
    for i in range(0, len(vocab_list), batch_size):
        batch = vocab_list[i:i + batch_size]
        vocab_str = ' '.join(batch)
        print(f"[DEBUG] Processing batch {i//batch_size + 1}: {batch}")
        
        system_prompt = "你是一個嚴格的中文詞彙測驗生成器。只輸出有效的JSON，不要有任何其他文字、解釋或markdown。"
        
        user_prompt = f"""給定詞彙：{vocab_str}

為每個詞彙生成一道選詞填空題。
要求：
- 把該詞彙放在句子中，並用 _____ 代替
- 提供正好 4 個選項 (A B C D)，只有 1 個正確
- 其他 3 個是合理但錯誤的干擾項
- 必須為所有 {len(batch)} 個詞彙都生成題目

嚴格只輸出以下格式的完整 JSON，不要加任何多餘內容：

{{
  "questions": [
    {{
      "vocabulary": "詞彙",
      "sentence": "包含_____的完整自然句子。",
      "options": {{"A": "選項1", "B": "選項2", "C": "選項3", "D": "正確答案"}},
      "correct": "D"
    }}
  ]
}}"""
        
        payload = {
            'model': 'MiniMax-M2.7',
            'messages': [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            'temperature': 0.5,
            'max_tokens': 3000,
            'stream': False
        }
        
        for attempt in range(max_retries):
            try:
                print(f"[DEBUG] Batch {i//batch_size + 1} attempt {attempt + 1}")
                response = requests.post(mini_max_url, headers=headers, json=payload, timeout=70)
                
                if response.status_code != 200:
                    print(f"[DEBUG] API Error {response.status_code}: {response.text[:200]}")
                    continue
                
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                print(f"[DEBUG] Raw content length: {len(content)}")
                
                if not content:
                    continue
                
                # 強力 JSON 清理
                content = re.sub(r'(?:```json)?', '', content, flags=re.IGNORECASE)
                content = re.sub(r'```', '', content, flags=re.IGNORECASE)
                
                # 找出所有 JSON 物件
                json_matches = re.findall(r'\{[\s\S]*?\}', content)
                if not json_matches:
                    print(f"[DEBUG] No JSON found")
                    continue
                
                json_str = json_matches[-1].strip()  # 取最後一個（通常是最完整的）
                
                # 修復常見的截斷問題
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                json_str = re.sub(r'"\s*,\s*"', '", "', json_str)  # 修復可能的引號問題
                
                print(f"[DEBUG] Cleaned JSON length: {len(json_str)}")
                
                data = json.loads(json_str)
                questions = data.get('questions', [])
                
                print(f"[DEBUG] Got {len(questions)} questions from batch")
                
                if questions:
                    # Shuffle options
                    for q in questions:
                        options = q.get('options', {})
                        correct_key = str(q.get('correct', 'A')).strip()
                        correct_text = options.get(correct_key, '')
                        
                        keys = list(options.keys())
                        random.shuffle(keys)
                        
                        new_options = {}
                        new_correct = None
                        for new_key in keys:
                            new_options[new_key] = options[new_key]
                            if options[new_key] == correct_text:
                                new_correct = new_key
                        
                        q['options'] = new_options
                        q['correct'] = new_correct or correct_key
                    
                    all_questions.extend(questions)
                    print(f"[DEBUG] Batch {i//batch_size + 1} SUCCESS")
                    break
            
            except json.JSONDecodeError as e:
                print(f"[DEBUG] JSON parse error: {e}")
            except Exception as e:
                print(f"[DEBUG] Error: {type(e).name}: {e}")
        
        else:
            print(f"[DEBUG] Batch {i//batch_size + 1} failed after {max_retries} attempts")
    
    random.shuffle(all_questions)
    print(f"[DEBUG] Total questions returned: {len(all_questions)}")
    return all_questions


@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION)


@app.route('/vocab-test')
def vocab_test():
    return render_template('vocab_test.html', version=APP_VERSION)


@app.route('/api/generate-quiz', methods=['POST'])
def api_generate_quiz():
    data = request.get_json()
    vocabularies = data.get('vocabularies', '')
    
    if not vocabularies.strip():
        return jsonify({'error': '請輸入中文詞彙'}), 400
    
    questions = generate_quiz_questions(vocabularies)
    
    if questions:
        return jsonify({
            'success': True,
            'questions': questions,
            'total': len(questions)
        })
    else:
        return jsonify({
            'error': '生成題目失敗，請稍後再試'
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
