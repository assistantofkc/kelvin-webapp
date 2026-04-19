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
APP_VERSION = 'v2.7'


def generate_quiz_questions(vocabularies):
    """
    Use MiniMax API to generate multiple choice questions for Chinese vocabularies.
    """
    print(f"[DEBUG] generate_quiz_questions called")
    
    if not vocabularies:
        print("[DEBUG] Empty vocabularies")
        return []
    
    # Split vocabularies
    vocab_list = [v.strip() for v in re.split(r'[\n\s]+', vocabularies) if v.strip()]
    print(f"[DEBUG] Split into {len(vocab_list)} vocabularies: {vocab_list}")
    
    if not vocab_list:
        return []
    
    # Limit to 10 words max to avoid timeout
    if len(vocab_list) > 10:
        vocab_list = vocab_list[:10]
        print(f"[DEBUG] Limited to 10 vocabularies: {vocab_list}")
    
    vocab_str = ' '.join(vocab_list)
    
    # Improved prompt with clearer instructions
    prompt = f"""你是一個中文詞彙測驗題目生成器。

給定以下中文詞彙：{vocab_str}

請為每個詞彙生成一道「選詞填空」題目。

要求：
- 每個題目是一個句子，其中一個詞彙變成「_____」（底線）
- 4個選項，只有1個正確答案
- 選項使用其他詞彙的意思作為干擾項
- 答案必須是提供嘅詞彙其中一個

嚴格按照以下JSON格式回覆，唔好加任何其他文字：
{{
  "questions": [
    {{
      "vocabulary": "詞彙",
      "sentence": "這是一個包含_____的句子",
      "options": {{
        "A": "干擾選項1",
        "B": "干擾選項2", 
        "C": "干擾選項3",
        "D": "干擾選項4"
      }},
      "correct": "A"
    }}
  ]
}}"""

    print("[DEBUG] Making API request...")
    
    try:
        headers = {
            'Authorization': f'Bearer {MINIMAX_API_KEY}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://kelvin-webapp.onrender.com',
            'X-OpenRouter-Title': 'Chinese Vocab Quiz'
        }
        
        payload = {
            'model': 'minimax/MiniMax-M2.7',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.7,
            'max_tokens': 1500
        }
        
        print(f"[DEBUG] Sending request to OpenRouter...")
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=60
        )
        
        print(f"[DEBUG] Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[DEBUG] API Error {response.status_code}: {response.text[:500]}")
            return []
        
        result = response.json()
        print(f"[DEBUG] Response keys: {list(result.keys())}")
        
        if 'choices' not in result or len(result['choices']) == 0:
            print(f"[DEBUG] No choices in response: {result}")
            return []
        
        message = result['choices'][0].get('message', {})
        content = message.get('content', '')
        
        if not content:
            print(f"[DEBUG] Empty content in response")
            return []
        
        print(f"[DEBUG] Content length: {len(content)}, preview: {content[:100]}...")
        
        # Extract JSON
        start = content.find('{')
        end = content.rfind('}') + 1
        if start == -1 or end == 0:
            print(f"[DEBUG] No JSON found. Content: {content[:200]}")
            return []
        
        json_str = content[start:end]
        print(f"[DEBUG] Parsing JSON: {json_str[:200]}...")
        
        data = json.loads(json_str)
        
        questions = data.get('questions', [])
        print(f"[DEBUG] Got {len(questions)} questions")
        
        if not questions:
            print(f"[DEBUG] No questions in data: {data}")
            return []
        
        # Shuffle and process options
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
        
        random.shuffle(questions)
        return questions
            
    except requests.exceptions.Timeout:
        print("[DEBUG] Request timed out")
        return []
    except json.JSONDecodeError as e:
        print(f"[DEBUG] JSON parse error: {e}")
        return []
    except Exception as e:
        print(f"[DEBUG] Error: {e}")
        import traceback
        traceback.print_exc()
        return []


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
