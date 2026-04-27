"""
Geckolab Sync API Module
Imported by kelvin-webapp - self-contained, zero impact on existing routes
Sync data stored in sync_data/ folder (auto-created, gitignored)
"""
import json, os, secrets
from datetime import datetime
from flask import request, jsonify, make_response

SYNC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_data')
os.makedirs(SYNC_DIR, exist_ok=True)

def _cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return resp

def _json(data, status=200):
    return _cors(make_response(jsonify(data), status))

def _f(code):
    safe = ''.join(c for c in code if c.isalnum() or c in '-_')
    return os.path.join(SYNC_DIR, f'{safe}.json')

def _load(code):
    f = _f(code)
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else None

def _save(code, data):
    data['updated_at'] = datetime.now().isoformat()
    json.dump(data, open(_f(code), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

def init_sync(app):
    @app.route('/sync/create', methods=['POST', 'OPTIONS'])
    def sync_create():
        if request.method == 'OPTIONS': return _json({})
        code = secrets.token_hex(3).upper()
        data = {'code': code, 'created_at': datetime.now().isoformat(),
                'app_version': request.json.get('app_version', 'unknown'),
                'gecko': None, 'logs': [], 'weights': [], 'history': []}
        _save(code, data)
        data['history'].append({'user': request.json.get('user', 'A'),
            'action': 'created', 'time': datetime.now().isoformat()})
        _save(code, data)
        return _json({'sync_code': code})

    @app.route('/sync/push', methods=['POST', 'OPTIONS'])
    def sync_push():
        if request.method == 'OPTIONS': return _json({})
        body = request.json
        code = body.get('code')
        user = body.get('user', '?')
        room = _load(code)
        if not room: return _json({'error': 'Room not found'}, 404)
        g = body.get('gecko')
        if g and (not room['gecko'] or g.get('updated_at','') > room['gecko'].get('updated_at','')):
            room['gecko'] = g

        # Apply deletions first (before merging new data)
        deleted_log_ids = set(body.get('deleted_log_ids', []))
        deleted_weight_ids = set(body.get('deleted_weight_ids', []))
        if deleted_log_ids:
            room['logs'] = [l for l in room['logs'] if l['id'] not in deleted_log_ids]
            room['history'].append({'user': user, 'action': f'deleted {len(deleted_log_ids)} logs',
                'time': datetime.now().isoformat()})
        if deleted_weight_ids:
            room['weights'] = [w for w in room['weights'] if w['id'] not in deleted_weight_ids]
            room['history'].append({'user': user, 'action': f'deleted {len(deleted_weight_ids)} weights',
                'time': datetime.now().isoformat()})

        # Merge logs by ID (if same ID, later timestamp wins)
        logs = body.get('logs', [])
        existing_log_ids = {l['id']: i for i, l in enumerate(room['logs'])}
        for log in logs:
            if log['id'] in existing_log_ids:
                idx = existing_log_ids[log['id']]
                if log.get('updated_at', '') > room['logs'][idx].get('updated_at', ''):
                    room['logs'][idx] = log
            else:
                room['logs'].append(log)

        # Merge weights by ID
        weights = body.get('weights', [])
        existing_weight_ids = {w['id']: i for i, w in enumerate(room['weights'])}
        for w in weights:
            if w['id'] in existing_weight_ids:
                idx = existing_weight_ids[w['id']]
                if w.get('updated_at', '') > room['weights'][idx].get('updated_at', ''):
                    room['weights'][idx] = w
            else:
                room['weights'].append(w)

        room['history'].append({'user': user, 'action': 'pushed',
            'time': datetime.now().isoformat()})
        _save(code, room)
        return _json({'ok': True, 'logs': len(room['logs']), 'weights': len(room['weights'])})

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
