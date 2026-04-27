# -*- coding: utf-8 -*-
"""
run_B1.py  (B1 = 0-back, 3AFC: 一致 / 相似 / 不同) — 传统单序列呈现（目标图更大 + 开始先"学习目标图"）

本次优化点（按你的要求，尽量少动结构）：
1) 指导语从文字改为图片：assets/instruction/B1_1.png
2) 过场页推进统一：按空格 或 点击屏幕；并加入最短等待时间（防误触一闪而过）
3) 按钮作答后：短暂高亮确认（原有 confirm_s 保留），并在关键位置 clearEvents 防止输入残留
4) "超时未回答"练习阶段原本就提示；正式阶段可选提示（默认不提示，只记录）
5) 可选预加载图片纹理，减少卡顿影响 RT（默认开启，可在 exp_info 里关）
6) 目标图是否常驻：可选（默认常驻，可由 exp_info 覆盖）

CSV（lists/B1_ListA.csv 或 lists/B1_ListB.csv...）列：
- stim_file
- target_file（可选；不写用 TARGET_DEFAULT）
- correct_resp（same/similar/different 或 一致/相似/不同）
- phase（practice/main；不写默认前 PRACTICE_N 行为练习）
- resp_deadline_s（可选）
- feedback_s（练习反馈页时长，可选）
- iti_s（题间注视点时长，可选）
- confirm_s（反应高亮时长，可选）
"""

from __future__ import annotations
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
from psychopy import visual, core, event

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


# ====================== 可调的全局参数 ======================
PRACTICE_N = 4

# 0-back 的目标提示是否常驻（默认常驻；可由 exp_info["show_target_always"] 覆盖）
SHOW_TARGET_ALWAYS = True
TARGET_SHOW_AT_START_S = 2.0  # 若不常驻：开头展示目标图的时长（小窗）

# "学习目标图"环节：是否启用、最短观看秒数（防止误按空格一闪而过）
STUDY_TARGET_BEFORE_PRACTICE = True
STUDY_MIN_S = 1.5

# （可选）进入正式阶段前再提醒一次目标图（不想要可改 False）
STUDY_TARGET_BEFORE_MAIN = False
STUDY_MAIN_MIN_S = 1.0

DEFAULT_DEADLINE = 3.2        # 三选一对老年人：建议 3.0~3.8；你可在 CSV 每行改
DEFAULT_FEEDBACK_S = 1.0
DEFAULT_ITI = 0.45
DEFAULT_CONFIRM = 0.20

# 过场页推进方式：空格 或 点击屏幕
ADVANCE_MIN_S = 0.8          # 过场页最短停留时间（防止误触一闪而过）
ALLOW_SCREEN_CLICK = True    # True: 允许点击屏幕推进；False: 仅空格推进

# 指导语图片（相对项目根目录）
INSTR_IMAGE_B1 = "assets/instruction/B1_1.png"

# 预加载图片（减少卡顿，提升 RT 稳定性）
PRELOAD_IMAGES = True

# 正式阶段超时提示（默认不提示，只记录）
SHOW_TIMEOUT_MAIN = False
TIMEOUT_FLASH_S_MAIN = 0.4

FIX_CHAR = "+"

# 默认目标图（如果 CSV 没写 target_file）
TARGET_DEFAULT = "B1_T_LivingRoom_Base.png"

LABEL_SAME = "一致"
LABEL_SIMILAR = "相似"
LABEL_DIFFERENT = "不同"

FONT_CN = CJK_FONT

# 目标小窗的大小与位置（保持原始大小，位置稍微往角落移避免重叠）
TARGET_PANEL_H_RATIO = 0.28  # 目标图高度占屏幕高度比例
TARGET_PANEL_POS = (-0.38, 0.38)  # (x,y) 坐标比例


# ====================== 数据结构 ======================
@dataclass
class Trial:
    phase: str                 # practice / main
    stim_path: Path
    target_path: Path
    correct: str               # same / similar / different
    deadline: float
    feedback_s: float          # 仅 practice 使用；main 忽略
    iti_s: float
    confirm_s: float
    meta: Dict[str, Any]


