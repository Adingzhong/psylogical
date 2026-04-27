"""
Flanker 触摸版指导语图片生成脚本
生成 9 张指导语/反馈图片，文案适配触摸按钮操作（无 Q/P/空格键引用）。
用法: python generate_instruction_images.py
"""
import os
import platform
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
GREEN = (120, 220, 120)
RED = (255, 110, 110)
BOX_RED = (255, 80, 80)
ACCENT = (255, 70, 170)
BLUE_FILL = (28, 66, 89)
GREEN_FILL = (28, 72, 40)
SOFT_GRAY = (165, 165, 165)
LEFT_COL_X = 300
LEFT_BODY_X = 335
RIGHT_STIM_X = 1320

ARROWS_DIR = BASE_DIR / "arrows"

# --- 跨平台字体 ---
if platform.system() == "Darwin":
    _CN_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
    _CN_FONT_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"  # Mac 无单独粗体文件
    _ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
else:
    _CN_FONT = r"C:\Windows\Fonts\msyh.ttc"
    _CN_FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
    _ARIAL_BOLD = r"C:\Windows\Fonts\arialbd.ttf"


def font(size: int, bold: bool = False, family: str = "cn") -> ImageFont.FreeTypeFont:
    if family == "arial":
        return ImageFont.truetype(_ARIAL_BOLD, size=size)
    return ImageFont.truetype(_CN_FONT_BOLD if bold else _CN_FONT, size=size)


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


def draw_centered_segments_middle(draw, center_x, center_y, segments, gap=8):
    metrics = []
    total_width = 0
    for text, size, fill, bold in segments:
        f = font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=f, anchor="lt")
        width = bbox[2] - bbox[0]
        metrics.append((text, size, fill, bold, width))
        total_width += width
    total_width += gap * max(0, len(metrics) - 1)
    x = center_x - total_width / 2
    for text, size, fill, bold, width in metrics:
        draw_text(draw, (x, center_y), text, size, fill, bold=bold, anchor="lm")
        x += width + gap


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
        (int(center_x - box_w / 2), int(center_y - box_h / 2),
         int(center_x + box_w / 2), int(center_y + box_h / 2)),
        radius=12, outline=BOX_RED, width=5,
    )
    if label:
        draw_text(draw, (center_x, int(center_y + box_h / 2 + 32)), label, 28, BOX_RED, bold=True, anchor="mm")


def save(image, name):
    image.convert("RGB").save(OUTPUT_DIR / name)
    print(f"  -> {name}")


# ===================== 各页面 =====================

def page_01():
    """欢迎页：介绍任务 + 左右按钮操作"""
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 118), "欢迎参加箭头朝向挑战！", 66, ACCENT, bold=True, anchor="ma")
    draw_centered_segments(draw, WIDTH // 2, 210,
                           [("只判断", 34, WHITE, True), ("中间", 48, WHITE, True), ("箭头方向", 34, WHITE, True)], gap=4)

    # 三个刺激示例
    top_y = 330
    draw_material_stimulus(image, draw, 380, top_y, ("中性", "c1.png"), "只看中间的箭头")
    draw_material_stimulus(image, draw, 960, top_y, ("不一致", "a1.png"), "两侧箭头不要看")
    draw_material_stimulus(image, draw, 1540, top_y, ("不一致-pop", "Y1.png"), "还是只看中间箭头")

    # 底部：左右按钮映射
    text_y = 720
    draw_centered_segments_middle(draw, 430, text_y,
                                  [("箭头朝", 34, WHITE, True), ("左", 46, ACCENT, True),
                                   ("点", 34, WHITE, True), ("左", 46, ACCENT, True), ("按钮", 34, WHITE, True)], gap=8)
    draw_centered_segments_middle(draw, 1490, text_y,
                                  [("箭头朝", 34, WHITE, True), ("右", 46, ACCENT, True),
                                   ("点", 34, WHITE, True), ("右", 46, ACCENT, True), ("按钮", 34, WHITE, True)], gap=8)
    draw_material_stimulus(image, draw, 430, 800, ("中性", "c2.png"), "")
    draw_material_stimulus(image, draw, 1490, 800, ("中性", "c1.png"), "")
    save(image, "01.png")


def page_02():
    """练习阶段说明"""
    image, draw = new_canvas()
    draw_text(draw, (360, 470), "练习阶段", 96, ACCENT, bold=True, anchor="mm")
    draw_text(draw, (360, 585), "请先熟悉规则", 84, ACCENT, bold=True, anchor="mm")

    right_cx = 1320
    draw_text(draw, (right_cx, 235), "练习时请这样做", 44, ACCENT, bold=True, anchor="ma")
    draw_material_stimulus(image, draw, right_cx, 320, ("中性", "c2.png"), "点 左")
    draw_material_stimulus(image, draw, right_cx, 520, ("中性", "c1.png"), "点 右")
    draw_centered_segments(draw, right_cx, 735,
                           [("中间箭头朝左  点", 34, WHITE, True), ("左", 38, ACCENT, True), ("按钮", 34, WHITE, True)])
    draw_centered_segments(draw, right_cx, 790,
                           [("中间箭头朝右  点", 34, WHITE, True), ("右", 38, ACCENT, True), ("按钮", 34, WHITE, True)])
    draw_centered_segments(draw, right_cx, 850, [("先看准，再逐渐加快速度", 36, WHITE, True)])
    save(image, "02_practice_start.png")


