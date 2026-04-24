"""
Personal Homepage with Chinese Vocabulary Test
Flask Web App for PythonAnywhere
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime, date
from werkzeug.utils import secure_filename

import requests
import os
import subprocess
# Auto-pull latest code on startup
try:
    result = subprocess.run(['git', 'pull', 'origin', 'main'], cwd=os.path.dirname(__file__), capture_output=True, text=True, timeout=30)
    if result.returncode == 0 and result.stdout.strip():
        print(f"[Git Pull] {result.stdout.strip()}")
except: pass

import random
import json
import os
import re
import sqlite3
from dotenv import load_dotenv

# Load .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kelvin-webapp-secret-key-change-in-production')

# App version
APP_VERSION = 'v6.39'


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
        {'char': '男', 'code': 'WKS', 'parts': '田大力'},
        {'char': '明', 'code': 'AB', 'parts': '日月'},
        {'char': '林', 'code': 'DD', 'parts': '木木'},
        {'char': '和', 'code': 'HDR', 'parts': '竹木口'},
        {'char': '花', 'code': 'TOP', 'parts': '廿人心'},
        {'char': '想', 'code': 'DUP', 'parts': '木山心'},
        {'char': '看', 'code': 'HQBU', 'parts': '竹手月山'},
        {'char': '國', 'code': 'WIRM', 'parts': '田戈口一'},
        {'char': '電', 'code': 'MBWU', 'parts': '一月田山'},
        {'char': '語', 'code': 'YRMMR', 'parts': '卜口一一口'},
        {'char': '聽', 'code': 'SGJWP', 'parts': '尸土十田心'},
        {'char': '問', 'code': 'ANR', 'parts': '日弓口'},
        {'char': '開', 'code': 'ANMT', 'parts': '日弓一廿'},
        {'char': '地', 'code': 'GPD', 'parts': '土心木'},
        {'char': '天', 'code': 'MK', 'parts': '一大'},
        {'char': '王', 'code': 'MG', 'parts': '一土'},
        {'char': '星', 'code': 'AHQM', 'parts': '日竹手一'},
        {'char': '信', 'code': 'OYMR', 'parts': '人卜一口'},
        {'char': '你', 'code': 'ONF', 'parts': '人弓火'},
        {'char': '伯', 'code': 'OHA', 'parts': '人竹日'},
        {'char': '家', 'code': 'JMSO', 'parts': '十一尸人'},
        {'char': '鬧', 'code': 'LNYLB', 'parts': '中弓卜中月'},
        {'char': '閉', 'code': 'ANDH', 'parts': '日弓木竹'},
        {'char': '閒', 'code': 'ANB', 'parts': '日弓月'},
        {'char': '圖', 'code': 'WRYW', 'parts': '田囗卜田'},
        {'char': '跑', 'code': 'RMPRU', 'parts': '口一心口山'},
        {'char': '路', 'code': 'RMHER', 'parts': '口一竹水口'},
        {'char': '這', 'code': 'YYMR', 'parts': '卜卜一口'},
        {'char': '都', 'code': 'JANL', 'parts': '十日弓中'},
        {'char': '進', 'code': 'YOG', 'parts': '卜人土'},
        {'char': '退', 'code': 'YAV', 'parts': '卜日女'},
        {'char': '起', 'code': 'GORU', 'parts': '土人口山'},
        {'char': '眼', 'code': 'BUAV', 'parts': '月山日女'},
        {'char': '說', 'code': 'YRCRU', 'parts': '卜口金口山'},
        {'char': '話', 'code': 'YRHJR', 'parts': '卜口竹十口'},
        {'char': '讀', 'code': 'YRGWC', 'parts': '卜口土田金'},
        {'char': '書', 'code': 'LGA', 'parts': '中土日'},
        {'char': '筆', 'code': 'HLQ', 'parts': '竹中手'},
        {'char': '畫', 'code': 'LGWM', 'parts': '中土田一'},
        {'char': '腳', 'code': 'BCRL', 'parts': '月金口中'},
        {'char': '頭', 'code': 'MTMBC', 'parts': '一廿一月金'},
        {'char': '命', 'code': 'OMRL', 'parts': '人一口中'},
        {'char': '愛', 'code': 'BBPE', 'parts': '月月心水'},
        {'char': '情', 'code': 'PQMB', 'parts': '心手一月'},
        {'char': '分', 'code': 'CSH', 'parts': '金尸竹'},
        {'char': '局', 'code': 'SSR', 'parts': '尸尸口'},
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



@app.route('/geckolab')
def geckolab():
    """Geckolab - Gecko Care Management App Landing Page"""
    return render_template('geckolab.html', version=APP_VERSION)

@app.route('/geckolab/api/login', methods=['POST'])
def geckolab_login():
    password = request.form.get('password', '')
    env_password = get_geckolab_password()
    if password == env_password:
        session['geckolab_logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid password'})

@app.route('/geckolab/logout')
def geckolab_logout():
    session.pop('geckolab_logged_in', None)
    return redirect(url_for('geckolab'))

    app.run(debug=True)

# ==================== GECKOLAB CONSTANTS ====================
GECKOLAB_DIR = os.path.join(os.path.dirname(__file__), 'geckolab')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'geckolab', 'uploads')
DB_PATH = os.path.join(GECKOLAB_DIR, 'geckolab.db')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_geckolab_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS geckos (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, species TEXT, dob TEXT, adopted_date TEXT, color TEXT DEFAULT '#FF6B6B', avatar_path TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS weight_records (id INTEGER PRIMARY KEY AUTOINCREMENT, gecko_id INTEGER NOT NULL, weight REAL NOT NULL, record_date TEXT NOT NULL, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (gecko_id) REFERENCES geckos(id) ON DELETE CASCADE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, gecko_id INTEGER NOT NULL, log_date TEXT NOT NULL, log_type TEXT NOT NULL, quantity TEXT, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (gecko_id) REFERENCES geckos(id) ON DELETE CASCADE)''')
    conn.commit()
    conn.close()
init_geckolab_db()

@app.route('/geckolab/api/geckos', methods=['GET'])
def get_geckos():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''SELECT g.*, (SELECT weight FROM weight_records WHERE gecko_id=g.id ORDER BY record_date DESC LIMIT 1) as latest_weight FROM geckos g ORDER BY g.name''')
    geckos = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'geckos': geckos})

@app.route('/geckolab/api/geckos', methods=['POST'])
def add_gecko():
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    name = request.form.get('name', '').strip()
    species = request.form.get('species', '').strip()
    dob = request.form.get('dob', '').strip()
    adopted_date = request.form.get('adopted_date', '').strip()
    color = request.form.get('color', '#FF6B6B').strip()
    avatar_path = None
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"gecko_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            avatar_path = f'/static/geckolab/uploads/{filename}'
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO geckos (name, species, dob, adopted_date, color, avatar_path) VALUES (?,?,?,?,?,?)', (name, species, dob, adopted_date, color, avatar_path))
    gecko_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'gecko_id': gecko_id})

@app.route('/geckolab/api/geckos/<int:gecko_id>', methods=['GET'])
def get_gecko(gecko_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM geckos WHERE id=?', (gecko_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'Not found'}), 404
    gecko = dict(row)
    if gecko.get('dob'):
        try:
            dob_date = datetime.strptime(gecko['dob'], '%Y-%m-%d').date()
            age_days = (date.today() - dob_date).days
            gecko['age_years'] = age_days // 365
            gecko['age_months'] = (age_days % 365) // 30
            gecko['age_days'] = age_days % 30
        except: pass
    c.execute('SELECT weight FROM weight_records WHERE gecko_id=? ORDER BY record_date DESC LIMIT 1', (gecko_id,))
    w = c.fetchone()
    gecko['latest_weight'] = w['weight'] if w else None
    conn.close()
    return jsonify({'success': True, 'gecko': gecko})

@app.route('/geckolab/api/geckos/<int:gecko_id>', methods=['PUT'])
def update_gecko(gecko_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    name = request.form.get('name', '').strip()
    species = request.form.get('species', '').strip()
    dob = request.form.get('dob', '').strip()
    adopted_date = request.form.get('adopted_date', '').strip()
    color = request.form.get('color', '#FF6B6B').strip()
    avatar_path = None
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"gecko_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            avatar_path = f'/static/geckolab/uploads/{filename}'
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if avatar_path:
        c.execute('UPDATE geckos SET name=?, species=?, dob=?, adopted_date=?, color=?, avatar_path=? WHERE id=?', (name, species, dob, adopted_date, color, avatar_path, gecko_id))
    else:
        c.execute('UPDATE geckos SET name=?, species=?, dob=?, adopted_date=?, color=? WHERE id=?', (name, species, dob, adopted_date, color, gecko_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/geckolab/api/geckos/<int:gecko_id>/avatar', methods=['DELETE'])
@app.route('/geckolab/api/geckos/<int:gecko_id>', methods=['DELETE'])
def delete_gecko(gecko_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM daily_logs WHERE gecko_id=?', (gecko_id,))
    c.execute('DELETE FROM weight_records WHERE gecko_id=?', (gecko_id,))
    c.execute('DELETE FROM geckos WHERE id=?', (gecko_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/geckos/<int:gecko_id>/weights', methods=['GET'])
def get_weight_history(gecko_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM weight_records WHERE gecko_id=? ORDER BY record_date DESC', (gecko_id,))
    weights = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'weights': weights})

@app.route('/geckolab/api/geckos/<int:gecko_id>/weights', methods=['POST'])
def add_weight(gecko_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    weight = float(request.form.get('weight', 0))
    record_date = request.form.get('record_date', datetime.now().strftime('%Y-%m-%d'))
    notes = request.form.get('notes', '').strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO weight_records (gecko_id, weight, record_date, notes) VALUES (?,?,?,?)', (gecko_id, weight, record_date, notes))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/geckos/<int:gecko_id>/logs', methods=['GET'])
def get_gecko_logs(gecko_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM daily_logs WHERE gecko_id=? ORDER BY log_date DESC', (gecko_id,))
    logs = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'logs': logs})

@app.route('/geckolab/api/logs', methods=['GET'])
def get_logs_by_date():
    log_date = request.args.get('date')
    if not log_date:
        return jsonify({'success': False, 'error': 'Date required'})
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT l.*, g.name, g.color FROM daily_logs l JOIN geckos g ON l.gecko_id=g.id WHERE l.log_date=?', (log_date,))
    logs = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'logs': logs})

@app.route('/geckolab/api/logs/month', methods=['GET'])
def get_logs_by_month():
    month = request.args.get('month')
    year = request.args.get('year')
    if not month or not year:
        return jsonify({'success': False, 'error': 'Month and year required'})
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT l.*, g.name, g.color FROM daily_logs l JOIN geckos g ON l.gecko_id=g.id WHERE strftime('%Y', l.log_date)=? AND strftime('%m', l.log_date)=?", (year, month.zfill(2)))
    logs = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify({'success': True, 'logs': logs})

@app.route('/geckolab/api/geckos/<int:gecko_id>/logs', methods=['POST'])
def add_daily_log(gecko_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    log_type = request.form.get('log_type', '')
    log_date = request.form.get('log_date', datetime.now().strftime('%Y-%m-%d'))
    quantity = request.form.get('quantity', '').strip()
    notes = request.form.get('notes', '').strip()
    if log_type not in ('feeding', 'peeling', 'poo', 'pee'):
        return jsonify({'success': False, 'error': 'Invalid log type'})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO daily_logs (gecko_id, log_date, log_type, quantity, notes) VALUES (?,?,?,?,?)', (gecko_id, log_date, log_type, quantity, notes))
    log_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'log_id': log_id})

@app.route('/geckolab/api/logs/<int:log_id>', methods=['DELETE'])
def delete_log(log_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM daily_logs WHERE id=?', (log_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

    app.run(debug=True)

@app.route('/geckolab/api/change-password', methods=['POST'])
def geckolab_change_password():
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    old_pwd = request.form.get('old_password', '')
    new_pwd = request.form.get('new_password', '')
    current_password = get_geckolab_password()
    if old_pwd != current_password:
        return jsonify({'success': False, 'error': '舊密碼錯誤'})
    save_geckolab_password(new_pwd)
    return jsonify({'success': True, 'message': '密碼已更改'})

@app.route('/geckolab/api/reset-data', methods=['POST'])
def geckolab_reset_data():
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM daily_logs')
    c.execute('DELETE FROM weight_records')
    c.execute('DELETE FROM geckos')
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)

# Password file for Geckolab
GECKOLAB_PASS_FILE = os.path.join(os.path.dirname(__file__), 'geckolab', 'password.json')

def get_geckolab_password():
    try:
        if os.path.exists(GECKOLAB_PASS_FILE):
            import json as _json
            with open(GECKOLAB_PASS_FILE, 'r') as f:
                data = _json.load(f)
                return data.get('password', os.environ.get('GECKOLAB_PASSWORD', 'geckolab123'))
    except: pass
    return os.environ.get('GECKOLAB_PASSWORD', 'geckolab123')

def save_geckolab_password(new_password):
    import json as _json
    with open(GECKOLAB_PASS_FILE, 'w') as f:
        _json.dump({'password': new_password}, f)