# ====================== 工具函数 ======================
def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _project_root() -> Path:
    # N-back/run/run_B1.py -> N-back
    return Path(__file__).resolve().parent.parent


def _contain_size(img_path: Path, max_w: float, max_h: float) -> Tuple[float, float]:
    """等比缩放：把图片完整放进 max_w × max_h（不裁剪、不拉伸）。"""
    try:
        from PIL import Image  # Pillow 通常可用；若不可用则回退
        with Image.open(img_path) as im:
            iw, ih = im.size
    except Exception:
        # 回退一个常见比例，避免崩溃
        iw, ih = 4.0, 3.0

    if iw <= 0 or ih <= 0:
        iw, ih = 4.0, 3.0

    scale = min(max_w / float(iw), max_h / float(ih))
    return float(iw) * scale, float(ih) * scale


def _safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _col(row: Dict[str, str], *names: str, default: str = "") -> str:
    keys = {k.lower(): k for k in row.keys()}
    for n in names:
        k = n.lower()
        if k in keys:
            return row[keys[k]]
    return default


def _float_or(x: Any, default: float) -> float:
    try:
        s = str(x).strip()
        if s == "" or s.lower() in ("nan", "none", "null"):
            return default
        return float(s)
    except Exception:
        return default


def _norm_resp(x: Any) -> str:
    s = str(x).strip().lower()
    zh_map = {"一致": "same", "相似": "similar", "不同": "different"}
    if s in ("same", "similar", "different"):
        return s
    if s in zh_map:
        return zh_map[s]
    return s


def _resolve_image(root: Path, block: str, list_name: str, maybe_path: str) -> Path:
    """
    允许 CSV 写：
    - 相对路径（如 stimuli/B1/ListA/xxx.png）
    - 仅文件名（如 xxx.png），则自动在 stimuli/B1/<list_name>/ 下找；找不到再回退到 ListA
    """
    p = Path(str(maybe_path).strip())
    if not str(p):
        return p

    cand = (root / p).resolve()
    if cand.exists():
        return cand

    stim_dir = root / "stimuli" / block / list_name
    if not stim_dir.exists():
        stim_dir = root / "stimuli" / block / "ListA"

    cand2 = (stim_dir / p.name).resolve()
    if cand2.exists():
        return cand2

    for suf in [".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG"]:
        cand3 = (stim_dir / (p.stem + suf)).resolve()
        if cand3.exists():
            return cand3

    stem = p.stem.lower().replace(" ", "")
    for f in stim_dir.glob("*"):
        if f.is_file() and f.stem.lower().replace(" ", "") == stem:
            return f.resolve()

    return cand2


def key_to_resp(k: str) -> Optional[str]:
    k = k.lower()
    if k in ("1", "left"):
        return "same"
    if k in ("2", "down"):
        return "similar"
    if k in ("3", "right"):
        return "different"
    return None


def resp_to_label(resp: str) -> str:
    return {"same": LABEL_SAME, "similar": LABEL_SIMILAR, "different": LABEL_DIFFERENT}.get(resp, resp)


def make_text(win: visual.Window, text: str, height_pix: float, pos=(0, 0)) -> visual.TextStim:
    return visual.TextStim(
        win,
        text=text,
        color="white",
        height=height_pix,
        wrapWidth=win.size[0] * 0.92,
        alignText="center",
        pos=pos,
        font=FONT_CN,
        units="pix",
    )


def wait_advance_with_draw(
    win: visual.Window,
    drawables: List[Any],
    min_wait_s: float = 0.0,
    allow_space: bool = True,
    allow_click: bool = True,
) -> None:
    """过场页等待：空格 或 点击屏幕底部中央按钮区域。支持最短等待时间。"""
    mouse = event.Mouse(win=win)

    # 防止按住鼠标导致秒过
    while any(mouse.getPressed()):
        core.wait(0.01)

    event.clearEvents()
    clock = core.Clock()

    while True:
        if allow_space:
            keys = event.getKeys(keyList=["space", "escape"])
            if "escape" in keys:
                core.quit()
            if "space" in keys and clock.getTime() >= min_wait_s:
                return
        else:
            keys = event.getKeys(keyList=["escape"])
            if "escape" in keys:
                core.quit()

        if allow_click:
            if mouse.getPressed()[0] and clock.getTime() >= min_wait_s:
                while any(mouse.getPressed()):
                    core.wait(0.01)
                return

        for d in drawables:
            d.draw()
        win.flip()


