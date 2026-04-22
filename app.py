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
APP_VERSION = 'v6.18'


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


# MASTER_BANK for Cangjie Practice - 已校正並去掉加號
MASTER_BANK = {
    # Level 1: 24 基本字根
    1: [
        {'char': '日', 'code': 'A', 'parts': '日'}, {'char': '月', 'code': 'B', 'parts': '月'},
        {'char': '金', 'code': 'C', 'parts': '金'}, {'char': '木', 'code': 'D', 'parts': '木'},
        {'char': '水', 'code': 'E', 'parts': '水'}, {'char': '火', 'code': 'F', 'parts': '火'},
        {'char': '土', 'code': 'G', 'parts': '土'}, {'char': '竹', 'code': 'H', 'parts': '竹'},
        {'char': '戈', 'code': 'I', 'parts': '戈'}, {'char': '十', 'code': 'J', 'parts': '十'},
        {'char': '大', 'code': 'K', 'parts': '大'}, {'char': '中', 'code': 'L', 'parts': '中'},
        {'char': '一', 'code': 'M', 'parts': '一'}, {'char': '弓', 'code': 'N', 'parts': '弓'},
        {'char': '人', 'code': 'O', 'parts': '人'}, {'char': '心', 'code': 'P', 'parts': '心'},
        {'char': '手', 'code': 'Q', 'parts': '手'}, {'char': '口', 'code': 'R', 'parts': '口'},
        {'char': '尸', 'code': 'S', 'parts': '尸'}, {'char': '廿', 'code': 'T', 'parts': '廿'},
        {'char': '山', 'code': 'U', 'parts': '山'}, {'char': '女', 'code': 'V', 'parts': '女'},
        {'char': '田', 'code': 'W', 'parts': '田'}, {'char': '卜', 'code': 'Y', 'parts': '卜'}
    ],
    
    # Level 2: 字根變體
    2: [
        {'char': '目', 'code': 'B', 'parts': '月家族'}, {'char': '氵', 'code': 'E', 'parts': '水家族'},
        {'char': '艹', 'code': 'T', 'parts': '廿家族'}, {'char': '宀', 'code': 'J', 'parts': '十家族'},
        {'char': '亻', 'code': 'O', 'parts': '人家族'}, {'char': '扌', 'code': 'Q', 'parts': '手家族'},
        {'char': '刀', 'code': 'S', 'parts': '尸家族'}, {'char': '力', 'code': 'S', 'parts': '尸家族'},
        {'char': '曰', 'code': 'A', 'parts': '日家族'}, {'char': '八', 'code': 'C', 'parts': '金家族'},
        {'char': '厂', 'code': 'M', 'parts': '一家族'}, {'char': '匚', 'code': 'P', 'parts': '心家族'},
        {'char': '勹', 'code': 'P', 'parts': '心家族'}, {'char': '凵', 'code': 'U', 'parts': '山家族'},
        {'char': '冂', 'code': 'B', 'parts': '月家族'}, {'char': '爫', 'code': 'B', 'parts': '月家族'},
        {'char': '礻', 'code': 'I', 'parts': '戈家族'}, {'char': '衤', 'code': 'I', 'parts': '戈家族'},
        {'char': '糸', 'code': 'V', 'parts': '女家族'}, {'char': '辶', 'code': 'Y', 'parts': '卜家族'},
        {'char': '廴', 'code': 'N', 'parts': '弓家族'}, {'char': '彳', 'code': 'O', 'parts': '人家族'},
        {'char': '彡', 'code': 'H', 'parts': '竹家族'}, {'char': '灬', 'code': 'F', 'parts': '火家族'},
        {'char': '阝', 'code': 'N', 'parts': '弓家族'}, {'char': '刂', 'code': 'J', 'parts': '十家族'}
    ],
    
    # Level 3: 常用漢字
    3: [
        {'char': '男', 'code': 'WLS', 'parts': '田中力'},
        {'char': '明', 'code': 'AB', 'parts': '日月'},
        {'char': '林', 'code': 'DD', 'parts': '木木'},
        {'char': '和', 'code': 'HDR', 'parts': '竹木口'},
        {'char': '花', 'code': 'TOP', 'parts': '廿人心'},
        {'char': '想', 'code': 'DBP', 'parts': '木目心'},
        {'char': '看', 'code': 'HQU', 'parts': '竹手山'},
        {'char': '國', 'code': 'WIRM', 'parts': '囗戈口一'},
        {'char': '電', 'code': 'MBWU', 'parts': '一月田山'},
        {'char': '語', 'code': 'YRMIR', 'parts': '卜口一一口'},
        {'char': '聽', 'code': 'SJYP', 'parts': '耳十卜心'},
        {'char': '問', 'code': 'ANR', 'parts': '門口'},
        {'char': '開', 'code': 'ANMJ', 'parts': '門一十'},
        {'char': '地', 'code': 'GPD', 'parts': '土心木'},
        {'char': '天', 'code': 'MK', 'parts': '一大'},
        {'char': '王', 'code': 'MG', 'parts': '一土'},
        {'char': '星', 'code': 'AHM', 'parts': '日竹一'},
        {'char': '信', 'code': 'OYRR', 'parts': '人卜口口'},
        {'char': '你', 'code': 'ONF', 'parts': '人弓火'},
        {'char': '伯', 'code': 'OHA', 'parts': '人竹日'},
        {'char': '家', 'code': 'JJSO', 'parts': '十十尸人'},
        {'char': '鬧', 'code': 'ANYL', 'parts': '門卜中'},
        {'char': '閉', 'code': 'AND', 'parts': '門木'},
        {'char': '閒', 'code': 'ANB', 'parts': '門月'},
        {'char': '圖', 'code': 'WWRY', 'parts': '囗田口卜'},
        {'char': '跑', 'code': 'RMPU', 'parts': '口一心山'},
        {'char': '路', 'code': 'RMHR', 'parts': '口一竹口'},
        {'char': '這', 'code': 'YYRR', 'parts': '卜卜口口'},
        {'char': '都', 'code': 'JAN', 'parts': '十日弓'},
        {'char': '進', 'code': 'YOG', 'parts': '卜人土'},
        {'char': '退', 'code': 'YAV', 'parts': '卜日女'},
        {'char': '起', 'code': 'GOSO', 'parts': '土人尸人'},
        {'char': '眼', 'code': 'BAV', 'parts': '月日女'},
        {'char': '說', 'code': 'YRRU', 'parts': '言金口山'},
        {'char': '話', 'code': 'YRHR', 'parts': '言竹口'},
        {'char': '讀', 'code': 'YRGWC', 'parts': '言土田金'},
        {'char': '書', 'code': 'LGA', 'parts': '中土日'},
        {'char': '筆', 'code': 'HLS', 'parts': '竹中尸'},
        {'char': '畫', 'code': 'LWG', 'parts': '中田土'},
        {'char': '腳', 'code': 'BCIL', 'parts': '月金戈中'},
        {'char': '頭', 'code': 'MNC', 'parts': '一弓金'},
        {'char': '命', 'code': 'OML', 'parts': '人一中'},
        {'char': '愛', 'code': 'BBXP', 'parts': '月月難心'},
        {'char': '情', 'code': 'PQB', 'parts': '心手月'},
        {'char': '分', 'code': 'CS', 'parts': '金尸'},
        {'char': '局', 'code': 'SWR', 'parts': '尸田口'},
        {'char': '尼', 'code': 'SP', 'parts': '尸心'}
    ]
}

@app.route('/cangjie')
def cangjie():
    return render_template('cangjie.html', version=APP_VERSION)


@app.route('/cangjie/get_questions/<int:level>')
def get_cangjie_questions(level):
    if level not in MASTER_BANK:
        return jsonify({'error': 'Invalid level'}), 400
    
    # Shuffle and pick 10
    bank = MASTER_BANK[level].copy()
    random.shuffle(bank)
    questions = bank[:10]
    
    return jsonify({'questions': questions})


    app.run(debug=True)
