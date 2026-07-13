"""
sync_db_images.py
把 menu.db 里每道菜的 image 字段，同步到 static/images/ 下同名的独立图。

规则：
- 若 static/images/<菜名>.png 存在 → image 更新为 /img/<菜名>.png
- 若不存在同名图（如占位复用、暂无独立图）→ 保持原字段不动
- 更新前自动备份 menu.db 为 menu.db.bak
"""
import os
import sqlite3
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "static", "images")
DB = os.path.join(BASE, "menu.db")
BAK = DB + ".bak"


def main():
    if not os.path.exists(BAK):
        shutil.copy2(DB, BAK)
        print(f"已备份数据库: {BAK}")

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT name, image FROM dishes").fetchall()

    updated, skipped = [], []
    for r in rows:
        name = r["name"]
        cand = f"/img/{name}.png"
        if os.path.exists(os.path.join(IMG_DIR, f"{name}.png")):
            if r["image"] != cand:
                con.execute(
                    "UPDATE dishes SET image=? WHERE name=?",
                    (cand, name),
                )
                updated.append((name, r["image"], cand))
            else:
                skipped.append((name, "已正确，无需改"))
        else:
            skipped.append((name, f"无同名图，保持 {r['image']}"))

    con.commit()
    con.close()

    print(f"\n更新 {len(updated)} 道：")
    for u in updated:
        print(f"  {u[0]}: {u[1]}  ->  {u[2]}")
    print(f"\n跳过 {len(skipped)} 道：")
    for s in skipped:
        print(f"  {s[0]}: {s[1]}")


if __name__ == "__main__":
    main()