# 兼容旧函数名（尽量少动其它代码）
def wait_space_with_draw(win: visual.Window, drawables: List[Any], min_wait_s: float = 0.0) -> None:
    wait_advance_with_draw(
        win,
        drawables,
        min_wait_s=min_wait_s,
        allow_space=True,
        allow_click=ALLOW_SCREEN_CLICK,
    )


def show_instruction_image(win: visual.Window, img_path: Path, min_s: float = ADVANCE_MIN_S) -> None:
    """指导语图片 + 底部交互按钮（有hover/press反馈）。
    图片缩小到82%并上移，按钮在底部。"""
    canvas_w, canvas_h = win.size

    try:
        from PIL import Image as PILImage
        iw, ih = PILImage.open(str(img_path)).size
    except Exception:
        iw, ih = 1920, 1080

    img_scale = 0.82
    max_w = canvas_w * img_scale
    max_h = canvas_h * img_scale
    fw, fh = _contain_size(img_path, max_w, max_h)
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
    t0 = time.perf_counter()
    prev = True

    while True:
        now = time.perf_counter()
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

def preload_image_cache(win: visual.Window, paths: List[Path]) -> Dict[str, visual.ImageStim]:
    """预加载图片纹理（尽量不影响现有结构）。"""
    cache: Dict[str, visual.ImageStim] = {}
    placeholder = np.zeros((8, 8, 3), dtype=np.uint8)
    for p in paths:
        try:
            if p and p.exists():
                stim = visual.ImageStim(
                    win,
                    image=placeholder,
                    size=(1, 1),
                    pos=(9999, 9999),  # 放到屏幕外
                    units="pix",
                    autoLog=False,
                )
                stim.image = str(p)
                cache[str(p)] = stim
        except Exception:
            # 预加载失败不影响任务继续
            continue
    return cache


def build_buttons(win: visual.Window):
    """下方三按钮：一致/相似/不同（支持触屏点击）"""
    w, h = win.size
    btn_w = w * 0.26
    btn_h = h * 0.14
    y = -h * 0.38
    xs = [-w * 0.30, 0, w * 0.30]

    rects, texts = [], []
    labs = [f"{LABEL_SAME}\n(1)", f"{LABEL_SIMILAR}\n(2)", f"{LABEL_DIFFERENT}\n(3)"]
    for x, lab in zip(xs, labs):
        rects.append(
            visual.Rect(
                win,
                width=btn_w,
                height=btn_h,
                pos=(x, y),
                lineColor="white",
                fillColor=None,
                lineWidth=3,
                units="pix",
            )
        )
        texts.append(
            visual.TextStim(
                win,
                text=lab,
                color="white",
                height=h * 0.045,
                pos=(x, y),
                alignText="center",
                font=FONT_CN,
                units="pix",
            )
        )
    return rects, texts


def draw_fixation(win: visual.Window, fix_stim: visual.TextStim, dur: float) -> None:
    if dur <= 0:
        win.flip()
        return
    clock = core.Clock()
    while clock.getTime() < dur:
        fix_stim.draw()
        win.flip()


