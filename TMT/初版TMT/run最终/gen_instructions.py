"""
用 Pillow 生成 TMT 全部指导语图片 (v2 — 垂直居中)
运行: python3 gen_instructions.py
输出到 stimuli/zdy/
"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "stimuli" / "zdy"
W, H = 1640, 920
CY = H // 2  # 画布垂直中心 = 460
BG = (245, 245, 245)
BLACK = (40, 40, 40)
GRAY = (120, 120, 120)
LGRAY = (180, 180, 180)
RED = (220, 60, 60)
BLUE = (50, 120, 210)
GREEN = (50, 160, 80)
YELLOW = (230, 190, 40)

# ---- 字体 ----
def find_font(size, bold=False):
    import platform
    candidates = []
    if platform.system() == "Darwin":
        base = "/System/Library/Fonts"
        candidates = [
            f"{base}/STHeiti Medium.ttc",
            f"{base}/STHeiti Light.ttc",
            f"{base}/Hiragino Sans GB.ttc",
            f"{base}/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:
        base = "C:/Windows/Fonts"
        candidates = [
            f"{base}/msyh.ttc",
            f"{base}/msyhbd.ttc",
            f"{base}/simhei.ttf",
        ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

TITLE_FONT = find_font(72, bold=True)
BODY_FONT = find_font(48)
HINT_FONT = find_font(28)
SMALL_FONT = find_font(36)
NODE_FONT = find_font(40, bold=True)
NODE_FONT_SM = find_font(32)

# ---- 绘制工具 ----
def new_card():
    return Image.new("RGB", (W, H), BG)

def draw_title(draw, text, y=80, color=BLACK):
    bbox = draw.textbbox((0, 0), text, font=TITLE_FONT)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, fill=color, font=TITLE_FONT)

def draw_body(draw, text, y=None, color=BLACK, font=None):
    if font is None:
        font = BODY_FONT
    lines = text.split("\n")
    if y is None:
        total_h = len(lines) * 65
        y = (H - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, y), line, fill=color, font=font)
        y += 65

def draw_circle(draw, cx, cy, r, fill=None, outline=BLUE, width=3):
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fill, outline=outline, width=width)

def draw_arrow(draw, x1, y1, x2, y2, color=BLUE, width=4):
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    sz = 14
    draw.polygon([
        (x2, y2),
        (x2 - sz * math.cos(angle - 0.4), y2 - sz * math.sin(angle - 0.4)),
        (x2 - sz * math.cos(angle + 0.4), y2 - sz * math.sin(angle + 0.4)),
    ], fill=color)

def draw_node_label(draw, cx, cy, text, font=NODE_FONT, color=BLACK):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 4), text, fill=color, font=font)

def save(img, name):
    img.save(OUT / name, quality=95)
    print(f"  -> {name}")

# ================================================================
# 通用页面
# ================================================================

def gen_welcome():
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 150
    draw_title(d, "欢迎参加连线测试", y=80 + DY)
    draw_body(d, "这不是考试，没有对错\n请放轻松，随时可以休息\n如果不舒服请告诉工作人员", y=320 + DY, color=GRAY)
    save(img, "all_1.png")

def gen_howto():
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 50
    draw_title(d, "操作方法", y=80 + DY)
    nodes = [(450, 420 + DY), (820, 320 + DY), (820, 530 + DY)]
    for i, (x, y) in enumerate(nodes):
        draw_circle(d, x, y, 45, fill=(220, 230, 245), outline=BLUE, width=4)
        draw_node_label(d, x, y, str(i + 1))
    draw_arrow(d, 495, 410 + DY, 775, 330 + DY)
    draw_arrow(d, 820, 365 + DY, 820, 485 + DY)
    d.polygon([(400, 370 + DY), (420, 340 + DY), (440, 370 + DY)], fill=GRAY)
    d.rectangle([415, 370 + DY, 425, 410 + DY], fill=GRAY)
    draw_body(d, "手指按住圆点，划线连到下一个\n尽量不抬手，一笔连完", y=600 + DY, color=BLACK)
    save(img, "1.png")

def gen_practice_intro():
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 170
    draw_title(d, "先来练习一下", y=80 + DY)
    draw_body(d, "接下来试试连  1 → 2 → 3 → 4", y=400 + DY)
    save(img, "all_2.png")

def gen_formal_start():
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 160
    draw_title(d, "练习结束！", y=80 + DY)
    draw_body(d, "接下来进入正式测试\n连错了系统会提示，回到正确的点继续", y=370 + DY, color=GRAY)
    save(img, "2.png")

def gen_rest():
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 60
    draw_title(d, "休息一下", y=250 + DY)
    draw_body(d, "放松眼睛和手", y=420 + DY, color=GRAY)
    save(img, "3.png")
    save(img, "all_3.png")
    for prefix in ["A0_2", "A1_2", "B1_2", "B2_2", "B3_2", "B4_2"]:
        save(img, f"{prefix}.png")

def gen_end():
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 85
    draw_title(d, "测试结束！", y=220 + DY)
    draw_body(d, "感谢您的参与！\n如有不适或疑问请告诉工作人员", y=400 + DY, color=GRAY)
    save(img, "all_4.png")

# ================================================================
# 任务指导语（含示意图）
# ================================================================

def gen_A0():
    """A0: 按数字顺序连线 1→2→3→4→5→6"""
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 80
    draw_title(d, "按数字顺序连线", y=80 + DY)
    positions = [(300, 350 + DY), (500, 250 + DY), (700, 400 + DY),
                 (900, 280 + DY), (1100, 450 + DY), (1300, 300 + DY)]
    for i, (x, y) in enumerate(positions):
        draw_circle(d, x, y, 40, fill=(220, 235, 255), outline=BLUE, width=3)
        draw_node_label(d, x, y, str(i + 1))
    for i in range(len(positions) - 1):
        x1, y1 = positions[i]
        x2, y2 = positions[i + 1]
        draw_arrow(d, x1 + 35, y1, x2 - 35, y2, color=BLUE, width=3)
    draw_body(d, "从 1 开始，按顺序连到 6", y=550 + DY)
    save(img, "A0_1.png")

def gen_A1():
    """A1: 水果上的数字，按数字顺序连线"""
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 70
    draw_title(d, "按水果上的数字连线", y=80 + DY)
    fruits = [
        (350, 380 + DY, RED, "苹果", "1"),
        (600, 340 + DY, YELLOW, "柠檬", "2"),
        (850, 400 + DY, RED, "苹果", "3"),
        (1100, 350 + DY, YELLOW, "柠檬", "4"),
    ]
    for x, y, color, label, num in fruits:
        draw_circle(d, x, y, 50, fill=color, outline=color, width=2)
        draw_node_label(d, x, y, num, color=(255, 255, 255))
        d.text((x - 24, y + 55), label, fill=GRAY, font=SMALL_FONT)
    for i in range(len(fruits) - 1):
        x1, y1 = fruits[i][0], fruits[i][1]
        x2, y2 = fruits[i + 1][0], fruits[i + 1][1]
        draw_arrow(d, x1 + 45, y1, x2 - 45, y2, color=BLUE, width=3)
    draw_body(d, "只看数字，不管水果种类", y=570 + DY)
    save(img, "A1_1.png")

def gen_B1():
    """B1: 数字和汉字交替 1→一→2→二→3→三"""
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 55
    draw_title(d, "数字和汉字交替连线", y=80 + DY)
    top_nodes = [(350, 300 + DY, "1"), (700, 300 + DY, "2"), (1050, 300 + DY, "3")]
    bot_nodes = [(525, 500 + DY, "一"), (875, 500 + DY, "二"), (1225, 500 + DY, "三")]
    for x, y, label in top_nodes:
        draw_circle(d, x, y, 42, fill=(220, 235, 255), outline=BLUE, width=3)
        draw_node_label(d, x, y, label)
    for x, y, label in bot_nodes:
        draw_circle(d, x, y, 42, fill=(255, 240, 220), outline=(200, 130, 50), width=3)
        draw_node_label(d, x, y, label)
    path = [top_nodes[0], bot_nodes[0], top_nodes[1], bot_nodes[1], top_nodes[2], bot_nodes[2]]
    for i in range(len(path) - 1):
        x1, y1 = path[i][0], path[i][1]
        x2, y2 = path[i + 1][0], path[i + 1][1]
        draw_arrow(d, x1 + 30, y1 + 20, x2 - 30, y2 - 20, color=BLUE, width=3)
    draw_body(d, "数字、汉字交替着连", y=600 + DY)
    save(img, "B1_1.png")

def gen_B2():
    """B2: 方形和圆形交替 □1→○2→□3→○4"""
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 90
    draw_title(d, "方形和圆形交替连线", y=80 + DY)
    items = [
        (280, 400 + DY, "square", "1"),
        (560, 400 + DY, "circle", "2"),
        (840, 400 + DY, "square", "3"),
        (1120, 400 + DY, "circle", "4"),
    ]
    for x, y, shape, num in items:
        if shape == "square":
            d.rectangle([x-42, y-42, x+42, y+42], fill=(220, 235, 255), outline=BLUE, width=3)
        else:
            draw_circle(d, x, y, 42, fill=(255, 235, 220), outline=(200, 100, 50), width=3)
        draw_node_label(d, x, y, num)
    for i in range(len(items) - 1):
        x1, y1 = items[i][0], items[i][1]
        x2, y2 = items[i + 1][0], items[i + 1][1]
        draw_arrow(d, x1 + 45, y1, x2 - 45, y2, color=BLUE, width=3)
    draw_body(d, "方形、圆形交替着连", y=580 + DY)
    save(img, "B2_1.png")

def gen_B3():
    """B3: 两种水果交替 苹果1→柠檬1→苹果2→柠檬2→苹果3→柠檬3"""
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 40
    draw_title(d, "两种水果交替连线", y=80 + DY)
    top = [(350, 310 + DY, "1"), (700, 310 + DY, "2"), (1050, 310 + DY, "3")]
    bot = [(525, 510 + DY, "1"), (875, 510 + DY, "2"), (1225, 510 + DY, "3")]
    for x, y, num in top:
        draw_circle(d, x, y, 42, fill=RED, outline=RED, width=2)
        draw_node_label(d, x, y, num, color=(255, 255, 255))
        d.text((x - 24, y - 75), "苹果", fill=GRAY, font=SMALL_FONT)
    for x, y, num in bot:
        draw_circle(d, x, y, 42, fill=YELLOW, outline=YELLOW, width=2)
        draw_node_label(d, x, y, num, color=BLACK)
        d.text((x - 24, y + 50), "柠檬", fill=GRAY, font=SMALL_FONT)
    path = [top[0], bot[0], top[1], bot[1], top[2], bot[2]]
    for i in range(len(path) - 1):
        x1, y1 = path[i][0], path[i][1]
        x2, y2 = path[i + 1][0], path[i + 1][1]
        draw_arrow(d, x1 + 30, y1 + 25, x2 - 30, y2 - 25, color=BLUE, width=3)
    draw_body(d, "两种水果交替着连", y=630 + DY)
    save(img, "B3_1.png")

def gen_B4():
    """B4: 两种水果上的数字交替"""
    img = new_card()
    d = ImageDraw.Draw(img)
    DY = 70
    draw_title(d, "两种水果上的数字交替连线", y=80 + DY)
    items = [
        (300, 400 + DY, RED, "苹果1"),
        (540, 400 + DY, YELLOW, "柠檬1"),
        (780, 400 + DY, RED, "苹果2"),
        (1020, 400 + DY, YELLOW, "柠檬2"),
        (1260, 400 + DY, RED, "苹果3"),
    ]
    for x, y, color, label in items:
        draw_circle(d, x, y, 45, fill=color, outline=color, width=2)
        num = label[-1]
        draw_node_label(d, x, y, num, color=(255, 255, 255) if color == RED else BLACK)
        d.text((x - 36, y + 50), label[:2], fill=GRAY, font=NODE_FONT_SM)
    for i in range(len(items) - 1):
        x1, y1 = items[i][0], items[i][1]
        x2, y2 = items[i + 1][0], items[i + 1][1]
        draw_arrow(d, x1 + 40, y1, x2 - 40, y2, color=BLUE, width=3)
    draw_body(d, "按数字顺序，两种水果交替", y=570 + DY)
    save(img, "B4_1.png")

# ================================================================
if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print("生成TMT指导语图片 v2 (垂直居中)...")
    gen_welcome()
    gen_howto()
    gen_practice_intro()
    gen_formal_start()
    gen_rest()
    gen_end()
    gen_A0()
    gen_A1()
    gen_B1()
    gen_B2()
    gen_B3()
    gen_B4()
    print(f"\n全部完成！输出目录: {OUT}")
