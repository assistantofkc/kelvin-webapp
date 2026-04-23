"""
Geckolab - Gecko Care Management App
Flask Backend with SQLite Database
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import os
import re
from datetime import datetime, date
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'geckolab-secret-key-change-in-production')

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
GECKOLAB_DIR = os.path.join(BASE_DIR, 'geckolab')
UPLOAD_FOLDER = os.path.join(GECKOLAB_DIR, 'static', 'uploads')
DB_PATH = os.path.join(GECKOLAB_DIR, 'geckolab.db')

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Allowed extensions for image uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database initialization
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Geckos table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS geckos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            species TEXT,
            dob TEXT,
            adopted_date TEXT,
            color TEXT,
            avatar_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Weight records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weight_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gecko_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            record_date TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gecko_id) REFERENCES geckos(id) ON DELETE CASCADE
        )
    ''')
    
    # Daily logs table (feeding, poo/pee)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gecko_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            log_type TEXT NOT NULL,  -- 'feeding', 'poo', 'pee'
            quantity TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gecko_id) REFERENCES geckos(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database on module load
init_db()


# ==================== ROUTES ====================

@app.route('/geckolab')
def index():
    """Landing page - shows all geckos for login"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, species, color, avatar_path FROM geckos ORDER BY name')
    geckos = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('geckolab.html', geckos=geckos, page='geckolab')


@app.route('/geckolab/login', methods=['POST'])
def login():
    """Login handler - verify password from .env"""
    password = request.form.get('password', '')
    env_password = os.environ.get('GECKOLAB_PASSWORD', 'geckolab123')
    
    if password == env_password:
        session['geckolab_logged_in'] = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Invalid password'})


@app.route('/geckolab/logout')
def logout():
    """Logout handler"""
    session.pop('geckolab_logged_in', None)
    return redirect(url_for('index'))


@app.route('/geckolab/change-password', methods=['POST'])
def change_password():
    """Change .env password - requires logged in"""
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    
    env_password = os.environ.get('GECKOLAB_PASSWORD', 'geckolab123')
    
    if current_password != env_password:
        return jsonify({'success': False, 'error': 'Current password incorrect'})
    
    if len(new_password) < 4:
        return jsonify({'success': False, 'error': 'Password too short'})
    
    # Update .env file
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    
    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()
        
        with open(env_path, 'w') as f:
            for line in lines:
                if line.startswith('GECKOLAB_PASSWORD='):
                    f.write(f'GECKOLAB_PASSWORD={new_password}\n')
                else:
                    f.write(line)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ==================== GECKO CRUD ====================

@app.route('/geckolab/api/geckos', methods=['GET'])
def get_geckos():
    """Get all geckos"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT g.*, 
               (SELECT weight FROM weight_records WHERE gecko_id = g.id ORDER BY record_date DESC LIMIT 1) as latest_weight
        FROM geckos g ORDER BY g.name
    ''')
    geckos = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({'success': True, 'geckos': geckos})


@app.route('/geckolab/api/geckos', methods=['POST'])
def add_gecko():
    """Add new gecko"""
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    name = request.form.get('name', '').strip()
    species = request.form.get('species', '').strip()
    dob = request.form.get('dob', '').strip()
    adopted_date = request.form.get('adopted_date', '').strip()
    color = request.form.get('color', '#FF6B6B').strip()
    
    # Handle file upload
    avatar_path = None
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"gecko_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            avatar_path = f'/geckolab/static/uploads/{filename}'
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO geckos (name, species, dob, adopted_date, color, avatar_path)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, species, dob, adopted_date, color, avatar_path))
    
    gecko_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'gecko_id': gecko_id})


@app.route('/geckolab/api/geckos/<int:gecko_id>', methods=['GET'])
def get_gecko(gecko_id):
    """Get single gecko details with age calculation"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM geckos WHERE id = ?', (gecko_id,))
    gecko = dict(cursor.fetchone())
    
    if gecko['dob']:
        dob_date = datetime.strptime(gecko['dob'], '%Y-%m-%d').date()
        today = date.today()
        age_days = (today - dob_date).days
        gecko['age_years'] = age_days // 365
        gecko['age_months'] = (age_days % 365) // 30
        gecko['age_days'] = age_days % 30
    
    # Get latest weight
    cursor.execute('''
        SELECT weight, record_date FROM weight_records 
        WHERE gecko_id = ? ORDER BY record_date DESC LIMIT 1
    ''', (gecko_id,))
    weight_row = cursor.fetchone()
    gecko['latest_weight'] = weight_row['weight'] if weight_row else None
    
    conn.close()
    
    return jsonify({'success': True, 'gecko': gecko})


