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
import random
import json
import os
import re
import sqlite3
import secrets
import bcrypt
from dotenv import load_dotenv

# Load .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'kelvin-webapp-secret-key-change-in-production')

# ==================== SECURITY: HTTPS Enforcement ====================
@app.before_request
def enforce_https():
    """Redirect HTTP to HTTPS on PythonAnywhere (behind proxy)."""
    if request.headers.get('X-Forwarded-Proto', 'https') == 'http':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

# ==================== SECURITY: Rate Limiter ====================
from collections import defaultdict
import time as _time

_rate_limits = defaultdict(list)  # key → list of timestamps

def rate_limit(max_requests, window_seconds, key_fn=None):
    """
    Decorator: limit requests per key (default: client IP).
    Returns 429 if limit exceeded.
    """
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = key_fn(request) if key_fn else request.remote_addr
            now = _time.time()
            cutoff = now - window_seconds
            # Clean old entries
            _rate_limits[key] = [t for t in _rate_limits[key] if t > cutoff]
            if len(_rate_limits[key]) >= max_requests:
                return jsonify({'error': 'Too many requests. Please try again later.'}), 429
            _rate_limits[key].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# Auto-pull latest code on EVERY request (ensures latest code is always loaded)
@app.before_request
def auto_git_pull():
    import os as _os
    app_dir = _os.path.dirname(__file__)
    lock_file = _os.path.join(app_dir, '.git', 'index.lock')
    try:
        # Remove stale lock file if it exists
        if _os.path.exists(lock_file):
            _os.remove(lock_file)
        r = subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=app_dir, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            with open('/tmp/auto_pull.log', 'a') as f:
                f.write(f'FETCH FAIL [{r.returncode}]: {r.stderr.strip()}\n')
            return
        r = subprocess.run(['git', 'reset', '--hard', 'origin/main'], cwd=app_dir, capture_output=True, text=True, timeout=30)
        with open('/tmp/auto_pull.log', 'a') as f:
            f.write(f'OK: {r.stdout.strip()}\n')
    except Exception as e:
        with open('/tmp/auto_pull.log', 'a') as f:
            f.write(f'EXCEPTION: {e}\n')

# App version
APP_VERSION = 'v7.78'

# Debug: read auto-pull log
@app.route('/debug/auto-pull.log')
def debug_auto_pull_log():
    try:
        with open('/tmp/auto_pull.log', 'r') as f:
            return f'<pre>{f.read()[-2000:]}</pre>'
    except FileNotFoundError:
        return 'No log yet'


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

# === Pronunciation Practice Blueprint ===
try:
    from pronunciation_bp import pronunciation_bp
    app.register_blueprint(pronunciation_bp)
except Exception as e:
    print(f"[INFO] Pronunciation blueprint not loaded: {e}")

# === Cooking Ideas Blueprint ===
try:
    from cooking import cooking_bp
    app.register_blueprint(cooking_bp, url_prefix='/cooking-ideas')
    print("[INFO] Cooking Ideas blueprint loaded")
except Exception as e:
    print(f"[INFO] Cooking Ideas blueprint not loaded: {e}")


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
@rate_limit(max_requests=5, window_seconds=60)  # Security: max 5 login attempts/minute/IP
def geckolab_login():
    password = request.form.get('password', '')
    success, upgraded = verify_password(password)
    if success:
        session['geckolab_logged_in'] = True
        # Create auth token for "remember me" - never expires
        token = secrets.token_hex(32)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()
        c.execute('INSERT INTO auth_tokens (token) VALUES (?)', (token,))
        conn.commit()
        conn.close()
        # Set cookie that never expires
        response = jsonify({'success': True})
        response.set_cookie('geckolab_token', token, max_age=None, httponly=True)
        return response
    return jsonify({'success': False, 'error': 'Invalid password'})

@app.route('/geckolab/api/check-auth', methods=['GET'])
def check_geckolab_auth():
    token = request.cookies.get('geckolab_token')
    if not token:
        return jsonify({'logged_in': False})
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('SELECT id FROM auth_tokens WHERE token = ?', (token,))
    result = c.fetchone()
    conn.close()
    if result:
        session['geckolab_logged_in'] = True
        return jsonify({'logged_in': True})
    return jsonify({'logged_in': False})