def page_03():
    """练习结束，进入正式实验前的提醒"""
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
    # 不再绘制 keycap 和 footer
    save(image, "03.png")


def page_04():
    """练习未达标，重试说明"""
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 112), "练习正确率未达到 70%", 58, RED, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 190), "请再练习一次，并重点记住下面 3 点。", 38, WHITE, bold=True, anchor="ma")

    draw_text(draw, (LEFT_COL_X, 330), "1. 先看中间箭头", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 374), "不要先去看两侧箭头。", 29, WHITE, bold=True)
    draw_text(draw, (LEFT_COL_X, 500), "2. 中间箭头朝左时点左按钮", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 544), '请把"左按钮"和"左"牢牢记住。', 29, WHITE, bold=True)
    draw_text(draw, (LEFT_COL_X, 670), "3. 中间箭头朝右时点右按钮", 40, ACCENT, bold=True)
    draw_text(draw, (LEFT_BODY_X, 714), '请把"右按钮"和"右"牢牢记住。', 29, WHITE, bold=True)

    draw_material_stimulus(image, draw, RIGHT_STIM_X, 325, ("不一致", "a2.png"), "先看中间箭头")
    draw_material_stimulus(image, draw, RIGHT_STIM_X, 495, ("中性", "c2.png"), "点 左")
    draw_material_stimulus(image, draw, RIGHT_STIM_X, 665, ("中性", "c1.png"), "点 右")
    # 不再绘制 keycap 和 footer
    save(image, "04_practice_retry.png")


def page_05():
    """正式实验即将开始"""
    image, draw = new_canvas()
    draw_text(draw, (360, 470), "正式实验", 96, ACCENT, bold=True, anchor="mm")
    draw_text(draw, (360, 585), "即将开始", 96, ACCENT, bold=True, anchor="mm")

    right_cx = 1320
    draw_text(draw, (right_cx, 235), "只关注中间箭头朝向", 44, ACCENT, bold=True, anchor="ma")
    draw_material_stimulus(image, draw, right_cx, 320, ("中性", "c2.png"), "点 左")
    draw_material_stimulus(image, draw, right_cx, 520, ("中性", "c1.png"), "点 右")
    draw_centered_segments(draw, right_cx, 735,
                           [("中间箭头朝左  点", 34, WHITE, True), ("左", 38, ACCENT, True), ("按钮", 34, WHITE, True)])
    draw_centered_segments(draw, right_cx, 790,
                           [("中间箭头朝右  点", 34, WHITE, True), ("右", 38, ACCENT, True), ("按钮", 34, WHITE, True)])
    draw_centered_segments(draw, right_cx, 850, [("尽量快速作答，保持准确", 36, WHITE, True)])
    save(image, "05_formal_start.png")


def page_06():
    """休息 + 专注评分"""
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 112), "休息时间到了", 62, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 215), "请为自己刚刚的专注程度打一个分。", 38, WHITE, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 430), "请点击数字按钮评分", 40, ACCENT, bold=True, anchor="ma")

    for i in range(1, 10):
        x = 624 + (i - 1) * 82
        fill = (64, 64, 64)
        draw.rounded_rectangle((x, 540, x + 68, 626), radius=12, outline=WHITE, width=3, fill=fill)
        draw_text(draw, (x + 34, 583), str(i), 42, WHITE, bold=True, anchor="mm")
    draw_text(draw, (658, 675), "1分表示极其不专注", 30, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (1314, 675), "9分表示非常专注", 30, ACCENT, bold=True, anchor="ma")
    # 不再有"按空格键继续"
    save(image, "06_break_rating.png")


def page_07():
    """实验结束"""
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 360), "实验结束", 72, ACCENT, bold=True, anchor="ma")
    draw_text(draw, (WIDTH // 2, 480), "感谢您的参与！", 50, WHITE, bold=True, anchor="ma")
    save(image, "07.png")


def page_feedback_left():
    """练习错误反馈：应该点左按钮"""
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 340), "X", 90, RED, bold=True, anchor="mm")
    draw_text(draw, (WIDTH // 2, 420), "错误", 60, RED, bold=True, anchor="mm")
    draw_centered_segments_middle(draw, WIDTH // 2, 560,
                                  [("中间箭头朝", 48, WHITE, True), ("左", 56, ACCENT, True),
                                   ("时，应该点", 48, WHITE, True), ("左", 56, ACCENT, True), ("按钮", 48, WHITE, True)], gap=6)
    save(image, "q.png")


def page_feedback_right():
    """练习错误反馈：应该点右按钮"""
    image, draw = new_canvas()
    draw_text(draw, (WIDTH // 2, 340), "X", 90, RED, bold=True, anchor="mm")
    draw_text(draw, (WIDTH // 2, 420), "错误", 60, RED, bold=True, anchor="mm")
    draw_centered_segments_middle(draw, WIDTH // 2, 520,
                                  [("中间箭头朝", 48, WHITE, True), ("右", 56, ACCENT, True),
                                   ("时，应该点", 48, WHITE, True), ("右", 56, ACCENT, True), ("按钮", 48, WHITE, True)], gap=6)
    save(image, "p.png")


def main():
    print("生成 Flanker 触摸版指导语图片...")
    page_01()
    page_02()
    page_03()
    page_04()
    page_05()
    page_06()
    page_07()
    page_feedback_left()
    page_feedback_right()
    print(f"完成！输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
