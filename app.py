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

# App version
APP_VERSION = 'v5.47'


def generate_sentences(vocabularies, max_retries=2):
    """
    Generate fill-in-the-blank sentences for each vocabulary word.
    AI only generates {word, sentence} - options are generated client-side.
    Has retry logic for handling temporary failures.
    """
    print(f"[DEBUG] generate_sentences called")
    
    if not vocabularies:
        print("[DEBUG] Empty vocabularies")
        return []
    
    vocab_list = [v.strip() for v in re.split(r'[\n\s]+', vocabularies) if v.strip()]
    print(f"[DEBUG] Split into {len(vocab_list)} vocabularies")
    
    if not vocab_list:
        return []
    
    # MiniMax API
    mini_max_url = 'https://api.minimax.io/v1/text/chatcompletion_v2?GroupId=2043608871905276295'
    
    mini_max_api_key = os.environ.get('MINIMAX_API_KEY', '').strip()
    if not mini_max_api_key:
        mini_max_api_key = 'sk-cp-yrzrhj9MPRYAZ2Xit1OgVVCitgM7LBYmridy2CzkpNDN_R0LLi2Xubm69-Q0v0YIivMiJRtKcL7ngzNbPRq_2DlNmPK5iyeIIcDZAhpFS7e4w3Z5xwQvxNg'
    
    headers = {
        'Authorization': f'Bearer {mini_max_api_key}',
        'Content-Type': 'application/json'
    }
    
    # Join words
    vocab_str = ', '.join(vocab_list)
    
    # Prompt: AI only generates word + sentence, NO options
    prompt = f"""Given these Traditional Chinese words: {vocab_str}

For EACH word, create a unique fill-in-the-blank sentence (MUST use TRADITIONAL Chinese characters, NOT Simplified Chinese) where the word is replaced with "____".

Output ONLY valid JSON array, no other text:
[
  {{"word": "經歷", "sentence": "創業者在道路上面對了很多____最終找到成功方向"}},
  {{"word": "糾結", "sentence": "這個決定讓我陷入嚴重的_____難以果斷行動"}}
]

Rules:
- 請使用繁體中文（台灣/香港用字），絕對不要使用簡體中文
- 所有句子必須是繁體中文，包括所有標點符號
- Each sentence must be natural and context-rich
- The word must be naturally fit in the sentence
- Use "____" (4 underscores) as the placeholder
- Generate a DIFFERENT sentence for each word
- Output valid JSON array only, no markdown, no explanation"""

    payload = {
        'model': 'MiniMax-M2.7',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.3,
        'max_tokens': 2500
    }
    
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] Attempt {attempt + 1}/{max_retries} - Calling MiniMax API...")
            response = requests.post(
                mini_max_url,
                headers=headers,
                json=payload,
                timeout=180
            )
            
            print(f"[DEBUG] Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"[DEBUG] API Error: {response.text[:300]}")
                if attempt < max_retries - 1:
                    print("[DEBUG] Retrying...")
                    continue
                return []
            
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            print(f"[DEBUG] Content length: {len(content)}")
            print(f"[DEBUG] Content preview: {content[:200]}...")
            
            if not content:
                if attempt < max_retries - 1:
                    continue
                return []
            
            # Clean and extract JSON
            content = re.sub(r'```json', '', content, flags=re.IGNORECASE)
            content = re.sub(r'```', '', content, flags=re.IGNORECASE)
            
            start = content.find('[')
            end = content.rfind(']') + 1
            if start == -1 or end == 0:
                print(f"[DEBUG] No JSON array found")
                if attempt < max_retries - 1:
                    continue
                return []
            
            json_str = content[start:end]
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            print(f"[DEBUG] JSON length: {len(json_str)}")
            
            data = json.loads(json_str)
            
            if not isinstance(data, list):
                print(f"[DEBUG] Expected list, got: {type(data)}")
                if attempt < max_retries - 1:
                    continue
                return []
            
            print(f"[DEBUG] Generated {len(data)} sentences")
            return data
        
        except requests.exceptions.Timeout:
            print(f"[DEBUG] Attempt {attempt + 1} timed out")
            if attempt < max_retries - 1:
                print("[DEBUG] Retrying...")
                continue
        except Exception as e:
            print(f"[DEBUG] Error: {e}")
            if attempt < max_retries - 1:
                continue
    
    print(f"[DEBUG] All retries failed")
    return []


@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION)


@app.route('/news-clipper')
def news_clipper():
    return render_template('news-clipper.html', version=APP_VERSION)


@app.route('/vocab-test')
def vocab_test():
    return render_template('vocab_test.html', version=APP_VERSION)


@app.route('/api/generate-quiz', methods=['POST'])
def api_generate_quiz():
    """
    API endpoint to generate quiz sentences.
    Returns {word, sentence} pairs. Options are generated client-side.
    """
    data = request.get_json()
    vocabularies = data.get('vocabularies', '')
    
    if not vocabularies.strip():
        return jsonify({'error': '請輸入中文詞彙'}), 400
    
    results = generate_sentences(vocabularies)
    
    if results:
        return jsonify({
            'success': True,
            'data': results,
            'total': len(results)
        })
    else:
        return jsonify({
            'error': '生成題目失敗，請稍後再試'
        }), 500


if __name__ == '__main__':
    app.run(debug=True)