def show_study_target(win: visual.Window, target_path: Path, title: str, min_s: float) -> None:
    """开始前的"学习目标图"展示：标题+图片+提示作为一个整体上下对称居中。"""
    w, h = win.size

    # 字号（老年被试友好）
    title_font = h * 0.06
    tip_font = h * 0.045

    # 文本块高度估计（用于整体对称居中布局）
    title_block_h = title_font * 1.25
    tip_lines = 2  # 这里固定两行提示
    tip_block_h = tip_lines * tip_font * 1.35

    gap1 = h * 0.03  # 标题-图片
    gap2 = h * 0.035  # 图片-提示

    # 预留给图片的最大空间（不拉伸）
    max_stack_h = h * 0.92
    img_max_h = max(120.0, max_stack_h - title_block_h - tip_block_h - gap1 - gap2)
    img_max_w = w * 0.82  # 留出左右黑边，更"对称"
    img_w, img_h = _contain_size(target_path, img_max_w, img_max_h)

    # 计算整体堆叠高度，然后整体居中
    stack_h = title_block_h + gap1 + img_h + gap2 + tip_block_h
    top_y = stack_h / 2.0

    title_y = top_y - title_block_h / 2.0
    img_y = title_y - title_block_h / 2.0 - gap1 - img_h / 2.0
    tip_y = img_y - img_h / 2.0 - gap2 - tip_block_h / 2.0

    placeholder = np.zeros((8, 8, 3), dtype=np.uint8)
    img = visual.ImageStim(win, image=placeholder, size=(img_w, img_h), pos=(0, img_y), units="pix")
    img.image = str(target_path)

    lab = visual.TextStim(
        win,
        text=title,
        color="white",
        height=title_font,
        pos=(0, title_y),
        alignText="center",
        font=FONT_CN,
        units="pix",
    )
    tip = visual.TextStim(
        win,
        text="记住这张目标图\n\n准备好后按屏幕继续",
        color="white",
        height=tip_font,
        pos=(0, tip_y),
        alignText="center",
        wrapWidth=w * 0.9,
        font=FONT_CN,
        units="pix",
    )
    wait_space_with_draw(win, [lab, img, tip], min_wait_s=max(0.0, float(min_s)))

# ====================== 读 CSV ======================
def load_trials(list_csv: Path, list_name: str) -> List[Trial]:
    root = _project_root()
    rows: List[Dict[str, str]] = []
    with list_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if any((v or "").strip() for v in r.values()):
                rows.append(r)

    def is_practice(r: Dict[str, str], idx: int) -> bool:
        ph = _col(r, "phase", default="").strip().lower()
        if ph in ("practice", "练习"):
            return True
        if ph in ("main", "formal", "正式"):
            return False
        return idx < PRACTICE_N

    trials: List[Trial] = []
    for i, r in enumerate(rows):
        phase = "practice" if is_practice(r, i) else "main"

        stim_file = _col(r, "stim_file", "image", "stim", default="").strip()
        if not stim_file:
            raise ValueError(f"CSV 第 {i+1} 行缺少 stim_file")

        stim_path = _resolve_image(root, "B1", list_name, stim_file)

        target_file = _col(r, "target_file", "target", default="").strip() or TARGET_DEFAULT
        target_path = _resolve_image(root, "B1", list_name, target_file)

        corr = _norm_resp(_col(r, "correct_resp", "correct", "answer", default=""))
        if corr not in ("same", "similar", "different"):
            raise ValueError(f"CSV 第 {i+1} 行 correct_resp 不合法：{corr}")

        deadline = _float_or(_col(r, "resp_deadline_s", "deadline_s", "deadline", default=""), DEFAULT_DEADLINE)
        feedback_s = _float_or(_col(r, "feedback_s", "feedback", default=""), DEFAULT_FEEDBACK_S)
        iti_s = _float_or(_col(r, "iti_s", "iti", default=""), DEFAULT_ITI)
        confirm_s = _float_or(_col(r, "confirm_s", "confirm_highlight_s", default=""), DEFAULT_CONFIRM)

        trials.append(
            Trial(
                phase=phase,
                stim_path=stim_path,
                target_path=target_path,
                correct=corr,
                deadline=deadline,
                feedback_s=feedback_s,
                iti_s=iti_s,
                confirm_s=confirm_s,
                meta=r,
            )
        )

    return trials


