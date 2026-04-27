"""
Geckolab Sync API Module
Imported by kelvin-webapp - self-contained, zero impact on existing routes
Sync data stored in sync_data/ folder (auto-created, gitignored)
"""
import json, os, secrets
from datetime import datetime
from flask import request, jsonify

SYNC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_data')
os.makedirs(SYNC_DIR, exist_ok=True)

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
    @app.route('/sync/create', methods=['POST'])
    def sync_create():
        code = secrets.token_hex(3).upper()
        data = {'code': code, 'created_at': datetime.now().isoformat(),
                'app_version': request.json.get('app_version', 'unknown'),
                'gecko': None, 'logs': [], 'weights': [], 'history': []}
        _save(code, data)
        data['history'].append({'user': request.json.get('user', 'A'),
            'action': 'created', 'time': datetime.now().isoformat()})
        _save(code, data)
        return jsonify({'sync_code': code})

    @app.route('/sync/push', methods=['POST'])
    def sync_push():
        body = request.json
        room = _load(body.get('code'))
        if not room: return jsonify({'error': 'Room not found'}), 404
        g = body.get('gecko')
        if g and (not room['gecko'] or g.get('updated_at','') > room['gecko'].get('updated_at','')):
            room['gecko'] = g
        for key in ['logs', 'weights']:
            idxs = {i['id']: i for i in room[key]}
            for item in body.get(key, []):
                if item['id'] in idxs:
                    if item.get('updated_at','') > idxs[item['id']].get('updated_at',''):
                        room[key][room[key].index(idxs[item['id']])] = item
                else:
                    room[key].append(item)
        room['history'].append({'user': body.get('user','?'), 'action': 'pushed',
            'time': datetime.now().isoformat()})
        _save(body['code'], room)
        return jsonify({'ok': True, 'logs': len(room['logs']), 'weights': len(room['weights'])})

    @app.route('/sync/pull', methods=['GET'])
    def sync_pull():
        room = _load(request.args.get('code'))
        if not room: return jsonify({'error': 'Room not found'}), 404
        return jsonify({'gecko': room['gecko'], 'logs': room['logs'],
            'weights': room['weights'], 'updated_at': room['updated_at']})

    @app.route('/sync/status', methods=['GET'])
    def sync_status():
        room = _load(request.args.get('code'))
        if not room: return jsonify({'error': 'Room not found'}), 404
        return jsonify({'code': room['code'], 'logs': len(room['logs']),
            'weights': len(room['weights']), 'updated_at': room['updated_at'],
            'history': room['history'][-5:]})
