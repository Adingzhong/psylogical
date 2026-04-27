# -*- coding: utf-8 -*-
"""
run_B4.py  (B4 = 2-back，按固定键/按钮)

✅ 设计目标（与你们项目一致）
- 单流呈现：图片一张一张出现（stim）
- 规则：如果"当前图片"与"前 2 张图片"完全相同 → 需要按下【固定键】或点击【固定按钮】
- 多数 trial 是不匹配（No-Go），少数为匹配（Go）
- 练习：给出对错反馈（单独反馈页）
- 正式：不反馈，用注视点空屏分隔（让被试知道 trial 在推进）
- 支持：键盘 + 触屏/鼠标（iPad/电脑都能用）

✅ 风格统一（对齐 B1/B2/B3）
- fullscr=True
- 背景深灰 BG=[-0.9,-0.9,-0.9]，白字
- 字体：微软雅黑（可替换）
- 鼠标指针可见（便于调试；触屏直接点按钮）

List 文件：
- 默认读取：../lists/B4_ListA.csv   （或 B4_ListB.csv / B4_ListC.csv）
- 列名（建议保持一致）：
  trial_index, phase, n, image, cond, correct, stim_dur, resp_deadline, isi, feedback

说明：
- correct:
    - "press" 代表该 trial 需要按键/点按钮（target）
    - "none" 代表该 trial 不应反应（foil）
    - "na"   代表 warmup（前 n 张）不计分
- resp_deadline：从刺激 onset 开始的最大反应窗口（秒）
  - 在窗口内：前 stim_dur 秒显示图片；剩余时间显示注视点（按钮仍保留，方便触屏作答）

独立运行：
  python run_B4.py
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from psychopy import visual, event, core, gui

import sys as _sys

def _get_cjk_font():
    if _sys.platform == "darwin":
        for f in ["Heiti SC", "STHeiti", "PingFang SC", "Hiragino Sans GB"]:
            try:
                from matplotlib.font_manager import findfont, FontProperties
                if findfont(FontProperties(family=f)) != findfont(FontProperties()):
                    return f
            except Exception:
                pass
        return "Heiti SC"
    else:
        return "Microsoft YaHei"

CJK_FONT = _get_cjk_font()

# ----------------------------
# 统一风格
# ----------------------------
BG = [-0.9, -0.9, -0.9]
FG = "white"
FONT_CN = CJK_FONT

# 固定反应键（调试用；触屏/鼠标用按钮）
RESPONSE_KEYS = ["j", "f", "num_1"]  # 任意一个都算"按下"

# 过场页推进（对齐 B1/B2/B3：空格或点击屏幕继续 + 最短等待）
ADVANCE_MIN_S = 0.8
ALLOW_SCREEN_CLICK = True

# 指导语图片（相对项目根目录）
INSTR_IMAGE_B4 = "assets/instruction/B4_1.png"

# 按下后的确认高亮与锁定（秒）
CONFIRM_S = 0.15

# 预加载图片（减少卡顿）
PRELOAD_IMAGES = True

# 正式阶段可选提示：仅在"应按但未按"时短闪（默认关闭）
SHOW_TIMEOUT_MAIN = False
TIMEOUT_FLASH_S_MAIN = 0.4


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _abs_path(p: str, root: Path) -> Path:
    p = (p or "").strip().lstrip("\ufeff")
    if p == "" or p.lower() == "nan":
        return Path("")
    pp = Path(p)
    return pp if pp.is_absolute() else (root / pp)


def _to_float(x: str, default: float) -> float:
    try:
        return float(str(x).strip())
    except Exception:
        return default


def _to_int(x: str, default: int) -> int:
    try:
        return int(float(str(x).strip()))
    except Exception:
        return default

def _to_bool(x: Any, default: bool) -> bool:
    s = str(x).strip().lower()
    if s in ["1", "true", "yes", "y", "on"]:
        return True
    if s in ["0", "false", "no", "n", "off"]:
        return False
    return default



def _norm_phase(s: str) -> str:
    s = (s or "").strip().lower()
    if s in ["practice", "练习"]:
        return "practice"
    if s in ["main", "formal", "正式"]:
        return "main"
    return "main"


def _norm_correct(s: str) -> str:
    s = (s or "").strip().lower()
    if s in ["press", "hit", "go", "1", "true"]:
        return "press"
    if s in ["none", "no", "nogo", "0", "false"]:
        return "none"
    if s in ["na", "warmup", ""]:
        return "na"
    return s


@dataclass
class Trial:
    trial_index: int
    phase: str              # practice/main
    n: int                  # 2
    image: Path
    cond: str               # warmup/target/foil（仅记录）
    correct: str            # press/none/na
    stim_dur: float
    resp_deadline: float    # 0 代表无反应窗口（warmup）
    isi: float
    feedback: int           # 1=练习反馈


def load_trials(list_name: str) -> List[Trial]:
    root = _project_root()
    list_path = root / "lists" / f"B4_{list_name}.csv"
    if not list_path.exists():
        raise FileNotFoundError(f"找不到 list：{list_path}")

    trials: List[Trial] = []
    with list_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV 没有表头。")

        fieldnames = [fn.strip().lstrip("\ufeff") for fn in reader.fieldnames]
        reader.fieldnames = fieldnames

        for row in reader:
            if row is None:
                continue
            vals = [(str(v).strip() if v is not None else "") for v in row.values()]
            if all(v == "" or v.lower() == "nan" for v in vals):
                continue

            tid = _to_int(row.get("trial_index", len(trials) + 1), len(trials) + 1)
            phase = _norm_phase(row.get("phase", "main"))
            n = _to_int(row.get("n", 2), 2)
            img = _abs_path(row.get("image", ""), root)
            cond = (row.get("cond", "") or "").strip().lower()
            correct = _norm_correct(row.get("correct", "na"))

            t = Trial(
                trial_index=tid,
                phase=phase,
                n=n,
                image=img,
                cond=cond,
                correct=correct,
                stim_dur=_to_float(row.get("stim_dur", 1.0), 1.0),
                resp_deadline=_to_float(row.get("resp_deadline", 0.0), 0.0),
                isi=_to_float(row.get("isi", 0.25), 0.25),
                feedback=_to_int(row.get("feedback", 0), 0),
            )
            trials.append(t)

    # 基本检查：避免空路径直接崩
    for t in trials:
        if t.image == Path("") or str(t.image).strip() == "":
            raise ValueError(f"trial_index={t.trial_index} 的 image 为空。")
        if not t.image.exists():
            raise FileNotFoundError(f"图片不存在：{t.image}")
        if t.n < 1:
            raise ValueError(f"trial_index={t.trial_index} 的 n 不合法：{t.n}")

    return trials


# ----------------------------
# UI / 页面
# ----------------------------
def _text(win: visual.Window, s: str, y: float = 0, h: float = 34, align: str = "center") -> visual.TextStim:
    return visual.TextStim(
        win, text=s, color=FG, height=h, pos=(0, y),
        font=FONT_CN, units="pix", wrapWidth=int(win.size[0] * 0.90),
        alignText=align
    )


def wait_advance_with_draw(
    win: visual.Window,
    drawables: List[Any],
    min_wait_s: float = 0.0,
    allow_space: bool = True,
    allow_click: bool = True,
) -> None:
    """等待推进：空格 或 点击屏幕底部中央按钮区域；支持最短等待时间（防误触一闪而过）。"""
    mouse = event.Mouse(win=win, visible=True)

    # 防止按住鼠标导致秒过
    while any(mouse.getPressed()):
        core.wait(0.01)

    event.clearEvents()
    clk = core.Clock()

    while True:
        if allow_space:
            keys = event.getKeys(keyList=["space", "escape"])
            if "escape" in keys:
                core.quit()
            if "space" in keys and clk.getTime() >= min_wait_s:
                return
        else:
            if "escape" in event.getKeys(["escape"]):
                core.quit()

        if allow_click and mouse.getPressed()[0] and clk.getTime() >= min_wait_s:
            while any(mouse.getPressed()):
                core.wait(0.01)
            return

        for d in drawables:
            d.draw()
        win.flip()


def show_page(
    win: visual.Window,
    body: str,
    footer: str = "按屏幕继续",
    min_wait_s: float = ADVANCE_MIN_S,
    allow_click: bool = ALLOW_SCREEN_CLICK,
):
    """纯文字过场页：正文+提示 作为一个整体上下对称居中；空格/点击继续 + 最短等待。"""
    win_w, win_h = win.size
    n_lines = max(1, body.count("\n") + 1)

    # 行数越少，字号越大（适老）
    if n_lines <= 3:
        body_h = int(win_h * 0.070)
    elif n_lines <= 6:
        body_h = int(win_h * 0.055)
    elif n_lines <= 10:
        body_h = int(win_h * 0.045)
    else:
        body_h = int(win_h * 0.040)

    foot_lines = max(1, footer.count("\n") + 1)
    foot_h = int(win_h * 0.035)

    # ——整体对称居中布局（估算文本块高度）——
    body_block_h = int(body_h * 1.25 * n_lines)
    foot_block_h = int(foot_h * 1.25 * foot_lines)
    gap = int(win_h * 0.040)

    total_h = body_block_h + gap + foot_block_h
    body_y = int((total_h / 2.0) - (body_block_h / 2.0))
    foot_y = -int((total_h / 2.0) - (foot_block_h / 2.0))

    body_stim = _text(win, body, y=body_y, h=body_h, align="center")
    foot = _text(win, footer, y=foot_y, h=foot_h, align="center")

    wait_advance_with_draw(
        win,
        [body_stim, foot],
        min_wait_s=min_wait_s,
        allow_space=True,
        allow_click=allow_click,
    )

def show_instruction_image(
    win: visual.Window,
    img_path: Path,
    footer: str = "按屏幕继续",
    min_wait_s: float = ADVANCE_MIN_S,
    allow_click: bool = ALLOW_SCREEN_CLICK,
) -> None:
    """指导语图片 + 底部交互按钮（有hover/press反馈）。
    图片缩小到82%并上移，按钮在底部。"""
    import time as _time
    canvas_w, canvas_h = win.size

    try:
        from PIL import Image as _PILImage
        iw, ih = _PILImage.open(str(img_path)).size
    except Exception:
        iw, ih = 1920, 1080

    img_scale = 0.82
    max_w = canvas_w * img_scale
    max_h = canvas_h * img_scale
    scale = min(max_w / float(iw), max_h / float(ih))
    fw, fh = iw * scale, ih * scale
    img_y = 0

    stim = visual.ImageStim(win, image=str(img_path),
                            size=(fw, fh), pos=(0, img_y), units="pix")

    btn_w = int(canvas_w * 0.22)
    btn_h = int(canvas_h * 0.08)
    btn_y = -canvas_h // 2 + int(canvas_h * 0.10)
    _c_normal = [26, 140, 255]
    _c_hover = [64, 170, 255]
    _c_press = [10, 90, 180]

    btn = visual.Rect(win, width=btn_w, height=btn_h, pos=(0, btn_y),
                      fillColor=_c_normal, colorSpace="rgb255",
                      lineWidth=0, units="pix")
    btn_lbl = visual.TextStim(win, text="继续", font=FONT_CN,
                               height=btn_h * 0.5, color=[255, 255, 255],
                               colorSpace="rgb255", pos=(0, btn_y),
                               units="pix", bold=True)

    mouse = event.Mouse(win=win)
    mouse.setVisible(True)
    event.clearEvents()
    t0 = _time.perf_counter()
    prev = True

    while True:
        now = _time.perf_counter()
        mpos = mouse.getPos()
        hovering = btn.contains(mpos)
        cur = any(mouse.getPressed())

        if cur and hovering:
            btn.fillColor = _c_press
        elif hovering:
            btn.fillColor = _c_hover
        else:
            btn.fillColor = _c_normal

        stim.draw()
        btn.draw()
        btn_lbl.draw()
        win.flip()

        if now - t0 < max(0.0, float(min_wait_s)):
            prev = cur
            continue

        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            core.quit()
        if "space" in keys:
            return

        if cur and not prev and hovering:
            btn.fillColor = _c_press
            stim.draw(); btn.draw(); btn_lbl.draw()
            win.flip()
            core.wait(0.12)
            return
        prev = cur

def preload_image_cache(win: visual.Window, paths: List[Path]) -> Dict[str, visual.ImageStim]:
    """预加载图片纹理：减少首帧卡顿，提升 RT 稳定性（失败不影响运行）。"""
    cache: Dict[str, visual.ImageStim] = {}
    placeholder = np.zeros((8, 8, 3), dtype=np.uint8)
    for p in paths:
        try:
            if not p or not p.exists():
                continue
            stim = visual.ImageStim(
                win,
                image=placeholder,
                size=(1, 1),
                pos=(9999, 9999),
                units="pix",
                autoLog=False,
            )
            stim.image = str(p)
            cache[str(p)] = stim
        except Exception:
            continue
    return cache

def fixation(win: visual.Window, dur: float, show_button=False, button=None, button_text=None):
    dur = max(0.0, float(dur))
    fix = visual.TextStim(win, text="+", color=FG, height=int(win.size[1] * 0.06),
                          pos=(0, int(win.size[1] * 0.08)), font=FONT_CN, units="pix")
    clk = core.Clock()
    while clk.getTime() < dur:
        fix.draw()
        if show_button and button is not None and button_text is not None:
            button.draw(); button_text.draw()
        win.flip()

def flash_message(win: visual.Window, text: str, dur: float):
    """短暂提示（不等待按键）。"""
    dur = max(0.0, float(dur))
    if dur <= 0:
        return
    win_w, win_h = win.size
    msg = _text(win, text, y=int(win_h * 0.05), h=int(win_h * 0.060), align="center")
    clk = core.Clock()
    while clk.getTime() < dur:
        msg.draw()
        win.flip()




def show_feedback_page(
    win: visual.Window,
    correct: bool,
    expected: str,
    max_wait: float = 2.0,
    min_wait_s: float = 0.2,
    allow_click: bool = ALLOW_SCREEN_CLICK,
):
    """练习反馈页：整体对称居中；可空格/点击继续；也会在 max_wait 后自动结束。"""
    if expected == "press":
        exp_txt = "应该按按钮"
    elif expected == "none":
        exp_txt = "应该不操作"
    else:
        exp_txt = "这一题不计分"

    win_w, win_h = win.size
    s = "正确" if bool(correct) else "错误"

    msg = f"{s}\n\n{exp_txt}"
    n_lines = max(1, msg.count("\n") + 1)

    # 字号：反馈短文本更大一点
    if n_lines <= 3:
        msg_h = int(win_h * 0.070)
    elif n_lines <= 6:
        msg_h = int(win_h * 0.060)
    else:
        msg_h = int(win_h * 0.050)

    tip_txt = "按屏幕继续"
    tip_h = int(win_h * 0.035)

    msg_block_h = int(msg_h * 1.25 * n_lines)
    tip_block_h = int(tip_h * 1.25)
    gap = int(win_h * 0.040)

    total_h = msg_block_h + gap + tip_block_h
    msg_y = int((total_h / 2.0) - (msg_block_h / 2.0))
    tip_y = -int((total_h / 2.0) - (tip_block_h / 2.0))

    fb = _text(win, msg, y=msg_y, h=msg_h, align="center")
    tip = _text(win, tip_txt, y=tip_y, h=tip_h, align="center")

    mouse = event.Mouse(win=win, visible=True)
    while any(mouse.getPressed()):
        core.wait(0.01)

    clk = core.Clock()
    while clk.getTime() < float(max_wait):
        fb.draw()
        tip.draw()
        win.flip()

        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            core.quit()
        if "space" in keys and clk.getTime() >= min_wait_s:
            break

        if allow_click and mouse.getPressed()[0] and clk.getTime() >= min_wait_s:
            while any(mouse.getPressed()):
                core.wait(0.01)
            break

def _fit_4by3(win_w: int, win_h: int, target_h: int) -> Tuple[int, int]:
    h = min(target_h, int(win_h * 0.80))
    w = int(h * 4 / 3)
    if w > int(win_w * 0.92):
        w = int(win_w * 0.92)
        h = int(w * 3 / 4)
    return w, h


def build_match_button(win: visual.Window):
    """底部大按钮：触屏/鼠标点击"""
    win_w, win_h = win.size
    bw = int(win_w * 0.42)
    bh = int(win_h * 0.12)
    by = -int(win_h * 0.38)

    btn = visual.Rect(
        win, width=bw, height=bh, pos=(0, by),
        lineColor=FG, fillColor=None, lineWidth=3, units="pix"
    )
    txt = visual.TextStim(
        win, text="匹配", color=FG,
        height=int(win_h * 0.035), pos=(0, by),
        font=FONT_CN, units="pix"
    )
    return btn, txt


def present_trial_with_response(
    win: visual.Window,
    img_path: Path,
    stim_dur: float,
    resp_deadline: float,
    button: visual.Rect,
    button_text: visual.TextStim,
    confirm_s: float = CONFIRM_S,
) -> Tuple[bool, float]:
    """
    在一个反应窗口内（resp_deadline秒）收集是否按下（键盘或点按钮）。
    - 前 stim_dur 秒显示图片 + 按钮
    - 之后显示注视点 + 按钮（按钮仍保留，便于触屏）
    返回 (pressed, rt)。未按下时 rt=-1.
    """
    win_w, win_h = win.size
    stim_w, stim_h = _fit_4by3(win_w, win_h, int(win_h * 0.62))
    blank = np.zeros((10, 10, 3), dtype=np.uint8)
    stim = visual.ImageStim(
        win, image=blank, units="pix",
        size=(stim_w, stim_h), pos=(0, int(win_h * 0.10)),
        autoLog=False
    )
    stim.image = str(img_path)

    fix = visual.TextStim(
        win, text="+", color=FG, height=int(win_h * 0.06),
        pos=(0, int(win_h * 0.10)), font=FONT_CN, units="pix"
    )

    mouse = event.Mouse(win=win, visible=True)
    # 防止按住导致秒选
    while any(mouse.getPressed()):
        core.wait(0.01)

    mouse.clickReset()
    event.clearEvents()

    if resp_deadline <= 0:
        resp_deadline = stim_dur
    resp_deadline = max(float(resp_deadline), float(stim_dur), 0.2)

    clk = core.Clock()
    pressed = False
    rt = -1.0

    hi = visual.Rect(
        win, width=button.width + 10, height=button.height + 10,
        pos=button.pos, lineColor=FG, fillColor=None, lineWidth=6, units="pix"
    )

    def draw_base(t_now: float):
        if t_now <= stim_dur:
            stim.draw()
        else:
            fix.draw()
        button.draw()
        button_text.draw()

    while clk.getTime() < resp_deadline:
        t_now = clk.getTime()
        draw_base(t_now)
        win.flip()

        keys = event.getKeys(keyList=RESPONSE_KEYS + ["escape"])
        if keys:
            if "escape" in keys:
                core.quit()
            pressed = True
            rt = clk.getTime()
            break

        if mouse.getPressed()[0]:
            if button.contains(mouse):
                pressed = True
                rt = clk.getTime()
                # 等松开，避免连点
                while any(mouse.getPressed()):
                    core.wait(0.01)
                break
            # 若点到别处，仍等松开，避免拖拽误触
            while any(mouse.getPressed()):
                core.wait(0.01)

    # 选中后确认高亮（键盘/点击统一）
    if pressed and confirm_s > 0:
        event.clearEvents()
        conf_clk = core.Clock()
        # 用按下时刻来决定显示 stim 还是 fixation
        t_sel = rt
        while conf_clk.getTime() < confirm_s:
            draw_base(t_sel)
            hi.draw()
            win.flip()

    return pressed, rt



# ----------------------------
# 主流程
# ----------------------------
def run_B4(
    win: Optional[visual.Window] = None,
    exp_info: Optional[Dict[str, str]] = None,
    list_name: str = "ListA"
) -> Dict[str, Any]:
    root = _project_root()

    # 信息：run_all 传入则不弹窗；独立运行才弹窗
    if exp_info is None:
        exp_info = {"participant": "test", "session": "1"}
        dlg = gui.DlgFromDict(exp_info, title="N-back B4 (2-back)")
        if not dlg.OK:
            core.quit()

    participant = str(exp_info.get("participant", "test"))
    session = str(exp_info.get("session", "1"))

    created_win = False
    if win is None:
        win = visual.Window(fullscr=True, units="pix", color=BG, allowGUI=False)
        created_win = True
    win.mouseVisible = True

    trials = load_trials(list_name)

    # 可选参数（run_all 可传入；不给则用默认值）
    allow_click = _to_bool(exp_info.get("allow_screen_click", ALLOW_SCREEN_CLICK), ALLOW_SCREEN_CLICK)
    advance_min_s = _to_float(exp_info.get("advance_min_s", ADVANCE_MIN_S), ADVANCE_MIN_S)
    do_preload = _to_bool(exp_info.get("preload_images", PRELOAD_IMAGES), PRELOAD_IMAGES)
    show_timeout_main = _to_bool(exp_info.get("show_timeout_main", SHOW_TIMEOUT_MAIN), SHOW_TIMEOUT_MAIN)

    # 指导语（优先图片；缺失则回退文字，避免现场崩）
    instr_path = root / INSTR_IMAGE_B4
    if instr_path.exists():
        show_instruction_image(
            win,
            instr_path,
            footer="按屏幕继续",
            min_wait_s=advance_min_s,
            allow_click=allow_click,
        )
    else:
        show_page(
            win,
            body="和前两张比\n\n相同 \u2192 按按钮\n不同 \u2192 不操作",
            footer="按屏幕继续",
            min_wait_s=advance_min_s,
            allow_click=allow_click,
        )

    # 可选预加载（减少中途卡顿，提升 RT 稳定性）
    _pre_cache = {}
    if do_preload:
        uniq = []
        seen = set()
        for t in trials:
            p = t.image.resolve()
            sp = str(p)
            if sp not in seen:
                seen.add(sp)
                uniq.append(p)
        _pre_cache = preload_image_cache(win, uniq)

    button, button_text = build_match_button(win)



    practice = [t for t in trials if t.phase == "practice"]
    main = [t for t in trials if t.phase != "practice"]

    if practice:
        show_page(win, "练习开始", footer="按屏幕继续", min_wait_s=advance_min_s, allow_click=allow_click)

    records: List[Dict[str, Any]] = []

    def score(expected: str, pressed: bool) -> Optional[bool]:
        if expected == "na":
            return None
        if expected == "press":
            return True if pressed else False
        if expected == "none":
            return False if pressed else True
        # 兜底
        return None

    def run_phase(phase_trials: List[Trial], is_practice: bool):
        for t in phase_trials:
            if "escape" in event.getKeys(["escape"]):
                core.quit()

            # 展示 + 收集反应
            pressed, rt = present_trial_with_response(
                win=win,
                img_path=t.image,
                stim_dur=t.stim_dur,
                resp_deadline=t.resp_deadline,
                button=button,
                button_text=button_text
            )

            is_correct = score(t.correct, pressed)

            # 练习反馈（单独页），正式不反馈（用注视点分隔）
            if is_practice and t.feedback == 1 and is_correct is not None:
                show_feedback_page(win, correct=bool(is_correct), expected=t.correct, max_wait=2.0, min_wait_s=0.2, allow_click=allow_click)
            else:
                if (not is_practice) and show_timeout_main and (t.correct == "press") and (not pressed):
                    flash_message(win, "超时", TIMEOUT_FLASH_S_MAIN)
                fixation(win, t.isi, show_button=True, button=button, button_text=button_text)

            records.append({
                "trial_index": t.trial_index,
                "phase": t.phase,
                "n": t.n,
                "cond": t.cond,
                "correct_rule": t.correct,
                "image": str(t.image),
                "pressed": 1 if pressed else 0,
                "rt": "" if rt < 0 else round(float(rt), 4),
                "is_correct": "" if is_correct is None else (1 if is_correct else 0),
                "stim_dur": t.stim_dur,
                "resp_deadline": t.resp_deadline,
                "isi": t.isi
            })

    if practice:
        run_phase(practice, is_practice=True)
        show_page(win, "练习结束，进入正式任务", footer="按屏幕继续", min_wait_s=advance_min_s, allow_click=allow_click)

    run_phase(main, is_practice=False)

    show_page(win, "本部分结束", footer="按屏幕继续", min_wait_s=advance_min_s, allow_click=allow_click)

    # 保存
    out_root = root / "result"
    raw_dir = out_root / "raw"
    summary_dir = out_root / "summary"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)

    tag = _now_tag()
    raw_path = raw_dir / f"{participant}_sess{session}_B4_{list_name}_{tag}.csv"

    fieldnames = [
        "participant", "session", "trial_index", "phase", "n", "cond",
        "correct_rule", "image", "pressed", "rt", "is_correct",
        "stim_dur", "resp_deadline", "isi"
    ]
    with raw_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in records:
            row = {k: "" for k in fieldnames}
            row["participant"] = participant
            row["session"] = session
            for k, v in r.items():
                if k in row:
                    row[k] = v
            w.writerow(row)

    # 汇总（只算有 is_correct 的 trial）
    prac_scored = [r for r in records if r.get("phase") == "practice" and r.get("is_correct") != ""]
    main_scored = [r for r in records if r.get("phase") != "practice" and r.get("is_correct") != ""]

    def _acc(rows):
        return (sum(1 for r in rows if r.get("is_correct") == 1) / len(rows)) if rows else ""

    def _mean_rt(rows):
        rts = [float(r["rt"]) for r in rows if r.get("rt") not in ("", None) and float(r.get("rt", -1)) >= 0]
        return (sum(rts) / len(rts)) if rts else ""

    n_practice = len([r for r in records if r.get("phase") == "practice"])
    n_main = len([r for r in records if r.get("phase") != "practice"])

    summary = {
        "participant": participant,
        "session": session,
        "block": "B4",
        "list_name": list_name,
        "n_practice": n_practice,
        "n_main": n_main,
        "acc_practice": _acc(prac_scored),
        "acc_main": _acc(main_scored),
        "mean_rt_main": _mean_rt(main_scored),
        "raw_path": str(raw_path),
    }

    summary_path = summary_dir / f"{participant}_sess{session}_B4_{list_name}_{tag}_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        wri = csv.DictWriter(f, fieldnames=list(summary.keys()))
        wri.writeheader()
        wri.writerow(summary)

    if created_win:
        win.close()

    return summary


if __name__ == "__main__":
    run_B4(win=None, exp_info=None, list_name="ListA")
