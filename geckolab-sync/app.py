"""
Geckolab Sync API - Standalone Flask App
Deployed in /home/assistantofkc/geckolab-sync/
Mount in WSGI at /sync path
"""
from flask import Flask, request, jsonify
import json
import os
import secrets
from datetime import datetime

app = Flask(__name__)
SYNC_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_data')
os.makedirs(SYNC_DATA_DIR, exist_ok=True)

def _get_room_file(code):
    safe = ''.join(c for c in code if c.isalnum() or c in '-_')
    return os.path.join(SYNC_DATA_DIR, f'{safe}.json')

def _load(code):
    f = _get_room_file(code)
    if not os.path.exists(f): return None
    with open(f, 'r', encoding='utf-8') as fp:
        return json.load(fp)

def _save(code, data):
    data['updated_at'] = datetime.now().isoformat()
    with open(_get_room_file(code), 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)

@app.route('/sync/create', methods=['POST'])
def create():
    code = secrets.token_hex(3).upper()
    data = {'code': code, 'created_at': datetime.now().isoformat(),
            'gecko': None, 'logs': [], 'weights': [], 'history': []}
    _save(code, data)
    data['history'].append({'user': request.json.get('user', 'A'),
        'action': 'created', 'timestamp': datetime.now().isoformat()})
    _save(code, data)
    return jsonify({'sync_code': code, 'message': 'Sync room created'})

@app.route('/sync/push', methods=['POST'])
def push():
    body = request.json
    room = _load(body.get('code'))
    if not room: return jsonify({'error': 'Room not found'}), 404
    gecko = body.get('gecko')
    if gecko and (not room['gecko'] or
        gecko.get('updated_at', '') > room['gecko'].get('updated_at', '')):
        room['gecko'] = gecko
    for key in ['logs', 'weights']:
        existing = {i['id']: i for i in room[key]}
        for item in body.get(key, []):
            if item['id'] in existing:
                if item.get('updated_at', '') > existing[item['id']].get('updated_at', ''):
                    room[key][room[key].index(existing[item['id']])] = item
            else:
                room[key].append(item)
    room['history'].append({'user': body.get('user', '?'),
        'action': 'pushed', 'timestamp': datetime.now().isoformat()})
    _save(body['code'], room)
    return jsonify({'message': 'Synced', 'log_count': len(room['logs']),
        'weight_count': len(room['weights'])})

@app.route('/sync/pull', methods=['GET'])
def pull():
    room = _load(request.args.get('code'))
    if not room: return jsonify({'error': 'Room not found'}), 404
    return jsonify({'code': room['code'], 'gecko': room['gecko'],
        'logs': room['logs'], 'weights': room['weights'],
        'updated_at': room['updated_at']})

@app.route('/sync/status', methods=['GET'])
def status():
    room = _load(request.args.get('code'))
    if not room: return jsonify({'error': 'Room not found'}), 404
    return jsonify({'code': room['code'], 'created_at': room['created_at'],
        'updated_at': room['updated_at'], 'log_count': len(room['logs']),
        'weight_count': len(room['weights']),
        'history': room['history'][-5:]})