@app.route('/geckolab/logout')
def geckolab_logout():
    session.pop('geckolab_logged_in', None)
    # Remove token from database
    token = request.cookies.get('geckolab_token')
    if token:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()
        c.execute('DELETE FROM auth_tokens WHERE token = ?', (token,))
        conn.commit()
        conn.close()
    response = redirect(url_for('geckolab'))
    response.delete_cookie('geckolab_token')
    return response

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
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS geckos (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, species TEXT, dob TEXT, adopted_date TEXT, color TEXT DEFAULT '#FF6B6B', avatar_path TEXT, personality TEXT, album_url TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    try:
        c.execute("ALTER TABLE geckos ADD COLUMN album_url TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE geckos ADD COLUMN personality TEXT")
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS weight_records (id INTEGER PRIMARY KEY AUTOINCREMENT, gecko_id INTEGER NOT NULL, weight REAL NOT NULL, record_date TEXT NOT NULL, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (gecko_id) REFERENCES geckos(id) ON DELETE CASCADE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, gecko_id INTEGER NOT NULL, log_date TEXT NOT NULL, log_type TEXT NOT NULL, quantity TEXT, notes TEXT, period TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (gecko_id) REFERENCES geckos(id) ON DELETE CASCADE)''')
    try:
        c.execute("ALTER TABLE daily_logs ADD COLUMN period TEXT")
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS feeding_reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, gecko_id INTEGER NOT NULL UNIQUE, interval_days INTEGER NOT NULL DEFAULT 3, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (gecko_id) REFERENCES geckos(id) ON DELETE CASCADE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS auth_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT NOT NULL UNIQUE, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
init_geckolab_db()

@app.route('/geckolab/api/geckos', methods=['GET'])
def get_geckos():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''SELECT g.*, (SELECT weight FROM weight_records WHERE gecko_id=g.id ORDER BY record_date DESC LIMIT 1) as latest_weight FROM geckos g ORDER BY g.name''')
    geckos = [dict(row) for row in c.fetchall()]
    
    # Get feeding reminders and calculate next feeding dates
    for g in geckos:
        reminder = c.execute('SELECT interval_days FROM feeding_reminders WHERE gecko_id=?', (g['id'],)).fetchone()
        g['feeding_interval_days'] = reminder['interval_days'] if reminder else None
        # Calculate next feeding date based on last feeding
        if g['feeding_interval_days']:
            last_feeding = c.execute("SELECT log_date FROM daily_logs WHERE gecko_id=? AND log_type='feeding' ORDER BY log_date DESC LIMIT 1", (g['id'],)).fetchone()
            if last_feeding:
                from datetime import datetime, timedelta
                last_date = datetime.strptime(last_feeding['log_date'], '%Y-%m-%d').date()
                next_date = last_date + timedelta(days=g['feeding_interval_days'])
                g['next_feeding_date'] = next_date.isoformat()
            else:
                g['next_feeding_date'] = None
        else:
            g['next_feeding_date'] = None
    
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
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('INSERT INTO geckos (name, species, dob, adopted_date, color, avatar_path, personality, album_url) VALUES (?,?,?,?,?,?,?,?)', (name, species, dob, adopted_date, color, avatar_path, request.form.get('personality', '').strip(), request.form.get('album_url', '').strip()))
    gecko_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'gecko_id': gecko_id})

