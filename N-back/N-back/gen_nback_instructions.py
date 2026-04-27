"""
用 Pillow 生成 N-back 指导语图片(参考 instruction_0310_1 设计)
运行: python3 gen_nback_instructions.py
输出到 assets/instruction/
"""
import os, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SCRIPT_DIR = Path(__file__).parent
OUT = SCRIPT_DIR / "assets" / "instruction"
ASSETS = Path(__file__).parent.parent / "instruction_0310_1" / "素材库"

W, H = 1920, 1080

# 颜色系统(参考设计文档)
BG_WARM = (255, 248, 235)       # 温暖米色背景
BG_HEADER = (70, 100, 140)      # 深蓝标题栏
WHITE = (255, 255, 255)
BLACK = (50, 50, 50)
GRAY = (130, 130, 130)
LGRAY = (200, 200, 200)
BLUE = (33, 150, 243)           # 标注蓝
ORANGE = (255, 152, 0)          # 标注橙
GREEN_BTN = (76, 175, 80)       # 一致按钮
YELLOW_BTN = (255, 193, 7)      # 相似按钮
RED_BTN = (244, 67, 54)         # 不同按钮
BROWN = (90, 70, 55)            # 正文深棕

# 字体
def find_font(size, bold=False):
    import platform
    candidates = []
    if platform.system() == "Darwin":
        base = "/System/Library/Fonts"
        if bold:
            candidates = [f"{base}/STHeiti Medium.ttc", f"{base}/PingFang.ttc"]
        else:
            candidates = [f"{base}/STHeiti Light.ttc", f"{base}/STHeiti Medium.ttc",
                          f"{base}/PingFang.ttc"]
    else:
        base = "C:/Windows/Fonts"
        candidates = [f"{base}/msyhbd.ttc" if bold else f"{base}/msyh.ttc",
                      f"{base}/simhei.ttf"]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except:
                continue
    return ImageFont.load_default()

TITLE_FONT = find_font(64, bold=True)
SUBTITLE_FONT = find_font(44, bold=True)
BODY_FONT = find_font(40)
BODY_BOLD = find_font(42, bold=True)
BTN_FONT = find_font(44, bold=True)
HINT_FONT = find_font(32)
SMALL_FONT = find_font(28)
LABEL_FONT = find_font(34, bold=True)

# 工具函数
def new_card(bg=BG_WARM):
    return Image.new("RGB", (W, H), bg)

def center_text(draw, text, y, font, color=BLACK):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, fill=color, font=font)

def draw_rounded_rect(draw, xy, fill, radius=16):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)

def draw_button(draw, cx, cy, w, h, color, label, font=BTN_FONT):
    x0, y0 = cx - w // 2, cy - h // 2
    draw_rounded_rect(draw, (x0, y0, x0 + w, y0 + h), fill=color, radius=14)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2 - 2), label, fill=WHITE, font=font)

def load_illustration(name, size=(280, 280)):
    """加载漫画素材并缩放"""
    path = ASSETS / name
    if path.exists():
        img = Image.open(path).convert("RGBA")
        img = img.resize(size, Image.LANCZOS)
        return img
    return None

def paste_img(canvas, img, pos):
    if img and img.mode == "RGBA":
        canvas.paste(img, pos, img)
    elif img:
        canvas.paste(img, pos)

