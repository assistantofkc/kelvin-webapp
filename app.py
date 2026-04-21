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
APP_VERSION = 'v5.95'


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
    # Level 1: 24 基本字根 (Basic Roots)
    1: [
        {'char': '日', 'code': 'A', 'parts': '日 (A)'},
        {'char': '月', 'code': 'B', 'parts': '月 (B)'},
        {'char': '金', 'code': 'C', 'parts': '金 (C)'},
        {'char': '木', 'code': 'D', 'parts': '木 (D)'},
        {'char': '水', 'code': 'E', 'parts': '水 (E)'},
        {'char': '火', 'code': 'F', 'parts': '火 (F)'},
        {'char': '土', 'code': 'G', 'parts': '土 (G)'},
        {'char': '竹', 'code': 'H', 'parts': '竹 (H)'},
        {'char': '戈', 'code': 'I', 'parts': '戈 (I)'},
        {'char': '十', 'code': 'J', 'parts': '十 (J)'},
        {'char': '大', 'code': 'K', 'parts': '大 (K)'},
        {'char': '中', 'code': 'L', 'parts': '中 (L)'},
        {'char': '一', 'code': 'M', 'parts': '一 (M)'},
        {'char': '弓', 'code': 'N', 'parts': '弓 (N)'},
        {'char': '人', 'code': 'O', 'parts': '人 (O)'},
        {'char': '心', 'code': 'P', 'parts': '心 (P)'},
        {'char': '手', 'code': 'Q', 'parts': '手 (Q)'},
        {'char': '口', 'code': 'R', 'parts': '口 (R)'},
        {'char': '尸', 'code': 'S', 'parts': '尸 (S)'},
        {'char': '廿', 'code': 'T', 'parts': '廿 (T)'},
        {'char': '山', 'code': 'U', 'parts': '山 (U)'},
        {'char': '女', 'code': 'V', 'parts': '女 (V)'},
        {'char': '田', 'code': 'W', 'parts': '田 (W)'},
        {'char': '卜', 'code': 'Y', 'parts': '卜 (Y)'},
    ],
    
    # Level 2: 字根變體 (Variants)
    2: [
        {'char': '目', 'code': 'B', 'parts': '月家族'},
        {'char': '氵', 'code': 'E', 'parts': '水家族'},
        {'char': '艹', 'code': 'T', 'parts': '廿家族'},
        {'char': '宀', 'code': 'J', 'parts': '十家族'},
        {'char': '亻', 'code': 'O', 'parts': '人家族'},
        {'char': '扌', 'code': 'Q', 'parts': '手家族'},
        {'char': '刀', 'code': 'S', 'parts': '尸家族'},
        {'char': '力', 'code': 'S', 'parts': '尸家族'},
        {'char': '曰', 'code': 'A', 'parts': '日家族'},
        {'char': '八', 'code': 'C', 'parts': '金家族'},
        {'char': '厂', 'code': 'M', 'parts': '一家族'},
        {'char': '匚', 'code': 'P', 'parts': '心家族'},
        {'char': '勹', 'code': 'P', 'parts': '心家族'},
        {'char': '凵', 'code': 'U', 'parts': '山家族'},
        {'char': '冂', 'code': 'B', 'parts': '月家族'},
        {'char': '爫', 'code': 'B', 'parts': '月家族'},
        {'char': '龵', 'code': 'Q', 'parts': '手家族'},
        {'char': '礻', 'code': 'I', 'parts': '戈家族'},
        {'char': '糸', 'code': 'V', 'parts': '女家族'},
        {'char': '辶', 'code': 'Y', 'parts': '卜家族'},
        {'char': '廴', 'code': 'N', 'parts': '弓家族'},
        {'char': '彳', 'code': 'O', 'parts': '人家族'},
        {'char': '彡', 'code': 'H', 'parts': '竹家族'},
        {'char': '灬', 'code': 'F', 'parts': '火家族'},
        {'char': '阝', 'code': 'N', 'parts': '弓家族'},
        {'char': '卩', 'code': 'V', 'parts': '卩'},
        {'char': '刂', 'code': 'J', 'parts': '刀家族'},
        {'char': '礻', 'code': 'I', 'parts': '示家族'},
        {'char': '衤', 'code': 'HI', 'parts': '衣家族'},
        {'char': '忄', 'code': 'P', 'parts': '心家族'},
        {'char': '犭', 'code': 'QH', 'parts': '犬家族'},
        {'char': '釒', 'code': 'C', 'parts': '金'},
        {'char': '飠', 'code': 'IHV', 'parts': '食'},
        {'char': '馬', 'code': 'SF', 'parts': '馬'},
        {'char': '魚', 'code': 'WF', 'parts': '魚'},
        {'char': '鳥', 'code': 'HN', 'parts': '鳥'},
        {'char': '虫', 'code': 'LI', 'parts': '虫'},
        {'char': '言', 'code': 'Y', 'parts': '言'},
        {'char': '車', 'code': 'JJ', 'parts': '車'},
        {'char': '戈', 'code': 'IP', 'parts': '戈'},
        {'char': '戊', 'code': 'IP', 'parts': '戈'},
        {'char': '戌', 'code': 'IP', 'parts': '戈'},
        {'char': '戶', 'code': 'HS', 'parts': '戶'},
        {'char': '矛', 'code': 'NSS', 'parts': '矛'},
        {'char': '聿', 'code': 'YAJ', 'parts': '聿'},
        {'char': '艮', 'code': 'ME', 'parts': '艮'},
        {'char': '疋', 'code': 'SU', 'parts': '疋'},
        {'char': '白', 'code': 'HA', 'parts': '白'},
        {'char': '皮', 'code': 'QE', 'parts': '皮'},
        {'char': '皿', 'code': 'W', 'parts': '皿'},
        {'char': '罒', 'code': 'W', 'parts': '罒'},
        {'char': '立', 'code': 'YT', 'parts': '立'},
        {'char': '穴', 'code': 'J', 'parts': '穴'},
        {'char': '耒', 'code': 'KD', 'parts': '耒'},
        {'char': '老', 'code': 'KP', 'parts': '老'},
        {'char': '耳', 'code': 'SJ', 'parts': '耳'},
        {'char': '臣', 'code': 'HAL', 'parts': '臣'},
        {'char': '自', 'code': 'HDA', 'parts': '自'},
        {'char': '至', 'code': 'YGU', 'parts': '至'},
        {'char': '臼', 'code': 'HJ', 'parts': '臼'},
        {'char': '舌', 'code': 'JR', 'parts': '舌'},
        {'char': '舟', 'code': 'HHN', 'parts': '舟'},
        {'char': '色', 'code': 'NSU', 'parts': '色'},
        {'char': '虍', 'code': 'HI', 'parts': '虍'},
        {'char': '血', 'code': 'BLA', 'parts': '血'},
        {'char': '行', 'code': 'OON', 'parts': '行'},
        {'char': '衣', 'code': 'HI', 'parts': '衣'},
        {'char': '見', 'code': 'BUU', 'parts': '見'},
        {'char': '角', 'code': 'SN', 'parts': '角'},
        {'char': '谷', 'code': 'ORR', 'parts': '谷'},
        {'char': '豆', 'code': 'YRI', 'parts': '豆'},
        {'char': '豕', 'code': 'KHN', 'parts': '豕'},
        {'char': '貝', 'code': 'BO', 'parts': '貝'},
        {'char': '赤', 'code': 'GGO', 'parts': '赤'},
        {'char': '走', 'code': 'GYO', 'parts': '走'},
        {'char': '足', 'code': 'RA', 'parts': '足'},
        {'char': '身', 'code': 'THN', 'parts': '身'},
        {'char': '辛', 'code': 'YJ', 'parts': '辛'},
        {'char': '辰', 'code': 'EHI', 'parts': '辰'},
        {'char': '邑', 'code': 'PR', 'parts': '邑'},
        {'char': '酉', 'code': 'TWI', 'parts': '酉'},
        {'char': '釆', 'code': 'QF', 'parts': '釆'},
        {'char': '里', 'code': 'WG', 'parts': '里'},
        {'char': '黾', 'code': 'W', 'parts': '黾'},
        {'char': '住', 'code': 'OMG', 'parts': '住'},
        {'char': '來', 'code': 'MW', 'parts': '來'},
        {'char': '東', 'code': 'KDI', 'parts': '東'},
        {'char': '果', 'code': 'MW', 'parts': '果'},
        {'char': '門', 'code': 'AN', 'parts': '門'},
        {'char': '長', 'code': 'NKE', 'parts': '長'},
        {'char': '阜', 'code': 'N', 'parts': '阜'},
        {'char': '隶', 'code': 'VIX', 'parts': '隶'},
        {'char': '隹', 'code': 'OG', 'parts': '隹'},
        {'char': '雨', 'code': 'MB', 'parts': '雨'},
        {'char': '青', 'code': 'TJJ', 'parts': '青'},
        {'char': '非', 'code': 'TJJ', 'parts': '非'},
        {'char': '表面的', 'code': 'SJ', 'parts': '表面的'},
        {'char': '函', 'code': 'BU', 'parts': '函'},
        {'char': '亞', 'code': 'SYL', 'parts': '亞'},
        {'char': '亟', 'code': 'NUU', 'parts': '亟'},
        {'char': '亙', 'code': 'MA', 'parts': '亙'},
        {'char': '亓', 'code': 'M', 'parts': '亓'},
    ],
    
    # Level 3: 常用漢字 (Combined Characters)
    3: [
        {'char': '男', 'code': 'WLS', 'parts': '田+力'},
        {'char': '明', 'code': 'AB', 'parts': '日+月'},
        {'char': '林', 'code': 'DD', 'parts': '木+木'},
        {'char': '和', 'code': 'HDR', 'parts': '禾+口'},
        {'char': '花', 'code': 'TOP', 'parts': '艹+人+心'},
        {'char': '想', 'code': 'DBP', 'parts': '木+木+心'},
        {'char': '看', 'code': 'HQBU', 'parts': '手+目'},
        {'char': '國', 'code': 'WGI', 'parts': '囗+戈'},
        {'char': '電', 'code': 'LBW', 'parts': '雨+田'},
        {'char': '腦', 'code': 'BVS', 'parts': '月+㠯'},
        {'char': '語', 'code': 'YMR', 'parts': '言+吾'},
        {'char': '聽', 'code': 'SJYP', 'parts': '耳+心+王'},
        {'char': '問', 'code': 'ANR', 'parts': '門+口'},
        {'char': '開', 'code': 'ANWU', 'parts': '門+幵'},
        {'char': '關', 'code': 'ANHU', 'parts': '門+⺍'},
        {'char': '地', 'code': 'GPD', 'parts': '土+也'},
        {'char': '天', 'code': 'MK', 'parts': '一+大'},
        {'char': '王', 'code': 'MG', 'parts': '一+土'},
        {'char': '早', 'code': 'AJ', 'parts': '日+十'},
        {'char': '星', 'code': 'ATC', 'parts': '日+生'},
        {'char': '尖', 'code': 'FK', 'parts': '小+大'},
        {'char': '森', 'code': 'DDD', 'parts': '木+木+木'},
        {'char': '品', 'code': 'RRR', 'parts': '口+口+口'},
        {'char': '炎', 'code': 'FF', 'parts': '火+火'},
        {'char': '信', 'code': 'OYR', 'parts': '人+言'},
        {'char': '休', 'code': 'OD', 'parts': '人+木'},
        {'char': '位', 'code': 'OYT', 'parts': '人+立'},
        {'char': '住', 'code': 'OMG', 'parts': '人+主'},
        {'char': '你', 'code': 'ONF', 'parts': '人+爾'},
        {'char': '他', 'code': 'OPD', 'parts': '人+也'},
        {'char': '什', 'code': 'OJ', 'parts': '人+十'},
        {'char': '伙', 'code': 'OF', 'parts': '人+火'},
        {'char': '伯', 'code': 'OA', 'parts': '人+白'},
        {'char': '作', 'code': 'OHS', 'parts': '人+乍'},
        {'char': '借', 'code': 'OTA', 'parts': '人+昔'},
        {'char': '假', 'code': 'OHV', 'parts': '人+叚'},
        {'char': '好', 'code': 'VN', 'parts': '女+子'},
        {'char': '媽', 'code': 'VSF', 'parts': '女+馬'},
        {'char': '安', 'code': 'JV', 'parts': '宀+女'},
        {'char': '字', 'code': 'JN', 'parts': '宀+子'},
        {'char': '家', 'code': 'JSE', 'parts': '宀+豕'},
        {'char': '客', 'code': 'JHR', 'parts': '宀+各'},
        {'char': '完', 'code': 'JMU', 'parts': '宀+元'},
        {'char': '定', 'code': 'JMO', 'parts': '宀+正'},
        {'char': '聞', 'code': 'ANSJ', 'parts': '門+耳'},
        {'char': '悶', 'code': 'ANP', 'parts': '門+心'},
        {'char': '鬧', 'code': 'ANWY', 'parts': '門+市'},
        {'char': '閉', 'code': 'ANN', 'parts': '門+才'},
        {'char': '閒', 'code': 'ANS', 'parts': '門+木'},
        {'char': '因', 'code': 'WK', 'parts': '囗+大'},
        {'char': '回', 'code': 'WR', 'parts': '囗+口'},
        {'char': '固', 'code': 'WJR', 'parts': '囗+古'},
        {'char': '圈', 'code': 'WLV', 'parts': '囗+卷'},
        {'char': '園', 'code': 'WLG', 'parts': '囗+袁'},
        {'char': '圖', 'code': 'WLY', 'parts': '囗+圖'},
        {'char': '城', 'code': 'GIP', 'parts': '土+成'},
        {'char': '場', 'code': 'GSHI', 'parts': '土+昜'},
        {'char': '坐', 'code': 'OOG', 'parts': '人+人+土'},
        {'char': '走', 'code': 'GYO', 'parts': '土+止'},
        {'char': '跑', 'code': 'RMLK', 'parts': '足+包'},
        {'char': '跳', 'code': 'RMHN', 'parts': '足+兆'},
        {'char': '路', 'code': 'RMLR', 'parts': '足+各'},
        {'char': '這', 'code': 'YRS', 'parts': '辶+言'},
        {'char': '都', 'code': 'JAP', 'parts': '者+阝'},
        {'char': '進', 'code': 'YOO', 'parts': '辶+隹'},
        {'char': '退', 'code': 'YRV', 'parts': '辶+艮'},
        {'char': '道', 'code': 'YTH', 'parts': '辶+首'},
        {'char': '起', 'code': 'GOU', 'parts': '走+己'},
        {'char': '睡', 'code': 'BHAJ', 'parts': '目+垂'},
        {'char': '眼', 'code': 'BHE', 'parts': '目+艮'},
        {'char': '睛', 'code': 'BTJ', 'parts': '目+青'},
        {'char': '耳', 'code': 'SJ', 'parts': '耳'},
        {'char': '言', 'code': 'YRRR', 'parts': '言'},
        {'char': '說', 'code': 'YRH', 'parts': '言+兌'},
        {'char': '話', 'code': 'YRJ', 'parts': '言+舌'},
        {'char': '讀', 'code': 'YRC', 'parts': '言+賣'},
        {'char': '書', 'code': 'HDA', 'parts': '聿+曰'},
        {'char': '筆', 'code': 'HQS', 'parts': '竹+聿'},
        {'char': '畫', 'code': 'LGW', 'parts': '聿+田'},
        {'char': '腳', 'code': 'BQJ', 'parts': '月+卻'},
        {'char': '頭', 'code': 'YRV', 'parts': '豆+頁'},
        {'char': '命', 'code': 'OIR', 'parts': '人+口'},
        {'char': '生', 'code': 'HG', 'parts': '牛'},
        {'char': '老', 'code': 'KFP', 'parts': '耂+匕'},
        {'char': '師', 'code': 'HLJ', 'parts': '𠂤+帀'},
        {'char': '意', 'code': 'YFP', 'parts': '立+日+心'},
        {'char': '思', 'code': 'WP', 'parts': '田+心'},
        {'char': '愛', 'code': 'BXP', 'parts': '爪+冖+心'},
        {'char': '友', 'code': 'HK', 'parts': '𠂇+又'},
        {'char': '情', 'code': 'BQJ', 'parts': '心+青'},
        {'char': '感', 'code': 'IPPU', 'parts': '咸+心'},
        {'char': '動', 'code': 'HJS', 'parts': '重+力'},
        {'char': '工', 'code': 'M', 'parts': '工'},
        {'char': '由', 'code': 'LW', 'parts': '由'},
        {'char': '用', 'code': 'BQ', 'parts': '月+用'},
        {'char': '分', 'code': 'O', 'parts': '人+刀'},
        {'char': '切', 'code': 'PS', 'parts': '七+刀'},
        {'char': '包', 'code': 'PN', 'parts': '勹+已'},
        {'char': '北', 'code': 'IL', 'parts': '匕+月'},
        {'char': '午', 'code': 'OJ', 'parts': '人+十'},
        {'char': '真', 'code': 'JHP', 'parts': '十+目+一'},
        {'char': '石', 'code': 'MR', 'parts': '石+口'},
        {'char': '右', 'code': 'MR', 'parts': '口+十'},
        {'char': '司', 'code': 'RN', 'parts': '口+月'},
        {'char': '局', 'code': 'RS', 'parts': '口+尸'},
        {'char': '尿', 'code': 'NE', 'parts': '尸+水'},
        {'char': '尼', 'code': 'ES', 'parts': '尸+比'},
        {'char': '尾', 'code': 'NS', 'parts': '尸+毛'},
        {'char': '屁', 'code': 'IP', 'parts': '尸+比'},
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
