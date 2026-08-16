"""
小夏的美食手账后端 v4.1 — 个人饮食记录版
- 去掉了 price 与 dine_type 两个字段
- 一条记录 = 吃了什么 + 几份 + 时间 + 备忘
- 菜品含菜谱（recipe 食材 + steps 做法），GET /dish/<菜名> 查看详情
图片存在 static/images/，URL 通过 /img/<name> 访问
"""
import os
import json
import time
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# 后端部署在 Render（容器默认 UTC 时区），时间戳必须用北京时间生成
BEIJING = timezone(timedelta(hours=8))
from flask import Flask, request, g, send_from_directory

app = Flask(__name__)

# ===== 安全配置 =====
# 生产环境默认关闭调试模式；仅在显式设置 DEBUG=true 时才开启。
# 调试模式会暴露交互式调试器（潜在 RCE）与详细堆栈信息，存在严重安全风险。
app.config["DEBUG"] = os.environ.get("DEBUG", "false").lower() == "true"
# 限制请求体大小为 1MB，防止超大请求体耗尽资源（DoS）
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

# 后台管理接口密钥（环境变量 ADMIN_TOKEN）。
# 未设置时，所有写/删管理接口直接拒绝访问，防止被安全测试脚本或未授权用户
# 越权增删菜品、清空全部记录。小程序运行所需的公开接口不受影响。
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")


def require_admin():
    """校验后台管理接口访问权限。

    返回 None 表示校验通过；否则返回 (响应体, 状态码)。
    """
    if not ADMIN_TOKEN:
        return {"code": 403, "msg": "管理接口未启用"}, 403
    token = request.headers.get("X-Admin-Token") or request.args.get("token", "")
    if token != ADMIN_TOKEN:
        return {"code": 401, "msg": "未授权访问"}, 401
    return None


# 确保所有路径用绝对路径（云端需要）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "menu.db")
IMG_DIR = os.path.join(BASE_DIR, "static", "images")

