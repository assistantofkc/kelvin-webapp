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
    MINIMAX_API_URL = os.environ.get('MINIMAX_API_URL', 'https://generativelanguage.googleapis.com')

# App version
APP_VERSION = 'v3.0'


def generate_quiz_questions(vocabularies):
    """使用 Gemini API 生成中文詞彙測驗題目"""
    print(f"[DEBUG] generate_quiz_questions called")
    
    if not vocabularies:
        print("[DEBUG] Empty vocabularies")
        return []
    
    vocab_list = [v.strip() for v in re.split(r'[\n\s]+', vocabularies) if v.strip()]
    print(f"[DEBUG] Split into {len(vocab_list)} vocabularies")
    
    if not vocab_list:
        return []
    
    all_questions = []
    batch_size = 5
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Gemini API endpoint
    gemini_api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not gemini_api_key:
        gemini_api_key = 'AIzaSyC9aEJ_GD92Rb0M6HKXAmwQPDZgQHRXKCw'  # fallback
    gemini_url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_api_key}'
    
    for i in range(0, len(vocab_list), batch_size):
        batch = vocab_list[i:i + batch_size]
        vocab_str = ' '.join(batch)
        print(f"[DEBUG] Processing batch {i//batch_size + 1}: {batch}")
        
        prompt = f"""給定以下中文詞彙：{vocab_str}

請為每個詞彙生成一道「選詞填空」題目。

要求：
1. 每個題目是一個句子，空格用_____表示
2. 4個選項(A/B/C/D)，只有1個正確答案
3. 答案必須是輸入詞彙的其中一個
4. 每個干擾選項必須是另一個詞彙的意思，看起來合理但不正確

嚴格按照以下JSON格式輸出，唔好加任何其他文字：
{{
  "questions": [
    {{
      "vocabulary": "詞彙",
      "sentence": "包含_____的完整句子",
      "options": {{"A": "選項1", "B": "選項2", "C": "選項3", "D": "正確答案"}},
      "correct": "D"
    }}
  ]
}}"""
        
        payload = {
            'contents': [{
                'parts': [{'text': prompt}]
            }],
            'generationConfig': {
                'temperature': 0.5,
                'maxOutputTokens': 2048
            }
        }
        
        try:
            print(f"[DEBUG] Calling Gemini API...")
            response = requests.post(
                gemini_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            print(f"[DEBUG] Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[DEBUG] API Error: {response.text[:300]}")
                continue
            
            result = response.json()
            
            # Gemini returns text in candidates[0].content.parts[0].text
            try:
                content = result['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError) as e:
                print(f"[DEBUG] Failed to extract content: {e}")
                print(f"[DEBUG] Result: {result}")
                continue
            
            print(f"[DEBUG] Content length: {len(content)}")
            print(f"[DEBUG] Content preview: {content[:200]}...")
            
            if not content:
                continue
            
            # Extract JSON
            content = re.sub(r'```json', '', content, flags=re.IGNORECASE)
            content = re.sub(r'```', '', content, flags=re.IGNORECASE)
            
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                print(f"[DEBUG] No JSON found")
                continue
            
            json_str = content[start:end]
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            print(f"[DEBUG] JSON length: {len(json_str)}")
            
            data = json.loads(json_str)
            questions = data.get('questions', [])
            
            print(f"[DEBUG] Got {len(questions)} questions")
            
            if questions:
                # Shuffle options
                for q in questions:
                    options = q.get('options', {})
                    correct_key = q.get('correct', 'A')
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
                print(f"[DEBUG] Batch SUCCESS")
        
        except requests.exceptions.Timeout:
            print(f"[DEBUG] Request timed out")
        except Exception as e:
            print(f"[DEBUG] Error: {e}")
    
    random.shuffle(all_questions)
    print(f"[DEBUG] Total questions: {len(all_questions)}")
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
