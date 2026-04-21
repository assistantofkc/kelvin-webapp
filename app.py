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
from dotenv import load_dotenv

# Load .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)

# App version
APP_VERSION = 'v5.91'


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
        return jsonify({
            'success': False,
            'error': 'MiniMax API key not configured. Please set MINIMAX_API_KEY environment variable.'
        }), 500
    
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


# MASTER_BANK for Cangjie Practice
MASTER_BANK = {
    # Level 1: 24 Fundamental Roots (基本字根)
    1: [
        {'char': '日', 'code': 'AAA', 'parts': ['日', '日', '日']},
        {'char': '月', 'code': 'BAA', 'parts': ['月', '月', '月']},
        {'char': '木', 'code': 'D', 'parts': ['木']},
        {'char': '水', 'code': 'E', 'parts': ['水']},
        {'char': '火', 'code': 'F', 'parts': ['火']},
        {'char': '土', 'code': 'G', 'parts': ['土']},
        {'char': '金', 'code': 'C', 'parts': ['金']},
        {'char': '人', 'code': 'O', 'parts': ['人']},
        {'char': '心', 'code': 'XU', 'parts': ['心', '心']},
        {'char': '手', 'code': 'Q', 'parts': ['手']},
        {'char': '口', 'code': 'R', 'parts': ['口']},
        {'char': '山', 'code': 'U', 'parts': ['山']},
        {'char': '石', 'code': 'GRR', 'parts': ['石', '口', '口']},
        {'char': '田', 'code': 'W', 'parts': ['田']},
        {'char': '卜', 'code': 'Y', 'parts': ['卜']},
        {'char': '中', 'code': 'JR', 'parts': ['中', '口']},
        {'char': '大', 'code': 'K', 'parts': ['大']},
        {'char': '小', 'code': 'IU', 'parts': ['小', '山']},
        {'char': '女', 'code': 'V', 'parts': ['女']},
        {'char': '竹', 'code': 'H', 'parts': ['竹']},
        {'char': '戈', 'code': 'IP', 'parts': ['戈', '戈']},
        {'char': '十', 'code': 'J', 'parts': ['十']},
        {'char': '弓', 'code': 'N', 'parts': ['弓']},
        # Additional Level 1 practice (composite forms)
        {'char': '林', 'code': 'DD', 'parts': ['木', '木']},
        {'char': '森', 'code': 'DDD', 'parts': ['木', '木', '木']},
        {'char': '呂', 'code': 'RRA', 'parts': ['口', '口', '日']},
        {'char': '哥', 'code': 'SJR', 'parts': ['可', '口']},
        {'char': '言', 'code': 'YRR', 'parts': ['言', '口', '口']},
        {'char': '舌', 'code': 'JJR', 'parts': ['十', '十', '口']},
        {'char': '內', 'code': 'BQ', 'parts': ['月', '手']},
        {'char': '冊', 'code': 'BBBA', 'parts': ['月', '月', '月', '日']},
        {'char': '用', 'code': 'BHQ', 'parts': ['月', '竹', '手']},
        {'char': '甩', 'code': 'BIX', 'parts': ['月', '小', '心']},
        {'char': '甬', 'code': 'BNG', 'parts': ['月', '弓', '土']},
        {'char': '疋', 'code': 'SU', 'parts': ['疋', '山']},
        {'char': '彳', 'code': 'O', 'parts': ['彳']},
        {'char': '廴', 'code': 'YTT', 'parts': ['廴', '卜', '卜']},
        {'char': '辶', 'code': 'YHU', 'parts': ['辶', '卜', '山']},
        {'char': '阝', 'code': 'NL', 'parts': ['阝', '弓', '月']},
        {'char': '卩', 'code': 'V', 'parts': ['卩']},
        {'char': '勹', 'code': 'P', 'parts': ['勹']},
        {'char': '匕', 'code': 'N', 'parts': ['匕']},
        {'char': '匚', 'code': 'T', 'parts': ['匚']},
        {'char': '匸', 'code': 'I', 'parts': ['匸']},
        {'char': '厶', 'code': 'U', 'parts': ['厶']},
        {'char': '又', 'code': 'E', 'parts': ['又']},
        {'char': '宀', 'code': 'J', 'parts': ['宀']},
        {'char': '尢', 'code': 'K', 'parts': ['尢']},
        {'char': '尣', 'code': 'OW', 'parts': ['尣', '人']},
        {'char': '尸', 'code': 'S', 'parts': ['尸']},
        {'char': '屮', 'code': 'E', 'parts': ['屮']},
        {'char': '工', 'code': 'YI', 'parts': ['工']},
        {'char': '左', 'code': 'YI', 'parts': ['左', '工']},
        {'char': '且', 'code': 'B', 'parts': ['且']},
        {'char': '丘', 'code': 'HA', 'parts': ['丘']},
        {'char': '亟', 'code': 'NUU', 'parts': ['亟', '一', '口']},
        {'char': '企', 'code': 'OHR', 'parts': ['人', '止', '口']},
        {'char': '凶', 'code': 'U', 'parts': ['凶']},
    ],
    
    # Level 2: Two-character words (兩字詞)
    2: [
        {'char': '日月', 'code': 'BAA', 'parts': ['月', '日']},
        {'char': '人口', 'code': 'OR', 'parts': ['人', '口']},
        {'char': '大小', 'code': 'IK', 'parts': ['大', '小']},
        {'char': '山水', 'code': 'UE', 'parts': ['山', '水']},
        {'char': '木林', 'code': 'DD', 'parts': ['木', '林']},
        {'char': '森林', 'code': 'DD', 'parts': ['木', '森']},
        {'char': '土心', 'code': 'G', 'parts': ['土', '心']},
        {'char': '手工', 'code': 'Q', 'parts': ['手', '工']},
        {'char': '中日', 'code': 'JR', 'parts': ['中', '日']},
        {'char': '中中', 'code': 'JR', 'parts': ['中', '中']},
        {'char': '中心', 'code': 'JR', 'parts': ['中', '心']},
        {'char': '水中', 'code': 'E', 'parts': ['水', '中']},
        {'char': '火心', 'code': 'F', 'parts': ['火', '心']},
        {'char': '人心', 'code': 'O', 'parts': ['人', '心']},
        {'char': '日日', 'code': 'AAA', 'parts': ['日', '日']},
        {'char': '月月', 'code': 'BAA', 'parts': ['月', '月']},
        {'char': '木木', 'code': 'DD', 'parts': ['木', '木']},
        {'char': '水水', 'code': 'EE', 'parts': ['水', '水']},
        {'char': '火山', 'code': 'F', 'parts': ['火', '山']},
        {'char': '土木', 'code': 'G', 'parts': ['土', '木']},
        {'char': '金水', 'code': 'C', 'parts': ['金', '水']},
        {'char': '金工', 'code': 'C', 'parts': ['金', '工']},
        {'char': '石口', 'code': 'GRR', 'parts': ['石', '口']},
        {'char': '石石', 'code': 'GRGR', 'parts': ['石', '石']},
        {'char': '卜口', 'code': 'YR', 'parts': ['卜', '口']},
        {'char': '弓手', 'code': 'NQ', 'parts': ['弓', '手']},
        {'char': '竹木', 'code': 'H', 'parts': ['竹', '木']},
        {'char': '竹心', 'code': 'H', 'parts': ['竹', '心']},
        {'char': '戈心', 'code': 'IP', 'parts': ['戈', '心']},
        {'char': '十心', 'code': 'J', 'parts': ['十', '心']},
        {'char': '女人', 'code': 'V', 'parts': ['女', '人']},
        {'char': '山大', 'code': 'U', 'parts': ['山', '大']},
        {'char': '山大', 'code': 'UK', 'parts': ['山', '大']},
        {'char': '中山', 'code': 'JR', 'parts': ['中', '山']},
        {'char': '中小', 'code': 'JIU', 'parts': ['中', '小']},
        {'char': '口心', 'code': 'R', 'parts': ['口', '心']},
        {'char': '口口', 'code': 'RR', 'parts': ['口', '口']},
        {'char': '田力', 'code': 'W', 'parts': ['田', '力']},
        {'char': '田土', 'code': 'WG', 'parts': ['田', '土']},
        {'char': '卜卜', 'code': 'YY', 'parts': ['卜', '卜']},
        {'char': '手心', 'code': 'Q', 'parts': ['手', '心']},
        {'char': '手口', 'code': 'QR', 'parts': ['手', '口']},
        {'char': '手土', 'code': 'QG', 'parts': ['手', '土']},
        {'char': '心心', 'code': 'XU', 'parts': ['心', '心']},
    ],
    
    # Level 3: Common daily characters (常用字)
    3: [
        # Simple 1-letter characters
        {'char': '一', 'code': 'M', 'parts': ['一']},
        {'char':  '丨', 'code': 'J', 'parts': ['丨']},
        {'char': '丿', 'code': 'I', 'parts': ['丿']},
        {'char': '丶', 'code': 'I', 'parts': ['丶']},
        {'char': '丸', 'code': 'HI', 'parts': ['九', '丶']},
        {'char': '凡', 'code': 'HN', 'parts': ['几', '丶']},
        {'char': '刃', 'code': 'VN', 'parts': ['刀', '丶']},
        {'char': '及', 'code': 'E', 'parts': ['及']},
        {'char': '太', 'code': 'K', 'parts': ['大', '丶']},
        {'char': '夭', 'code': 'K', 'parts': ['大', '丿']},
        {'char': '夫', 'code': 'K', 'parts': ['夫']},
        {'char': '孔', 'code': 'XU', 'parts': ['子', '乚']},
        {'char': '尤', 'code': 'HI', 'parts': ['尤', '丶']},
        {'char': '尨', 'code': 'JIK', 'parts': ['尤', '彐', '大']},
        {'char': '尭', 'code': 'HGI', 'parts': ['垚', '九']},
        {'char': '屳', 'code': 'HHV', 'parts': ['山', '人', '彡']},
        {'char': '屹', 'code': 'O', 'parts': ['山', '人']},
        {'char': '州', 'code': 'E', 'parts': ['州']},
        {'char': '巨', 'code': 'W', 'parts': ['匚', '口']},
        {'char': '巨', 'code': 'G', 'parts': ['巨']},
        {'char': '廿', 'code': 'J', 'parts': ['廿']},
        {'char': '卅', 'code': 'JJ', 'parts': ['廿', '十']},
        {'char': '卌', 'code': 'JJJ', 'parts': ['卅', '十']},
        {'char': '卉', 'code': 'J', 'parts': ['卉']},
        {'char': '卍', 'code': 'WN', 'parts': ['卍']},
        {'char': '厶', 'code': 'U', 'parts': ['厶']},
        {'char': '卩', 'code': 'V', 'parts': ['卩']},
        {'char': '厂', 'code': 'D', 'parts': ['厂']},
        {'char': '卜', 'code': 'Y', 'parts': ['卜']},
        {'char': '卞', 'code': 'Y', 'parts': ['卜', '十']},
        {'char': '卦', 'code': 'YH', 'parts': ['卜', '土', '卜']},
        {'char': '𠂇', 'code': 'I', 'parts': ['𠂇']},
        {'char': '倩', 'code': 'OIR', 'parts': ['人', '青', '土']},
        {'char': '借', 'code': 'OAJ', 'parts': ['人', '昔', '日']},
        {'char': '偎', 'code': 'OAV', 'parts': ['人', '畏', '月']},
        {'char': '側', 'code': 'OIR', 'parts': ['人', '貝', '日']},
        {'char': '做', 'code': 'OJQR', 'parts': ['人', '古', '口', '文']},
        {'char': '停', 'code': 'OIR', 'parts': ['人', '亭', '口']},
        {'char': '備', 'code': 'HBY', 'parts': ['人', '田', '月', '卜']},
        {'char': '傅', 'code': 'OJFQ', 'parts': ['人', '甫', '寸']},
        {'char': '傴', 'code': 'OBV', 'parts': ['人', '臣', '女']},
        {'char': '傲', 'code': 'OHE', 'parts': ['人', '高', '火']},
        {'char': '傘', 'code': 'OO', 'parts': ['人', '人', '十']},
        {'char': '催', 'code': 'OOR', 'parts': ['人', '山', '口']},
        {'char': '傷', 'code': 'OHR', 'parts': ['人', '傷', '口']},
        {'char': '傻', 'code': 'OVI', 'parts': ['人', '穴', '工', '口']},
        {'char': '傾', 'code': 'OIV', 'parts': ['人', '頃', '頁']},
        {'char': '傳', 'code': 'OIU', 'parts': ['人', '專', '寸']},
        {'char': '偍', 'code': 'OJR', 'parts': ['人', '日', '十']},
        {'char': '偽', 'code': 'OJJ', 'parts': ['人', '為', '灬']},
        {'char': '傑', 'code': 'OFQ', 'parts': ['人', '火', '木']},
        {'char': '傘', 'code': 'OOO', 'parts': ['人', '人', '人']},
    ]
}


@app.route('/cangjie')
def cangjie():
    return render_template('cangjie.html', version=APP_VERSION)


def get_cangjie_questions(level):
    if level not in MASTER_BANK:
        return jsonify({'error': 'Invalid level'}), 400
    
    # Shuffle and pick 10
    bank = MASTER_BANK[level].copy()
    random.shuffle(bank)
    questions = bank[:10]
    
    return jsonify({'questions': questions})


    app.run(debug=True)
