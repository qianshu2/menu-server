"""用 Twemoji 彩色 SVG 生成彩色分类图标(矢量栅格化, 真彩色)。

- 下载 Twemoji SVG(按 emoji 码点)到临时目录
- svg2rlg + renderPM 栅格化为 96x96 透明 PNG, 覆盖 miniprogram/images/cats/ 下 10 个图标
"""
import os
import urllib.request
import fitz  # PyMuPDF
from PIL import Image

OUT = r"C:/Users/Administrator/WorkBuddy/Claw/miniprogram/images/cats"
SVG_DIR = r"C:/Users/Administrator/WorkBuddy/Claw/.cache_svg"
os.makedirs(SVG_DIR, exist_ok=True)

BASE = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/svg/{}.svg"

# 文件名 -> emoji 码点(hex)
ICONS = {
    "shaocai.png":   "1f373",  # 烧菜 🍳
    "liangcai.png":  "1f957",  # 凉菜 🥗
    "tanggeng.png":  "1f372",  # 汤羹 🍲
    "zhushi.png":    "1f35a",  # 主食 🍚
    "xiaochi.png":   "1f35f",  # 小吃 🍟
    "yinpin.png":    "1f964",  # 饮品 🥤
    "rechai.png":    "1f958",  # 热菜 🥘
    "zhengcai.png":  "1f95f",  # 蒸菜 🥟
    "haixian.png":   "1f990",  # 海鲜 🦐
    "tiaoliao.png":  "1f9c2",  # 调料 🧂
}


def download(cp):
    url = BASE.format(cp)
    path = os.path.join(SVG_DIR, cp + ".svg")
    if not os.path.exists(path):
        urllib.request.urlretrieve(url, path)
    return path


def render(fname, cp):
    svg = download(cp)
    doc = fitz.open(svg)
    page = doc.load_page(0)
    # 高倍渲染(144px)再缩到 96, 更清晰; 保留透明
    zoom = 144 / 36.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=True)
    out = os.path.join(OUT, fname)
    im = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    im = im.resize((96, 96), Image.LANCZOS)
    im.save(out)
    colors = len({(p[0], p[1], p[2]) for p in im.get_flattened_data() if p[3] > 10})
    print(f"{fname} ({cp}) -> 不透明像素:{sum(1 for p in im.get_flattened_data() if p[3]>10)}, 颜色数:{colors}")


if __name__ == "__main__":
    for fname, cp in ICONS.items():
        render(fname, cp)
