"""
Pronunciation Practice Blueprint - 普通話發音練習
Adds /pronunciation route to the existing kelvin-webapp
"""
import json
import os
from flask import Blueprint, render_template, request, jsonify
import requests

pronunciation_bp = Blueprint('pronunciation', __name__, template_folder='templates')

# Load .env file for local dev / PythonAnywhere
ENV_FILE = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(ENV_FILE):
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                if key not in os.environ:
                    os.environ[key] = val

PASSAGES = [
    {
        "id": 1,
        "title": "婆婆的餃子",
        "text": "餃子是我婆婆的中餐拿手菜，叫粟米紅蘿蔔豬肉餃子。內裡的豬肉鮮甜多汁和皮很薄，我很喜歡吃，每天早上都會吃它做早餐。"
    },
    {
        "id": 2,
        "title": "香港街頭小食 — 魚丸",
        "text": "今天我要介紹的香港街頭小食是魚丸，是一種很常見也很美味的小食，他很軟和彈牙，價錢也很便宜。辣辣的咖哩汁和魚丸簡直是絕配啊！"
    },
    {
        "id": 3,
        "title": "極端天氣 — 颱風",
        "text": "我今天要介紹的一種極端天氣就是颱風，它形成於熱帶的海洋，它會一直旋轉直到它化解，並令到它旁邊的各種物件卷上天空，造成人命傷亡，所以很危險的啊！"
    },
    {
        "id": 4,
        "title": "環保好方法",
        "text": "我要分享的一個環保好方法，就是會用舊襯衣重用做毛巾，在家中廚房需要經常抹油污，就可以用這些舊襯衣代替即棄紙巾，我覺得這種是很好的一個環保方法。"
    }
]

PRONUNCIATION_VERSION = 'v2.1'

# Path to custom passages JSON file on PythonAnywhere
CUSTOM_FILE = os.path.join(os.path.dirname(__file__), 'pronunciation_custom.json')

def load_custom_passages():
    """Load custom passages from JSON file, merge with defaults."""
    passages = [dict(p) for p in PASSAGES]  # Copy defaults
    try:
        if os.path.exists(CUSTOM_FILE):
            with open(CUSTOM_FILE, 'r', encoding='utf-8') as f:
                customs = json.load(f)
                for c in customs:
                    idx = c.get('id', 0) - 1
                    if 0 <= idx < len(passages):
                        if c.get('title'):
                            passages[idx]['title'] = c['title']
                        if c.get('text'):
                            passages[idx]['text'] = c['text']
    except Exception as e:
        print(f"Error loading custom passages: {e}")
    return passages

@pronunciation_bp.route('/pronunciation')
def index():
    passages = load_custom_passages()
    return render_template('pronunciation.html', passages=passages, version=PRONUNCIATION_VERSION)

@pronunciation_bp.route('/pronunciation/save-passage', methods=['POST'])
def save_passage():
    """Save a custom passage edit from the frontend."""
    data = request.get_json()
    passage_id = data.get('id')
    title = data.get('title', '')
    text = data.get('text', '')

    # Load existing customs
    customs = []
    try:
        if os.path.exists(CUSTOM_FILE):
            with open(CUSTOM_FILE, 'r', encoding='utf-8') as f:
                customs = json.load(f)
    except Exception:
        customs = []

    # Update or add the entry
    updated = False
    for c in customs:
        if c.get('id') == passage_id:
            c['title'] = title
            c['text'] = text
            updated = True
            break
    if not updated:
        customs.append({'id': passage_id, 'title': title, 'text': text})

    # Save to file
    try:
        with open(CUSTOM_FILE, 'w', encoding='utf-8') as f:
            json.dump(customs, f, ensure_ascii=False, indent=2)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@pronunciation_bp.route('/pronunciation/reset-passage', methods=['POST'])
def reset_passage():
    """Reset a passage back to default."""
    data = request.get_json()
    passage_id = data.get('id')

    customs = []
    try:
        if os.path.exists(CUSTOM_FILE):
            with open(CUSTOM_FILE, 'r', encoding='utf-8') as f:
                customs = json.load(f)
    except Exception:
        customs = []

    # Remove the entry for this passage
    customs = [c for c in customs if c.get('id') != passage_id]

    try:
        with open(CUSTOM_FILE, 'w', encoding='utf-8') as f:
            json.dump(customs, f, ensure_ascii=False, indent=2)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@pronunciation_bp.route('/pronunciation/assess', methods=['POST'])
def assess_pronunciation():
    """
    Azure Pronunciation Assessment endpoint.
    Receives audio (WAV) + reference text, returns phoneme-level scores.
    """
    api_key = os.environ.get('AZURE_SPEECH_KEY', '')
    region = os.environ.get('AZURE_SPEECH_REGION', 'eastasia')
    if not api_key:
        return jsonify({'status': 'error', 'message': 'Azure key not configured'}), 500

    reference_text = request.form.get('reference', '')
    if 'audio' not in request.files:
        return jsonify({'status': 'error', 'message': 'No audio file'}), 400

    audio_file = request.files['audio']
    audio_data = audio_file.read()

    if len(audio_data) < 100:
        return jsonify({'status': 'error', 'message': 'Audio too short'}), 400

    # Call Azure Pronunciation Assessment API
    url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=zh-CN"

    pa_config = json.dumps({
        "ReferenceText": reference_text,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "EnableMiscue": True
    })
    # MUST be base64 encoded for REST API
    import base64
    pa_config_b64 = base64.b64encode(pa_config.encode('utf-8')).decode('ascii')

    headers = {
        'Ocp-Apim-Subscription-Key': api_key,
        'Pronunciation-Assessment': pa_config_b64,
        'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000',
        'Accept': 'application/json'
    }

    try:
        resp = requests.post(url, headers=headers, data=audio_data, timeout=30)
        result = resp.json()

        if resp.status_code != 200:
            err_msg = result.get('Message', str(result)) if isinstance(result, dict) else str(result)
            return jsonify({'status': 'error', 'message': err_msg}), resp.status_code

        # Parse Azure response into phoneme-level feedback
        words_result = []
        if 'NBest' in result and len(result['NBest']) > 0:
            nbest = result['NBest'][0]
            if 'Words' in nbest:
                for w in nbest['Words']:
                    pa = w.get('PronunciationAssessment', {})
                    if isinstance(pa, str):
                        pa = {}
                    word_info = {
                        'word': w.get('Word', ''),
                        'accuracy': pa.get('AccuracyScore', 0) if isinstance(pa, dict) else 0,
                        'error_type': pa.get('ErrorType', '') if isinstance(pa, dict) else '',
                        'phonemes': []
                    }
                    if 'Phonemes' in w:
                        for p in w['Phonemes']:
                            ph_pa = p.get('PronunciationAssessment', {})
                            if isinstance(ph_pa, str):
                                ph_pa = {}
                            word_info['phonemes'].append({
                                'phoneme': p.get('Phoneme', ''),
                                'accuracy': ph_pa.get('AccuracyScore', 0) if isinstance(ph_pa, dict) else 0,
                            })
                    words_result.append(word_info)

        return jsonify({
            'status': 'ok',
            'recognition': result.get('DisplayText', ''),
            'words': words_result
        })

    except requests.exceptions.Timeout:
        return jsonify({'status': 'error', 'message': 'Azure API timeout'}), 504
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
