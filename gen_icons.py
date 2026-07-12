from PIL import Image, ImageDraw, ImageFont
import os

# 菜系 → emoji图标 + 配色
cats = {
    "shaocai":  ("🍖", "烧菜", (255, 107, 53)),
    "liangcai": ("🥗", "凉菜", (76, 175, 80)),
    "tanggeng": ("🍜", "汤羹", (255, 152, 0)),
    "zhushi":   ("🍚", "主食", (255, 193, 7)),
    "xiaochi":  ("🥟", "小吃", (233, 30, 99)),
    "yinpin":   ("🥤", "饮品", (33, 150, 243)),
}

size = 96
out = "miniprogram/images/cats"
os.makedirs(out, exist_ok=True)

# 加载中文字体（用于小号标签文字）
label_font = None
for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf",
           "C:/Windows/Fonts/simhei.ttf"]:
    if os.path.exists(fp):
        try:
            label_font = ImageFont.truetype(fp, 14)
            break
        except Exception:
            continue
if label_font is None:
    label_font = ImageFont.load_default()

# 尝试加载 emoji 字体（Windows 用 Segoe UI Emoji）
emoji_font = None
for fp in ["C:/Windows/Fonts/seguiemj.ttf", "C:/Windows/Fonts/Segoe UI Emoji.ttf",
           "C:/Windows/Fonts/seguisym.ttf"]:
    if os.path.exists(fp):
        try:
            emoji_font = ImageFont.truetype(fp, 44)
            break
        except Exception:
            continue
if emoji_font is None:
    emoji_font = ImageFont.load_default()


def draw_icon(emoji, label, color):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 浅色圆角背景
    r, g, b = color
    bg_color = (r, g, b, 35)          # 很淡的底色
    border_color = (r, g, b, 80)       # 淡边框
    d.rounded_rectangle([2, 2, size - 2, size - 2], radius=20, fill=bg_color)
    d.rounded_rectangle([2, 2, size - 2, size - 2], radius=20, outline=border_color, width=2)

    # 居中绘制 emoji（大号）
    bbox = d.textbbox((0, 0), emoji, font=emoji_font)
    ew, eh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    ex = (size - ew) / 2 - bbox[0]
    ey = (size - eh) / 2 - bbox[1] - 6   # 稍微上移，给文字留空间
    d.text((ex, ey), emoji, font=emoji_font, fill=(0, 0, 0, 230))

    # 底部小号文字标签
    lbbox = d.textbbox((0, 0), label, font=label_font)
    lw, lh = lbbox[2] - lbbox[0], lbbox[3] - lbbox[1]
    lx = (size - lw) / 2 - lbbox[0]
    ly = size - lh - 8 - lbbox[1]
    d.text((lx, ly), label, font=label_font, fill=(80, 80, 80, 220))

    return img


for key, (emoji, label, color) in cats.items():
    img = draw_icon(emoji, label, color)
    img.save(os.path.join(out, key + ".png"))

# 兜底图标
img = draw_icon("📋", "其他", (150, 150, 150))
img.save(os.path.join(out, "default.png"))

print("icons generated:", os.listdir(out))