def draw_arrow_h(draw, x1, y, x2, color=BLUE, width=5):
    """水平箭头"""
    draw.line([(x1, y), (x2, y)], fill=color, width=width)
    sz = 16
    if x2 > x1:
        draw.polygon([(x2, y), (x2 - sz, y - sz // 2), (x2 - sz, y + sz // 2)], fill=color)
    else:
        draw.polygon([(x2, y), (x2 + sz, y - sz // 2), (x2 + sz, y + sz // 2)], fill=color)

def draw_img_frame(draw, x, y, w, h, color=BLUE, width=4, label=None, label_font=LABEL_FONT):
    """给图片画边框+标签"""
    draw.rectangle([x - 4, y - 4, x + w + 4, y + h + 4], outline=color, width=width)
    if label:
        bbox = draw.textbbox((0, 0), label, font=label_font)
        tw = bbox[2] - bbox[0]
        center_text(draw, label, y + h + 10, label_font, color=color)

def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name, quality=95)
    print(f"  -> {name}")

# ================================================================
# 1. 总开始页
# ================================================================
def gen_welcome():
    img = new_card()
    d = ImageDraw.Draw(img)

    # 标题
    center_text(d, "欢迎参加本次测验", 60, TITLE_FONT, color=BG_HEADER)

    # 要点列表 -- 居中布局
    points = [
        "接下来会看到一些图片",
        "请根据提示作答",
        "坐姿舒适，眼睛看屏幕中央",
        "慢一点没关系，尽量完成",
        "不确定也要选一个，不要空着",
    ]
    dot_radius = 15
    dot_text_gap = 30  # 圆点右侧到文字的间距
    y = 220
    for text in points:
        # 测量文字宽度，以圆点+文字整体居中
        bbox = d.textbbox((0, 0), text, font=BODY_FONT)
        tw = bbox[2] - bbox[0]
        total_w = dot_radius * 2 + dot_text_gap + tw
        start_x = (W - total_w) // 2
        # 圆点
        d.ellipse([start_x, y + 8, start_x + dot_radius * 2, y + 8 + dot_radius * 2], fill=BLUE)
        # 文字
        d.text((start_x + dot_radius * 2 + dot_text_gap, y), text, fill=BROWN, font=BODY_FONT)
        y += 80

    # 底部提示
    center_text(d, "不舒服随时告诉工作人员", 750, HINT_FONT, color=GRAY)

    # 继续按钮

    save(img, "1.png")

# ================================================================
# 2. 休息页
# ================================================================
def gen_rest():
    img = new_card()
    d = ImageDraw.Draw(img)

    center_text(d, "休息一下", 200, TITLE_FONT, color=BG_HEADER)

    # 茶杯图标(简单绘制)
    cx, cy = W // 2, 480
    # 杯身
    d.rounded_rectangle([cx - 80, cy - 60, cx + 80, cy + 60], radius=20,
                         fill=(240, 220, 190), outline=(200, 170, 120), width=4)
    # 杯把
    d.arc([cx + 70, cy - 30, cx + 130, cy + 30], 270, 90,
          fill=(200, 170, 120), width=5)
    # 蒸汽
    for dx in [-25, 0, 25]:
        d.arc([cx + dx - 15, cy - 110, cx + dx + 15, cy - 70], 0, 180,
              fill=(200, 180, 150), width=3)

    center_text(d, "准备好后点击继续", 680, BODY_FONT, color=GRAY)


    save(img, "2.png")

# ================================================================
# 3. B1 指导页(0-back：和目标图比较)
# ================================================================
def gen_B1():
    img = new_card()
    d = ImageDraw.Draw(img)

    # 标题
    center_text(d, "【第一步】记住目标图", 30, SUBTITLE_FONT, color=BG_HEADER)
    center_text(d, "【第二步】每张图和目标图比较，判断关系", 90, SUBTITLE_FONT, color=BG_HEADER)

    # 加载漫画素材
    living_base = load_illustration("B1/G01_客厅基础.png", (260, 260))
    living_sim = load_illustration("B1/G02_客厅相似.png", (220, 220))
    kitchen = load_illustration("B1/G03_厨房不同.png", (220, 220))

    # 目标图(左侧大图+蓝框)
    target_x, target_y = 120, 180
    d.text((target_x, target_y - 5), "目标图", fill=BLUE, font=LABEL_FONT)
    paste_img(img, living_base, (target_x, target_y + 40))
    if living_base:
        draw_img_frame(d, target_x, target_y + 40, 260, 260, color=BLUE, width=5)

    # 三张对比图 + 箭头 + 按钮
    examples = [
        (living_base, "一致", GREEN_BTN, "完全一样"),
        (living_sim, "相似", YELLOW_BTN, "有小变化"),
        (kitchen, "不同", RED_BTN, "不是同一个"),
    ]
    start_x = 550
    for i, (ill, btn_label, btn_color, desc) in enumerate(examples):
        ex = start_x + i * 420
        ey = 220

        # 图片
        paste_img(img, ill, (ex + 20, ey))
        if ill:
            bw = ill.size[0] if ill else 220
            bh = ill.size[1] if ill else 220

        # 箭头指向按钮
        arrow_y = ey + 240
        d.text((ex + 30, arrow_y), "↓", fill=btn_color, font=TITLE_FONT)

        # 按钮
        draw_button(d, ex + 110, arrow_y + 100, 200, 70, btn_color, btn_label)

        # 说明
        center_text_x = ex + 110
        bbox = d.textbbox((0, 0), desc, font=SMALL_FONT)
        tw = bbox[2] - bbox[0]
        d.text((center_x := ex + 110 - tw // 2, arrow_y + 150), desc, fill=GRAY, font=SMALL_FONT)

    # 底部提示
    center_text(d, "不确定也要选一个", 920, BODY_FONT, color=BROWN)

    # 继续按钮

    save(img, "B1_1.png")

# ================================================================
# 4. B2 指导页(1-back：和上一张比较)
# ================================================================
def gen_B2():
    img = new_card()
    d = ImageDraw.Draw(img)

    # 标题（简化）
    center_text(d, "和上一张比较", 40, TITLE_FONT, color=BG_HEADER)
    center_text(d, "图片一张一张出现，比较相邻两张", 120, BODY_FONT, color=BROWN)

    # 加载素材
    bedroom = load_illustration("B2/G05_卧室.png", (200, 200))
    kitchen = load_illustration("B2/G06_餐厅.png", (200, 200))
    study = load_illustration("B2/G04_书房.png", (200, 200))

    # 第1张（灰色，标注"只看"）
    x1, y1 = 150, 220
    paste_img(img, bedroom, (x1, y1))
    draw_img_frame(d, x1, y1, 200, 200, color=LGRAY, width=3)
    d.text((x1 + 60, y1 + 210), "只看", fill=GRAY, font=LABEL_FONT)

    # 箭头1→2
    draw_arrow_h(d, x1 + 220, y1 + 100, x1 + 350, color=GRAY, width=4)

    # 第2张和第3张放在一个大框里，表示"比较这两张"
    bracket_x = x1 + 370
    bracket_y = 190
    # 大括号背景
    d.rounded_rectangle([bracket_x - 15, bracket_y, bracket_x + 1080, bracket_y + 340],
                         radius=16, fill=None, outline=ORANGE, width=4)
    d.text((bracket_x + 350, bracket_y - 5), "比较这两张", fill=ORANGE, font=BODY_BOLD)

    # 第2张（蓝框，上一张）
    x2 = bracket_x + 50
    y2 = bracket_y + 50
    paste_img(img, kitchen, (x2, y2))
    draw_img_frame(d, x2, y2, 200, 200, color=BLUE, width=4)
    d.text((x2 + 30, y2 + 210), "上一张", fill=BLUE, font=LABEL_FONT)

    # 箭头2→3
    draw_arrow_h(d, x2 + 240, y2 + 100, x2 + 440, color=ORANGE, width=5)

    # VS文字
    d.text((x2 + 310, y2 + 70), "VS", fill=ORANGE, font=TITLE_FONT)

    # 第3张（橙框，当前）
    x3 = x2 + 500
    paste_img(img, study, (x3, y2))
    draw_img_frame(d, x3, y2, 200, 200, color=ORANGE, width=4)
    d.text((x3 + 45, y2 + 210), "当前", fill=ORANGE, font=LABEL_FONT)

    # 判断说明
    center_text(d, "判断：这两张的关系是？", 600, BODY_BOLD, color=BROWN)

    # 三个按钮
    btn_y = 730
    draw_button(d, 450, btn_y, 240, 75, GREEN_BTN, "一致")
    draw_button(d, 800, btn_y, 240, 75, YELLOW_BTN, "相似")
    draw_button(d, 1150, btn_y, 240, 75, RED_BTN, "不同")

    center_text(d, "不确定也要选一个", 830, BODY_FONT, color=BROWN)

    save(img, "B2_1.png")

# ================================================================
# 5. B3 指导页(1-back probe：看到提示图，回忆上一张)
# ================================================================
def gen_B3():
    img = new_card()
    d = ImageDraw.Draw(img)

    center_text(d, "【重点：看到提示图，回忆上一张】", 30, SUBTITLE_FONT, color=BG_HEADER)

    # 加载素材
    cue = load_illustration("B3/G07_Cue星标.png", (200, 200))
    bathroom = load_illustration("B3/G08_浴室.png", (200, 200))
    hallway = load_illustration("B3/G09_走廊.png", (200, 200))

    # 步骤1：记住提示图
    d.text((100, 110), "1. 开始前先记住这张提示图", fill=BROWN, font=BODY_BOLD)
    paste_img(img, cue, (150, 170))
    if cue:
        draw_img_frame(d, 150, 170, 200, 200, color=(255, 215, 0), width=5)
    d.text((140, 385), "提示图", fill=(255, 180, 0), font=LABEL_FONT)

    # 步骤2：图片一张张出现，只看
    d.text((500, 110), "2. 然后图片一张张出现，只需要看", fill=BROWN, font=BODY_BOLD)
    seq_imgs = [bathroom, hallway, bathroom]
    seq_labels = ["只看", "只看", "只看"]
    for i, (si, sl) in enumerate(zip(seq_imgs, seq_labels)):
        sx = 520 + i * 240
        paste_img(img, si, (sx, 180))
        if i < 2:
            draw_arrow_h(d, sx + 210, 280, sx + 230, color=ORANGE, width=4)
        d.text((sx + 70, 390), sl, fill=GRAY, font=SMALL_FONT)

    # 步骤3：提示图再次出现时，选出上一张
    d.text((100, 450), "3. 当提示图再次出现时", fill=BROWN, font=BODY_BOLD)
    paste_img(img, cue, (150, 510))
    if cue:
        draw_img_frame(d, 150, 510, 200, 200, color=(255, 215, 0), width=4)

    draw_arrow_h(d, 370, 610, 500, color=ORANGE, width=5)

    d.text((520, 470), "从三张图中选出：上一张是哪张？", fill=BROWN, font=BODY_BOLD)

    # 三个选项
    options = [bathroom, hallway, cue]
    opt_labels = ["1", "2", "3"]
    correct_idx = 0  # bathroom是正确答案(提示图前一张)
    for i, (oi, ol) in enumerate(zip(options, opt_labels)):
        ox = 530 + i * 280
        paste_img(img, oi, (ox, 540))
        if oi:
            border_color = GREEN_BTN if i == correct_idx else LGRAY
            border_w = 5 if i == correct_idx else 2
            draw_img_frame(d, ox, 540, 200, 200, color=border_color, width=border_w)
        # 编号
        d.text((ox + 90, 750), ol, fill=BLACK, font=LABEL_FONT)

    # 正确标记
    d.text((530 + correct_idx * 280 + 50, 780), "✓ 正确", fill=GREEN_BTN, font=LABEL_FONT)

    center_text(d, "不确定也要选一个", 880, BODY_FONT, color=BROWN)


    save(img, "B3_1.png")

# ================================================================
# 6. B4 指导页(2-back：和前两张比较)
# ================================================================
def gen_B4():
    img = new_card()
    d = ImageDraw.Draw(img)

    center_text(d, "【重点：和前两张比较】", 40, SUBTITLE_FONT, color=BG_HEADER)

    # 用B2的素材做示意
    bedroom = load_illustration("B2/G05_卧室.png", (200, 200))
    kitchen = load_illustration("B2/G06_餐厅.png", (200, 200))
    study = load_illustration("B2/G04_书房.png", (200, 200))

    # 时间轴演示
    imgs_seq = [
        (bedroom, "第1张", GRAY),
        (kitchen, "第2张", GRAY),
        (bedroom, "第3张(当前)", ORANGE),
    ]
    for i, (ill, label, color) in enumerate(imgs_seq):
        ix = 200 + i * 520
        iy = 200
        paste_img(img, ill, (ix, iy))
        if ill:
            draw_img_frame(d, ix, iy, 200, 200, color=color, width=4)
        bbox = d.textbbox((0, 0), label, font=LABEL_FONT)
        tw = bbox[2] - bbox[0]
        d.text((ix + 100 - tw // 2, iy + 210), label, fill=color, font=LABEL_FONT)
        if i < 2:
            draw_arrow_h(d, ix + 220, iy + 100, ix + 500, color=ORANGE, width=4)

    # 对比说明
    d.rounded_rectangle([300, 460, 1620, 540], radius=12, fill=(255, 240, 220))
    center_text(d, '比较 当前 和 前两张(第1张) 是否相同', 475, BODY_BOLD, color=ORANGE)

    # 规则
    center_text(d, '相同 --> 按 匹配 按钮', 590, BODY_FONT, color=GREEN_BTN)
    center_text(d, '不同 --> 不操作', 660, BODY_FONT, color=RED_BTN)

    # 注意
    d.rounded_rectangle([500, 740, 1420, 820], radius=12, fill=(240, 248, 255))
    center_text(d, '注意：前两张 不是 上一张！', 755, BODY_BOLD, color=BLUE)

    center_text(d, "不确定也要按一下", 870, BODY_FONT, color=BROWN)


    save(img, "B4_1.png")

# ================================================================
if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    print("生成 N-back 指导语图片...")
    gen_welcome()
    gen_rest()
    gen_B1()
    gen_B2()
    gen_B3()
    gen_B4()
    print(f"\n全部完成！输出: {OUT}")
