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
    MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '')
    MINIMAX_API_URL = os.environ.get('MINIMAX_API_URL', 'https://api.minimax.io/v1/text/chatcompletion_v2')


def generate_quiz_questions(vocabularies):
    """
    Use MiniMax API to generate multiple choice questions for Chinese vocabularies.
    Returns a list of question dictionaries.
    """
    if not vocabularies:
        return []
    
    # Split vocabularies by newlines OR spaces
    vocab_list = [v.strip() for v in re.split(r'[\n\s]+', vocabularies) if v.strip()]
    
    if not vocab_list:
        return []
    
    # Build the prompt for MiniMax
    vocab_str = ' '.join(vocab_list)
    
    prompt = f"""你是一個中文詞彙測驗題目生成器。

給定以下中文詞彙：{vocab_str}

請為每個詞彙生成一道多重選擇題。題目必須：
1. 測試用戶對詞彙意思的理解
2. 有4個選項（A、B、C、D），只有1個正確答案
3. 題目和選項都要用繁體中文
4. 選項應該是其他不相關的詞彙意思作為干擾項

請以以下JSON格式回覆（不要加入任何其他文字）：
{{
  "questions": [
    {{
      "vocabulary": "詞彙",
      "question": "題目內容",
      "options": {{
        "A": "選項A的解釋",
        "B": "選項B的解釋",
        "C": "選項C的解釋",
        "D": "選項D的解釋"
      }},
      "correct": "A"
    }}
  ]
}}

請確保干擾項看起來合理但不正確。題目順序要隨機。"""

    try:
        headers = {
            'Authorization': f'Bearer {MINIMAX_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': 'MiniMax-M2.7-highspeed',
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.7,
            'max_tokens': 4000
        }
        
        response = requests.post(MINIMAX_API_URL, headers=headers, json=payload, timeout=(10, 120))
        
        if response.status_code != 200:
            print(f"API Error: {response.status_code} - {response.text}")
            return []
        
        result = response.json()
        
        # Get content from the response
        if 'choices' not in result or len(result['choices']) == 0:
            print(f"No choices in response: {result}")
            return []
        
        message = result['choices'][0].get('message', {})
        content = message.get('content', '')
        
        if not content:
            print(f"Empty content in response")
            return []
        
        # Extract JSON from content
        # Try multiple methods to find JSON
        json_str = None
        
        # Method 1: Find JSON block between { and }
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = content[start:end+1]
        
        if not json_str:
            print(f"Could not find JSON in content: {content[:200]}")
            return []
        
        # Parse JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"JSON string: {json_str[:500]}")
            return []
        
        questions = data.get('questions', [])
        
        if not questions:
            print(f"No questions in data: {data}")
            return []
        
        # Shuffle questions for randomness
        random.shuffle(questions)
        
        # Shuffle options within each question and track correct answer
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
        
        return questions
            
    except requests.exceptions.Timeout:
        print("API request timed out - PythonAnywhere network may be slow")
        raise Exception("API request timed out")
    except Exception as e:
        print(f"Error generating questions: {e}")
        import traceback
        traceback.print_exc()
        return []


@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')


@app.route('/vocab-test')
def vocab_test():
    """Chinese Vocabulary Test page"""
    return render_template('vocab_test.html')


@app.route('/api/generate-quiz', methods=['POST'])
def api_generate_quiz():
    """
    API endpoint to generate quiz questions.
    Receives vocabularies from client, calls MiniMax API, returns questions.
    API key is never exposed to client.
    """
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
            'error': '生成題目超時，請減少詞彙數量或稍後再試'
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
