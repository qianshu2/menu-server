"""
点菜后端 v3.0 — 带菜品图片
图片存在 static/images/，URL 通过 /img/<name> 访问
"""
import sqlite3
from datetime import datetime
from flask import Flask, request, g, send_from_directory

app = Flask(__name__)


# ===== 数据库初始化 =====
DB_PATH = "menu.db"

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
            price    REAL    NOT NULL,
            category TEXT    NOT NULL,
            image    TEXT    DEFAULT ''
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_name  TEXT    NOT NULL,
            quantity   INTEGER NOT NULL,
            unit_price REAL    NOT NULL,
            created_at TEXT    NOT NULL
        )
    ''')
    count = db.execute("SELECT COUNT(*) FROM dishes").fetchone()[0]
    if count == 0:
        dishes = [
            ("红烧牛肉面",   18, "主食", "/img/红烧牛肉面.png"),
            ("番茄鸡蛋盖饭", 15, "主食", "/img/番茄鸡蛋盖饭.png"),
            ("红烧牛肉",     38, "主食", "/img/红烧牛肉.png"),
            ("花椒鸡",       32, "主食", "/img/花椒鸡.png"),
            ("酸菜鱼",       36, "主食", "/img/酸菜鱼.png"),
            ("酸辣粉",       14, "主食", "/img/酸辣粉.png"),
            ("炸鸡翅(4个)",  12, "小吃", "/img/炸鸡翅(4个).png"),
            ("薯条",         10, "小吃", "/img/薯条.png"),
            ("可乐",          5, "饮品", "/img/可乐.jpg"),
            ("冰镇柠檬水",    8, "饮品", "/img/冰镇柠檬水.jpg"),
            ("杨枝甘露",     12, "饮品", "/img/杨枝甘露.png"),
        ]
        db.executemany(
            "INSERT INTO dishes (name, price, category, image) VALUES (?, ?, ?, ?)",
            dishes,
        )
    db.commit()
    db.close()

init_db()


# ===== 图片服务 =====
@app.route("/img/<path:filename>")
def serve_image(filename):
    """返回 static/images/ 下的图片"""
    return send_from_directory("static/images", filename)


# ===== Class 模型 =====
class Dish:
    def __init__(self, name, price, category, image=""):
        self.name = name
        self.price = price
        self.category = category
        self.image = image

    def to_dict(self):
        return {
            "name":     self.name,
            "price":    self.price,
            "category": self.category,
            "image":    self.image or f"/img/{self.name}.png",
        }


class Order:
    def __init__(self, dish_name, quantity, unit_price, created_at=None):
        self.dish_name = dish_name
        self.quantity = quantity
        self.unit_price = unit_price
        self.total = unit_price * quantity
        self.created_at = created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            "dish_name":  self.dish_name,
            "quantity":   self.quantity,
            "unit_price": self.unit_price,
            "total":      self.total,
            "created_at": self.created_at,
        }


# ===== 路由 =====

@app.route("/menu")
def get_menu():
    db = get_db()
    rows = db.execute("SELECT name, price, category, image FROM dishes").fetchall()
    menu_list = [Dish(r["name"], r["price"], r["category"], r["image"]).to_dict() for r in rows]
    return {"code": 200, "data": menu_list}


@app.route("/dish", methods=["POST"])
def add_dish():
    data = request.get_json()
    name = data.get("name")
    price = data.get("price")
    category = data.get("category")

    if not name or price is None:
        return {"code": 400, "msg": "菜名和价格不能为空"}, 400

    db = get_db()
    exist = db.execute("SELECT id FROM dishes WHERE name = ?", (name,)).fetchone()
    if exist:
        return {"code": 409, "msg": f"菜品已存在: {name}"}, 409

    image = f"/img/{name}.png"
    db.execute(
        "INSERT INTO dishes (name, price, category, image) VALUES (?, ?, ?, ?)",
        (name, price, category, image),
    )
    db.commit()
    return {"code": 200, "msg": f"添加成功: {name} ¥{price}"}


@app.route("/dish/<name>", methods=["PUT"])
def update_dish(name):
    """更新菜品 —— 可更新价格、分类、图片路径"""
    data = request.get_json()
    db = get_db()
    exist = db.execute("SELECT id FROM dishes WHERE name = ?", (name,)).fetchone()
    if not exist:
        return {"code": 404, "msg": f"没有这道菜: {name}"}, 404

    updates = []
    values = []
    for field in ["price", "category", "image"]:
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
    db = get_db()
    dish = db.execute("SELECT price FROM dishes WHERE name = ?", (dish_name,)).fetchone()
    if not dish:
        return {"code": 404, "msg": f"没有这道菜: {dish_name}"}, 404
    unit_price = dish["price"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO orders (dish_name, quantity, unit_price, created_at) VALUES (?, ?, ?, ?)",
        (dish_name, quantity, unit_price, now),
    )
    db.commit()
    order = Order(dish_name, quantity, unit_price, now)
    return {
        "code": 200,
        "msg": f"下单成功: {dish_name} x{quantity}，小计 ¥{order.total}",
        "order": order.to_dict(),
    }


@app.route("/orders")
def get_orders():
    db = get_db()
    rows = db.execute(
        "SELECT dish_name, quantity, unit_price, created_at FROM orders ORDER BY id DESC"
    ).fetchall()
    order_list = [
        Order(r["dish_name"], r["quantity"], r["unit_price"], r["created_at"]).to_dict()
        for r in rows
    ]
    total_amount = sum(o["total"] for o in order_list)
    return {"code": 200, "data": order_list, "count": len(order_list), "total_amount": total_amount}


@app.route("/clear-orders", methods=["POST"])
def clear_orders():
    db = get_db()
    db.execute("DELETE FROM orders")
    db.commit()
    return {"code": 200, "msg": "订单已清空"}


@app.route("/")
def home():
    return {
        "message": "欢迎来到点菜小程序后端 v3.0",
        "接口": [
            {"地址": "/",                    "说明": "首页"},
            {"地址": "/menu",                "说明": "获取菜单（含图片）"},
            {"地址": "/img/<文件名>",         "说明": "获取图片"},
            {"地址": "/dish (POST)",         "说明": "添加菜品"},
            {"地址": "/dish/<菜名> (DELETE)",  "说明": "删除菜品"},
            {"地址": "/order (POST)",        "说明": "下单"},
            {"地址": "/orders",              "说明": "订单列表"},
            {"地址": "/clear-orders (POST)",  "说明": "清空订单"},
        ],
    }


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