# ====================== 运行一个 phase ======================
def run_phase(
    win: visual.Window,
    trials: List[Trial],
    phase: str,
    list_name: str,
    show_target_always: bool,
    show_timeout_main: bool,
) -> List[Dict[str, Any]]:
    mouse = event.Mouse(win=win)
    win.mouseVisible = True
    mouse.setVisible(True)

    rects, texts = build_buttons(win)
    fix = visual.TextStim(
        win,
        text=FIX_CHAR,
        color="white",
        height=win.size[1] * 0.10,
        pos=(0, 0),
        font=FONT_CN,
        units="pix",
    )

    w, h = win.size
    # 当前图中央
    img_h = h * 0.66
    img_w = img_h * (4 / 3)

    placeholder = np.zeros((8, 8, 3), dtype=np.uint8)
    stim_img = visual.ImageStim(win, image=placeholder, size=(img_w, img_h), pos=(0, h * 0.06), units="pix")

    # 目标图（更大 + 左上）
    target_h = h * TARGET_PANEL_H_RATIO
    target_w = target_h * (4 / 3)
    tx = w * TARGET_PANEL_POS[0]
    ty = h * TARGET_PANEL_POS[1]
    target_img = visual.ImageStim(win, image=placeholder, size=(target_w, target_h), pos=(tx, ty), units="pix")
    target_border = visual.Rect(
        win,
        width=target_w + 8,
        height=target_h + 8,
        pos=(tx, ty),
        lineColor="white",
        fillColor=None,
        lineWidth=2,
        units="pix",
    )
    target_lab = visual.TextStim(
        win,
        text="目标图",
        color="white",
        height=h * 0.035,
        pos=(tx, ty + target_h * 0.62),
        font=FONT_CN,
        units="pix",
    )

    hint = visual.TextStim(
        win,
        text="和目标图比：相同？相似？不同？",
        color="white",
        height=h * 0.042,
        pos=(0, h * 0.36),
        font=FONT_CN,
        units="pix",
    )

    fb_text = visual.TextStim(
        win,
        text="",
        color="white",
        height=h * 0.085,
        pos=(0, 0),
        wrapWidth=w * 0.92,
        alignText="center",
        font=FONT_CN,
        units="pix",
    )

    phase_trials = [t for t in trials if t.phase == phase]
    results: List[Dict[str, Any]] = []

    # 目标图：取本 phase 第一行
    if phase_trials:
        if not phase_trials[0].target_path.exists():
            raise FileNotFoundError(f"目标图不存在：{phase_trials[0].target_path}")
        target_img.image = str(phase_trials[0].target_path)

    # 若不常驻：开头展示一次（小窗展示）
    if phase_trials and (not show_target_always):
        clock = core.Clock()
        while clock.getTime() < max(0.2, TARGET_SHOW_AT_START_S):
            target_border.draw()
            target_img.draw()
            target_lab.draw()
            tip = visual.TextStim(
                win,
                text="记住这张目标图",
                color="white",
                height=h * 0.06,
                pos=(0, -h * 0.10),
                font=FONT_CN,
                units="pix",
            )
            tip.draw()
            win.flip()
        draw_fixation(win, fix, 0.4)

    for ti, t in enumerate(phase_trials, start=1):
        if not t.stim_path.exists():
            raise FileNotFoundError(f"当前图不存在：{t.stim_path}")
        if not t.target_path.exists():
            raise FileNotFoundError(f"目标图不存在：{t.target_path}")

        target_img.image = str(t.target_path)
        stim_img.image = str(t.stim_path)

        # 防止按住鼠标导致"秒选"
        while any(mouse.getPressed()):
            core.wait(0.01)

        event.clearEvents()
        clock = core.Clock()
        resp = ""
        rt: Any = ""
        chosen_idx: Optional[int] = None

        deadline = t.deadline if t.deadline > 0 else DEFAULT_DEADLINE

        while True:
            if show_target_always:
                target_border.draw()
                target_img.draw()
                target_lab.draw()

            stim_img.draw()
            hint.draw()

            for r in rects:
                r.draw()
            for txs in texts:
                txs.draw()

            win.flip()

            keys = event.getKeys()
            if "escape" in keys:
                core.quit()

            for k in keys:
                rr = key_to_resp(k)
                if rr is not None:
                    resp = rr
                    chosen_idx = {"same": 0, "similar": 1, "different": 2}[resp]
                    rt = clock.getTime()
                    break
            if resp:
                break

            if mouse.getPressed()[0]:
                mx, my = mouse.getPos()
                for bi, rect in enumerate(rects):
                    if rect.contains((mx, my)):
                        resp = ["same", "similar", "different"][bi]
                        chosen_idx = bi
                        rt = clock.getTime()
                        break
                while any(mouse.getPressed()):
                    core.wait(0.01)
                if resp:
                    break

            if clock.getTime() >= deadline:
                break

        is_correct = int(resp == t.correct) if resp else 0

        # ===== 超时提示（正式阶段可选） =====
        if resp == "" and phase == "main" and show_timeout_main and TIMEOUT_FLASH_S_MAIN > 0:
            fb_text.text = "超时"
            flash_clock = core.Clock()
            while flash_clock.getTime() < TIMEOUT_FLASH_S_MAIN:
                fb_text.draw()
                win.flip()

        # ===== 反应确认：高亮按钮 =====
        if resp != "" and t.confirm_s > 0:
            event.clearEvents()
            conf_clock = core.Clock()
            while conf_clock.getTime() < t.confirm_s:
                if show_target_always:
                    target_border.draw()
                    target_img.draw()
                    target_lab.draw()

                stim_img.draw()
                hint.draw()

                for bi, r in enumerate(rects):
                    if chosen_idx is not None and bi == chosen_idx:
                        r.fillColor = "white"
                        r.lineColor = "white"
                        r.lineWidth = 5
                    else:
                        r.fillColor = None
                        r.lineColor = "white"
                        r.lineWidth = 3
                    r.draw()
                for txs in texts:
                    txs.draw()

                win.flip()

            for r in rects:
                r.fillColor = None
                r.lineColor = "white"
                r.lineWidth = 3

        # ===== 练习反馈页：单开一页 =====
        if phase == "practice":
            fb_dur = t.feedback_s if t.feedback_s > 0 else DEFAULT_FEEDBACK_S
            if fb_dur > 0:
                if resp == "":
                    fb_text.text = "超时，请快些作答"
                elif is_correct:
                    fb_text.text = "正确!"
                else:
                    fb_text.text = f"错误\n\n正确答案：{resp_to_label(t.correct)}"

                fb_clock = core.Clock()
                while fb_clock.getTime() < fb_dur:
                    fb_text.draw()
                    win.flip()

        # ===== 正式/练习：都用注视点分隔 =====
        event.clearEvents()
        draw_fixation(win, fix, t.iti_s)

        results.append({
            "list_name": list_name,
            "phase": phase,
            "trial_in_phase": ti,
            "stim_file": str(t.stim_path),
            "target_file": str(t.target_path),
            "correct_resp": t.correct,
            "resp": resp,
            "rt_s": rt,
            "is_correct": is_correct if resp else 0,
            "resp_deadline_s": deadline,
            "confirm_s": t.confirm_s,
            "iti_s": t.iti_s,
            "feedback_s": t.feedback_s,
        })

    return results


