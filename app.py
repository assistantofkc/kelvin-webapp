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
APP_VERSION = 'v2.12'


def generate_quiz_questions(vocabularies, max_retries=2):
    """
    Use MiniMax API to generate multiple choice questions for Chinese vocabularies.
    Processes vocabularies in batches to avoid timeout.
    """
    print(f"[DEBUG] generate_quiz_questions called")
    
    if not vocabularies:
        print("[DEBUG] Empty vocabularies")
        return []
    
    # Split vocabularies
    vocab_list = [v.strip() for v in re.split(r'[\n\s]+', vocabularies) if v.strip()]
    print(f"[DEBUG] Split into {len(vocab_list)} vocabularies")
    
    if not vocab_list:
        return []
    
    all_questions = []
    batch_size = 5  # Process 5 words at a time
    
    headers = {
        'Authorization': f'Bearer {MINIMAX_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    mini_max_url = 'https://api.minimax.io/v1/text/chatcompletion_v2?GroupId=2043608871905276295'
    
    # Process in batches
    for i in range(0, len(vocab_list), batch_size):
        batch = vocab_list[i:i+batch_size]
        vocab_str = ' '.join(batch)
        print(f"[DEBUG] Processing batch {i//batch_size + 1}: {batch}")
        
        prompt = f"""給定以下中文詞彙：{vocab_str}

請為每個詞彙生成一道「選詞填空」題目。

要求：
- 每個題目是一個句子，空格用_____表示
- 4個選項，只有1個正確答案
- 答案必須係輸入詞彙嘅其中一個

JSON格式：
{{"questions": [{{"vocabulary": "詞", "sentence": "句___子", "options": {{"A":"選","B":"項","C":"干","D":"擾"}}, "correct": "A"}}]}}

嚴格只輸出JSON，唔好加其他文字。"""
        
        mini_max_payload = {
            'model': 'MiniMax-M2.7',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 1000
        }
        
        success = False
        for attempt in range(max_retries):
            try:
                print(f"[DEBUG] Batch {i//batch_size + 1} attempt {attempt + 1}")
                response = requests.post(
                    mini_max_url,
                    headers=headers,
                    json=mini_max_payload,
                    timeout=60
                )
                
                print(f"[DEBUG] Batch {i//batch_size + 1} status: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"[DEBUG] API Error: {response.text[:200]}")
                    continue
                
                result = response.json()
                message = result.get('choices', [{}])[0].get('message', {})
                content = message.get('content', '')
                
                if not content:
                    continue
                
                # Extract JSON
                start = content.find('{')
                end = content.rfind('}') + 1
                if start == -1:
                    continue
                
                json_str = content[start:end]
                data = json.loads(json_str)
                questions = data.get('questions', [])
                
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
                    success = True
                    print(f"[DEBUG] Batch {i//batch_size + 1} got {len(questions)} questions")
                    break
                
            except Exception as e:
                print(f"[DEBUG] Batch error: {e}")
                continue
        
        if not success:
            print(f"[DEBUG] Batch {i//batch_size + 1} failed after {max_retries} attempts")
    
    random.shuffle(all_questions)
    print(f"[DEBUG] Total questions: {len(all_questions)}")
    return all_questions


@app.route('/')
def index():
    """Home page"""
    return render_template('index.html', version=APP_VERSION)


@app.route('/vocab-test')
def vocab_test():
    """Chinese Vocabulary Test page"""
    return render_template('vocab_test.html', version=APP_VERSION)


@app.route('/api/generate-quiz', methods=['POST'])
def api_generate_quiz():
    """API endpoint to generate quiz questions."""
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
            'error': '生成題目失敗，請嘗試減少詞彙數量（最多10個）'
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
