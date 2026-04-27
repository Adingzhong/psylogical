# -*- coding: utf-8 -*-
"""
run_A1_opt_v2.py — A1 水果数字顺序（N=6）优化版 PsychoPy
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from psychopy import core, event, visual
import sys


def _get_cjk_font():
    """Return a CJK-capable font name for the current platform."""
    if sys.platform == "darwin":
        for f in ["Heiti SC", "STHeiti", "PingFang SC", "Hiragino Sans GB"]:
            try:
                from matplotlib.font_manager import findfont, FontProperties
                if findfont(FontProperties(family=f)) != findfont(FontProperties()):
                    return f
            except Exception:
                pass
        return "Heiti SC"  # fallback
    else:
        return "Microsoft YaHei"  # Windows default


CJK_FONT = _get_cjk_font()

# =========================
# 任务常量
# =========================
TASK_TYPE = "A1"
N = 6

WIN_SIZE_FALLBACK = (1024, 768)
BG_COLOR = (1, 1, 1)
TEXT_COLOR = (-1, -1, -1)

# 硬上限（秒）
HARD_LIMIT_S_DEFAULT = 40.0

# 卡住提示
STALL_HINT_S = 10.0
HINT_FLASH_S = 0.85

# 节点渲染大小（A1/B3/B4 统一建议你后续也在 B3/B4 里用同一个 AUTO）
NODE_DIAMETER_PX_AUTO = 170

# 轨迹在节点附近会被"底盘遮挡"掉：底盘越大，线越早消失。
# 适配要求：让线能更贴近节点再隐藏 —— 把底盘半径倍率调小即可。
BACK_DISC_MULT = 1.008

# 命中与容忍（适老：容错稍大，但错触发需"核心圈+停留"）
HIT_RADIUS_MULT = 0.88
START_TOL_MULT = 1.15

# 正确触发：进入核心圈即可，或稍停留
CORE_HIT_MULT = 0.45
RIGHT_DWELL_S = 0.11

# 错误触发：更敏感（更短 dwell），但必须进"错误核心圈"
WRONG_DWELL_S = 0.22
WRONG_CORE_MULT = 0.58

# 轨迹
LINE_W = 8
LINE_COLOR = (-0.15, -0.15, -0.15)
DRAW_MIN_MOVE_PX = 1.5

# 环形提示
HINT_RING_W = 10
HINT_RING_COLOR = (-0.2, 0.6, -0.2)

ERROR_FLASH_S = 0.32
ERROR_RING_W = 10
ERROR_RING_COLOR = (1, -0.3, -0.3)

START_RING_W = 12
START_RING_COLOR = (0.1, 0.55, 0.95)

RETURN_RING_W = 12
RETURN_RING_COLOR = (0.95, 0.65, 0.05)

# raw 输出采样（60Hz）
RAW_SAMPLE_DT = 1.0 / 60.0


# =========================
# 数据结构
# =========================
@dataclass
class Node:
    k: int
    pos: Tuple[float, float]  # pix
    category: str             # apple/lemon


@dataclass
class SegmentRow:
    segment_index: int
    stage_key: str
    task_type: str
    style: str
    layout_id: int
    kind: str              # SEGMENT / ERROR / MARKER
    from_k: int
    to_k: int
    start_ts_ms: int
    end_ts_ms: int
    duration_ms: int
    path_length_px: float
    is_error: int
    error_type: str        # none / order / invalid_start / timeout_hint
    hint_level: int
    note: str


# =========================
# 基础工具
# =========================
def resolve_root() -> Path:
    here = Path(__file__).resolve().parent
    for p in [here] + list(here.parents):
        if (p / "layouts").exists():
            return p
    return here


def now_ms(clock: core.Clock) -> int:
    return int(round(clock.getTime() * 1000))


def dist(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def pick_layout_id(subject_id: str) -> int:
    # subject -> 1..3 稳定映射
    h = 0
    for ch in subject_id:
        h = (h * 131 + ord(ch)) % 1000003
    return (h % 3) + 1


def write_csv(path: Path, fieldnames: List[str], rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def sha1_of_file(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _try_parse_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return int(x)
    if isinstance(x, str):
        s = x.strip()
        digits = "".join(ch for ch in s if ch.isdigit())
        if digits:
            try:
                return int(digits)
            except Exception:
                return None
        try:
            return int(s)
        except Exception:
            return None
    return None


def parse_node_k(nd: Dict[str, Any], fallback_k: Optional[int]) -> Optional[int]:
    for key in ("node_id", "k", "id", "index", "number", "num", "label", "text", "name"):
        if key in nd:
            k = _try_parse_int(nd.get(key))
            if k is not None:
                return k
    return fallback_k


def _norm_to_pix(v: float, span: float, *, axis: str, y_origin_top: bool) -> float:
    if 0.0 <= v <= 1.0:
        if axis == "x":
            return (v - 0.5) * span
        return (0.5 - v) * span if y_origin_top else (v - 0.5) * span
    if -1.0 <= v <= 1.0:
        return v * (span / 2.0)
    return v


def parse_node_pos(nd: Dict[str, Any], canvas_w: float, canvas_h: float, y_origin_top: bool) -> Optional[Tuple[float, float]]:
    for key in ("pos_px", "pos", "position", "xy"):
        if key in nd and isinstance(nd[key], (list, tuple)) and len(nd[key]) >= 2:
            try:
                x, y = float(nd[key][0]), float(nd[key][1])
                if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                    x = _norm_to_pix(x, canvas_w, axis="x", y_origin_top=y_origin_top)
                    y = _norm_to_pix(y, canvas_h, axis="y", y_origin_top=y_origin_top)
                return (x, y)
            except Exception:
                pass

    if "x" in nd and "y" in nd:
        try:
            x, y = float(nd["x"]), float(nd["y"])
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                x = _norm_to_pix(x, canvas_w, axis="x", y_origin_top=y_origin_top)
                y = _norm_to_pix(y, canvas_h, axis="y", y_origin_top=y_origin_top)
            return (x, y)
        except Exception:
            pass

    if "x_norm" in nd and "y_norm" in nd:
        try:
            xn = float(nd["x_norm"])
            yn = float(nd["y_norm"])
            x = _norm_to_pix(xn, canvas_w, axis="x", y_origin_top=y_origin_top)
            y = _norm_to_pix(yn, canvas_h, axis="y", y_origin_top=y_origin_top)
            return (x, y)
        except Exception:
            pass

    return None


def normalize_category(cat: str) -> str:
    c = (cat or "").strip().lower()
    if c in ("苹果", "apple"):
        return "apple"
    if c in ("柠檬", "lemon"):
        return "lemon"
    return c if c else "apple"


def find_layout_file(root: Path, style: str, layout_id: int) -> Path:
    cands = [
        root / "layouts" / "A1" / style / f"N{N}_v1_layout{layout_id}.json",
        root / "layouts" / "A1" / f"N{N}_v1_layout{layout_id}.json",
    ]
    for p in cands:
        if p.exists():
            return p
    raise FileNotFoundError("找不到 A1 布局 JSON，尝试过：\n" + "\n".join(str(p) for p in cands))


def load_a1_layout(root: Path, style: str, layout_id: int, canvas_w: float, canvas_h: float, y_origin_top: bool) -> Tuple[List[Node], int, Path]:
    p = find_layout_file(root, style, layout_id)
    obj = json.loads(p.read_text(encoding="utf-8"))

    node_size_px = int(obj.get("node_size_px", 170))
    nodes_obj = obj.get("nodes", None)
    if nodes_obj is None or not isinstance(nodes_obj, list):
        raise ValueError(f"布局 JSON nodes 字段无效：{p}")

    nodes: List[Node] = []
    auto_k = 1
    for nd in nodes_obj:
        if not isinstance(nd, dict):
            raise ValueError(f"nodes 元素不是 dict：{nd}")

        pos = parse_node_pos(nd, canvas_w, canvas_h, y_origin_top)
        if pos is None:
            raise ValueError(f"节点无法解析坐标字段：keys={list(nd.keys())}")

        k = parse_node_k(nd, fallback_k=auto_k)
        if k is None:
            raise ValueError(f"节点无法解析编号：keys={list(nd.keys())}")

        cat = normalize_category(str(nd.get("category", nd.get("fruit", nd.get("type", "apple")))))
        nodes.append(Node(k=int(k), pos=pos, category=cat))
        auto_k += 1

    if len(nodes) != N:
        raise ValueError(f"A1 节点数不等于 N={N}：实际 {len(nodes)}（文件：{p}）")

    ks = sorted(n.k for n in nodes)
    if ks != list(range(1, N + 1)):
        raise ValueError(f"节点编号必须覆盖 1..{N} 且不重复，但现在是：{ks}（文件：{p}）")

    nodes = sorted(nodes, key=lambda n: n.k)
    return nodes, node_size_px, p


def _collect_pngs(base: Path) -> List[Path]:
    if not base.exists():
        return []
    return [p for p in base.rglob("*.png") if p.is_file()]


def find_numbered_fruit_png(root: Path, style: str, category: str, k: int) -> Path:
    """确定性查找，保证与 layouts 预览使用同一套素材路径与命名规则。"""
    style = (style or "").strip().lower()
    fruit = normalize_category(category)

    # 1) 标准路径优先（与生成脚本一致）
    base = root / "stimuli" / "fruits" / "numbered" / style
    c1 = base / f"{fruit}_{style}_{k}.png"
    c2 = base / f"{fruit}_{style}_{k:02d}.png"
    if c1.exists():
        return c1
    if c2.exists():
        return c2

    # 2) 兼容兜底：全局扫描
    search_roots = [
        root / "stimuli" / "fruits" / "numbered",
        root / "stimuli" / "fruits",
        root / "stimuli",
    ]

    all_pngs: List[Path] = []
    for sr in search_roots:
        all_pngs.extend(_collect_pngs(sr))
    if not all_pngs:
        raise FileNotFoundError("找不到任何水果 PNG，请确认放在 DTMT/stimuli/ 下。")

    def token_set(p: Path) -> set:
        stem = p.stem.lower()
        toks = re.split(r"[^a-z0-9]+", stem)
        return set(t for t in toks if t)

    wanted = {fruit, style, str(k)}
    candidates = []
    for p in all_pngs:
        ts = token_set(p)
        if wanted.issubset(ts):
            candidates.append(p)

    if not candidates:
        for p in all_pngs:
            stem = p.stem.lower()
            if fruit in stem and str(k) in stem and style in stem:
                candidates.append(p)

    if not candidates:
        raise FileNotFoundError(
            f"找不到 numbered 图片：fruit={fruit}, style={style}, k={k}.\n"
            f"建议命名：{fruit}_{style}_{k}.png 或 {fruit}_{style}_{k:02d}.png，并放在 stimuli/fruits/numbered/{style}/ 下。"
        )

    candidates.sort(key=lambda x: (len(str(x)), str(x)))
    return candidates[0]


def create_window(fullscr: bool, screen_index: int) -> visual.Window:
    try:
        win = visual.Window(
            size=WIN_SIZE_FALLBACK,
            fullscr=fullscr,
            screen=screen_index,
            units="pix",
            color=BG_COLOR,
            allowGUI=(not fullscr),
        )
        return win
    except Exception:
        win = visual.Window(
            size=WIN_SIZE_FALLBACK,
            fullscr=False,
            screen=screen_index,
            units="pix",
            color=BG_COLOR,
            allowGUI=True,
        )
        return win


# =========================
# UI：按钮 (Helper)
# =========================
def point_in_rect(pt: Tuple[float, float], rect_center: Tuple[float, float], w: float, h: float) -> bool:
    x, y = pt
    cx, cy = rect_center
    return (cx - w / 2 <= x <= cx + w / 2) and (cy - h / 2 <= y <= cy + h / 2)


# =========================
# 命中计算
# =========================
def nearest_node_within(nodes: List[Node], pos_xy: Tuple[float, float], r: float) -> Tuple[Optional[Node], float]:
    best = None
    best_d = 1e18
    for n in nodes:
        d = dist(pos_xy, n.pos)
        if d <= r and d < best_d:
            best = n
            best_d = d
    return best, best_d


# =========================
# 主任务
# =========================
def run_a1(
    win: Optional[visual.Window] = None,
    subject_id: str = "S001",
    session_id: str = "SES1",
    age: str = "",
    style: str = "bw",
    layout_id: int = 0,
    hard_limit_s: float = HARD_LIMIT_S_DEFAULT,
    windowed: bool = False,
    screen_index: int = 0,
    y_origin_top: bool = True,
    node_diam_override: int = 0,
    show_start_wait: bool = True,
    b_order: str = "",
    **kwargs: Any,
) -> None:
    root = resolve_root()
    style = style.lower().strip()
    if style not in ("bw", "color", "auto"):
        raise ValueError("A1 style 必须为 bw / color / auto")


    if layout_id not in (1, 2, 3):
        layout_id = pick_layout_id(subject_id)

    # style=auto：根据 run_all 决定的 B3/B4 顺序来平衡 A1 的颜色版本
    if style != "color":
        print(f"[A1] NOTE: style argument '{style}' ignored; A1 baseline locks to color.")
    style = "color"

    win_provided = (win is not None)
    if win is None:
        win = create_window(fullscr=(not windowed), screen_index=screen_index)
    
    canvas_w, canvas_h = float(win.size[0]), float(win.size[1])

    nodes, layout_node_diam, layout_path = load_a1_layout(root, style, layout_id, canvas_w, canvas_h, y_origin_top)
    print(f"[A1] resolved style={style} layout_id={layout_id} layout_file={layout_path}")

    # 渲染直径：默认适中（只需与 B3/B4 统一）
    if node_diam_override > 0:
        render_diam = int(node_diam_override)
    else:
        render_diam = min(int(layout_node_diam), int(NODE_DIAMETER_PX_AUTO))

    node_radius = render_diam / 2.0
    hit_radius = node_radius * HIT_RADIUS_MULT
    core_radius = node_radius * CORE_HIT_MULT
    start_tol = node_radius * START_TOL_MULT
    wrong_core_radius = node_radius * WRONG_CORE_MULT

    # 输出路径
    out_dir = root / "results" / "A1"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = f"{subject_id}_{session_id}_{TASK_TYPE}_{style}_layout{layout_id}_{stamp}"
    summary_path = out_dir / f"{base}_summary.csv"
    segments_path = out_dir / f"{base}_segments.csv"
    raw_path = out_dir / f"{base}_raw_path.csv"
    layout_nodes_path = out_dir / f"{base}_layout_nodes.csv"
    event_marker_path = out_dir / f"{base}_event_marker.csv"

    # 事件标记
    event_marker_rows: List[dict] = []

    def add_marker(event_name: str, note: str = "", k_from: int = -1, k_to: int = -1) -> None:
        try:
            ts = now_ms(global_clock)
        except Exception:
            ts = int(round(time.time() * 1000))
        event_marker_rows.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "style": style,
            "stage_key": stage_key if "stage_key" in locals() else "",
            "layout_id": layout_id,
            "ts_ms": ts,
            "event": event_name,
            "from_k": k_from,
            "to_k": k_to,
            "note": note,
        })

    mouse = event.Mouse(win=win)
    mouse.setVisible(True)

    # 节点图片 + 底盘
    back_discs: Dict[int, visual.Circle] = {}
    fruit_imgs: Dict[int, visual.ImageStim] = {}
    for n in nodes:
        back_discs[n.k] = visual.Circle(
            win=win,
            radius=node_radius * BACK_DISC_MULT,
            pos=n.pos,
            fillColor=BG_COLOR,
            lineColor=None,
        )
        img_path = find_numbered_fruit_png(root, style, n.category, n.k)
        fruit_imgs[n.k] = visual.ImageStim(
            win=win,
            image=str(img_path),
            pos=n.pos,
            size=(render_diam, render_diam),
            units="pix",
            interpolate=True,
        )

    # 轨迹
    committed_path_stims: List[visual.ShapeStim] = []
    live_path = visual.ShapeStim(
        win=win,
        vertices=[(0, 0), (1, 1)],
        closeShape=False,
        lineColor=LINE_COLOR,
        lineWidth=LINE_W,
        fillColor=None,
    )

    hint_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.10,
        pos=(0, 0),
        lineColor=HINT_RING_COLOR,
        lineWidth=HINT_RING_W,
        fillColor=None,
    )
    error_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.12,
        pos=(0, 0),
        lineColor=ERROR_RING_COLOR,
        lineWidth=ERROR_RING_W,
        fillColor=None,
    )
    start_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.14,
        pos=(0, 0),
        lineColor=START_RING_COLOR,
        lineWidth=START_RING_W,
        fillColor=None,
    )
    return_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.14,
        pos=(0, 0),
        lineColor=RETURN_RING_COLOR,
        lineWidth=RETURN_RING_W,
        fillColor=None,
    )

    # =========================
    # 指导语（全屏图片）
    # - 独立运行 A1 时：展示通用"操作方法/正式任务提示"(若存在) + A1 专属指导页。
    # - run_all 调用 A1 时：默认只展示 A1 专属指导页，避免与前置练习/总说明重复。
    # =========================
    def _close_win() -> None:
        if (not win_provided) and (win is not None):
            win.close()

    def show_image_wait(
        img_path: Path,
        key_list: Tuple[str, ...] = ("space", "return", "num_enter"),
        allow_escape: bool = True,
        min_wait: float = 0.25,
    ) -> str:
        """展示全屏图片 + 底部蓝色按钮，等待按钮点击或按键。
        按钮有 hover/press 视觉反馈。
        """
        stim: Optional[visual.BaseVisualStim] = None
        if img_path.exists():
            try:
                stim = visual.ImageStim(
                    win=win,
                    image=str(img_path),
                    units="pix",
                    size=(canvas_w, canvas_h),
                )
            except Exception:
                stim = None

        if stim is None:
            stim = visual.TextStim(
                win=win,
                text=f"[提示页缺失]\n{img_path.name}\n\n按 空格/回车 继续",
                font=CJK_FONT,
                color=TEXT_COLOR,
                height=FONT_SIZE * 0.55,
                wrapWidth=canvas_w * 0.9,
            )

        # 创建底部按钮
        btn_w, btn_h = int(canvas_w * 0.28), int(canvas_h * 0.10)
        btn_y = -canvas_h // 2 + int(canvas_h * 0.12)
        _btn_normal = (0.1, 0.55, 0.82)
        _btn_hover = (0.25, 0.68, 0.95)
        _btn_press = (-0.1, 0.35, 0.62)

        btn_rect = visual.Rect(win, width=btn_w, height=btn_h, pos=(0, btn_y),
                               fillColor=_btn_normal, lineWidth=0, units="pix")
        btn_shadow = visual.Rect(win, width=btn_w, height=btn_h,
                                 pos=(2, btn_y - 4), fillColor=(0.6, 0.6, 0.6),
                                 lineWidth=0, units="pix", opacity=0.3)
        btn_label = visual.TextStim(win, text="继续", font=CJK_FONT, height=btn_h * 0.5,
                                    color=(1, 1, 1), pos=(0, btn_y), units="pix", bold=True)

        mouse = event.Mouse(win=win)
        mouse.setVisible(True)

        # 防止上一屏按键"连按"带入
        event.clearEvents()
        t0 = core.Clock()
        prev_pressed = True
        while t0.getTime() < float(min_wait):
            stim.draw()
            btn_shadow.draw(); btn_rect.draw(); btn_label.draw()
            win.flip()
        event.clearEvents()
        prev_pressed = mouse.getPressed()[0]

        while True:
            # hover 检测
            mpos = mouse.getPos()
            hovering = btn_rect.contains(mpos)
            cur_pressed = mouse.getPressed()[0]

            # 按钮状态
            if cur_pressed and hovering:
                btn_rect.fillColor = _btn_press
                btn_shadow.opacity = 0
            elif hovering:
                btn_rect.fillColor = _btn_hover
                btn_shadow.opacity = 0.3
            else:
                btn_rect.fillColor = _btn_normal
                btn_shadow.opacity = 0.3

            # 绘制
            stim.draw()
            btn_shadow.draw(); btn_rect.draw(); btn_label.draw()
            win.flip()

            # 点击检测（释放时在按钮上 = 确认）
            if cur_pressed and not prev_pressed and hovering:
                btn_rect.fillColor = _btn_press
                stim.draw(); btn_rect.draw(); btn_label.draw()
                win.flip()
                core.wait(0.15)
                return "space"
            prev_pressed = cur_pressed

            # 键盘检测
            keys = event.getKeys()
            if allow_escape and ("escape" in keys):
                return "escape"
            for k in key_list:
                if k in keys:
                    return k

            core.wait(0.008)

    # 指导语页路径（允许缺失时回退）
    p_common_1 = root / "stimuli" / "zdy" / "1.png"       # 通用操作方法
    p_common_2 = root / "stimuli" / "zdy" / "2.png"       # "接下来是正式任务"
    if not p_common_2.exists():
        p_common_2 = root / "stimuli" / "zdy" / "all_3.png"  # 兼容旧命名
    p_task = root / "stimuli" / "zdy" / "A1_1.png"        # A1 专属指导语

    # 默认：run_all 调用时不重复展示通用页；独立运行时展示通用页
    show_common = bool(kwargs.get("show_common_instructions", (not win_provided)))
    if show_common:
        for p_img in (p_common_1, p_common_2):
            if p_img.exists():
                if show_image_wait(p_img) == "escape":
                    _close_win()
                    return

    if show_image_wait(p_task) == "escape":
        _close_win()
        return

# =========================
    # 正式阶段：先进入"起始点高亮等待"状态
    # =========================
    global_clock = core.Clock()
    stage_key = "A1_formal"

    started = False
    task_start_ms = 0

    current_k = 1
    next_k = 2
    finished = 0
    await_finish_enter = False
    start_to_first_correct_s: Optional[float] = None
    completion_time_s: Optional[float] = None

    total_errors = 0
    order_errors = 0
    timeout_errors = 0
    invalid_start_count = 0

    raw_rows: List[dict] = []
    seg_rows: List[SegmentRow] = []
    seg_index = 0

    pen_down = False
    segment_start_ms: Optional[int] = None

    current_path_draw: List[Tuple[float, float]] = []
    current_path_len = 0.0

    last_sample_ms = 0
    last_progress_ms = 0

    hint_active_until_ms = 0
    error_flash_until_ms = 0
    error_flash_k = -1

    need_return = False  # 错误后必须回到 current_k

    cand_node: Optional[Node] = None
    cand_since: Optional[float] = None

    hud = visual.TextStim(
        win=win,
        text="",
        font=CJK_FONT,
        color=(-0.25, -0.25, -0.25),
        height=20,
        pos=(0, canvas_h / 2 - 26),
        wrapWidth=canvas_w * 0.90,
    )
    msg = visual.TextStim(
        win=win,
        text="",
        font=CJK_FONT,
        color=(-0.2, -0.2, -0.2),
        height=22,
        pos=(0, canvas_h / 2 - 52),
        wrapWidth=canvas_w * 0.90,
    )

    def reset_candidate():
        nonlocal cand_node, cand_since
        cand_node = None
        cand_since = None

    def add_draw_point(pt: Tuple[float, float]):
        nonlocal current_path_draw
        if not current_path_draw:
            current_path_draw = [pt]
            return
        if dist(pt, current_path_draw[-1]) >= DRAW_MIN_MOVE_PX:
            current_path_draw.append(pt)

    def commit_polyline(poly: List[Tuple[float, float]]):
        if len(poly) < 2:
            return
        st = visual.ShapeStim(
            win=win,
            vertices=poly,
            closeShape=False,
            lineColor=LINE_COLOR,
            lineWidth=LINE_W,
            fillColor=None,
        )
        committed_path_stims.append(st)

    def record_error(kind: str, to_k: int, err_type: str, note: str, start_ms: int, end_ms: int, plen: float):
        nonlocal seg_index
        seg_index += 1
        seg_rows.append(SegmentRow(
            segment_index=seg_index,
            stage_key=stage_key,
            task_type=TASK_TYPE,
            style=style,
            layout_id=layout_id,
            kind=kind,
            from_k=current_k,
            to_k=to_k,
            start_ts_ms=start_ms,
            end_ts_ms=end_ms,
            duration_ms=end_ms - start_ms,
            path_length_px=float(plen),
            is_error=1 if kind == "ERROR" else 0,
            error_type=err_type,
            hint_level=0,
            note=note,
        ))

    # 进入正式画面但尚未开始计时：持续高亮 1，直到点中
    event.clearEvents()
    while True:
        keys = event.getKeys()
        if "escape" in keys:
            if not win_provided:
                win.close()
            return

        pressed = mouse.getPressed()[0]
        pos = mouse.getPos()

        win.clearBuffer()
        for k in range(1, N + 1):
            back_discs[k].draw()
            fruit_imgs[k].draw()

        start_ring.pos = nodes[0].pos
        start_ring.draw()

        hud.text = "请先点到 1 开始"
        hud.draw()
        win.flip()

        if pressed and dist(pos, nodes[0].pos) <= start_tol:
            started = True
            task_start_ms = now_ms(global_clock)
            add_marker("BLOCK_START", "start timing", k_from=1, k_to=2)
            last_sample_ms = task_start_ms
            last_progress_ms = task_start_ms
            pen_down = True
            segment_start_ms = task_start_ms
            current_path_draw = []
            current_path_len = 0.0
            add_draw_point(pos)
            break

    # =========================
    # 正式循环
    # =========================
    while True:
        now = now_ms(global_clock)
        elapsed_s = (now - task_start_ms) / 1000.0

        if elapsed_s >= hard_limit_s and finished == 0:
            finished = 0
            completion_time_s = hard_limit_s
            add_marker("HARD_LIMIT", "elapsed>=hard_limit", k_from=current_k, k_to=next_k)
            break

        keys = event.getKeys()
        if "escape" in keys:
            finished = 0
            completion_time_s = min(elapsed_s, hard_limit_s)
            add_marker("EXIT_EARLY", "escape during task", k_from=current_k, k_to=next_k)
            break

        pressed = mouse.getPressed()[0]
        pos = mouse.getPos()

        # raw_path 采样
        if (now - last_sample_ms) >= int(RAW_SAMPLE_DT * 1000):
            raw_rows.append({
                "subject_id": subject_id,
                "session_id": session_id,
                "age": age,
                "task_type": TASK_TYPE,
                "style": style,
                "stage_key": stage_key,
                "layout_id": layout_id,
                "ts_ms": now,
                "x_px": pos[0],
                "y_px": pos[1],
                "is_pen_down": 1 if pressed else 0,
                "started": 1,
            })
            last_sample_ms = now

        # 卡住提示：只在非回退状态触发
        if (not need_return) and (next_k <= N) and (now - last_progress_ms >= int(STALL_HINT_S * 1000)):
            timeout_errors += 1
            hint_active_until_ms = now + int(HINT_FLASH_S * 1000)
            add_marker("TIMEOUT_PROMPT", "stall>=10s -> highlight next", k_from=current_k, k_to=next_k)
            last_progress_ms = now

            seg_index += 1
            seg_rows.append(SegmentRow(
                segment_index=seg_index,
                stage_key=stage_key,
                task_type=TASK_TYPE,
                style=style,
                layout_id=layout_id,
                kind="MARKER",
                from_k=current_k,
                to_k=next_k,
                start_ts_ms=now,
                end_ts_ms=now,
                duration_ms=0,
                path_length_px=0.0,
                is_error=0,
                error_type="timeout_hint",
                hint_level=1,
                note="stall>=10s -> highlight next",
            ))

        # 按下开始一段
        if pressed and not pen_down:
            pen_down = True
            reset_candidate()

            if need_return:
                # 回退状态：必须从 current_k 附近起笔
                if dist(pos, nodes[current_k - 1].pos) > start_tol:
                    pen_down = False
                    segment_start_ms = None
                    current_path_draw = []
                    current_path_len = 0.0
                else:
                    need_return = False
                    segment_start_ms = now
                    current_path_draw = []
                    current_path_len = 0.0
                    add_draw_point(pos)
            else:
                # 正常状态：必须从 current_k 起笔，否则算 invalid_start
                if dist(pos, nodes[current_k - 1].pos) > start_tol:
                    invalid_start_count += 1
                    record_error(
                        kind="ERROR",
                        to_k=current_k,
                        err_type="invalid_start",
                        note="pen down not near current node",
                        start_ms=now,
                        end_ms=now,
                        plen=0.0,
                    )
                    pen_down = False
                    segment_start_ms = None
                    current_path_draw = []
                    current_path_len = 0.0
                else:
                    segment_start_ms = now
                    current_path_draw = []
                    current_path_len = 0.0
                    add_draw_point(pos)

        # 松开结束一段
        elif (not pressed) and pen_down:
            pen_down = False
            reset_candidate()

            if segment_start_ms is not None and (not need_return) and (next_k <= N):
                picked, _ = nearest_node_within(nodes, pos, hit_radius)

                # 松手落在正确点
                if picked is not None and picked.k == next_k:
                    seg_end_ms = now

                    if start_to_first_correct_s is None and current_k == 1 and next_k == 2:
                        start_to_first_correct_s = (seg_end_ms - task_start_ms) / 1000.0

                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        style=style,
                        layout_id=layout_id,
                        kind="SEGMENT",
                        from_k=current_k,
                        to_k=next_k,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end_ms,
                        duration_ms=seg_end_ms - segment_start_ms,
                        path_length_px=float(current_path_len),
                        is_error=0,
                        error_type="none",
                        hint_level=0,
                        note="release inside correct next",
                    ))
                    commit_polyline(list(current_path_draw))

                    current_k = next_k
                    next_k = current_k + 1
                    last_progress_ms = now

                    if current_k == N:
                        finished = 1
                        completion_time_s = (now - task_start_ms) / 1000.0
                        await_finish_enter = True

                # 松手落在错误点：判错 + 回退
                elif picked is not None and picked.k != current_k:
                    total_errors += 1
                    order_errors += 1

                    seg_end_ms = now
                    record_error(
                        kind="ERROR",
                        to_k=picked.k,
                        err_type="order",
                        note="release inside wrong node -> require return",
                        start_ms=segment_start_ms,
                        end_ms=seg_end_ms,
                        plen=current_path_len,
                    )
                    commit_polyline(list(current_path_draw))

                    error_flash_k = picked.k
                    error_flash_until_ms = now + int(ERROR_FLASH_S * 1000)
                    need_return = True

            segment_start_ms = None
            current_path_draw = []
            current_path_len = 0.0

        # 不断笔：更新轨迹 + dwell 判定
        if pen_down and segment_start_ms is not None:
            if current_path_draw:
                last_pt = current_path_draw[-1]
                if dist(pos, last_pt) >= 0.1:
                    current_path_len += dist(pos, last_pt)
                    add_draw_point(pos)

            if (not need_return) and (next_k <= N):
                picked, picked_d = nearest_node_within(nodes, pos, hit_radius)

                if picked is None or picked.k == current_k:
                    reset_candidate()
                else:
                    if cand_node is None or picked.k != cand_node.k:
                        cand_node = picked
                        cand_since = time.perf_counter()

                    dwell = (time.perf_counter() - cand_since) if cand_since is not None else 0.0

                    # 正确点：核心圈或短停留确认
                    if picked.k == next_k:
                        if (picked_d <= core_radius) or (dwell >= RIGHT_DWELL_S):
                            seg_end_ms = now

                            if start_to_first_correct_s is None and current_k == 1 and next_k == 2:
                                start_to_first_correct_s = (seg_end_ms - task_start_ms) / 1000.0

                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index,
                                stage_key=stage_key,
                                task_type=TASK_TYPE,
                                style=style,
                                layout_id=layout_id,
                                kind="SEGMENT",
                                from_k=current_k,
                                to_k=next_k,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end_ms,
                                duration_ms=seg_end_ms - segment_start_ms,
                                path_length_px=float(current_path_len),
                                is_error=0,
                                error_type="none",
                                hint_level=0,
                                note="continuous confirm correct next",
                            ))

                            commit_polyline(list(current_path_draw))

                            current_k = next_k
                            next_k = current_k + 1
                            last_progress_ms = now
                            reset_candidate()

                            if current_k == N:
                                finished = 1
                                completion_time_s = (now - task_start_ms) / 1000.0
                                await_finish_enter = True

                            # 不断笔续连：切新段
                            segment_start_ms = now
                            current_path_draw = []
                            current_path_len = 0.0
                            add_draw_point(pos)

                    # 错误点：更敏感（dwell更短）但必须进"错误核心圈"
                    else:
                        if (picked_d <= wrong_core_radius) and (dwell >= WRONG_DWELL_S):
                            total_errors += 1
                            order_errors += 1

                            seg_end_ms = now
                            record_error(
                                kind="ERROR",
                                to_k=picked.k,
                                err_type="order",
                                note="dwell on wrong node core -> require return",
                                start_ms=segment_start_ms,
                                end_ms=seg_end_ms,
                                plen=current_path_len,
                            )
                            commit_polyline(list(current_path_draw))

                            error_flash_k = picked.k
                            error_flash_until_ms = now + int(ERROR_FLASH_S * 1000)
                            need_return = True

                            # 错误后要求松手再继续（防止连串误触）
                            pen_down = False
                            segment_start_ms = None
                            current_path_draw = []
                            current_path_len = 0.0
                            reset_candidate()

        # ===== 绘制 =====
        win.clearBuffer()

        # 固化轨迹
        for st in committed_path_stims:
            st.draw()

        # 当前段轨迹
        if pen_down and len(current_path_draw) >= 2:
            live_path.setVertices(current_path_draw)
            live_path.draw()

        # 节点
        for k in range(1, N + 1):
            back_discs[k].draw()
            fruit_imgs[k].draw()

        # 高亮提示
        if now <= hint_active_until_ms and next_k <= N:
            hint_ring.pos = nodes[next_k - 1].pos
            hint_ring.draw()

        if now <= error_flash_until_ms and (1 <= error_flash_k <= N):
            error_ring.pos = nodes[error_flash_k - 1].pos
            error_ring.draw()

        # 回退提示
        if need_return:
            return_ring.pos = nodes[current_k - 1].pos
            return_ring.draw()
            msg.text = f"请回到 {current_k} 后继续"
        else:
            msg.text = ""

        hud.text = f"进度：{current_k}/{N}"
        hud.draw()
        msg.draw()
        win.flip()
        if await_finish_enter:
            # Show completion message and redraw
            msg.text = "完成！请点击屏幕继续"
            msg.draw()
            hud.draw()
            win.flip()
            core.wait(0.05)
            event.clearEvents()
            # Accept keyboard OR touch/mouse click
            waiting = True
            while waiting:
                keys = event.getKeys(keyList=["space", "return", "num_enter", "escape"])
                if keys:
                    k = keys[0]
                    waiting = False
                elif mouse.getPressed()[0]:
                    k = "return"
                    core.wait(0.2)  # debounce
                    waiting = False
                core.wait(0.01)
            if k == "escape":
                core.quit()
            break
    
    add_marker("BLOCK_END", f"finished={finished}", k_from=current_k, k_to=next_k)

    # =========================
    # 保存
    # =========================
    if started and completion_time_s is None:
        completion_time_s = min((now_ms(global_clock) - task_start_ms) / 1000.0, hard_limit_s)
    if not started:
        completion_time_s = 0.0
    if start_to_first_correct_s is None:
        start_to_first_correct_s = float(completion_time_s)

    try:
        layout_hash = sha1_of_file(layout_path)
    except Exception:
        layout_hash = ""

    summary_fields = [
        "subject_id", "session_id", "age", "task_type", "style", "layout_id",
        "layout_file", "layout_sha1",
        "layout_node_diam_px", "render_node_diam_px",
        "canvas_w", "canvas_h", "y_origin_top",
        "started", "finished",
        "completion_time_s", "start_to_first_correct_s",
        "total_errors", "order_errors", "timeout_errors",
        "invalid_start_count",
        "hard_limit_s",
        "timestamp",
    ]

    summary_row = {
        "subject_id": subject_id,
        "session_id": session_id,
        "task_type": TASK_TYPE,
        "style": style,
        "layout_id": int(layout_id),
        "layout_file": str(layout_path),
        "layout_sha1": layout_hash,
        "layout_node_diam_px": int(layout_node_diam),
        "render_node_diam_px": int(render_diam),
        "canvas_w": int(canvas_w),
        "canvas_h": int(canvas_h),
        "y_origin_top": int(1 if y_origin_top else 0),
        "started": int(1 if started else 0),
        "finished": int(finished),
        "completion_time_s": round(float(completion_time_s), 4),
        "start_to_first_correct_s": round(float(start_to_first_correct_s), 4),
        "total_errors": int(total_errors),
        "order_errors": int(order_errors),
        "timeout_errors": int(timeout_errors),
        "invalid_start_count": int(invalid_start_count),
        "hard_limit_s": float(hard_limit_s),
        "timestamp": time.strftime("%Y%m%d_%H%M%S"),
    }

    write_csv(summary_path, summary_fields, [summary_row])

    seg_fields = [
        "subject_id", "session_id", "age",
        "segment_index", "stage_key", "task_type", "style", "layout_id",
        "kind", "from_k", "to_k",
        "start_ts_ms", "end_ts_ms", "duration_ms",
        "path_length_px",
        "is_error", "error_type",
        "hint_level", "note",
    ]

    seg_out: List[dict] = []
    for r in seg_rows:
        seg_out.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "segment_index": r.segment_index,
            "stage_key": r.stage_key,
            "task_type": r.task_type,
            "style": r.style,
            "layout_id": r.layout_id,
            "kind": r.kind,
            "from_k": r.from_k,
            "to_k": r.to_k,
            "start_ts_ms": r.start_ts_ms,
            "end_ts_ms": r.end_ts_ms,
            "duration_ms": r.duration_ms,
            "path_length_px": round(float(r.path_length_px), 3),
            "is_error": r.is_error,
            "error_type": r.error_type,
            "hint_level": r.hint_level,
            "note": r.note,
        })
    write_csv(segments_path, seg_fields, seg_out)

    raw_fields = [
        "subject_id", "session_id", "age", "task_type", "style", "stage_key",
        "layout_id", "ts_ms", "x_px", "y_px", "is_pen_down", "started",
    ]
    write_csv(raw_path, raw_fields, raw_rows)

    # layout_nodes.csv（布局复现/质控）
    layout_rows: List[dict] = []
    for n in nodes:
        layout_rows.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "style": style,
            "layout_id": int(layout_id),
            "layout_file": str(layout_path),
            "layout_sha1": layout_hash,
            "render_node_diam_px": int(render_diam),
            "node_k": int(n.k),
            "x_px": float(n.pos[0]),
            "y_px": float(n.pos[1]),
            "category": str(getattr(n, "category", "")),
        })
    write_csv(
        layout_nodes_path,
        ["subject_id","session_id","age","task_type","style","layout_id","layout_file","layout_sha1","render_node_diam_px",
         "node_k","x_px","y_px","category"],
        layout_rows,
    )

    # event_marker.csv（关键事件）
    write_csv(
        event_marker_path,
        ["subject_id","session_id","age","task_type","style","stage_key","layout_id","ts_ms","event","from_k","to_k","note"],
        event_marker_rows,
    )

    # =========================
    # 结束休息页（仅独立运行时显示，run_all 有自己的休息页）
    # =========================
    if not win_provided:
        end_image_path = root / "stimuli" / "zdy" / "3.png"
        if not end_image_path.exists():
            end_image_path = root / "stimuli" / "zdy" / "A0_2.png"
        show_image_wait(end_image_path, key_list=("space", "return", "num_enter"), allow_escape=True, min_wait=0.25)
        win.close()

    print("\n[SAVED]")
    print("layout_file =", layout_path)
    print(summary_path)
    print(segments_path)
    print(raw_path)


# =========================
# CLI
# =========================
def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", type=str, default="S001", help="被试编号")
    ap.add_argument("--session", type=str, default="SES1", help="会话编号")
    ap.add_argument("--age", type=str, default="", help="年龄（可空）")


    ap.add_argument("--style", type=str, default="bw", choices=["bw", "color", "auto"], help="bw / color / auto")
    ap.add_argument("--b_order", type=str, default="", choices=["", "B3B4", "B4B3"], help="当 style=auto 时，用于决定 A1 用 bw 还是 color")
    ap.add_argument("--layout", type=int, default=0, help="布局编号1-3；0=按subject稳定映射")
    ap.add_argument("--hard_limit", type=float, default=HARD_LIMIT_S_DEFAULT, help="硬上限（秒）")

    ap.add_argument("--windowed", action="store_true", help="窗口模式（电脑调试）")
    ap.add_argument("--screen", type=int, default=0, help="多屏索引")

    ap.add_argument("--y_origin_bottom", action="store_true", help="若 y_norm 是 0=下 1=上，启用此项")
    ap.add_argument("--node_diam", type=int, default=0, help="渲染用节点直径(px)。0=自动")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()

    layout_id = args.layout if args.layout in (1, 2, 3) else pick_layout_id(args.subject)

    # style=auto：根据 run_all 决定的 B3/B4 顺序来平衡 A1 的颜色版本
    if args.style == "auto":
        # 规则（可在 run_all 里固定）：B3B4 -> A1用bw；B4B3 -> A1用color
        if args.b_order == "B3B4":
            args.style = "bw"
        elif args.b_order == "B4B3":
            args.style = "color"
        else:
            # 未提供顺序时，回退到按 subject 的稳定映射（奇偶）
            args.style = "color" if (pick_layout_id(args.subject) % 2 == 0) else "bw"

    run_a1(
        win=None,
        subject_id=args.subject,
        session_id=args.session,
        age=args.age,
        style=args.style,
        b_order=args.b_order,
        layout_id=layout_id,
        hard_limit_s=float(args.hard_limit),
        windowed=bool(args.windowed),
        screen_index=int(args.screen),
        y_origin_top=(not args.y_origin_bottom),
        node_diam_override=int(args.node_diam),
        show_start_wait=True,
    )