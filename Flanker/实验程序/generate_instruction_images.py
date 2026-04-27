from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "instructions"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH = 1920
HEIGHT = 1080
BG = (0, 0, 0)
WHITE = (245, 245, 245)
YELLOW = (247, 236, 0)
CYAN = (122, 214, 255)
SOFT_GRAY = (165, 165, 165)
GREEN = (120, 220, 120)
RED = (255, 110, 110)
BOX_RED = (255, 80, 80)
ACCENT = (255, 70, 170)
BLUE_FILL = (28, 66, 89)
GREEN_FILL = (28, 72, 40)
LEFT_KEY_X = 300
RIGHT_KEY_X = 1450
KEYCAP_Y = 830
LEFT_COL_X = 300
LEFT_BODY_X = 335
RIGHT_STIM_X = 1320

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
ARIAL_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
ARROWS_DIR = BASE_DIR / "arrows"


def font(size: int, bold: bool = False, family: str = "yahei") -> ImageFont.FreeTypeFont:
    if family == "arial":
        return ImageFont.truetype(ARIAL_BOLD, size=size)
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size=size)


def new_canvas():
    image = Image.new("RGBA", (WIDTH, HEIGHT), BG + (255,))
    draw = ImageDraw.Draw(image)
    return image, draw


def draw_text(draw, xy, text, size, fill, bold=False, anchor="la"):
    draw.text(xy, text, font=font(size, bold=bold), fill=fill, anchor=anchor)


def draw_centered_segments(draw, center_x, y, segments, gap=8):
    metrics = []
    total_width = 0
    for text, size, fill, bold in segments:
        f = font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=f, anchor="la")
        width = bbox[2] - bbox[0]
        metrics.append((text, size, fill, bold, width))
        total_width += width
    total_width += gap * max(0, len(metrics) - 1)
    x = center_x - total_width / 2
    for text, size, fill, bold, width in metrics:
        draw_text(draw, (x, y), text, size, fill, bold=bold, anchor="la")
        x += width + gap


def draw_paragraph(draw, start_x, start_y, lines, gap=26):
    y = start_y
    for item in lines:
        draw_text(draw, (start_x, y), item["text"], item["size"], item["color"], bold=item.get("bold", False))
        y += item["size"] + gap
    return y


def draw_keycap(draw, x, y, key, caption, border, fill):
    draw.rounded_rectangle((x, y, x + 170, y + 150), radius=18, outline=border, width=4, fill=fill)
    draw_text(draw, (x + 85, y + 54), key, 78, WHITE, bold=True, anchor="mm")
    draw_text(draw, (x + 85, y + 112), caption, 22, WHITE, bold=True, anchor="mm")


def draw_stimulus_row(draw, center_x, y, symbols, colors, label, label_mode="below"):
    spacing = 95
    center_y = y + 36
    arrow_font = font(72, bold=True, family="arial")
    for idx, symbol in enumerate(symbols):
        symbol_x = center_x + (idx - 2) * spacing
        draw.text((symbol_x, center_y), symbol, font=arrow_font, fill=colors[idx], anchor="mm")

    draw.rounded_rectangle((center_x - 46, center_y - 48, center_x + 46, center_y + 48), radius=12, outline=BOX_RED, width=5)
    if label_mode == "right":
        draw_text(draw, (center_x + 115, center_y), label, 30, BOX_RED, bold=True, anchor="lm")
    else:
        draw_text(draw, (center_x, center_y + 76), label, 28, BOX_RED, bold=True, anchor="mm")


def draw_material_stimulus(image, draw, center_x, y, relative_parts, label):
    stim_path = ARROWS_DIR.joinpath(*relative_parts)
    stim = Image.open(stim_path).convert("RGBA")
    target_w = 430
    target_h = 72
    scale = min(target_w / stim.width, target_h / stim.height)
    new_size = (max(1, int(stim.width * scale)), max(1, int(stim.height * scale)))
    stim = stim.resize(new_size)
    top_left = (int(center_x - new_size[0] / 2), int(y))
    image.alpha_composite(stim, dest=top_left)

    center_y = y + new_size[1] / 2
    box_w = max(82, int(new_size[0] * 0.17))
    box_h = max(78, int(new_size[1] * 0.92))
    draw.rounded_rectangle(
        (
            int(center_x - box_w / 2),
            int(center_y - box_h / 2),
            int(center_x + box_w / 2),
            int(center_y + box_h / 2),
        ),
        radius=12,
        outline=BOX_RED,
        width=5,
    )
    draw_text(draw, (center_x, int(center_y + box_h / 2 + 32)), label, 28, BOX_RED, bold=True, anchor="mm")


