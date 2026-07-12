"""
小夏的美食手账后端 v4.1 — 个人饮食记录版
- 去掉了 price 与 dine_type 两个字段
- 一条记录 = 吃了什么 + 几份 + 时间 + 备忘
- 菜品含菜谱（recipe 食材 + steps 做法），GET /dish/<菜名> 查看详情
图片存在 static/images/，URL 通过 /img/<name> 访问
"""
import os
import sqlite3
from datetime import datetime
from flask import Flask, request, g, send_from_directory

app = Flask(__name__)

# 确保所有路径用绝对路径（云端需要）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "menu.db")
IMG_DIR = os.path.join(BASE_DIR, "static", "images")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute('''
        CREATE TABLE IF NOT EXISTS dishes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            category TEXT    NOT NULL,
            image    TEXT    DEFAULT ''
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_name  TEXT    NOT NULL,
            quantity   INTEGER NOT NULL,
            created_at TEXT    NOT NULL,
            note       TEXT    DEFAULT ''
        )
    ''')

    # ===== 兼容旧表：清理已废弃的列 =====
    dish_cols = [row[1] for row in db.execute("PRAGMA table_info(dishes)").fetchall()]
    if "price" in dish_cols:
        db.execute("ALTER TABLE dishes DROP COLUMN price")
    # 新增菜谱字段（v4.1）
    if "recipe" not in dish_cols:
        db.execute("ALTER TABLE dishes ADD COLUMN recipe TEXT DEFAULT ''")
    if "steps" not in dish_cols:
        db.execute("ALTER TABLE dishes ADD COLUMN steps TEXT DEFAULT ''")

    order_cols = [row[1] for row in db.execute("PRAGMA table_info(orders)").fetchall()]
    if "unit_price" in order_cols:
        db.execute("ALTER TABLE orders DROP COLUMN unit_price")
    if "dine_type" in order_cols:
        db.execute("ALTER TABLE orders DROP COLUMN dine_type")
    # 旧表可能还没有 note 列
    if "note" not in order_cols:
        db.execute("ALTER TABLE orders ADD COLUMN note TEXT DEFAULT ''")

    count = db.execute("SELECT COUNT(*) FROM dishes").fetchone()[0]
    if count == 0:
        dishes = [
            # === 烧菜 ===
            ("红烧肉",       "烧菜", "/img/红烧牛肉.png"),
            ("宫保鸡丁",     "烧菜", "/img/花椒鸡.png"),
            ("回锅肉",       "烧菜", "/img/红烧牛肉.png"),
            # === 凉菜 ===
            ("拍黄瓜",       "凉菜", "/img/番茄鸡蛋盖饭.png"),
            ("凉拌木耳",     "凉菜", "/img/酸菜鱼.png"),
            ("口水鸡",       "凉菜", "/img/炸鸡翅(4个).png"),
            # === 汤羹 ===
            ("番茄蛋花汤",   "汤羹", "/img/番茄鸡蛋盖饭.png"),
            ("紫菜蛋花汤",   "汤羹", "/img/杨枝甘露.png"),
            ("银耳莲子羹",   "汤羹", "/img/杨枝甘露.png"),
            # === 主食 ===
            ("红烧牛肉面",   "主食", "/img/红烧牛肉面.png"),
            ("番茄鸡蛋盖饭", "主食", "/img/番茄鸡蛋盖饭.png"),
            ("红烧牛肉",     "主食", "/img/红烧牛肉.png"),
            ("花椒鸡",       "主食", "/img/花椒鸡.png"),
            ("酸菜鱼",       "主食", "/img/酸菜鱼.png"),
            ("酸辣粉",       "主食", "/img/酸辣粉.png"),
            # === 小吃 ===
            ("炸鸡翅(4个)",  "小吃", "/img/炸鸡翅(4个).png"),
            ("薯条",         "小吃", "/img/薯条.png"),
            # === 饮品 ===
            ("可乐",         "饮品", "/img/可乐.jpg"),
            ("冰镇柠檬水",   "饮品", "/img/冰镇柠檬水.jpg"),
            ("杨枝甘露",     "饮品", "/img/杨枝甘露.png"),
        ]
        db.executemany(
            "INSERT INTO dishes (name, category, image) VALUES (?, ?, ?)",
            dishes,
        )

    # ===== 填充菜谱内容（已有菜品若为空则补上）=====
    recipes = {
        "红烧牛肉面": (
            "牛腩300g、碱水面200g、葱姜蒜、八角2颗、桂皮1小块、香叶2片、生抽2勺、老抽1勺、料酒1勺、冰糖、盐",
            "1. 牛腩切块冷水下锅焯水捞出\n2. 锅热油炒冰糖至焦糖色，下牛肉翻炒上色\n3. 加葱姜蒜、八角桂皮香叶炒香，淋料酒、生抽、老抽\n4. 加开水没过牛肉，大火烧开转小火炖90分钟\n5. 另锅煮面捞出，浇上牛肉汤，撒葱花即可",
        ),
        "番茄鸡蛋盖饭": (
            "番茄2个、鸡蛋2个、米饭1碗、葱、盐、糖、生抽",
            "1. 番茄划十字烫水去皮切块，鸡蛋打散\n2. 热油炒熟鸡蛋盛出\n3. 底油炒番茄出沙，加糖、盐、生抽\n4. 倒回鸡蛋翻炒，出锅浇在米饭上",
        ),
        "红烧牛肉": (
            "牛肉500g、土豆1个、葱姜蒜、八角2颗、生抽、老抽、冰糖、料酒",
            "1. 牛肉切块焯水\n2. 炒糖色下牛肉上色，加葱姜八角\n3. 加料酒、生抽、老抽和开水炖1小时\n4. 加土豆块再炖20分钟收汁",
        ),
        "花椒鸡": (
            "鸡腿肉400g、花椒一把、干辣椒、葱姜蒜、生抽、料酒、糖",
            "1. 鸡腿肉切丁，加料酒、生抽腌15分钟\n2. 热油下鸡丁煸至变色盛出\n3. 底油爆香花椒、干辣椒、葱姜蒜\n4. 倒回鸡丁翻炒，加生抽、糖出锅",
        ),
        "酸菜鱼": (
            "草鱼1条、酸菜1包、泡椒、花椒、葱姜、蛋清1个、淀粉、盐",
            "1. 鱼片成片，加蛋清、淀粉、盐抓匀腌制\n2. 酸菜切段炒干水分\n3. 加水煮开放酸菜煮出味\n4. 下鱼片煮至变白，捞出浇上热花椒油",
        ),
        "酸辣粉": (
            "红薯粉、醋2勺、辣椒油、生抽、花生碎、榨菜、葱花、香菜、高汤",
            "1. 红薯粉泡软煮熟过凉水\n2. 碗底放醋、生抽、辣椒油、榨菜\n3. 冲入热高汤，放入红薯粉\n4. 撒花生碎、葱花、香菜即可",
        ),
        "炸鸡翅(4个)": (
            "鸡翅4个、料酒、生抽、姜、蒜、淀粉、鸡蛋、面包糠",
            "1. 鸡翅划刀，加料酒、生抽、姜蒜腌30分钟\n2. 依次裹淀粉、蛋液、面包糠\n3. 油温六成热下鸡翅炸至金黄\n4. 捞出控油即可",
        ),
        "薯条": (
            "土豆2个、盐、食用油、番茄酱",
            "1. 土豆切条泡水去淀粉\n2. 沸水焯1分钟捞出沥干\n3. 油温六成热炸至金黄酥脆\n4. 撒盐，蘸番茄酱食用",
        ),
        "可乐": (
            "罐装可乐1罐",
            "1. 冰镇后开罐即饮",
        ),
        "冰镇柠檬水": (
            "柠檬1个、蜂蜜2勺、冰块、凉开水",
            "1. 柠檬切片去籽\n2. 杯中放柠檬片捣出汁\n3. 加蜂蜜、冰块，倒入凉开水搅匀",
        ),
        "杨枝甘露": (
            "芒果2个、西柚半个、椰浆100ml、西米30g、淡奶、糖",
            "1. 西米煮至透明过凉水\n2. 芒果一半切块一半打成泥\n3. 混合芒果泥、椰浆、淡奶、糖\n4. 加西米、芒果块、西柚粒冷藏即可",
        ),
        # === 新增菜系示例菜谱 ===
        "红烧肉": (
            "五花肉500g、冰糖30g、葱姜蒜、八角2颗、桂皮1小块、香叶2片、生抽3勺、老抽2勺、料酒2勺",
            "1. 五花肉切3cm方块冷水下锅焯水捞出\n2. 锅热油炒冰糖至焦糖色，下肉块翻炒上色\n3. 加葱姜蒜、八角桂皮香叶炒香\n4. 淋料酒、生抽、老抽，加热水没过肉\n5. 大火烧开转小火炖90分钟收汁即可",
        ),
        "宫保鸡丁": (
            "鸡胸肉300g、花生米50g、干辣椒8个、花椒一把、葱白、姜蒜、生抽、老抽、醋、糖、淀粉",
            "1. 鸡胸肉切丁，加生抽、料酒、淀粉抓匀腌15分钟\n2. 调碗汁：生抽+老抽+醋+糖+淀粉+水搅匀\n3. 热油炸花生米至金黄捞出\n4. 底油爆香干辣椒花椒，下鸡丁炒至变色\n5. 倒入碗汁翻炒，撒葱段和花生米出锅",
        ),
        "回锅肉": (
            "五花肉300g、青椒2个、豆瓣酱2勺、甜面酱1勺、蒜苗、姜蒜、生抽、糖",
            "1. 五花肉整块冷水下锅煮20分钟至七八分熟\n2. 捞出切片（约2mm厚）\n3. 青椒切块、蒜苗切段\n4. 锅热少油煸炒肉片出油卷边\n5. 加豆瓣酱、甜面酱炒出红油\n6. 下青椒、蒜苗大火翻炒，淋生抽出锅",
        ),
        "拍黄瓜": (
            "黄瓜2根、蒜末、辣椒油1勺、醋2勺、生抽1勺、盐、白糖、香油、芝麻",
            "1. 黄瓜洗净用刀背拍碎切段\n2. 放碗中加蒜末\n3. 调汁：辣椒油+醋+生抽+盐+白糖+香油搅匀\n4. 浇在黄瓜上拌匀，撒芝麻即可",
        ),
        "凉拌木耳": (
            "干木耳30g、胡萝卜半根、蒜末、小米辣2个、醋3勺、生抽2勺、香油、盐、糖",
            "1. 干木耳泡发撕小朵，沸水焯2分钟过凉水\n2. 胡萝卜切丝焯水\n3. 蒜末+小米辣放碗里\n4. 加醋、生抽、香油、盐、糖调成料汁\n5. 倒入木耳胡萝卜拌匀即可",
        ),
        "口水鸡": (
            "鸡腿2个、花生碎、芝麻、葱花、辣椒油3勺、生抽2勺、醋2勺、白糖、花椒粉、姜蒜",
            "1. 鸡腿冷水下锅加姜片料酒煮至熟透（约20分钟）\n2. 捞出冰水中浸泡10分钟，切块摆盘\n3. 调料汁：辣椒油+生抽+醋+白糖+花椒粉+姜末搅匀\n4. 浇在鸡肉上，撒花生碎、葱花、芝麻",
        ),
        "番茄蛋花汤": (
            "番茄2个、鸡蛋2个、葱花、盐、胡椒粉、香油",
            "1. 番茄去皮切块\n2. 锅热少许油炒番茄出沙\n3. 加水烧开煮5分钟\n4. 鸡蛋打散淋入锅中形成蛋花\n5. 加盐、胡椒粉调味，淋香油撒葱花",
        ),
        "紫菜蛋花汤": (
            "干紫菜1片、鸡蛋2个、虾皮适量、葱花、盐、香油",
            "1. 干紫菜撕小块用清水泡软\n2. 锅烧开水，放入紫菜和虾皮煮2分钟\n3. 鸡蛋打散淋入锅中搅成蛋花\n4. 加盐调味，淋香油撒葱花即可",
        ),
        "银耳莲子羹": (
            "银耳15g、莲子30g、红枣6颗、冰糖40g、枸杞适量",
            "1. 银耳提前2小时泡发去根撕小朵\n2. 莲子泡发去芯，红枣洗净\n3. 所有材料放入锅中加足量清水\n4. 大火烧开转小火炖1小时至银耳软糯出胶\n5. 加冰糖搅拌融化，撒枸杞即可",
        ),
    }
    for name, (recipe, steps) in recipes.items():
        db.execute(
            "UPDATE dishes SET recipe=?, steps=? WHERE name=? AND (recipe IS NULL OR recipe='')",
            (recipe, steps, name),
        )

    db.commit()
    db.close()