@app.route('/geckolab/api/geckos/<int:gecko_id>', methods=['PUT'])
def update_gecko(gecko_id):
    """Update gecko details"""
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    name = request.form.get('name', '').strip()
    species = request.form.get('species', '').strip()
    dob = request.form.get('dob', '').strip()
    adopted_date = request.form.get('adopted_date', '').strip()
    color = request.form.get('color', '#FF6B6B').strip()
    
    # Handle file upload if new avatar provided
    avatar_path = None
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"gecko_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            avatar_path = f'/geckolab/static/uploads/{filename}'
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if avatar_path:
        cursor.execute('''
            UPDATE geckos SET name=?, species=?, dob=?, adopted_date=?, color=?, avatar_path=?
            WHERE id=?
        ''', (name, species, dob, adopted_date, color, avatar_path, gecko_id))
    else:
        cursor.execute('''
            UPDATE geckos SET name=?, species=?, dob=?, adopted_date=?, color=?
            WHERE id=?
        ''', (name, species, dob, adopted_date, color, gecko_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})


# ==================== WEIGHT MANAGEMENT ====================

@app.route('/geckolab/api/geckos/<int:gecko_id>/weights', methods=['GET'])
def get_weight_history(gecko_id):
    """Get weight history for a gecko"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM weight_records WHERE gecko_id = ? ORDER BY record_date DESC
    ''', (gecko_id,))
    weights = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({'success': True, 'weights': weights})


@app.route('/geckolab/api/geckos/<int:gecko_id>/weights', methods=['POST'])
def add_weight(gecko_id):
    """Add weight record"""
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    weight = float(request.form.get('weight', 0))
    record_date = request.form.get('record_date', datetime.now().strftime('%Y-%m-%d'))
    notes = request.form.get('notes', '').strip()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO weight_records (gecko_id, weight, record_date, notes)
        VALUES (?, ?, ?, ?)
    ''', (gecko_id, weight, record_date, notes))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})


# ==================== DAILY LOGS ====================

@app.route('/geckolab/api/geckos/<int:gecko_id>/logs', methods=['GET'])
def get_daily_logs(gecko_id):
    """Get daily logs for a gecko"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    month = request.args.get('month')
    year = request.args.get('year')
    
    query = 'SELECT * FROM daily_logs WHERE gecko_id = ?'
    params = [gecko_id]
    
    if month and year:
        query += ' AND strftime("%m", log_date) = ? AND strftime("%Y", log_date) = ?'
        params.extend([month.zfill(2), year])
    
    query += ' ORDER BY log_date DESC'
    
    cursor.execute(query, params)
    logs = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({'success': True, 'logs': logs})


@app.route('/geckolab/api/logs', methods=['GET'])
def get_logs_by_date():
    """Get all logs for a specific date (for calendar display)"""
    log_date = request.args.get('date')
    
    if not log_date:
        return jsonify({'success': False, 'error': 'Date required'})
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT l.*, g.name, g.color FROM daily_logs l
        JOIN geckos g ON l.gecko_id = g.id
        WHERE l.log_date = ?
    ''', (log_date,))
    
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'logs': logs})


@app.route('/geckolab/api/geckos/<int:gecko_id>/logs', methods=['POST'])
def add_daily_log(gecko_id):
    """Add daily log entry"""
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    log_type = request.form.get('log_type', '')  # 'feeding', 'poo', 'pee'
    log_date = request.form.get('log_date', datetime.now().strftime('%Y-%m-%d'))
    quantity = request.form.get('quantity', '').strip()
    notes = request.form.get('notes', '').strip()
    
    if log_type not in ('feeding', 'poo', 'pee'):
        return jsonify({'success': False, 'error': 'Invalid log type'})
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO daily_logs (gecko_id, log_date, log_type, quantity, notes)
        VALUES (?, ?, ?, ?, ?)
    ''', (gecko_id, log_date, log_type, quantity, notes))
    
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'log_id': log_id})


@app.route('/geckolab/api/logs/<int:log_id>', methods=['DELETE'])
def delete_log(log_id):
    """Delete a log entry"""
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM daily_logs WHERE id = ?', (log_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})
