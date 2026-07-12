from PIL import Image, ImageDraw, ImageFont
import os

cats = {
    "shaocai":  ("烧菜", (255, 107, 53)),
    "liangcai": ("凉菜", (76, 175, 80)),
    "tanggeng": ("汤羹", (255, 152, 0)),
    "zhushi":   ("主食", (255, 193, 7)),
    "xiaochi":  ("小吃", (233, 30, 99)),
    "yinpin":   ("饮品", (33, 150, 243)),
}

size = 96
out = "miniprogram/images/cats"
os.makedirs(out, exist_ok=True)

# 尝试加载中文字体
font = None
for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf",
           "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]:
    if os.path.exists(fp):
        try:
            font = ImageFont.truetype(fp, 30)
            break
        except Exception:
            continue
if font is None:
    font = ImageFont.load_default()


def draw_label(img, label, fill):
    d = ImageDraw.Draw(img)
    bbox = d.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1]
    d.text((x, y), label, font=font, fill=fill)


for key, (label, color) in cats.items():
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, size - 4, size - 4], radius=22, fill=color + (255,))
    draw_label(img, label, (255, 255, 255, 255))
    img.save(os.path.join(out, key + ".png"))

# 兜底图标（分类无对应图标时使用）
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([4, 4, size - 4, size - 4], radius=22, fill=(190, 190, 190, 255))
draw_label(img, "菜", (255, 255, 255, 255))
img.save(os.path.join(out, "default.png"))

print("icons generated:", os.listdir(out))