def footer(draw, text):
    draw_text(draw, (WIDTH // 2, 1028), text, 34, WHITE, bold=True, anchor="mm")


def save(image, name):
    image.convert("RGB").save(OUTPUT_DIR / name)


def page_01():
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 112), "欢迎参加箭头挑战", 62, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 190), "您的任务是：判断中间箭头的朝向，并尽可能又快又准地按键。", 38, WHITE, bold=True, anchor="ma")
    draw_text(draw, (220, 270), "请记住下面 3 个重点：", 34, CYAN, bold=True)

    left_x = LEFT_COL_X
    body_x = LEFT_BODY_X
    stim_center_x = RIGHT_STIM_X
    row1_y = 345
    row2_y = 495
    row3_y = 645

    draw_text(draw, (left_x, row1_y), "1. 只看中间箭头", 40, ACCENT, bold=True)
    draw_text(draw, (body_x, row1_y + 42), "看到一排箭头时，请把注意力放在正中间。", 29, WHITE, bold=True)

    draw_text(draw, (left_x, row2_y), "2. 两边箭头可能干扰您，但它们不重要", 34, ACCENT, bold=True)
    draw_text(draw, (body_x, row2_y + 40), "两侧内容只会造成干扰，不需要根据它们作答。", 29, WHITE, bold=True)

    draw_text(draw, (left_x, row3_y), "3. 出现黄色箭头时，也只看中间箭头方向", 34, ACCENT, bold=True)
    draw_text(draw, (body_x, row3_y + 40), "颜色变化不改变规则，仍然只判断中间箭头。", 29, WHITE, bold=True)

    draw_material_stimulus(image, draw, stim_center_x, row1_y - 8, ("中性", "c1.png"), "还是看中间箭头")
    draw_material_stimulus(image, draw, stim_center_x, row2_y - 8, ("不一致", "a2.png"), "请注意中间箭头")
    draw_material_stimulus(image, draw, stim_center_x, row3_y - 8, ("不一致-pop", "Y1.png"), "颜色不重要")
    draw_keycap(draw, LEFT_KEY_X, KEYCAP_Y, "Q", "箭头朝左按Q", CYAN, BLUE_FILL)
    draw_keycap(draw, RIGHT_KEY_X, KEYCAP_Y, "P", "箭头朝右按P", GREEN, GREEN_FILL)
    footer(draw, "请按空格键继续")
    save(image, "01_welcome_intro.png")


def page_02():
    image, draw = new_canvas()
    draw_text(draw, (360, 470), "练习阶段", 96, ACCENT, bold=True, anchor="mm")
    draw_text(draw, (360, 585), "请先熟悉规则", 84, ACCENT, bold=True, anchor="mm")
    draw_text(draw, (360, 715), "请按空格键开始练习", 38, WHITE, bold=True, anchor="mm")
    right_center_x = 1320
    draw_text(draw, (right_center_x, 235), "练习时请这样做", 44, ACCENT, bold=True, anchor="ma")
    draw_material_stimulus(image, draw, right_center_x, 320, ("中性", "c2.png"), "按 Q")
    draw_material_stimulus(image, draw, right_center_x, 520, ("中性", "c1.png"), "按 P")
    draw_centered_segments(draw, right_center_x, 735, [("中间箭头朝左  按", 34, WHITE, True), ("Q", 38, ACCENT, True), ("键", 34, WHITE, True)])
    draw_centered_segments(draw, right_center_x, 790, [("中间箭头朝右  按", 34, WHITE, True), ("P", 38, ACCENT, True), ("键", 34, WHITE, True)])
    draw_centered_segments(draw, right_center_x, 850, [("先看准，再逐渐加快速度", 36, WHITE, True)])
    save(image, "02_practice_start.png")


def page_03():
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 112), "练习结束", 62, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 190), "请记住正式实验前最重要的 3 点。", 38, WHITE, bold=True, anchor="ma")
    draw_text(draw, (LEFT_COL_X, 330), "1. 只判断中间箭头的朝向", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 374), "看到一排刺激时，先找到正中间。", 29, WHITE, bold=True)
    draw_text(draw, (LEFT_COL_X, 500), "2. 忽略两侧箭头", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 544), "两侧内容只会造成干扰，不需要理会。", 29, WHITE, bold=True)
    draw_text(draw, (LEFT_COL_X, 670), "3. 忽略颜色变化", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 714), "即使出现黄色箭头，也仍然只看中间箭头。", 29, WHITE, bold=True)
    draw_material_stimulus(image, draw, RIGHT_STIM_X, 325, ("不一致", "a2.png"), "只看中间箭头")
    draw_material_stimulus(image, draw, RIGHT_STIM_X, 495, ("不一致", "a1.png"), "忽略两侧箭头")
    draw_material_stimulus(image, draw, RIGHT_STIM_X, 665, ("一致-pop", "5a.png"), "忽略颜色")
    draw_keycap(draw, LEFT_KEY_X, KEYCAP_Y, "Q", "箭头朝左按Q", CYAN, BLUE_FILL)
    draw_keycap(draw, RIGHT_KEY_X, KEYCAP_Y, "P", "箭头朝右按P", GREEN, GREEN_FILL)
    footer(draw, "请按空格键继续")
    save(image, "03_practice_end.png")