init_db()


# ===== 前端页面 =====
@app.route("/app")
def order_app():
    """返回饮食记录前端页面"""
    return send_from_directory(BASE_DIR, "order_app.html")


# ===== 图片服务 =====
@app.route("/img/<path:filename>")
def serve_image(filename):
    """返回 static/images/ 下的图片"""
    return send_from_directory(IMG_DIR, filename)


# ===== Class 模型 =====
class Dish:
    def __init__(self, name, category, image="", recipe="", steps=""):
        self.name = name
        self.category = category
        self.image = image
        self.recipe = recipe      # 食材清单
        self.steps = steps        # 制作步骤（换行分隔）

    def to_dict(self):
        return {
            "name":     self.name,
            "category": self.category,
            "image":    self.image or f"/img/{self.name}.png",
            "recipe":   self.recipe,
            "steps":    self.steps,
        }


class Order:
    def __init__(self, dish_name, quantity, created_at=None):
        self.dish_name = dish_name
        self.quantity = quantity
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.note = ""

    def to_dict(self):
        return {
            "dish_name":  self.dish_name,
            "quantity":   self.quantity,
            "created_at": self.created_at,
            "note":       self.note,
        }


# ===== 路由 =====

@app.route("/menu")
def get_menu():
    db = get_db()
    rows = db.execute("SELECT name, category, image FROM dishes").fetchall()
    menu_list = [Dish(r["name"], r["category"], r["image"]).to_dict() for r in rows]
    return {"code": 200, "data": menu_list}


