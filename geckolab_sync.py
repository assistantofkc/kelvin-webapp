"""
Geckolab Sync API Module
Imported by kelvin-webapp - self-contained, zero impact on existing routes
Storage: SQLite (transaction-safe, no race condition on concurrent pushes)

⚠️  PRODUCTION DATABASE - SCHEMA LOCKED
    The sync table structure must NEVER be modified without:
    1. Creating a staging environment first
    2. Testing all edge cases
    3. Getting explicit approval from Kelvin
    4. Having a rollback plan
    Live users depend on this DB. DO NOT ADD/ALTER/DROP columns.
"""
import json, os, secrets, sqlite3
from datetime import datetime
from flask import request, jsonify, make_response

SYNC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_data')
os.makedirs(SYNC_DIR, exist_ok=True)
DB_PATH = os.path.join(SYNC_DIR, 'geckolab_sync.db')

# ⚠️ Production schema - DO NOT MODIFY existing tables
# This is the canonical schema definition. _init_db() validates against this.
# Medical tables added 2026-05-02 — new tables only, no existing table changes
_EXPECTED_SCHEMA = {
    'sync_rooms': {
        'code':         ('TEXT', True),    # PRIMARY KEY
        'created_at':   ('TEXT', True),
        'updated_at':   ('TEXT', True),
        'app_version':  ('TEXT', False, "'unknown'"),
        'gecko':        ('TEXT', False),
        'logs':         ('TEXT', False, "'[]'"),
        'weights':      ('TEXT', False, "'[]'"),
        'history':      ('TEXT', False, "'[]'"),
    },
    # === NEW: Medical Handbook Tables (2026-05-02) ===
    'medical_illnesses': {
        'id':           ('INTEGER', True),  # PRIMARY KEY AUTOINCREMENT
        'code':         ('TEXT', False),     # sync room code (global scope, avoids cross-contamination)
        'gecko_id':     ('INTEGER', True),
        'name':         ('TEXT', True),
        'start_date':   ('TEXT', True),
        'end_date':     ('TEXT', False),
        'symptoms':     ('TEXT', False),
        'severity':     ('TEXT', False, "'medium'"),
        'status':       ('TEXT', False, "'active'"),
        'photo_paths':  ('TEXT', False),
        'notes':        ('TEXT', False),
        'created_at':   ('TEXT', False),
        'updated_at':   ('TEXT', False),
    },
    'medical_medicines': {
        'id':           ('INTEGER', True),
        'code':         ('TEXT', False),
        'gecko_id':     ('INTEGER', True),
        'illness_id':   ('INTEGER', False),
        'name':         ('TEXT', True),
        'dosage':       ('TEXT', False),
        'frequency':    ('TEXT', False),
        'time_of_day':  ('TEXT', False),
        'start_date':   ('TEXT', True),
        'end_date':     ('TEXT', False),
        'interval_days':('INTEGER', False, '1'),
        'reminder_enabled': ('INTEGER', False, '0'),
        'notes':        ('TEXT', False),
        'created_at':   ('TEXT', False),
        'updated_at':   ('TEXT', False),
    },
    'medical_vet_visits': {
        'id':           ('INTEGER', True),
        'code':         ('TEXT', False),
        'gecko_id':     ('INTEGER', True),
        'illness_id':   ('INTEGER', False),
        'clinic_name':  ('TEXT', False),
        'vet_name':     ('TEXT', False),
        'visit_date':   ('TEXT', True),
        'diagnosis':    ('TEXT', False),
        'cost':         ('REAL', False),
        'next_visit_date': ('TEXT', False),
        'reminder_enabled': ('INTEGER', False, '0'),
        'photo_paths':  ('TEXT', False),
        'notes':        ('TEXT', False),
        'created_at':   ('TEXT', False),
        'updated_at':   ('TEXT', False),
    },
    'medicine_log': {
        'id':           ('INTEGER', True),
        'code':         ('TEXT', False),
        'medicine_id':  ('INTEGER', True),
        'gecko_id':     ('INTEGER', True),
        'taken_date':   ('TEXT', True),
        'taken_period': ('TEXT', False),
        'notes':        ('TEXT', False),
        'created_at':   ('TEXT', False),
    },
}

def _cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    return resp

def _json(data, status=200):
    return _cors(make_response(jsonify(data), status))