# 菜谱字典（模块级，作为「做法」的单一事实来源；init_db 结束后填充，供 /dish 回退使用）
RECIPES = {}

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
    # 订阅消息授权用户表：记录 openid，供后续推送（一次性订阅模型下仅作记录与去重）
    db.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            openid     TEXT PRIMARY KEY,
            updated_at TEXT NOT NULL
        )
    ''')
    # 家庭共享房间（路线 A：房间码模型，无登录）
    db.execute('''
        CREATE TABLE IF NOT EXISTS share_rooms (
            code       TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS share_items (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            code       TEXT NOT NULL,
            dish_name  TEXT NOT NULL,
            quantity   INTEGER NOT NULL DEFAULT 1,
            added_by   TEXT DEFAULT '我',
            created_at TEXT NOT NULL
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

    # 种子菜品：部署时菜品集合与映射的单一事实来源
    dishes = [
        # === 烧菜 ===
        ("红烧肉",       "烧菜", "/img/红烧肉.png"),
        ("宫保鸡丁",     "烧菜", "/img/宫保鸡丁.png"),
        ("回锅肉",       "烧菜", "/img/回锅肉.png"),
        ("麻婆豆腐",     "烧菜", "/img/麻婆豆腐.png"),
        # === 凉菜 ===
        ("拍黄瓜",       "凉菜", "/img/拍黄瓜.png"),
        ("凉拌木耳",     "凉菜", "/img/凉拌木耳.png"),
        ("口水鸡",       "凉菜", "/img/口水鸡.png"),
        # === 汤羹 ===
        ("番茄蛋花汤",   "汤羹", "/img/番茄鸡蛋盖饭.png"),
        ("紫菜蛋花汤",   "汤羹", "/img/紫菜蛋花汤.png"),
        ("银耳莲子羹",   "汤羹", "/img/银耳莲子羹.png"),
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
        ("可乐",         "饮品", "/img/可乐.png"),
        ("冰镇柠檬水",   "饮品", "/img/冰镇柠檬水.png"),
        ("杨枝甘露",     "饮品", "/img/杨枝甘露.png"),
    ]

    count = db.execute("SELECT COUNT(*) FROM dishes").fetchone()[0]
    if count == 0:
        # 全新部署：一次性写入全部种子菜
        db.executemany(
            "INSERT INTO dishes (name, category, image) VALUES (?, ?, ?)",
            dishes,
        )
    else:
        # 库已存在：补齐种子中新增的菜（如后续加菜），不改动已有菜的映射
        for name, cat, img in dishes:
            if not db.execute("SELECT 1 FROM dishes WHERE name=?", (name,)).fetchone():
                db.execute(
                    "INSERT INTO dishes (name, category, image) VALUES (?, ?, ?)",
                    (name, cat, img),
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
        "麻婆豆腐": (
            "嫩豆腐1盒、牛肉末100g、豆瓣酱2勺、花椒粉、干辣椒、葱姜蒜、生抽、料酒、淀粉、葱花",
            "1. 嫩豆腐切小块，沸水加少许盐焯1分钟捞出\n2. 热油炒香牛肉末至变色，下豆瓣酱、葱姜蒜、干辣椒炒出红油\n3. 加适量清水烧开，放入豆腐轻轻推匀煮3分钟\n4. 淋生抽、料酒调味，水淀粉勾芡收汁\n5. 撒花椒粉、葱花即可出锅",
        ),
        # ===== 补齐其余 23 道菜的做法（单一事实来源，启动时同步入库）=====
        "水煮肉片": (
            "猪里脊300g、黄豆芽、青菜、干辣椒、花椒、豆瓣酱2勺、葱姜蒜、淀粉、蛋清、生抽、料酒",
            "1. 肉片加蛋清、淀粉、料酒抓匀腌15分钟\n2. 豆芽青菜焯水铺碗底\n3. 热油炒豆瓣酱和姜蒜出红油，加水烧开\n4. 下肉片滑熟捞出铺在菜上\n5. 撒干辣椒花椒，浇滚烫热油激香",
        ),
        "毛血旺": (
            "鸭血1盒、毛肚、午餐肉、黄豆芽、干辣椒、花椒、豆瓣酱、葱姜蒜",
            "1. 豆芽焯水铺碗底\n2. 热油炒豆瓣酱、姜蒜出红油，加水煮开\n3. 下鸭血、午餐肉煮入味\n4. 放毛肚烫熟捞出\n5. 撒干辣椒花椒，浇热油",
        ),
        "干锅虾": (
            "大虾400g、干辣椒、花椒、葱姜蒜、土豆条、生抽、料酒、香菜",
            "1. 虾开背去虾线，油温炸至金黄\n2. 土豆条炸熟\n3. 底油爆香干辣椒花椒葱姜蒜\n4. 下虾和土豆翻炒，淋生抽料酒\n5. 撒香菜出锅",
        ),
        "清蒸鲈鱼": (
            "鲈鱼1条、葱姜、蒸鱼豉油、料酒、香菜",
            "1. 鲈鱼洗净两面划刀，抹料酒姜片腌10分钟\n2. 水开上锅蒸8分钟，倒掉蒸鱼水\n3. 铺葱姜丝，淋蒸鱼豉油\n4. 浇一勺滚烫热油激香",
        ),
        "蒜泥白肉": (
            "五花肉300g、蒜、生抽、香醋、辣椒油、糖、葱花",
            "1. 五花肉整块冷水下锅煮20分钟至熟\n2. 捞出放凉切薄片\n3. 蒜捣泥，加生抽、醋、辣椒油、糖调汁\n4. 浇在肉片上，撒葱花",
        ),
        "黄焖鸡": (
            "鸡腿肉400g、土豆1个、香菇5朵、青椒、生抽、老抽、冰糖、料酒、姜",
            "1. 鸡块焯水，土豆香菇切块\n2. 热油炒冰糖上色，下鸡块翻炒\n3. 加生抽老抽料酒和开水，放香菇炖20分钟\n4. 加土豆再炖15分钟，放青椒收汁",
        ),
        "凉拌牛肉": (
            "牛腱子300g、香菜、蒜、生抽、香醋、辣椒油、花椒粉",
            "1. 牛肉冷水下锅加姜片料酒煮熟，放凉\n2. 逆纹切薄片\n3. 蒜末加生抽、醋、辣椒油、花椒粉调汁\n4. 淋牛肉上，撒香菜拌匀",
        ),
        "小炒牛肉": (
            "牛里脊300g、青椒2个、小米辣、姜蒜、生抽、料酒、淀粉",
            "1. 牛肉切薄片，加生抽、料酒、淀粉腌10分钟\n2. 青椒切丝，小米辣切圈\n3. 热油大火快炒牛肉至变色盛出\n4. 底油爆香姜蒜辣椒，下青椒和牛肉翻炒出锅",
        ),
        "番茄牛腩": (
            "牛腩500g、番茄3个、葱姜、生抽、冰糖、料酒",
            "1. 牛腩切块焯水\n2. 番茄去皮切块炒出汁\n3. 加牛腩、生抽、冰糖、料酒和开水炖1小时\n4. 收汁至浓稠即可",
        ),
        "笋子牛肉": (
            "牛肉300g、笋200g、青红椒、豆瓣酱、姜蒜、生抽、淀粉",
            "1. 牛肉切片腌好，笋切片焯水\n2. 热油快炒牛肉盛出\n3. 底油炒豆瓣酱、姜蒜，下笋片和青红椒\n4. 倒回牛肉翻炒，淋生抽出锅",
        ),
        "辣子鸡丁": (
            "鸡腿肉400g、干辣椒一把、花椒、葱姜蒜、生抽、料酒、淀粉",
            "1. 鸡肉切丁加生抽、料酒、淀粉腌15分钟\n2. 油温六成热炸至金黄酥脆\n3. 底油爆香干辣椒花椒葱姜蒜\n4. 下鸡丁翻炒均匀出锅",
        ),
        "酸萝卜老鸭汤": (
            "老鸭半只、酸萝卜200g、姜、料酒、盐、枸杞",
            "1. 鸭块冷水下锅焯水\n2. 加姜片料酒炖1小时\n3. 放酸萝卜再炖30分钟\n4. 加盐调味，撒枸杞",
        ),
        "海带炖猪脚": (
            "猪脚1只、海带结200g、姜、料酒、生抽、盐",
            "1. 猪脚焯水去血沫\n2. 加姜料酒炖1小时至软\n3. 放海带结再炖30分钟\n4. 加盐生抽调味",
        ),
        "盐水毛豆": (
            "毛豆300g、八角2颗、花椒、盐、姜",
            "1. 毛豆洗净剪去两头\n2. 冷水下锅加八角花椒姜和盐\n3. 煮8分钟至熟\n4. 连汤浸泡入味，放凉更佳",
        ),
        "粉蒸肉": (
            "五花肉300g、蒸肉米粉1包、土豆1个、生抽、料酒、豆瓣酱",
            "1. 五花肉切片加生抽、料酒、豆瓣酱腌20分钟\n2. 裹上蒸肉米粉\n3. 土豆垫底铺肉片\n4. 上锅蒸40分钟至软糯",
        ),
        "粉蒸排骨": (
            "排骨400g、蒸肉米粉1包、红薯1个、生抽、料酒、豆瓣酱",
            "1. 排骨斩块加生抽、料酒、豆瓣酱腌20分钟\n2. 裹上蒸肉米粉\n3. 红薯垫底铺排骨\n4. 上锅蒸40分钟至软烂",
        ),
        "白灼大虾": (
            "大虾400g、生抽、芥末、姜、料酒",
            "1. 水加姜片料酒烧开\n2. 下大虾煮2分钟至变红卷曲\n3. 捞出过冰水更弹\n4. 蘸生抽芥末食用",
        ),
        "爆炒花蛤": (
            "花蛤500g、干辣椒、蒜、葱、生抽、料酒",
            "1. 花蛤吐沙洗净，焯水至开口捞出\n2. 热油爆香蒜末干辣椒\n3. 下花蛤大火翻炒\n4. 淋生抽料酒，撒葱花出锅",
        ),
        "鱼香肉丝": (
            "猪里脊300g、青椒1个、木耳、胡萝卜、豆瓣酱、葱姜蒜、醋、糖、淀粉",
            "1. 肉切丝加淀粉料酒腌好\n2. 调碗汁：醋+糖+生抽+淀粉+水\n3. 热油炒肉丝盛出，底油炒豆瓣酱出红油\n4. 下青椒木耳胡萝卜丝，倒回肉丝和碗汁翻炒",
        ),
        "手撕鸡": (
            "鸡腿2个、葱、香菜、生抽、香油、辣椒油、蒜",
            "1. 鸡腿冷水下锅煮熟放凉\n2. 撕成细条\n3. 蒜末加生抽、香油、辣椒油调汁\n4. 淋鸡肉上，撒葱花香菜拌匀",
        ),
        "凉拌三丝": (
            "胡萝卜1根、青椒1个、木耳、蒜、生抽、醋、香油、辣椒油",
            "1. 胡萝卜青椒切丝，木耳泡发切丝\n2. 分别焯水过凉\n3. 蒜末加生抽、醋、香油、辣椒油调汁\n4. 拌匀即可",
        ),
        "爽口木耳": (
            "干木耳30g、洋葱半个、蒜、小米辣、生抽、醋、香油",
            "1. 木耳泡发撕小朵焯水过凉\n2. 洋葱切丝\n3. 蒜末小米辣加生抽、醋、香油调汁\n4. 拌匀腌制10分钟更入味",
        ),
        "凉拌万能佐料": (
            "蒜末、小米辣、生抽2勺、香醋1勺、香油、糖、葱花、熟芝麻",
            "1. 蒜末小米辣放碗里\n2. 加生抽、香醋、香油、糖搅匀\n3. 撒葱花熟芝麻\n4. 淋在任意凉菜上拌匀即可",
        ),
    }
    for name, (recipe, steps) in recipes.items():
        # 代码字典是菜谱的单一事实来源，每次启动都按代码同步，避免持久库/缓存导致菜谱为空
        db.execute(
            "UPDATE dishes SET recipe=?, steps=? WHERE name=?",
            (recipe, steps, name),
        )
    global RECIPES
    RECIPES = recipes  # 暴露给 /dish 接口，库内菜谱为空时回退

    db.commit()
    db.close()

init_db()


# ===== 图片服务 =====
@app.route("/img/<filename>")
def serve_image(filename):
    """返回 static/images/ 下的图片；仅允许图片扩展名，禁止路径穿越"""
    # 防御目录遍历：拒绝包含路径分隔符或父目录标记的文件名
    if ".." in filename or "/" in filename or "\\" in filename:
        return {"code": 403, "msg": "禁止访问"}, 403
    allowed_ext = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
    if not filename.lower().endswith(allowed_ext):
        return {"code": 403, "msg": "禁止访问"}, 403
    resp = send_from_directory(IMG_DIR, filename)
    # 菜品图几乎不变，缓存 1 天，减少重复请求、缓解 Render 冷启动延迟
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


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
        self.created_at = created_at or datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
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
    # 库内菜谱为空时回退到代码字典（确保「做法」始终可用，不依赖 init_db 写入时机）
    recipe = row["recipe"] or ""
    steps = row["steps"] or ""
    if not recipe and name in RECIPES:
        recipe, steps = RECIPES[name]
    dish = Dish(row["name"], row["category"], row["image"], recipe, steps)
    return {"code": 200, "data": dish.to_dict()}


@app.route("/dishes/recipes")
def get_dishes_recipes():
    """批量获取多道菜的菜谱（食材 + 做法）。

    小程序「采购清单」页原先需逐道菜发 GET /dish/<name>（N+1 请求），
    改为一次传入多个菜名，显著降低请求数与首屏耗时。
    参数：names=菜名1,菜名2（英文逗号分隔，最多 50 个）
    """
    names_param = request.args.get("names", "")
    name_list = [n for n in names_param.split(",") if n]
    if len(name_list) > 50:
        return {"code": 400, "msg": "一次最多查询 50 道菜"}, 400

    db = get_db()
    result = {}
    for name in name_list:
        row = db.execute(
            "SELECT name, category, image, recipe, steps FROM dishes WHERE name = ?", (name,)
        ).fetchone()
        if not row:
            continue
        recipe = row["recipe"] or ""
        steps = row["steps"] or ""
        if not recipe and name in RECIPES:
            recipe, steps = RECIPES[name]
        result[name] = {
            "name": row["name"],
            "category": row["category"],
            "image": row["image"] or f"/img/{row['name']}.png",
            "recipe": recipe,
            "steps": steps,
        }
    return {"code": 200, "data": result}


@app.route("/dish", methods=["POST"])
def add_dish():
    denied = require_admin()
    if denied:
        return denied
    data = request.get_json(silent=True)
    if not data:
        return {"code": 400, "msg": "请求体格式错误"}, 400
    name = (data.get("name") or "").strip()
    category = (data.get("category") or "").strip()

    if not name:
        return {"code": 400, "msg": "菜名不能为空"}, 400
    if len(name) > 50:
        return {"code": 400, "msg": "菜名过长（上限 50 字符）"}, 400

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
    """更新菜品 —— 可更新分类、图片路径（后台管理接口）"""
    denied = require_admin()
    if denied:
        return denied
    data = request.get_json(silent=True)
    if not data:
        return {"code": 400, "msg": "请求体格式错误"}, 400

    db = get_db()
    exist = db.execute("SELECT id FROM dishes WHERE name = ?", (name,)).fetchone()
    if not exist:
        return {"code": 404, "msg": f"没有这道菜: {name}"}, 404

    # 字段名来自白名单，值是参数化绑定，不存在 SQL 注入风险
    updates = []
    values = []
    for field in ["category", "image"]:
        if field in data and data[field] is not None:
            updates.append(f"{field} = ?")
            values.append(str(data[field])[:200])
    if not updates:
        return {"code": 400, "msg": "没有要更新的字段"}, 400

    values.append(name)
    db.execute(f"UPDATE dishes SET {', '.join(updates)} WHERE name = ?", values)
    db.commit()
    return {"code": 200, "msg": f"已更新: {name}"}


@app.route("/dish/<name>", methods=["DELETE"])
def delete_dish(name):
    denied = require_admin()
    if denied:
        return denied
    db = get_db()
    result = db.execute("DELETE FROM dishes WHERE name = ?", (name,))
    db.commit()
    if result.rowcount == 0:
        return {"code": 404, "msg": f"没有这道菜: {name}"}, 404
    return {"code": 200, "msg": f"已删除: {name}"}


@app.route("/order", methods=["POST"])
def make_order():
    data = request.get_json(silent=True)
    if not data:
        return {"code": 400, "msg": "请求体格式错误"}, 400
    dish_name = (data.get("dish_name") or "").strip()
    quantity = data.get("quantity", 1)
    note = data.get("note", "")

    # 输入校验：防止类型混淆、超范围数值与超长文本写入数据库
    if not dish_name:
        return {"code": 400, "msg": "菜名不能为空"}, 400
    if len(dish_name) > 50:
        return {"code": 400, "msg": "菜名过长（上限 50 字符）"}, 400
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        return {"code": 400, "msg": "数量必须为整数"}, 400
    if quantity < 1 or quantity > 999:
        return {"code": 400, "msg": "数量需在 1-999 之间"}, 400
    if not isinstance(note, str) or len(note) > 500:
        return {"code": 400, "msg": "备注不合法或过长（上限 500 字符）"}, 400

    db = get_db()
    dish = db.execute("SELECT id FROM dishes WHERE name = ?", (dish_name,)).fetchone()
    if not dish:
        return {"code": 404, "msg": f"没有这道菜: {dish_name}"}, 404
    now = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
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
    # 支持按日期过滤（?date=YYYY-MM-DD），供小程序「采购清单」只取今日记录，
    # 避免把历史记录全量拉回再在客户端按 created_at 前缀过滤（存在跨日/时区偏差）。
    date = request.args.get("date")
    sql = "SELECT dish_name, quantity, created_at, note FROM orders"
    params = ()
    if date:
        if not isinstance(date, str) or len(date) > 20 or ".." in date:
            return {"code": 400, "msg": "日期参数不合法"}, 400
        sql += " WHERE created_at LIKE ?"
        params = (date + "%",)
    sql += " ORDER BY id DESC"
    rows = db.execute(sql, params).fetchall()
    order_list = []
    for r in rows:
        order = Order(r["dish_name"], r["quantity"], r["created_at"])
        order.note = r["note"] or ""
        order_list.append(order.to_dict())
    return {"code": 200, "data": order_list, "count": len(order_list)}


@app.route("/orders/calendar")
def orders_calendar():
    """按日聚合的饮食记录日历：返回某月每天记录次数、连续打卡天数、本月总数。"""
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    now = datetime.now(BEIJING)
    if not year:
        year = now.year
    if not month:
        month = now.month
    # 该月每天的记录次数（按 quantity 累加）
    prefix = f"{year:04d}-{month:02d}-"
    rows = get_db().execute(
        "SELECT created_at, quantity FROM orders WHERE created_at LIKE ?",
        (prefix + "%",),
    ).fetchall()
    days = {}
    for r in rows:
        day = r["created_at"][8:10]
        days[day] = days.get(day, 0) + (r["quantity"] or 1)
    # 连续打卡：从今天往前数，遇到无记录的日期即断
    distinct = set()
    for r in get_db().execute("SELECT DISTINCT substr(created_at,1,10) AS d FROM orders").fetchall():
        if r["d"]:
            distinct.add(r["d"])
    streak = 0
    cur = now.date()
    while cur.strftime("%Y-%m-%d") in distinct:
        streak += 1
        cur = cur - timedelta(days=1)
    return {
        "code": 200,
        "data": {
            "year": year,
            "month": month,
            "days": days,
            "streak": streak,
            "monthTotal": sum(days.values()),
        },
    }


@app.route("/clear-orders", methods=["POST"])
def clear_orders():
    db = get_db()
    # 支持按日期清除当日记录（小程序「采购清单-清除当日」功能，公开可用）
    data = request.get_json(silent=True) or {}
    date = data.get("date")
    if date:
        if not isinstance(date, str) or len(date) > 20 or ".." in date:
            return {"code": 400, "msg": "日期参数不合法"}, 400
        cur = db.execute("DELETE FROM orders WHERE created_at LIKE ?", (date + "%",))
        deleted = cur.rowcount
        db.commit()
        return {"code": 200, "msg": f"已清除 {date} 的记录 {deleted} 条", "deleted": deleted}
    # 不带 date：清空全部记录属高危操作，需要后台权限
    denied = require_admin()
    if denied:
        return denied
    db.execute("DELETE FROM orders")
    db.commit()
    return {"code": 200, "msg": "记录已清空"}


# ===== 微信订阅消息（提醒） =====
# 需在小程序后台配置以下环境变量，否则相关接口返回「微信未配置」：
#   WX_APPID    - 小程序 AppID
#   WX_SECRET   - 小程序 AppSecret
#   WX_TMPL_ID  - 订阅消息模板 ID（MP 后台「订阅消息」申请，字段需与 /notify 中 tmpl_data 对应）
WX_APPID = os.environ.get("WX_APPID")
WX_SECRET = os.environ.get("WX_SECRET")
WX_TMPL_ID = os.environ.get("WX_TMPL_ID")

# access_token 缓存（内存 + 过期时间）。微信 token 有效期 7200 秒，
# 缓存避免每次发送都请求，降低频率限制风险。
_WX_TOKEN = {"value": None, "expire": 0}


def _wx_http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _wx_http_post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def get_wx_token():
    """获取微信 access_token（带缓存）。未配置 AppID/Secret 时返回 None。"""
    if not WX_APPID or not WX_SECRET:
        return None
    now = time.time()
    if _WX_TOKEN["value"] and _WX_TOKEN["expire"] > now + 60:
        return _WX_TOKEN["value"]
    url = (
        "https://api.weixin.qq.com/cgi-bin/token"
        "?grant_type=client_credential"
        f"&appid={WX_APPID}&secret={WX_SECRET}"
    )
    info = _wx_http_get(url)
    if not info or "access_token" not in info:
        return None
    _WX_TOKEN["value"] = info["access_token"]
    _WX_TOKEN["expire"] = now + info.get("expires_in", 7200)
    return _WX_TOKEN["value"]


@app.route("/wx/login", methods=["POST"])
def wx_login():
    """用 wx.login 拿到的 code 换取 openid；未配置微信则明确报错。"""
    if not WX_APPID or not WX_SECRET:
        return {"code": 503, "msg": "微信未配置（请设置环境变量 WX_APPID/WX_SECRET）"}, 503
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return {"code": 400, "msg": "缺少 code"}, 400
    url = (
        "https://api.weixin.qq.com/sns/jscode2session"
        f"?appid={WX_APPID}&secret={WX_SECRET}"
        f"&js_code={urllib.parse.quote(code)}&grant_type=authorization_code"
    )
    info = _wx_http_get(url)
    if not info or "openid" not in info:
        return {"code": 502, "msg": "换取 openid 失败"}, 502
    openid = info["openid"]
    # 记录授权用户（兼容旧 SQLite：先查后插/更新，避免依赖 UPSERT 语法）
    now = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    if db_get_subscriber(openid):
        get_db().execute("UPDATE subscribers SET updated_at=? WHERE openid=?", (now, openid))
    else:
        get_db().execute("INSERT INTO subscribers (openid, updated_at) VALUES (?, ?)", (openid, now))
    get_db().commit()
    return {"code": 200, "data": {"openid": openid}}


def db_get_subscriber(openid):
    return get_db().execute("SELECT 1 FROM subscribers WHERE openid=?", (openid,)).fetchone()


@app.route("/notify", methods=["POST"])
def notify():
    """发送一条订阅消息提醒（一次性订阅：发送后即消耗该次授权）。"""
    if not WX_TMPL_ID:
        return {"code": 503, "msg": "微信未配置（请设置环境变量 WX_TMPL_ID）"}, 503
    data = request.get_json(silent=True) or {}
    openid = (data.get("openid") or "").strip()
    if not openid:
        return {"code": 400, "msg": "缺少 openid"}, 400
    token = get_wx_token()
    if not token:
        return {"code": 502, "msg": "获取 access_token 失败"}, 502
    dish = (data.get("dish") or "今天的小夏推荐").strip()
    # 模板字段需与你在 MP 后台申请的模板一致；以下 thing1/time2/thing3 为示例，
    # 实际请按模板的字段名修改（可在 MP 后台「我的模板」查看字段关键字）。
    tmpl_data = {
        "thing1": {"value": "该做晚饭啦"},
        "time2": {"value": datetime.now(BEIJING).strftime("%H:%M")},
        "thing3": {"value": f"小夏推荐：{dish}"},
    }
    url = f"https://api.weixin.qq.com/cgi-bin/message/subscribe/send?access_token={token}"
    payload = {
        "touser": openid,
        "template_id": WX_TMPL_ID,
        "data": tmpl_data,
    }
    result = _wx_http_post(url, payload)
    if not result or result.get("errcode", 0) != 0:
        return {"code": 502, "msg": "发送失败", "detail": result}, 502
    return {"code": 200, "msg": "已发送提醒"}


# ===== 家庭共享（路线 A：房间码，无登录） =====
import random
import string

def gen_room_code():
    """生成 6 位大写字母+数字房间码，保证与已有房间不冲突。"""
    alphabet = string.ascii_uppercase + string.digits
    # 去掉易混字符（0/O/1/I）降低输错概率
    alphabet = alphabet.translate(str.maketrans("", "", "0O1I"))
    for _ in range(10):
        code = "".join(random.choice(alphabet) for _ in range(6))
        exist = get_db().execute(
            "SELECT 1 FROM share_rooms WHERE code=?", (code,)
        ).fetchone()
        if not exist:
            return code
    return None  # 极端冲突兜底


@app.route("/share/room", methods=["POST"])
def create_share_room():
    code = gen_room_code()
    if not code:
        return {"code": 500, "msg": "生成房间码失败"}, 500
    now = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    get_db().execute(
        "INSERT INTO share_rooms (code, created_at) VALUES (?, ?)", (code, now)
    )
    get_db().commit()
    return {"code": 200, "data": {"code": code}}


@app.route("/share/room/<code>", methods=["GET"])
def get_share_room(code):
    """校验房间是否存在（加入时用）。"""
    exist = get_db().execute(
        "SELECT 1 FROM share_rooms WHERE code=?", (code,)
    ).fetchone()
    if not exist:
        return {"code": 404, "msg": "房间不存在"}, 404
    return {"code": 200, "data": {"code": code}}


@app.route("/share/room/<code>/items", methods=["GET"])
def get_share_items(code):
    if not get_db().execute("SELECT 1 FROM share_rooms WHERE code=?", (code,)).fetchone():
        return {"code": 404, "msg": "房间不存在"}, 404
    rows = get_db().execute(
        "SELECT dish_name, quantity, added_by FROM share_items "
        "WHERE code=? ORDER BY id ASC", (code,)
    ).fetchall()
    items = [
        {"dish_name": r["dish_name"], "quantity": r["quantity"], "added_by": r["added_by"]}
        for r in rows
    ]
    return {"code": 200, "data": items}


@app.route("/share/room/<code>/items", methods=["POST"])
def add_share_item(code):
    if not get_db().execute("SELECT 1 FROM share_rooms WHERE code=?", (code,)).fetchone():
        return {"code": 404, "msg": "房间不存在"}, 404
    data = request.get_json(silent=True) or {}
    name = (data.get("dish_name") or "").strip()
    qty = data.get("quantity", 1)
    added_by = (data.get("added_by") or "我").strip()[:20] or "我"
    if not name:
        return {"code": 400, "msg": "菜名不能为空"}, 400
    if len(name) > 50:
        return {"code": 400, "msg": "菜名过长（上限 50 字符）"}, 400
    if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1 or qty > 999:
        return {"code": 400, "msg": "数量需为 1-999 的整数"}, 400
    now = datetime.now(BEIJING).strftime("%Y-%m-%d %H:%M:%S")
    get_db().execute(
        "INSERT INTO share_items (code, dish_name, quantity, added_by, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (code, name, qty, added_by, now),
    )
    get_db().commit()
    return {"code": 200, "msg": f"已添加：{name}"}


@app.route("/share/room/<code>/items", methods=["DELETE"])
def remove_share_item(code):
    if not get_db().execute("SELECT 1 FROM share_rooms WHERE code=?", (code,)).fetchone():
        return {"code": 404, "msg": "房间不存在"}, 404
    data = request.get_json(silent=True) or {}
    name = (data.get("dish_name") or "").strip()
    if not name:
        return {"code": 400, "msg": "菜名不能为空"}, 400
    cur = get_db().execute(
        "DELETE FROM share_items WHERE code=? AND dish_name=?", (code, name)
    )
    get_db().commit()
    return {"code": 200, "msg": f"已移除：{name}", "deleted": cur.rowcount}


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
            {"地址": "/clear-orders (POST)",   "说明": "清空记录（全清需后台权限）"},
            {"地址": "/share/room (POST)",     "说明": "创建家庭共享房间，返回房间码"},
            {"地址": "/share/room/<码> (GET)",  "说明": "校验/获取房间"},
            {"地址": "/share/room/<码>/items",  "说明": "共享清单：GET 列表 / POST 增 / DELETE 删"},
        ],
    }


# ===== 全局错误处理（生产环境不泄露堆栈信息）=====
@app.errorhandler(404)
def handle_404(_e):
    return {"code": 404, "msg": "Not Found"}, 404


@app.errorhandler(405)
def handle_405(_e):
    return {"code": 405, "msg": "Method Not Allowed"}, 405


@app.errorhandler(413)
def handle_413(_e):
    return {"code": 413, "msg": "请求体过大"}, 413


@app.errorhandler(500)
def handle_500(_e):
    # 不向客户端暴露内部异常与堆栈
    return {"code": 500, "msg": "服务器内部错误"}, 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=app.config["DEBUG"], host="0.0.0.0", port=port)