@app.route("/dish/<name>", methods=["GET"])
def get_dish(name):
    """获取单道菜的详情（含食材和做法）"""
    db = get_db()
    row = db.execute(
        "SELECT name, category, image, recipe, steps FROM dishes WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        return {"code": 404, "msg": f"没有这道菜: {name}"}, 404
    dish = Dish(row["name"], row["category"], row["image"], row["recipe"], row["steps"])
    return {"code": 200, "data": dish.to_dict()}


@app.route("/dish", methods=["POST"])
def add_dish():
    data = request.get_json()
    name = data.get("name")
    category = data.get("category")

    if not name:
        return {"code": 400, "msg": "菜名不能为空"}, 400

    db = get_db()
    exist = db.execute("SELECT id FROM dishes WHERE name = ?", (name,)).fetchone()
    if exist:
        return {"code": 409, "msg": f"菜品已存在: {name}"}, 409

    image = f"/img/{name}.png"
    db.execute(
        "INSERT INTO dishes (name, category, image) VALUES (?, ?, ?)",
        (name, category, image),
    )
    db.commit()
    return {"code": 200, "msg": f"添加成功: {name}"}


@app.route("/dish/<name>", methods=["PUT"])
def update_dish(name):
    """更新菜品 —— 可更新分类、图片路径"""
    data = request.get_json()
    db = get_db()
    exist = db.execute("SELECT id FROM dishes WHERE name = ?", (name,)).fetchone()
    if not exist:
        return {"code": 404, "msg": f"没有这道菜: {name}"}, 404

    updates = []
    values = []
    for field in ["category", "image"]:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])
    if not updates:
        return {"code": 400, "msg": "没有要更新的字段"}, 400

    values.append(name)
    db.execute(f"UPDATE dishes SET {', '.join(updates)} WHERE name = ?", values)
    db.commit()
    return {"code": 200, "msg": f"已更新: {name}"}


