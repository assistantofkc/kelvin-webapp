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
APP_VERSION = 'v5.0'


def generate_sentences(vocabularies):
    """
    Generate fill-in-the-blank sentences for each vocabulary word.
    AI only generates {word, sentence} - options are generated client-side.
    """
    print(f"[DEBUG] generate_sentences called")
    
    if not vocabularies:
        print("[DEBUG] Empty vocabularies")
        return []
    
    vocab_list = [v.strip() for v in re.split(r'[\n\s]+', vocabularies) if v.strip()]
    print(f"[DEBUG] Split into {len(vocab_list)} vocabularies")
    
    if not vocab_list:
        return []
    
    # NVIDIA API endpoint
    invoke_url = 'https://integrate.api.nvidia.com/v1/chat/completions'
    
    nvidia_api_key = os.environ.get('NVIDIA_API_KEY', '').strip()
    if not nvidia_api_key:
        nvidia_api_key = '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'
    
    headers = {
        'Authorization': f'Bearer {nvidia_api_key}',
        'Content-Type': 'application/json'
    }
    
    # Join words - use all words in one prompt for efficiency
    vocab_str = ', '.join(vocab_list)
    
    # Prompt: AI only generates word + sentence, NO options
    prompt = f"""Given these Chinese words: {vocab_str}

For EACH word, create a unique fill-in-the-blank sentence where the word is replaced with "____".

Output ONLY valid JSON array, no other text:
[
  {{"word": "經歷", "sentence": "他_____了很多困難終於成功"}},
  {{"word": "糾結", "sentence": "這個決定讓我非常_____"}}
]

Rules:
- Each sentence must be natural and context-rich
- The word must be naturally fit in the sentence
- Use "____" (4 underscores) as the placeholder
- Generate a DIFFERENT sentence for each word
- Output valid JSON array only, no markdown, no explanation"""

    payload = {
        'model': 'moonshotai/kimi-k2.5',
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 2048,
        'temperature': 0.7,
        'top_p': 1.0,
        'stream': False
    }
    
    try:
        print(f"[DEBUG] Calling NVIDIA/kimi API...")
        response = requests.post(
            invoke_url,
            headers=headers,
            json=payload,
            timeout=60
        )
        
        print(f"[DEBUG] Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"[DEBUG] API Error: {response.text[:300]}")
            return []
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        print(f"[DEBUG] Content length: {len(content)}")
        print(f"[DEBUG] Content preview: {content[:200]}...")
        
        if not content:
            return []
        
        # Clean and extract JSON
        content = re.sub(r'```json', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content, flags=re.IGNORECASE)
        
        start = content.find('[')
        end = content.rfind(']') + 1
        if start == -1 or end == 0:
            print(f"[DEBUG] No JSON array found")
            return []
        
        json_str = content[start:end]
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        print(f"[DEBUG] JSON length: {len(json_str)}")
        
        data = json.loads(json_str)
        
        if not isinstance(data, list):
            print(f"[DEBUG] Expected list, got: {type(data)}")
            return []
        
        print(f"[DEBUG] Generated {len(data)} sentences")
        return data
    
    except Exception as e:
        print(f"[DEBUG] Error: {e}")
        import traceback
        traceback.print_exc()
        return []


@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION)


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
