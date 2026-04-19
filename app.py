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
APP_VERSION = 'v2.14'


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
    batch_size = 4  # Reduced to ensure reliable JSON
    
    headers = {
        'Authorization': f'Bearer {MINIMAX_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    mini_max_url = 'https://api.minimax.io/v1/text/chatcompletion_v2?GroupId=2043608871905276295'
    
    # System message (MiniMax responds better with this)
    system_msg = "你是一個專業的中文詞彙測驗題目生成器。你必須嚴格按照指定的JSON格式輸出，唔好添加任何額外文字、解釋或markdown。"
    
    # Process in batches
    for i in range(0, len(vocab_list), batch_size):
        batch = vocab_list[i:i+batch_size]
        vocab_str = ' '.join(batch)
        print(f"[DEBUG] Processing batch {i//batch_size + 1}: {batch}")
        
        # Stronger prompt with exact JSON example
        prompt = f"""給定以下中文詞彙：{vocab_str}

請為每個詞彙生成一道「選詞填空」題目。

嚴格要求：
1. 每個題目是一個句子，空格用_____表示
2. 4個選項(A/B/C/D)，只有1個正確答案
3. 答案必須是輸入詞彙的其中一個
4. 每個干擾選項必須是另一個詞彙的意思，看起來合理但不正確

嚴格按照以下JSON格式輸出，唔好加任何其他文字：

舉例：如果詞彙是「經歷 糾結 挫敗」
輸出必須是：
{{"questions": [
  {{"vocabulary": "經歷", "sentence": "他_____了很多困難終於成功", "options": {{"A": "描述困難", "B": "親身體驗", "C": "放棄", "D": "逃避"}}, "correct": "B"}},
  {{"vocabulary": "糾結", "sentence": "這個決定讓我非常_____", "options": {{"A": "開心", "B": "果斷", "C": "矛盾難抉擇", "D": "輕鬆"}}, "correct": "C"}},
  {{"vocabulary": "挫敗", "sentence": "連續失敗讓他感到_____", "options": {{"A": "振奮", "B": "成功", "C": "失落失敗", "D": "滿足"}}, "correct": "C"}}
]}}

而家輪到你。詞彙：{vocab_str}"""
        
        mini_max_payload = {
            'model': 'MiniMax-M2.7',
            'messages': [
                {'role': 'system', 'content': system_msg},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3,  # Lower temp = more predictable output
            'max_tokens': 2000
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
                    print(f"[DEBUG] API Error: {response.text[:300]}")
                    continue
                
                result = response.json()
                message = result.get('choices', [{}])[0].get('message', {})
                content = message.get('content', '')
                
                print(f"[DEBUG] Content length: {len(content)}")
                print(f"[DEBUG] Content preview: {content[:200]}...")
                
                if not content:
                    print(f"[DEBUG] Empty content")
                    continue
                
                # Better JSON extraction
                json_str = None
                
                # Remove markdown code blocks first
                content_clean = content.replace('```json', '').replace('```', '').strip()
                
                # Find JSON block
                start = content_clean.find('{')
                end = content_clean.rfind('}') + 1
                if start != -1 and end > start:
                    json_str = content_clean[start:end]
                
                if not json_str:
                    print(f"[DEBUG] No JSON found in: {content_clean[:200]}")
                    continue
                
                print(f"[DEBUG] JSON str length: {len(json_str)}")
                
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON parse error: {e}")
                    print(f"[DEBUG] JSON string: {json_str[:300]}")
                    continue
                
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
                    success = True
                    print(f"[DEBUG] Batch {i//batch_size + 1} SUCCESS with {len(questions)} questions")
                    break
                
            except requests.exceptions.Timeout:
                print(f"[DEBUG] Batch {i//batch_size + 1} timed out")
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
            'error': '生成題目失敗，請稍後再試'
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