@app.route('/geckolab/api/geckos/<int:gecko_id>', methods=['GET'])
def get_gecko(gecko_id):
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    if avatar_path:
        c.execute('UPDATE geckos SET name=?, species=?, dob=?, adopted_date=?, color=?, avatar_path=?, personality=?, album_url=? WHERE id=?', (name, species, dob, adopted_date, color, avatar_path, request.form.get('personality', '').strip(), request.form.get('album_url', '').strip(), gecko_id))
    else:
        c.execute('UPDATE geckos SET name=?, species=?, dob=?, adopted_date=?, color=?, personality=?, album_url=? WHERE id=?', (name, species, dob, adopted_date, color, request.form.get('personality', '').strip(), request.form.get('album_url', '').strip(), gecko_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/geckolab/api/geckos/<int:gecko_id>/avatar', methods=['DELETE'])
@app.route('/geckolab/api/geckos/<int:gecko_id>', methods=['DELETE'])
def delete_gecko(gecko_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('DELETE FROM daily_logs WHERE gecko_id=?', (gecko_id,))
    c.execute('DELETE FROM weight_records WHERE gecko_id=?', (gecko_id,))
    c.execute('DELETE FROM geckos WHERE id=?', (gecko_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/geckos/<int:gecko_id>/weights', methods=['GET'])
def get_weight_history(gecko_id):
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('INSERT INTO weight_records (gecko_id, weight, record_date, notes) VALUES (?,?,?,?)', (gecko_id, weight, record_date, notes))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/geckos/<int:gecko_id>/weights/<int:weight_id>', methods=['PUT'])
def update_weight(gecko_id, weight_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    weight = float(request.form.get('weight', 0))
    record_date = request.form.get('record_date', datetime.now().strftime('%Y-%m-%d'))
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('UPDATE weight_records SET weight=?, record_date=? WHERE id=? AND gecko_id=?', (weight, record_date, weight_id, gecko_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/geckos/<int:gecko_id>/weights/<int:weight_id>', methods=['DELETE'])
def delete_weight(gecko_id, weight_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('DELETE FROM weight_records WHERE id=? AND gecko_id=?', (weight_id, gecko_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/geckos/<int:gecko_id>/logs', methods=['GET'])
def get_gecko_logs(gecko_id):
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
    conn = sqlite3.connect(DB_PATH, timeout=30)
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
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    period = request.form.get('period', '')
    c.execute('INSERT INTO daily_logs (gecko_id, log_date, log_type, quantity, notes, period) VALUES (?,?,?,?,?,?)', (gecko_id, log_date, log_type, quantity, notes, period))
    log_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'log_id': log_id})

@app.route('/geckolab/api/logs/<int:log_id>', methods=['PUT'])
def update_log(log_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    data = request.get_json()
    log_date = data.get('log_date', '').strip()
    log_type = data.get('log_type', '').strip()
    quantity = data.get('quantity', '')
    notes = data.get('notes', '')
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    period = data.get('period', '')
    c.execute('UPDATE daily_logs SET log_date=?, log_type=?, quantity=?, notes=?, period=? WHERE id=?', (log_date, log_type, quantity, notes, period, log_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/logs/<int:log_id>', methods=['DELETE'])
def delete_log(log_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('DELETE FROM daily_logs WHERE id=?', (log_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/change-password', methods=['POST'])
@rate_limit(max_requests=3, window_seconds=60)  # Security: max 3 change attempts/minute/IP
def geckolab_change_password():
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    old_pwd = request.form.get('old_password', '')
    new_pwd = request.form.get('new_password', '')
    success, _ = verify_password(old_pwd)
    if not success:
        return jsonify({'success': False, 'error': '舊密碼錯誤'})
    save_geckolab_password(new_pwd)
    # Invalidate all existing tokens - all users must re-login with new password
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('DELETE FROM auth_tokens')
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '密碼已更改，所有用戶需重新登入'})

@app.route('/geckolab/api/reset-data', methods=['POST'])
def geckolab_reset_data():
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('DELETE FROM daily_logs')
    c.execute('DELETE FROM weight_records')
    c.execute('DELETE FROM geckos')
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# Privacy Policy
@app.route('/privacy')
def privacy_policy():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Privacy Policy - Geckolab</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #333; }
        h1 { color: #1a1a2e; }
        h2 { color: #333; margin-top: 30px; }
    </style>
</head>
<body>
    <h1>Privacy Policy</h1>
    <p><strong>Last updated: April 28, 2026</strong></p>

    <p>This Privacy Policy describes how Geckolab ("we", "our", or "the app") handles your information when you use our mobile application.</p>

    <h2>Information We Collect</h2>
    <p><strong>Local Data Only:</strong> All your gecko data (names, species, feeding records, weight history, photos) is stored <strong>locally on your device</strong>. We do not collect, upload, or store any of your personal data on our servers unless you explicitly enable the <strong>GeckoSync</strong> feature.</p>

    <p><strong>GeckoSync Data:</strong> If you choose to use the GeckoSync feature to share gecko data with a partner, the shared data (gecko profiles, feeding logs, weight records) is transmitted to and stored on our sync server. This data is only accessible using the unique sync code you create and share. We do not access, read, or use this data for any purpose other than facilitating the sync between paired devices.</p>

    <h2>Data Storage and Security</h2>
    <p>Local data is stored in a SQLite database on your device. Sync data is stored on our secure server and is associated only with an anonymous sync code. No personally identifiable information is collected or stored.</p>

    <h2>Third-Party Services</h2>
    <p>Geckolab does not use any third-party analytics, advertising, or tracking services. No data is shared with third parties.</p>

    <h2>Children\'s Privacy</h2>
    <p>Geckolab does not knowingly collect personal information from children under 13.</p>

    <h2>Changes to This Policy</h2>
    <p>We may update this Privacy Policy from time to time. Changes will be posted on this page.</p>

    <h2>Contact</h2>
    <p>If you have questions about this Privacy Policy, please contact us at: assistantofkc@gmail.com</p>
</body>
</html>'''

# Data Deletion
@app.route('/privacy/delete')
def data_deletion():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Deletion - Geckolab</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #333; }
        h1 { color: #1a1a2e; }
        h2 { color: #333; margin-top: 30px; }
        code { background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }
        .step { margin: 15px 0; padding: 10px 15px; background: #f8f8f8; border-left: 3px solid #26A69A; }
    </style>
</head>
<body>
    <h1>Data Deletion - Geckolab</h1>
    <p>This page explains how to request deletion of your data in the Geckolab app.</p>

    <h2>Local Data</h2>
    <p>All gecko data is stored locally on your device. To delete local data:</p>
    <div class="step"><strong>Option A:</strong> Go to App Settings > Clear Data / Clear Storage on your Android device, or uninstall the app.</div>
    <div class="step"><strong>Option B:</strong> Open Geckolab > Settings > Reset All Data.</div>

    <h2>Synced Data (GeckoSync)</h2>
    <p>If you have used the GeckoSync feature, your gecko data is stored on our sync server under an anonymous sync code. To delete synced data:</p>
    <div class="step"><strong>Method 1:</strong> Open the gecko profile > Sync > Reset Sync. This immediately removes all synced data from the server.</div>
    <div class="step"><strong>Method 2:</strong> Email us at <code>assistantofkc@gmail.com</code> with your sync code, and we will delete your data within 7 days.</div>

    <h2>What Gets Deleted</h2>
    <ul>
        <li>Gecko profiles (name, species, photos)</li>
        <li>Feeding logs and records</li>
        <li>Weight history</li>
        <li>All associated sync data</li>
    </ul>

    <h2>Retention</h2>
    <p>Synced data is retained only while the sync code is active. Data is immediately deleted when the user performs a Reset Sync in the app. No data is retained after deletion.</p>
</body>
</html>'''

# Feeding Reminder endpoints
@app.route('/geckolab/api/feeding-reminders', methods=['GET'])
def get_feeding_reminders():
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    reminders = c.execute('SELECT * FROM feeding_reminders').fetchall()
    conn.close()
    return jsonify({'success': True, 'reminders': [dict(r) for r in reminders]})

@app.route('/geckolab/api/feeding-reminders/<int:gecko_id>', methods=['POST'])
def set_feeding_reminder(gecko_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    data = request.get_json()
    interval_days = data.get('interval_days', 3)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO feeding_reminders (gecko_id, interval_days) VALUES (?, ?)', (gecko_id, interval_days))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/feeding-reminders/<int:gecko_id>', methods=['DELETE'])
def delete_feeding_reminder(gecko_id):
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('DELETE FROM feeding_reminders WHERE gecko_id=?', (gecko_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/geckolab/api/export', methods=['GET'])
def geckolab_export():
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Export geckos
    geckos = c.execute('SELECT * FROM geckos').fetchall()
    weights = c.execute('SELECT * FROM weight_records').fetchall()
    logs = c.execute('SELECT * FROM daily_logs').fetchall()
    conn.close()
    
    csv_lines = []
    csv_lines.append('# Geckos')
    csv_lines.append('id,name,species,dob,adopted_date,color,avatar_path,personality,album_url,created_at')
    for g in geckos:
        csv_lines.append(f'{g["id"]},{g["name"]},{g["species"]},{g["dob"]},{g["adopted_date"]},{g["color"]},{g["avatar_path"]},{g["personality"]},{g["album_url"]},{g["created_at"]}')
    
    csv_lines.append('')
    csv_lines.append('# Weight Records')
    csv_lines.append('id,gecko_id,weight,record_date,notes,created_at')
    for w in weights:
        csv_lines.append(f'{w["id"]},{w["gecko_id"]},{w["weight"]},{w["record_date"]},{w["notes"]},{w["created_at"]}')
    
    csv_lines.append('')
    csv_lines.append('# Daily Logs')
    csv_lines.append('id,gecko_id,log_date,log_type,quantity,notes,period,created_at')
    for l in logs:
        csv_lines.append(f'{l["id"]},{l["gecko_id"]},{l["log_date"]},{l["log_type"]},{l["quantity"]},{l["notes"]},{l["period"]},{l["created_at"]}')
    
    return jsonify({'success': True, 'csv': '\n'.join(csv_lines)})

@app.route('/geckolab/api/import', methods=['POST'])
def geckolab_import():
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    data = request.get_json()
    csv_content = data.get('csv', '')
    if not csv_content:
        return jsonify({'success': False, 'error': 'No CSV content'})
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()
        
        lines = csv_content.strip().split('\n')
        section = None
        imported_geckos = 0
        imported_weights = 0
        imported_logs = 0
        errors = []
        
        header_skipped = {'Geckos': False, 'Weight Records': False, 'Daily Logs': False}
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                if line.startswith('#'):
                    section = line.replace('# ', '').replace('#', '').strip()
                    header_skipped[section] = False
                continue
            parts = line.split(',')
            # Skip header lines
            if section in header_skipped and not header_skipped[section]:
                header_skipped[section] = True
                continue
            try:
                if section == 'Geckos' and len(parts) >= 10:
                    if not parts[1]:  # name is REQUIRED
                        errors.append('Gecko name required')
                        continue
                    gid = int(parts[0]) if parts[0] and parts[0].strip() else None
                    c.execute('INSERT INTO geckos (id, name, species, dob, adopted_date, color, avatar_path, personality, album_url, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)', (gid, parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7] if len(parts) > 7 else '', parts[8] if len(parts) > 8 else '', parts[9] if len(parts) > 9 else ''))
                    imported_geckos += 1
                elif section == 'Weight Records' and len(parts) >= 6:
                    if not parts[1] or not parts[2] or not parts[3]:  # gecko_id, weight, record_date required
                        errors.append('Weight needs gecko_id, weight, record_date')
                        continue
                    gid = int(parts[1])
                    wt = float(parts[2])
                    c.execute('INSERT INTO weight_records (id, gecko_id, weight, record_date, notes, created_at) VALUES (?,?,?,?,?,?)', (int(parts[0]) if parts[0] and parts[0].strip() else None, gid, wt, parts[3], parts[4] if len(parts) > 4 else '', parts[5] if len(parts) > 5 else ''))
                    imported_weights += 1
                elif section == 'Daily Logs' and len(parts) >= 7:
                    if not parts[1] or not parts[2] or not parts[3]:  # gecko_id, log_date, log_type required
                        errors.append('Log needs gecko_id, date, type')
                        continue
                    gid = int(parts[1])
                    c.execute('INSERT INTO daily_logs (id, gecko_id, log_date, log_type, quantity, notes, period, created_at) VALUES (?,?,?,?,?,?,?,?)', (int(parts[0]) if parts[0] and parts[0].strip() else None, gid, parts[2], parts[3], parts[4] if len(parts) > 4 else '', parts[5] if len(parts) > 5 else '', parts[6] if len(parts) > 6 else '', parts[7] if len(parts) > 7 else ''))
                    imported_logs += 1
            except Exception as e:
                errors.append(f'Line error: {str(e)[:50]}')
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'已還原：{imported_geckos}守宮 {imported_weights}體重 {imported_logs}紀錄', 'errors': errors[:5] if errors else []})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

# Password file for Geckolab
GECKOLAB_PASS_FILE = os.path.join(os.path.dirname(__file__), 'geckolab', 'password.json')

def _bcrypt_hash(plaintext):
    """Hash a plaintext password with bcrypt."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    return bcrypt.hashpw(plaintext, bcrypt.gensalt()).decode('utf-8')

def _bcrypt_verify(plaintext, stored_hash):
    """Verify a plaintext password against a bcrypt hash."""
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode('utf-8')
    try:
        return bcrypt.checkpw(plaintext, stored_hash)
    except ValueError:
        # Invalid hash format (e.g., still legacy plaintext)
        return False

def get_geckolab_password():
    """Returns dict with 'password' (bcrypt hash) and optionally 'password_legacy' (plaintext for migration)."""
    try:
        if os.path.exists(GECKOLAB_PASS_FILE):
            with open(GECKOLAB_PASS_FILE, 'r') as f:
                data = json.load(f)
                return {
                    'password': data.get('password', os.environ.get('GECKOLAB_PASSWORD', 'geckolab123')),
                    'password_legacy': data.get('password_legacy')
                }
    except: pass
    return {
        'password': os.environ.get('GECKOLAB_PASSWORD', 'geckolab123'),
        'password_legacy': None
    }

def verify_password(plaintext):
    """
    Verify password with fallback for migration.
    Strategy:
    1. Try bcrypt first (normal path after migration)
    2. Fallback: check explicit password_legacy OR auto-detect plaintext (not starting with $2)
    3. On legacy match -> auto-upgrade to bcrypt (best-effort, non-blocking)
       If upgrade fails, legacy still works on next login.
    Returns: (success: bool, upgraded: bool)
    """
    stored = get_geckolab_password()

    # Path 1: bcrypt verification (normal after migration)
    if _bcrypt_verify(plaintext, stored['password']):
        return True, False

    # Path 2: legacy fallback — explicit password_legacy OR auto-detect plaintext
    is_bcrypt = stored['password'].startswith('$2')
    legacy_candidate = None

    if stored.get('password_legacy'):
        legacy_candidate = stored['password_legacy']
    elif not is_bcrypt:
        # Stored password is plaintext (not bcrypt hash) → auto-detect legacy
        legacy_candidate = stored['password']

    if legacy_candidate and plaintext == legacy_candidate:
        # Auto-upgrade: hash with bcrypt, write new file
        # Best-effort: if this fails, legacy comparison still works on next login
        try:
            bcrypt_hash = _bcrypt_hash(plaintext)
            new_data = {'password': bcrypt_hash}
            with open(GECKOLAB_PASS_FILE, 'w') as f:
                json.dump(new_data, f)
        except Exception as e:
            print(f"[Security] bcrypt auto-upgrade failed (legacy fallback intact): {e}")
        return True, True

    return False, False

def save_geckolab_password(new_password):
    """Save new password as bcrypt hash (clears any legacy)."""
    bcrypt_hash = _bcrypt_hash(new_password)
    with open(GECKOLAB_PASS_FILE, 'w') as f:
        json.dump({'password': bcrypt_hash}, f)

# === Geckolab Sync (separate module) ===
import sys, os as _os
_sync_dir = _os.path.dirname(_os.path.abspath(__file__))
if _sync_dir not in sys.path:
    sys.path.insert(0, _sync_dir)
try:
    from geckolab_sync import init_sync
    init_sync(app)
except Exception:
    pass  # sync unavailable, webapp still works
