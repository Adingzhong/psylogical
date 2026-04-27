# -*- coding: utf-8 -*-
"""
run_B3.py  (B3 = Lag-1 Probe 回忆式：伪随机间隔 + cue 触发三选一)

✅ 设计符合你的口径：
- 开始先学习 cue（大图），按空格进入
- 图片单流呈现（stim），中间不需要作答
- 当出现 cue（probe 行）时：先短暂呈现 cue → 再进入三选一"上一张是哪张？"（键盘1/2/3或点击图片）
- 练习阶段：单独反馈页（正确/错误 + 正确选项）
- 正式阶段：不反馈，仅注视点空屏分隔 trial（更清楚"我有没有按上"）

✅ 与 B1/B2 风格统一： 
- fullscr=True
- units="pix"
- 深灰背景 color=[-0.9,-0.9,-0.9] + 白字
- 鼠标指针可见（便于调试；触屏也可直接点）

List 文件：
- 默认读取：../lists/B3_ListA.csv   （或 B3_ListB.csv / B3_ListC.csv）
- 列名（建议保持一致）：
  trial_index, phase, event, image, lag1_true, opt1, opt2, opt3, correct_opt, stim_dur, resp_deadline, isi, feedback

独立运行：
  python run_B3.py
"""

from __future__ import annotations

import csv
import os
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
# 常量：和 B1/B2 对齐
# ----------------------------
BG = [-0.9, -0.9, -0.9]     # 深灰
FG = "white"               # 白字
FONT_CN = CJK_FONT


# 过场页推进：空格 或 点击屏幕
ALLOW_SCREEN_CLICK = True
ADVANCE_MIN_S = 0.8  # 过场页最短停留时间（防误触一闪而过）

# 指导语图片（相对项目根目录）
INSTR_IMAGE_B3 = "assets/instruction/B3_1.png"

# 预加载图片（减少卡顿，提升 RT 稳定性）
PRELOAD_IMAGES = True

# probe 选中后的确认高亮（并锁输入）
PROBE_CONFIRM_S = 0.15

# 正式阶段超时提示（默认不提示，仅记录；可通过 exp_info 打开）
SHOW_TIMEOUT_MAIN = False
TIMEOUT_FLASH_S_MAIN = 0.4



def _project_root() -> Path:
    # .../N-back/run/run_B3.py -> root = .../N-back
    return Path(__file__).resolve().parents[1]


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _abs_path(p: str, root: Path) -> Path:
    p = (p or "").strip().lstrip("\ufeff")
    if p == "" or p.lower() == "nan":
        return Path("")
    pp = Path(p)
    return pp if pp.is_absolute() else (root / pp)

