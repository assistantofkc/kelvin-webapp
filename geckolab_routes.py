"""
Geckolab Routes - Gecko Care Management App
These routes are integrated into the main app.py
"""

# ==================== GECKOLAB CONSTANTS ====================

# Paths for Geckolab
GECKOLAB_DIR = os.path.join(os.path.dirname(__file__), 'geckolab')
UPLOAD_FOLDER = os.path.join(GECKOLAB_DIR, 'static', 'uploads')
DB_PATH = os.path.join(GECKOLAB_DIR, 'geckolab.db')

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== DATABASE INITIALIZATION ====================

def init_geckolab_db():
    """Initialize Geckolab database"""
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
            color TEXT DEFAULT '#FF6B6B',
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
    
    # Daily logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gecko_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            log_type TEXT NOT NULL,
            quantity TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gecko_id) REFERENCES geckos(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()


# Initialize on import
init_geckolab_db()


# ==================== GECKOLAB ROUTES ====================

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
    """Get single gecko details"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM geckos WHERE id = ?', (gecko_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'success': False, 'error': 'Gecko not found'}), 404
    
    gecko = dict(row)
    
    # Calculate age
    if gecko.get('dob'):
        try:
            dob_date = datetime.strptime(gecko['dob'], '%Y-%m-%d').date()
            today = date.today()
            age_days = (today - dob_date).days
            gecko['age_years'] = age_days // 365
            gecko['age_months'] = (age_days % 365) // 30
            gecko['age_days'] = age_days % 30
        except:
            pass
    
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


@app.route('/geckolab/api/geckos/<int:gecko_id>', methods=['DELETE'])
def delete_gecko(gecko_id):
    """Delete a gecko"""
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM geckos WHERE id = ?', (gecko_id,))
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
def get_gecko_logs(gecko_id):
    """Get daily logs for a gecko"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM daily_logs WHERE gecko_id = ? ORDER BY log_date DESC
    ''', (gecko_id,))
    logs = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return jsonify({'success': True, 'logs': logs})


@app.route('/geckolab/api/logs', methods=['GET'])
def get_logs_by_date():
    """Get all logs for a specific date (for calendar)"""
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


@app.route('/geckolab/api/logs/month', methods=['GET'])
def get_logs_by_month():
    """Get all logs for a specific month (for calendar display)"""
    month = request.args.get('month')
    year = request.args.get('year')
    
    if not month or not year:
        return jsonify({'success': False, 'error': 'Month and year required'})
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT l.*, g.name, g.color FROM daily_logs l
        JOIN geckos g ON l.gecko_id = g.id
        WHERE strftime('%Y', l.log_date) = ? AND strftime('%m', l.log_date) = ?
    ''', (year, month.zfill(2)))
    
    logs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'logs': logs})


@app.route('/geckolab/api/geckos/<int:gecko_id>/logs', methods=['POST'])
def add_daily_log(gecko_id):
    """Add daily log entry"""
    if not session.get('geckolab_logged_in'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    log_type = request.form.get('log_type', '')
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
