"""
Cooking Ideas - SQLite Models
Recipe database with seed data (住家菜)
"""

import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), 'recipes.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

DB_VERSION = 11

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Check DB version and force re-init if schema changed
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='db_version'")
    has_version = c.fetchone()
    need_reinit = False
    if has_version:
        c.execute('SELECT version FROM db_version')
        row = c.fetchone()
        if row and row[0] < DB_VERSION:
            c.execute('DROP TABLE IF EXISTS recipes')
            c.execute('DROP TABLE IF EXISTS custom_dishes')
            c.execute('DROP TABLE IF EXISTS bookmarks')
            # Note: user_recipes is NEVER dropped — it contains user data
            need_reinit = True
    else:
        # Check if tables exist but no version table (old DB)
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='recipes'")
        if c.fetchone():
            c.execute('DROP TABLE IF EXISTS recipes')
            c.execute('DROP TABLE IF EXISTS custom_dishes')
            c.execute('DROP TABLE IF EXISTS bookmarks')
            need_reinit = True
    
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
            kid_friendly INTEGER DEFAULT 0,
            ingredients TEXT NOT NULL,
            steps TEXT NOT NULL,
            tips TEXT DEFAULT '',
            source TEXT DEFAULT 'seed',
            servings INTEGER DEFAULT 4,
            image_base64 TEXT DEFAULT '',
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
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (recipe_id) REFERENCES recipes(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cuisine TEXT DEFAULT '中式',
            cooking_method TEXT DEFAULT '炒',
            taste TEXT DEFAULT '清淡',
            nutrition_tags TEXT DEFAULT '',
            prep_time_min INTEGER DEFAULT 30,
            ingredients TEXT DEFAULT '',
            steps TEXT DEFAULT '',
            tips TEXT DEFAULT '',
            servings INTEGER DEFAULT 4,
            creator TEXT DEFAULT '',
            image_base64 TEXT DEFAULT '',
            is_spicy INTEGER DEFAULT 0,
            can_prep_early INTEGER DEFAULT 0,
            kid_friendly INTEGER DEFAULT 1,
            db_recipe_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER
        )
    ''')
    
    # Migration: add kid_friendly column if missing (DB v7 → v8)
    try:
        c.execute('SELECT kid_friendly FROM recipes LIMIT 0')
    except:
        c.execute('ALTER TABLE recipes ADD COLUMN kid_friendly INTEGER DEFAULT 0')
    try:
        c.execute('SELECT kid_friendly FROM user_recipes LIMIT 0')
    except:
        c.execute('ALTER TABLE user_recipes ADD COLUMN kid_friendly INTEGER DEFAULT 1')
    
    c.execute('SELECT COUNT(*) FROM recipes')
    count = c.fetchone()[0]
    
    if count == 0 or need_reinit:
        _seed_recipes(c)
        c.execute('DELETE FROM db_version')
        c.execute('INSERT INTO db_version (version) VALUES (?)', (DB_VERSION,))
    
    # Insert any extra recipes that don't exist yet (fill criteria gaps)
    _insert_extra_recipes(c)
    
    # Flag kid-friendly: non-spicy + no alcohol in ingredients or steps
    ALCOHOL_KW = ['%酒%', '%味醂%', '%紹興%', '%料酒%', '%清酒%', '%花雕%', '%米酒%', '%啤酒%']
    alc_cond = ' AND '.join(['(ingredients NOT LIKE ? AND steps NOT LIKE ?)'] * len(ALCOHOL_KW))
    alc_params = []
    for kw in ALCOHOL_KW:
        alc_params.extend([kw, kw])
    c.execute(f'UPDATE recipes SET kid_friendly = 1 WHERE is_spicy = 0 AND ({alc_cond})', alc_params)
    c.execute(f'UPDATE recipes SET kid_friendly = 0 WHERE is_spicy = 1 OR NOT ({alc_cond})', alc_params)
    
    conn.commit()
    conn.close()

def _insert_extra_recipes(c):
    """Insert additional recipes that fill criteria gaps (only if name not already in DB)."""
    for r in _build_extra_recipes():
        c.execute('SELECT id FROM recipes WHERE name = ?', [r['name']])
        if not c.fetchone():
            c.execute('''
                INSERT INTO recipes (name, cuisine, cooking_method, taste, nutrition_tags, prep_time_min, can_prep_early, has_soup, has_cold_dish, is_spicy, ingredients, steps, tips, source, servings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed', 4)
            ''', (
                r['name'], r['cuisine'], r['method'], r['taste'], r['nutrition'],
                r['time'], r.get('early', 0), r.get('has_soup', 0),
                r.get('has_cold_dish', 0), r.get('spicy', 0),
                r['ingredients'], r['steps'], r.get('tips', '')
            ))

def _seed_recipes(c):
    """Seed 100 住家菜 across 4 cuisines."""
    recipes = _build_recipe_list()
    for r in recipes:
        c.execute('''
            INSERT INTO recipes (name, cuisine, cooking_method, taste, nutrition_tags, prep_time_min, can_prep_early, has_soup, has_cold_dish, is_spicy, ingredients, steps, tips, source, servings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed', 4)
        ''', (
            r['name'], r['cuisine'], r['method'], r['taste'], r['nutrition'],
            r['time'], r.get('early', 0), r.get('has_soup', 0),
            r.get('has_cold_dish', 0), r.get('spicy', 0),
            r['ingredients'], r['steps'], r.get('tips', '')
        ))

def _build_recipe_list():
    """Return list of 100 住家菜 recipe dicts."""
    recipes = []
    
    # ===== 中式住家菜 (25) =====
    recipes += [
        {"name":"番茄炒蛋","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜,蛋白質","time":10,"early":0,"spicy":0,"ingredients":"番茄2個,雞蛋3隻,蔥花,鹽,糖,油","steps":"1. 番茄切塊，雞蛋打散加鹽\n2. 熱油先炒蛋至七成熟，撈起\n3. 原鑊炒番茄至出汁，加少少糖\n4. 加回炒蛋兜勻\n5. 灑蔥花上碟","tips":"番茄加少少糖可以平衡酸味"},
        {"name":"蒸水蛋","cuisine":"中式","method":"蒸","taste":"清淡","nutrition":"蛋白質","time":12,"early":0,"spicy":0,"ingredients":"雞蛋3隻,溫水(蛋液1.5倍),鹽,生抽,蔥花,麻油","steps":"1. 雞蛋打散，加鹽同溫水拌勻\n2. 過篩倒入淺碟，撇去泡泡\n3. 蓋上保鮮紙，中火蒸8-10分鐘\n4. 淋上生抽、麻油\n5. 灑蔥花即成","tips":"用溫水蒸出嚟先滑，凍水會起蜂巢"},
        {"name":"梅菜蒸肉餅","cuisine":"中式","method":"蒸","taste":"濃味","nutrition":"紅肉,蛋白質","time":20,"early":1,"spicy":0,"ingredients":"豬肉碎250g,甜梅菜80g,生抽,生粉,糖,麻油","steps":"1. 梅菜浸水15分鐘去鹹味，切碎\n2. 梅菜加少少糖拌勻\n3. 豬肉碎加生抽、生粉、麻油拌勻\n4. 加入梅菜碎混合\n5. 平鋪碟上，大火蒸12-15分鐘","tips":"豬肉最好半肥瘦，蒸出嚟先唔會乾"},
        {"name":"薯仔燜雞翼","cuisine":"中式","method":"炆","taste":"濃味","nutrition":"白肉,澱粉質","time":35,"early":1,"spicy":0,"ingredients":"雞翼10隻,薯仔2個,薑片,生抽,老抽,冰糖,水","steps":"1. 雞翼汆水，薯仔去皮切塊\n2. 熱油爆香薑片\n3. 落雞翼煎至兩面金黃\n4. 加入薯仔、生抽、老抽、冰糖\n5. 加水蓋過材料，大火煮滾轉小火炆20分鐘\n6. 收汁至濃稠","tips":"小朋友最鍾意，可以撈多兩碗飯"},
        {"name":"蠔油西蘭花炒牛肉","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"紅肉,菜","time":15,"early":0,"spicy":0,"ingredients":"西蘭花1個,牛肉片150g,蒜蓉,蠔油,生抽,生粉","steps":"1. 牛肉用生抽、生粉醃15分鐘\n2. 西蘭花切小朵，汆水1分鐘\n3. 熱油爆香蒜蓉，炒牛肉至七成熟\n4. 加入西蘭花兜炒\n5. 加蠔油調味快炒兜勻","tips":"西蘭花汆水可以保持翠綠"},
        {"name":"腐乳炒通菜","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"菜","time":8,"early":0,"spicy":0,"ingredients":"通菜300g,腐乳3磚,蒜蓉,糖,油","steps":"1. 通菜洗淨摘段\n2. 腐乳壓爛加少少糖拌勻\n3. 熱油大火爆香蒜蓉\n4. 落通菜大火快炒\n5. 加入腐乳醬快炒兜勻\n6. 即上碟","tips":"通菜要大火快炒，炒耐咗會出水變黑"},
        {"name":"豆豉蒸排骨","cuisine":"中式","method":"蒸","taste":"濃味","nutrition":"紅肉,蛋白質","time":20,"early":1,"spicy":0,"ingredients":"排骨300g,豆豉1湯匙,蒜蓉,薑絲,生抽,生粉,油","steps":"1. 排骨洗淨瀝乾\n2. 豆豉沖洗後壓爛\n3. 排骨加豆豉、蒜蓉、薑絲、生抽、生粉、油拌勻\n4. 醃15分鐘\n5. 平鋪碟上，大火蒸12-15分鐘","tips":"排骨要瀝乾水先醃，唔係會出水"},
        {"name":"洋蔥豬扒","cuisine":"中式","method":"煎","taste":"濃味","nutrition":"紅肉,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"豬扒2塊,洋蔥1個,生抽,蠔油,糖,生粉,黑胡椒","steps":"1. 豬扒用刀背拍鬆，生抽+生粉醃15分鐘\n2. 洋蔥切絲\n3. 熱油中火煎豬扒每面3-4分鐘至金黃熟透，撈起\n4. 原鑊炒香洋蔥絲至軟身\n5. 加蠔油、糖、黑胡椒、少少水煮成汁\n6. 淋在豬扒上","tips":"豬扒拍鬆先醃，煎出嚟唔會捲起"},
        {"name":"節瓜粉絲蝦米煲","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,澱粉質","time":25,"early":0,"spicy":0,"ingredients":"節瓜1個,粉絲1把,蝦米,薑片,雞湯,蠔油","steps":"1. 粉絲浸軟，蝦米浸軟，節瓜去皮切條\n2. 熱油爆香薑片、蝦米\n3. 加入節瓜炒香\n4. 加雞湯、蠔油煮滾\n5. 轉小火炆10分鐘至節瓜軟\n6. 加入粉絲煮2分鐘收汁","tips":"節瓜炆到透明就最入味"},
        {"name":"清蒸鯇魚腩","cuisine":"中式","method":"蒸","taste":"清淡","nutrition":"魚,蛋白質","time":12,"early":0,"spicy":0,"ingredients":"鯇魚腩1塊,薑絲,蔥絲,蒸魚豉油,油","steps":"1. 鯇魚腩洗淨抹乾，魚身𠝹兩刀\n2. 鋪上薑絲\n3. 水滾落鑊大火蒸8-10分鐘\n4. 倒去蒸魚水\n5. 鋪上新鮮蔥絲\n6. 淋上蒸魚豉油，熱油澆面","tips":"蒸魚水一定要倒走，唔係會腥"},
        {"name":"沙薑雞翼","cuisine":"中式","method":"炆","taste":"濃味","nutrition":"白肉,蛋白質","time":25,"early":1,"spicy":0,"ingredients":"雞翼10隻,沙薑粉,鹽,麻油,薑片","steps":"1. 雞翼汆水備用\n2. 水煮滾加薑片\n3. 加入雞翼煮10分鐘至熟\n4. 撈起瀝乾\n5. 沙薑粉+鹽+麻油拌勻\n6. 趁熱撈勻雞翼\n7. 放涼後食更入味","tips":"沙薑粉要趁雞翼熱時撈先上味"},
        {"name":"西芹炒雞柳","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"白肉,菜","time":15,"early":0,"spicy":0,"ingredients":"雞胸肉150g,西芹250g,甘筍片,蒜蓉,鹽,生抽,生粉","steps":"1. 雞胸肉切條，用生抽+生粉醃10分鐘\n2. 西芹去絲切段，甘筍切片\n3. 西芹、甘筍汆水備用\n4. 熱油爆香蒜蓉，炒雞柳至變色\n5. 加入西芹甘筍快炒\n6. 加鹽調味兜勻","tips":"西芹去絲口感先爽脆"},
        {"name":"粟米肉粒","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"紅肉,澱粉質","time":15,"early":0,"spicy":0,"ingredients":"豬肉粒150g,粟米蓉1罐,雞蛋1隻,蔥花,鹽,生粉水","steps":"1. 豬肉粒用生抽+生粉醃10分鐘\n2. 熱油炒豬肉粒至熟\n3. 加入粟米蓉煮滾\n4. 加鹽調味\n5. 勾薄芡\n6. 熄火倒入蛋液攪成蛋花\n7. 灑蔥花","tips":"小朋友撈飯一流，簡單快靚正"},
        {"name":"瑞士雞翼","cuisine":"中式","method":"炆","taste":"濃味","nutrition":"白肉,蛋白質","time":30,"early":1,"spicy":0,"ingredients":"雞翼12隻,瑞士汁(生抽+老抽+冰糖+八角+桂皮+水),薑片","steps":"1. 雞翼汆水去血水\n2. 瑞士汁材料煮滾成滷汁\n3. 加入雞翼、薑片\n4. 小火浸煮15-20分鐘\n5. 熄火再浸10分鐘入味\n6. 上碟","tips":"滷汁留起可以重用，越滷越香"},
        {"name":"菜脯炒蛋","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"蛋白質,菜","time":10,"early":0,"spicy":0,"ingredients":"雞蛋4隻,菜脯50g,蔥花,油","steps":"1. 菜脯浸水10分鐘去鹹味，切粒\n2. 白鑊烘香菜脯粒\n3. 雞蛋打散，加入菜脯粒、蔥花\n4. 熱油倒入蛋液\n5. 中小火煎至兩面金黃\n6. 切件上碟","tips":"菜脯要烘香先落蛋，香味出晒嚟"},
        {"name":"榨菜蒸牛肉","cuisine":"中式","method":"蒸","taste":"濃味","nutrition":"紅肉,蛋白質","time":15,"early":1,"spicy":0,"ingredients":"牛肉片200g,榨菜絲80g,薑絲,生抽,生粉,糖,油","steps":"1. 牛肉片用生抽、生粉、糖拌勻\n2. 榨菜絲浸水5分鐘去鹹\n3. 牛肉+榨菜+薑絲拌勻\n4. 平鋪碟上\n5. 大火蒸8-10分鐘\n6. 淋少少熟油","tips":"牛肉唔好蒸太耐，否則會韌"},
        {"name":"蕃茄薯仔魚湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"魚,菜","time":40,"early":0,"has_soup":1,"spicy":0,"ingredients":"紅衫魚/鯇魚尾2條,番茄3個,薯仔2個,薑片,鹽","steps":"1. 魚洗淨抹乾，番茄薯仔切塊\n2. 熱油煎魚至兩面金黃\n3. 加入滾水、薑片，大火滾10分鐘至奶白色\n4. 加入番茄薯仔\n5. 轉中小火煲20分鐘\n6. 加鹽調味","tips":"魚一定要煎香同加滾水，湯先奶白"},
        {"name":"蒜蓉炒菜心","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":8,"early":0,"spicy":0,"ingredients":"菜心300g,蒜蓉,鹽,油","steps":"1. 菜心洗淨，摘走老葉\n2. 熱油爆香蒜蓉\n3. 落菜心大火快炒\n4. 加少少水焗1分鐘\n5. 落鹽調味上碟","tips":"炒菜要夠鑊氣，全程大火"},
        {"name":"麻婆豆腐","cuisine":"中式","method":"炒","taste":"辣","nutrition":"白肉,蛋白質","time":15,"early":0,"spicy":1,"ingredients":"豆腐1盒,豬肉碎100g,豆瓣醬,蒜蓉,蔥花,生抽,花椒粉,生粉水","steps":"1. 豆腐切方塊，汆水備用\n2. 熱油爆香蒜蓉、豆瓣醬\n3. 加入豬肉碎炒散\n4. 加水煮滾，放入豆腐輕輕拌勻\n5. 小火煮3分鐘，勾薄芡\n6. 灑花椒粉、蔥花","tips":"豆腐汆水可以定形，煮時唔會爛"},
        {"name":"粟米魚柳","cuisine":"中式","method":"煎","taste":"清淡","nutrition":"魚,澱粉質","time":20,"early":0,"spicy":0,"ingredients":"魚柳2塊,粟米蓉1罐,雞蛋1隻,麵粉,鹽,胡椒粉","steps":"1. 魚柳抹乾，灑鹽胡椒粉\n2. 沾上薄薄麵粉，再沾蛋液\n3. 熱油中火煎至兩面金黃熟透\n4. 粟米蓉加熱，淋在魚柳上","tips":"魚柳要完全解凍抹乾先煎到金黃"},
        {"name":"魚香茄子","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"菜,澱粉質","time":20,"early":0,"spicy":1,"ingredients":"茄子2條,豬肉碎100g,蒜蓉,豆瓣醬,蔥花,生抽,醋,糖","steps":"1. 茄子切條，用鹽水浸10分鐘防變黑\n2. 熱油煎茄子至軟身，撈起\n3. 爆香蒜蓉、豆瓣醬\n4. 加豬肉碎炒散\n5. 加入生抽、醋、糖\n6. 茄子回鑊快炒兜勻\n7. 灑蔥花","tips":"茄子先用鹽水浸可以防變黑同吸少啲油"},
        {"name":"涼瓜炒牛肉","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"紅肉,菜","time":20,"early":0,"spicy":0,"ingredients":"涼瓜1條,牛肉片150g,蒜蓉,豆豉,生抽,糖,生粉","steps":"1. 牛肉用生抽+生粉醃15分鐘\n2. 涼瓜去瓤切片，用鹽醃10分鐘擠出苦水\n3. 汆水1分鐘\n4. 熱油爆香蒜蓉豆豉\n5. 落牛肉炒至七成熟\n6. 加涼瓜快炒\n7. 加糖、生抽兜勻","tips":"涼瓜用鹽醃再汆水可以去大部份苦味"},
        {"name":"老少平安","cuisine":"中式","method":"蒸","taste":"清淡","nutrition":"白肉,蛋白質","time":20,"early":1,"spicy":0,"ingredients":"豆腐1盒,魚肉200g,雞蛋1隻,蔥花,生抽,麻油,胡椒粉","steps":"1. 豆腐壓爛，瀝走多餘水份\n2. 加入魚肉、雞蛋、胡椒粉拌勻\n3. 平鋪碟上，掃平表面\n4. 大火蒸12-15分鐘\n5. 淋上生抽、麻油\n6. 灑蔥花","tips":"豆腐要盡量瀝乾水，唔係蒸出嚟會出水"},
        {"name":"麵豉蒸排骨","cuisine":"中式","method":"蒸","taste":"濃味","nutrition":"紅肉,蛋白質","time":20,"early":1,"spicy":0,"ingredients":"排骨300g,麵豉醬1湯匙,蒜蓉,薑絲,生抽,生粉,糖,油","steps":"1. 排骨洗淨瀝乾\n2. 麵豉醬+生抽+糖+蒜蓉+薑絲+生粉+油拌勻\n3. 加入排骨拌勻醃15分鐘\n4. 平鋪碟上\n5. 大火蒸12-15分鐘","tips":"麵豉醬本身夠味，唔使落太多生抽"},
        {"name":"豉椒炒蜆","cuisine":"中式","method":"炒","taste":"辣","nutrition":"白肉,蛋白質","time":20,"early":0,"spicy":1,"ingredients":"蜆500g,豆豉,蒜蓉,辣椒,蔥段,生抽,蠔油","steps":"1. 蜆放入鹽水吐沙30分鐘\n2. 熱油爆香蒜蓉、豆豉、辣椒\n3. 落蜆大火快炒\n4. 加入生抽、蠔油調味\n5. 蜆殼打開即上碟，灑蔥段","tips":"蜆殼唔開嗰啲要揀走，唔好食"},
    ]
    
    # ===== 港式西餐住家菜 (25) =====
    recipes += [
        {"name":"番茄肉醬意粉","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"紅肉,澱粉質","time":40,"early":1,"spicy":0,"ingredients":"意粉200g,牛肉碎200g,洋蔥,甘筍,蒜蓉,番茄罐頭,香草,鹽,黑胡椒","steps":"1. 洋蔥、甘筍切碎粒\n2. 熱油炒香洋蔥蒜蓉\n3. 加入牛肉碎炒散\n4. 加入番茄罐頭、香草\n5. 小火炆20分鐘\n6. 意粉按包裝煮好\n7. 淋上肉醬","tips":"肉醬可以早一晚整定，更入味"},
        {"name":"白汁雞皇飯","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"白肉,澱粉質","time":30,"early":0,"spicy":0,"ingredients":"雞腿肉2塊,白飯,洋蔥,甘筍,忌廉蘑菇湯1罐,牛油","steps":"1. 雞肉切件，洋蔥甘筍切粒\n2. 牛油炒香洋蔥、甘筍\n3. 加入雞肉炒至變色\n4. 加入忌廉蘑菇湯同半罐水\n5. 煮滾轉小火煮15分鐘\n6. 淋在白飯上","tips":"用罐頭湯做底快靚正，港式茶餐廳做法"},
        {"name":"卡邦尼意粉","cuisine":"西式","method":"炒","taste":"濃味","nutrition":"澱粉質,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"意粉200g,煙肉粒100g,蛋黃2隻,巴馬臣芝士碎,黑胡椒","steps":"1. 意粉按包裝時間煮至al dente\n2. 煙肉粒乾煎至脆\n3. 蛋黃+芝士碎+黑胡椒拌勻\n4. 意粉撈起趁熱加入蛋黃芝士混合物拌勻\n5. 加入煙肉粒兜勻","tips":"唔好喺火上面落蛋，用餘溫拌勻先creamy"},
        {"name":"忌廉蘑菇湯","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"菜,蛋白質","time":25,"early":0,"has_soup":1,"spicy":0,"ingredients":"白蘑菇200g,洋蔥半個,牛油,麵粉2湯匙,雞湯300ml,牛奶200ml,淡忌廉","steps":"1. 蘑菇切片，洋蔥切碎\n2. 牛油炒香洋蔥、蘑菇至軟身\n3. 加入麵粉炒勻\n4. 逐少加入雞湯同牛奶攪拌\n5. 煮滾轉小火煮10分鐘\n6. 用手提攪拌機打滑（可留少少蘑菇粒）\n7. 加淡忌廉攪拌","tips":"麵粉一定要炒熟先落奶，唔係會有生粉味"},
        {"name":"南瓜湯","cuisine":"西式","method":"炆","taste":"清淡","nutrition":"菜","time":25,"early":1,"has_soup":1,"spicy":0,"ingredients":"南瓜500g,洋蔥半個,牛油,雞湯400ml,淡忌廉,鹽,黑胡椒","steps":"1. 南瓜去皮去籽切塊，洋蔥切碎\n2. 牛油炒香洋蔥至透明\n3. 加入南瓜、雞湯煮滾\n4. 小火煮15分鐘至南瓜腍\n5. 用手提攪拌機打至滑\n6. 加淡忌廉、鹽、黑胡椒調味","tips":"南瓜揀日本南瓜甜味最夠"},
        {"name":"焗豬扒飯","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"紅肉,澱粉質","time":50,"early":1,"spicy":0,"ingredients":"豬扒2塊,白飯2碗,雞蛋2隻,番茄,洋蔥,芝士碎,茄汁,鹽","steps":"1. 豬扒煎熟切條\n2. 雞蛋炒碎蛋炒飯做底，放入焗盤\n3. 鋪上豬扒條\n4. 洋蔥番茄炒香加茄汁煮成醬淋上面\n5. 灑大量芝士碎\n6. 200°C焗15-20分鐘至芝士金黃","tips":"炒飯底要炒得乾身，焗出嚟先唔會濕"},
        {"name":"芝士焗西蘭花","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"菜,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"西蘭花1個,芝士碎,牛油,麵粉,牛奶,鹽,黑胡椒","steps":"1. 西蘭花切小朵，汆水2分鐘瀝乾\n2. 牛油+麵粉炒成roux\n3. 逐少加牛奶攪拌成白醬\n4. 加鹽、黑胡椒調味\n5. 西蘭花放入焗盤，淋上白醬\n6. 灑芝士碎\n7. 200°C焗10-15分鐘至金黃","tips":"小朋友最鍾意，可以加煙肉碎更香"},
        {"name":"吞拿魚粟米沙律","cuisine":"西式","method":"炒","taste":"清淡","nutrition":"魚,菜","time":10,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"吞拿魚罐頭1罐,粟米粒半罐,蛋黃醬,生菜,車厘茄,鹽,黑胡椒","steps":"1. 吞拿魚瀝油/水\n2. 粟米粒瀝乾\n3. 吞拿魚+粟米+蛋黃醬拌勻\n4. 加鹽黑胡椒調味\n5. 鋪在生菜上\n6. 配車厘茄","tips":"夏天食最啱，雪凍仲好味"},
        {"name":"蛋沙律三文治","cuisine":"西式","method":"炒","taste":"清淡","nutrition":"蛋白質,澱粉質","time":15,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"雞蛋3隻,麵包4片,蛋黃醬,鹽,黑胡椒,牛油","steps":"1. 雞蛋烚熟（水滾後8分鐘）\n2. 浸凍水去殼\n3. 用叉壓碎雞蛋\n4. 加入蛋黃醬、鹽、黑胡椒拌勻\n5. 麵包搽牛油\n6. 夾入蛋沙律\n7. 去邊切件","tips":"蛋唔好烚太熟，蛋黃中間微濕最好"},
        {"name":"煎豬扒配洋蔥汁","cuisine":"西式","method":"煎","taste":"濃味","nutrition":"紅肉,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"豬扒2塊,洋蔥1個,牛油,雞湯,喼汁,鹽,黑胡椒","steps":"1. 豬扒用刀背拍鬆，灑鹽黑胡椒\n2. 熱油中火煎豬扒每面3-4分鐘至熟\n3. 取出備用\n4. 原鑊加牛油炒洋蔥絲至焦糖色\n5. 加雞湯、喼汁煮成汁\n6. 淋在豬扒上","tips":"洋蔥炒到焦糖色先香甜"},
        {"name":"煎雞扒配蘑菇汁","cuisine":"西式","method":"煎","taste":"濃味","nutrition":"白肉,蛋白質","time":25,"early":0,"spicy":0,"ingredients":"雞腿肉2塊,蘑菇100g,牛油,淡忌廉,雞湯,鹽,黑胡椒","steps":"1. 雞腿肉抹乾，灑鹽黑胡椒\n2. 雞皮向下冷鑊慢火煎至皮脆\n3. 翻面再煎至熟\n4. 取出備用\n5. 原鑊加牛油炒蘑菇片\n6. 加雞湯、淡忌廉煮成汁\n7. 淋在雞扒上","tips":"冷鑊落雞皮向下，可以逼出雞油"},
        {"name":"原個焗薯仔","cuisine":"西式","method":"焗","taste":"清淡","nutrition":"澱粉質","time":50,"early":0,"spicy":0,"ingredients":"大薯仔2個,牛油,酸忌廉,蔥花,鹽,黑胡椒","steps":"1. 薯仔洗淨，用叉在表面拮窿\n2. 掃上橄欖油、灑鹽\n3. 200°C焗45-50分鐘至軟\n4. 切十字打開\n5. 加入牛油、酸忌廉\n6. 灑蔥花、黑胡椒","tips":"拮窿可以防止焗嗰陣爆開"},
        {"name":"漢堡扒","cuisine":"西式","method":"煎","taste":"濃味","nutrition":"紅肉,蛋白質","time":25,"early":1,"spicy":0,"ingredients":"牛肉碎250g,洋蔥碎,麵包糠,雞蛋1隻,鹽,黑胡椒,喼汁","steps":"1. 洋蔥碎炒香放涼\n2. 牛肉碎+洋蔥+麵包糠+雞蛋+調味拌勻\n3. 分成兩份，搓成圓餅形\n4. 中間壓一個凹位\n5. 熱油中火煎每面4-5分鐘","tips":"中間壓凹位可以防煎時脹起"},
        {"name":"香草焗雞腿","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"白肉,蛋白質","time":40,"early":1,"spicy":0,"ingredients":"雞腿4隻,迷迭香,蒜頭,檸檬,橄欖油,鹽,黑胡椒","steps":"1. 雞腿抹乾，灑鹽黑胡椒\n2. 加入迷迭香、蒜頭、橄欖油拌勻\n3. 醃30分鐘\n4. 焗爐200°C焗30-35分鐘\n5. 中途翻面\n6. 擠檸檬汁上碟","tips":"雞皮要焗到脆先好食，最後5分鐘可以轉grill mode"},
        {"name":"忌廉粟米湯","cuisine":"西式","method":"炆","taste":"清淡","nutrition":"菜","time":20,"early":0,"has_soup":1,"spicy":0,"ingredients":"粟米蓉1罐,雞湯300ml,牛奶200ml,牛油,麵粉,雞蛋1隻,鹽","steps":"1. 牛油+麵粉炒成roux\n2. 逐少加入雞湯同牛奶攪拌\n3. 加入粟米蓉煮滾\n4. 轉小火煮5分鐘\n5. 加鹽調味\n6. 熄火倒入蛋液攪成蛋花","tips":"經典港式西湯，小朋友最愛"},
        {"name":"牛油蒜蓉煎蝦","cuisine":"西式","method":"煎","taste":"濃味","nutrition":"白肉,蛋白質","time":10,"early":0,"spicy":0,"ingredients":"大蝦8隻,牛油,蒜蓉,檸檬汁,鹽,番茜碎","steps":"1. 蝦去殼去腸，留尾\n2. 抹乾灑鹽\n3. 熱鑊落牛油、蒜蓉\n4. 落蝦中火煎每面1.5-2分鐘\n5. 擠檸檬汁\n6. 灑番茜碎","tips":"蝦一變色就唔好煎太耐，否則會韌"},
        {"name":"焗三文魚","cuisine":"西式","method":"焗","taste":"清淡","nutrition":"魚,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"三文魚柳2塊,檸檬,牛油,蒜蓉,鹽,黑胡椒","steps":"1. 三文魚抹乾，灑鹽黑胡椒\n2. 焗盤鋪上檸檬片\n3. 放上三文魚，上面放牛油蒜蓉\n4. 200°C焗12-15分鐘\n5. 唔好焗太熟，中間微微粉紅","tips":"三文魚焗到剛熟最滑，過熟會鞋"},
        {"name":"炒雜菌","cuisine":"西式","method":"炒","taste":"清淡","nutrition":"菜","time":10,"early":0,"spicy":0,"ingredients":"雜菌(蘑菇/冬菇/雞髀菇)300g,牛油,蒜蓉,鹽,黑胡椒","steps":"1. 雜菌抹乾淨切片（唔好洗）\n2. 熱鑊落牛油蒜蓉\n3. 落雜菌大火快炒\n4. 加鹽黑胡椒調味\n5. 即上碟","tips":"菇唔好洗，用濕布抹就得，洗咗會出水"},
        {"name":"黑椒牛柳粒","cuisine":"西式","method":"煎","taste":"濃味","nutrition":"紅肉,蛋白質","time":15,"early":0,"spicy":0,"ingredients":"牛柳200g,三色椒,洋蔥,黑胡椒碎,生抽,蠔油,牛油","steps":"1. 牛柳切粒，用生抽醃10分鐘\n2. 三色椒洋蔥切塊\n3. 大火熱油煎牛柳粒每面1分鐘\n4. 取出備用\n5. 原鑊炒三色椒洋蔥\n6. 牛柳粒回鑊\n7. 加蠔油、大量黑胡椒碎兜勻","tips":"牛柳粒要大火快煎先鎖住肉汁"},
        {"name":"芝士焗肉醬意粉","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"紅肉,澱粉質","time":35,"early":1,"spicy":0,"ingredients":"意粉200g,肉醬(預先煮好),芝士碎,牛油","steps":"1. 意粉煮至al dente，瀝乾\n2. 撈少少牛油\n3. 焗盤底放意粉\n4. 淋上肉醬\n5. 灑大量芝士碎\n6. 200°C焗15分鐘至芝士金黃","tips":"焗之前所有材料要熱，唔係要焗好耐"},
        {"name":"薯仔沙律","cuisine":"西式","method":"炆","taste":"清淡","nutrition":"澱粉質,菜","time":25,"early":1,"has_cold_dish":1,"spicy":0,"ingredients":"薯仔2個,雞蛋2隻,蛋黃醬,鹽,黑胡椒","steps":"1. 薯仔去皮切粒，煮10分鐘至腍\n2. 雞蛋烚熟切粒\n3. 薯仔瀝乾放涼\n4. 加入蛋粒、蛋黃醬\n5. 加鹽黑胡椒拌勻\n6. 雪凍食更佳","tips":"薯仔粒唔好煮太腍，保持少少咬口"},
        {"name":"蒜蓉包","cuisine":"西式","method":"焗","taste":"濃味","nutrition":"澱粉質","time":10,"early":0,"spicy":0,"ingredients":"法包1條,牛油50g,蒜蓉,番茜碎,鹽","steps":"1. 牛油室溫軟化\n2. 加入蒜蓉、番茜碎、鹽拌勻\n3. 法包切片（唔好切斷）\n4. 每片之間搽上蒜蓉牛油\n5. 用錫紙包好\n6. 200°C焗8-10分鐘\n7. 最後2分鐘打開錫紙焗至脆","tips":"牛油要室溫軟化先容易搽"},
        {"name":"羅宋湯","cuisine":"西式","method":"炆","taste":"濃味","nutrition":"菜,紅肉","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"牛肉200g,番茄,椰菜,甘筍,西芹,薯仔,洋蔥,茄膏,檸檬汁,鹽","steps":"1. 牛肉切件汆水\n2. 所有蔬菜切塊\n3. 熱油炒香洋蔥、牛肉\n4. 加入茄膏、番茄炒香\n5. 加水同所有蔬菜\n6. 大火煮滾轉小火煲45分鐘\n7. 加鹽同檸檬汁調味","tips":"羅宋湯隔夜更好飲，酸味會更出"},
        {"name":"粟米斑塊","cuisine":"西式","method":"煎","taste":"清淡","nutrition":"魚,澱粉質","time":25,"early":0,"spicy":0,"ingredients":"魚柳2塊（可用龍脷柳）,粟米蓉1罐,雞蛋1隻,麵粉,鹽,胡椒粉","steps":"1. 魚柳抹乾切塊，灑鹽胡椒粉\n2. 沾上麵粉→蛋液→麵粉\n3. 熱油半煎炸至金黃\n4. 粟米蓉加熱\n5. 淋在魚塊上","tips":"港式茶餐廳經典，可以加少少蛋花喺粟米汁入面"},
        {"name":"白汁三文魚意粉","cuisine":"西式","method":"炒","taste":"濃味","nutrition":"魚,澱粉質","time":25,"early":0,"spicy":0,"ingredients":"意粉200g,三文魚柳1塊,淡忌廉100ml,蒜蓉,牛油,鹽,黑胡椒,番茜","steps":"1. 意粉按包裝煮好\n2. 三文魚抹乾切粒，灑鹽\n3. 熱鑊落牛油蒜蓉\n4. 煎三文魚粒至表面金黃\n5. 加入淡忌廉煮滾\n6. 加鹽黑胡椒調味\n7. 撈入意粉拌勻\n8. 灑番茜碎","tips":"三文魚唔好煮太耐，保持嫩滑"},
    ]
    
    # ===== 日式家常菜 (25) =====
    recipes += [
        {"name":"照燒雞扒","cuisine":"日式","method":"煎","taste":"濃味","nutrition":"白肉,蛋白質","time":25,"early":1,"spicy":0,"ingredients":"雞腿肉2塊,照燒汁(醬油+味醂+清酒+糖),白芝麻","steps":"1. 雞腿肉去筋，用叉在皮上戳洞\n2. 雞皮向下冷鑊慢火煎至金黃脆皮\n3. 翻面再煎至熟\n4. 加入照燒汁煮至濃稠\n5. 切片灑白芝麻","tips":"冷鑊落雞可以逼出雞油，皮更脆"},
        {"name":"味噌湯","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"菜,蛋白質","time":15,"early":0,"has_soup":1,"spicy":0,"ingredients":"昆布高湯500ml（或即溶高湯粉）,白味噌2湯匙,豆腐,海帶,蔥花","steps":"1. 高湯煮至微滾\n2. 加入豆腐粒、海帶\n3. 熄火\n4. 用篩溶入味噌\n5. 灑蔥花","tips":"味噌一定要熄火後先落，否則香味會走"},
        {"name":"日式咖哩飯","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"紅肉,澱粉質,菜","time":40,"early":1,"spicy":0,"ingredients":"咖哩磚半盒,牛肉/雞肉200g,洋蔥,甘筍,薯仔,白飯","steps":"1. 洋蔥、甘筍、薯仔切塊\n2. 熱油炒香洋蔥至透明\n3. 加入肉類炒至變色\n4. 加水煮滾，撇去浮沫\n5. 小火煮20分鐘至蔬菜軟\n6. 熄火加入咖哩磚攪拌溶化\n7. 小火再煮5分鐘至濃稠\n8. 配上白飯","tips":"日式咖哩隔夜更好食，可以早一晚整定"},
        {"name":"親子丼","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"白肉,蛋白質,澱粉質","time":15,"early":0,"spicy":0,"ingredients":"雞腿肉1塊,雞蛋2隻,洋蔥,白飯,醬油,味醂,清酒,高湯","steps":"1. 醬油+味醂+清酒+高湯煮成丼汁\n2. 洋蔥切絲，雞肉切件\n3. 丼汁煮滾，加入洋蔥煮軟\n4. 加入雞肉煮熟\n5. 蛋液分兩次倒入\n6. 淋在白飯上","tips":"蛋液分兩次落，做出滑嫩同流心雙重口感"},
        {"name":"牛丼","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"紅肉,澱粉質","time":15,"early":0,"spicy":0,"ingredients":"牛肉薄片150g,洋蔥,白飯,醬油,味醂,清酒,高湯,紅薑","steps":"1. 醬油+味醂+清酒+高湯煮成醬汁\n2. 加入洋蔥絲煮軟\n3. 加入牛肉片煮熟（唔好煮太耐）\n4. 淋在白飯上\n5. 配紅薑","tips":"牛肉最後落，變色即熟"},
        {"name":"鹽燒鯖魚","cuisine":"日式","method":"焗","taste":"清淡","nutrition":"魚,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"鯖魚1條,鹽,檸檬,蘿蔔蓉","steps":"1. 鯖魚內外抹鹽，醃10分鐘\n2. 預熱焗爐200°C\n3. 鯖魚放在烤架上\n4. 焗10-12分鐘至皮脆\n5. 配檸檬、蘿蔔蓉","tips":"用grill mode皮會更脆"},
        {"name":"日式溏心蛋","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"蛋白質","time":15,"early":1,"spicy":0,"ingredients":"雞蛋4隻,醬油,味醂,清酒,糖,水","steps":"1. 雞蛋室溫回溫\n2. 水滾後放入雞蛋，準確計時6.5分鐘\n3. 立即放入冰水降溫\n4. 去殼\n5. 醬油+味醂+清酒+糖+水煮溶放涼\n6. 浸蛋過夜","tips":"準確計時係溏心嘅關鍵"},
        {"name":"炒烏冬","cuisine":"日式","method":"炒","taste":"濃味","nutrition":"澱粉質,菜","time":15,"early":0,"spicy":0,"ingredients":"烏冬2包,椰菜絲,甘筍絲,豬肉片,日式炒麵醬汁,木魚碎","steps":"1. 烏冬用熱水沖散瀝乾\n2. 熱油炒豬肉片至變色\n3. 加入椰菜絲、甘筍絲\n4. 加入烏冬大火快炒\n5. 加炒麵醬汁兜勻\n6. 灑木魚碎","tips":"烏冬用熱水沖散就得，唔使再煮"},
        {"name":"玉子燒","cuisine":"日式","method":"煎","taste":"清淡","nutrition":"蛋白質","time":15,"early":0,"spicy":0,"ingredients":"雞蛋3隻,高湯,醬油,味醂,糖,油","steps":"1. 蛋液+高湯+醬油+味醂+糖拌勻\n2. 平底鑊掃油加熱（用細火）\n3. 倒入薄薄一層蛋液\n4. 半熟時由前向後捲\n5. 再掃油，重複步驟3-4\n6. 用保鮮紙捲實定型\n7. 切件上碟","tips":"全程小火，冇玉子燒鑊用平底鑊都得"},
        {"name":"照燒三文魚","cuisine":"日式","method":"煎","taste":"濃味","nutrition":"魚,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"三文魚柳2塊,照燒汁(醬油+味醂+清酒+糖),白芝麻,檸檬","steps":"1. 三文魚抹乾灑鹽\n2. 中小火煎三文魚每面3-4分鐘\n3. 加入照燒汁\n4. 煮至醬汁濃稠包裹魚柳\n5. 灑白芝麻，配檸檬","tips":"照燒汁最後收汁先會亮面"},
        {"name":"日式炸雞","cuisine":"日式","method":"炸","taste":"濃味","nutrition":"白肉,蛋白質","time":35,"early":1,"spicy":0,"ingredients":"雞腿肉300g,醬油,味醂,清酒,薑汁,蒜蓉,片栗粉/生粉","steps":"1. 雞肉切件，用醬油+味醂+清酒+薑汁+蒜蓉醃30分鐘\n2. 瀝乾醃料\n3. 沾上片栗粉\n4. 170°C炸第一次至熟（約5分鐘）\n5. 撈起，油溫升至190°C翻炸30秒至脆\n6. 配檸檬、蛋黃醬","tips":"炸兩次先做到外脆內多汁"},
        {"name":"南瓜煮","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"菜","time":20,"early":1,"spicy":0,"ingredients":"南瓜300g,高湯,醬油,味醂,糖","steps":"1. 南瓜去籽切塊\n2. 高湯+醬油+味醂+糖煮成煮汁\n3. 南瓜皮向下排好在鑊中\n4. 注入煮汁（約蓋過一半）\n5. 蓋上蓋小火煮至南瓜軟\n6. 熄火後浸10分鐘入味","tips":"南瓜皮向下煮可以保持形狀唔會爛"},
        {"name":"茶碗蒸","cuisine":"日式","method":"蒸","taste":"清淡","nutrition":"蛋白質,白肉","time":25,"early":1,"spicy":0,"ingredients":"雞蛋2隻,高湯,蝦仁,雞肉粒,冬菇,味醂,醬油","steps":"1. 蛋液+高湯+味醂+醬油拌勻（蛋液:高湯=1:3）\n2. 過篩去氣泡\n3. 碗底放蝦仁、雞肉、冬菇\n4. 倒入蛋液\n5. 蓋上保鮮紙\n6. 中火蒸12-15分鐘","tips":"蒸時鑊蓋用筷子隔開少少防倒汗水"},
        {"name":"日式角煮","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"紅肉,蛋白質","time":90,"early":1,"spicy":0,"ingredients":"五花腩500g,醬油,味醂,清酒,糖,薑片,蔥段,雞蛋","steps":"1. 五花腩汆水切厚件\n2. 熱鑊煎香五花腩\n3. 加入醬油、味醂、清酒、糖、薑蔥\n4. 加水蓋過肉\n5. 大火煮滾轉小火炆1-1.5小時至腍\n6. 加入烚蛋一起炆30分鐘","tips":"炆好隔夜更入味，送飯一流"},
        {"name":"日式漢堡扒","cuisine":"日式","method":"煎","taste":"濃味","nutrition":"紅肉,蛋白質","time":25,"early":1,"spicy":0,"ingredients":"牛肉碎200g,豬肉碎50g,洋蔥碎,麵包糠,雞蛋,鹽,黑胡椒","steps":"1. 洋蔥碎炒香放涼\n2. 兩種肉碎+洋蔥+麵包糠+雞蛋+調味拌勻\n3. 分成兩個圓餅，中間壓凹\n4. 熱油中火煎每面4-5分鐘\n5. 喼汁+茄汁+糖煮成醬汁淋上","tips":"混合豬肉碎可以令漢堡扒更多汁"},
        {"name":"薑汁豬肉","cuisine":"日式","method":"炒","taste":"濃味","nutrition":"紅肉,蛋白質","time":15,"early":0,"spicy":0,"ingredients":"豬肉薄片200g,洋蔥,薑蓉,醬油,味醂,清酒,糖,椰菜絲","steps":"1. 醬油+味醂+清酒+薑蓉+糖混合成醬汁\n2. 洋蔥切絲\n3. 熱油炒洋蔥至軟\n4. 加入豬肉片炒至變色\n5. 倒入醬汁快炒兜勻\n6. 鋪在椰菜絲上","tips":"豬肉片用梅頭肉最軟嫩"},
        {"name":"和風炒野菜","cuisine":"日式","method":"炒","taste":"清淡","nutrition":"菜","time":10,"early":0,"spicy":0,"ingredients":"椰菜,芽菜,甘筍絲,韭菜,蒜蓉,醬油,味醂,麻油,白芝麻","steps":"1. 椰菜切絲，甘筍切絲\n2. 熱油爆香蒜蓉\n3. 依次落甘筍→椰菜→芽菜大火快炒\n4. 加醬油、味醂調味\n5. 熄火加麻油\n6. 灑白芝麻、韭菜","tips":"蔬菜要大火快炒保持爽脆"},
        {"name":"蕎麥麵","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"澱粉質","time":15,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"蕎麥麵200g,日式沾麵汁,蔥花,芥末,紫菜絲","steps":"1. 蕎麥麵按包裝煮熟\n2. 用凍水沖洗至完全冷卻\n3. 瀝乾水份\n4. 沾麵汁稀釋\n5. 麵放在竹簾或碟上\n6. 配蔥花、芥末、紫菜絲\n7. 食時夾起麵沾汁","tips":"蕎麥麵要過冷河先爽口彈牙"},
        {"name":"日式蛋包飯","cuisine":"日式","method":"煎","taste":"濃味","nutrition":"澱粉質,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"白飯1碗,雞肉粒,洋蔥,茄汁,雞蛋3隻,牛油,鹽","steps":"1. 洋蔥雞肉粒炒香\n2. 加入白飯、茄汁炒成茄汁炒飯\n3. 蛋液打散加鹽\n4. 平底鑊掃牛油，小火倒蛋液\n5. 蛋半熟時放入炒飯\n6. 用蛋皮包好\n7. 上面淋茄汁","tips":"蛋皮唔好煎太熟，半流心狀態最靚"},
        {"name":"筑前煮","cuisine":"日式","method":"炆","taste":"濃味","nutrition":"菜,白肉","time":30,"early":1,"spicy":0,"ingredients":"雞腿肉200g,甘筍,牛蒡,蒟蒻,冬菇,蓮藕,醬油,味醂,清酒,高湯","steps":"1. 所有材料切塊\n2. 雞肉炒至變色\n3. 加入所有蔬菜略炒\n4. 加高湯、醬油、味醂、清酒\n5. 大火煮滾轉小火炆20分鐘\n6. 熄火浸10分鐘入味","tips":"筑前煮係日本家庭必備煮物，可以早一晚整定"},
        {"name":"日式番薯煮","cuisine":"日式","method":"炆","taste":"清淡","nutrition":"澱粉質","time":20,"early":1,"spicy":0,"ingredients":"日本番薯2個,高湯,醬油,味醂,糖","steps":"1. 番薯切圓塊（約2cm厚）\n2. 高湯+醬油+味醂+糖煮成煮汁\n3. 番薯放入煮汁\n4. 小火煮至番薯腍（約15分鐘）\n5. 熄火浸10分鐘入味","tips":"番薯唔好切太薄，煮時會爛"},
        {"name":"日式芝麻菠菜","cuisine":"日式","method":"炒","taste":"清淡","nutrition":"菜","time":10,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"菠菜200g,白芝麻醬/芝麻粉,醬油,糖,白芝麻","steps":"1. 菠菜洗淨，汆水1分鐘\n2. 浸凍水降溫\n3. 擠乾水份，切段\n4. 芝麻醬+醬油+糖拌勻\n5. 撈入菠菜\n6. 灑白芝麻","tips":"菠菜一定要擠乾水，唔係會溝淡醬汁"},
        {"name":"照燒茄子","cuisine":"日式","method":"煎","taste":"濃味","nutrition":"菜","time":15,"early":0,"spicy":0,"ingredients":"茄子2條,照燒汁(醬油+味醂+糖),白芝麻,油,蔥花","steps":"1. 茄子切厚片，表面𠝹十字紋\n2. 熱油中火煎茄子兩面至軟身\n3. 加入照燒汁\n4. 煮至醬汁濃稠\n5. 灑白芝麻、蔥花","tips":"茄子𠝹十字紋可以更快入味"},
        {"name":"三文魚茶漬飯","cuisine":"日式","method":"炒","taste":"清淡","nutrition":"魚,澱粉質","time":10,"early":0,"spicy":0,"ingredients":"白飯1碗,三文魚鬆/三文魚碎,綠茶/高湯,紫菜絲,芝麻,芥末","steps":"1. 白飯放入碗\n2. 鋪上三文魚鬆\n3. 灑紫菜絲、芝麻\n4. 沖入熱綠茶或高湯\n5. 配少少芥末","tips":"簡單快靚正，用食剩嘅三文魚都得"},
        {"name":"日式豆腐沙律","cuisine":"日式","method":"炒","taste":"清淡","nutrition":"蛋白質,菜","time":10,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"嫩豆腐1盒,車厘茄,青瓜絲,生菜,芝麻醬,白芝麻","steps":"1. 豆腐輕輕瀝乾水，切件\n2. 青瓜切絲，車厘茄切半\n3. 生菜鋪底\n4. 放上豆腐、青瓜、車厘茄\n5. 淋上芝麻醬\n6. 灑白芝麻","tips":"豆腐要買日式絹豆腐先夠滑"},
    ]
    
    # ===== 東南亞家常菜 (25) =====
    recipes += [
        {"name":"冬蔭功湯","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,蛋白質","time":25,"early":0,"has_soup":1,"spicy":1,"ingredients":"蝦200g,草菇,冬蔭功醬,香茅,南薑,檸檬葉,椰奶,魚露,青檸汁,辣椒","steps":"1. 香茅拍扁，南薑切片\n2. 水煮滾加入香茅南薑檸檬葉煮5分鐘\n3. 加入冬蔭功醬、草菇\n4. 加入蝦煮熟\n5. 加魚露、青檸汁調味\n6. 最後加入椰奶攪拌","tips":"椰奶最後落，煮太耐會分層"},
        {"name":"海南雞飯","cuisine":"東南亞","method":"炆","taste":"清淡","nutrition":"白肉,澱粉質","time":60,"early":1,"spicy":0,"ingredients":"雞1隻,米,雞湯,薑,蒜頭,班蘭葉,薑蓉蘸料,黑醬油","steps":"1. 雞用鹽抹勻，浸入滾水加薑蔥\n2. 轉小火微滾浸雞30分鐘\n3. 取出浸冰水定皮\n4. 雞油炒香薑蒜蓉，加生米炒香\n5. 加雞湯、班蘭葉煮成油飯\n6. 雞斬件，配蘸醬","tips":"浸雞而唔係滾雞，肉先嫩滑"},
        {"name":"肉骨茶","cuisine":"東南亞","method":"炆","taste":"濃味","nutrition":"紅肉,蛋白質","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"排骨500g,肉骨茶藥材包,蒜頭,冬菇,生抽,老抽,蠔油","steps":"1. 排骨汆水去血沫\n2. 水煮滾加入肉骨茶藥材包、蒜頭\n3. 加排骨大火煮滾轉小火\n4. 炆1小時至排骨軟腍\n5. 加入冬菇、生抽老抽蠔油調味\n6. 再炆15分鐘","tips":"配油炸鬼、白飯一齊食最正宗"},
        {"name":"泰式炒金邊粉","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,白肉","time":20,"early":0,"spicy":1,"ingredients":"金邊粉200g,蝦仁,豆腐乾,芽菜,韭菜,雞蛋,羅望子醬,魚露,糖,花生碎,青檸","steps":"1. 金邊粉浸軟瀝乾\n2. 羅望子醬+魚露+糖調成醬汁\n3. 熱油炒蝦仁、豆腐乾\n4. 打入雞蛋炒散\n5. 加入金邊粉、醬汁大火快炒\n6. 加入芽菜、韭菜兜勻\n7. 灑花生碎，配青檸","tips":"金邊粉唔好浸太耐，保持Q彈"},
        {"name":"馬來西亞咖哩雞","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,澱粉質","time":50,"early":1,"spicy":1,"ingredients":"雞件500g,馬來咖哩粉,椰奶,薯仔,洋蔥,蒜頭,香茅","steps":"1. 雞件用咖哩粉醃30分鐘\n2. 洋蔥蒜頭香茅爆香\n3. 加入雞件炒至變色\n4. 加咖哩粉、水煮滾\n5. 加薯仔小火炆30分鐘\n6. 最後加椰奶煮滾","tips":"椰奶最後落保持香味"},
        {"name":"印尼炒飯","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,蛋白質","time":15,"early":0,"spicy":1,"ingredients":"隔夜白飯2碗,蝦仁,雞肉粒,雞蛋,甜醬油,辣椒醬,蒜蓉,蔥花,蝦片","steps":"1. 熱油炒香蒜蓉\n2. 加入蝦仁、雞肉炒熟\n3. 打入雞蛋炒散\n4. 加入白飯大火快炒\n5. 加甜醬油、辣椒醬調味\n6. 煎太陽蛋放面\n7. 配蝦片、青瓜片","tips":"要用隔夜飯炒先粒粒分明"},
        {"name":"泰式青咖哩雞","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,菜","time":30,"early":0,"spicy":1,"ingredients":"青咖哩醬,雞肉200g,椰奶,泰國茄子,青豆角,魚露,椰糖,羅勒葉","steps":"1. 椰奶煮至出油\n2. 加入青咖哩醬炒香\n3. 加入雞肉炒至變色\n4. 加入椰奶煮5分鐘\n5. 加入茄子、豆角煮熟\n6. 加魚露、椰糖調味\n7. 灑羅勒葉","tips":"椰奶要先煮出油再加咖哩醬先香"},
        {"name":"星洲炒米","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,白肉","time":20,"early":0,"spicy":1,"ingredients":"米粉200g,叉燒絲,蝦仁,雞蛋,芽菜,咖哩粉,洋蔥絲,青椒絲","steps":"1. 米粉浸軟瀝乾\n2. 熱油炒香洋蔥、青椒\n3. 加入叉燒、蝦仁\n4. 加咖哩粉炒香\n5. 加入米粉大火快炒\n6. 加入芽菜兜勻","tips":"咖哩粉要先炒先出味"},
        {"name":"泰式豬頸肉","cuisine":"東南亞","method":"焗","taste":"濃味","nutrition":"紅肉,蛋白質","time":35,"early":1,"spicy":0,"ingredients":"豬頸肉300g,蠔油,生抽,蜜糖,蒜蓉,胡椒粉","steps":"1. 豬頸肉用蠔油+生抽+蜜糖+蒜蓉醃至少2小時\n2. 焗爐200°C焗15分鐘\n3. 掃上蜜糖\n4. 再焗5-10分鐘至表面焦香\n5. 切片，配蘸醬","tips":"掃蜜糖係做出焦香表面嘅關鍵"},
        {"name":"越式米紙卷","cuisine":"東南亞","method":"炒","taste":"清淡","nutrition":"菜,白肉","time":20,"early":0,"has_cold_dish":1,"spicy":0,"ingredients":"米紙,蝦,米粉,生菜,薄荷葉,青瓜絲,花生蘸醬","steps":"1. 蝦煮熟切半\n2. 米粉淥熟\n3. 米紙用溫水浸軟（2-3秒）\n4. 鋪上生菜、米粉、蝦、青瓜絲、薄荷葉\n5. 捲緊，兩邊摺入\n6. 配花生蘸醬","tips":"米紙浸水2-3秒就夠，太軟會爛"},
        {"name":"沙嗲串燒","cuisine":"東南亞","method":"焗","taste":"濃味","nutrition":"白肉,蛋白質","time":40,"early":1,"spicy":0,"ingredients":"雞肉300g,沙嗲醬,椰奶,黃薑粉,竹籤,花生蘸醬","steps":"1. 雞肉切件，用沙嗲醬+椰奶+黃薑粉醃過夜\n2. 竹籤浸水30分鐘防燒焦\n3. 串起肉件\n4. 焗爐200°C焗10分鐘，中途翻面\n5. 配花生蘸醬、青瓜、洋蔥","tips":"用grill mode最接近炭火燒"},
        {"name":"泰式椰汁雞湯","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,菜","time":25,"early":0,"has_soup":1,"spicy":1,"ingredients":"雞肉200g,椰奶,雞湯,香茅,南薑,檸檬葉,辣椒,魚露,青檸汁,草菇","steps":"1. 椰奶煮至出油\n2. 加入香茅、南薑、檸檬葉、辣椒煮5分鐘\n3. 加入雞湯、雞肉\n4. 加入草菇煮熟\n5. 加魚露、青檸汁調味","tips":"Tom Kha Gai要酸辣椰香平衡"},
        {"name":"馬來西亞炒粿條","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,白肉","time":15,"early":0,"spicy":1,"ingredients":"粿條300g,蝦仁,臘腸片,芽菜,韭菜,雞蛋,蒜蓉,辣椒醬,甜醬油,魚露","steps":"1. 粿條分開\n2. 大火熱油爆香蒜蓉\n3. 加入蝦仁、臘腸片\n4. 打入雞蛋炒散\n5. 加入粿條大火快炒\n6. 加辣椒醬、甜醬油、魚露\n7. 加入芽菜、韭菜兜勻","tips":"鑊要夠熱，大火快炒先有鑊氣"},
        {"name":"越式牛肉河粉","cuisine":"東南亞","method":"炆","taste":"清淡","nutrition":"紅肉,澱粉質","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"牛骨,牛肉薄片,河粉,洋蔥,薑,八角,桂皮,魚露,芽菜,青檸,辣椒,九層塔","steps":"1. 牛骨汆水，加洋蔥薑（先烤香）、八角、桂皮煲湯2小時\n2. 牛肉薄片備用\n3. 河粉淥熟放碗\n4. 鋪上生牛肉片\n5. 淋上滾熱牛骨湯\n6. 配芽菜、青檸、辣椒、九層塔","tips":"牛骨同洋蔥薑要先烤香湯先有深度"},
        {"name":"芒果糯米飯","cuisine":"東南亞","method":"蒸","taste":"清淡","nutrition":"澱粉質","time":40,"early":1,"spicy":0,"ingredients":"糯米200g,椰奶,糖,鹽,芒果2個,芝麻","steps":"1. 糯米浸過夜\n2. 隔水蒸糯米25-30分鐘至熟\n3. 椰奶+糖+鹽煮熱\n4. 蒸好糯米趁熱拌入椰奶\n5. 芒果切片\n6. 糯米飯配芒果\n7. 淋椰奶醬灑芝麻","tips":"糯米要浸夠時間先蒸得透"},
        {"name":"泰式青木瓜沙律","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"菜","time":15,"early":0,"has_cold_dish":1,"spicy":1,"ingredients":"青木瓜絲,車厘茄,花生碎,蝦米,蒜頭,辣椒,魚露,青檸汁,椰糖","steps":"1. 蒜頭、辣椒、蝦米用舂搗碎\n2. 加入椰糖、魚露、青檸汁調味\n3. 加入青木瓜絲、車厘茄輕輕舂勻\n4. 灑花生碎","tips":"青木瓜要即刨即食保持爽脆"},
        {"name":"泰式鹽焗魚","cuisine":"東南亞","method":"焗","taste":"清淡","nutrition":"魚,蛋白質","time":40,"early":0,"spicy":0,"ingredients":"鱸魚1條,粗鹽,香茅,檸檬葉,南薑,檸檬","steps":"1. 魚洗淨，塞入香茅、檸檬葉、南薑\n2. 粗鹽加蛋白拌勻\n3. 鹽鋪在魚上完全覆蓋\n4. 焗爐200°C焗25-30分鐘\n5. 敲開鹽殼\n6. 配海鮮蘸醬","tips":"鹽殼可以鎖住魚汁，魚肉特別嫩"},
        {"name":"泰式香葉包雞","cuisine":"東南亞","method":"焗","taste":"濃味","nutrition":"白肉,蛋白質","time":40,"early":1,"spicy":0,"ingredients":"雞腿肉300g,班蘭葉,蠔油,生抽,蒜蓉,胡椒粉,麻油","steps":"1. 雞肉切件，用蠔油+生抽+蒜蓉+麻油醃30分鐘\n2. 班蘭葉洗淨\n3. 用班蘭葉包裹雞件\n4. 焗爐180°C焗15-20分鐘\n5. 配甜辣醬","tips":"包雞時班蘭葉紋路向外"},
        {"name":"泰式打拋豬","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"紅肉,蛋白質","time":15,"early":0,"spicy":1,"ingredients":"豬肉碎200g,泰式羅勒葉,蒜蓉,辣椒,魚露,生抽,糖,雞蛋","steps":"1. 熱油爆香蒜蓉、辣椒\n2. 加入豬肉碎炒散\n3. 加魚露、生抽、糖調味\n4. 加入羅勒葉快炒\n5. 煎太陽蛋放面\n6. 配白飯","tips":"羅勒葉最後落保持香味"},
        {"name":"福建蝦麵","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"澱粉質,白肉","time":30,"early":0,"spicy":1,"ingredients":"油麵+米粉,蝦,豬肉片,芽菜,雞蛋,蝦頭高湯,辣椒醬,蒜蓉","steps":"1. 蝦頭炒出蝦油，加水煮成高湯\n2. 熱油爆香蒜蓉\n3. 加入蝦、豬肉片炒熟\n4. 加入麵條、辣椒醬\n5. 注入蝦頭高湯\n6. 大火快炒至收汁\n7. 加芽菜、雞蛋","tips":"蝦頭高湯係精髓"},
        {"name":"泰式炒茄子","cuisine":"東南亞","method":"炒","taste":"辣","nutrition":"菜","time":15,"early":0,"spicy":1,"ingredients":"茄子200g,蒜蓉,辣椒,泰式羅勒葉,魚露,生抽,糖","steps":"1. 茄子切塊\n2. 熱油爆香蒜蓉辣椒\n3. 加入茄子大火快炒\n4. 加魚露、生抽、糖調味\n5. 加少少水焗2分鐘\n6. 灑泰式羅勒葉","tips":"普通茄子都可以，唔一定要泰國茄子"},
        {"name":"巴東牛肉","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"紅肉,蛋白質","time":120,"early":1,"spicy":1,"ingredients":"牛肉500g,椰奶,巴東醬(可用現成),椰絲","steps":"1. 牛肉切大件\n2. 巴東醬用油小火炒香（約10分鐘）\n3. 加入牛肉、椰奶\n4. 小火炆1.5-2小時至牛肉軟腍\n5. 醬汁煮至濃稠近乎乾身\n6. 灑上烘香椰絲","tips":"巴東牛肉要炆到醬汁收乾先正宗"},
        {"name":"越南春卷","cuisine":"東南亞","method":"炸","taste":"清淡","nutrition":"白肉,菜","time":30,"early":1,"spicy":0,"ingredients":"春卷皮,豬肉碎,蝦仁,粉絲,木耳,甘筍絲,生菜,魚露蘸汁","steps":"1. 粉絲、木耳浸軟切碎\n2. 豬肉碎+蝦仁+粉絲+木耳+甘筍拌勻\n3. 春卷皮包入餡料\n4. 170°C油炸至金黃\n5. 配生菜包住食，沾魚露汁","tips":"春卷皮要包實但唔好太緊"},
        {"name":"叻沙","cuisine":"東南亞","method":"炆","taste":"辣","nutrition":"白肉,澱粉質","time":35,"early":0,"has_soup":1,"spicy":1,"ingredients":"叻沙醬,米粉,蝦,魚蛋,豆腐卜,芽菜,椰奶,雞湯,青檸","steps":"1. 叻沙醬用油炒香\n2. 加入雞湯、椰奶煮滾\n3. 加入豆腐卜煮5分鐘\n4. 加入蝦、魚蛋煮熟\n5. 米粉淥熟放碗底\n6. 倒入叻沙湯\n7. 放芽菜、青檸","tips":"叻沙醬要先炒香先出味"},
        {"name":"越南咖啡布丁","cuisine":"東南亞","method":"蒸","taste":"濃味","nutrition":"澱粉質","time":20,"early":1,"spicy":0,"ingredients":"越南咖啡粉,煉奶,魚膠粉/寒天粉,糖,水","steps":"1. 越南咖啡用滴漏壺沖出濃縮咖啡\n2. 寒天粉+水+糖煮溶\n3. 混合咖啡液及煉奶\n4. 倒入模具\n5. 冷藏至凝固","tips":"用越南滴漏壺先沖到正宗越南咖啡味"},
    ]
    
    return recipes

def _build_extra_recipes():
    """Additional recipes to fill criteria gaps (炸, 燉, etc)."""
    return [
        # ===== 炸 (4 new) =====
        {"name":"日式炸豬排","cuisine":"日式","method":"炸","taste":"濃味","nutrition":"紅肉,澱粉質","time":30,"early":1,"spicy":0,"ingredients":"豬扒2塊,麵粉,雞蛋,麵包糠,椰菜絲,豬扒醬,鹽,黑胡椒","steps":"1. 豬扒用刀背拍鬆，灑鹽黑胡椒\n2. 依序沾麵粉→蛋液→麵包糠\n3. 170°C炸6-8分鐘至金黃\n4. 撈起瀝油切片\n5. 配椰菜絲、豬扒醬","tips":"炸之前肉要室溫回溫，炸出嚟先均勻"},
        {"name":"酥炸魷魚","cuisine":"中式","method":"炸","taste":"濃味","nutrition":"白肉,蛋白質","time":20,"early":0,"spicy":0,"ingredients":"魷魚300g,脆漿粉(麵粉+粟粉+泡打粉),椒鹽,檸檬","steps":"1. 魷魚洗淨切圈，抹乾\n2. 脆漿粉加冰水攪成粉漿\n3. 魷魚沾粉漿\n4. 180°C炸3-4分鐘至金黃酥脆\n5. 灑椒鹽，配檸檬","tips":"粉漿用冰水開，炸出嚟先脆"},
        {"name":"炸豆腐","cuisine":"中式","method":"炸","taste":"清淡","nutrition":"蛋白質,菜","time":15,"early":0,"spicy":0,"ingredients":"硬豆腐1盒,生粉,蒜蓉,辣椒,生抽,醋,糖,蔥花","steps":"1. 豆腐切件，用廚房紙吸乾水份\n2. 沾上薄薄生粉\n3. 180°C炸至金黃\n4. 蒜蓉+辣椒+生抽+醋+糖煮成醬汁\n5. 淋在炸豆腐上，灑蔥花","tips":"豆腐一定要吸乾水先炸，唔係會彈油"},
        {"name":"椒鹽雞翼","cuisine":"中式","method":"炸","taste":"濃味","nutrition":"白肉,蛋白質","time":25,"early":0,"spicy":0,"ingredients":"雞翼10隻,椒鹽,蒜蓉,辣椒,生粉,生抽,料酒","steps":"1. 雞翼用生抽、料酒醃30分鐘\n2. 瀝乾，沾上生粉\n3. 170°C炸8-10分鐘至熟\n4. 油溫升至190°C翻炸1分鐘至脆\n5. 爆香蒜蓉辣椒，加入雞翼、椒鹽兜勻","tips":"炸兩次先做到外脆內多汁"},
        
        # ===== 燉 (6 new) =====
        {"name":"紅燒牛腩","cuisine":"中式","method":"燉","taste":"濃味","nutrition":"紅肉,蛋白質","time":120,"early":1,"spicy":0,"ingredients":"牛腩500g,白蘿蔔1條,薑片,八角,桂皮,生抽,老抽,冰糖","steps":"1. 牛腩汆水切件，白蘿蔔去皮切塊\n2. 熱油爆香薑片、八角、桂皮\n3. 加入牛腩炒香\n4. 加生抽、老抽、冰糖、水蓋過牛腩\n5. 大火煮滾轉小火燉1.5小時\n6. 加入白蘿蔔再燉30分鐘至腍","tips":"隔夜更入味，燉好攤凍再翻熱最好食"},
        {"name":"燉雞湯","cuisine":"中式","method":"燉","taste":"清淡","nutrition":"白肉,蛋白質","time":120,"early":1,"has_soup":1,"spicy":0,"ingredients":"雞半隻,淮山,杞子,紅棗,薑片,鹽","steps":"1. 雞斬件汆水去血沫\n2. 淮山、杞子、紅棗洗淨\n3. 所有材料放入燉盅\n4. 加入熱水蓋過材料\n5. 隔水燉2小時\n6. 加鹽調味","tips":"用熱水燉唔會降溫，湯更鮮甜"},
        {"name":"東坡肉","cuisine":"中式","method":"燉","taste":"濃味","nutrition":"紅肉,蛋白質","time":150,"early":1,"spicy":0,"ingredients":"五花腩500g,生抽,老抽,冰糖,紹興酒,薑片,蔥段","steps":"1. 五花腩汆水，切大方塊\n2. 用棉繩綁十字定型\n3. 砂鍋底鋪薑蔥，皮向下放肉\n4. 加生抽、老抽、冰糖、紹興酒、水\n5. 大火煮滾轉小火燉2小時\n6. 翻面再燉30分鐘至皮軟腍","tips":"綁繩可以保持形狀，燉好先解開"},
        {"name":"燉蛋","cuisine":"中式","method":"燉","taste":"清淡","nutrition":"蛋白質","time":25,"early":0,"spicy":0,"ingredients":"雞蛋3隻,牛奶200ml,糖30g","steps":"1. 雞蛋打散加糖拌勻\n2. 加入牛奶攪拌均勻\n3. 過篩倒入碗中，撇去泡泡\n4. 蓋上保鮮紙\n5. 隔水中火燉12-15分鐘\n6. 冷熱皆可食","tips":"蛋液過篩先滑，保鮮紙防倒汗水"},
        {"name":"淮山杞子燉排骨","cuisine":"中式","method":"燉","taste":"清淡","nutrition":"紅肉,蛋白質","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"排骨400g,淮山,杞子,紅棗,薑片,鹽","steps":"1. 排骨汆水洗淨\n2. 淮山、杞子、紅棗浸軟\n3. 所有材料放入燉盅\n4. 加熱水蓋過材料\n5. 隔水燉1.5小時\n6. 加鹽調味","tips":"燉湯唔好中途開蓋，保持溫度"},
        {"name":"南乳燜豬手","cuisine":"中式","method":"燉","taste":"濃味","nutrition":"紅肉,蛋白質","time":120,"early":1,"spicy":0,"ingredients":"豬手1隻,南乳2磚,薑片,蒜頭,八角,生抽,老抽,冰糖","steps":"1. 豬手斬件汆水5分鐘\n2. 南乳壓爛\n3. 熱油爆香薑蒜、南乳\n4. 加豬手炒香\n5. 加生抽、老抽、冰糖、八角、水\n6. 大火煮滾轉小火燉1.5小時至腍","tips":"南乳要先爆香先出味"},

        # ===== 煎 (2 new) =====
        {"name":"煎釀豆腐","cuisine":"中式","method":"煎","taste":"清淡","nutrition":"蛋白質,白肉","time":25,"early":0,"spicy":0,"ingredients":"硬豆腐2盒,魚肉200g,蔥花,生抽,蠔油,生粉","steps":"1. 豆腐切件，中間挖小洞\n2. 魚肉加蔥花、生抽拌勻\n3. 豆腐洞內撲少少生粉，釀入魚肉\n4. 熱油中火，魚肉面向下煎至金黃\n5. 翻面煎至豆腐金黃\n6. 加蠔油、水煮成汁淋上","tips":"豆腐撲生粉可以防魚肉甩出嚟"},
        {"name":"煎魚餅","cuisine":"中式","method":"煎","taste":"濃味","nutrition":"魚,蛋白質","time":20,"early":1,"spicy":0,"ingredients":"魚肉300g,蔥花,芫茜,鹽,胡椒粉,生粉","steps":"1. 魚肉加蔥花、芫茜、鹽、胡椒粉、生粉拌勻\n2. 攪至起膠\n3. 分成小份，搓圓壓扁\n4. 熱油中火煎至兩面金黃\n5. 配甜辣醬或生抽","tips":"魚肉要攪到起膠先彈牙"},

        # ===== 蒸 (2 new) =====
        {"name":"豉汁蒸魚頭","cuisine":"中式","method":"蒸","taste":"濃味","nutrition":"魚,蛋白質","time":15,"early":0,"spicy":0,"ingredients":"大魚頭半個,豆豉,蒜蓉,薑絲,辣椒,生抽,油,蔥花","steps":"1. 魚頭洗淨斬件\n2. 豆豉沖洗壓爛，加蒜蓉、薑絲、辣椒拌勻\n3. 鋪在魚頭上\n4. 大火蒸10分鐘\n5. 淋上生抽，灑蔥花\n6. 燒滾油淋面","tips":"蒸魚時間因魚頭大細調整"},
        {"name":"糯米蒸排骨","cuisine":"中式","method":"蒸","taste":"濃味","nutrition":"紅肉,澱粉質","time":45,"early":1,"spicy":0,"ingredients":"排骨400g,糯米200g,生抽,老抽,蠔油,薑絲,蒜蓉","steps":"1. 糯米浸水4小時以上\n2. 排骨用生抽、老抽、蠔油、薑蒜醃30分鐘\n3. 糯米瀝乾，加少少生抽拌勻\n4. 排骨沾上糯米\n5. 大火蒸40分鐘至糯米熟透","tips":"糯米要浸夠時間先蒸得透"},

        # ===== 冷盤 (6 new, 中式涼拌) =====
        {"name":"涼拌青瓜","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":10,"early":1,"has_cold_dish":1,"spicy":0,"ingredients":"青瓜2條,蒜蓉,醋,生抽,麻油,糖,辣椒油(可選)","steps":"1. 青瓜洗淨，用刀拍鬆後切段\n2. 加鹽醃10分鐘出水，瀝乾\n3. 蒜蓉+醋+生抽+麻油+糖攪勻成醬汁\n4. 淋在青瓜上拌勻\n5. 雪凍30分鐘更佳","tips":"青瓜拍鬆先入味，唔好切太幼"},
        {"name":"皮蛋豆腐","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"蛋白質","time":5,"early":1,"has_cold_dish":1,"spicy":0,"ingredients":"嫩豆腐1盒,皮蛋2隻,蔥花,生抽,麻油,蠔油,蒜蓉","steps":"1. 豆腐瀝乾水，切件上碟\n2. 皮蛋去殼切粒，鋪在豆腐上\n3. 蒜蓉+生抽+蠔油+麻油攪勻淋上\n4. 灑蔥花\n5. 雪凍食更佳","tips":"豆腐要嫩，室溫食或雪凍都得"},
        {"name":"涼拌木耳","cuisine":"中式","method":"炒","taste":"辣","nutrition":"菜","time":15,"early":1,"has_cold_dish":1,"spicy":1,"ingredients":"木耳100g,蒜蓉,辣椒,醋,生抽,麻油,糖,芫茜","steps":"1. 木耳浸軟，汆水2分鐘\n2. 撈起浸凍水，瀝乾\n3. 蒜蓉+辣椒+醋+生抽+麻油+糖攪勻\n4. 木耳絲加入醬汁拌勻\n5. 灑芫茜，雪凍30分鐘","tips":"木耳汆水要保持爽脆，唔好煮太耐"},
        {"name":"口水雞","cuisine":"中式","method":"炆","taste":"辣","nutrition":"白肉,蛋白質","time":40,"early":1,"has_cold_dish":1,"spicy":1,"ingredients":"雞腿2隻,花椒油,辣椒油,芝麻醬,蒜蓉,芝麻,蔥花,青瓜絲","steps":"1. 雞腿煮熟後放入冰水定皮\n2. 去骨切件，鋪在青瓜絲上\n3. 花椒油+辣椒油+芝麻醬+蒜蓉調成醬汁\n4. 淋在雞上，灑芝麻蔥花\n5. 雪凍食更佳","tips":"煮雞時加薑蔥可以去腥"},
        {"name":"蒜泥白肉","cuisine":"中式","method":"炆","taste":"濃味","nutrition":"紅肉,蛋白質","time":30,"early":1,"has_cold_dish":1,"spicy":0,"ingredients":"五花腩300g,蒜蓉,生抽,醋,麻油,辣椒油,青瓜絲","steps":"1. 五花腩汆水後煮熟\n2. 放涼後切薄片\n3. 青瓜絲墊底，鋪上白肉\n4. 蒜蓉+生抽+醋+麻油+辣椒油攪勻淋上\n5. 雪凍食更佳","tips":"肉要切得越薄越好，雪過先切更薄"},
        {"name":"涼拌海蜇","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"白肉,菜","time":20,"early":1,"has_cold_dish":1,"spicy":0,"ingredients":"海蜇200g,青瓜絲,甘筍絲,蒜蓉,醋,生抽,麻油,糖","steps":"1. 海蜇浸水2小時去鹹味，換水幾次\n2. 汆水10秒立即撈起浸凍水\n3. 瀝乾水份\n4. 加青瓜絲、甘筍絲、蒜蓉、醋、生抽、麻油、糖拌勻\n5. 雪凍30分鐘","tips":"海蜇汆水唔好太耐，要保持爽脆"},
        
        # ===== 中式純菜 (12 new, vegetable-only dishes) =====
        {"name":"蒜蓉炒芥蘭","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":8,"early":0,"spicy":0,"ingredients":"芥蘭300g,蒜蓉,鹽,油,糖","steps":"1. 芥蘭洗淨，摘去老葉，切段\n2. 燒熱水加少少糖，汆水1分鐘撈起\n3. 熱油爆香蒜蓉\n4. 落芥蘭大火快炒\n5. 加鹽調味上碟","tips":"汆水加糖可以保持芥蘭翠綠"},
        {"name":"清炒白菜","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":7,"early":0,"spicy":0,"ingredients":"白菜300g,蒜蓉,鹽,油","steps":"1. 白菜洗淨，切段\n2. 熱油爆香蒜蓉\n3. 落白菜大火快炒\n4. 加少少水焗1分鐘\n5. 加鹽調味上碟","tips":"白菜要大火快炒，保持爽脆"},
        {"name":"白灼生菜","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":5,"early":0,"spicy":0,"ingredients":"生菜300g,蠔油,生抽,油,蒜蓉","steps":"1. 生菜洗淨剝開\n2. 燒滾一鍋水，加少少油\n3. 生菜汆水30秒立即撈起\n4. 瀝乾上碟\n5. 蒜蓉+蠔油+生抽+油煮滾淋上面","tips":"汆水加油可以保持生菜翠綠唔變黃"},
        {"name":"上湯娃娃菜","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜","time":15,"early":0,"spicy":0,"ingredients":"娃娃菜2棵,雞湯200ml,蒜蓉,薑片,鹽","steps":"1. 娃娃菜洗淨，切開四份\n2. 熱油爆香蒜蓉薑片\n3. 加入雞湯煮滾\n4. 放入娃娃菜\n5. 小火煮5-8分鐘至軟腍\n6. 加鹽調味","tips":"娃娃菜用上湯燴先入味，唔好煮太腍"},
        {"name":"蠔油炒豆苗","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"菜","time":6,"early":0,"spicy":0,"ingredients":"豆苗300g,蠔油,蒜蓉,鹽,油","steps":"1. 豆苗洗淨瀝乾\n2. 熱油爆香蒜蓉\n3. 落豆苗大火快炒\n4. 加蠔油、鹽調味\n5. 快炒至軟身即上碟","tips":"豆苗好易熟，全程大火唔好炒太耐"},
        {"name":"蒜蓉炒西蘭花","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":10,"early":0,"spicy":0,"ingredients":"西蘭花1個,蒜蓉,鹽,油","steps":"1. 西蘭花切小朵，汆水1分鐘\n2. 熱油爆香蒜蓉\n3. 落西蘭花大火快炒\n4. 加鹽調味\n5. 兜勻上碟","tips":"汆水可以保持西蘭花翠綠爽脆"},
        {"name":"乾煸四季豆","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"菜","time":15,"early":0,"spicy":0,"ingredients":"四季豆300g,蒜蓉,薑蓉,生抽,糖,油","steps":"1. 四季豆去筋，摘段\n2. 熱油大火將四季豆炒至表皮起皺\n3. 撈起瀝油\n4. 原鑊爆香蒜蓉薑蓉\n5. 四季豆回鑊，加生抽、糖兜勻","tips":"四季豆一定要炒熟，半生唔熟會中毒"},
        {"name":"清炒椰菜花","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":10,"early":0,"spicy":0,"ingredients":"椰菜花1個,蒜蓉,鹽,油","steps":"1. 椰菜花切小朵，汆水1分鐘\n2. 熱油爆香蒜蓉\n3. 落椰菜花大火快炒\n4. 加鹽調味上碟","tips":"椰菜花唔好炒太耐，保持爽脆口感"},
        {"name":"腐乳炒生菜","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"菜","time":7,"early":0,"spicy":0,"ingredients":"生菜300g,腐乳2磚,蒜蓉,糖,油","steps":"1. 生菜洗淨剝開\n2. 腐乳壓爛加少少糖拌勻\n3. 熱油大火爆香蒜蓉\n4. 落生菜大火快炒\n5. 加入腐乳醬快炒兜勻\n6. 即上碟","tips":"生菜要大火快炒，炒太耐會出水"},
        {"name":"薑汁炒芥蘭","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":8,"early":0,"spicy":0,"ingredients":"芥蘭300g,薑汁1湯匙,鹽,糖,油","steps":"1. 芥蘭洗淨摘段\n2. 燒熱水加少少糖，汆水1分鐘\n3. 熱油爆香薑汁\n4. 落芥蘭大火快炒\n5. 加鹽調味上碟","tips":"薑汁炒芥蘭清熱解毒，冬天最啱食"},
        {"name":"清炒菠菜","cuisine":"中式","method":"炒","taste":"清淡","nutrition":"菜","time":6,"early":0,"spicy":0,"ingredients":"菠菜300g,蒜蓉,鹽,油","steps":"1. 菠菜洗淨，摘去根部\n2. 熱油爆香蒜蓉\n3. 落菠菜大火快炒\n4. 菠菜軟身即加鹽兜勻\n5. 即上碟","tips":"菠菜好易熟，炒太耐會變黑出水"},
        {"name":"粉絲炒椰菜","cuisine":"中式","method":"炒","taste":"濃味","nutrition":"菜,澱粉質","time":10,"early":0,"spicy":0,"ingredients":"椰菜半個,粉絲1把,蒜蓉,生抽,蠔油,油","steps":"1. 粉絲浸軟，椰菜切絲\n2. 熱油爆香蒜蓉\n3. 落椰菜絲大火快炒至軟身\n4. 加入粉絲、生抽、蠔油\n5. 快炒兜勻至粉絲吸收醬汁\n6. 上碟","tips":"粉絲唔好浸太耐，保持少少彈性"},
        
        # ===== 中式湯品 (10 new, Chinese soups) =====
        {"name":"冬瓜瘦肉湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,紅肉","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"冬瓜500g,瘦肉300g,薑片,鹽","steps":"1. 瘦肉汆水洗淨\n2. 冬瓜去皮去籽切大塊\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉中小火煲45分鐘\n5. 加鹽調味","tips":"冬瓜唔好切太細，煲湯會溶晒"},
        {"name":"西洋菜豬骨湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,紅肉","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"西洋菜300g,豬骨400g,蜜棗2粒,薑片,鹽","steps":"1. 豬骨汆水洗淨\n2. 西洋菜洗淨摘段\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1.5小時\n5. 加鹽調味","tips":"西洋菜要水滾先落，唔係會苦"},
        {"name":"青紅蘿蔔瘦肉湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,紅肉","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"青蘿蔔1條,紅蘿蔔2條,瘦肉300g,蜜棗,薑片,鹽","steps":"1. 瘦肉汆水洗淨\n2. 青紅蘿蔔去皮切塊\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1.5小時\n5. 加鹽調味","tips":"青紅蘿蔔要切大塊，煲湯先出味"},
        {"name":"蓮藕排骨湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"紅肉,澱粉質","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"蓮藕1節,排骨400g,花生,蜜棗,薑片,鹽","steps":"1. 排骨汆水洗淨\n2. 蓮藕去皮切片，花生浸軟\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1.5小時\n5. 加鹽調味","tips":"蓮藕揀粉藕煲湯先香濃"},
        {"name":"節瓜排骨湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,紅肉","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"節瓜2個,排骨400g,薑片,鹽","steps":"1. 排骨汆水洗淨\n2. 節瓜去皮切大塊\n3. 排骨、薑片放入煲加水煲30分鐘\n4. 加入節瓜再煲20分鐘\n5. 加鹽調味","tips":"節瓜後落唔會煲到溶晒"},
        {"name":"粟米紅蘿蔔豬骨湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,紅肉,澱粉質","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"粟米2條,紅蘿蔔2條,豬骨400g,蜜棗,薑片,鹽","steps":"1. 豬骨汆水洗淨\n2. 粟米斬段，紅蘿蔔去皮切塊\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1.5小時\n5. 加鹽調味","tips":"粟米連芯煲湯更甜"},
        {"name":"粉葛鯪魚湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"魚,澱粉質","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"粉葛1條,鯪魚2條,赤小豆,蜜棗,薑片,鹽","steps":"1. 鯪魚洗淨抹乾，煎至兩面金黃\n2. 粉葛去皮切塊，赤小豆浸軟\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1.5小時\n5. 加鹽調味","tips":"魚一定要煎香先煲，湯先奶白唔腥"},
        {"name":"紫菜蛋花湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,蛋白質","time":10,"early":0,"has_soup":1,"spicy":0,"ingredients":"紫菜1片,雞蛋2隻,雞湯500ml,蔥花,麻油,鹽","steps":"1. 紫菜撕碎\n2. 雞湯煮滾\n3. 加入紫菜煮2分鐘\n4. 蛋液慢慢倒入攪成蛋花\n5. 加鹽、麻油調味，灑蔥花","tips":"蛋液要慢慢倒同攪拌先有靚蛋花"},
        {"name":"芫荽皮蛋魚片湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"魚,蛋白質","time":20,"early":0,"has_soup":1,"spicy":0,"ingredients":"魚片200g,皮蛋2隻,芫荽,薑絲,雞湯500ml,鹽,胡椒粉","steps":"1. 魚片用鹽、胡椒粉醃5分鐘\n2. 皮蛋去殼切粒\n3. 雞湯加薑絲煮滾\n4. 加入皮蛋煮3分鐘\n5. 放入魚片煮至變色\n6. 灑芫荽，熄火上碗","tips":"魚片要最後落，煮太耐會散"},
        {"name":"番茄豆腐湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,蛋白質","time":20,"early":0,"has_soup":1,"spicy":0,"ingredients":"番茄3個,嫩豆腐1盒,雞蛋1隻,蔥花,雞湯500ml,鹽","steps":"1. 番茄切塊，豆腐切粒\n2. 雞湯煮滾，加番茄煮5分鐘至出味\n3. 加入豆腐輕輕拌勻煮3分鐘\n4. 蛋液慢慢倒入攪成蛋花\n5. 加鹽調味，灑蔥花","tips":"番茄要煮到出汁溶入湯先夠味"},
        {"name":"老黃瓜瘦肉湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,紅肉","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"老黃瓜1條,瘦肉300g,蜜棗,薑片,鹽","steps":"1. 瘦肉汆水洗淨\n2. 老黃瓜去皮去籽切大塊\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1.5小時\n5. 加鹽調味","tips":"老黃瓜要揀深色多紋先夠老，煲湯最甜"},
        {"name":"菜乾豬骨湯","cuisine":"中式","method":"炆","taste":"濃味","nutrition":"菜,紅肉","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"菜乾100g,豬骨400g,蜜棗,薑片,鹽","steps":"1. 菜乾浸水1小時洗淨，豬骨汆水\n2. 所有材料放入煲，加水蓋過\n3. 大火煮滾轉小火煲1.5小時\n4. 加鹽調味","tips":"菜乾要浸夠時間先出味，唔好貪快"},
        {"name":"胡椒豬肚湯","cuisine":"中式","method":"炆","taste":"濃味","nutrition":"紅肉,蛋白質","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"豬肚1個,白胡椒粒2湯匙,瘦肉200g,薑片,鹽","steps":"1. 豬肚用鹽+生粉搓洗兩次，汆水\n2. 白胡椒粒略拍碎\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1.5小時至豬肚腍\n5. 豬肚撈起切片回煲，加鹽調味","tips":"豬肚一定要洗得乾淨，搓洗兩次先冇腥味"},
        {"name":"木瓜魚湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"魚,菜","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"木瓜1個,鯇魚尾2條,瘦肉200g,蜜棗,薑片,鹽","steps":"1. 魚尾洗淨抹乾，煎至金黃\n2. 木瓜去皮去籽切塊，瘦肉汆水\n3. 魚尾+瘦肉+薑片+蜜棗放入煲加水煲30分鐘\n4. 加入木瓜再煲20分鐘\n5. 加鹽調味","tips":"木瓜後落唔會煲溶，湯先清甜"},
        {"name":"豆腐魚頭湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"魚,蛋白質","time":30,"early":0,"has_soup":1,"spicy":0,"ingredients":"大魚頭半個,嫩豆腐1盒,薑片,蔥花,鹽,胡椒粉","steps":"1. 魚頭洗淨斬件，抹乾\n2. 熱油爆香薑片，煎魚頭至金黃\n3. 加滾水大火滾10分鐘至奶白色\n4. 加入豆腐煮5分鐘\n5. 加鹽、胡椒粉，灑蔥花","tips":"魚頭煎香加滾水，湯即刻奶白"},
        {"name":"蕃茄薯仔湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,澱粉質","time":30,"early":1,"has_soup":1,"spicy":0,"ingredients":"番茄3個,薯仔2個,瘦肉200g,薑片,鹽","steps":"1. 瘦肉汆水，番茄薯仔切塊\n2. 所有材料放入煲，加水蓋過\n3. 大火煮滾轉小火煲30分鐘\n4. 加鹽調味","tips":"薯仔唔好切太細，煲湯會溶晒"},
        {"name":"冬瓜薏米湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,澱粉質","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"冬瓜500g,薏米50g,瘦肉300g,薑片,鹽","steps":"1. 瘦肉汆水洗淨\n2. 冬瓜去皮去籽切大塊，薏米浸30分鐘\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1小時\n5. 加鹽調味","tips":"夏天飲最啱，消暑祛濕"},
        {"name":"雪耳瘦肉湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"紅肉,蛋白質","time":60,"early":1,"has_soup":1,"spicy":0,"ingredients":"雪耳2朵,瘦肉300g,蜜棗,薑片,鹽","steps":"1. 雪耳浸軟去蒂，撕細朵\n2. 瘦肉汆水洗淨\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1小時\n5. 加鹽調味","tips":"雪耳要浸到全透先煲，出膠先靚"},
        {"name":"蘋果雪梨瘦肉湯","cuisine":"中式","method":"炆","taste":"清淡","nutrition":"菜,紅肉","time":90,"early":1,"has_soup":1,"spicy":0,"ingredients":"蘋果2個,雪梨2個,瘦肉300g,蜜棗,薑片,鹽","steps":"1. 瘦肉汆水洗淨\n2. 蘋果雪梨去芯切塊（唔使去皮）\n3. 所有材料放入煲，加水蓋過\n4. 大火煮滾轉小火煲1.5小時\n5. 加鹽調味","tips":"蘋果雪梨連皮煲更香，天然甜味唔使落糖"},
    ]

