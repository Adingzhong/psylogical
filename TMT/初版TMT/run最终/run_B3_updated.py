# -*- coding: utf-8 -*-
"""
run_B3_opt_v1.py — B3 水果 A/B 交替（两套同数字）
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from psychopy import visual, event, core
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
# 0) 任务参数（默认值）
# =========================
TASK_TYPE = "B3"

N_DEFAULT = 6
VERSION_DEFAULT = f"N{N_DEFAULT}_v1"

HARD_LIMIT_S_DEFAULT = 40.0

STALL_HINT_S = 10.0
HINT_FLASH_S = 0.8

WIN_SIZE_DEFAULT = (1024, 768)
BG_COLOR = (1, 1, 1)
TEXT_COLOR = (-1, -1, -1)

# 节点渲染直径
NODE_DIAMETER_PX_AUTO = 170
# 轨迹
LINE_W = 8
LINE_COLOR = (-0.15, -0.15, -0.15)
DRAW_MIN_MOVE_PX = 1.5

# 命中判定
HIT_RADIUS_MULT = 0.85
START_TOL_MULT = 1.10
CORE_HIT_MULT = 0.45
RIGHT_DWELL_S = 0.12

# 错误
WRONG_DWELL_S = 0.40
WRONG_CORE_MULT = 0.55

# 环形提示
HINT_RING_W = 10
HINT_RING_COLOR = (-0.2, 0.6, -0.2)

ERROR_FLASH_S = 0.30
ERROR_RING_W = 10
ERROR_RING_COLOR = (1, -0.3, -0.3)

START_RING_W = 12
START_RING_COLOR = (0.1, 0.55, 0.95)

RETURN_HINT_S = 0.9
RETURN_RING_W = 12
RETURN_RING_COLOR = (0.95, 0.65, 0.05)

HUD_SIZE = 22

RAW_SAMPLE_DT = 1.0 / 60.0


# =========================
# 1) 数据结构
# =========================
@dataclass
class Node:
    step: int
    node_id: str
    fruit: str
    num: int
    stim_path: Optional[Path]
    pos: Tuple[float, float]  # pix


@dataclass
class SegmentRow:
    segment_index: int
    stage_key: str
    task_type: str
    layout_id: int
    kind: str  # SEGMENT / ERROR / MARKER
    from_label: str
    to_label: str
    from_fruit: str
    to_fruit: str
    from_num: int
    to_num: int
    start_ts_ms: int
    end_ts_ms: int
    duration_ms: int
    path_length_px: float
    is_error: int
    error_type: str  # none / order / type / timeout_hint / invalid_start
    note: str


# =========================
# 2) 工具函数
# =========================

def resolve_root() -> Path:
    """自动从当前脚本位置向上找 DTMT 根目录（以 layouts/ 为标志）。"""
    here = Path(__file__).resolve().parent
    for p in [here] + list(here.parents):
        if (p / "layouts").exists():
            return p
    return here


def sha1_of_file(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now_ms(global_clock: core.Clock) -> int:
    return int(round(global_clock.getTime() * 1000))


def dist(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def pick_layout_id(subject_id: str) -> int:
    """稳定映射 subject -> 1..3（不随机器变化）。"""
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


def _safe_int(x: Any) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float):
        if abs(x - round(x)) < 1e-9:
            return int(round(x))
        return None
    if isinstance(x, str):
        s = x.strip()
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            try:
                return int(s)
            except Exception:
                return None
    return None


def _norm_to_pix(v: float, span: float, axis: str, y_origin_top: bool) -> float:
    """支持 0..1 / -1..1 / 直接像素。"""
    if 0.0 <= v <= 1.0:
        if axis == "x":
            return (v - 0.5) * span
        return (0.5 - v) * span if y_origin_top else (v - 0.5) * span
    if -1.0 <= v <= 1.0:
        return v * (span / 2.0)
    return v


def parse_node_pos_as_pix(
    nd: Dict[str, Any],
    win_w: float,
    win_h: float,
    y_origin_top: bool,
    canvas_w_hint: Optional[float],
    canvas_h_hint: Optional[float],
) -> Tuple[float, float]:
    """优先 x_norm/y_norm，其次 x_px/y_px+canvas，最后 pos/pos_px。"""
    if "x_norm" in nd and "y_norm" in nd:
        x = _norm_to_pix(float(nd["x_norm"]), win_w, "x", y_origin_top)
        y = _norm_to_pix(float(nd["y_norm"]), win_h, "y", y_origin_top)
        return x, y

    if "x_px" in nd and "y_px" in nd and canvas_w_hint and canvas_h_hint:
        x0 = float(nd["x_px"]) / float(canvas_w_hint)
        y0 = float(nd["y_px"]) / float(canvas_h_hint)
        x = _norm_to_pix(x0, win_w, "x", y_origin_top)
        y = _norm_to_pix(y0, win_h, "y", y_origin_top)
        return x, y

    for key in ("pos_px", "pos"):
        if key in nd and isinstance(nd[key], (list, tuple)) and len(nd[key]) >= 2:
            x, y = float(nd[key][0]), float(nd[key][1])
            if canvas_w_hint and canvas_h_hint and 0.0 <= x <= canvas_w_hint and 0.0 <= y <= canvas_h_hint:
                x0, y0 = x / float(canvas_w_hint), y / float(canvas_h_hint)
                x = _norm_to_pix(x0, win_w, "x", y_origin_top)
                y = _norm_to_pix(y0, win_h, "y", y_origin_top)
                return x, y
            return x, y

    raise ValueError(f"节点坐标字段无法解析：keys={list(nd.keys())}")


def infer_fruitA_fruitB(nodes: List[Node]) -> Tuple[str, str]:
    counts: Dict[str, int] = {}
    for n in nodes:
        counts[n.fruit] = counts.get(n.fruit, 0) + 1
    if len(counts) < 2:
        only = next(iter(counts.keys())) if counts else "A"
        return only, "B"
    sorted_items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return sorted_items[0][0], sorted_items[1][0]


def load_b3_layout_with_version(
    root: Path,
    layout_id: int,
    win_w: float,
    win_h: float,
    y_origin_top: bool,
) -> Tuple[int, int, int, str, str, str, List[Node], List[int], Path]:
    """返回 N, M, node_diam_px_scaled, style, fruitA, fruitB, nodes, seq_steps, json_path"""
    layout_dir = root / "layouts" / "B3"
    p = layout_dir / f"{VERSION_DEFAULT}_layout{layout_id}.json"
    if not p.exists():
        cand = sorted(layout_dir.glob(f"*_layout{layout_id}.json"))
        if not cand:
            raise FileNotFoundError(f"找不到 B3 layout 文件：{p}，且 layouts/B3 下无 *_layout{layout_id}.json")
        p = cand[0]

    obj = json.loads(p.read_text(encoding="utf-8"))

    N = _safe_int(obj.get("N")) or N_DEFAULT
    M = _safe_int(obj.get("M")) or (2 * N - 1)

    style = str(obj.get("style", "bw")).strip() or "bw"
    fruitA = (obj.get("fruitA") or "").strip()
    fruitB = (obj.get("fruitB") or "").strip()

    canvas_px = obj.get("canvas_px") or obj.get("canvas") or obj.get("preview_canvas_px")
    canvas_w_hint = None
    canvas_h_hint = None
    if isinstance(canvas_px, dict):
        canvas_w_hint = float(canvas_px.get("w") or canvas_px.get("width") or 0) or None
        canvas_h_hint = float(canvas_px.get("h") or canvas_px.get("height") or 0) or None

    node_diam = _safe_int(obj.get("node_diam_px")) or 200
    # 按窗口缩放 node_diam
    if canvas_w_hint and canvas_h_hint:
        scale = min(win_w / canvas_w_hint, win_h / canvas_h_hint)
        node_diam = int(round(node_diam * scale))

    # 适中 cap（不影响布局 json 的原值，只影响渲染）
    node_diam = min(int(node_diam), int(NODE_DIAMETER_PX_AUTO))

    nodes_obj = obj.get("nodes")
    if nodes_obj is None or not isinstance(nodes_obj, list):
        raise ValueError(f"布局 JSON 缺少 nodes 列表：{p}")

    nodes: List[Node] = []
    for i, nd in enumerate(nodes_obj):
        if not isinstance(nd, dict):
            continue

        node_id_raw = nd.get("node_id", nd.get("id", nd.get("k", i + 1)))
        node_id = str(node_id_raw).strip() or f"node_{i+1:02d}"

        step = _safe_int(nd.get("step"))
        if step is None:
            step = _safe_int(nd.get("node_id"))
        if step is None:
            step = _safe_int(nd.get("id"))
        if step is None:
            step = _safe_int(nd.get("k"))
        if step is None:
            step = i + 1

        fruit = str(nd.get("fruit", nd.get("kind", nd.get("group", "unknown")))).strip() or "unknown"

        num = _safe_int(nd.get("num"))
        if num is None:
            num = _safe_int(nd.get("value"))
        if num is None:
            lab = nd.get("label")
            num = _safe_int(lab) or 0

        stim_rel = nd.get("stim_rel") or nd.get("stim") or nd.get("image")
        stim_path = None
        if isinstance(stim_rel, str) and stim_rel.strip():
            sp = (root / stim_rel).resolve()
            if sp.exists():
                stim_path = sp

        x, y = parse_node_pos_as_pix(
            nd,
            win_w=win_w,
            win_h=win_h,
            y_origin_top=y_origin_top,
            canvas_w_hint=canvas_w_hint,
            canvas_h_hint=canvas_h_hint,
        )

        nodes.append(Node(
            step=int(step),
            node_id=node_id,
            fruit=fruit,
            num=int(num),
            stim_path=stim_path,
            pos=(x, y),
        ))

    if not fruitA or not fruitB:
        a2, b2 = infer_fruitA_fruitB(nodes)
        fruitA = fruitA or a2
        fruitB = fruitB or b2

    # 主序列 steps
    seq_steps: List[int] = []
    pn = obj.get("path_node_ids") or obj.get("path") or obj.get("sequence")
    if isinstance(pn, list) and pn:
        for v in pn:
            s = _safe_int(v)
            if s is not None:
                seq_steps.append(int(s))
    if not seq_steps:
        seq_steps = sorted({n.step for n in nodes})

    node_by_step: Dict[int, Node] = {n.step: n for n in nodes}

    full_target = list(range(1, M + 1))
    for s in full_target:
        if s not in seq_steps:
            seq_steps.append(s)
    seq_steps = [s for s in seq_steps if s in full_target]
    seq_steps = sorted(seq_steps, key=lambda x: full_target.index(x))

    missing = [s for s in seq_steps if s not in node_by_step]
    if missing:
        raise ValueError(f"B3 主序列 step 无法映射到节点：missing={missing}（文件：{p}）")

    return int(N), int(M), int(node_diam), style, fruitA, fruitB, nodes, seq_steps, p


def nearest_node_within(nodes: List[Node], pos_xy: Tuple[float, float], r: float) -> Tuple[Optional[Node], float]:
    best = None
    best_d = 1e18
    for n in nodes:
        d = dist(pos_xy, n.pos)
        if d <= r and d < best_d:
            best = n
            best_d = d
    return best, best_d


def fruit_zh(name: str) -> str:
    m = {
        "apple": "苹果",
        "lemon": "柠檬",
        "banana": "香蕉",
        "orange": "橙子",
        "pear": "梨",
        "peach": "桃",
        "unknown": "未知",
    }
    return m.get(name, name)


def node_label(n: Node) -> str:
    return f"{n.fruit}-{n.num}"


def point_in_rect(pt: Tuple[float, float], rect_center: Tuple[float, float], w: float, h: float) -> bool:
    x, y = pt
    cx, cy = rect_center
    return (cx - w / 2 <= x <= cx + w / 2) and (cy - h / 2 <= y <= cy + h / 2)


# =========================
# 4) 主任务
# =========================

def run_b3(
    win: "visual.Window | None" = None,
    subject_id: str = "S001",
    session_id: str = "SES1",
    age: str = "",
    layout_id: int = 0,
    hard_limit_s: float = HARD_LIMIT_S_DEFAULT,
    windowed: bool = False,
    y_origin_top: bool = True,
    node_diam_override: int = 0,
    show_start_wait: bool = True,
    **kwargs,
) -> None:
    root = resolve_root()

    win_provided = win is not None
    if win is None:
        win = visual.Window(
            size=WIN_SIZE_DEFAULT,
            fullscr=(not windowed),
            units="pix",
            color=BG_COLOR,
            allowGUI=windowed,
        )
    win_w, win_h = float(win.size[0]), float(win.size[1])

    N, M, node_diam, style, fruitA, fruitB, nodes, seq_steps, json_path = load_b3_layout_with_version(
        root=root,
        layout_id=layout_id,
        win_w=win_w,
        win_h=win_h,
        y_origin_top=y_origin_top,
    )

    # 主序列
    node_by_step = {n.step: n for n in nodes}
    seq_nodes = [node_by_step[s] for s in seq_steps]

    node_radius = node_diam / 2.0
    hit_radius = node_radius * HIT_RADIUS_MULT
    core_radius = node_radius * CORE_HIT_MULT
    start_tol = node_radius * START_TOL_MULT
    wrong_core_radius = node_radius * WRONG_CORE_MULT

    out_dir = root / "results" / "B3"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = f"{subject_id}_{session_id}_{TASK_TYPE}_layout{layout_id}_{stamp}"
    summary_path = out_dir / f"{base}_summary.csv"
    segments_path = out_dir / f"{base}_segments.csv"
    raw_path = out_dir / f"{base}_raw_path.csv"

    layout_nodes_path = out_dir / f"{base}_layout_nodes.csv"
    event_marker_path = out_dir / f"{base}_event_marker.csv"

    try:
        layout_sha1 = sha1_of_file(json_path)
    except Exception:
        layout_sha1 = ""


    # write layout_nodes for reproducibility
    layout_rows: List[dict] = []
    for n in nodes:
        layout_rows.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "stage_key": "layout",
            "layout_id": int(layout_id),
            "layout_json": str(json_path),
            "layout_sha1": layout_sha1,
            "node_step": int(n.step),
            "node_id": n.node_id,
            "fruit": n.fruit,
            "num": int(n.num),
            "x_px": float(n.pos[0]),
            "y_px": float(n.pos[1]),
            "render_node_diam_px": int(node_diam),
        })
    if layout_rows:
        write_csv(layout_nodes_path, list(layout_rows[0].keys()), layout_rows)

    mouse = event.Mouse(win=win)
    mouse.setVisible(True)

    # stimuli
    img_stims: Dict[str, visual.ImageStim] = {}
    rect_stims: Dict[str, visual.Rect] = {}
    text_stims: Dict[str, visual.TextStim] = {}
    back_discs: Dict[str, visual.Circle] = {}

    for n in nodes:
        back_discs[n.node_id] = visual.Circle(
            win=win,
            radius=node_radius * 0.90,
            pos=n.pos,
            fillColor=BG_COLOR,
            lineColor=None,
        )

        if n.stim_path is not None and n.stim_path.exists():
            img_stims[n.node_id] = visual.ImageStim(
                win=win,
                image=str(n.stim_path),
                pos=n.pos,
                size=(node_diam, node_diam),
                units="pix",
                interpolate=True,
            )
        else:
            rect_stims[n.node_id] = visual.Rect(
                win=win,
                width=node_diam,
                height=node_diam,
                pos=n.pos,
                lineColor=(-1, -1, -1),
                lineWidth=3,
                fillColor=(1, 1, 1),
            )
            text_stims[n.node_id] = visual.TextStim(
                win=win,
                text=str(n.num),
                font=CJK_FONT,
                pos=n.pos,
                color=(-1, -1, -1),
                height=48,
                bold=True,
            )

    # 轨迹：固化 + live
    committed_path_stims: List[visual.ShapeStim] = []
    live_path = visual.ShapeStim(
        win=win,
        vertices=[(0, 0), (1, 1)],
        closeShape=False,
        lineColor=LINE_COLOR,
        lineWidth=LINE_W,
        fillColor=None,
    )

    # rings
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
    # - 独立运行 B3 时：展示通用"操作方法/正式任务提示"(若存在) + B3 专属指导页。
    # - run_all 调用 B3 时：默认只展示 B3 专属指导页，避免与前置练习/总说明重复。
    # =========================
    canvas_w, canvas_h = win_w, win_h

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
                height=max(18.0, canvas_h * 0.045),
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

    zdy_dir = root / "stimuli" / "zdy"
    img_b3 = zdy_dir / "B3_1.png"

    img_howto = zdy_dir / "1.png"
    img_formal = zdy_dir / "2.png"
    if (not img_formal.exists()) and (zdy_dir / "all_3.png").exists():
        img_formal = zdy_dir / "all_3.png"

    show_common = bool(kwargs.get("show_common_instructions", (not win_provided)))
    pages: List[Path] = []
    if show_common:
        if img_howto.exists():
            pages.append(img_howto)
        if img_formal.exists():
            pages.append(img_formal)
    pages.append(img_b3)

    for p in pages:
        k = show_image_wait(p)
        if k == "escape":
            if not win_provided:
                win.close()
            return

    # =========================
    # 正式阶段：先等待"点到起始点"
    # =========================
    global_clock = core.Clock()
    stage_key = "B3_formal"

    started = False
    task_start_ms = 0

    idx = 0  # 当前正确点索引（0=起点）
    finished = 0
    await_finish_enter = False
    completion_time_s: Optional[float] = None
    start_to_first_correct_s: Optional[float] = None

    total_errors = 0
    order_errors = 0
    type_errors = 0
    timeout_errors = 0
    invalid_start_count = 0

    raw_rows: List[dict] = []
    seg_rows: List[SegmentRow] = []

    # event markers (for run_all QC)
    event_marker_rows: List[dict] = []
    def add_marker(event_name: str, note: str = "", k_from: int = -1, k_to: int = -1) -> None:
        event_marker_rows.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "stage_key": stage_key,
            "layout_id": int(layout_id),
            "ts_ms": now_ms(global_clock),
            "event": event_name,
            "from_k": k_from,
            "to_k": k_to,
            "note": note,
        })
    seg_index = 0

    # 绘制/路径状态
    pen_down = False
    segment_start_ms: Optional[int] = None
    current_path_draw: List[Tuple[float, float]] = []
    current_path_len = 0.0

    last_sample_ms = 0
    last_progress_ms = 0

    hint_active_until_ms = 0
    error_flash_until_ms = 0
    error_flash_node: Optional[Node] = None

    need_return = False  # 错误后必须回到当前正确点才能继续
    return_hint_until_ms = 0

    cand_node: Optional[Node] = None
    cand_since: Optional[float] = None

    hud = visual.TextStim(
        win=win,
        text="",
        font=CJK_FONT,
        color=(-0.25, -0.25, -0.25),
        height=HUD_SIZE,
        pos=(0, win_h / 2 - 26),
        wrapWidth=win_w * 0.92,
    )
    msg = visual.TextStim(
        win=win,
        text="",
        font=CJK_FONT,
        color=(-0.2, -0.2, -0.2),
        height=22,
        pos=(0, win_h / 2 - 52),
        wrapWidth=win_w * 0.92,
    )

    def cur_node() -> Node:
        return seq_nodes[idx]

    def next_node() -> Optional[Node]:
        if idx + 1 >= len(seq_nodes):
            return None
        return seq_nodes[idx + 1]

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

    def classify_wrong(expected_next: Node, wrong: Node) -> str:
        if wrong.fruit != expected_next.fruit:
            return "type"
        return "order"

    # --- 起始等待循环：高亮起点直到按下起点 ---
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

        # 轨迹（尚未开始则无）
        for st in committed_path_stims:
            st.draw()

        # 节点（先画底盘再画图）
        for n in nodes:
            back_discs[n.node_id].draw()
        for n in nodes:
            if n.node_id in img_stims:
                img_stims[n.node_id].pos = n.pos
                img_stims[n.node_id].draw()
            else:
                rect_stims[n.node_id].draw()
                text_stims[n.node_id].draw()

        # 起始点高亮
        start_ring.pos = cur_node().pos
        start_ring.draw()

        hud.text = "请先点到起始点开始"
        hud.draw()
        win.flip()

        if pressed:
            if dist(pos, cur_node().pos) <= start_tol:
                started = True
                task_start_ms = now_ms(global_clock)
                last_sample_ms = task_start_ms
                last_progress_ms = task_start_ms
                add_marker("BLOCK_START", "start timing", k_from=cur_node().step, k_to=cur_node().step)

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
            add_marker("HARD_LIMIT", "elapsed>=hard_limit", k_from=cur_node().step, k_to=(next_node().step if next_node() else -1))
            break

        keys = event.getKeys()
        if "escape" in keys:
            finished = 0
            completion_time_s = min(elapsed_s, hard_limit_s)
            add_marker("EXIT_EARLY", "escape", k_from=cur_node().step, k_to=(next_node().step if next_node() else -1))
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
                "stage_key": stage_key,
                "layout_id": layout_id,
                "ts_ms": now,
                "x_px": pos[0],
                "y_px": pos[1],
                "is_pen_down": 1 if pressed else 0,
            })
            last_sample_ms = now

        cur = cur_node()
        nxt = next_node()

        # 卡住提示（回退阶段不提示）
        if (not need_return) and (nxt is not None) and (now - last_progress_ms >= int(STALL_HINT_S * 1000)):
            timeout_errors += 1
            hint_active_until_ms = now + int(HINT_FLASH_S * 1000)
            last_progress_ms = now

            seg_index += 1
            seg_rows.append(SegmentRow(
                segment_index=seg_index,
                stage_key=stage_key,
                task_type=TASK_TYPE,
                layout_id=layout_id,
                kind="MARKER",
                from_label=node_label(cur),
                to_label=node_label(nxt),
                from_fruit=cur.fruit,
                to_fruit=nxt.fruit,
                from_num=cur.num,
                to_num=nxt.num,
                start_ts_ms=now,
                end_ts_ms=now,
                duration_ms=0,
                path_length_px=0.0,
                is_error=0,
                error_type="timeout_hint",
                note="stall>=10s -> highlight next",
            ))

            add_marker("TIMEOUT_PROMPT", "stall>=10s", k_from=cur.step, k_to=nxt.step)

        # pen down
        if pressed and not pen_down:
            pen_down = True
            reset_candidate()

            if need_return:
                # 错误回退期间：必须从当前正确点开始
                if dist(pos, cur.pos) > start_tol:
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
                # 正常：必须从当前正确点起笔
                if dist(pos, cur.pos) > start_tol:
                    invalid_start_count += 1
                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="ERROR",
                        from_label=node_label(cur),
                        to_label=node_label(cur),
                        from_fruit=cur.fruit,
                        to_fruit=cur.fruit,
                        from_num=cur.num,
                        to_num=cur.num,
                        start_ts_ms=now,
                        end_ts_ms=now,
                        duration_ms=0,
                        path_length_px=0.0,
                        is_error=1,
                        error_type="invalid_start",
                        note="pen down not near current node",
                    ))
                    pen_down = False
                    segment_start_ms = None
                    current_path_draw = []
                    current_path_len = 0.0
                else:
                    segment_start_ms = now
                    current_path_draw = []
                    current_path_len = 0.0
                    add_draw_point(pos)

        # pen up
        elif (not pressed) and pen_down:
            pen_down = False
            reset_candidate()

            if segment_start_ms is not None and (not need_return) and (nxt is not None):
                picked, _ = nearest_node_within(nodes, pos, hit_radius)

                # 松手落在正确下一点
                if picked is not None and picked.step == nxt.step:
                    seg_end = now
                    seg_dur = seg_end - segment_start_ms

                    if start_to_first_correct_s is None and idx == 0:
                        start_to_first_correct_s = (seg_end - task_start_ms) / 1000.0

                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="SEGMENT",
                        from_label=node_label(cur),
                        to_label=node_label(nxt),
                        from_fruit=cur.fruit,
                        to_fruit=nxt.fruit,
                        from_num=cur.num,
                        to_num=nxt.num,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end,
                        duration_ms=seg_dur,
                        path_length_px=float(current_path_len),
                        is_error=0,
                        error_type="none",
                        note="release inside correct next",
                    ))

                    commit_polyline(list(current_path_draw))

                    idx += 1
                    last_progress_ms = now

                    if idx >= len(seq_nodes) - 1:
                        finished = 1
                        completion_time_s = (now - task_start_ms) / 1000.0
                        await_finish_enter = True

                # 松手落在错误点（非当前点）=> 错误 + 要求回退
                elif picked is not None and picked.node_id != cur.node_id:
                    total_errors += 1
                    et = classify_wrong(nxt, picked)
                    if et == "type":
                        type_errors += 1
                    else:
                        order_errors += 1

                    seg_end = now
                    seg_dur = seg_end - segment_start_ms

                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="ERROR",
                        from_label=node_label(cur),
                        to_label=node_label(picked),
                        from_fruit=cur.fruit,
                        to_fruit=picked.fruit,
                        from_num=cur.num,
                        to_num=picked.num,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end,
                        duration_ms=seg_dur,
                        path_length_px=float(current_path_len),
                        is_error=1,
                        error_type=et,
                        note="release inside wrong node -> require return",
                    ))

                    commit_polyline(list(current_path_draw))

                    error_flash_node = picked
                    error_flash_until_ms = now + int(ERROR_FLASH_S * 1000)
                    need_return = True
                    return_hint_until_ms = now + int(RETURN_HINT_S * 1000)

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

            if (not need_return) and (nxt is not None):
                picked, picked_d = nearest_node_within(nodes, pos, hit_radius)

                if picked is None or picked.node_id == cur.node_id:
                    reset_candidate()
                else:
                    if cand_node is None or picked.node_id != cand_node.node_id:
                        cand_node = picked
                        cand_since = time.perf_counter()

                    dwell = (time.perf_counter() - cand_since) if cand_since is not None else 0.0

                    # 正确点：核心圈立即命中 或 短停留命中
                    if picked.step == nxt.step:
                        if (picked_d <= core_radius) or (dwell >= RIGHT_DWELL_S):
                            seg_end = now
                            seg_dur = seg_end - segment_start_ms

                            if start_to_first_correct_s is None and idx == 0:
                                start_to_first_correct_s = (seg_end - task_start_ms) / 1000.0

                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index,
                                stage_key=stage_key,
                                task_type=TASK_TYPE,
                                layout_id=layout_id,
                                kind="SEGMENT",
                                from_label=node_label(cur),
                                to_label=node_label(nxt),
                                from_fruit=cur.fruit,
                                to_fruit=nxt.fruit,
                                from_num=cur.num,
                                to_num=nxt.num,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end,
                                duration_ms=seg_dur,
                                path_length_px=float(current_path_len),
                                is_error=0,
                                error_type="none",
                                note="continuous confirm correct next",
                            ))

                            commit_polyline(list(current_path_draw))

                            idx += 1
                            last_progress_ms = now
                            reset_candidate()

                            if idx >= len(seq_nodes) - 1:
                                finished = 1
                                completion_time_s = (now - task_start_ms) / 1000.0
                                await_finish_enter = True

                            # 不断笔续连：切新段，从当前正确点位置开始
                            segment_start_ms = now
                            current_path_draw = []
                            current_path_len = 0.0
                            add_draw_point(cur_node().pos)

                    # 错误点：进入核心圈 + 停留触发（更稳，少误触）
                    else:
                        if (picked_d <= wrong_core_radius) and (dwell >= WRONG_DWELL_S):
                            total_errors += 1
                            et = classify_wrong(nxt, picked)
                            if et == "type":
                                type_errors += 1
                            else:
                                order_errors += 1

                            seg_end = now
                            seg_dur = seg_end - segment_start_ms

                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index,
                                stage_key=stage_key,
                                task_type=TASK_TYPE,
                                layout_id=layout_id,
                                kind="ERROR",
                                from_label=node_label(cur),
                                to_label=node_label(picked),
                                from_fruit=cur.fruit,
                                to_fruit=picked.fruit,
                                from_num=cur.num,
                                to_num=picked.num,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end,
                                duration_ms=seg_dur,
                                path_length_px=float(current_path_len),
                                is_error=1,
                                error_type=et,
                                note="long dwell on wrong node core -> require return",
                            ))

                            commit_polyline(list(current_path_draw))

                            error_flash_node = picked
                            error_flash_until_ms = now + int(ERROR_FLASH_S * 1000)
                            need_return = True
                            return_hint_until_ms = now + int(RETURN_HINT_S * 1000)

                            # 错误后要求松手再继续
                            pen_down = False
                            segment_start_ms = None
                            current_path_draw = []
                            current_path_len = 0.0
                            reset_candidate()

        # ===== 绘制 =====
        win.clearBuffer()

        for st in committed_path_stims:
            st.draw()

        if pen_down and len(current_path_draw) >= 2:
            live_path.setVertices(current_path_draw)
            live_path.draw()

        # 节点
        for n in nodes:
            back_discs[n.node_id].draw()
        for n in nodes:
            if n.node_id in img_stims:
                img_stims[n.node_id].pos = n.pos
                img_stims[n.node_id].draw()
            else:
                rect_stims[n.node_id].draw()
                text_stims[n.node_id].draw()

        if now <= hint_active_until_ms and nxt is not None:
            hint_ring.pos = nxt.pos
            hint_ring.draw()

        if now <= error_flash_until_ms and error_flash_node is not None:
            error_ring.pos = error_flash_node.pos
            error_ring.draw()

        if need_return and now <= return_hint_until_ms:
            return_ring.pos = cur_node().pos
            return_ring.draw()

        if need_return:
            msg.text = "请回到当前点后继续"
        else:
            msg.text = ""

        hud.text = f"进度：{idx + 1}/{len(seq_nodes)}"
        hud.draw(); msg.draw()

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

    # =========================
    # 保存
    # =========================
    if completion_time_s is None:
        completion_time_s = min((now_ms(global_clock) - task_start_ms) / 1000.0, hard_limit_s)
    if start_to_first_correct_s is None:
        start_to_first_correct_s = float(completion_time_s)

    summary_fields = [
        "subject_id", "session_id", "age", "task_type", "layout_id",
        "layout_json", "layout_sha1",
        "N", "M", "style", "fruitA", "fruitB",
        "finished",
        "completion_time_s", "start_to_first_correct_s",
        "total_errors", "order_errors", "type_errors",
        "timeout_errors", "invalid_start_count",
        "hard_limit_s",
        "timestamp",
    ]
    summary_row = {
        "subject_id": subject_id,
        "session_id": session_id,
        "task_type": TASK_TYPE,
        "layout_id": int(layout_id),
        "layout_json": str(json_path),
        "layout_sha1": layout_sha1,
        "N": int(N),
        "M": int(len(seq_nodes)),
        "style": style,
        "fruitA": fruitA,
        "fruitB": fruitB,
        "finished": int(finished),
        "completion_time_s": round(float(completion_time_s), 4),
        "start_to_first_correct_s": round(float(start_to_first_correct_s), 4),
        "total_errors": int(total_errors),
        "order_errors": int(order_errors),
        "type_errors": int(type_errors),
        "timeout_errors": int(timeout_errors),
        "invalid_start_count": int(invalid_start_count),
        "hard_limit_s": float(hard_limit_s),
        "timestamp": time.strftime("%Y%m%d_%H%M%S"),
    }
    write_csv(summary_path, summary_fields, [summary_row])

    seg_fields = [
        "subject_id", "session_id", "age",
        "segment_index", "stage_key", "task_type", "layout_id",
        "kind",
        "from_label", "to_label",
        "from_fruit", "to_fruit",
        "from_num", "to_num",
        "start_ts_ms", "end_ts_ms", "duration_ms",
        "path_length_px",
        "is_error", "error_type",
        "note",
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
            "layout_id": r.layout_id,
            "kind": r.kind,
            "from_label": r.from_label,
            "to_label": r.to_label,
            "from_fruit": r.from_fruit,
            "to_fruit": r.to_fruit,
            "from_num": r.from_num,
            "to_num": r.to_num,
            "start_ts_ms": r.start_ts_ms,
            "end_ts_ms": r.end_ts_ms,
            "duration_ms": r.duration_ms,
            "path_length_px": round(float(r.path_length_px), 3),
            "is_error": r.is_error,
            "error_type": r.error_type,
            "note": r.note,
        })
    write_csv(segments_path, seg_fields, seg_out)

    raw_fields = [
        "subject_id", "session_id", "age", "task_type", "stage_key",
        "layout_id", "ts_ms", "x_px", "y_px", "is_pen_down",
    ]
    write_csv(raw_path, raw_fields, raw_rows)

    # event markers
    marker_fields = ["subject_id","session_id","age","task_type","stage_key","layout_id","ts_ms","event","from_k","to_k","note"]
    write_csv(event_marker_path, marker_fields, event_marker_rows)

    # =========================
    # 结束休息页（仅独立运行时显示，run_all 有自己的休息页）
    # =========================
    if not win_provided:
        zdy_dir = root / "stimuli" / "zdy"
        img_rest = zdy_dir / "3.png"
        if (not img_rest.exists()) and (zdy_dir / "A0_2.png").exists():
            img_rest = zdy_dir / "A0_2.png"
        if (not img_rest.exists()) and (zdy_dir / "B3_2.png").exists():
            img_rest = zdy_dir / "B3_2.png"
        show_image_wait(img_rest, key_list=("space", "return", "num_enter"), allow_escape=True)
        win.close()
    return

    print("\n[SAVED]")
    print("layout_file =", json_path)
    print(summary_path)
    print(segments_path)
    print(raw_path)


# =========================
# 5) CLI
# =========================

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", type=str, default="S001", help="被试编号")
    ap.add_argument("--session", type=str, default="SES1", help="会话编号")
    ap.add_argument("--age", type=str, default="", help="年龄（可空）")

    ap.add_argument("--layout", type=int, default=0, help="布局编号1-3；0=按subject稳定映射到1-3")
    ap.add_argument("--hard_limit", type=float, default=HARD_LIMIT_S_DEFAULT, help="正式阶段硬上限（秒）")
    ap.add_argument("--windowed", action="store_true", help="窗口模式（仅用于电脑调试）")
    ap.add_argument("--y_origin_bottom", action="store_true", help="若 y_norm 是 0=下 1=上，启用此项")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    layout_id = args.layout if args.layout in (1, 2, 3) else pick_layout_id(args.subject)

    run_b3(
        subject_id=args.subject,
        session_id=args.session,
        age=args.age,
        layout_id=layout_id,
        hard_limit_s=float(args.hard_limit),
        windowed=bool(args.windowed),
        y_origin_top=(not args.y_origin_bottom),
    )
    core.quit()