@app.route("/dish/<name>", methods=["DELETE"])
def delete_dish(name):
    db = get_db()
    result = db.execute("DELETE FROM dishes WHERE name = ?", (name,))
    db.commit()
    if result.rowcount == 0:
        return {"code": 404, "msg": f"没有这道菜: {name}"}, 404
    return {"code": 200, "msg": f"已删除: {name}"}


@app.route("/order", methods=["POST"])
def make_order():
    data = request.get_json()
    dish_name = data.get("dish_name")
    quantity = data.get("quantity", 1)
    note = data.get("note", "")
    db = get_db()
    dish = db.execute("SELECT id FROM dishes WHERE name = ?", (dish_name,)).fetchone()
    if not dish:
        return {"code": 404, "msg": f"没有这道菜: {dish_name}"}, 404
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO orders (dish_name, quantity, created_at, note) VALUES (?, ?, ?, ?)",
        (dish_name, quantity, now, note),
    )
    db.commit()
    order = Order(dish_name, quantity, now)
    order.note = note
    return {
        "code": 200,
        "msg": f"已记录: {dish_name} x{quantity}",
        "order": order.to_dict(),
    }


@app.route("/orders")
def get_orders():
    db = get_db()
    rows = db.execute(
        "SELECT dish_name, quantity, created_at, note FROM orders ORDER BY id DESC"
    ).fetchall()
    order_list = []
    for r in rows:
        order = Order(r["dish_name"], r["quantity"], r["created_at"])
        order.note = r["note"] or ""
        order_list.append(order.to_dict())
    return {"code": 200, "data": order_list, "count": len(order_list)}


@app.route("/clear-orders", methods=["POST"])
def clear_orders():
    db = get_db()
    db.execute("DELETE FROM orders")
    db.commit()
    return {"code": 200, "msg": "记录已清空"}


@app.route("/")
def home():
    return {
        "message": "欢迎来到小夏的美食手账后端 v4.1（个人饮食记录 + 菜谱）",
        "接口": [
            {"地址": "/",                     "说明": "首页"},
            {"地址": "/menu",                 "说明": "获取菜谱（含图片）"},
            {"地址": "/img/<文件名>",          "说明": "获取图片"},
            {"地址": "/dish/<菜名> (GET)",      "说明": "菜品详情（含菜谱）"},
            {"地址": "/dish (POST)",          "说明": "添加菜品"},
            {"地址": "/dish/<菜名> (DELETE)",   "说明": "删除菜品"},
            {"地址": "/order (POST)",         "说明": "记录饮食"},
            {"地址": "/orders",               "说明": "饮食记录列表"},
            {"地址": "/clear-orders (POST)",   "说明": "清空记录"},
        ],
    }


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
