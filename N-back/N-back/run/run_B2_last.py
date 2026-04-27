# -*- coding: utf-8 -*-
"""
run_B2.py  (B2 = 1-back, 3AFC: 一致 / 相似 / 不同) — 传统"单序列呈现" + 练习反馈单独页面

你提的关键点已实现：
✅ 练习阶段：作答后先"按钮高亮确认(已记录)" → 再进入【单独反馈页】显示正确/错误(+正确答案)
✅ 正式阶段：不显示对错反馈；作答后"按钮高亮确认" → 注视点空屏(ITI/ISI)
✅ 单序列呈现：每次只呈现"当前图片"，被试需与"上一张图片"比较（上一张不显示）
✅ 第1张（或 correct 为空/NaN 的行）：仅呈现用于"建立上一张"记忆，不要求作答（warmup）

CSV 兼容：
- phase: practice/main 或 练习/正式；若缺省则前 PRACTICE_N 行为练习
- image: 可写 image / stim_file / stim / file
- correct: same/similar/different 或 一致/相似/不同；为空则表示"只看不答"
- stim_dur: 当前图的"先看图"时长（秒）
- resp_deadline: 作答时限（秒）；<=0 则本 trial 不作答
- isi: 题间注视点时长（秒）
- feedback: 0=不反馈；1=用默认反馈时长；>1.5=直接视为反馈时长(秒)
"""

from __future__ import annotations
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

try:
    from PIL import Image
except Exception:
    Image = None

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


# ====================== 可调默认参数（CSV 不写/写空时用）======================
PRACTICE_N = 4

DEFAULT_STIM_DUR = 1.0
DEFAULT_DEADLINE = 2.5      # 老年三选一一般建议 2.5~3.5；你也可直接在 CSV 每行调
DEFAULT_ISI = 0.35          # 注视点空屏（更清楚分 trial）
DEFAULT_FEEDBACK_S = 0.9    # 练习反馈页默认时长
DEFAULT_CONFIRM_S = 0.20    # 反应后按钮高亮确认

# ===== 过场页/指导语（按你统一交互：空格 或 点击屏幕推进 + 最短等待） =====
ADVANCE_MIN_S = 0.8          # 过场页最短停留时间（防误触一闪而过）
ALLOW_SCREEN_CLICK = True    # True: 允许点击屏幕推进；False: 仅空格推进
INSTR_IMAGE_B2 = "assets/instruction/B2_1.png"  # 指导语图片（相对项目根目录）

# 预加载图片（减少卡顿，提升 RT 稳定性）
PRELOAD_IMAGES = True

# 正式阶段超时提示（默认不提示，只记录；可由 exp_info 覆盖）
SHOW_TIMEOUT_MAIN = False
TIMEOUT_FLASH_S_MAIN = 0.4

FIX_CHAR = "+"
FONT_CN = CJK_FONT

LABEL_SAME = "一致"
LABEL_SIMILAR = "相似"
LABEL_DIFFERENT = "不同"


# ====================== 数据结构 ======================
@dataclass
class Trial:
    phase: str              # practice / main
    image_path: Path
    correct: str            # same/similar/different/""(空=只看不答)
    stim_dur: float
    resp_deadline: float
    isi: float
    feedback_dur: float     # 0=无反馈（正式阶段通常为0）
    confirm_s: float
    meta: Dict[str, Any]


# ====================== 工具函数 ======================
def _now_tag() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _project_root() -> Path:
    # N-back/run/run_B2.py -> N-back
    return Path(__file__).resolve().parent.parent


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
    if s in ("", "nan", "none", "null"):
        return ""
    zh_map = {"一致": "same", "相似": "similar", "不同": "different"}
    if s in ("same", "similar", "different"):
        return s
    if s in zh_map:
        return zh_map[s]
    return s


def _resolve_image(root: Path, block: str, list_name: str, maybe_path: str) -> Path:
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


