"""
fix_jpg_images.py
把菜单里以 .jpg 结尾的图片统一转成 .png，并同步更新 menu.db 的 image 字段。
原因：menu_server.serve_image 按文件名精确读取 static/images/，而数据库里
「可乐」「冰镇柠檬水」的 image 字段指向 .jpg，文件也是 .jpg，但项目约定
默认按 .png 拼路径，容易造成前端加载不到。转为 png 后保持一致。
"""
import sqlite3
import os
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "static", "images")
DB = os.path.join(BASE, "menu.db")


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT name, image FROM dishes WHERE image LIKE '%.jpg'"
    ).fetchall()

    changed = []
    for r in rows:
        old_rel = r["image"].lstrip("/")          # e.g. img/可乐.jpg
        old_path = os.path.join(IMG_DIR, os.path.basename(old_rel))
        if not os.path.exists(old_path):
            print(f"SKIP (文件不存在): {old_path}")
            continue

        new_rel = os.path.splitext(old_rel)[0] + ".png"
        new_path = os.path.join(IMG_DIR, os.path.basename(new_rel))

        with Image.open(old_path) as im:
            im.convert("RGB").save(new_path, "PNG")
        os.remove(old_path)

        con.execute(
            "UPDATE dishes SET image=? WHERE name=?",
            (new_rel, r["name"]),
        )
        changed.append((r["name"], old_rel, new_rel))
        print(f"OK  {r['name']}: {old_rel} -> {new_rel}")

    con.commit()
    con.close()

    if not changed:
        print("没有需要转换的 .jpg 图片。")
    else:
        print(f"\n共转换 {len(changed)} 张，数据库字段已同步。")


if __name__ == "__main__":
    main()