def page_04():
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 112), "练习正确率未达到 70%", 58, RED, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 190), "请再练习一次，并重点记住下面 3 点。", 38, WHITE, bold=True, anchor="ma")
    draw_text(draw, (LEFT_COL_X, 330), "1. 先看中间箭头", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 374), "不要先去看两侧箭头。", 29, WHITE, bold=True)
    draw_text(draw, (LEFT_COL_X, 500), "2. 中间箭头朝左时按【Q】键", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 544), "请把 Q 键和“左”牢牢记住。", 29, WHITE, bold=True)
    draw_text(draw, (LEFT_COL_X, 670), "3. 中间箭头朝右时按【P】键", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 714), "请把 P 键和“右”牢牢记住。", 29, WHITE, bold=True)
    draw_material_stimulus(image, draw, RIGHT_STIM_X, 325, ("不一致", "a2.png"), "先看中间箭头")
    draw_material_stimulus(image, draw, RIGHT_STIM_X, 495, ("中性", "c2.png"), "按 Q")
    draw_material_stimulus(image, draw, RIGHT_STIM_X, 665, ("中性", "c1.png"), "按 P")
    draw_keycap(draw, LEFT_KEY_X, KEYCAP_Y, "Q", "箭头朝左按Q", CYAN, BLUE_FILL)
    draw_keycap(draw, RIGHT_KEY_X, KEYCAP_Y, "P", "箭头朝右按P", GREEN, GREEN_FILL)
    footer(draw, "请按空格键重新练习")
    save(image, "04_practice_retry.png")


def page_05():
    image, draw = new_canvas()
    draw_text(draw, (360, 470), "正式实验", 96, ACCENT, bold=True, anchor="mm")
    draw_text(draw, (360, 585), "即将开始", 96, ACCENT, bold=True, anchor="mm")
    draw_text(draw, (360, 715), "请按空格键开始游戏", 38, WHITE, bold=True, anchor="mm")
    right_center_x = 1320
    draw_text(draw, (right_center_x, 235), "只关注中间箭头朝向", 44, ACCENT, bold=True, anchor="ma")
    draw_material_stimulus(image, draw, right_center_x, 320, ("中性", "c2.png"), "按 Q")
    draw_material_stimulus(image, draw, right_center_x, 520, ("中性", "c1.png"), "按 P")
    draw_centered_segments(draw, right_center_x, 735, [("中间箭头朝左  按", 34, WHITE, True), ("Q", 38, ACCENT, True), ("键", 34, WHITE, True)])
    draw_centered_segments(draw, right_center_x, 790, [("中间箭头朝右  按", 34, WHITE, True), ("P", 38, ACCENT, True), ("键", 34, WHITE, True)])
    draw_centered_segments(draw, right_center_x, 850, [("尽量快速作答，保持准确", 36, WHITE, True)])
    save(image, "05_formal_start.png")


def page_06():
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 112), "休息时间到了", 62, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 215), "请为自己刚刚的专注程度打一个分。", 38, WHITE, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 430), "请按数字键【1-9】评分", 40, ACCENT, bold=True, anchor="ma")
    for i in range(1, 10):
        x = 624 + (i - 1) * 82
        fill = (64, 64, 64)
        border = WHITE
        draw.rounded_rectangle((x, 540, x + 68, 626), radius=12, outline=border, width=3, fill=fill)
        draw_text(draw, (x + 34, 583), str(i), 42, WHITE, bold=True, anchor="mm")
    draw_text(draw, (658, 675), "1分表示极其不专注", 30, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (1314, 675), "9分表示非常专注", 30, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 980), "按空格键继续实验", 36, WHITE, bold=True, anchor="ma")
    save(image, "06_break_rating.png")


def page_07():
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 360), "实验结束", 72, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 480), "感谢您的参与！", 50, WHITE, bold=True, anchor="ma")
    save(image, "07_finish.png")


def main():
    page_01()
    page_02()
    page_03()
    page_04()
    page_05()
    page_06()
    page_07()
    print(f"Instruction images generated in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
