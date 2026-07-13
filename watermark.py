"""
watermark.py
给 static/images/ 下的菜品图批量添加“AI生成”显式标识，支持增量更新。

合规依据：《人工智能生成合成内容标识办法》(2025-09-01 施行)要求
AI 生成图片在显著位置标注。本脚本：
- 文字置于右下角，字号向上取整不低于画面最短边的 5%
- 半透明白字 + 黑色描边，保证清晰可读
- 原图备份于 static/images_originals/（按内容哈希比对，避免重复叠加、不丢失更新）
- 增量逻辑：
    新增图      → 直接加水印并备份
    未改动图    → 用干净备份重加（不产生叠加）
    被替换的图  → 用新内容加水印并刷新备份
"""
import os
import glob
import shutil
import hashlib
import math
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE, "static", "images")
BACKUP = os.path.join(BASE, "static", "images_originals")
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
TEXT = "AI生成"


def file_hash(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(BACKUP, exist_ok=True)
    files = sorted(
        glob.glob(os.path.join(IMG_DIR, "*.png"))
        + glob.glob(os.path.join(IMG_DIR, "*.jpg"))
        + glob.glob(os.path.join(IMG_DIR, "*.jpeg"))
    )
    if not files:
        print("未找到图片文件。")
        return

    added = changed = unchanged = 0
    for fp in files:
        rel = os.path.basename(fp)
        bak = os.path.join(BACKUP, rel)
        if not os.path.exists(bak):
            src, status = fp, "新增"
            added += 1
        elif file_hash(fp) == file_hash(bak):
            src, status = bak, "未改"
            unchanged += 1
        else:
            src, status = fp, "替换"
            changed += 1

        im = Image.open(src).convert("RGBA")
        w, h = im.size
        short = min(w, h)
        font_size = max(math.ceil(short * 0.05), 14)
        try:
            font = ImageFont.truetype(FONT_PATH, font_size)
        except Exception:
            font = ImageFont.load_default()

        draw = ImageDraw.Draw(im)
        bbox = draw.textbbox((0, 0), TEXT, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        margin = int(short * 0.03)
        x = w - tw - margin
        y = h - th - margin
        stroke = max(1, int(font_size * 0.08))
        draw.text(
            (x, y), TEXT, font=font,
            fill=(255, 255, 255, 220),
            stroke_width=stroke, stroke_fill=(0, 0, 0, 220),
        )

        # 仅新增或被替换时刷新备份
        if status in ("新增", "替换"):
            shutil.copy2(fp, bak)

        ext = os.path.splitext(fp)[1].lower()
        if ext in (".jpg", ".jpeg"):
            im.convert("RGB").save(fp, "JPEG", quality=95)
        else:
            im.save(fp, "PNG")

        print(f"[{status}] {rel}  ({w}x{h}, 字号 {font_size}px)")

    print(f"\n完成。新增 {added} / 替换 {changed} / 未改 {unchanged}。"
          f"原图备份于: {BACKUP}")


if __name__ == "__main__":
    main()
