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
APP_VERSION = 'v5.86'


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
    1: [
        {'char': '日', 'code': 'AAA', 'hint': '日日日 (AAA)'},
        {'char': '月', 'code': 'BAA', 'hint': '月月月 (BAA)'},
        {'char': '木', 'code': 'D', 'hint': '木 (D)'},
        {'char': '水', 'code': 'E', 'hint': '水 (E)'},
        {'char': '火', 'code': 'F', 'hint': '火 (F)'},
        {'char': '土', 'code': 'G', 'hint': '土 (G)'},
        {'char': '金', 'code': 'C', 'hint': '金 (C)'},
        {'char': '人', 'code': 'O', 'hint': '人 (O)'},
        {'char': '心', 'code': 'XU', 'hint': '心心心 (XU)'},
        {'char': '手', 'code': 'Q', 'hint': '手 (Q)'},
        {'char': '口', 'code': 'R', 'hint': '口 (R)'},
        {'char': '山', 'code': 'U', 'hint': '山 (U)'},
        {'char': '石', 'code': 'GR', 'hint': '石 (GR)'},
        {'char': '田', 'code': 'W', 'hint': '田 (W)'},
        {'char': '卜', 'code': 'Y', 'hint': '卜 (Y)'},
        {'char': '中', 'code': 'JR', 'hint': '中 (JR)'},
        {'char': '大', 'code': 'K', 'hint': '大 (K)'},
        {'char': '小', 'code': 'U', 'hint': '小 (U)'},
        {'char': '女', 'code': 'V', 'hint': '女 (V)'},
        {'char': '竹', 'code': 'H', 'hint': '竹 (H)'},
        {'char': '戈', 'code': 'IP', 'hint': '戈 (IP)'},
        {'char': '十', 'code': 'J', 'hint': '十 (J)'},
        {'char': '弓', 'code': 'N', 'hint': '弓 (N)'},
        {'char': '人人', 'code': 'OO', 'hint': '人人 (OO)'},
        {'char': '日日', 'code': 'AA', 'hint': '日日 (AA)'},
        {'char': '月月', 'code': 'BB', 'hint': '月月 (BB)'},
        {'char': '木木', 'code': 'DD', 'hint': '木木 (DD)'},
        {'char': '水水', 'code': 'EE', 'hint': '水水 (EE)'},
        {'char': '火火', 'code': 'FF', 'hint': '火火 (FF)'},
        {'char': '土土', 'code': 'GG', 'hint': '土土 (GG)'},
        {'char': '金金', 'code': 'CC', 'hint': '金金 (CC)'},
        {'char': '人心', 'code': 'OXU', 'hint': '人心 (OXU)'},
        {'char': '日月', 'code': 'BA', 'hint': '日月 (BA)'},
        {'char': '山水', 'code': 'UE', 'hint': '山水 (UE)'},
        {'char': '木材', 'code': 'DC', 'hint': '木材 (DC)'},
        {'char': '火土', 'code': 'FG', 'hint': '火土 (FG)'},
        {'char': '金水', 'code': 'CE', 'hint': '金水 (CE)'},
        {'char': '人口', 'code': 'OR', 'hint': '人口 (OR)'},
        {'char': '手工', 'code': 'QD', 'hint': '手工 (QD)'},
        {'char': '大山', 'code': 'KU', 'hint': '大山 (KU)'},
        {'char': '石田', 'code': 'GRW', 'hint': '石田 (GRW)'},
        {'char': '卜口', 'code': 'YR', 'hint': '卜口 (YR)'},
        {'char': '中大', 'code': 'JK', 'hint': '中大 (JK)'},
        {'char': '大小', 'code': 'KU', 'hint': '大小 (KU)'},
        {'char': '女心', 'code': 'VXU', 'hint': '女心 (VXU)'},
        {'char': '竹木', 'code': 'HD', 'hint': '竹木 (HD)'},
        {'char': '戈弓', 'code': 'IN', 'hint': '戈弓 (IN)'},
        {'char': '十心', 'code': 'JXU', 'hint': '十心 (JXU)'},
        {'char': '弓手', 'code': 'NQ', 'hint': '弓手 (NQ)'},
        {'char': '日火', 'code': 'AF', 'hint': '日火 (AF)'},
        {'char': '月水', 'code': 'BE', 'hint': '月水 (BE)'},
        {'char': '木金', 'code': 'DC', 'hint': '木金 (DC)'},
        {'char': '水土', 'code': 'EG', 'hint': '水土 (EG)'},
        {'char': '火金', 'code': 'FC', 'hint': '火金 (FC)'},
        {'char': '金火', 'code': 'CF', 'hint': '金火 (CF)'},
        {'char': '人口心', 'code': 'ORXU', 'hint': '人口心 (ORXU)'},
        {'char': '手心', 'code': 'QXU', 'hint': '手心 (QXU)'},
        {'char': '山川', 'code': 'UU', 'hint': '山川 (UU)'},
        {'char': '石口', 'code': 'GRR', 'hint': '石口 (GRR)'},
        {'char': '卜田', 'code': 'YW', 'hint': '卜田 (YW)'},
        {'char': '中口', 'code': 'JR', 'hint': '中口 (JR)'},
        {'char': '大女', 'code': 'KV', 'hint': '大女 (KV)'},
        {'char': '小竹', 'code': 'UH', 'hint': '小竹 (UH)'},
        {'char': '女戈', 'code': 'VIP', 'hint': '女戈 (VIP)'},
        {'char': '竹弓', 'code': 'HN', 'hint': '竹弓 (HN)'},
        {'char': '戈十', 'code': 'IJ', 'hint': '戈十 (IJ)'},
        {'char': '十戈', 'code': 'JIP', 'hint': '十戈 (JIP)'},
        {'char': '弓心', 'code': 'NXU', 'hint': '弓心 (NXU)'},
        {'char': '心心', 'code': 'XU', 'hint': '心心 (XU)'},
        {'char': '手竹', 'code': 'QH', 'hint': '手竹 (QH)'},
        {'char': '人口竹', 'code': 'ORH', 'hint': '人口竹 (ORH)'},
        {'char': '日日日', 'code': 'AAA', 'hint': '日日日 (AAA)'},
        {'char': '月月月', 'code': 'BAA', 'hint': '月月月 (BAA)'},
        {'char': '木木木', 'code': 'DDD', 'hint': '木木木 (DDD)'},
        {'char': '水水水', 'code': 'EEE', 'hint': '水水水 (EEE)'},
        {'char': '火火火', 'code': 'FFF', 'hint': '火火火 (FFF)'},
        {'char': '土土土', 'code': 'GGG', 'hint': '土土土 (GGG)'},
        {'char': '金金金', 'code': 'CCC', 'hint': '金金金 (CCC)'},
        {'char': '人人人', 'code': 'OOO', 'hint': '人人人 (OOO)'},
        {'char': '心心心', 'code': 'XU', 'hint': '心心心 (XU)'},
        {'char': '卜卜', 'code': 'YY', 'hint': '卜卜 (YY)'},
        {'char': '中中', 'code': 'JJ', 'hint': '中中 (JJ)'},
        {'char': '大大', 'code': 'KK', 'hint': '大大 (KK)'},
        {'char': '小小', 'code': 'UU', 'hint': '小小 (UU)'},
        {'char': '女女', 'code': 'VV', 'hint': '女女 (VV)'},
        {'char': '竹竹', 'code': 'HH', 'hint': '竹竹 (HH)'},
        {'char': '戈戈', 'code': 'II', 'hint': '戈戈 (II)'},
        {'char': '十十', 'code': 'JJ', 'hint': '十十 (JJ)'},
        {'char': '弓弓', 'code': 'NN', 'hint': '弓弓 (NN)'},
        {'char': '口口', 'code': 'RR', 'hint': '口口 (RR)'},
        {'char': '山山', 'code': 'UU', 'hint': '山山 (UU)'},
        {'char': '石石', 'code': 'GRG', 'hint': '石石 (GRG)'},
        {'char': '田田', 'code': 'WW', 'hint': '田田 (WW)'},
        {'char': '木手', 'code': 'DQ', 'hint': '木手 (DQ)'},
        {'char': '水火', 'code': 'EF', 'hint': '水火 (EF)'},
    ],
    2: [
        {'char': '眼', 'code': 'BHAU', 'hint': '目+象 (BHAU)'},
        {'char': '睛', 'code': 'BHA', 'hint': '目+青 (BHA)'},
        {'char': '氵', 'code': 'E', 'hint': '水部 (E)'},
        {'char': '氵', 'code': 'E', 'hint': '三點水 (E)'},
        {'char': '�', 'code': 'EHHV', 'hint': '水+麗 (EHHV)'},
        {'char': '海', 'code': 'EYYK', 'hint': '水+每 (EYYK)'},
        {'char': '江', 'code': 'E', 'hint': '水+工 (EG)'},
        {'char': '河', 'code': 'E', 'hint': '水+可 (ERK)'},
        {'char': '湖', 'code': 'EWW', 'hint': '水+胡 (EWW)'},
        {'char': '泉', 'code': 'E', 'hint': '白+水 (BU)'},
        {'char': '艹', 'code': 'T', 'hint': '草頭 (T)'},
        {'char': '花', 'code': 'THX', 'hint': '艹+化 (THX)'},
        {'char': '芳', 'code': 'THO', 'hint': '艹+方 (THO)'},
        {'char': '荷', 'code': 'THR', 'hint': '艹+何 (THR)'},
        {'char': '苦', 'code': 'TR', 'hint': '艹+古 (TR)'},
        {'char': '茶', 'code': 'TWO', 'hint': '艹+茶 (TWO)'},
        {'char': '萬', 'code': 'TWO', 'hint': '艹+萬 (TWOT)'},
        {'char': '莫', 'code': 'TBR', 'hint': '艹+日 (TBR)'},
        {'char': '蔔', 'code': 'YPU', 'hint': '卜+葡 (YPU)'},
        {'char': '夢', 'code': 'BVNQ', 'hint': '冖+夕 (BVNQ)'},
        {'char': '艹', 'code': 'T', 'hint': '草 (T)'},
        {'char': '薛', 'code': 'TWV', 'hint': '艹+薛 (TWV)'},
        {'char': '藏', 'code': 'THOI', 'hint': '艹+藏 (THOI)'},
        {'char': '蕊', 'code': 'TYMF', 'hint': '艹+蕊 (TYMF)'},
        {'char': '薰', 'code': 'TFDI', 'hint': '艹+熏 (TFDI)'},
        {'char': '藍', 'code': 'TWB', 'hint': '艹+藍 (TWB)'},
        {'char': '藕', 'code': 'TWIM', 'hint': '艹+耦 (TWIM)'},
        {'char': '蘭', 'code': 'TWJ', 'hint': '艹+蘭 (TWJ)'},
        {'char': '蘆', 'code': 'TXC', 'hint': '艹+盧 (TXC)'},
        {'char': '蘋', 'code': 'FMB', 'hint': '艹+頻 (FMB)'},
        {'char': '垂', 'code': 'TJ', 'hint': '土+艸 (TJ)'},
        {'char': '重', 'code': 'JJC', 'hint': '千+日 (JJC)'},
        {'char': '復', 'code': 'OHE', 'hint': '彳+日 (OHE)'},
        {'char': '泉', 'code': 'BUU', 'hint': '白+水 (BUU)'},
        {'char': '韓', 'code': 'HWJ', 'hint': '卓+韋 (HWJ)'},
        {'char': '韋', 'code': 'W', 'hint': '韋 (W)'},
        {'char': '日', 'code': 'A', 'hint': '日 (A)'},
        {'char': '曰', 'code': 'A', 'hint': '曰 (A)'},
        {'char': '曲', 'code': 'W', 'hint': '曲 (W)'},
        {'char': '書', 'code': 'HIO', 'hint': '書 (HIO)'},
        {'char': '冒', 'code': 'AB', 'hint': '冒 (AB)'},
        {'char': '冕', 'code': 'UUP', 'hint': '免+冂 (UUP)'},
        {'char': '最', 'code': 'CI', 'hint': '最 (CI)'},
        {'char': '會', 'code': 'OIR', 'hint': '曾+人 (OIR)'},
        {'char': '朧', 'code': 'BQG', 'hint': '龍+月 (BQG)'},
        {'char': '龜', 'code': 'HXU', 'hint': '龜 (HXU)'},
        {'char': '龍', 'code': 'L', 'hint': '龍 (L)'},
        {'char': '龜', 'code': 'W', 'hint': '龜 (W)'},
        {'char': '肅', 'code': 'QSK', 'hint': '肅 (QSK)'},
        {'char': '黾', 'code': 'W', 'hint': '黽 (W)'},
        {'char': '鼎', 'code': 'HQ', 'hint': '鼎 (HQ)'},
        {'char': '鼓', 'code': 'HR', 'hint': '鼓 (HR)'},
        {'char': '鼠', 'code': 'HV', 'hint': '鼠 (HV)'},
        {'char': '齊', 'code': 'YI', 'hint': '齊 (YI)'},
        {'char': '齒', 'code': 'YO', 'hint': '齒 (YO)'},
        {'char': '龍', 'code': 'K', 'hint': '龍 (K)'},
        {'char': '龜', 'code': 'Y', 'hint': '龜 (Y)'},
        {'char': '戈', 'code': 'IP', 'hint': '戈 (IP)'},
        {'char': '戊', 'code': 'IP', 'hint': '戊 (IP)'},
        {'char': '戌', 'code': 'IP', 'hint': '戌 (IP)'},
        {'char': '戍', 'code': 'IP', 'hint': '戍 (IP)'},
        {'char': '戎', 'code': 'IP', 'hint': '戎 (IP)'},
        {'char': '戒', 'code': 'IP', 'hint': '戒 (IP)'},
        {'char': '戕', 'code': 'IP', 'hint': '戕 (IP)'},
        {'char': '或', 'code': 'IPOR', 'hint': '或 (IPOR)'},
        {'char': '戚', 'code': 'IPF', 'hint': '戚 (IPF)'},
        {'char': '戛', 'code': 'IP', 'hint': '戛 (IP)'},
        {'char': '戟', 'code': 'IPJR', 'hint': '戟 (IPJR)'},
        {'char': '戢', 'code': 'IP', 'hint': '戢 (IP)'},
        {'char': '戢', 'code': 'IP', 'hint': '戢 (IP)'},
        {'char': '戶', 'code': 'H', 'hint': '戶 (H)'},
        {'char': '門', 'code': 'BN', 'hint': '門 (BN)'},
        {'char': '卯', 'code': 'H', 'hint': '卯 (H)'},
        {'char': '氈', 'code': 'HFQ', 'hint': '毛+占 (HFQ)'},
        {'char': '毯', 'code': 'HFQ', 'hint': '毛+炎 (HFQ)'},
        {'char': '氌', 'code': 'HL', 'hint': '毛+魯 (HL)'},
        {'char': '毀', 'code': 'OGF', 'hint': '每+殳 (OGF)'},
        {'char': '敖', 'code': 'FHQ', 'hint': '土+反 (FHQ)'},
        {'char': '毫', 'code': 'YV', 'hint': '亳 (YV)'},
        {'char': '勃', 'code': 'NPM', 'hint': '孛+力 (NPM)'},
        {'char': '勇', 'code': 'NPS', 'hint': '甬+力 (NPS)'},
        {'char': '勉', 'code': 'HK', 'hint': '免+力 (HKN)'},
        {'char': '勒', 'code': 'KS', 'hint': '革+力 (KS)'},
        {'char': '務', 'code': 'HDS', 'hint': '矛+夂 (HDS)'},
        {'char': '勘', 'code': 'XSV', 'hint': '甚+力 (XSV)'},
        {'char': '智', 'code': 'ARA', 'hint': '知+日 (ARA)'},
        {'char': '乍', 'code': 'O', 'hint': '乍 (O)'},
        {'char': '洛', 'code': 'VIK', 'hint': '各+口 (VIK)'},
        {'char': '客', 'code': 'JR', 'hint': '客 (JR)'},
        {'char': '額', 'code': 'YPR', 'hint': '客+頁 (YPR)'},
        {'char': '題', 'code': 'RRN', 'hint': '是+頁 (RRN)'},
        {'char': '順', 'code': 'LO', 'hint': '川+頁 (LO)'},
        {'char': '預', 'code': 'NMO', 'hint': '予+頁 (NMO)'},
        {'char': '頭', 'code': 'YRV', 'hint': '豆+頁 (YRV)'},
        {'char': '題', 'code': 'AF', 'hint': '日+是 (AF)'},
    ],
    3: [
        {'char': '我', 'code': 'NHQ', 'hint': '我的手 (NHQ)'},
        {'char': '你', 'code': 'O', 'hint': '你的人 (O)'},
        {'char': '他', 'code': 'OH', 'hint': '他的人 (OH)'},
        {'char': '們', 'code': 'OGN', 'hint': '們 (OGN)'},
        {'char': '的', 'code': 'MHR', 'hint': '的白 (MHR)'},
        {'char': '是', 'code': 'A', 'hint': '是非 (A)'},
        {'char': '在', 'code': 'IK', 'hint': '在此 (IK)'},
        {'char': '有', 'code': 'E', 'hint': '沒有 (E)'},
        {'char': '和', 'code': 'H', 'hint': '和 (H)'},
        {'char': '為', 'code': 'I', 'hint': '為 (I)'},
        {'char': '這', 'code': 'I', 'hint': '這 (I)'},
        {'char': '中', 'code': 'JR', 'hint': '中間 (JR)'},
        {'char': '大', 'code': 'K', 'hint': '大小 (K)'},
        {'char': '小', 'code': 'U', 'hint': '小 (U)'},
        {'char': '年', 'code': 'OF', 'hint': '年月 (OF)'},
        {'char': '月', 'code': 'BAA', 'hint': '月份 (BAA)'},
        {'char': '日', 'code': 'AAA', 'hint': '日期 (AAA)'},
        {'char': '時', 'code': 'JR', 'hint': '時間 (JR)'},
        {'char': '分', 'code': 'O', 'hint': '分 (O)'},
        {'char': '秒', 'code': 'OF', 'hint': '秒 (OF)'},
        {'char': '看', 'code': 'HA', 'hint': '看 (HA)'},
        {'char': '見', 'code': 'U', 'hint': '見 (U)'},
        {'char': '聽', 'code': 'Y', 'hint': '聽 (Y)'},
        {'char': '說', 'code': 'YSR', 'hint': '說話 (YSR)'},
        {'char': '讀', 'code': 'IWR', 'hint': '讀書 (IWR)'},
        {'char': '寫', 'code': 'W', 'hint': '寫 (W)'},
        {'char': '書', 'code': 'HIO', 'hint': '書本 (HIO)'},
        {'char': '本', 'code': 'D', 'hint': '本 (D)'},
        {'char': '文', 'code': 'K', 'hint': '文字 (K)'},
        {'char': '字', 'code': 'I', 'hint': '字 (I)'},
        {'char': '國', 'code': 'W', 'hint': '國家 (W)'},
        {'char': '人', 'code': 'O', 'hint': '人 (O)'},
        {'char': '我', 'code': 'NHQ', 'hint': '我 (NHQ)'},
        {'char': '們', 'code': 'OGN', 'hint': '們 (OGN)'},
        {'char': '你', 'code': 'O', 'hint': '你 (O)'},
        {'char': '他', 'code': 'OH', 'hint': '他 (OH)'},
        {'char': '她', 'code': 'OH', 'hint': '她 (OH)'},
        {'char': '它', 'code': 'H', 'hint': '它 (H)'},
        {'char': '們', 'code': 'OGN', 'hint': '們 (OGN)'},
        {'char': '的', 'code': 'MHR', 'hint': '的 (MHR)'},
        {'char': '了', 'code': 'X', 'hint': '了 (X)'},
        {'char': '在', 'code': 'IK', 'hint': '在 (IK)'},
        {'char': '是', 'code': 'A', 'hint': '是 (A)'},
        {'char': '有', 'code': 'E', 'hint': '有 (E)'},
        {'char': '和', 'code': 'H', 'hint': '和 (H)'},
        {'char': '為', 'code': 'I', 'hint': '為 (I)'},
        {'char': '這', 'code': 'I', 'hint': '這 (I)'},
        {'char': '那', 'code': 'P', 'hint': '那 (P)'},
        {'char': '都', 'code': 'IOR', 'hint': '都 (IOR)'},
        {'char': '着', 'code': 'Y', 'hint': '着 (Y)'},
        {'char': '過', 'code': 'IW', 'hint': '過 (IW)'},
        {'char': '來', 'code': 'X', 'hint': '來 (X)'},
        {'char': '去', 'code': 'X', 'hint': '去 (X)'},
        {'char': '能', 'code': 'X', 'hint': '能 (X)'},
        {'char': '很', 'code': 'O', 'hint': '很 (O)'},
        {'char': '好', 'code': 'V', 'hint': '好 (V)'},
        {'char': '很', 'code': 'O', 'hint': '很 (O)'},
        {'char': '多', 'code': 'H', 'hint': '多 (H)'},
        {'char': '少', 'code': 'U', 'hint': '少 (U)'},
        {'char': '見', 'code': 'U', 'hint': '見 (U)'},
        {'char': '現', 'code': 'AW', 'hint': '現 (AW)'},
        {'char': '在', 'code': 'IK', 'hint': '在 (IK)'},
        {'char': '時', 'code': 'JR', 'hint': '時 (JR)'},
        {'char': '候', 'code': 'O', 'hint': '候 (O)'},
        {'char': '候', 'code': 'O', 'hint': '候 (O)'},
        {'char': '知', 'code': 'IR', 'hint': '知 (IR)'},
        {'char': '道', 'code': 'I', 'hint': '道 (I)'},
        {'char': '理', 'code': 'V', 'hint': '理 (V)'},
        {'char': '學', 'code': 'X', 'hint': '學 (X)'},
        {'char': '校', 'code': 'D', 'hint': '校 (D)'},
        {'char': '生', 'code': 'C', 'hint': '生 (C)'},
        {'char': '習', 'code': 'X', 'hint': '習 (X)'},
        {'char': '慣', 'code': 'N', 'hint': '慣 (N)'},
        {'char': '例', 'code': 'X', 'hint': '例 (X)'},
        {'char': '題', 'code': 'RRN', 'hint': '題 (RRN)'},
        {'char': '目', 'code': 'B', 'hint': '目 (B)'},
        {'char': '前', 'code': 'X', 'hint': '前 (X)'},
        {'char': '後', 'code': 'X', 'hint': '後 (X)'},
        {'char': '年', 'code': 'OF', 'hint': '年 (OF)'},
        {'char': '年', 'code': 'OF', 'hint': '年 (OF)'},
        {'char': '兩', 'code': 'X', 'hint': '兩 (X)'},
        {'char': '三', 'code': 'E', 'hint': '三 (E)'},
        {'char': '四', 'code': 'W', 'hint': '四 (W)'},
        {'char': '五', 'code': 'K', 'hint': '五 (K)'},
        {'char': '六', 'code': 'I', 'hint': '六 (I)'},
        {'char': '七', 'code': 'I', 'hint': '七 (I)'},
        {'char': '八', 'code': 'O', 'hint': '八 (O)'},
        {'char': '九', 'code': 'X', 'hint': '九 (X)'},
        {'char': '十', 'code': 'J', 'hint': '十 (J)'},
        {'char': '百', 'code': 'HA', 'hint': '百 (HA)'},
        {'char': '千', 'code': 'O', 'hint': '千 (O)'},
        {'char': '萬', 'code': 'T', 'hint': '萬 (T)'},
        {'char': '億', 'code': 'X', 'hint': '億 (X)'},
        {'char': '第', 'code': 'X', 'hint': '第 (X)'},
        {'char': '一', 'code': 'M', 'hint': '一 (M)'},
        {'char': '二', 'code': 'M', 'hint': '二 (M)'},
        {'char': '三', 'code': 'E', 'hint': '三 (E)'},
        {'char': '四', 'code': 'W', 'hint': '四 (W)'},
        {'char': '五', 'code': 'K', 'hint': '五 (K)'},
        {'char': '六', 'code': 'I', 'hint': '六 (I)'},
        {'char': '七', 'code': 'I', 'hint': '七 (I)'},
        {'char': '八', 'code': 'O', 'hint': '八 (O)'},
        {'char': '九', 'code': 'X', 'hint': '九 (X)'},
        {'char': '十', 'code': 'J', 'hint': '十 (J)'},
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
