"""
Pronunciation Practice Blueprint - 普通話發音練習
Adds /pronunciation route to the existing kelvin-webapp
"""
from flask import Blueprint, render_template

pronunciation_bp = Blueprint('pronunciation', __name__, template_folder='templates')

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

PRONUNCIATION_VERSION = 'v1.16'

@pronunciation_bp.route('/pronunciation')
def index():
    return render_template('pronunciation.html', passages=PASSAGES, version=PRONUNCIATION_VERSION)
