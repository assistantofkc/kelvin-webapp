"""
Geckolab Sync API
Lightweight Flask API for syncing gecko data between users
Deployed at: https://assistantofkc.pythonanywhere.com/sync/
"""
from flask import Flask, request, jsonify
import json
import os
import secrets
from datetime import datetime

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), 'sync_data')
os.makedirs(DATA_DIR, exist_ok=True)


def _get_room_file(code):
    """Get the file path for a sync room code."""
    safe_code = ''.join(c for c in code if c.isalnum() or c in '-_')
    return os.path.join(DATA_DIR, f'{safe_code}.json')


def _load_room(code):
    """Load sync room data."""
    filepath = _get_room_file(code)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_room(code, data):
    """Save sync room data."""
    filepath = _get_room_file(code)
    data['updated_at'] = datetime.now().isoformat()
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@app.route('/create', methods=['POST'])
def create_room():
    """Create a new sync room. Returns sync_code."""
    code = secrets.token_hex(3).upper()  # e.g., "A1B2C3"
    data = {
        'code': code,
        'created_at': datetime.now().isoformat(),
        'gecko': None,       # { id, name, species, sex, birth_date, adopted_date, color, image_data, album_url }
        'logs': [],          # [{ id, gecko_id, log_date, log_type, quantity, period, food_type, paste_type, notes }]
        'weights': [],       # [{ id, gecko_id, weight, record_date, notes }]
        'history': []        # [{ user, action, timestamp }]
    }
    _save_room(code, data)
    data['history'].append({'user': request.json.get('user', 'A'), 'action': 'created', 'timestamp': datetime.now().isoformat()})
    _save_room(code, data)
    return jsonify({'sync_code': code, 'message': 'Sync room created'})


@app.route('/push', methods=['POST'])
def push_data():
    """Push local gecko data to sync room."""
    body = request.json
    code = body.get('code')
    gecko_data = body.get('gecko')
    logs = body.get('logs', [])
    weights = body.get('weights', [])
    user = body.get('user', 'unknown')

    if not code or not gecko_data:
        return jsonify({'error': 'Missing code or gecko data'}), 400

    room = _load_room(code)
    if not room:
        return jsonify({'error': 'Sync room not found'}), 404

    # Merge gecko profile (latest timestamp wins)
    if not room['gecko'] or (gecko_data.get('updated_at', '') > room['gecko'].get('updated_at', '')):
        room['gecko'] = gecko_data

    # Merge logs by ID (if same ID, later timestamp wins)
    existing_log_ids = {l['id']: i for i, l in enumerate(room['logs'])}
    for log in logs:
        if log['id'] in existing_log_ids:
            idx = existing_log_ids[log['id']]
            if log.get('updated_at', '') > room['logs'][idx].get('updated_at', ''):
                room['logs'][idx] = log
        else:
            room['logs'].append(log)

    # Merge weights by ID
    existing_weight_ids = {w['id']: i for i, w in enumerate(room['weights'])}
    for w in weights:
        if w['id'] in existing_weight_ids:
            idx = existing_weight_ids[w['id']]
            if w.get('updated_at', '') > room['weights'][idx].get('updated_at', ''):
                room['weights'][idx] = w
        else:
            room['weights'].append(w)

    room['history'].append({'user': user, 'action': 'pushed', 'timestamp': datetime.now().isoformat()})
    _save_room(code, room)
    return jsonify({'message': 'Data synced', 'log_count': len(room['logs']), 'weight_count': len(room['weights'])})


@app.route('/pull', methods=['GET'])
def pull_data():
    """Pull latest synced data from sync room."""
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Missing code'}), 400
        
    room = _load_room(code)
    if not room:
        return jsonify({'error': 'Sync room not found'}), 404

    return jsonify({
        'code': code,
        'gecko': room['gecko'],
        'logs': room['logs'],
        'weights': room['weights'],
        'updated_at': room['updated_at']
    })


@app.route('/status', methods=['GET'])
def room_status():
    """Check sync room status."""
    code = request.args.get('code')
    if not code:
        return jsonify({'error': 'Missing code'}), 400

    room = _load_room(code)
    if not room:
        return jsonify({'error': 'Sync room not found'}), 404

    return jsonify({
        'code': code,
        'created_at': room['created_at'],
        'updated_at': room['updated_at'],
        'log_count': len(room['logs']),
        'weight_count': len(room['weights']),
        'history': room['history'][-5:]  # last 5 actions
    })


if __name__ == '__main__':
    app.run(debug=True)
