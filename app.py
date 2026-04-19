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
APP_VERSION = 'v2.16'


def generate_quiz_questions(vocabularies, max_retries=2):
    """
    Fixed version: stronger prompt + system message + robust JSON extraction
    Works reliably for 20+ vocabularies (batches of 5).
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
    batch_size = 5
    headers = {
        'Authorization': f'Bearer {MINIMAX_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    mini_max_url = 'https://api.minimax.io/v1/text/chatcompletion_v2?GroupId=2043608871905276295'
    
    for i in range(0, len(vocab_list), batch_size):
        batch = vocab_list[i:i + batch_size]
        vocab_str = ' '.join(batch)
        print(f"[DEBUG] Processing batch {i//batch_size + 1}/{len(vocab_list)//batch_size + 1}: {batch}")
        
        # === STRONGER PROMPT (this is the key fix) ===
        system_prompt = (
            "你是一個專業的中文詞彙測驗題目生成器。\n"
            "你必須嚴格只輸出有效的JSON，不要有任何額外文字、解釋、markdown或json標記。"
        )
        
        user_prompt = f"""給定以下中文詞彙：{vocab_str}

請為每個詞彙生成一道「選詞填空」題目。
要求：
- 每個題目必須使用該詞彙做成一個自然句子，把該詞彙替換成「_____」
- 提供正好4個選項 (A、B、C、D)，只有1個是正確答案
- 其他3個是合理的干擾項（意思相近但不同）
- 答案必須是原本輸入的詞彙之一

嚴格按照以下格式輸出，不要加任何其他內容：

{{
  "questions": [
    {{
      "vocabulary": "詞彙1",
      "sentence": "這是一個包含_____的完整句子。",
      "options": {{
        "A": "干擾選項1",
        "B": "干擾選項2",
        "C": "干擾選項3",
        "D": "正確答案"
      }},
      "correct": "D"
    }}
  ]
}}"""
        
        mini_max_payload = {
            'model': 'MiniMax-M2.7',
            'messages': [
                {"role": "system", "name": "QuizGenerator", "content": system_prompt},
                {"role": "user", "name": "User", "content": user_prompt}
            ],
            'temperature': 0.5,  # more stable output
            'max_tokens': 2000,  # increased — very important for 5 questions
            'stream': False
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
                
                print(f"[DEBUG] Status: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"[DEBUG] API Error: {response.text[:300]}")
                    continue
                
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                print(f"[DEBUG] Raw content length: {len(content)} | First 200 chars: {content[:200]}")
                
                if not content:
                    continue
                
                # === 改進後的 JSON 提取（更穩健）===
                # 先移除 markdown code blocks
                content = re.sub(r'```json', '', content, flags=re.IGNORECASE)
                content = re.sub(r'```', '', content, flags=re.IGNORECASE)  # 移除結尾
                
                # 再找出整個 JSON 物件（最可靠的方法）
                json_match = re.search(r'\{[\s\S]*?\}', content)  # 非貪婪模式，匹配第一個完整的 {}
                if not json_match:
                    print(f"[DEBUG] No JSON object found in content")
                    print(f"[DEBUG] Content preview: {content[:300]}")
                    continue
                
                json_str = json_match.group(0).strip()
                
                # 額外清理（防止有些模型會加逗號或多餘符號）
                json_str = re.sub(r',\s*}', '}', json_str)  # 移除最後一個多餘逗號
                json_str = re.sub(r',\s*]', ']', json_str)
                
                print(f"[DEBUG] Cleaned JSON length: {len(json_str)} | Preview: {json_str[:150]}...")
                
                try:
                    data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON parse error after cleaning: {e}")
                    print(f"[DEBUG] Problematic JSON: {json_str[:500]}")
                    continue
                
                questions = data.get('questions', [])
                
                print(f"[DEBUG] Parsed {len(questions)} questions from batch")
                
                if questions:
                    # Shuffle options inside each question
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
                    print(f"[DEBUG] Batch {i//batch_size + 1} SUCCESS ✅")
                    break
            
            except requests.exceptions.Timeout:
                print(f"[DEBUG] Batch timed out")
            except json.JSONDecodeError as e:
                print(f"[DEBUG] JSON decode error: {e}")
            except Exception as e:
                print(f"[DEBUG] Unexpected error: {e}")
                import traceback
                traceback.print_exc()
        
        if not success:
            print(f"[DEBUG] Batch {i//batch_size + 1} completely failed after {max_retries} attempts")
    
    random.shuffle(all_questions)
    print(f"[DEBUG] TOTAL questions generated: {len(all_questions)}")
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