def wait_space(win: visual.Window, stim: visual.TextStim, min_wait_s: float = 0.0) -> None:
    """兼容旧调用：显示一个文本并等待推进。"""
    wait_advance_with_draw(
        win,
        [stim],
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
    """预加载图片纹理（尽量不改变主逻辑）。"""
    cache: Dict[str, visual.ImageStim] = {}
    placeholder = np.zeros((8, 8, 3), dtype=np.uint8)
    for p in paths:
        try:
            if p and p.exists():
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


def draw_fixation(win: visual.Window, fix: visual.TextStim, dur: float) -> None:
    if dur <= 0:
        win.flip()
        return
    clk = core.Clock()
    while clk.getTime() < dur:
        fix.draw()
        win.flip()


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

        img_file = _col(r, "image", "stim_file", "stim", "file", default="").strip()
        if not img_file:
            raise ValueError(f"CSV 第 {i+1} 行缺少 image/stim_file")
        img_path = _resolve_image(root, "B2", list_name, img_file)

        corr = _norm_resp(_col(r, "correct", "correct_resp", "answer", default=""))

        stim_dur = _float_or(_col(r, "stim_dur", "stimdur", default=""), DEFAULT_STIM_DUR)
        deadline = _float_or(_col(r, "resp_deadline", "deadline", "resp_deadline_s", default=""), DEFAULT_DEADLINE)
        isi = _float_or(_col(r, "isi", "iti", "iti_s", default=""), DEFAULT_ISI)

        # feedback 列：0/1/秒数
        fb_raw = _col(r, "feedback", "feedback_s", default="")
        fb_val = _float_or(fb_raw, 0.0)
        if phase != "practice":
            fb_dur = 0.0
        else:
            if fb_val <= 0.0:
                fb_dur = 0.0
            elif fb_val <= 1.5:
                fb_dur = DEFAULT_FEEDBACK_S
            else:
                fb_dur = fb_val

        # 若 correct 为空或 deadline<=0：视作只看不答（warmup/encoding-only）
        if corr == "" or deadline <= 0:
            corr = ""
            deadline = 0.0
            fb_dur = 0.0

        trials.append(
            Trial(
                phase=phase,
                image_path=img_path,
                correct=corr,
                stim_dur=max(0.0, stim_dur),
                resp_deadline=max(0.0, deadline),
                isi=max(0.0, isi),
                feedback_dur=max(0.0, fb_dur),
                confirm_s=DEFAULT_CONFIRM_S,
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
    show_timeout_main: bool,
) -> List[Dict[str, Any]]:
    mouse = event.Mouse(win=win)
    win.mouseVisible = True
    mouse.setVisible(True)

    rects, texts = build_buttons(win)
    fix = visual.TextStim(win, text=FIX_CHAR, color="white", height=win.size[1] * 0.10,
                          pos=(0, 0), font=FONT_CN, units="pix")

    w, h = win.size
    img_h = h * 0.68
    img_w = img_h * (4 / 3)

    placeholder = np.zeros((8, 8, 3), dtype=np.uint8)
    img = visual.ImageStim(win, image=placeholder, size=(img_w, img_h), pos=(0, h * 0.08), units="pix")

    hint = visual.TextStim(
        win,
        text="和上一张比：相同？相似？不同？",
        color="white",
        height=h * 0.042,
        pos=(0, h * 0.36),
        font=FONT_CN,
        units="pix",
    )

    fb = visual.TextStim(
        win,
        text="",
        color="white",
        height=h * 0.08,
        wrapWidth=w * 0.92,
        alignText="center",
        pos=(0, 0),
        font=FONT_CN,
        units="pix",
    )

    phase_trials = [t for t in trials if t.phase == phase]
    results: List[Dict[str, Any]] = []

    for ti, t in enumerate(phase_trials, start=1):
        if not t.image_path.exists():
            raise FileNotFoundError(f"图片不存在：{t.image_path}")

        img.image = str(t.image_path)

        # 防止按住鼠标导致"秒选"
        while any(mouse.getPressed()):
            core.wait(0.01)

        # ========= 1) 先看图（encoding） =========
        if t.stim_dur > 0:
            clk = core.Clock()
            while clk.getTime() < t.stim_dur:
                img.draw()
                win.flip()

        # ========= 2) 若该 trial 需要作答：进入作答界面 =========
        resp = ""
        rt: Any = ""
        chosen_idx: Optional[int] = None
        is_correct = 0

        if t.correct != "" and t.resp_deadline > 0:
            event.clearEvents()
            clock = core.Clock()

            while True:
                img.draw()
                hint.draw()
                for r in rects:
                    r.draw()
                for tx in texts:
                    tx.draw()

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

                if clock.getTime() >= t.resp_deadline:
                    break

            is_correct = int(resp == t.correct) if resp else 0

            # ===== 超时提示（正式阶段可选：默认不提示，只记录） =====
            if resp == "" and phase == "main" and show_timeout_main and TIMEOUT_FLASH_S_MAIN > 0:
                fb.text = "超时"
                flash_clk = core.Clock()
                while flash_clk.getTime() < TIMEOUT_FLASH_S_MAIN:
                    fb.draw()
                    win.flip()

            # ========= 反应确认：按钮高亮 =========
            if resp != "" and t.confirm_s > 0:
                # 锁定输入：清空事件，确认阶段不再读键鼠
                event.clearEvents()
                conf_clk = core.Clock()
                while conf_clk.getTime() < t.confirm_s:
                    img.draw()
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
                    for tx in texts:
                        tx.draw()
                    win.flip()

                for r in rects:
                    r.fillColor = None
                    r.lineColor = "white"
                    r.lineWidth = 3

                event.clearEvents()

            # ========= 练习反馈页（单独页面）=========
            if phase == "practice" and t.feedback_dur > 0:
                if resp == "":
                    fb.text = "超时，请快些作答"
                elif is_correct:
                    fb.text = "正确!"
                else:
                    fb.text = f"错误\n\n正确答案：{resp_to_label(t.correct)}"
                fb_clk = core.Clock()
                while fb_clk.getTime() < t.feedback_dur:
                    fb.draw()
                    win.flip()

        # ========= 3) 题间注视点 =========
        event.clearEvents()
        draw_fixation(win, fix, t.isi)

        results.append({
            "list_name": list_name,
            "phase": phase,
            "trial_in_phase": ti,
            "image_file": str(t.image_path),
            "correct_resp": t.correct,
            "resp": resp,
            "rt_s": rt,
            "is_correct": is_correct,
            "stim_dur": t.stim_dur,
            "resp_deadline": t.resp_deadline,
            "isi": t.isi,
            "feedback_dur": t.feedback_dur,
        })

    return results


# ====================== 主入口 ======================
def run_B2(win: Optional[visual.Window] = None,
           exp_info: Optional[Dict[str, Any]] = None,
           list_name: str = "ListA") -> Dict[str, Any]:

    root = _project_root()

    # 兼容两种命名：B2_ListA.csv 或 B2_ListA_v2_*.csv
    list_csv = root / "lists" / f"B2_{list_name}.csv"
    if not list_csv.exists():
        alt = root / "lists" / f"B2_{list_name}.csv".replace("B2_", "B2_")  # no-op
        if alt.exists():
            list_csv = alt
        else:
            # 最常见兜底
            alt2 = root / "lists" / "B2_ListA.csv"
            if alt2.exists():
                list_csv = alt2
            else:
                # 再兜底：找一个 B2_*list_name*.csv
                cands = list((root / "lists").glob(f"B2*{list_name}*.csv"))
                if cands:
                    list_csv = cands[0]
                else:
                    raise FileNotFoundError(f"找不到 B2 的 list 文件（期望 {root/'lists'} 下存在 B2_{list_name}.csv）")

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
    # 可选开关（保持默认即可；run_all 可通过 exp_info 覆盖）
    do_preload = bool(exp_info.get("preload_images", PRELOAD_IMAGES))
    show_timeout_main = bool(exp_info.get("show_timeout_main", SHOW_TIMEOUT_MAIN))
    advance_min_s = _float_or(exp_info.get("advance_min_s", ADVANCE_MIN_S), ADVANCE_MIN_S)
    participant = str(exp_info.get("participant", "test"))
    session = str(exp_info.get("session", "1"))
    tag = _now_tag()

    w, h = win.size

    # ===== 指导语：图片 =====
    instr_img_path = root / INSTR_IMAGE_B2
    if not instr_img_path.exists():
        raise FileNotFoundError(f"找不到指导语图片：{instr_img_path}")
    show_instruction_image(win, instr_img_path, min_s=advance_min_s)

    # ===== 预加载（可选） =====
    if do_preload:
        uniq_paths: List[Path] = []
        seen = set()
        for t in trials:
            sp = str(t.image_path)
            if sp and sp not in seen:
                seen.add(sp)
                uniq_paths.append(t.image_path)
        _ = preload_image_cache(win, uniq_paths)

    p1 = make_text(win, "练习开始\n\n第1张只看不答\n\n按屏幕继续", height_pix=h * 0.07)
    wait_space(win, p1, min_wait_s=advance_min_s)

    prac = run_phase(win, trials, phase="practice", list_name=list_name, show_timeout_main=show_timeout_main)
    prac_acc = (sum(r["is_correct"] for r in prac if r["correct_resp"] != "") /
                max(1, sum(1 for r in prac if r["correct_resp"] != "")))

    p2 = make_text(win, f"练习结束\n\n正确率：{prac_acc*100:.0f}%\n\n按屏幕进入正式任务", height_pix=h * 0.07)
    wait_space(win, p2, min_wait_s=advance_min_s)

    m1 = make_text(win, "正式任务开始\n\n请尽量又快又准\n\n按屏幕继续", height_pix=h * 0.07)
    wait_space(win, m1, min_wait_s=advance_min_s)

    main = run_phase(win, trials, phase="main", list_name=list_name, show_timeout_main=show_timeout_main)

    m2 = make_text(win, "本部分结束\n\n按屏幕继续", height_pix=h * 0.07)
    wait_space(win, m2, min_wait_s=advance_min_s)

    # 保存结果
    out_root = root / "result"
    raw_dir = out_root / "raw"
    summary_dir = out_root / "summary"
    _safe_mkdir(raw_dir)
    _safe_mkdir(summary_dir)

    raw_path = raw_dir / f"{participant}_sess{session}_B2_{list_name}_{tag}.csv"
    all_rows = prac + main
    if all_rows:
        with raw_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)

    def acc(rows):
        scored = [r for r in rows if r["correct_resp"] != ""]
        return (sum(r["is_correct"] for r in scored) / len(scored)) if scored else ""

    def mean_rt(rows):
        rts = [r["rt_s"] for r in rows if isinstance(r["rt_s"], (float, int)) and r["resp"] != ""]
        return (sum(rts) / len(rts)) if rts else ""

    summary = {
        "participant": participant,
        "session": session,
        "block": "B2",
        "list_name": list_name,
        "n_practice": len(prac),
        "n_main": len(main),
        "acc_practice": acc(prac),
        "acc_main": acc(main),
        "mean_rt_main": mean_rt(main),
        "raw_path": str(raw_path),
    }

    summary_path = summary_dir / f"{participant}_sess{session}_B2_{list_name}_{tag}_summary.csv"
    with summary_path.open("w", encoding="utf-8-sig", newline="") as f:
        wri = csv.DictWriter(f, fieldnames=list(summary.keys()))
        wri.writeheader()
        wri.writerow(summary)

    if created_win:
        win.close()
        core.quit()

    return summary


if __name__ == "__main__":
    run_B2(win=None, exp_info={"participant": "test", "session": "1"}, list_name="ListA")
