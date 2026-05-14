"""
Cooking Ideas - SQLite Models
Recipe database with seed data
"""

import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), 'recipes.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            name_en TEXT DEFAULT '',
            cuisine TEXT NOT NULL,
            cooking_method TEXT NOT NULL,
            taste TEXT NOT NULL,
            nutrition_tags TEXT NOT NULL,
            prep_time_min INTEGER DEFAULT 30,
            can_prep_early INTEGER DEFAULT 0,
            has_soup INTEGER DEFAULT 0,
            has_cold_dish INTEGER DEFAULT 0,
            is_spicy INTEGER DEFAULT 0,
            ingredients TEXT NOT NULL,
            steps TEXT NOT NULL,
            tips TEXT DEFAULT '',
            source TEXT DEFAULT 'seed',
            servings INTEGER DEFAULT 4,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS custom_dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            recipe_id INTEGER,
            notes TEXT DEFAULT '',
            added_by TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (recipe_id) REFERENCES recipes(id)
        )
    ''')
    
    # Check if seed data already exists
    c.execute('SELECT COUNT(*) FROM recipes')
    count = c.fetchone()[0]
    
    if count == 0:
        seed_recipes(c)
    
    conn.commit()
    conn.close()

def seed_recipes(c):
    """Seed ~100 recipes across 4 cuisines."""
    recipes = []
    
    # ===== CHINESE (中菜) - 25 recipes =====
    chinese = [
        {"name":"清蒸石斑魚","cuisine":"中式","method":"蒸","taste":"清淡","nutrition":"魚,蛋白質","time":25,"early":0,"spicy":0,"ingredients":"石斑魚1條,薑絲,蔥段,蒸魚豉油,油","steps":"1. 石斑魚洗淨，魚身兩面切花刀\n2. 鋪上薑絲，放入蒸鍋大火蒸10-12分鐘\n3. 倒去蒸魚水，鋪上新鮮蔥絲\n4. 淋上蒸魚豉油，熱油澆在蔥絲上即可","tips":"蒸魚時間按魚嘅大細調整，每500g約蒸8分鐘"},
        {"name":"麻婆豆腐","cuisine":"中式","method":"炒","taste":"辣","nutrition":"白肉,蛋白質","time":20,"early":0,"spicy":1,"ingredients":"豆腐1盒,豬肉碎100g,豆瓣醬,花椒粉,蒜蓉,蔥花,生抽","steps":"1. 豆腐切小方塊，汆水備用\n2. 熱油爆香蒜蓉、豆瓣醬\n3. 加入豬肉碎炒至變色\n4. 加水煮滾，放入豆腐輕輕拌勻\n5. 小火煮5分鐘，勾薄芡\n6. 灑花椒粉同蔥花上碟","tips":"豆腐先汆水可以定形，唔容易爛"},
        {"name":"乾炒牛河","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"紅肉,澱粉質","time":20,"early":0,"spicy":0,"ingredients":"河粉300g,牛肉片150g,芽菜,洋蔥絲,蔥段,生抽,老抽,油","steps":"1. 牛肉用生抽、生粉醃15分鐘\n2. 河粉分開，大火熱油炒香洋蔥\n3. 加入牛肉大火爆炒至七成熟\n4. 落河粉大火快炒，加入生抽老抽調味\n5. 最後加入芽菜、蔥段兜勻上碟","tips":"全程大火，河粉要分開先落鑊"},
        {"name":"白切雞","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"白肉,蛋白質","time":45,"early":0,"spicy":0,"ingredients":"雞1隻(約1.5kg),薑片,蔥段,鹽,薑蓉蘸料","steps":"1. 大煲水煮滾，加入薑片蔥段\n2. 雞放入滾水中，水再滾後轉小火\n3. 浸煮約30-35分鐘至熟\n4. 取出放入冰水浸泡10分鐘定皮\n5. 斬件上碟，配薑蓉蘸料","tips":"用筷子插入雞髀，流出清汁即熟"},
        {"name":"咕嚕肉","cuisine":"中式","method":"炸","taste":"濃味","nutrition":"紅肉,澱粉質","time":30,"early":0,"spicy":0,"ingredients":"豬肉200g,菠蘿,青椒,紅椒,雞蛋,生粉,甜酸醬","steps":"1. 豬肉切件，用鹽、胡椒粉醃15分鐘\n2. 沾蛋液再上生粉，油炸至金黃\n3. 菠蘿、青紅椒切塊\n4. 甜酸醬煮滾，加入所有材料快炒兜勻","tips":"豬肉炸兩次會更脆"},
        {"name":"蝦餃","cuisine":"中式","method":"蒸","taste":"清淡","nutrition":"白肉,蛋白質","time":40,"early":1,"spicy":0,"ingredients":"澄麵150g,生粉50g,蝦仁200g,肥豬肉50g,竹筍粒,調味料","steps":"1. 澄麵+生粉用滾水搓成粉糰\n2. 蝦仁切粒，加入肥豬肉、竹筍、調味拌勻\n3. 粉糰擀薄皮，包入餡料\n4. 摺出花邊，大火蒸6-8分鐘","tips":"餃皮要擀得夠薄先透明"},
        {"name":"薑蔥炒蟹","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"白肉,蛋白質","time":25,"early":0,"spicy":0,"ingredients":"花蟹2隻,薑片,蔥段,蒜蓉,生抽,蠔油,生粉","steps":"1. 蟹洗淨斬件，蟹鉗拍裂\n2. 蟹件沾生粉，熱油半煎炸至變紅\n3. 爆香薑片、蒜蓉\n4. 落蟹件快炒，加入生抽蠔油調味\n5. 最後落蔥段兜勻","tips":"蟹件沾生粉炸可以鎖住肉汁"},
        {"name":"粟米魚肚羹","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"白肉,蛋白質","time":30,"early":0,"has_soup":1,"spicy":0,"ingredients":"魚肚100g,粟米蓉1罐,雞湯500ml,雞蛋1隻,生粉水","steps":"1. 魚肚浸軟切絲\n2. 雞湯煮滾，加入粟米蓉、魚肚\n3. 煮10分鐘後勾芡\n4. 熄火倒入蛋液攪拌成蛋花","tips":"蛋液要慢慢倒入同時不停攪拌"},
        {"name":"紅燒排骨","cuisine":"中式","method":"炆","taste":"濃味","nutrition":"紅肉,蛋白質","time":60,"early":1,"spicy":0,"ingredients":"排骨500g,生抽,老抽,冰糖,八角,桂皮,薑片,料酒","steps":"1. 排骨汆水去血沫\n2. 熱油爆香薑片、八角桂皮\n3. 落排骨煎至微金黃\n4. 加入生抽、老抽、冰糖、料酒、水\n5. 大火煮滾轉小火炆40分鐘至收汁","tips":"炆耐啲更入味，可以早一晚炆好"},
        {"name":"鹹蛋蒸肉餅","cuisine":"中式","method":"蒸","taste":"濃味","nutrition":"紅肉,蛋白質","time":20,"early":1,"spicy":0,"ingredients":"豬肉碎250g,鹹蛋2隻,生抽,胡椒粉,生粉,蔥花","steps":"1. 豬肉碎加入生抽、胡椒粉、生粉拌勻\n2. 平鋪在碟上，中間壓一個凹位\n3. 鹹蛋黃放在凹位上\n4. 大火蒸12-15分鐘\n5. 灑蔥花上碟","tips":"豬肉最好半肥瘦，蒸出來先滑"},
        {"name":"魚香茄子","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"菜,澱粉質","time":20,"early":0,"spicy":1,"ingredients":"茄子2條,豬肉碎100g,蒜蓉,豆瓣醬,蔥花,生抽,醋,糖","steps":"1. 茄子切條，熱油煎至軟身\n2. 爆香蒜蓉、豆瓣醬\n3. 加入豬肉碎炒散\n4. 加生抽、醋、糖調成魚香汁\n5. 加入茄子快炒兜勻","tips":"茄子先用鹽水浸可以防變黑"},
        {"name":"賽螃蟹","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"白肉,蛋白質","time":15,"early":0,"spicy":0,"ingredients":"蛋白4隻,蝦仁100g,蟹柳,薑末,醋,鹽,生粉水","steps":"1. 蛋白打散，加入鹽、生粉水\n2. 蝦仁、蟹柳切粒\n3. 熱油倒入蛋白液，小火慢慢推炒\n4. 蛋白成形後加入蝦仁蟹柳粒\n5. 上碟，配薑末醋","tips":"全程小火，蛋白先會嫩滑似蟹肉"},
        {"name":"乾煸四季豆","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"菜,澱粉質","time":15,"early":0,"spicy":0,"ingredients":"四季豆300g,豬肉碎80g,蒜蓉,乾辣椒,生抽,豆豉","steps":"1. 四季豆去筋，切段\n2. 熱油大火煸四季豆至表面起皺\n3. 撈起備用\n4. 爆香蒜蓉、豆豉、乾辣椒\n5. 加入豬肉碎炒散\n6. 落四季豆、生抽快炒兜勻","tips":"四季豆一定要煸熟，生食有毒"},
        {"name":"西湖牛肉羹","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"紅肉,蛋白質","time":30,"early":0,"has_soup":1,"spicy":0,"ingredients":"牛肉碎150g,豆腐1盒,蛋白2隻,雞湯500ml,芫茜,生粉水","steps":"1. 牛肉碎用生抽醃10分鐘\n2. 豆腐切小粒\n3. 雞湯煮滾，加入牛肉碎、豆腐粒\n4. 煮5分鐘後勾芡\n5. 熄火倒入蛋白攪拌\n6. 灑芫茜碎","tips":"牛肉碎要分散放入，唔好成舊落"},
        {"name":"蒜蓉炒菜心","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":8,"early":0,"spicy":0,"ingredients":"菜心300g,蒜蓉,鹽,油","steps":"1. 菜心洗淨，摘走老葉\n2. 熱油爆香蒜蓉\n3. 落菜心大火快炒\n4. 加少少水焗1分鐘\n5. 落鹽調味上碟","tips":"炒菜要夠鑊氣，全程大火"},
        {"name":"豉椒炒蜆","cuisine":"中式","method":"炒","taste":"辣","nutrition":"白肉,蛋白質","time":20,"early":0,"spicy":1,"ingredients":"蜆500g,豆豉,蒜蓉,辣椒,蔥段,生抽,蠔油","steps":"1. 蜆放入鹽水吐沙30分鐘\n2. 熱油爆香蒜蓉、豆豉、辣椒\n3. 落蜆大火快炒\n4. 加入生抽、蠔油調味\n5. 蜆殼打開即上碟，灑蔥段","tips":"蜆殼唔開嗰啲要揀走，唔好食"},
        {"name":"沙茶牛肉炒芥蘭","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"紅肉,菜","time":15,"early":0,"spicy":0,"ingredients":"牛肉片150g,芥蘭250g,沙茶醬,蒜蓉,生抽,生粉","steps":"1. 牛肉用生抽、生粉、沙茶醬醃15分鐘\n2. 芥蘭摘段，汆水備用\n3. 熱油爆香蒜蓉\n4. 落牛肉大火爆炒至七成熟\n5. 加入芥蘭快炒兜勻","tips":"芥蘭汆水可以去苦澀味"},
        {"name":"糯米飯","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"澱粉質,蛋白質","time":45,"early":0,"spicy":0,"ingredients":"糯米300g,冬菇,蝦米,臘腸,臘肉,蔥花,生抽,老抽","steps":"1. 糯米浸水4小時以上\n2. 冬菇、蝦米浸軟切粒，臘腸臘肉切粒\n3. 糯米隔水蒸30分鐘至熟\n4. 熱油爆香臘味、冬菇、蝦米\n5. 加入糯米飯、生抽老抽炒勻\n6. 灑蔥花上碟","tips":"糯米浸夠時間先蒸得透"},
        {"name":"口水雞","cuisine":"中式","method":"炆","taste":"辣","nutrition":"白肉,蛋白質","time":40,"early":1,"has_cold_dish":1,"spicy":1,"ingredients":"雞腿2隻,花椒油,辣椒油,芝麻醬,蒜蓉,芝麻,蔥花,青瓜絲","steps":"1. 雞腿煮熟後放入冰水定皮\n2. 去骨切件，鋪在青瓜絲上\n3. 花椒油+辣椒油+芝麻醬+蒜蓉調成醬汁\n4. 淋在雞上，灑芝麻蔥花","tips":"煮雞時加薑蔥可以去腥"},
        {"name":"蝦仁炒蛋","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"白肉,蛋白質","time":10,"early":0,"spicy":0,"ingredients":"蝦仁150g,雞蛋4隻,蔥花,鹽,胡椒粉,油","steps":"1. 蝦仁洗淨吸乾水，用鹽胡椒粉醃5分鐘\n2. 雞蛋打散加鹽\n3. 熱油先炒蝦仁至七成熟，撈起\n4. 落蛋液，半凝固時加回蝦仁\n5. 灑蔥花，輕輕炒勻上碟","tips":"蛋唔好炒太熟，半流心狀態最滑"},
        {"name":"西芹炒腰果","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜,蛋白質","time":15,"early":0,"spicy":0,"ingredients":"西芹250g,腰果100g,紅蘿蔔片,蒜蓉,鹽","steps":"1. 腰果用小火炸至金黃撈起\n2. 西芹去絲切段，汆水\n3. 熱油爆香蒜蓉\n4. 落西芹、紅蘿蔔快炒\n5. 加鹽調味，最後加入腰果兜勻","tips":"腰果最後先落保持脆口"},
        {"name":"冬瓜盅","cuisine":"中式","method":"燉","taste":"清淡","nutrition":"菜,白肉","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"小冬瓜1個,瘦肉粒,蝦仁,冬菇,瑤柱,金華火腿,雞湯","steps":"1. 冬瓜頂部切開做蓋，挖去瓜瓤\n2. 冬菇瑤柱浸軟，火腿切粒\n3. 所有材料放入冬瓜內\n4. 注入雞湯，蓋上冬瓜蓋\n5. 隔水燉1.5小時","tips":"燉盅水要夠熱，中途加水要加滾水"},
        {"name":"蜜汁叉燒","cuisine":"中式","method":"焗","taste":"濃味","nutrition":"紅肉,蛋白質","time":60,"early":1,"spicy":0,"ingredients":"豬肉(梅頭)500g,叉燒醬,蜜糖,生抽,老抽,玫瑰露酒","steps":"1. 豬肉用叉燒醬、生抽、老抽、玫瑰露酒醃過夜\n2. 預熱焗爐200°C\n3. 豬肉放在烤架上，焗20分鐘\n4. 掃上蜜糖，再焗10分鐘\n5. 翻面再掃蜜糖，焗多10分鐘\n6. 切片上碟","tips":"梅頭肉肥瘦適中最適合做叉燒"},
        {"name":"蒜蓉粉絲蒸扇貝","cuisine":"中式","method":"蒸","taste":"清淡","nutrition":"白肉,澱粉質","time":20,"early":1,"spicy":0,"ingredients":"扇貝6隻,粉絲1把,蒜蓉,蔥花,生抽,油","steps":"1. 粉絲浸軟剪段\n2. 扇貝洗淨，放上粉絲\n3. 蒜蓉用油爆香，鋪在扇貝上\n4. 大火蒸6-8分鐘\n5. 淋上生抽，灑蔥花\n6. 燒滾油淋上面","tips":"蒸海鮮時間唔可以太長，否則會韌"},
        {"name":"酸辣湯","cuisine":"中式","method":"炆","taste":"辣","nutrition":"菜,紅肉","time":30,"early":0,"has_soup":1,"spicy":1,"ingredients":"瘦肉絲,豆腐,木耳,冬菇,筍絲,雞蛋,醋,胡椒粉,生粉水","steps":"1. 木耳、冬菇浸軟切絲\n2. 雞湯煮滾，加入所有材料\n3. 煮10分鐘\n4. 加醋、胡椒粉、生抽調味\n5. 勾芡後熄火，倒入蛋液攪拌","tips":"醋要最後先落，保持酸味"},
    ]
    
    # ===== WESTERN (西式) - 25 recipes =====
    western = [
        {"name":"香草烤雞","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"白肉,蛋白質","time":90,"early":1,"spicy":0,"ingredients":"全雞1隻,迷迭香,百里香,檸檬,蒜頭,橄欖油,鹽,黑胡椒","steps":"1. 雞洗淨抹乾，內外塗抹鹽、黑胡椒、橄欖油\n2. 檸檬切半、蒜頭拍扁塞入雞肚\n3. 灑上迷迭香、百里香\n4. 預熱焗爐180°C，焗1-1.5小時\n5. 中途取出掃上肉汁\n6. 靜置10分鐘後切件","tips":"用溫度計插入雞髀，74°C即熟"},
        {"name":"卡邦尼意粉","cuisine":"西式","method":"炒","taste":"濃味","nutrition":"澱粉質,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"意粉200g,煙肉粒100g,蛋黃2隻,巴馬臣芝士碎,黑胡椒,鹽","steps":"1. 意粉按包裝時間煮至al dente\n2. 煙肉粒乾煎至脆\n3. 蛋黃+芝士碎+黑胡椒拌勻\n4. 意粉撈起後趁熱加入蛋黃芝士混合物\n5. 加入煙肉粒拌勻\n6. 灑額外芝士碎上碟","tips":"正宗Carbonara唔落cream，只用蛋黃芝士"},
        {"name":"煎牛扒配蘑菇汁","cuisine":"西式","method":"煎","taste":"濃味","nutrition":"紅肉,蛋白質","time":25,"early":0,"spicy":0,"ingredients":"牛扒200g,蘑菇100g,牛油,蒜頭,百里香,鹽,黑胡椒","steps":"1. 牛扒室溫放置30分鐘，抹乾灑鹽黑胡椒\n2. 大火熱鑊落油，煎牛扒每面2-3分鐘（medium rare）\n3. 最後加入牛油、蒜頭、百里香，用匙羹淋汁在牛扒上\n4. 取出靜置5分鐘\n5. 同鑊炒香蘑菇片做配菜","tips":"牛扒煎完一定要rest，鎖住肉汁"},
        {"name":"凱撒沙律","cuisine":"西式","method":"炒","taste":"清淡","nutrition":"菜,蛋白質","time":15,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"羅馬生菜,煙肉碎,巴馬臣芝士,麵包粒,凱撒醬,檸檬汁","steps":"1. 生菜洗淨撕成小塊\n2. 煙肉煎脆切碎\n3. 麵包粒用蒜油焗至金黃\n4. 混合生菜、凱撒醬、檸檬汁\n5. 灑上煙肉碎、芝士片、麵包粒","tips":"生菜要完全瀝乾水，否則沙律醬會稀"},
        {"name":"焗三文魚配檸檬牛油","cuisine":"西式","method":"焗","taste":"清淡","nutrition":"魚,蛋白質","time":25,"early":0,"spicy":0,"ingredients":"三文魚柳2塊,檸檬,牛油,蒜蓉,刁草,鹽,黑胡椒","steps":"1. 三文魚抹乾，灑鹽黑胡椒\n2. 焗盤鋪上檸檬片\n3. 放上三文魚，上面放牛油、蒜蓉、刁草\n4. 焗爐200°C焗12-15分鐘\n5. 擠檸檬汁上碟","tips":"三文魚唔好焗太熟，中間微微粉紅最滑"},
        {"name":"薯蓉","cuisine":"西式","method":"炆","taste":"清淡","nutrition":"澱粉質,菜","time":30,"early":0,"spicy":0,"ingredients":"薯仔500g,牛油50g,牛奶100ml,鹽,黑胡椒,豆蔻粉","steps":"1. 薯仔去皮切塊，煮15分鐘至軟\n2. 隔水後趁熱壓成蓉\n3. 加入牛油、熱牛奶拌勻\n4. 加鹽、黑胡椒、豆蔻粉調味","tips":"薯仔要趁熱壓，凍咗會起膠"},
        {"name":"法式洋蔥湯","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"菜,澱粉質","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"洋蔥4個,牛油,牛肉湯,白酒,法包,格魯耶爾芝士","steps":"1. 洋蔥切絲，用牛油小火炒30分鐘至焦糖色\n2. 加入白酒煮至揮發\n3. 加入牛肉湯煮20分鐘\n4. 湯倒入焗碗\n5. 放上法包片、鋪滿芝士\n6. 焗至芝士金黃","tips":"洋蔥要慢火炒先出甜味，急唔嚟"},
        {"name":"肉醬意粉","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"紅肉,澱粉質","time":45,"early":1,"spicy":0,"ingredients":"意粉200g,牛肉碎200g,洋蔥,甘筍,西芹,蒜蓉,番茄罐頭,紅酒,香草","steps":"1. 洋蔥、甘筍、西芹切碎粒\n2. 熱油炒香蔬菜粒、蒜蓉\n3. 加入牛肉碎炒散\n4. 加紅酒煮至揮發\n5. 加入番茄罐頭、香草，小火炆30分鐘\n6. 意粉煮好，淋上肉醬","tips":"肉醬炆耐啲更入味，可以早一晚整定"},
        {"name":"周打蜆湯","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"白肉,蛋白質","time":30,"early":0,"has_soup":1,"spicy":0,"ingredients":"蜆肉200g,薯仔,洋蔥,煙肉,牛油,麵粉,牛奶,淡忌廉","steps":"1. 煙肉煎脆切碎\n2. 牛油炒香洋蔥粒、薯仔粒\n3. 加入麵粉炒成roux\n4. 慢慢加入牛奶攪拌\n5. 加入蜆肉煮10分鐘\n6. 加入淡忌廉、灑煙肉碎","tips":"加奶要慢慢落，邊落邊攪避免起粒"},
        {"name":"燒豬肋骨","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"紅肉,蛋白質","time":120,"early":1,"spicy":0,"ingredients":"豬肋骨1排,BBQ醬,蜜糖,蒜粉,煙燻辣椒粉,鹽,黑胡椒","steps":"1. 混合香料塗抹豬肋骨\n2. 用錫紙包好，150°C焗1.5小時\n3. 取出打開錫紙\n4. 掃上BBQ醬+蜜糖\n5. 200°C再焗15分鐘至表面焦香","tips":"低溫慢焗先做到骨肉分離效果"},
        {"name":"白酒煮青口","cuisine":"西式","method":"炆","taste":"清淡","nutrition":"白肉,蛋白質","time":15,"early":0,"spicy":0,"ingredients":"青口500g,白酒150ml,蒜蓉,牛油,蕃茜碎,忌廉","steps":"1. 青口洗淨去鬚\n2. 牛油炒香蒜蓉\n3. 落青口、白酒，蓋上蓋煮3-4分鐘\n4. 青口打開後加入忌廉\n5. 灑蕃茜碎上碟","tips":"青口唔打開嗰啲唔好食"},
        {"name":"蘑菇意大利飯","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"澱粉質,菜","time":35,"early":0,"spicy":0,"ingredients":"意大利米200g,蘑菇,洋蔥,牛油,雞湯,白酒,巴馬臣芝士","steps":"1. 洋蔥切碎，蘑菇切片\n2. 牛油炒香洋蔥至透明\n3. 加入意大利米炒1分鐘\n4. 加白酒煮至揮發\n5. 逐少加入熱雞湯，不停攪拌\n6. 重複至米飯al dente\n7. 加入蘑菇、芝士拌勻","tips":"雞湯要逐羹落，不停攪拌出澱粉質先creamy"},
        {"name":"烤蔬菜沙律","cuisine":"西式","method":"焗","taste":"清淡","nutrition":"菜","time":30,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"意大利青瓜,甜椒,茄子,車厘茄,橄欖油,黑醋,鹽","steps":"1. 蔬菜切大塊\n2. 拌入橄欖油、鹽\n3. 焗爐200°C焗20分鐘\n4. 放涼後淋黑醋\n5. 灑新鮮香草","tips":"蔬菜要切得大細一致先均勻焗熟"},
        {"name":"班尼迪蛋","cuisine":"西式","method":"煎","taste":"濃味","nutrition":"蛋白質,澱粉質","time":20,"early":0,"spicy":0,"ingredients":"雞蛋2隻,英式鬆餅,煙三文魚/火腿,荷蘭醬,白醋","steps":"1. 水煮滾加白醋，攪出漩渦\n2. 打入雞蛋，小火煮3分鐘\n3. 鬆餅烘熱\n4. 鋪上煙三文魚、水波蛋\n5. 淋上荷蘭醬","tips":"水波蛋要新鮮雞蛋先靚，蛋白唔會散"},
        {"name":"鬆餅","cuisine":"西式","method":"焗","taste":"清淡","nutrition":"澱粉質","time":25,"early":1,"spicy":0,"ingredients":"麵粉200g,泡打粉,糖50g,牛油50g,牛奶120ml,雞蛋1隻","steps":"1. 麵粉+泡打粉+糖混合\n2. 加入凍牛油粒，用手指搓成麵包糠狀\n3. 加入蛋液、牛奶輕手拌勻\n4. 搓成圓形，切出鬆餅形狀\n5. 200°C焗12-15分鐘","tips":"麵糰唔好搓太耐，否則唔鬆軟"},
        {"name":"炸魚薯條","cuisine":"西式","method":"炸","taste":"濃味","nutrition":"魚,澱粉質","time":30,"early":0,"spicy":0,"ingredients":"魚柳2塊,麵粉,啤酒/梳打水,薯仔2個,鹽,檸檬,他他醬","steps":"1. 薯仔切粗條，浸水去澱粉\n2. 油炸第一次至軟身（160°C）\n3. 麵粉+啤酒攪成炸漿\n4. 魚柳沾漿，180°C炸至金黃\n5. 薯條再炸第二次至脆（190°C）\n6. 配檸檬、他他醬","tips":"薯條炸兩次先外脆內軟"},
        {"name":"千層麵","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"紅肉,澱粉質","time":60,"early":1,"spicy":0,"ingredients":"千層麵皮,肉醬,白醬(牛油+麵粉+牛奶),芝士碎","steps":"1. 準備肉醬（參考肉醬意粉）\n2. 準備白醬：牛油+麵粉炒勻，加牛奶攪拌\n3. 焗盤一層肉醬→麵皮→白醬→芝士，重複\n4. 最上層灑大量芝士\n5. 180°C焗30-40分鐘","tips":"麵皮要完全被醬汁覆蓋先唔會乾"},
        {"name":"番茄濃湯","cuisine":"西式","method":"炆","taste":"清淡","nutrition":"菜","time":25,"early":0,"has_soup":1,"spicy":0,"ingredients":"番茄4個,洋蔥,蒜頭,羅勒,雞湯,淡忌廉","steps":"1. 番茄、洋蔥切塊\n2. 橄欖油炒香洋蔥蒜頭\n3. 加入番茄煮10分鐘\n4. 用攪拌機打成蓉\n5. 加入雞湯、羅勒煮5分鐘\n6. 淋淡忌廉裝飾","tips":"用新鮮成熟番茄味道最好"},
        {"name":"焗薯皮","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"澱粉質,蛋白質","time":50,"early":1,"spicy":0,"ingredients":"薯仔4個,煙肉碎,芝士碎,酸忌廉,蔥花,牛油","steps":"1. 薯仔200°C焗45分鐘至熟\n2. 切半挖出薯肉（留邊約5mm）\n3. 薯皮內外掃牛油\n4. 放回焗爐焗至脆\n5. 放入煙肉、芝士\n6. 焗至芝士溶化\n7. 配酸忌廉蔥花","tips":"薯皮要焗到脆先好食"},
        {"name":"香煎帶子配粟米蓉","cuisine":"西式","method":"煎","taste":"清淡","nutrition":"白肉,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"帶子6隻,粟米蓉,牛油,蒜頭,鹽,黑胡椒,番茜","steps":"1. 帶子抹乾，灑鹽黑胡椒\n2. 大火熱油，煎帶子每面1.5分鐘至金黃\n3. 取出備用\n4. 同鑊加牛油蒜蓉\n5. 粟米蓉加熱\n6. 粟米蓉鋪底，放上帶子","tips":"帶子一定要抹乾先煎到金黃"},
        {"name":"布朗尼","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"澱粉質","time":35,"early":1,"spicy":0,"ingredients":"黑朱古力200g,牛油150g,糖150g,雞蛋3隻,麵粉100g,合桃碎","steps":"1. 朱古力+牛油隔水座溶\n2. 加入糖拌勻，稍涼後加蛋\n3. 篩入麵粉輕手拌勻\n4. 加入合桃碎\n5. 倒入焗盤，180°C焗20-25分鐘","tips":"布朗尼中間微微濕潤先正宗"},
        {"name":"希臘沙律","cuisine":"西式","method":"炒","taste":"清淡","nutrition":"菜,蛋白質","time":10,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"番茄,青瓜,紫洋蔥,橄欖,Feta芝士,橄欖油,紅酒醋,奧勒岡","steps":"1. 番茄、青瓜、紫洋蔥切塊\n2. 加入橄欖、Feta芝士\n3. 淋橄欖油、紅酒醋\n4. 灑奧勒岡香草","tips":"Feta芝士本身夠鹹，唔使額外加鹽"},
        {"name":"西班牙海鮮飯","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"白肉,澱粉質","time":50,"early":0,"spicy":0,"ingredients":"意大利米,蝦,青口,魷魚,雞肉,番茄,洋蔥,番紅花,雞湯","steps":"1. 海鮮處理乾淨\n2. 橄欖油炒香洋蔥、番茄\n3. 加入米炒1分鐘\n4. 加入番紅花、雞湯\n5. 鋪上海鮮、雞肉\n6. 小火煮20分鐘，不要攪拌\n7. 最後大火2分鐘做出飯焦","tips":"煮飯過程唔好攪拌，先做到飯焦"},
        {"name":"香草烤羊架","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"紅肉,蛋白質","time":40,"early":1,"spicy":0,"ingredients":"羊架1排,迷迭香,芥末醬,麵包糠,蒜蓉,橄欖油,鹽,黑胡椒","steps":"1. 羊架抹乾，灑鹽黑胡椒\n2. 大火煎封表面\n3. 掃上芥末醬\n4. 麵包糠+迷迭香+蒜蓉+橄欖油混合，鋪在羊架上\n5. 200°C焗15-20分鐘（medium）\n6. 靜置5分鐘切件","tips":"羊架要室溫回溫先煎封"},
    ]
    
    # ===== JAPANESE (日式) - 25 recipes =====
    japanese = [
        {"name":"照燒雞扒","cuisine":"日式","method":"煎","taste":"濃味","nutrition":"白肉,蛋白質","time":25,"early":1,"spicy":0,"ingredients":"雞腿肉2塊,照燒汁(醬油+味醂+清酒+糖),白芝麻","steps":"1. 雞腿肉去筋，用叉在皮上戳洞\n2. 雞皮向下冷鑊慢火煎至金黃脆皮\n3. 翻面再煎至熟\n4. 加入照燒汁煮至濃稠\n5. 切片灑白芝麻","tips":"從冷鑊開始煎皮可以逼出雞油，皮更脆"},
        {"name":"味噌湯","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"菜,蛋白質","time":15,"early":0,"has_soup":1,"spicy":0,"ingredients":"昆布高湯500ml,白味噌2湯匙,豆腐,海帶,蔥花","steps":"1. 昆布浸水30分鐘，然後煮至微滾（不要大滾）\n2. 取出昆布，加入豆腐粒、海帶\n3. 熄火，用篩溶入味噌\n4. 灑蔥花","tips":"味噌一定要熄火後先落，否則香味會走"},
        {"name":"日式咖哩飯","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"紅肉,澱粉質,菜","time":40,"early":1,"spicy":0,"ingredients":"咖哩磚,牛肉/雞肉200g,洋蔥,甘筍,薯仔,白飯","steps":"1. 洋蔥、甘筍、薯仔切塊\n2. 熱油炒香洋蔥至透明\n3. 加入肉類炒至變色\n4. 加水煮滾，撇去浮沫\n5. 小火煮20分鐘至蔬菜軟\n6. 熄火加入咖哩磚攪拌\n7. 小火再煮5分鐘至濃稠\n8. 配上白飯","tips":"日式咖哩隔夜更好食，可以早一晚整定"},
        {"name":"吉列豬扒","cuisine":"日式","method":"炸","taste":"濃味","nutrition":"紅肉,澱粉質","time":30,"early":0,"spicy":0,"ingredients":"豬扒2塊,麵粉,雞蛋,麵包糠,椰菜絲,豬扒醬,檸檬","steps":"1. 豬扒用刀背拍鬆，灑鹽胡椒\n2. 順序沾上麵粉→蛋液→麵包糠\n3. 170°C油炸至金黃（約5-6分鐘）\n4. 切條上碟\n5. 配椰菜絲、豬扒醬、檸檬","tips":"麵包糠要用日式粗粒，炸出嚟先脆"},
        {"name":"壽喜燒","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"紅肉,菜,蛋白質","time":30,"early":0,"spicy":0,"ingredients":"牛肉薄片200g,豆腐,大蔥,白菜,冬菇,蒟蒻絲,壽喜燒汁,生雞蛋","steps":"1. 壽喜燒汁：醬油+味醂+清酒+糖煮溶\n2. 熱鍋用牛油擦底\n3. 煎香大蔥段、牛肉片\n4. 加入壽喜燒汁\n5. 放入豆腐、白菜、冬菇、蒟蒻絲\n6. 邊煮邊食，牛肉沾生雞蛋食","tips":"牛肉唔好煮太熟，變色即食"},
        {"name":"天婦羅","cuisine":"日式","method":"炸","taste":"清淡","nutrition":"菜,白肉","time":30,"early":0,"spicy":0,"ingredients":"蝦,蕃薯,茄子,南瓜,天婦羅粉,冰水,天婦羅汁","steps":"1. 蔬菜切片，蝦去殼留尾\n2. 天婦羅粉+冰水輕手拌勻（有顆粒都OK）\n3. 材料沾粉漿\n4. 170-180°C油炸至脆\n5. 配天婦羅汁","tips":"粉漿要用冰水唔好攪太勻，炸出嚟先脆"},
        {"name":"親子丼","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"白肉,蛋白質,澱粉質","time":15,"early":0,"spicy":0,"ingredients":"雞腿肉1塊,雞蛋2隻,洋蔥,白飯,醬油,味醂,清酒,高湯","steps":"1. 醬油+味醂+清酒+高湯煮成丼汁\n2. 洋蔥切絲，雞肉切件\n3. 丼汁煮滾，加入洋蔥煮軟\n4. 加入雞肉煮熟\n5. 蛋液分兩次倒入（第一次8成熟，第二次半熟）\n6. 淋在白飯上","tips":"蛋液分兩次落，做出滑嫩同流心雙重口感"},
        {"name":"大阪燒","cuisine":"日式","method":"煎","taste":"濃味","nutrition":"澱粉質,菜","time":20,"early":0,"spicy":0,"ingredients":"大阪燒粉100g,水,雞蛋,椰菜絲,豬肉片,大阪燒醬,蛋黃醬,木魚碎,紫菜粉","steps":"1. 粉+水+雞蛋拌成麵糊\n2. 加入大量椰菜絲拌勻\n3. 平底鑊煎成圓餅形\n4. 鋪上豬肉片\n5. 兩面煎至金黃\n6. 掃上大阪燒醬、蛋黃醬\n7. 灑木魚碎、紫菜粉","tips":"椰菜要多，煎時唔好壓扁"},
        {"name":"三文魚刺身飯","cuisine":"日式","method":"炒","taste":"清淡","nutrition":"魚,澱粉質","time":15,"early":0,"spicy":0,"ingredients":"三文魚刺身200g,壽司飯,紫菜絲,芝麻,醬油,芥末","steps":"1. 壽司飯煮好加壽司醋拌勻放涼\n2. 三文魚切片\n3. 飯上鋪三文魚\n4. 灑紫菜絲、芝麻\n5. 配醬油芥末","tips":"三文魚買刺身級別，飯要放涼先鋪魚"},
        {"name":"味噌烤銀鱈魚","cuisine":"日式","method":"焗","taste":"濃味","nutrition":"魚,蛋白質","time":40,"early":1,"spicy":0,"ingredients":"銀鱈魚2塊,白味噌,味醂,清酒,糖","steps":"1. 味噌+味醂+清酒+糖混合成醃料\n2. 銀鱈魚用醃料醃至少2小時（最好過夜）\n3. 抹走表面多餘味噌\n4. 焗爐200°C焗10-12分鐘\n5. 表面微焦即可","tips":"味噌醃過夜更入味，但焗前要抹走否則會燶"},
        {"name":"牛油果三文魚卷","cuisine":"日式","method":"炒","taste":"清淡","nutrition":"魚,澱粉質","time":30,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"壽司飯,紫菜,三文魚刺身,牛油果,青瓜,壽司醋","steps":"1. 壽司飯加壽司醋拌勻放涼\n2. 紫菜放竹簾上\n3. 鋪飯，留邊\n4. 放三文魚、牛油果、青瓜條\n5. 捲緊切件","tips":"刀沾水先切，切完抹乾淨再切下一刀"},
        {"name":"烏冬湯麵","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"澱粉質,蛋白質","time":20,"early":0,"has_soup":1,"spicy":0,"ingredients":"烏冬麵2包,日式高湯,醬油,味醂,蔥花,天婦羅碎,魚板","steps":"1. 高湯+醬油+味醂煮成湯底\n2. 烏冬麵按包裝時間煮熟\n3. 麵放入碗，注入熱湯\n4. 放上魚板、天婦羅碎、蔥花","tips":"烏冬唔好煮太耐，保持彈牙口感"},
        {"name":"日式炸雞","cuisine":"日式","method":"炸","taste":"濃味","nutrition":"白肉,蛋白質","time":35,"early":1,"spicy":0,"ingredients":"雞腿肉300g,醬油,味醂,清酒,薑汁,蒜蓉,片栗粉","steps":"1. 雞肉切件，用醬油+味醂+清酒+薑汁+蒜蓉醃30分鐘\n2. 瀝乾醃料\n3. 沾上片栗粉\n4. 170°C炸第一次至熟（約5分鐘）\n5. 撈起，油溫升至190°C翻炸30秒至脆\n6. 配檸檬、蛋黃醬","tips":"炸兩次先做到日式炸雞嘅酥脆口感"},
        {"name":"茶碗蒸","cuisine":"日式","method":"蒸","taste":"清淡","nutrition":"蛋白質,白肉","time":25,"early":1,"spicy":0,"ingredients":"雞蛋2隻,高湯,蝦仁,雞肉粒,冬菇,銀杏,味醂,醬油","steps":"1. 蛋液+高湯+味醂+醬油拌勻（蛋液:高湯=1:3）\n2. 過篩去氣泡\n3. 碗底放蝦仁、雞肉、冬菇\n4. 倒入蛋液\n5. 用中火蒸12-15分鐘（蓋上保鮮紙）\n6. 放上銀杏裝飾","tips":"蒸時鑊蓋用筷子隔開少少，防止倒汗水滴落"},
        {"name":"蕎麥麵","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"澱粉質","time":15,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"蕎麥麵200g,日式沾麵汁,蔥花,芥末,紫菜絲","steps":"1. 蕎麥麵按包裝煮熟\n2. 用凍水沖洗至完全冷卻\n3. 瀝乾水份\n4. 沾麵汁稀釋\n5. 麵放在竹簾上\n6. 配蔥花、芥末、紫菜絲\n7. 食時夾起麵沾汁","tips":"蕎麥麵要過冷河先爽口彈牙"},
        {"name":"牛丼","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"紅肉,澱粉質","time":15,"early":0,"spicy":0,"ingredients":"牛肉薄片150g,洋蔥,白飯,醬油,味醂,清酒,高湯,紅薑","steps":"1. 醬油+味醂+清酒+高湯煮成醬汁\n2. 加入洋蔥絲煮軟\n3. 加入牛肉片煮熟\n4. 淋在白飯上\n5. 配紅薑","tips":"牛肉最後落，變色即熟，唔好煮老"},
        {"name":"鹽燒鯖魚","cuisine":"日式","method":"焗","taste":"清淡","nutrition":"魚,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"鯖魚1條,鹽,檸檬,蘿蔔蓉","steps":"1. 鯖魚內外抹鹽，醃10分鐘\n2. 預熱焗爐200°C或grill\n3. 鯖魚放在烤架上\n4. 焗10-12分鐘至皮脆\n5. 配檸檬、蘿蔔蓉","tips":"用grill mode皮會更脆"},
        {"name":"南瓜煮","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"菜","time":20,"early":1,"spicy":0,"ingredients":"南瓜300g,高湯,醬油,味醂,糖","steps":"1. 南瓜去籽切塊\n2. 高湯+醬油+味醂+糖煮成煮汁\n3. 南瓜皮向下排好\n4. 注入煮汁（約蓋過一半）\n5. 蓋上蓋小火煮至南瓜軟\n6. 熄火後浸10分鐘入味","tips":"南瓜皮向下煮可以保持形狀"},
        {"name":"玉子燒","cuisine":"日式","method":"煎","taste":"清淡","nutrition":"蛋白質","time":15,"early":0,"spicy":0,"ingredients":"雞蛋3隻,高湯,醬油,味醂,糖,油","steps":"1. 蛋液+高湯+醬油+味醂+糖拌勻\n2. 玉子燒鑊掃油加熱\n3. 倒入薄薄一層蛋液\n4. 半熟時由前向後捲\n5. 再掃油，重複步驟3-4\n6. 完成後用竹簾定型\n7. 切件上碟","tips":"全程小火，捲時用筷子同鑊鏟配合"},
        {"name":"日式溏心蛋","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"蛋白質","time":15,"early":1,"spicy":0,"ingredients":"雞蛋4隻,醬油,味醂,清酒,糖,水","steps":"1. 雞蛋室溫回溫\n2. 水滾後放入雞蛋，煮6.5分鐘\n3. 立即放入冰水降溫\n4. 去殼\n5. 醬油+味醂+清酒+糖+水煮溶放涼\n6. 浸蛋過夜","tips":"準確計時6.5分鐘做溏心效果"},
        {"name":"炒烏冬","cuisine":"日式","method":"炒","taste":"濃味","nutrition":"澱粉質,菜","time":15,"early":0,"spicy":0,"ingredients":"烏冬2包,椰菜絲,甘筍絲,豬肉片,炒麵醬汁,木魚碎","steps":"1. 烏冬用熱水沖散\n2. 熱油炒豬肉片至變色\n3. 加入椰菜絲、甘筍絲\n4. 加入烏冬\n5. 加炒麵醬汁大火快炒\n6. 灑木魚碎、紫菜粉","tips":"烏冬用熱水沖散就可以，唔使煮"},
        {"name":"角煮（日式滷肉）","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"紅肉,蛋白質","time":90,"early":1,"spicy":0,"ingredients":"五花腩500g,醬油,味醂,清酒,糖,薑片,蔥段,雞蛋","steps":"1. 五花腩汆水切厚件\n2. 熱鑊煎香五花腩\n3. 加入醬油、味醂、清酒、糖、薑蔥\n4. 加水蓋過肉，大火煮滾轉小火\n5. 炆1-1.5小時至軟腍\n6. 加入烚蛋一起炆30分鐘","tips":"炆好後隔夜更入味"},
        {"name":"味噌漬豆腐","cuisine":"日式","method":"炒","taste":"清淡","nutrition":"蛋白質,菜","time":10,"early":1,"has_cold_dish":1,"spicy":0,"ingredients":"硬豆腐1盒,白味噌,味醂,芝麻,蔥花","steps":"1. 豆腐用重物壓住去水30分鐘\n2. 味噌+味醂混合成漬醬\n3. 豆腐抹乾\n4. 均勻塗上漬醬\n5. 用保鮮紙包好冷藏4小時以上\n6. 切片灑芝麻蔥花","tips":"漬得越耐越入味，可以早一晚準備"},
        {"name":"照燒三文魚","cuisine":"日式","method":"煎","taste":"濃味","nutrition":"魚,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"三文魚柳2塊,照燒汁(醬油+味醂+清酒+糖),白芝麻,檸檬","steps":"1. 三文魚抹乾，灑鹽\n2. 中小火煎三文魚每面3-4分鐘\n3. 加入照燒汁\n4. 煮至醬汁濃稠包裹魚柳\n5. 灑白芝麻，配檸檬","tips":"照燒汁要最後收汁先會亮面"},
        {"name":"日式芝士蛋糕","cuisine":"日式","method":"焗","taste":"清淡","nutrition":"澱粉質,蛋白質","time":60,"early":1,"spicy":0,"ingredients":"忌廉芝士250g,糖80g,雞蛋3隻,淡忌廉200ml,低筋麵粉50g,檸檬汁","steps":"1. 忌廉芝士室溫軟化+糖打至順滑\n2. 分次加入蛋黃、淡忌廉、檸檬汁\n3. 篩入麵粉拌勻\n4. 蛋白打至濕性發泡\n5. 分次混合蛋白霜\n6. 水浴法160°C焗40-50分鐘","tips":"焗好後讓蛋糕在焗爐內慢慢冷卻防縮"},
    ]
    
    # ===== SOUTHEAST ASIAN (東南亞) - 25 recipes =====
    se_asian = [
        {"name":"冬蔭功湯","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,蛋白質","time":25,"early":0,"has_soup":1,"spicy":1,"ingredients":"蝦200g,草菇,冬蔭功醬,香茅,南薑,檸檬葉,椰奶,魚露,青檸汁,辣椒","steps":"1. 香茅拍扁，南薑切片\n2. 水煮滾加入香茅南薑檸檬葉煮5分鐘\n3. 加入冬蔭功醬、草菇\n4. 加入蝦煮熟\n5. 加魚露、青檸汁調味\n6. 最後加入椰奶攪拌","tips":"椰奶最後落，煮太耐會分層"},
        {"name":"海南雞飯","cuisine":"東南亞","method":"炆","taste":"清淡","nutrition":"白肉,澱粉質","time":60,"early":1,"spicy":0,"ingredients":"雞1隻,米,雞湯,薑,蒜頭,班蘭葉,薑蓉蘸料,辣椒蘸料,黑醬油","steps":"1. 雞用鹽抹勻全身，浸入滾水加薑蔥\n2. 轉小火，水微滾浸雞30分鐘\n3. 取出浸冰水定皮\n4. 雞油炒香薑蓉蒜蓉，加入生米炒香\n5. 加雞湯、班蘭葉煮成油飯\n6. 雞斬件，配三色蘸醬","tips":"浸雞而唔係滾雞，肉先嫩滑"},
        {"name":"肉骨茶","cuisine":"東南亞","method":"炆","taste":"濃味","nutrition":"紅肉,蛋白質","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"排骨500g,肉骨茶藥材包,蒜頭,冬菇,生抽,老抽,蠔油","steps":"1. 排骨汆水去血沫\n2. 水煮滾，加入肉骨茶藥材包、蒜頭\n3. 加排骨大火煮滾轉小火\n4. 炆1小時至排骨軟腍\n5. 加入冬菇、生抽老抽蠔油調味\n6. 再炆15分鐘","tips":"配油炸鬼、白飯一齊食最正宗"},
        {"name":"泰式炒金邊粉","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,白肉","time":20,"early":0,"spicy":1,"ingredients":"金邊粉200g,蝦仁,豆腐乾,芽菜,韭菜,雞蛋,羅望子醬,魚露,糖,花生碎,青檸","steps":"1. 金邊粉浸軟瀝乾\n2. 羅望子醬+魚露+糖調成醬汁\n3. 熱油炒蝦仁、豆腐乾\n4. 打入雞蛋炒散\n5. 加入金邊粉、醬汁大火快炒\n6. 加入芽菜、韭菜兜勻\n7. 灑花生碎，配青檸","tips":"金邊粉唔好浸太耐，保持Q彈"},
        {"name":"越南春卷","cuisine":"東南亞","method":"炸","taste":"清淡","nutrition":"白肉,菜","time":30,"early":1,"spicy":0,"ingredients":"春卷皮,豬肉碎,蝦仁,粉絲,木耳,甘筍絲,生菜,魚露蘸汁","steps":"1. 粉絲、木耳浸軟切碎\n2. 豬肉碎+蝦仁+粉絲+木耳+甘筍拌勻\n3. 春卷皮包入餡料\n4. 170°C油炸至金黃\n5. 配生菜包住食，沾魚露汁","tips":"春卷皮要包實但唔好太緊，炸時會膨脹"},
        {"name":"叻沙","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,澱粉質","time":35,"early":0,"has_soup":1,"spicy":1,"ingredients":"叻沙醬,米粉,蝦,魚蛋,豆腐卜,芽菜,椰奶,雞湯,青檸","steps":"1. 叻沙醬用油炒香\n2. 加入雞湯、椰奶煮滾\n3. 加入豆腐卜煮5分鐘\n4. 加入蝦、魚蛋煮熟\n5. 米粉淥熟放碗底\n6. 倒入叻沙湯\n7. 放芽菜、青檸","tips":"叻沙醬要先炒香先出味"},
        {"name":"馬來西亞咖哩雞","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,澱粉質","time":50,"early":1,"spicy":1,"ingredients":"雞件500g,馬來咖哩粉,椰奶,薯仔,洋蔥,蒜頭,薑,香茅","steps":"1. 雞件用咖哩粉醃30分鐘\n2. 洋蔥蒜頭薑香茅爆香\n3. 加入雞件炒至變色\n4. 加入咖哩粉、水\n5. 煮滾後加薯仔\n6. 小火炆30分鐘\n7. 最後加椰奶煮滾","tips":"椰奶最後落保持香味"},
        {"name":"泰式青木瓜沙律","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"菜","time":15,"early":0,"has_cold_dish":1,"spicy":1,"ingredients":"青木瓜絲,車厘茄,花生碎,蝦米,蒜頭,辣椒,魚露,青檸汁,椰糖","steps":"1. 蒜頭、辣椒、蝦米用舂搗碎\n2. 加入椰糖、魚露、青檸汁調味\n3. 加入青木瓜絲、車厘茄輕輕舂勻\n4. 灑花生碎","tips":"青木瓜要即刨即食，保持爽脆"},
        {"name":"印尼炒飯","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,蛋白質","time":15,"early":0,"spicy":1,"ingredients":"白飯2碗,蝦仁,雞肉粒,雞蛋,甜醬油,辣椒醬,蒜蓉,蔥花,蝦片","steps":"1. 熱油炒香蒜蓉\n2. 加入蝦仁、雞肉炒熟\n3. 打入雞蛋炒散\n4. 加入白飯大火快炒\n5. 加甜醬油、辣椒醬調味\n6. 煎太陽蛋放面\n7. 配蝦片、青瓜片","tips":"要用隔夜飯炒先粒粒分明"},
        {"name":"沙嗲串燒","cuisine":"東南亞","method":"焗","taste":"濃味","nutrition":"白肉,蛋白質","time":40,"early":1,"spicy":0,"ingredients":"雞肉/豬肉300g,沙嗲醬,椰奶,黃薑粉,香茅,竹籤,花生蘸醬","steps":"1. 雞肉切件，用沙嗲醬+椰奶+黃薑粉醃過夜\n2. 竹籤浸水30分鐘防燒焦\n3. 串起肉件\n4. 焗爐200°C焗10分鐘，中途翻面\n5. 配花生蘸醬、青瓜、洋蔥","tips":"用炭火燒最香，焗爐用grill mode代替"},
        {"name":"泰式青咖哩","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,菜","time":30,"early":0,"spicy":1,"ingredients":"青咖哩醬,雞肉200g,椰奶,泰國茄子,青豆角,魚露,椰糖,羅勒葉","steps":"1. 椰奶煮至出油\n2. 加入青咖哩醬炒香\n3. 加入雞肉炒至變色\n4. 加入椰奶煮5分鐘\n5. 加入茄子、豆角煮熟\n6. 加魚露、椰糖調味\n7. 灑羅勒葉","tips":"椰奶要先煮出油再加咖哩醬先香"},
        {"name":"越式牛肉河粉","cuisine":"東南亞","method":"炆","taste":"清淡","nutrition":"紅肉,澱粉質","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"牛骨,牛肉薄片,河粉,洋蔥,薑,八角,桂皮,魚露,芽菜,青檸,辣椒,九層塔","steps":"1. 牛骨汆水，加洋蔥、薑（先烤香）、八角、桂皮煲湯2小時\n2. 牛肉薄片備用\n3. 河粉淥熟放碗\n4. 鋪上生牛肉片\n5. 淋上滾熱牛骨湯（湯要夠熱淥熟牛肉）\n6. 配芽菜、青檸、辣椒、九層塔","tips":"牛骨同洋蔥薑要先烤香湯先有深度"},
        {"name":"芒果糯米飯","cuisine":"東南亞","method":"蒸","taste":"清淡","nutrition":"澱粉質","time":40,"early":1,"spicy":0,"ingredients":"糯米200g,椰奶,糖,鹽,芒果2個,芝麻","steps":"1. 糯米浸過夜\n2. 隔水蒸糯米25-30分鐘至熟\n3. 椰奶+糖+鹽煮熱\n4. 蒸好糯米趁熱拌入椰奶\n5. 芒果切片\n6. 糯米飯配芒果片\n7. 淋椰奶醬，灑芝麻","tips":"糯米要浸夠時間，蒸出嚟先軟糯"},
        {"name":"泰式鹽焗魚","cuisine":"東南亞","method":"焗","taste":"清淡","nutrition":"魚,蛋白質","time":40,"early":0,"spicy":0,"ingredients":"鱸魚1條,粗鹽,香茅,檸檬葉,南薑,檸檬,蘸醬","steps":"1. 魚洗淨，塞入香茅、檸檬葉、南薑\n2. 粗鹽加蛋白拌勻\n3. 鹽鋪在魚上完全覆蓋\n4. 焗爐200°C焗25-30分鐘\n5. 敲開鹽殼\n6. 配泰式海鮮蘸醬","tips":"鹽殼可以鎖住魚汁，魚肉特別嫩"},
        {"name":"星洲炒米","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,白肉","time":20,"early":0,"spicy":1,"ingredients":"米粉200g,叉燒絲,蝦仁,雞蛋,芽菜,咖哩粉,洋蔥絲,青椒絲","steps":"1. 米粉浸軟瀝乾\n2. 熱油炒香洋蔥、青椒\n3. 加入叉燒、蝦仁\n4. 加入咖哩粉炒香\n5. 加入米粉大火快炒\n6. 加入芽菜兜勻","tips":"咖哩粉要先炒先出味，唔好最後落"},
        {"name":"印尼燒雞","cuisine":"東南亞","method":"焗","taste":"濃味","nutrition":"白肉,蛋白質","time":60,"early":1,"spicy":0,"ingredients":"全雞1隻,印尼甜醬油,蒜蓉,紅蔥頭,薑黃,香茅,椰奶","steps":"1. 蒜蓉紅蔥頭薑黃香茅打成醬\n2. 加入甜醬油、椰奶\n3. 雞塗抹醃料，醃過夜\n4. 焗爐180°C焗45-60分鐘\n5. 中途掃上剩餘醃料","tips":"印尼甜醬油(kecap manis)係靈魂，唔好用普通醬油代替"},
        {"name":"泰式豬頸肉","cuisine":"東南亞","method":"焗","taste":"濃味","nutrition":"紅肉,蛋白質","time":35,"early":1,"spicy":0,"ingredients":"豬頸肉300g,蠔油,生抽,蜜糖,蒜蓉,胡椒粉,蘸醬(魚露+青檸+辣椒+糖)","steps":"1. 豬頸肉用蠔油+生抽+蜜糖+蒜蓉醃至少2小時\n2. 焗爐200°C焗15分鐘\n3. 掃上蜜糖\n4. 再焗5-10分鐘至表面焦香\n5. 切片\n6. 配泰式蘸醬","tips":"掃蜜糖係做出焦香表面嘅關鍵"},
        {"name":"越式米紙卷","cuisine":"東南亞","method":"炒","taste":"清淡","nutrition":"菜,白肉","time":20,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"米紙,蝦,米粉,生菜,薄荷葉,青瓜絲,花生蘸醬","steps":"1. 蝦煮熟切半\n2. 米粉淥熟\n3. 米紙用溫水浸軟\n4. 鋪上生菜、米粉、蝦、青瓜絲、薄荷葉\n5. 捲緊，兩邊摺入\n6. 配花生蘸醬","tips":"米紙浸水2-3秒就夠，太軟會爛"},
        {"name":"泰式香葉包雞","cuisine":"東南亞","method":"焗","taste":"濃味","nutrition":"白肉,蛋白質","time":40,"early":1,"spicy":0,"ingredients":"雞腿肉300g,班蘭葉,蠔油,生抽,蒜蓉,胡椒粉,麻油","steps":"1. 雞肉切件，用蠔油+生抽+蒜蓉+麻油醃30分鐘\n2. 班蘭葉洗淨\n3. 用班蘭葉包裹雞件\n4. 焗爐180°C焗15-20分鐘\n5. 配甜辣醬","tips":"包雞時班蘭葉紋路向外，焗出嚟有紋理"},
        {"name":"福建蝦麵","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,白肉","time":30,"early":0,"spicy":1,"ingredients":"油麵+米粉,蝦,豬肉片,芽菜,雞蛋,蝦頭高湯,辣椒醬,蒜蓉","steps":"1. 蝦頭炒出蝦油，加水煮成高湯\n2. 熱油爆香蒜蓉\n3. 加入蝦、豬肉片炒熟\n4. 加入麵條、辣椒醬\n5. 注入蝦頭高湯\n6. 大火快炒至收汁\n7. 加入芽菜、雞蛋","tips":"蝦頭高湯係精髓，唔好慳"},
        {"name":"泰式炒茄子","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"菜","time":15,"early":0,"spicy":1,"ingredients":"泰國茄子(小圓茄)200g,蒜蓉,辣椒,泰式羅勒葉,魚露,生抽,糖","steps":"1. 泰國茄子切半\n2. 熱油爆香蒜蓉辣椒\n3. 加入茄子大火快炒\n4. 加魚露、生抽、糖調味\n5. 加少少水焗2分鐘\n6. 灑泰式羅勒葉","tips":"用泰國茄子口感特別好，普通茄子亦可"},
        {"name":"巴東牛肉","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"紅肉,蛋白質","time":120,"early":1,"spicy":1,"ingredients":"牛肉500g,椰奶,巴東醬(辣椒乾+香茅+南薑+黃薑+蒜頭+紅蔥頭),椰絲","steps":"1. 巴東醬材料打成醬\n2. 牛肉切大件\n3. 巴東醬用油小火炒香（約10分鐘）\n4. 加入牛肉、椰奶\n5. 小火炆1.5-2小時至牛肉軟腍\n6. 醬汁煮至濃稠近乎乾身\n7. 灑上烘香椰絲","tips":"巴東牛肉要炆到醬汁收乾先正宗"},
        {"name":"泰式椰汁雞湯","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,菜","time":25,"early":0,"has_soup":1,"spicy":1,"ingredients":"雞肉200g,椰奶,雞湯,香茅,南薑,檸檬葉,辣椒,魚露,青檸汁,草菇","steps":"1. 椰奶煮至出油\n2. 加入香茅、南薑、檸檬葉、辣椒煮5分鐘\n3. 加入雞湯、雞肉\n4. 加入草菇煮熟\n5. 加魚露、青檸汁調味","tips":"Tom Kha Gai要酸辣椰香平衡"},
        {"name":"越南咖啡布丁","cuisine":"東南亞","method":"蒸","taste":"濃味","nutrition":"澱粉質","time":20,"early":1,"spicy":0,"ingredients":"越南咖啡粉,煉奶,魚膠粉/寒天粉,糖,水","steps":"1. 越南咖啡用滴漏壺沖出濃縮咖啡\n2. 寒天粉+水+糖煮溶\n3. 混合咖啡液及煉奶\n4. 倒入模具\n5. 冷藏至凝固","tips":"用越南滴漏壺先沖到正宗越南咖啡味"},
        {"name":"馬來西亞炒粿條","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,白肉","time":15,"early":0,"spicy":1,"ingredients":"粿條300g,蝦仁,臘腸片,芽菜,韭菜,雞蛋,蒜蓉,辣椒醬,甜醬油,魚露","steps":"1. 粿條分開\n2. 大火熱油爆香蒜蓉\n3. 加入蝦仁、臘腸片\n4. 打入雞蛋炒散\n5. 加入粿條大火快炒\n6. 加辣椒醬、甜醬油、魚露\n7. 加入芽菜、韭菜兜勻","tips":"鑊要夠熱，大火快炒先有鑊氣"},
    ]
    
    all_recipes = chinese + western + japanese + se_asian
    
    for r in all_recipes:
        c.execute('''
            INSERT INTO recipes (name, cuisine, cooking_method, taste, nutrition_tags, prep_time_min, can_prep_early, has_soup, has_cold_dish, is_spicy, ingredients, steps, tips, source, servings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed', 4)
        ''', (
            r['name'],
            r['cuisine'],
            r['method'],
            r['taste'],
            r['nutrition'],
            r['time'],
            r.get('early', 0),
            r.get('has_soup', 0),
            r.get('has_cold_dish', 0),
            r.get('spicy', 0),
            r['ingredients'],
            r['steps'],
            r.get('tips', '')
        ))