def _get_db():
    """Get a new SQLite connection (WAL mode for concurrent reads)."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def _validate_schema(conn):
    """Verify the production DB schema matches the expected schema.
    Prints warnings if mismatches are found. Never alters the schema."""
    try:
        for table_name, expected_cols in _EXPECTED_SCHEMA.items():
            rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            actual_cols = {r['name']: {'type': r['type'], 'notnull': bool(r['notnull']),
                                        'dflt_value': r['dflt_value']} for r in rows}
            for col_name, (col_type, required, *rest) in expected_cols.items():
                default = rest[0] if rest else None
                if col_name not in actual_cols:
                    print(f"⚠️  SCHEMA MISMATCH: Column '{col_name}' missing from '{table_name}'!")
                elif actual_cols[col_name]['type'].upper() != col_type.upper():
                    print(f"⚠️  SCHEMA MISMATCH: Column '{col_name}' type is "
                          f"'{actual_cols[col_name]['type']}' instead of '{col_type}'")
    except Exception as e:
        print(f"⚠️  Schema validation skipped (table may not exist yet): {e}")

def _init_db():
    """Initialize the database schema.
    ⚠️  USES CREATE IF NOT EXISTS — will never alter existing tables.
        Any schema change must go through staging first."""
    conn = _get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sync_rooms (
            code TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            app_version TEXT DEFAULT 'unknown',
            gecko TEXT,
            logs TEXT DEFAULT '[]',
            weights TEXT DEFAULT '[]',
            history TEXT DEFAULT '[]'
        )
    ''')
    # === NEW: Medical Handbook Tables (2026-05-02) ===
    # These are additive — zero impact on existing sync_rooms table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS medical_illnesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            gecko_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            symptoms TEXT,
            severity TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'active',
            photo_paths TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS medical_medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            gecko_id INTEGER NOT NULL,
            illness_id INTEGER,
            name TEXT NOT NULL,
            dosage TEXT,
            frequency TEXT,
            time_of_day TEXT,
            start_date TEXT NOT NULL,
            end_date TEXT,
            interval_days INTEGER DEFAULT 1,
            reminder_enabled INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS medical_vet_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            gecko_id INTEGER NOT NULL,
            illness_id INTEGER,
            clinic_name TEXT,
            vet_name TEXT,
            visit_date TEXT NOT NULL,
            diagnosis TEXT,
            cost REAL,
            next_visit_date TEXT,
            reminder_enabled INTEGER DEFAULT 0,
            photo_paths TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS medicine_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            medicine_id INTEGER NOT NULL,
            gecko_id INTEGER NOT NULL,
            taken_date TEXT NOT NULL,
            taken_period TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.commit()
    # Migrations: add missing columns for existing databases
    _migrate_schema(conn)
    # Validate existing schema on every startup
    _validate_schema(conn)
    conn.close()

def _migrate_schema(conn):
    """Add missing columns to existing tables (idempotent)."""
    try:
        for table in ['medical_illnesses', 'medical_medicines', 'medical_vet_visits', 'medicine_log']:
            cols = [r['name'] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if 'interval_days' not in cols and table == 'medical_medicines':
                conn.execute("ALTER TABLE medical_medicines ADD COLUMN interval_days INTEGER DEFAULT 1")
            if 'code' not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN code TEXT")
        # Clean up orphaned records from before code-scoping was added
        for table in ['medical_illnesses', 'medical_medicines', 'medical_vet_visits', 'medicine_log']:
            deleted = conn.execute(f"DELETE FROM {table} WHERE code IS NULL").rowcount
            if deleted:
                print(f'[sync] Cleaned {deleted} orphaned records from {table}')
        conn.commit()
    except Exception as e:
        print(f'[sync] Schema migration warning: {e}')

def _load(code):
    """Load a sync room from SQLite. Returns dict or None."""
    conn = _get_db()
    row = conn.execute("SELECT * FROM sync_rooms WHERE code = ?", (code,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        'code': row['code'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'app_version': row['app_version'],
        'gecko': json.loads(row['gecko']) if row['gecko'] else None,
        'logs': json.loads(row['logs']) if row['logs'] else [],
        'weights': json.loads(row['weights']) if row['weights'] else [],
        'history': json.loads(row['history']) if row['history'] else [],
    }

def _save(code, data):
    """Save a sync room to SQLite (UPSERT)."""
    conn = _get_db()
    data['updated_at'] = datetime.now().isoformat()
    conn.execute('''
        INSERT INTO sync_rooms (code, created_at, updated_at, app_version, gecko, logs, weights, history)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            updated_at = excluded.updated_at,
            gecko = excluded.gecko,
            logs = excluded.logs,
            weights = excluded.weights,
            history = excluded.history
    ''', (
        code,
        data.get('created_at', data['updated_at']),
        data['updated_at'],
        data.get('app_version', 'unknown'),
        json.dumps(data.get('gecko'), ensure_ascii=False) if data.get('gecko') else None,
        json.dumps(data.get('logs', []), ensure_ascii=False),
        json.dumps(data.get('weights', []), ensure_ascii=False),
        json.dumps(data.get('history', []), ensure_ascii=False),
    ))
    conn.commit()
    conn.close()

def _transactional_push(code, updater_fn):
    """Execute a push within a SQLite transaction to prevent race conditions."""
    conn = _get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM sync_rooms WHERE code = ?", (code,)).fetchone()
        if not row:
            conn.rollback()
            conn.close()
            return None

        room = {
            'code': row['code'],
            'created_at': row['created_at'],
            'updated_at': row['updated_at'],
            'app_version': row['app_version'],
            'gecko': json.loads(row['gecko']) if row['gecko'] else None,
            'logs': json.loads(row['logs']) if row['logs'] else [],
            'weights': json.loads(row['weights']) if row['weights'] else [],
            'history': json.loads(row['history']) if row['history'] else [],
        }

        # Apply changes within the transaction
        result = updater_fn(room)

        now = datetime.now().isoformat()
        room['updated_at'] = now

        conn.execute('''
            UPDATE sync_rooms SET
                updated_at = ?, gecko = ?, logs = ?, weights = ?, history = ?
            WHERE code = ?
        ''', (
            now,
            json.dumps(room.get('gecko'), ensure_ascii=False) if room.get('gecko') else None,
            json.dumps(room.get('logs', []), ensure_ascii=False),
            json.dumps(room.get('weights', []), ensure_ascii=False),
            json.dumps(room.get('history', []), ensure_ascii=False),
            code,
        ))
        conn.commit()
        conn.close()
        return result
    except Exception:
        conn.rollback()
        conn.close()
        raise

def _dump_db(conn):
    """Diagnostic: dump all sync rooms and medical records."""
    rooms = []
    for row in conn.execute("SELECT code, gecko, logs, weights FROM sync_rooms").fetchall():
        g = json.loads(row['gecko']) if row['gecko'] else None
        rooms.append({
            'code': row['code'],
            'gecko_id': g.get('id') if g else None,
            'gecko_name': g.get('name') if g else None,
            'logs': len(json.loads(row['logs']) if row['logs'] else []),
            'weights': len(json.loads(row['weights']) if row['weights'] else []),
        })
    medical = {'illnesses': [], 'medicines': [], 'vet_visits': []}
    for r in conn.execute("SELECT * FROM medical_illnesses").fetchall():
        medical['illnesses'].append({'id': r['id'], 'gecko_id': r['gecko_id'], 'name': r['name'], 'status': r['status']})
    for r in conn.execute("SELECT * FROM medical_medicines").fetchall():
        medical['medicines'].append({'id': r['id'], 'gecko_id': r['gecko_id'], 'name': r['name']})
    for r in conn.execute("SELECT * FROM medical_vet_visits").fetchall():
        medical['vet_visits'].append({'id': r['id'], 'gecko_id': r['gecko_id'], 'clinic_name': r['clinic_name'], 'vet_name': r['vet_name']})
    return {'rooms': rooms, 'medical': medical}

def init_sync(app):
    _init_db()

    @app.route('/sync/debug', methods=['GET'])
    def sync_debug():
        conn = _get_db()
        data = _dump_db(conn)
        conn.close()
        return _json(data)

    @app.route('/sync/create', methods=['POST', 'OPTIONS'])
    def sync_create():
        if request.method == 'OPTIONS': return _json({})
        code = secrets.token_hex(3).upper()
        now = datetime.now().isoformat()
        data = {
            'code': code, 'created_at': now, 'updated_at': now,
            'app_version': request.json.get('app_version', 'unknown'),
            'gecko': None, 'logs': [], 'weights': [], 'history': []
        }
        _save(code, data)
        # Record creation in history
        conn = _get_db()
        row = conn.execute("SELECT history FROM sync_rooms WHERE code = ?", (code,)).fetchone()
        history = json.loads(row['history']) if row and row['history'] else []
        history.append({'user': request.json.get('user', 'A'),
            'action': 'created', 'time': datetime.now().isoformat()})
        conn.execute("UPDATE sync_rooms SET history = ? WHERE code = ?",
            (json.dumps(history, ensure_ascii=False), code))
        conn.commit()
        conn.close()
        return _json({'sync_code': code})

    @app.route('/sync/push', methods=['POST', 'OPTIONS'])
    def sync_push():
        if request.method == 'OPTIONS': return _json({})
        body = request.json
        code = body.get('code')
        user = body.get('user', '?')

        def do_push(room):
            g = body.get('gecko')
            if g and (not room['gecko'] or g.get('updated_at', '') > room['gecko'].get('updated_at', '')):
                room['gecko'] = g

            # Apply deletions first
            deleted_log_ids = set(body.get('deleted_log_ids', []))
            deleted_weight_ids = set(body.get('deleted_weight_ids', []))
            if deleted_log_ids:
                room['logs'] = [l for l in room['logs'] if l['id'] not in deleted_log_ids]
                room['history'].append({'user': user,
                    'action': f'deleted {len(deleted_log_ids)} logs',
                    'time': datetime.now().isoformat()})
            if deleted_weight_ids:
                room['weights'] = [w for w in room['weights'] if w['id'] not in deleted_weight_ids]
                room['history'].append({'user': user,
                    'action': f'deleted {len(deleted_weight_ids)} weights',
                    'time': datetime.now().isoformat()})

            # Merge logs by ID
            logs = body.get('logs', [])
            existing = {l['id']: i for i, l in enumerate(room['logs'])}
            for log in logs:
                if log['id'] in existing:
                    idx = existing[log['id']]
                    if log.get('updated_at', '') > room['logs'][idx].get('updated_at', ''):
                        room['logs'][idx] = log
                else:
                    room['logs'].append(log)

            # Merge weights by ID
            weights = body.get('weights', [])
            existing_w = {w['id']: i for i, w in enumerate(room['weights'])}
            for w in weights:
                if w['id'] in existing_w:
                    idx = existing_w[w['id']]
                    if w.get('updated_at', '') > room['weights'][idx].get('updated_at', ''):
                        room['weights'][idx] = w
                else:
                    room['weights'].append(w)

            room['history'].append({'user': user, 'action': 'pushed',
                'time': datetime.now().isoformat()})
            return {'ok': True, 'logs': len(room['logs']), 'weights': len(room['weights'])}

        result = _transactional_push(code, do_push)
        if result is None:
            return _json({'error': 'Room not found'}, 404)
        return _json(result)

    @app.route('/sync/pull', methods=['GET', 'OPTIONS'])
    def sync_pull():
        if request.method == 'OPTIONS': return _json({})
        room = _load(request.args.get('code'))
        if not room: return _json({'error': 'Room not found'}, 404)
        return _json({'gecko': room['gecko'], 'logs': room['logs'],
            'weights': room['weights'], 'updated_at': room['updated_at']})

    @app.route('/sync/status', methods=['GET', 'OPTIONS'])
    def sync_status():
        if request.method == 'OPTIONS': return _json({})
        room = _load(request.args.get('code'))
        if not room: return _json({'error': 'Room not found'}, 404)
        return _json({'code': room['code'], 'logs': len(room['logs']),
            'weights': len(room['weights']), 'updated_at': room['updated_at'],
            'history': room['history'][-5:]})

    @app.route('/sync/room', methods=['DELETE', 'OPTIONS'])
    def sync_delete_room():
        if request.method == 'OPTIONS': return _json({})
        code = request.args.get('code')
        if not code: return _json({'error': 'Missing code'}, 400)
        conn = _get_db()
        cursor = conn.execute("DELETE FROM sync_rooms WHERE code = ?", (code,))
        conn.commit()
        conn.close()
        if cursor.rowcount == 0:
            return _json({'error': 'Room not found'}, 404)
        return _json({'ok': True})

    # ========== Medical Handbook Sync Endpoints (2026-05-02) ==========

    @app.route('/sync/medical/pull', methods=['GET', 'OPTIONS'])
    def sync_medical_pull():
        """Pull all medical records for a sync room. Keys by sync code (not gecko_id)."""
        if request.method == 'OPTIONS': return _json({})
        code = request.args.get('code')
        if not code: return _json({'error': 'Missing code'}, 400)
        room = _load(code)
        if not room: return _json({'error': 'Room not found'}, 404)
        conn = _get_db()
        illnesses = [dict(r) for r in conn.execute(
            "SELECT * FROM medical_illnesses WHERE code = ?", (code,)).fetchall()]
        medicines = [dict(r) for r in conn.execute(
            "SELECT * FROM medical_medicines WHERE code = ?", (code,)).fetchall()]
        vet_visits = [dict(r) for r in conn.execute(
            "SELECT * FROM medical_vet_visits WHERE code = ?", (code,)).fetchall()]
        med_logs = [dict(r) for r in conn.execute(
            "SELECT * FROM medicine_log WHERE code = ?", (code,)).fetchall()]
        conn.close()
        return _json({'illnesses': illnesses, 'medicines': medicines, 'vet_visits': vet_visits, 'medicine_logs': med_logs})

    @app.route('/sync/medical/push', methods=['POST', 'OPTIONS'])
    def sync_medical_push():
        """Push medical records to the server. Upserts by ID."""
        if request.method == 'OPTIONS': return _json({})
        body = request.json
        code = body.get('code')
        user = body.get('user', '?')
        if not code: return _json({'error': 'Missing code'}, 400)
        room = _load(code)
        if not room: return _json({'error': 'Room not found'}, 404)
        conn = _get_db()
        try:
            conn.execute("BEGIN IMMEDIATE")
            now = datetime.now().isoformat()

            def _upsert(table, records):
                """Upsert records into a medical table. Keys by (code, id) for global uniqueness."""
                for rec in records:
                    rec['updated_at'] = now
                    existing = conn.execute(f"SELECT id FROM {table} WHERE code = ? AND id = ?",
                        (code, rec['id'])).fetchone()
                    if existing:
                        cols = ', '.join(f"{k} = ?" for k in rec if k not in ('id', 'code'))
                        vals = [rec[k] for k in rec if k not in ('id', 'code')] + [code, rec['id']]
                        conn.execute(f"UPDATE {table} SET {cols} WHERE code = ? AND id = ?", vals)
                    else:
                        rec['code'] = code
                        cols = ', '.join(rec.keys())
                        ph = ', '.join('?' * len(rec))
                        conn.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({ph})", list(rec.values()))

            _upsert('medical_illnesses', body.get('illnesses', []))
            _upsert('medical_medicines', body.get('medicines', []))
            _upsert('medical_vet_visits', body.get('vet_visits', []))

            # Handle medicine_logs separately (scoped by code, INSERT if new)
            for log in body.get('medicine_logs', []):
                existing = conn.execute(
                    'SELECT id FROM medicine_log WHERE code = ? AND medicine_id = ? AND taken_date = ?',
                    (code, log['medicine_id'], log['taken_date'])).fetchone()
                if not existing:
                    log['code'] = code
                    cols = ', '.join(log.keys())
                    ph = ', '.join('?' * len(log))
                    conn.execute(f"INSERT INTO medicine_log ({cols}) VALUES ({ph})", list(log.values()))

            # Handle deletions
            for id_set, table in [(body.get('deleted_illness_ids', []), 'medical_illnesses'),
                                   (body.get('deleted_medicine_ids', []), 'medical_medicines'),
                                   (body.get('deleted_vet_ids', []), 'medical_vet_visits'),
                                   (body.get('deleted_medlog_ids', []), 'medicine_log')]:
                for rid in id_set:
                    conn.execute(f"DELETE FROM {table} WHERE code = ? AND id = ?", (code, rid))

            conn.commit()
            result = {'ok': True, 'illnesses': len(body.get('illnesses', [])),
                      'medicines': len(body.get('medicines', [])),
                      'vet_visits': len(body.get('vet_visits', []))}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return _json(result)
