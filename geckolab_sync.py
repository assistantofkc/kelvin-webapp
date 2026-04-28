"""
Geckolab Sync API Module
Imported by kelvin-webapp - self-contained, zero impact on existing routes
Storage: SQLite (transaction-safe, no race condition on concurrent pushes)
"""
import json, os, secrets, sqlite3
from datetime import datetime
from flask import request, jsonify, make_response

SYNC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_data')
os.makedirs(SYNC_DIR, exist_ok=True)
DB_PATH = os.path.join(SYNC_DIR, 'geckolab_sync.db')

def _cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
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

def _init_db():
    """Initialize the database schema."""
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
    conn.commit()
    conn.close()

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


def init_sync(app):
    _init_db()

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
