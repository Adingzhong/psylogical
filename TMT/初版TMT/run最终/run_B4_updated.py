# -*- coding: utf-8 -*-
"""
run_B4_last.py — B4 水果A/B交替（图片刺激版，默认 color）
修复：变量名一致性 layout_sha1
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
# 0) 默认参数（B4）
# =========================
TASK_TYPE = "B4"
VERSION_DEFAULT = "N6_v1"

HARD_LIMIT_S_DEFAULT = 40.0

STALL_HINT_S = 10.0
HINT_FLASH_S = 0.85

WIN_SIZE_DEFAULT = (1024, 768)
BG_COLOR = (1, 1, 1)
TEXT_COLOR = (-1, -1, -1)

# 节点大小
NODE_DIAMETER_PX_AUTO = 170

# 命中判定
HIT_RADIUS_MULT = 0.85
START_TOL_MULT = 1.15

CORE_HIT_MULT = 0.45
RIGHT_DWELL_S = 0.12

# 错误：更敏感，但必须进入"错误核心圈"并停留
WRONG_CORE_MULT = 0.58
WRONG_DWELL_S = 0.28

# 连线
LINE_W = 8
LINE_COLOR = (-0.15, -0.15, -0.15)
DRAW_MIN_MOVE_PX = 1.5

ERROR_FLASH_S = 0.30
ERROR_RING_W = 10
ERROR_RING_COLOR = (1, -0.3, -0.3)

HINT_RING_W = 10
HINT_RING_COLOR = (-0.2, 0.6, -0.2)

# 错误后提示"回到当前点"
RETURN_RING_W = 12
RETURN_RING_COLOR = (0.95, 0.65, 0.05)

# 起始点高亮
START_RING_W = 12
START_RING_COLOR = (0.1, 0.55, 0.95)

RAW_SAMPLE_DT = 1.0 / 60.0

# HUD
HUD_SIZE = 20

# 图片渲染缩放
IMG_SCALE = 1.00

# 防止节点中心跑到屏幕外
CLAMP_PAD_PX = 8.0

FRUIT_ZH = {
    "apple": "苹果",
    "lemon": "柠檬",
    "banana": "香蕉",
    "orange": "橙子",
}


# =========================
# 1) 数据结构
# =========================
@dataclass
class Node:
    node_id: str
    step: int          
    fruit: str         
    num: int           
    style: str         
    stim_rel: str      
    pos: Tuple[float, float]  


@dataclass
class SegmentRow:
    segment_index: int
    stage_key: str
    task_type: str
    layout_id: int
    kind: str            
    from_label: str
    to_label: str
    from_kind: str       
    to_kind: str
    from_value: int      
    to_value: int
    start_ts_ms: int
    end_ts_ms: int
    duration_ms: int
    path_length_px: float
    is_error: int
    error_type: str      
    note: str


# =========================
# 2) 工具函数
# =========================
def resolve_root() -> Path:
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


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def pick_layout_id(subject_id: str) -> int:
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


def _norm_to_pix(v: float, span: float, axis: str, y_origin_top: bool) -> float:
    if 0.0 <= v <= 1.0:
        if axis == "x":
            return (v - 0.5) * span
        return (0.5 - v) * span if y_origin_top else (v - 0.5) * span
    if -1.0 <= v <= 1.0:
        return v * (span / 2.0)
    return v


def parse_node_pos_as_pix(
    nd: Dict[str, Any],
    canvas_w: float,
    canvas_h: float,
    y_origin_top: bool,
    ref_canvas_px: Optional[Dict[str, Any]] = None
) -> Tuple[float, float]:
    if "x_norm" in nd and "y_norm" in nd:
        x = _norm_to_pix(float(nd["x_norm"]), canvas_w, "x", y_origin_top)
        y = _norm_to_pix(float(nd["y_norm"]), canvas_h, "y", y_origin_top)
        return x, y

    if "x_px" in nd and "y_px" in nd:
        x_px, y_px = float(nd["x_px"]), float(nd["y_px"])
        if ref_canvas_px and "w" in ref_canvas_px and "h" in ref_canvas_px:
            rw = float(ref_canvas_px["w"])
            rh = float(ref_canvas_px["h"])
            if rw > 0 and rh > 0:
                x_norm = x_px / rw
                y_norm = y_px / rh
                x = _norm_to_pix(float(x_norm), canvas_w, "x", y_origin_top)
                y = _norm_to_pix(float(y_norm), canvas_h, "y", y_origin_top)
                return x, y
        return x_px, y_px

    for key in ("pos_px", "pos"):
        if key in nd and isinstance(nd[key], (list, tuple)) and len(nd[key]) >= 2:
            x, y = float(nd[key][0]), float(nd[key][1])
            if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
                x = _norm_to_pix(x, canvas_w, "x", y_origin_top)
                y = _norm_to_pix(y, canvas_h, "y", y_origin_top)
            return x, y

    if "x" in nd and "y" in nd:
        x, y = float(nd["x"]), float(nd["y"])
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            x = _norm_to_pix(x, canvas_w, "x", y_origin_top)
            y = _norm_to_pix(y, canvas_h, "y", y_origin_top)
        return x, y

    raise ValueError(f"节点坐标字段无法解析：keys={list(nd.keys())}")


def find_layout_file(root: Path, layout_id: int, version: str) -> Path:
    p = root / "layouts" / "B4" / f"{version}_layout{layout_id}.json"
    if p.exists():
        return p
    cand = list((root / "layouts" / "B4").glob(f"*layout{layout_id}.json"))
    if cand:
        return cand[0]
    raise FileNotFoundError(f"找不到布局 JSON：{p}")


def _derive_step(nd: Dict[str, Any], fallback_step: int) -> int:
    v = nd.get("step", None)
    if v is not None:
        try:
            return int(v)
        except Exception:
            pass
    for k in ("node_id", "id", "nodeId"):
        if k in nd and nd[k] is not None:
            try:
                return int(nd[k])
            except Exception:
                pass
    return int(fallback_step)


def _derive_num(nd: Dict[str, Any], stim_rel: str) -> int:
    if nd.get("num", None) is not None:
        try:
            return int(nd["num"])
        except Exception:
            pass
    base = Path(str(stim_rel)).name
    parts = base.replace(".png", "").split("_")
    for tok in reversed(parts):
        if tok.isdigit():
            return int(tok)
    return -1


def _derive_style(nd: Dict[str, Any], stim_rel: str, default_style: str) -> str:
    if nd.get("style", None):
        return str(nd["style"]).strip()
    s = str(stim_rel).lower()
    if "/color/" in s or "_color_" in s:
        return "color"
    if "/bw/" in s or "_bw_" in s:
        return "bw"
    return default_style


def _derive_fruit(nd: Dict[str, Any], stim_rel: str) -> str:
    if nd.get("fruit", None):
        return str(nd["fruit"]).strip().lower()
    s = Path(str(stim_rel)).name.lower()
    if s.startswith("apple_"):
        return "apple"
    if s.startswith("lemon_"):
        return "lemon"
    if s.startswith("banana_"):
        return "banana"
    if s.startswith("orange_"):
        return "orange"
    return "unknown"


def _ensure_stim_rel(fruit: str, style: str, num: int, stim_rel: Optional[str]) -> str:
    if stim_rel:
        return str(stim_rel)
    return f"stimuli/fruits/numbered/{style}/{fruit}_{style}_{num}.png"


def load_b4_layout_with_version(
    root: Path,
    layout_id: int,
    canvas_w: float,
    canvas_h: float,
    y_origin_top: bool,
    version: str
) -> Tuple[int, int, int, str, str, str, List[Node], List[int], Path]:
    p = find_layout_file(root, layout_id, version)
    obj = json.loads(p.read_text(encoding="utf-8"))

    N = int(obj.get("N", 6))
    M = int(obj.get("M", 2 * N - 1))
    node_diam_layout = int(obj.get("node_diam_px", obj.get("nodeDiamPx", 200)))
    style = str(obj.get("style", "color")).strip().lower() or "color"
    fruitA = str(obj.get("fruitA", obj.get("fruit_a", "apple"))).strip().lower()
    fruitB = str(obj.get("fruitB", obj.get("fruit_b", "lemon"))).strip().lower()

    ref_canvas = obj.get("canvas_px", None)
    nodes_obj = obj.get("nodes", None)
    if nodes_obj is None or not isinstance(nodes_obj, list) or len(nodes_obj) == 0:
        raise ValueError(f"布局 JSON 缺少 nodes 列表：{p}")

    nodes_by_step: Dict[int, Node] = {}
    for i, nd in enumerate(nodes_obj, start=1):
        if not isinstance(nd, dict):
            continue
        step = _derive_step(nd, i)

        stim_rel = nd.get("stim_rel", nd.get("stimRel", nd.get("stim", None)))
        fruit = _derive_fruit(nd, str(stim_rel) if stim_rel else "")
        style2 = _derive_style(nd, str(stim_rel) if stim_rel else "", style)
        num = _derive_num(nd, str(stim_rel) if stim_rel else "")

        stim_rel = _ensure_stim_rel(fruit, style2, num, stim_rel)

        x, y = parse_node_pos_as_pix(nd, canvas_w, canvas_h, y_origin_top, ref_canvas_px=ref_canvas)

        r = node_diam_layout / 2.0
        x = clamp(x, -canvas_w / 2 + r + CLAMP_PAD_PX, canvas_w / 2 - r - CLAMP_PAD_PX)
        y = clamp(y, -canvas_h / 2 + r + CLAMP_PAD_PX, canvas_h / 2 - r - CLAMP_PAD_PX)

        node_id = str(nd.get("node_id", nd.get("id", step))).strip()

        nodes_by_step[int(step)] = Node(
            node_id=node_id,
            step=int(step),
            fruit=str(fruit),
            num=int(num),
            style=str(style2),
            stim_rel=str(stim_rel),
            pos=(float(x), float(y)),
        )

    seq_steps: List[int] = []
    if isinstance(obj.get("path_node_ids", None), list) and obj["path_node_ids"]:
        for v in obj["path_node_ids"]:
            try:
                seq_steps.append(int(v))
            except Exception:
                pass
    if not seq_steps:
        seq_steps = list(range(1, M + 1))

    missing = [s for s in seq_steps if s not in nodes_by_step]
    if missing:
        raise ValueError(f"B4 主序列 step 覆盖不全：missing={missing}（文件：{p}）")

    nodes = [nodes_by_step[s] for s in sorted(nodes_by_step.keys())]
    return N, M, node_diam_layout, style, fruitA, fruitB, nodes, seq_steps, p


def nearest_node_within(nodes: List[Node], pos_xy: Tuple[float, float], r: float) -> Tuple[Optional[Node], float]:
    best = None
    best_d = 1e18
    for n in nodes:
        d = dist(pos_xy, n.pos)
        if d <= r and d < best_d:
            best = n
            best_d = d
    return best, best_d


def fruit_label(fruit: str, num: int) -> str:
    zh = FRUIT_ZH.get(fruit.lower(), fruit)
    return f"{zh}{num}"


def point_in_rect(pt: Tuple[float, float], rect_center: Tuple[float, float], w: float, h: float) -> bool:
    x, y = pt
    cx, cy = rect_center
    return (cx - w / 2 <= x <= cx + w / 2) and (cy - h / 2 <= y <= cy + h / 2)


# =========================
# 3) 主任务
# =========================
def run_b4(
    win: "visual.Window | None" = None,
    subject_id: str = "S001",
    session_id: str = "SES1",
    age: str = "",
    layout_id: int = 0,
    hard_limit_s: float = HARD_LIMIT_S_DEFAULT,
    windowed: bool = False,
    y_origin_top: bool = True,
    version: str = VERSION_DEFAULT,
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
    canvas_w, canvas_h = float(win.size[0]), float(win.size[1])

    N, M, node_diam_layout, style, fruitA, fruitB, nodes, seq_steps, json_path = load_b4_layout_with_version(
        root, layout_id, canvas_w, canvas_h, y_origin_top, version
    )

    if node_diam_override > 0:
        node_diam = int(node_diam_override)
    else:
        node_diam = int(min(node_diam_layout, NODE_DIAMETER_PX_AUTO))

    node_radius = node_diam / 2.0
    hit_radius = node_radius * HIT_RADIUS_MULT
    core_radius = node_radius * CORE_HIT_MULT
    wrong_core_radius = node_radius * WRONG_CORE_MULT
    start_tol = node_radius * START_TOL_MULT

    step_to_node: Dict[int, Node] = {n.step: n for n in nodes}
    seq: List[int] = list(seq_steps)

    def cur_node(idx: int) -> Node:
        return step_to_node[seq[idx]]

    def next_node(idx: int) -> Optional[Node]:
        if idx + 1 >= len(seq):
            return None
        return step_to_node[seq[idx + 1]]

    out_dir = root / "results" / TASK_TYPE
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = f"{subject_id}_{session_id}_{TASK_TYPE}_layout{layout_id}_{stamp}"

    summary_path = out_dir / f"{base}_summary.csv"
    segments_path = out_dir / f"{base}_segments.csv"
    raw_path = out_dir / f"{base}_raw_path.csv"

    layout_nodes_path = out_dir / f"{base}_layout_nodes.csv"
    event_marker_path = out_dir / f"{base}_event_marker.csv"

    mouse = event.Mouse(win=win)
    mouse.setVisible(True)

    back_discs: Dict[str, visual.Circle] = {}
    img_stims: Dict[str, visual.ImageStim] = {}
    for n in nodes:
        back_discs[n.node_id] = visual.Circle(
            win=win,
            radius=node_radius * 0.90,
            pos=n.pos,
            fillColor=BG_COLOR,
            lineColor=None,
        )

        img_path = root / n.stim_rel
        if not img_path.exists():
            raise FileNotFoundError(f"找不到刺激图片：{img_path}")

        img_stims[n.node_id] = visual.ImageStim(
            win=win,
            image=str(img_path),
            pos=n.pos,
            size=(node_diam * IMG_SCALE, node_diam * IMG_SCALE),
            units="pix",
            interpolate=True,
        )

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
        win=win, radius=node_radius * 1.10, pos=(0, 0),
        lineColor=HINT_RING_COLOR, lineWidth=HINT_RING_W, fillColor=None
    )
    error_ring = visual.Circle(
        win=win, radius=node_radius * 1.12, pos=(0, 0),
        lineColor=ERROR_RING_COLOR, lineWidth=ERROR_RING_W, fillColor=None
    )
    return_ring = visual.Circle(
        win=win, radius=node_radius * 1.14, pos=(0, 0),
        lineColor=RETURN_RING_COLOR, lineWidth=RETURN_RING_W, fillColor=None
    )
    start_ring = visual.Circle(
        win=win, radius=node_radius * 1.14, pos=(0, 0),
        lineColor=START_RING_COLOR, lineWidth=START_RING_W, fillColor=None
    )

    def add_draw_point(poly: List[Tuple[float, float]], pt: Tuple[float, float]) -> None:
        if not poly:
            poly.append(pt)
            return
        if dist(pt, poly[-1]) >= DRAW_MIN_MOVE_PX:
            poly.append(pt)

    def commit_polyline(poly: List[Tuple[float, float]]) -> None:
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

# =========================
    # 指导语（全屏图片）
    # 说明：仅修改"呈现方式"，不改任务逻辑/判错/记录。
    # 规则：
    # - 独立运行：默认显示通用页 1.png、2.png，再显示 B4_1.png
    # - run_all 调用（win_provided=True）：默认仅显示 B4_1.png，避免重复
    #   如需强制显示通用页：传 show_common_instructions=True
    # =========================

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
    img_b4 = zdy_dir / "B4_1.png"

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

    # B4 专属页始终显示（除非 show_start_wait=False）
    pages.append(img_b4)

    if show_start_wait:
        for p in pages:
            k = show_image_wait(p, key_list=("space", "return", "num_enter"), allow_escape=True)
            if k == "escape":
                if not win_provided:
                    win.close()
                return
    global_clock = core.Clock()
    task_start_ms = now_ms(global_clock)

    stage_key = f"{TASK_TYPE}_formal"
    finished = 0
    await_finish_enter = False
    start_to_first_correct_s: Optional[float] = None
    completion_time_s: Optional[float] = None

    total_errors = 0
    order_errors = 0
    type_errors = 0
    timeout_errors = 0
    invalid_start_count = 0

    raw_rows: List[dict] = []
    seg_rows: List[SegmentRow] = []
    seg_index = 0

    event_marker_rows: List[dict] = []
    def add_marker(event_name: str, note: str = "", k_from: int = -1, k_to: int = -1) -> None:
        try: ts = now_ms(global_clock)
        except Exception: ts = 0
        event_marker_rows.append({
            "subject_id": subject_id, "session_id": session_id, "age": age, "task_type": TASK_TYPE,
            "style": style, "layout_id": int(layout_id), "ts_ms": int(ts), "event": str(event_name),
            "from_k": int(k_from), "to_k": int(k_to), "note": str(note),
        })

    add_marker("BLOCK_START", "start timing")

    pen_down = False
    segment_start_ms: Optional[int] = None
    current_path: List[Tuple[float, float]] = []
    current_path_len = 0.0

    last_sample_ms = task_start_ms
    last_progress_ms = task_start_ms

    hint_active_until_ms = 0
    error_flash_until_ms = 0
    error_flash_node: Optional[Node] = None

    cand_node: Optional[Node] = None
    cand_since: Optional[float] = None
    need_return = False
    idx = 0  # current step index (0-based)

    hud = visual.TextStim(win=win, text="", font=CJK_FONT, color=(-0.25,-0.25,-0.25), height=HUD_SIZE, pos=(0, canvas_h/2-26))
    msg = visual.TextStim(win=win, text="", font=CJK_FONT, color=(-0.2,-0.2,-0.2), height=22, pos=(0, canvas_h/2-52))

    def reset_candidate():
        nonlocal cand_node, cand_since
        cand_node = None
        cand_since = None

    def classify_wrong(expected: Node, wrong: Node) -> str:
        if wrong.num != expected.num: return "order"
        if wrong.fruit != expected.fruit: return "type"
        return "order"

    while True:
        now = now_ms(global_clock)
        elapsed_s = (now - task_start_ms) / 1000.0

        if elapsed_s >= hard_limit_s and finished == 0:
            finished = 0; completion_time_s = hard_limit_s; break

        keys = event.getKeys()
        if "escape" in keys:
            add_marker("EXIT_EARLY", "escape")
            finished = 0; completion_time_s = min(elapsed_s, hard_limit_s); break

        pressed = mouse.getPressed()[0]
        pos = mouse.getPos()

        if (now - last_sample_ms) >= int(RAW_SAMPLE_DT * 1000):
            raw_rows.append({
                "subject_id": subject_id, "session_id": session_id, "age": age, "task_type": TASK_TYPE,
                "stage_key": stage_key, "layout_id": layout_id, "ts_ms": now, "x_px": pos[0], "y_px": pos[1],
                "is_pen_down": 1 if pressed else 0
            })
            last_sample_ms = now

        cur = cur_node(idx)
        nxt = next_node(idx)

        if (not need_return) and (nxt is not None) and (now - last_progress_ms >= int(STALL_HINT_S * 1000)):
            timeout_errors += 1
            hint_active_until_ms = now + int(HINT_FLASH_S * 1000)
            last_progress_ms = now
            seg_index += 1
            seg_rows.append(SegmentRow(
                segment_index=seg_index, stage_key=stage_key, task_type=TASK_TYPE, layout_id=layout_id, kind="MARKER",
                from_label=fruit_label(cur.fruit, cur.num), to_label=fruit_label(nxt.fruit, nxt.num),
                from_kind=cur.fruit, to_kind=nxt.fruit, from_value=cur.num, to_value=nxt.num,
                start_ts_ms=now, end_ts_ms=now, duration_ms=0, path_length_px=0.0, is_error=0,
                error_type="timeout_hint", note="stall>=10s -> highlight next"
            ))
            add_marker("TIMEOUT_PROMPT", "stall", k_from=cur.step, k_to=nxt.step)

        if pressed and (not pen_down):
            if need_return and dist(pos, cur.pos) > start_tol:
                pen_down = False
            else:
                pen_down = True; reset_candidate()
                if dist(pos, cur.pos) > start_tol:
                    invalid_start_count += 1
                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index, stage_key=stage_key, task_type=TASK_TYPE, layout_id=layout_id, kind="ERROR",
                        from_label=fruit_label(cur.fruit, cur.num), to_label=fruit_label(cur.fruit, cur.num),
                        from_kind=cur.fruit, to_kind=cur.fruit, from_value=cur.num, to_value=cur.num,
                        start_ts_ms=now, end_ts_ms=now, duration_ms=0, path_length_px=0.0, is_error=1,
                        error_type="invalid_start", note="pen down not near current node"
                    ))
                    pen_down = False; segment_start_ms = None; current_path = []; current_path_len = 0.0
                else:
                    need_return = False; segment_start_ms = now; current_path = []; current_path_len = 0.0
                    add_draw_point(current_path, pos)

        elif (not pressed) and pen_down:
            pen_down = False; reset_candidate()
            if segment_start_ms is not None and nxt is not None and (not need_return):
                picked, picked_d = nearest_node_within(nodes, pos, hit_radius)
                if picked is not None and (picked.step == nxt.step):
                    seg_end = now; seg_dur = seg_end - segment_start_ms
                    if start_to_first_correct_s is None and idx == 0: start_to_first_correct_s = (seg_end - task_start_ms) / 1000.0
                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index, stage_key=stage_key, task_type=TASK_TYPE, layout_id=layout_id, kind="SEGMENT",
                        from_label=fruit_label(cur.fruit, cur.num), to_label=fruit_label(nxt.fruit, nxt.num),
                        from_kind=cur.fruit, to_kind=nxt.fruit, from_value=cur.num, to_value=nxt.num,
                        start_ts_ms=segment_start_ms, end_ts_ms=seg_end, duration_ms=seg_dur,
                        path_length_px=float(current_path_len), is_error=0, error_type="none", note="release correct"
                    ))
                    commit_polyline(list(current_path))
                    idx += 1; last_progress_ms = now
                    if idx >= len(seq) - 1: finished = 1; completion_time_s = (now - task_start_ms) / 1000.0; await_finish_enter = True
                elif picked is not None and picked.node_id != cur.node_id:
                    total_errors += 1; et = classify_wrong(nxt, picked)
                    if et == "type": type_errors += 1
                    else: order_errors += 1
                    seg_end = now; seg_dur = seg_end - segment_start_ms
                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index, stage_key=stage_key, task_type=TASK_TYPE, layout_id=layout_id, kind="ERROR",
                        from_label=fruit_label(cur.fruit, cur.num), to_label=fruit_label(picked.fruit, picked.num),
                        from_kind=cur.fruit, to_kind=picked.fruit, from_value=cur.num, to_value=picked.num,
                        start_ts_ms=segment_start_ms, end_ts_ms=seg_end, duration_ms=seg_dur,
                        path_length_px=float(current_path_len), is_error=1, error_type=et, note="release wrong"
                    ))
                    commit_polyline(list(current_path))
                    error_flash_node = picked; error_flash_until_ms = now + int(ERROR_FLASH_S * 1000); need_return = True
            segment_start_ms = None; current_path = []; current_path_len = 0.0

        if pen_down and segment_start_ms is not None:
            if current_path:
                last_pt = current_path[-1]
                if dist(pos, last_pt) > 0.1: current_path_len += dist(pos, last_pt); add_draw_point(current_path, pos)
            if nxt is not None and (not need_return):
                picked, picked_d = nearest_node_within(nodes, pos, hit_radius)
                if picked is None or picked.node_id == cur.node_id: reset_candidate()
                else:
                    if cand_node is None or picked.node_id != cand_node.node_id: cand_node = picked; cand_since = time.perf_counter()
                    dwell = (time.perf_counter() - cand_since) if cand_since is not None else 0.0
                    if picked.step == nxt.step:
                        if (picked_d <= core_radius) or (dwell >= RIGHT_DWELL_S):
                            seg_end = now; seg_dur = seg_end - segment_start_ms
                            if start_to_first_correct_s is None and idx == 0: start_to_first_correct_s = (seg_end - task_start_ms) / 1000.0
                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index, stage_key=stage_key, task_type=TASK_TYPE, layout_id=layout_id, kind="SEGMENT",
                                from_label=fruit_label(cur.fruit, cur.num), to_label=fruit_label(nxt.fruit, nxt.num),
                                from_kind=cur.fruit, to_kind=nxt.fruit, from_value=cur.num, to_value=nxt.num,
                                start_ts_ms=segment_start_ms, end_ts_ms=seg_end, duration_ms=seg_dur,
                                path_length_px=float(current_path_len), is_error=0, error_type="none", note="dwell correct"
                            ))
                            commit_polyline(list(current_path))
                            idx += 1; last_progress_ms = now; reset_candidate()
                            if idx >= len(seq) - 1: finished = 1; completion_time_s = (now - task_start_ms) / 1000.0; await_finish_enter = True
                            segment_start_ms = now; current_path = []; current_path_len = 0.0; add_draw_point(current_path, pos)
                    else:
                        if (picked_d <= wrong_core_radius) and (dwell >= WRONG_DWELL_S):
                            total_errors += 1; et = classify_wrong(nxt, picked)
                            if et == "type": type_errors += 1
                            else: order_errors += 1
                            seg_end = now; seg_dur = seg_end - segment_start_ms
                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index, stage_key=stage_key, task_type=TASK_TYPE, layout_id=layout_id, kind="ERROR",
                                from_label=fruit_label(cur.fruit, cur.num), to_label=fruit_label(picked.fruit, picked.num),
                                from_kind=cur.fruit, to_kind=picked.fruit, from_value=cur.num, to_value=picked.num,
                                start_ts_ms=segment_start_ms, end_ts_ms=seg_end, duration_ms=seg_dur,
                                path_length_px=float(current_path_len), is_error=1, error_type=et, note="dwell wrong"
                            ))
                            commit_polyline(list(current_path))
                            error_flash_node = picked; error_flash_until_ms = now + int(ERROR_FLASH_S * 1000); need_return = True
                            pen_down = False; segment_start_ms = None; current_path = []; current_path_len = 0.0; reset_candidate()

        win.clearBuffer()
        for st in committed_path_stims: st.draw()
        if pen_down and len(current_path) >= 2: live_path.setVertices(current_path); live_path.draw()
        for n in nodes: back_discs[n.node_id].draw(); img_stims[n.node_id].draw()
        if now <= hint_active_until_ms and nxt is not None: hint_ring.pos = nxt.pos; hint_ring.draw()
        if now <= error_flash_until_ms and error_flash_node is not None: error_ring.pos = error_flash_node.pos; error_ring.draw()
        if need_return: return_ring.pos = cur.pos; return_ring.draw(); msg.text = f"请回到 {fruit_label(cur.fruit, cur.num)} 后继续"
        else: msg.text = ""
        hud.text = f"进度：{idx+1}/{len(seq)}"; hud.draw(); msg.draw(); win.flip()
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
 

    add_marker("BLOCK_END", f"finished={int(finished)}")
    if completion_time_s is None: completion_time_s = min((now_ms(global_clock) - task_start_ms) / 1000.0, hard_limit_s)
    if start_to_first_correct_s is None: start_to_first_correct_s = float(completion_time_s)

    # ------------------
    # 修复：统一变量名 layout_sha1
    # ------------------
    layout_sha1 = ""
    try:
        layout_sha1 = sha1_of_file(json_path)
    except Exception:
        pass

    summary_row = {
        "subject_id": subject_id, "session_id": session_id, "age": age, "task_type": TASK_TYPE,
        "layout_id": int(layout_id), "layout_file": str(json_path), "layout_sha1": layout_sha1,
        "version": str(version), "style": str(style), "fruitA": str(fruitA), "fruitB": str(fruitB),
        "layout_node_diam_px": int(node_diam_layout), "render_node_diam_px": int(node_diam),
        "canvas_w": int(canvas_w), "canvas_h": int(canvas_h), "y_origin_top": int(1 if y_origin_top else 0),
        "finished": int(finished), "completion_time_s": round(float(completion_time_s), 4),
        "start_to_first_correct_s": round(float(start_to_first_correct_s), 4),
        "total_errors": int(total_errors), "order_errors": int(order_errors), "type_errors": int(type_errors),
        "timeout_errors": int(timeout_errors), "invalid_start_count": int(invalid_start_count),
        "hard_limit_s": float(hard_limit_s), "timestamp": time.strftime("%Y%m%d_%H%M%S")
    }
    write_csv(summary_path, list(summary_row.keys()), [summary_row])

    seg_out = []
    for r in seg_rows:
        seg_out.append({
            "subject_id": subject_id, "session_id": session_id, "age": age, "segment_index": r.segment_index,
            "stage_key": r.stage_key, "task_type": r.task_type, "layout_id": r.layout_id, "kind": r.kind,
            "from_label": r.from_label, "to_label": r.to_label, "from_kind": r.from_kind, "to_kind": r.to_kind,
            "from_value": r.from_value, "to_value": r.to_value, "start_ts_ms": r.start_ts_ms, "end_ts_ms": r.end_ts_ms,
            "duration_ms": r.duration_ms, "path_length_px": round(float(r.path_length_px), 3), "is_error": r.is_error,
            "error_type": r.error_type, "note": r.note
        })
    write_csv(segments_path, ["subject_id","session_id","age","segment_index","stage_key","task_type","layout_id","kind",
                              "from_label","to_label","from_kind","to_kind","from_value","to_value","start_ts_ms","end_ts_ms",
                              "duration_ms","path_length_px","is_error","error_type","note"], seg_out)
    write_csv(raw_path, ["subject_id","session_id","age","task_type","stage_key","layout_id","ts_ms","x_px","y_px","is_pen_down"], raw_rows)

    try:
        l_rows = []
        for n in nodes:
            l_rows.append({
                "subject_id": subject_id, "session_id": session_id, "age": age, "task_type": TASK_TYPE, "style": style,
                "layout_id": int(layout_id), "layout_file": str(json_path), "layout_sha1": layout_sha1,
                "render_node_diam_px": int(node_diam), "node_id": n.node_id, "step": int(n.step),
                "fruit": str(n.fruit), "num": int(n.num), "x_px": float(n.pos[0]), "y_px": float(n.pos[1]),
            })
        write_csv(layout_nodes_path, list(l_rows[0].keys()), l_rows)
    except: pass
    try: write_csv(event_marker_path, ["subject_id","session_id","age","task_type","style","layout_id","ts_ms","event","from_k","to_k","note"], event_marker_rows)
    except: pass

# =========================
    # 结束休息页（仅独立运行时显示，run_all 有自己的休息页）
    # =========================
    if not win_provided:
        zdy_dir = root / "stimuli" / "zdy"
        img_rest = zdy_dir / "3.png"
        if (not img_rest.exists()) and (zdy_dir / "A0_2.png").exists():
            img_rest = zdy_dir / "A0_2.png"
        if (not img_rest.exists()) and (zdy_dir / "B4_2.png").exists():
            img_rest = zdy_dir / "B4_2.png"
        show_image_wait(img_rest, key_list=("space", "return", "num_enter"), allow_escape=True)
        win.close()
    return


# =========================
# 4) CLI
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
    ap.add_argument("--version", type=str, default=VERSION_DEFAULT, help="布局版本前缀（默认 N6_v1）")
    ap.add_argument("--node_diam", type=int, default=0, help="渲染用节点直径(px)。0=自动（与A1/B3/B4统一）")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    layout_id = args.layout if args.layout in (1, 2, 3) else pick_layout_id(args.subject)

    run_b4(
        subject_id=args.subject,
        session_id=args.session,
        age=args.age,
        layout_id=layout_id,
        hard_limit_s=float(args.hard_limit),
        windowed=bool(args.windowed),
        y_origin_top=(not args.y_origin_bottom),
        version=str(args.version),  
        node_diam_override=int(args.node_diam),
    )

    core.quit()