def _as_bool(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ["1", "true", "yes", "y", "t"]:
        return True
    if s in ["0", "false", "no", "n", "f"]:
        return False
    return default


def _as_float(v: Any, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


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


def _norm_phase(s: str) -> str:
    s = (s or "").strip().lower()
    if s in ["practice", "练习"]:
        return "practice"
    if s in ["main", "formal", "正式"]:
        return "main"
    return "main"


def _norm_event(s: str) -> str:
    s = (s or "").strip().lower()
    if s in ["stim", "s", "trial"]:
        return "stim"
    if s in ["probe", "p", "cue"]:
        return "probe"
    return ""


@dataclass
class Trial:
    trial_index: int
    phase: str              # practice/main
    event: str              # stim/probe
    image: Path             # stim image or cue image
    lag1_true: Path         # only for probe (for logging)
    opt1: Path              # only for probe
    opt2: Path
    opt3: Path
    correct_opt: int        # 1/2/3 for probe
    stim_dur: float         # stim duration; for probe = cue display duration
    resp_deadline: float    # for probe
    isi: float              # fixation duration
    feedback: int           # 1 in practice probe, else 0


def load_trials(list_name: str) -> List[Trial]:
    root = _project_root()
    list_path = root / "lists" / f"B3_{list_name}.csv"
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

            # 判断"整行空"
            vals = [(str(v).strip() if v is not None else "") for v in row.values()]
            if all(v == "" or v.lower() == "nan" for v in vals):
                continue

            phase = _norm_phase(row.get("phase", "main"))
            event_name = _norm_event(row.get("event", ""))

            # event 为空：尝试从 image 推断（以 cue.png 作为 probe）
            image_rel = (row.get("image", "") or "").strip()
            if event_name == "":
                if image_rel.lower().endswith("cue.png"):
                    event_name = "probe"
                else:
                    event_name = "stim"

            # trial_index
            tid = _to_int(row.get("trial_index", len(trials) + 1), len(trials) + 1)

            t = Trial(
                trial_index=tid,
                phase=phase,
                event=event_name,
                image=_abs_path(row.get("image", ""), root),
                lag1_true=_abs_path(row.get("lag1_true", ""), root),
                opt1=_abs_path(row.get("opt1", ""), root),
                opt2=_abs_path(row.get("opt2", ""), root),
                opt3=_abs_path(row.get("opt3", ""), root),
                correct_opt=_to_int(row.get("correct_opt", 0), 0),
                stim_dur=_to_float(row.get("stim_dur", 1.0), 1.0),
                resp_deadline=_to_float(row.get("resp_deadline", 3.0), 3.0),
                isi=_to_float(row.get("isi", 0.25), 0.25),
                feedback=_to_int(row.get("feedback", 0), 0),
            )
            trials.append(t)

    # 基本合法性检查（避免你遇到"空 event / 空路径"直接崩）
    for t in trials:
        if t.event not in ["stim", "probe"]:
            raise ValueError(f"trial_index={t.trial_index} 的 event 不合法：{t.event!r}")
        if str(t.image) == "" or t.image == Path(""):
            raise ValueError(f"trial_index={t.trial_index} 的 image 为空。")
        # probe 必须有选项
        if t.event == "probe":
            if (t.opt1 == Path("") or t.opt2 == Path("") or t.opt3 == Path("")):
                raise ValueError(f"trial_index={t.trial_index} 的 probe 选项(opt1/2/3) 有空。")
            if t.correct_opt not in [1, 2, 3]:
                raise ValueError(f"trial_index={t.trial_index} 的 correct_opt 必须是 1/2/3。")

    return trials


# ----------------------------
# 视觉页面
# ----------------------------
def _text(win: visual.Window, s: str, y: float = 0, h: float = 34) -> visual.TextStim:
    return visual.TextStim(win, text=s, color=FG, height=h, pos=(0, y),
                           font=FONT_CN, units="pix", wrapWidth=int(win.size[0] * 0.90),
                           alignText="center")


def wait_advance_with_draw(
    win: visual.Window,
    drawables: List[Any],
    min_wait_s: float = 0.0,
    allow_space: bool = True,
    allow_click: bool = True,
):
    """过场页等待：空格 或 点击屏幕底部中央按钮区域。支持最短等待时间（防误触秒过）。"""
    mouse = event.Mouse(win=win, visible=True)

    # 防止按住鼠标/触屏导致"秒过"
    while any(mouse.getPressed()):
        core.wait(0.01)

    event.clearEvents()
    clk = core.Clock()

    while True:
        for d in drawables:
            d.draw()
        win.flip()

        t = clk.getTime()

        # 键盘推进
        if allow_space:
            keys = event.getKeys(keyList=["space", "escape"])
            if "escape" in keys:
                core.quit()
            if "space" in keys and t >= min_wait_s:
                return
        else:
            keys = event.getKeys(keyList=["escape"])
            if "escape" in keys:
                core.quit()

        # 点击推进：接受任意位置点击
        if allow_click and mouse.getPressed()[0] and t >= min_wait_s:
            while any(mouse.getPressed()):
                core.wait(0.01)
            return


def wait_space_with_draw(win: visual.Window, drawables: List[Any], min_wait_s: float = 0.0):
    """兼容旧调用：默认空格或点击屏幕推进。"""
    wait_advance_with_draw(
        win,
        drawables,
        min_wait_s=min_wait_s,
        allow_space=True,
        allow_click=ALLOW_SCREEN_CLICK,
    )


def _fit_image_keep_aspect(
    img_path: Path,
    win_w: int,
    win_h: int,
    max_w_ratio: float = 0.96,
    max_h_ratio: float = 0.86,
) -> Tuple[int, int]:
    """等比缩放图片以适配屏幕，避免被拉伸导致文字看起来"被拉开/有空格"。

    max_h_ratio 会给底部推进提示留出空间。
    """
    try:
        from PIL import Image  # Pillow 通常已安装；若缺失则走 fallback
        with Image.open(str(img_path)) as im:
            iw, ih = im.size
        if iw <= 0 or ih <= 0:
            raise ValueError("bad image size")
        scale = min((win_w * max_w_ratio) / iw, (win_h * max_h_ratio) / ih)
        return int(iw * scale), int(ih * scale)
    except Exception:
        # 兜底：不等比也不至于溢出屏幕
        return int(win_w * 0.96), int(win_h * 0.80)


def show_instruction_image(win: visual.Window, img_path: Path, min_s: float = ADVANCE_MIN_S):
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

        if now - t0 < max(0.0, float(min_s)):
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


def show_page(
    win: visual.Window,
    body: str,
    footer: str = "按屏幕继续",
    footer_y: Optional[float] = None,
    min_wait_s: float = ADVANCE_MIN_S,
):
    """过场/提示页（适老版，整体对称居中）

    你要的效果：正文 + 底部提示作为一个"整体"，在屏幕上上下对称居中，
    而不是"正文在中间、底部提示贴底"。
    """
    win_w, win_h = win.size
    n_lines = body.count("\n") + 1

    # 短提示（如"练习开始/结束"）字号更大
    if n_lines <= 4:
        body_h = int(win_h * 0.070)
    elif n_lines <= 8:
        body_h = int(win_h * 0.055)
    else:
        body_h = int(win_h * 0.040)

    foot_h = int(win_h * 0.038)
    # 视觉间距：跟随字号变化，避免"挤"或"太散"
    gap = max(int(body_h * 0.85), int(win_h * 0.030))

    # 估算正文块高度（按行数估计；空行也算高度）
    line_h = int(body_h * 1.25)
    body_block_h = max(line_h, n_lines * line_h)

    # 整体居中：body 在上，footer 在下
    if footer_y is None:
        body_y = int((foot_h + gap) / 2)
        foot_y = -int((body_block_h + gap) / 2)
    else:
        # 兼容旧用法：若指定 footer_y，则只固定 footer，正文保持在更靠中的位置
        foot_y = int(footer_y)
        body_y = 0

    body_stim = _text(win, body, y=body_y, h=body_h)
    foot = _text(win, footer, y=foot_y, h=foot_h)

    wait_space_with_draw(win, [body_stim, foot], min_wait_s=max(0.0, float(min_wait_s)))


def fixation(win: visual.Window, dur: float):
    dur = max(0.0, float(dur))
    fix = visual.TextStim(win, text="+", color=FG, height=int(win.size[1] * 0.06),
                          pos=(0, 0), font=FONT_CN, units="pix")
    fix.draw()
    win.flip()
    core.wait(dur)


def show_feedback(
    win: visual.Window,
    correct: bool,
    correct_opt: int,
    timed_out: bool = False,
    max_wait: float = 2.0,
    min_wait_s: float = 0.25,
):
    """练习反馈页：整体对称居中 + 空格/点击提前结束，否则 max_wait 自动结束。"""
    win_w, win_h = win.size

    if timed_out:
        s = "超时，请快些作答"
    else:
        s = "正确!" if correct else f"错误（正确答案：{correct_opt}）"

    msg_h = int(win_h * 0.060)
    tip_h = int(win_h * 0.035)
    gap = max(int(msg_h * 0.90), int(win_h * 0.025))

    # 估算 msg 高度用于整体居中
    n_lines = s.count("\n") + 1
    msg_block_h = max(int(msg_h * 1.25), n_lines * int(msg_h * 1.25))
    total_h = msg_block_h + gap + tip_h

    msg_y = int((tip_h + gap) / 2)
    tip_y = -int((msg_block_h + gap) / 2)

    msg = visual.TextStim(
        win,
        text=s,
        color=FG,
        height=msg_h,
        pos=(0, msg_y),
        font=FONT_CN,
        units="pix",
        alignText="center",
        wrapWidth=int(win_w * 0.92),
    )
    tip = visual.TextStim(
        win,
        text="按屏幕继续",
        color=FG,
        height=tip_h,
        pos=(0, tip_y),
        font=FONT_CN,
        units="pix",
        alignText="center",
        wrapWidth=int(win_w * 0.92),
    )

    mouse = event.Mouse(win=win, visible=True)
    while any(mouse.getPressed()):
        core.wait(0.01)

    clk = core.Clock()
    event.clearEvents()

    max_wait = max(0.2, float(max_wait))
    min_wait_s = max(0.0, float(min_wait_s))

    while clk.getTime() < max_wait:
        msg.draw()
        tip.draw()
        win.flip()

        t = clk.getTime()
        if t >= min_wait_s:
            keys = event.getKeys(keyList=["space", "escape"])
            if "escape" in keys:
                core.quit()
            if "space" in keys:
                break
            if mouse.getPressed()[0]:
                break

        core.wait(0.01)


def _fit_4by3(win_w: int, win_h: int, target_h: int) -> Tuple[int, int]:
    """给定高度 target_h，按 4:3 计算宽度，并保证不超过屏幕"""
    h = min(target_h, int(win_h * 0.80))
    w = int(h * 4 / 3)
    if w > int(win_w * 0.92):
        w = int(win_w * 0.92)
        h = int(w * 3 / 4)
    return w, h


def cue_learn_screen(win: visual.Window, cue_path: Path, min_wait_s: float = ADVANCE_MIN_S):
    """cue 学习页：大图 + 提示放在图片下方；支持空格或点击屏幕推进，并加最短等待时间。"""
    win_w, win_h = win.size
    cue_w, cue_h = _fit_4by3(win_w, win_h, int(win_h * 0.62))

    blank = np.zeros((10, 10, 3), dtype=np.uint8)
    cue = visual.ImageStim(
        win,
        image=blank,
        units="pix",
        size=(cue_w, cue_h),
        pos=(0, int(win_h * 0.10)),
    )
    cue.image = str(cue_path)

    tip = visual.TextStim(
        win,
        text="记住这张图\n\n按屏幕继续",
        color=FG,
        height=int(win_h * 0.035),
        pos=(0, -int(win_h * 0.34)),
        font=FONT_CN,
        units="pix",
    )

    wait_space_with_draw(win, [cue, tip], min_wait_s=max(0.0, float(min_wait_s)))

def show_stim(win: visual.Window, img_path: Path, dur: float):
    win_w, win_h = win.size
    stim_w, stim_h = _fit_4by3(win_w, win_h, int(win_h * 0.66))
    blank = np.zeros((10, 10, 3), dtype=np.uint8)
    stim = visual.ImageStim(win, image=blank, units="pix",
                            size=(stim_w, stim_h), pos=(0, int(win_h * 0.03)))
    stim.image = str(img_path)

    stim.draw()
    win.flip()
    core.wait(max(0.02, float(dur)))


def preload_image_cache(win: visual.Window, paths: List[Path]) -> List[visual.ImageStim]:
    """预加载图片到内存（尽量减少磁盘抖动）。不进行 flip，不影响被试看到的画面。"""
    cache: List[visual.ImageStim] = []
    seen = set()
    for p in paths:
        if not p or p == Path(""):
            continue
        sp = str(p)
        if sp in seen:
            continue
        seen.add(sp)
        if not Path(p).exists():
            continue
        try:
            stim = visual.ImageStim(win, image=sp, units="pix", size=(10, 10), pos=(0, 0))
            cache.append(stim)
        except Exception:
            # 预加载失败不阻断任务
            continue
    return cache

def show_cue_only(win: visual.Window, cue_path: Path, dur: float):
    # cue 单独出现（随后再进入"额外询问页"）
    show_stim(win, cue_path, dur)


def probe_3afc(
    win: visual.Window,
    opt_paths: Tuple[Path, Path, Path],
    correct_opt: int,
    deadline: float,
    confirm_s: float = PROBE_CONFIRM_S,
) -> Tuple[Optional[int], float, bool]:
    """三选一：返回 (choice[1-3 or None], rt, is_correct)。

    优化点：
    - 支持键盘 1/2/3 与触屏/鼠标点击
    - 点击区域：图片 + 外框都可点（更适老）
    - 选中后统一确认高亮 confirm_s，并在确认阶段锁输入
    """
    win_w, win_h = win.size
    deadline = max(0.3, float(deadline))
    confirm_s = max(0.0, float(confirm_s))

    # 选项尺寸：保证三张都在屏幕内
    margin_x = int(win_w * 0.06)
    gap = int(win_w * 0.03)
    avail_w = win_w - 2 * margin_x - 2 * gap
    opt_w = int(avail_w / 3)
    opt_h = int(opt_w * 3 / 4)

    y_img = -int(win_h * 0.02)
    x1 = -int((opt_w + gap))
    x2 = 0
    x3 = int((opt_w + gap))

    blank = np.zeros((10, 10, 3), dtype=np.uint8)
    img1 = visual.ImageStim(win, image=blank, units="pix", size=(opt_w, opt_h), pos=(x1, y_img))
    img2 = visual.ImageStim(win, image=blank, units="pix", size=(opt_w, opt_h), pos=(x2, y_img))
    img3 = visual.ImageStim(win, image=blank, units="pix", size=(opt_w, opt_h), pos=(x3, y_img))
    img1.image = str(opt_paths[0])
    img2.image = str(opt_paths[1])
    img3.image = str(opt_paths[2])

    def frame_at(x):
        return visual.Rect(
            win,
            width=opt_w + 10,
            height=opt_h + 10,
            pos=(x, y_img),
            lineColor=FG,
            fillColor=None,
            lineWidth=2,
            units="pix",
        )

    f1, f2, f3 = frame_at(x1), frame_at(x2), frame_at(x3)

    prompt = visual.TextStim(
        win,
        text="上一张是哪个？",
        color=FG,
        height=int(win_h * 0.04),
        pos=(0, int(win_h * 0.34)),
        font=FONT_CN,
        units="pix",
    )

    lab_y = y_img - int(opt_h / 2) - int(win_h * 0.06)
    l1 = visual.TextStim(win, text="1", color=FG, height=int(win_h * 0.045),
                         pos=(x1, lab_y), font=FONT_CN, units="pix")
    l2 = visual.TextStim(win, text="2", color=FG, height=int(win_h * 0.045),
                         pos=(x2, lab_y), font=FONT_CN, units="pix")
    l3 = visual.TextStim(win, text="3", color=FG, height=int(win_h * 0.045),
                         pos=(x3, lab_y), font=FONT_CN, units="pix")

    mouse = event.Mouse(win=win, visible=True)
    # 防止按住导致一进来就选中
    while any(mouse.getPressed()):
        core.wait(0.01)

    def draw_screen(highlight_choice: Optional[int] = None):
        prompt.draw()
        f1.draw(); img1.draw(); l1.draw()
        f2.draw(); img2.draw(); l2.draw()
        f3.draw(); img3.draw(); l3.draw()
        if highlight_choice in (1, 2, 3):
            hx = [x1, x2, x3][highlight_choice - 1]
            hi = visual.Rect(
                win,
                width=opt_w + 18,
                height=opt_h + 18,
                pos=(hx, y_img),
                lineColor=FG,
                fillColor=None,
                lineWidth=6,
                units="pix",
            )
            hi.draw()

    event.clearEvents()
    clk = core.Clock()

    choice: Optional[int] = None
    rt = -1.0

    while clk.getTime() < deadline:
        draw_screen(None)
        win.flip()

        keys = event.getKeys(keyList=["1", "2", "3", "num_1", "num_2", "num_3", "escape"])
        if keys:
            k = keys[0]
            if k == "escape":
                core.quit()
            if k in ["1", "num_1"]:
                choice = 1
            elif k in ["2", "num_2"]:
                choice = 2
            else:
                choice = 3
            rt = clk.getTime()
            break

        if mouse.getPressed()[0]:
            mx, my = mouse.getPos()
            if img1.contains((mx, my)) or f1.contains((mx, my)):
                choice = 1
            elif img2.contains((mx, my)) or f2.contains((mx, my)):
                choice = 2
            elif img3.contains((mx, my)) or f3.contains((mx, my)):
                choice = 3

            # 等松开，避免连点/误触
            while any(mouse.getPressed()):
                core.wait(0.01)

            if choice is not None:
                rt = clk.getTime()
                break

    ok = (choice == int(correct_opt)) if choice is not None else False

    # 选中后的确认高亮（锁输入）
    if choice is not None and confirm_s > 0:
        event.clearEvents()
        conf_clk = core.Clock()
        while conf_clk.getTime() < confirm_s:
            draw_screen(highlight_choice=choice)
            win.flip()

    return choice, rt, ok

# ----------------------------
# 主流程
# ----------------------------
def run_B3(
    win: Optional[visual.Window] = None,
    exp_info: Optional[Dict[str, str]] = None,
    list_name: str = "ListA"
) -> Dict[str, Any]:
    root = _project_root()

    # 信息：run_all 传入则不弹窗；独立运行才弹窗
    if exp_info is None:
        exp_info = {"participant": "test", "session": "1"}
        dlg = gui.DlgFromDict(exp_info, title="N-back B3")
        if not dlg.OK:
            core.quit()

    participant = str(exp_info.get("participant", "test"))
    session = str(exp_info.get("session", "1"))

    # 可选参数（run_all 可传入）
    advance_min_s = _as_float(exp_info.get("advance_min_s", ADVANCE_MIN_S), ADVANCE_MIN_S)
    preload_images = _as_bool(exp_info.get("preload_images", PRELOAD_IMAGES), PRELOAD_IMAGES)
    show_timeout_main = _as_bool(exp_info.get("show_timeout_main", SHOW_TIMEOUT_MAIN), SHOW_TIMEOUT_MAIN)

    created_win = False
    if win is None:
        win = visual.Window(fullscr=True, units="pix", color=BG, allowGUI=False)
        created_win = True
    win.mouseVisible = _as_bool(exp_info.get("mouse_visible", True), True)

    # 读 list
    trials = load_trials(list_name)
    if not trials:
        raise ValueError("B3 list 为空，无法运行。")

    # cue 文件（用于学习页 & probe 的 cue 展示）
    cue_default = root / "stimuli" / "B3" / list_name / "cue.png"
    cue_path: Optional[Path] = cue_default if cue_default.exists() else None
    if cue_path is None:
        for t in trials:
            if t.event == "probe" and t.image and t.image != Path(""):
                cue_path = t.image
                break
    if cue_path is None:
        cue_path = trials[0].image
    if not cue_path.exists():
        raise FileNotFoundError(f"cue 图片不存在：{cue_path}")

    # 预加载（可选）：尽量减少磁盘抖动带来的卡顿
    _preload_cache: List[visual.ImageStim] = []
    if preload_images:
        preload_paths: List[Path] = [cue_path]
        for t in trials:
            # stim 图
            if t.image and t.image != Path(""):
                preload_paths.append(t.image)
            # probe 的 lag1_true 与 3 个选项
            if t.lag1_true and t.lag1_true != Path(""):
                preload_paths.append(t.lag1_true)
            if t.opt1 and t.opt1 != Path(""):
                preload_paths.append(t.opt1)
            if t.opt2 and t.opt2 != Path(""):
                preload_paths.append(t.opt2)
            if t.opt3 and t.opt3 != Path(""):
                preload_paths.append(t.opt3)
        _preload_cache = preload_image_cache(win, preload_paths)

    # 指导语（图片优先；若图片缺失则回退为文字）
    instr_path = root / INSTR_IMAGE_B3
    if instr_path.exists():
        show_instruction_image(win, instr_path, min_s=advance_min_s)
    else:
        show_page(
            win,
            body="看图片，记住每一张\n\n出现提示时，选出上一张是哪个",
            footer="按屏幕继续",
            min_wait_s=advance_min_s,
        )

    # cue 学习（大图 + 提示在下方）
    cue_learn_screen(win, cue_path, min_wait_s=advance_min_s)

    # 分练习/正式
    practice = [t for t in trials if t.phase == "practice"]
    main = [t for t in trials if t.phase != "practice"]

    records: List[Dict[str, Any]] = []

    def run_phase(phase_trials: List[Trial], is_practice: bool):
        for t in phase_trials:
            if "escape" in event.getKeys(["escape"]):
                core.quit()

            if not t.image.exists():
                raise FileNotFoundError(f"图片不存在：{t.image}")

            if t.event == "stim":
                show_stim(win, t.image, t.stim_dur)
                fixation(win, t.isi)

                records.append({
                    "trial_index": t.trial_index,
                    "phase": t.phase,
                    "event": "stim",
                    "image": str(t.image),
                    "choice": "",
                    "rt": "",
                    "is_correct": ""
                })

            elif t.event == "probe":
                # 先 cue 单独出现
                show_cue_only(win, cue_path, t.stim_dur)

                # 再进入"额外询问页"
                choice, rt, ok = probe_3afc(
                    win,
                    opt_paths=(t.opt1, t.opt2, t.opt3),
                    correct_opt=t.correct_opt,
                    deadline=t.resp_deadline
                )

                if is_practice and t.feedback == 1:
                    show_feedback(win, ok, t.correct_opt, timed_out=(choice is None), max_wait=2.0)
                else:
                    # 正式：默认不反馈；超时可选短提示（不打断节奏）
                    if (choice is None) and (not is_practice) and show_timeout_main and TIMEOUT_FLASH_S_MAIN > 0:
                        flash = visual.TextStim(
                            win,
                            text="超时",
                            color=FG,
                            height=int(win.size[1] * 0.06),
                            pos=(0, 0),
                            font=FONT_CN,
                            units="pix",
                        )
                        flash.draw()
                        win.flip()
                        core.wait(float(TIMEOUT_FLASH_S_MAIN))
                    fixation(win, t.isi)

                records.append({
                    "trial_index": t.trial_index,
                    "phase": t.phase,
                    "event": "probe",
                    "image": str(cue_path),
                    "lag1_true": str(t.lag1_true),
                    "opt1": str(t.opt1),
                    "opt2": str(t.opt2),
                    "opt3": str(t.opt3),
                    "correct_opt": t.correct_opt,
                    "choice": "" if choice is None else int(choice),
                    "rt": "" if rt < 0 else round(float(rt), 4),
                    "is_correct": 1 if ok else 0
                })

            else:
                raise ValueError(f"未知 event：{t.event!r}")

    # 开始提示
    if practice:
        show_page(
            win,
            "练习开始",
            footer="按屏幕继续",
            min_wait_s=advance_min_s
        )
        run_phase(practice, is_practice=True)
        show_page(
            win,
            "练习结束，进入正式任务",
            footer="按屏幕继续",
            min_wait_s=advance_min_s
        )
    else:
        show_page(
            win,
            "正式任务开始",
            footer="按屏幕继续",
            min_wait_s=advance_min_s
        )

    run_phase(main, is_practice=False)

    show_page(win, "本部分结束", footer="按屏幕继续", min_wait_s=advance_min_s)

    # 保存
    out_root = root / "result"
    raw_dir = out_root / "raw"
    summary_dir = out_root / "summary"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    tag = _now_tag()
    raw_path = raw_dir / f"{participant}_sess{session}_B3_{list_name}_{tag}.csv"

    fieldnames = [
        "participant", "session", "trial_index", "phase", "event",
        "image", "lag1_true", "opt1", "opt2", "opt3", "correct_opt",
        "choice", "rt", "is_correct"
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

    if created_win:
        win.close()

    # 汇总
    prac_probes = [r for r in records if r.get("event") == "probe" and r.get("phase") == "practice"]
    main_probes = [r for r in records if r.get("event") == "probe" and r.get("phase") != "practice"]
    all_probes = prac_probes + main_probes

    def _acc(rows):
        return (sum(1 for r in rows if r.get("is_correct") == 1) / len(rows)) if rows else ""

    def _mean_rt(rows):
        rts = [float(r["rt"]) for r in rows if r.get("rt") not in ("", None)]
        return (sum(rts) / len(rts)) if rts else ""

    n_practice = len([r for r in records if r.get("phase") == "practice"])
    n_main = len([r for r in records if r.get("phase") != "practice"])

    summary = {
        "participant": participant,
        "session": session,
        "block": "B3",
        "list_name": list_name,
        "n_practice": n_practice,
        "n_main": n_main,
        "n_probe_practice": len(prac_probes),
        "n_probe_main": len(main_probes),
        "acc_practice": _acc(prac_probes),
        "acc_main": _acc(main_probes),
        "acc_main_probe": _acc(main_probes),
        "mean_rt_main": _mean_rt(main_probes),
        "raw_path": str(raw_path),
    }

    summary_path = summary_dir / f"{participant}_sess{session}_B3_{list_name}_{tag}_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        wri = csv.DictWriter(f, fieldnames=list(summary.keys()))
        wri.writeheader()
        wri.writerow(summary)

    return summary


if __name__ == "__main__":
    run_B3(win=None, exp_info=None, list_name="ListA")