# ====================== 主入口 ======================
def run_B1(
    win: Optional[visual.Window] = None,
    exp_info: Optional[Dict[str, Any]] = None,
    list_name: str = "ListA",
) -> Dict[str, Any]:

    root = _project_root()

    list_csv = root / "lists" / f"B1_{list_name}.csv"
    if not list_csv.exists():
        alt = root / "lists" / "B1_ListA.csv"
        if alt.exists():
            list_csv = alt
        else:
            raise FileNotFoundError(f"找不到 list：{list_csv}")

    trials = load_trials(list_csv, list_name=list_name)

    created_win = False
    if win is None:
        win = visual.Window(
            fullscr=True,
            units="pix",
            color=[-0.9, -0.9, -0.9],
            allowGUI=False
        )
        created_win = True

    win.mouseVisible = True

    exp_info = exp_info or {}

    # ===== 可选参数（可由 run_all 通过 exp_info 传入） =====
    show_target_always = bool(exp_info.get("show_target_always", SHOW_TARGET_ALWAYS))
    show_timeout_main = bool(exp_info.get("show_timeout_main", SHOW_TIMEOUT_MAIN))
    do_preload = bool(exp_info.get("preload_images", PRELOAD_IMAGES))

    participant = str(exp_info.get("participant", "test"))
    session = str(exp_info.get("session", "1"))
    tag = _now_tag()

    w, h = win.size

    # ===== 指导语：图片 =====
    instr_img_path = root / INSTR_IMAGE_B1
    if not instr_img_path.exists():
        raise FileNotFoundError(f"找不到指导语图片：{instr_img_path}")
    show_instruction_image(win, instr_img_path, min_s=ADVANCE_MIN_S)

    # 选择一张目标图用于"学习"展示（取第一条 trial 的 target）
    first_target = next((t.target_path for t in trials if t.target_path), None)
    if first_target is None or (not first_target.exists()):
        # 兜底：用默认
        first_target = _resolve_image(root, "B1", list_name, TARGET_DEFAULT)

    # ===== 预加载（可选） =====
    _preload_cache = {}
    if do_preload:
        uniq_paths = []
        seen = set()
        for t in trials:
            for pp in (t.stim_path, t.target_path):
                sp = str(pp)
                if sp and sp not in seen:
                    seen.add(sp)
                    uniq_paths.append(pp)
        _preload_cache = preload_image_cache(win, uniq_paths)

    if STUDY_TARGET_BEFORE_PRACTICE:
        show_study_target(win, first_target, "学习目标图", min_s=STUDY_MIN_S)

    p1 = make_text(win, "练习开始\n\n按屏幕继续", height_pix=h * 0.07)
    wait_space_with_draw(win, [p1], min_wait_s=ADVANCE_MIN_S)

    prac = run_phase(
        win, trials,
        phase="practice",
        list_name=list_name,
        show_target_always=show_target_always,
        show_timeout_main=show_timeout_main,
    )

    prac_acc = (sum(r["is_correct"] for r in prac) / len(prac)) if prac else 0
    p2 = make_text(
        win,
        f"练习结束\n\n正确率：{prac_acc*100:.0f}%\n\n按屏幕进入正式任务",
        height_pix=h * 0.07
    )
    wait_space_with_draw(win, [p2], min_wait_s=ADVANCE_MIN_S)

    if STUDY_TARGET_BEFORE_MAIN:
        show_study_target(win, first_target, "再看一眼目标图", min_s=STUDY_MAIN_MIN_S)

    m1 = make_text(
        win,
        "正式任务开始\n\n请尽量又快又准\n\n按屏幕继续",
        height_pix=h * 0.07
    )
    wait_space_with_draw(win, [m1], min_wait_s=ADVANCE_MIN_S)

    main = run_phase(
        win, trials,
        phase="main",
        list_name=list_name,
        show_target_always=show_target_always,
        show_timeout_main=show_timeout_main,
    )

    m2 = make_text(win, "本部分结束\n\n按屏幕继续", height_pix=h * 0.07)
    wait_space_with_draw(win, [m2], min_wait_s=ADVANCE_MIN_S)

    # 保存结果
    out_root = root / "result"
    raw_dir = out_root / "raw"
    summary_dir = out_root / "summary"
    _safe_mkdir(raw_dir)
    _safe_mkdir(summary_dir)

    raw_path = raw_dir / f"{participant}_sess{session}_B1_{list_name}_{tag}.csv"
    all_rows = prac + main
    if all_rows:
        with raw_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    def acc(rows):
        return (sum(r["is_correct"] for r in rows) / len(rows)) if rows else ""

    def mean_rt(rows):
        rts = [r["rt_s"] for r in rows if isinstance(r["rt_s"], (float, int)) and r["resp"] != ""]
        return (sum(rts) / len(rts)) if rts else ""

    summary = {
        "participant": participant,
        "session": session,
        "block": "B1",
        "list_name": list_name,
        "n_practice": len(prac),
        "n_main": len(main),
        "acc_practice": acc(prac),
        "acc_main": acc(main),
        "mean_rt_main": mean_rt(main),
        "raw_path": str(raw_path),
    }

    summary_path = summary_dir / f"{participant}_sess{session}_B1_{list_name}_{tag}_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        wri = csv.DictWriter(f, fieldnames=list(summary.keys()))
        wri.writeheader()
        wri.writerow(summary)

    if created_win:
        win.close()
        core.quit()

    return summary


if __name__ == "__main__":
    run_B1(win=None, exp_info={"participant": "test", "session": "1"}, list_name="ListA")