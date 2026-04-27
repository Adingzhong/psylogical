"""
N-back 指导语图片生成脚本 v7 — 所有内容居中
"""
import platform
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "assets" / "instruction"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
素材 = Path(__file__).resolve().parent.parent / "instruction_0310_1" / "素材库"

W, H = 1920, 1080
CX = W // 2  # 画布水平中心
BG = (245, 235, 217)
TITLE = (45, 85, 130)
ACCENT = (210, 85, 40)
TEXT = (60, 60, 60)
GREEN = (75, 175, 85)
YELLOW = (235, 175, 45)
RED = (220, 75, 65)
BLUE = (70, 140, 210)
ORANGE = (230, 150, 50)
ARROW = (210, 110, 40)
GRAY = (170, 170, 170)
WHITE = (255, 255, 255)
LIGHT_BG = (255, 245, 225)

if platform.system() == "Darwin":
    _F = "/System/Library/Fonts/STHeiti Medium.ttc"
else:
    _F = r"C:\Windows\Fonts\msyhbd.ttc"

def fnt(s): return ImageFont.truetype(_F, s)

def new_canvas():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def ct(draw, y, text, size, color=TITLE):
    f = fnt(size)
    bb = draw.textbbox((0, 0), text, font=f)
    draw.text(((W - bb[2] + bb[0]) // 2, y), text, font=f, fill=color)

def text_w(draw, text, size):
    f = fnt(size)
    bb = draw.textbbox((0, 0), text, font=f)
    return bb[2] - bb[0]

def load(path, h=None, w=None):
    img = Image.open(path).convert("RGBA")
    if h and img.height > h:
        r = h / img.height
        img = img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)
    if w and img.width > w:
        r = w / img.width
        img = img.resize((int(img.width * r), int(img.height * r)), Image.LANCZOS)
    return img

def paste(canvas, img, x, y, border=None, bw=4):
    if img.mode == "RGBA":
        bg = Image.new("RGBA", img.size, BG + (255,))
        bg.alpha_composite(img)
        img = bg.convert("RGB")
    canvas.paste(img, (x, y))
    if border:
        d = ImageDraw.Draw(canvas)
        d.rectangle((x - bw, y - bw, x + img.width + bw, y + img.height + bw), outline=border, width=bw)
    return img.width, img.height

def arrow_r(draw, x1, y, x2, color=ARROW, w=5):
    draw.line((x1, y, x2 - 15, y), fill=color, width=w)
    draw.polygon([(x2 - 15, y - 14), (x2 + 5, y), (x2 - 15, y + 14)], fill=color)

def btn(draw, x, y, w, h, text, bg, tc=WHITE):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 3, fill=bg)
    f = fnt(int(h * 0.48))
    bb = draw.textbbox((0, 0), text, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((x + (w - tw) // 2, y + (h - th) // 2 - 3), text, font=f, fill=tc)

def save(img, name):
    img.save(OUTPUT_DIR / name, quality=95)
    print(f"  -> {name}")


# ==================== 页面 ====================

def page_welcome():
    img, draw = new_canvas()
    DY = 100  # 垂直居中偏移
    ct(draw, 100 + DY, "欢迎参加本次测验", 66)
    items = ["接下来会看到一些图片", "请根据提示作答",
             "坐姿舒适，眼睛看屏幕中央", "慢一点没关系，尽量完成",
             "不确定也要选一个，不要空着"]
    max_tw = max(text_w(draw, it, 42) for it in items)
    list_x = CX - max_tw // 2
    dot_x = list_x - 40
    y = 270 + DY
    for it in items:
        draw.ellipse((dot_x, y + 14, dot_x + 24, y + 38), fill=BLUE)
        draw.text((dot_x + 40, y), it, font=fnt(42), fill=TEXT)
        y += 82
    ct(draw, 750 + DY, "不舒服随时告诉工作人员", 32, GRAY)
    save(img, "1.png")


def page_rest():
    img, draw = new_canvas()
    DY = 70
    ct(draw, 380 + DY, "休息一下", 80, TITLE)
    draw.line((CX - 200, 490 + DY, CX + 200, 490 + DY), fill=GRAY, width=2)
    ct(draw, 520 + DY, "准备好后点击继续", 38, GRAY)
    save(img, "2.png")


def page_b1():
    """B1: 0-back 和目标图比较 — 居中版"""
    img, draw = new_canvas()
    DY = 30
    # 部分标记
    draw.text((W - 220, 20), "第 1/4 部分", font=fnt(28), fill=GRAY)
    ct(draw, 20 + DY, "【第一步】记住目标图", 44, ACCENT)
    ct(draw, 78 + DY, "【第二步】每张图和目标图比较，判断关系", 44, ACCENT)

    content_y = 160 + DY

    target = load(素材 / "B1" / "G01_客厅基础.png", h=480)
    cmp_imgs = [load(素材 / "B1" / fn, h=340)
                for fn in ("G01_客厅基础.png", "G02_客厅相似.png", "G03_厨房不同.png")]

    gap_target_cmp = 50
    gap_between_cmp = 30
    total_cmp_w = sum(ci.width for ci in cmp_imgs) + gap_between_cmp * 2
    total_w = target.width + gap_target_cmp + total_cmp_w
    start_x = CX - total_w // 2

    tx = start_x
    paste(img, target, tx, content_y, BLUE, 6)
    draw.text((tx + 15, content_y - 36), "目标图", font=fnt(36), fill=BLUE)

    info = [("一致", GREEN, "完全一样"), ("相似", YELLOW, "有小变化"), ("不同", RED, "不是同一个")]
    cx_start = tx + target.width + gap_target_cmp
    for i, (ci, (lb, clr, desc)) in enumerate(zip(cmp_imgs, info)):
        x = cx_start + i * (ci.width + gap_between_cmp)
        paste(img, ci, x, content_y)
        mid = x + ci.width // 2

        ay = content_y + ci.height + 6
        draw.line((mid, ay, mid, ay + 28), fill=clr, width=5)
        draw.polygon([(mid - 12, ay + 28), (mid + 12, ay + 28), (mid, ay + 44)], fill=clr)
        btn(draw, mid - 100, ay + 52, 200, 72, lb, clr)
        f = fnt(26)
        bb = draw.textbbox((0, 0), desc, font=f)
        draw.text((mid - (bb[2] - bb[0]) // 2, ay + 136), desc, font=f, fill=TEXT)

    ct(draw, 910 + DY, "不确定也要选一个", 40, TEXT)
    save(img, "B1_1.png")


def page_b2():
    """B2: 1-back 和上一张比较 — 居中版"""
    img, draw = new_canvas()
    DY = 100
    draw.text((W - 220, 20), "第 2/4 部分", font=fnt(28), fill=GRAY)
    ct(draw, 25 + DY, "【重点：和上一张比较】", 48, ACCENT)
    ct(draw, 85 + DY, "图片一张一张出现，比较相邻两张", 36, TEXT)

    i1 = load(素材 / "B2" / "G04_书房.png", h=280)
    i2 = load(素材 / "B2" / "G06_餐厅.png", h=280)
    i3 = load(素材 / "B2" / "G05_卧室.png", h=280)

    arrow_gap = 80
    total_w = i1.width + arrow_gap + i2.width + arrow_gap + i3.width
    sx = CX - total_w // 2
    y0 = 190 + DY

    x1 = sx
    x2 = x1 + i1.width + arrow_gap
    x3 = x2 + i2.width + arrow_gap

    paste(img, i1, x1, y0)
    paste(img, i2, x2, y0, BLUE, 5)
    paste(img, i3, x3, y0, ORANGE, 5)

    draw.text((x1 + 20, y0 + i1.height + 10), "第1张 只看", font=fnt(28), fill=GRAY)
    draw.text((x2 + 40, y0 + i2.height + 15), "上一张", font=fnt(30), fill=BLUE)
    draw.text((x3 + 50, y0 + i3.height + 15), "当前", font=fnt(30), fill=ACCENT)

    arrow_r(draw, x1 + i1.width + 10, y0 + 140, x2 - 15)
    arrow_r(draw, x2 + i2.width + 10, y0 + 140, x3 - 15)

    draw.rounded_rectangle((x2 - 25, y0 - 35, x3 + i3.width + 25, y0 + i3.height + 55),
                           radius=22, outline=ORANGE, width=3)
    draw.text(((x2 + x3) // 2, y0 - 32), "比较这两张", font=fnt(26), fill=ACCENT)

    ct(draw, 580 + DY, "判断：这两张的关系是？", 40, TEXT)
    btn_w, btn_h, btn_gap = 220, 75, 60
    btn_total = 3 * btn_w + 2 * btn_gap
    bx = CX - btn_total // 2
    btn(draw, bx, 660 + DY, btn_w, btn_h, "一致", GREEN)
    btn(draw, bx + btn_w + btn_gap, 660 + DY, btn_w, btn_h, "相似", YELLOW)
    btn(draw, bx + 2 * (btn_w + btn_gap), 660 + DY, btn_w, btn_h, "不同", RED)
    ct(draw, 770 + DY, "不确定也要选一个", 36, TEXT)
    save(img, "B2_1.png")


def page_b3():
    """B3: Probe Recall — 居中版"""
    img, draw = new_canvas()
    DY = 55
    draw.text((W - 220, 20), "第 3/4 部分", font=fnt(28), fill=GRAY)
    ct(draw, 15 + DY, "【重点：看到提示图，回忆上一张】", 46, ACCENT)

    flow_y = 85 + DY
    flow_h = 175
    arrow_gap = 35

    cue = load(素材 / "B3" / "G07_Cue星标.png", h=flow_h)
    f1 = load(素材 / "B3" / "G09_走廊.png", h=flow_h)
    f2 = load(素材 / "B3" / "G08_浴室.png", h=flow_h)
    cue2 = load(素材 / "B3" / "G07_Cue星标.png", h=flow_h)

    flow_imgs = [cue, f1, f2, cue2]
    flow_total = sum(fi.width for fi in flow_imgs) + arrow_gap * 3 * 2
    flow_sx = CX - flow_total // 2

    labels_top = ["记住提示图", "图片一张张出现，只看", "", ""]
    labels_bot = ["提示图", "只看", "只看", "提示图出现!"]
    borders = [ACCENT, None, None, ACCENT]

    fx = flow_sx
    for i, fi in enumerate(flow_imgs):
        if i > 0:
            arrow_r(draw, fx - arrow_gap + 5, flow_y + flow_h // 2 + 25, fx - 5)
        if labels_top[i]:
            draw.text((fx, flow_y - 8), labels_top[i], font=fnt(22), fill=ACCENT if i == 0 else TEXT)
        paste(img, fi, fx, flow_y + 25, borders[i], 4 if borders[i] else 0)
        draw.text((fx + fi.width // 2 - 25, flow_y + flow_h + 30), labels_bot[i],
                  font=fnt(20), fill=ACCENT if borders[i] else GRAY)
        fx += fi.width + arrow_gap * 2

    draw.text((CX - 350, 340 + DY), "提示图出现后，从三张图中选出：", font=fnt(32), fill=TEXT)
    ct(draw, 390 + DY, "上一张是哪张？", 46, ACCENT)

    opt_h = 270
    o1 = load(素材 / "B3" / "G09_走廊.png", h=opt_h)
    o2 = load(素材 / "B3" / "G08_浴室.png", h=opt_h)
    o3 = load(素材 / "B1" / "G03_厨房不同.png", h=opt_h)

    opt_gap = 60
    opt_total = o1.width + o2.width + o3.width + opt_gap * 2
    osx = CX - opt_total // 2
    oy = 460 + DY

    opts = [(o1, None), (o2, GREEN), (o3, None)]
    ox = osx
    for i, (oi, bdr) in enumerate(opts):
        bw = 7 if bdr else 3
        bc = bdr if bdr else GRAY
        paste(img, oi, ox, oy, bc, bw)
        draw.text((ox + oi.width // 2 - 12, oy + oi.height + 8), str(i + 1), font=fnt(36), fill=TEXT)
        if bdr == GREEN:
            draw.rounded_rectangle((ox + oi.width // 2 - 50, oy + oi.height + 48,
                                    ox + oi.width // 2 + 50, oy + oi.height + 88),
                                   radius=10, fill=GREEN)
            draw.text((ox + oi.width // 2 - 28, oy + oi.height + 52), "正确", font=fnt(26), fill=WHITE)
        ox += oi.width + opt_gap

    ct(draw, 840 + DY, "浴室是提示图的前一张 → 选 2", 32, GREEN)
    ct(draw, 895 + DY, "不确定也要选一个", 36, TEXT)
    save(img, "B3_1.png")


def page_b4():
    """B4: 2-back — 居中版"""
    img, draw = new_canvas()
    DY = 40
    draw.text((W - 220, 20), "第 4/4 部分", font=fnt(28), fill=GRAY)
    ct(draw, 15 + DY, "【重点：跳过一张，和前两张比较】", 46, ACCENT)

    i1 = load(素材 / "B2" / "G04_书房.png", h=250)
    i2 = load(素材 / "B2" / "G06_餐厅.png", h=250)
    i3 = load(素材 / "B2" / "G04_书房.png", h=250)

    arrow_gap = 90
    total_w = i1.width + arrow_gap + i2.width + arrow_gap + i3.width
    sx = CX - total_w // 2
    y0 = 100 + DY

    x1 = sx
    x2 = x1 + i1.width + arrow_gap
    x3 = x2 + i2.width + arrow_gap

    paste(img, i1, x1, y0, BLUE, 5)
    paste(img, i2, x2, y0)
    draw.line((x2, y0, x2 + i2.width, y0 + i2.height), fill=(200, 180, 160), width=3)
    draw.line((x2 + i2.width, y0, x2, y0 + i2.height), fill=(200, 180, 160), width=3)
    paste(img, i3, x3, y0, BLUE, 5)

    draw.text((x1 + 20, y0 + i1.height + 12), "第1张", font=fnt(30), fill=BLUE)
    draw.text((x2 + 30, y0 + i2.height + 12), "第2张(跳过)", font=fnt(26), fill=GRAY)
    draw.text((x3 + 10, y0 + i3.height + 12), "第3张(当前)", font=fnt(30), fill=ACCENT)

    arrow_r(draw, x1 + i1.width + 15, y0 + 125, x2 - 25)
    arrow_r(draw, x2 + i2.width + 15, y0 + 125, x3 - 25)

    lx1 = x1 + i1.width // 2
    lx3 = x3 + i3.width // 2
    ly = y0 + i1.height + 50
    draw.line((lx1, ly, lx1, ly + 30), fill=BLUE, width=3)
    draw.line((lx1, ly + 30, lx3, ly + 30), fill=BLUE, width=4)
    draw.line((lx3, ly + 30, lx3, ly), fill=BLUE, width=3)
    mid_lx = (lx1 + lx3) // 2
    draw.rounded_rectangle((mid_lx - 80, ly + 10, mid_lx + 80, ly + 50), radius=12, fill=BLUE)
    draw.text((mid_lx - 38, ly + 13), "一样!", font=fnt(26), fill=WHITE)

    ry = 520 + DY
    rule_x = CX - 300
    draw.text((rule_x, ry), "一样", font=fnt(48), fill=GREEN)
    arrow_r(draw, rule_x + 150, ry + 28, rule_x + 250, GREEN)
    draw.text((rule_x + 270, ry - 5), "点", font=fnt(48), fill=TEXT)
    btn(draw, rule_x + 340, ry - 5, 200, 65, "匹配", GREEN)
    draw.text((rule_x + 560, ry), "按钮", font=fnt(48), fill=TEXT)

    draw.text((rule_x, ry + 90), "不一样", font=fnt(48), fill=RED)
    arrow_r(draw, rule_x + 200, ry + 118, rule_x + 250, RED)
    draw.text((rule_x + 270, ry + 85), "不操作，等下一张", font=fnt(48), fill=RED)

    draw.rounded_rectangle((CX - 400, 720 + DY, CX + 400, 790 + DY), radius=15, fill=LIGHT_BG)
    ct(draw, 730 + DY, "上面例子：第3张 = 第1张(都是书房) → 点匹配!", 34, GREEN)

    draw.rounded_rectangle((CX - 350, 820 + DY, CX + 350, 885 + DY), radius=15, fill=(255, 235, 215))
    ct(draw, 830 + DY, "记住：跳一张比！不是和上一张比！", 36, ACCENT)

    ct(draw, 920 + DY, "不确定也要按一下", 36, TEXT)
    save(img, "B4_1.png")


def main():
    print("生成 N-back 指导语图片 v7 (居中版)...")
    page_welcome()
    page_rest()
    page_b1()
    page_b2()
    page_b3()
    page_b4()
    print(f"完成！输出: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
