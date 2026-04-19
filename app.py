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
APP_VERSION = 'v2.5'


def generate_quiz_questions(vocabularies, batch_size=5):
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
    
    # Process in batches
    for i in range(0, len(vocab_list), batch_size):
        batch = vocab_list[i:i+batch_size]
        print(f"[DEBUG] Processing batch: {batch}")
        
        # Build prompt for fill-in-the-blank style questions
        vocab_str = ' '.join(batch)
        
        prompt = f"""給定以下中文詞彙：{vocab_str}

請為每個詞彙生成一道「選詞填空」題目。

題目格式：
- 句子中有一個空格需要填入詞彙
- 4個選項，只有1個正確
- 答案是其中一個詞彙

JSON格式（不要其他文字）：
{{
  "questions": [
    {{
      "vocabulary": "詞彙",
      "sentence": "_______最正確的句子",
      "options": {{
        "A": "干擾選項1",
        "B": "干擾選項2",
        "C": "干擾選項3",
        "D": "干擾選項4"
      }},
      "correct": "A"
    }}
  ]
}}

每個干擾選項應該是另一個詞彙的意思，看起來合理但唔岩。"""

        try:
            headers = {
                'Authorization': f'Bearer {MINIMAX_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': 'minimax/MiniMax-M2.7',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens': 800
            }
            
            print(f"[DEBUG] Calling OpenRouter API for batch {i//batch_size + 1}...")
            response = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=45
            )
            
            print(f"[DEBUG] Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[DEBUG] API Error: {response.text[:300]}")
                continue
            
            result = response.json()
            
            if 'choices' not in result or len(result['choices']) == 0:
                print(f"[DEBUG] No choices in response")
                continue
            
            message = result['choices'][0].get('message', {})
            content = message.get('content', '')
            
            if not content:
                print(f"[DEBUG] Empty content")
                continue
            
            # Extract JSON
            start = content.find('{')
            end = content.rfind('}') + 1
            if start == -1 or end == 0:
                print(f"[DEBUG] No JSON found in content: {content[:100]}")
                continue
            
            json_str = content[start:end]
            data = json.loads(json_str)
            
            questions = data.get('questions', [])
            print(f"[DEBUG] Got {len(questions)} questions from batch")
            
            # Shuffle options within each question
            for q in questions:
                options = q.get('options', {})
                correct_answer_text = options.get(q.get('correct', 'A'), '')
                
                keys = list(options.keys())
                random.shuffle(keys)
                
                new_options = {}
                new_correct = None
                for new_key in keys:
                    new_options[new_key] = options[new_key]
                    if options[new_key] == correct_answer_text:
                        new_correct = new_key
                
                q['options'] = new_options
                if new_correct:
                    q['correct'] = new_correct
            
            all_questions.extend(questions)
            
        except requests.exceptions.Timeout:
            print(f"[DEBUG] Batch {i//batch_size + 1} timed out")
            continue
        except Exception as e:
            print(f"[DEBUG] Error in batch {i//batch_size + 1}: {e}")
            continue
    
    # Shuffle all questions
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
    print("[DEBUG] /api/generate-quiz called")
    data = request.get_json()
    vocabularies = data.get('vocabularies', '')
    
    if not vocabularies.strip():
        return jsonify({'error': '請輸入中文詞彙'}), 400
    
    questions = generate_quiz_questions(vocabularies, batch_size=5)
    
    if questions:
        return jsonify({
            'success': True,
            'questions': questions,
            'total': len(questions)
        })
    else:
        return jsonify({
            'error': '生成題目時發生錯誤，請減少詞彙數量或稍後再試'
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
