# -*- coding: utf-8 -*-

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
# 0) 任务参数（B2）
# =========================
TASK_TYPE = "B2"
N = 6
VERSION = f"N{N}_v1"

HARD_LIMIT_S_DEFAULT = 40.0

STALL_HINT_S = 10.0
HINT_FLASH_S = 0.8

WIN_SIZE_DEFAULT = (1024, 768)
BG_COLOR = (1, 1, 1)

NODE_FILL = (1, 1, 1)
NODE_BORDER = (-1, -1, -1)
NODE_BORDER_W = 4
TEXT_COLOR = (-1, -1, -1)

NODE_FONT_SIZE = 72
HUD_SIZE = 22

# 命中判定（稳 + 适老）
HIT_RADIUS_MULT = 0.85
CORE_HIT_MULT = 0.45
START_TOL_MULT = 1.10

# 不断笔 dwell
RIGHT_DWELL_S = 0.12

# 错误触发：更敏感一点，但通过"核心圈/核心方块"约束降低擦边误触
WRONG_DWELL_S = 0.29
WRONG_CORE_MULT = 0.55

# 轨迹
LINE_W = 8
LINE_COLOR = (-0.15, -0.15, -0.15)
DRAW_MIN_MOVE_PX = 1.5

ERROR_FLASH_S = 0.30
ERROR_RING_W = 10
ERROR_RING_COLOR = (1, -0.3, -0.3)

HINT_RING_W = 10
HINT_RING_COLOR = (-0.2, 0.6, -0.2)

START_RING_W = 12
START_RING_COLOR = (0.1, 0.55, 0.95)

RETURN_RING_W = 12
RETURN_RING_COLOR = (0.95, 0.65, 0.05)

RAW_SAMPLE_DT = 1.0 / 60.0

# 默认渲染用节点直径（若布局里更大，自动下调到这个值）
NODE_DIAMETER_PX_AUTO = 150


# =========================
# 1) 数据结构
# =========================
@dataclass
class Node:
    node_id: str
    value: int
    shape: str                 # "square" / "circle"
    role: str                  # "main" / "lure"
    k: Optional[int]
    pos: Tuple[float, float]


@dataclass
class SegmentRow:
    segment_index: int
    stage_key: str
    task_type: str
    layout_id: int
    kind: str               # SEGMENT / ERROR / MARKER
    from_value: int
    to_value: int
    from_shape: str
    to_shape: str
    start_ts_ms: int
    end_ts_ms: int
    duration_ms: int
    path_length_px: float
    is_error: int
    error_type: str         # none / order / type / timeout_hint / invalid_start / return_required
    note: str


# =========================
# 2) 基础工具
# =========================
def resolve_root() -> Path:
    here = Path(__file__).resolve().parent
    for p in [here] + list(here.parents):
        if (p / "layouts").exists():
            return p
    return here


def now_ms(global_clock: core.Clock) -> int:
    return int(round(global_clock.getTime() * 1000))


def dist(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


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


def sha1_of_file(p: Path) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_layout_file(root: Path, layout_id: int) -> Path:
    p = root / "layouts" / "B2" / f"{VERSION}_layout{layout_id}.json"
    if p.exists():
        return p
    raise FileNotFoundError(f"找不到布局 JSON：{p}")


def _norm_to_pix(v: float, span: float, axis: str, y_origin_top: bool) -> float:
    if axis == "x":
        return (v - 0.5) * span
    return (0.5 - v) * span if y_origin_top else (v - 0.5) * span


def parse_node_pos_as_pix(
    nd: Dict[str, Any],
    canvas_w: float,
    canvas_h: float,
    y_origin_top: bool,
    preview_canvas_px: Optional[List[int]] = None,
) -> Tuple[float, float]:
    # 优先 norm
    if "x_norm" in nd and "y_norm" in nd:
        x = _norm_to_pix(float(nd["x_norm"]), canvas_w, "x", y_origin_top)
        y = _norm_to_pix(float(nd["y_norm"]), canvas_h, "y", y_origin_top)
        return x, y

    # 兼容 preview 像素坐标（按 canvas 归一化后再映射）
    if "x_px" in nd and "y_px" in nd and preview_canvas_px and len(preview_canvas_px) >= 2:
        pw, ph = float(preview_canvas_px[0]), float(preview_canvas_px[1])
        x_norm = float(nd["x_px"]) / pw
        y_norm = float(nd["y_px"]) / ph
        x = _norm_to_pix(x_norm, canvas_w, "x", y_origin_top)
        y = _norm_to_pix(y_norm, canvas_h, "y", y_origin_top)
        return x, y

    if "pos" in nd and isinstance(nd["pos"], (list, tuple)) and len(nd["pos"]) >= 2:
        x, y = float(nd["pos"][0]), float(nd["pos"][1])
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            x = _norm_to_pix(x, canvas_w, "x", y_origin_top)
            y = _norm_to_pix(y, canvas_h, "y", y_origin_top)
        return x, y

    raise ValueError(f"节点坐标字段无法解析：keys={list(nd.keys())}")


def fit_positions_if_needed(
    positions: List[Tuple[float, float]],
    canvas_w: float,
    canvas_h: float,
    margin: float
) -> List[Tuple[float, float]]:
    if not positions:
        return positions

    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    safe_minx = -canvas_w / 2 + margin
    safe_maxx = canvas_w / 2 - margin
    safe_miny = -canvas_h / 2 + margin
    safe_maxy = canvas_h / 2 - margin

    inside = (minx >= safe_minx and maxx <= safe_maxx and miny >= safe_miny and maxy <= safe_maxy)
    if inside:
        return positions

    bw = maxx - minx if (maxx - minx) > 1e-6 else 1.0
    bh = maxy - miny if (maxy - miny) > 1e-6 else 1.0
    target_w = canvas_w - 2 * margin
    target_h = canvas_h - 2 * margin
    s = min(target_w / bw, target_h / bh, 1.0)

    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0

    out: List[Tuple[float, float]] = []
    for (x, y) in positions:
        xx = (x - cx) * s
        yy = (y - cy) * s
        out.append((xx, yy))
    return out


def load_b2_layout(
    root: Path,
    layout_id: int,
    canvas_w: float,
    canvas_h: float,
    y_origin_top_override: Optional[bool]
) -> Tuple[List[Node], int, List[Tuple[str, int, str]], Path]:
    p = find_layout_file(root, layout_id)
    obj = json.loads(p.read_text(encoding="utf-8"))

    node_diam = int(obj.get("node_size_px", obj.get("node_diam_px", 165)))
    preview_canvas_px = obj.get("preview_canvas_px", None)

    y_origin = str(obj.get("y_norm_origin", "top")).strip().lower()
    y_origin_top_json = (y_origin != "bottom")
    y_origin_top = y_origin_top_json if (y_origin_top_override is None) else y_origin_top_override

    nodes_obj = obj.get("nodes", None)
    if nodes_obj is None or not isinstance(nodes_obj, list):
        raise ValueError(f"布局 JSON 缺少 nodes 列表：{p}")

    nodes: List[Node] = []
    for nd in nodes_obj:
        if not isinstance(nd, dict):
            continue
        node_id = str(nd.get("node_id", nd.get("id", ""))).strip() or f"node_{len(nodes)+1:02d}"
        value = int(nd.get("value"))
        shape = str(nd.get("shape", "")).strip().lower()
        role = str(nd.get("role", "lure")).strip().lower()
        k = nd.get("k", None)
        k_int = int(k) if (k is not None and str(k).strip().isdigit()) else None

        if shape not in ("square", "circle"):
            raise ValueError(f"B2 节点 shape 非法：{shape}（node_id={node_id}，文件={p}）")

        x, y = parse_node_pos_as_pix(nd, canvas_w, canvas_h, y_origin_top, preview_canvas_px)
        nodes.append(Node(node_id=node_id, value=value, shape=shape, role=role, k=k_int, pos=(x, y)))

    main_seq_obj = obj.get("main_sequence", None)
    main_sequence: List[Tuple[str, int, str]] = []

    if isinstance(main_seq_obj, list) and len(main_seq_obj) > 0:
        for it in main_seq_obj:
            if not isinstance(it, dict):
                continue
            v = int(it.get("value"))
            sh = str(it.get("shape")).strip().lower()
            if sh not in ("square", "circle"):
                raise ValueError(f"B2 main_sequence 里 shape 非法：{sh}（文件：{p}）")
            main_sequence.append((sh, v, "from_json"))
    else:
        start_shape = str(obj.get("start_shape", "square")).strip().lower()
        if start_shape not in ("square", "circle"):
            start_shape = "square"
        for v in range(1, N + 1):
            sh = start_shape if (v % 2 == 1) else ("circle" if start_shape == "square" else "square")
            main_sequence.append((sh, v, "derived"))

    if len(main_sequence) != N:
        raise ValueError(f"B2 主序列长度不对：期望 {N}，实际 {len(main_sequence)}（文件：{p}）")

    need_vals = set(range(1, N + 1))
    have_vals = {v for (_, v, _) in main_sequence}
    if need_vals != have_vals:
        raise ValueError(f"B2 主序列 value 覆盖不对：need=1..{N}，have={sorted(list(have_vals))}（文件：{p}）")

    # 主序列节点必须存在
    for (sh, v, _) in main_sequence:
        ok = any((n.value == v and n.shape == sh and n.role == "main") for n in nodes)
        if not ok:
            ok2 = any((n.value == v and n.shape == sh) for n in nodes)
            if not ok2:
                raise ValueError(f"B2 缺少主序列节点：{sh}{v}（文件：{p}）")

    margin = (node_diam / 2.0) + 18.0
    fitted = fit_positions_if_needed([n.pos for n in nodes], canvas_w, canvas_h, margin)
    nodes = [Node(**{**n.__dict__, "pos": fitted[i]}) for i, n in enumerate(nodes)]

    return nodes, node_diam, main_sequence, p


def node_hit_test(
    node: Node,
    pos_xy: Tuple[float, float],
    hit_r: float,
    hit_half_side: float
) -> bool:
    dx = pos_xy[0] - node.pos[0]
    dy = pos_xy[1] - node.pos[1]
    if node.shape == "circle":
        return (dx * dx + dy * dy) <= (hit_r * hit_r)
    return (abs(dx) <= hit_half_side) and (abs(dy) <= hit_half_side)


def nearest_node_within(
    nodes: List[Node],
    pos_xy: Tuple[float, float],
    hit_r: float,
    hit_half_side: float
) -> Tuple[Optional[Node], float]:
    best = None
    best_d = 1e18
    for n in nodes:
        if not node_hit_test(n, pos_xy, hit_r, hit_half_side):
            continue
        d = dist(pos_xy, n.pos)
        if d < best_d:
            best = n
            best_d = d
    return best, best_d


# =========================
# 4) 主任务（B2）
# =========================
def run_b2(
    win: Optional[visual.Window] = None,
    subject_id: str = "S001",
    session_id: str = "SES1",
    age: str = "",
    layout_id: int = 0,
    hard_limit_s: float = HARD_LIMIT_S_DEFAULT,
    windowed: bool = False,
    y_origin_top: bool = True,
    y_origin_top_override: Optional[bool] = None,
    node_diam_override: int = 0,
    show_start_wait: bool = True,
    **kwargs,
) -> None:
    root = resolve_root()
    # normalize overrides for integrated run_all usage
    if y_origin_top_override is None:
        y_origin_top_override = bool(y_origin_top)
    win_provided = win is not None

    if win is None:
        win = visual.Window(
            size=WIN_SIZE_DEFAULT,
            fullscr=(not windowed),
            units="pix",
            color=BG_COLOR,
            allowGUI=windowed
    )
    canvas_w, canvas_h = float(win.size[0]), float(win.size[1])

    nodes, layout_node_diam, main_sequence, layout_path = load_b2_layout(
        root=root,
        layout_id=layout_id,
        canvas_w=canvas_w,
        canvas_h=canvas_h,
        y_origin_top_override=y_origin_top_override
    )

    # 渲染节点大小：默认适中；可覆盖
    if node_diam_override > 0:
        render_diam = int(node_diam_override)
    else:
        render_diam = min(int(layout_node_diam), int(NODE_DIAMETER_PX_AUTO))
    node_radius = render_diam / 2.0

    hit_r = node_radius * HIT_RADIUS_MULT
    core_r = node_radius * CORE_HIT_MULT
    hit_half = node_radius * HIT_RADIUS_MULT
    core_half = node_radius * CORE_HIT_MULT
    start_tol = node_radius * START_TOL_MULT

    wrong_core_r = node_radius * WRONG_CORE_MULT
    wrong_core_half = node_radius * WRONG_CORE_MULT

    def find_node_for_step(shape: str, value: int) -> Node:
        mains = [n for n in nodes if n.role == "main" and n.shape == shape and n.value == value]
        if mains:
            return mains[0]
        anys = [n for n in nodes if n.shape == shape and n.value == value]
        return anys[0]

    seq_nodes: List[Node] = [find_node_for_step(sh, v) for (sh, v, _) in main_sequence]

    out_dir = root / "results" / "B2"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = f"{subject_id}_{session_id}_{TASK_TYPE}_layout{layout_id}_{stamp}"

    summary_path = out_dir / f"{base}_summary.csv"
    segments_path = out_dir / f"{base}_segments.csv"
    raw_path = out_dir / f"{base}_raw_path.csv"
    layout_nodes_path = out_dir / f"{base}_layout_nodes.csv"
    event_marker_path = out_dir / f"{base}_event_marker.csv"

    mouse = event.Mouse(win=win)
    mouse.setVisible(True)

    def _close_win() -> None:
        if (not win_provided) and (win is not None):
            win.close()
    
    # 形状刺激：用 render_diam
    squares: Dict[str, visual.Rect] = {}
    circles: Dict[str, visual.Circle] = {}
    labels: Dict[str, visual.TextStim] = {}

    for n in nodes:
        if n.shape == "square":
            squares[n.node_id] = visual.Rect(
                win=win,
                width=render_diam,
                height=render_diam,
                pos=n.pos,
                lineColor=NODE_BORDER,
                lineWidth=NODE_BORDER_W,
                fillColor=NODE_FILL
            )
        else:
            circles[n.node_id] = visual.Circle(
                win=win,
                radius=node_radius,
                pos=n.pos,
                lineColor=NODE_BORDER,
                lineWidth=NODE_BORDER_W,
                fillColor=NODE_FILL
            )
        labels[n.node_id] = visual.TextStim(
            win=win,
            text=str(n.value),
            font=CJK_FONT,
            pos=n.pos,
            color=TEXT_COLOR,
            height=NODE_FONT_SIZE,
            bold=True
        )

    # 轨迹：固化 polyline + 当前段 live polyline
    committed_path_stims: List[visual.ShapeStim] = []
    live_path = visual.ShapeStim(
        win=win,
        vertices=[(0, 0), (1, 1)],
        closeShape=False,
        lineColor=LINE_COLOR,
        lineWidth=LINE_W,
        fillColor=None
    )

    hint_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.08,
        pos=(0, 0),
        lineColor=HINT_RING_COLOR,
        lineWidth=HINT_RING_W,
        fillColor=None
    )
    error_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.10,
        pos=(0, 0),
        lineColor=ERROR_RING_COLOR,
        lineWidth=ERROR_RING_W,
        fillColor=None
    )
    start_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.14,
        pos=(0, 0),
        lineColor=START_RING_COLOR,
        lineWidth=START_RING_W,
        fillColor=None
    )
    return_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.14,
        pos=(0, 0),
        lineColor=RETURN_RING_COLOR,
        lineWidth=RETURN_RING_W,
        fillColor=None
    )

    def commit_polyline(poly: List[Tuple[float, float]]):
        if len(poly) < 2:
            return
        st = visual.ShapeStim(
            win=win,
            vertices=poly,
            closeShape=False,
            lineColor=LINE_COLOR,
            lineWidth=LINE_W,
            fillColor=None
        )
        committed_path_stims.append(st)

    # =========================
    # 指导语（替换为图片，移除语音）
    # =========================
    # =========================
    # 指导语（全屏图片）
    # - 独立运行 B2 时：展示通用"操作方法/正式任务提示"(若存在) + B2 专属指导页。
    # - run_all 调用 B2 时：默认只展示 B2 专属指导页，避免与前置练习/总说明重复。
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
                text=f"[提示页缺失]\\n{img_path.name}\\n\\n按 空格/回车 继续",
                font=CJK_FONT,
                color=TEXT_COLOR,
                height=NODE_FONT_SIZE * 0.55,
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

    # 组织指导页顺序
    zdy_dir = root / "stimuli" / "zdy"
    img_b2 = zdy_dir / "B2_1.png"

    # 通用页：优先使用 1/2.png；若不存在则回退到 all_3.png（旧命名）
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
    pages.append(img_b2)

    for p in pages:
        k = show_image_wait(p)
        if k == "escape":
            _close_win()
            return

    # =========================
    # 正式阶段：起始点高亮等待
    # =========================
    stage_key = "B2_formal"
    global_clock = core.Clock()

    started = False
    task_start_ms = 0

    idx = 0
    finished = 0
    need_return = False
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

    # event markers（用于run_all质控/追溯）
    event_marker_rows: List[dict] = []
    def add_marker(event_name: str, note: str = "", k_from: int = -1, k_to: int = -1) -> None:
        event_marker_rows.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "stage_key": stage_key,
            "layout_id": layout_id,
            "ts_ms": now_ms(global_clock),
            "event": event_name,
            "from_k": int(k_from),
            "to_k": int(k_to),
            "note": note
        })

    pen_down = False
    segment_start_ms: Optional[int] = None
    current_path: List[Tuple[float, float]] = []
    current_path_len = 0.0

    last_sample_ms = 0
    last_progress_ms = 0

    hint_active_until_ms = 0
    error_flash_until_ms = 0
    error_flash_node: Optional[Node] = None

    cand_node: Optional[Node] = None
    cand_since: Optional[float] = None

    hud = visual.TextStim(
        win=win,
        text="",
        font=CJK_FONT,
        color=(-0.25, -0.25, -0.25),
        height=HUD_SIZE,
        pos=(0, canvas_h / 2 - 26),
        wrapWidth=canvas_w * 0.9
    )
    msg = visual.TextStim(
        win=win,
        text="",
        font=CJK_FONT,
        color=(-0.2, -0.2, -0.2),
        height=22,
        pos=(0, canvas_h / 2 - 52),
        wrapWidth=canvas_w * 0.9
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
        nonlocal current_path
        if not current_path:
            current_path = [pt]
            return
        if dist(pt, current_path[-1]) >= DRAW_MIN_MOVE_PX:
            current_path.append(pt)

    def classify_wrong(nxt: Node, wrong: Node) -> str:
        if wrong.value != nxt.value:
            return "order"
        if wrong.shape != nxt.shape:
            return "type"
        return "order"

    # 起始等待
    if show_start_wait:
        start_node = seq_nodes[0]
        event.clearEvents()
        while True:
            keys = event.getKeys()
            if "escape" in keys:
                _close_win()
                return

            pressed = mouse.getPressed()[0]
            pos = mouse.getPos()

            win.clearBuffer()

            # 轨迹（无）
            for n in nodes:
                if n.shape == "square":
                    squares[n.node_id].draw()
                else:
                    circles[n.node_id].draw()
                labels[n.node_id].draw()

            start_ring.pos = start_node.pos
            start_ring.draw()

            hud.text = "请先点到起始点开始"
            hud.draw()
            win.flip()

            if pressed and dist(pos, start_node.pos) <= start_tol:
                started = True
                task_start_ms = now_ms(global_clock)
                add_marker("BLOCK_START", "start timing")
                last_sample_ms = task_start_ms
                last_progress_ms = task_start_ms

                pen_down = True
                segment_start_ms = task_start_ms
                current_path = []
                current_path_len = 0.0
                add_draw_point(pos)
                break
    else:
        started = True
        task_start_ms = now_ms(global_clock)
        add_marker("BLOCK_START", "start timing")
        last_sample_ms = task_start_ms
        last_progress_ms = task_start_ms

    # =========================
    # 正式循环
    # =========================
    while True:
        now = now_ms(global_clock)
        elapsed_s = (now - task_start_ms) / 1000.0 if started else 0.0

        if started and elapsed_s >= hard_limit_s and finished == 0:
            finished = 0
            completion_time_s = hard_limit_s
            break

        keys = event.getKeys()
        if "escape" in keys:
            add_marker("EXIT_EARLY", "escape")
            finished = 0
            completion_time_s = min(elapsed_s, hard_limit_s) if started else 0.0
            break

        pressed = mouse.getPressed()[0]
        pos = mouse.getPos()

        # raw_path 采样
        if started and (now - last_sample_ms) >= int(RAW_SAMPLE_DT * 1000):
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
                "started": 1
            })
            last_sample_ms = now

        cur = cur_node()
        nxt = next_node()

        # 10s 无进展提示：高亮下一正确点（你特别要求）
        if started and (not need_return) and (nxt is not None) and (now - last_progress_ms >= int(STALL_HINT_S * 1000)):
            timeout_errors += 1
            add_marker("TIMEOUT_PROMPT", f"stall>={STALL_HINT_S:.0f}s", k_from=idx, k_to=idx+1)
            hint_active_until_ms = now + int(HINT_FLASH_S * 1000)
            last_progress_ms = now

            seg_index += 1
            seg_rows.append(SegmentRow(
                segment_index=seg_index,
                stage_key=stage_key,
                task_type=TASK_TYPE,
                layout_id=layout_id,
                kind="MARKER",
                from_value=cur.value,
                to_value=nxt.value,
                from_shape=cur.shape,
                to_shape=nxt.shape,
                start_ts_ms=now,
                end_ts_ms=now,
                duration_ms=0,
                path_length_px=0.0,
                is_error=0,
                error_type="timeout_hint",
                note=f"stall>={STALL_HINT_S:.0f}s -> highlight next"
            ))

        # pen down
        if pressed and not pen_down:
            pen_down = True
            reset_candidate()

            if need_return:
                # 错误回退阶段：必须从当前正确点附近重新开始
                if dist(pos, cur.pos) > start_tol:
                    pen_down = False
                    segment_start_ms = None
                    current_path = []
                    current_path_len = 0.0
                else:
                    need_return = False
                    segment_start_ms = now
                    current_path = []
                    current_path_len = 0.0
                    add_draw_point(pos)
            else:
                # 正常：必须从当前点起笔
                if dist(pos, cur.pos) > start_tol:
                    invalid_start_count += 1
                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="ERROR",
                        from_value=cur.value,
                        to_value=cur.value,
                        from_shape=cur.shape,
                        to_shape=cur.shape,
                        start_ts_ms=now,
                        end_ts_ms=now,
                        duration_ms=0,
                        path_length_px=0.0,
                        is_error=1,
                        error_type="invalid_start",
                        note="pen down not near current node"
                    ))
                    pen_down = False
                    segment_start_ms = None
                    current_path = []
                    current_path_len = 0.0
                else:
                    segment_start_ms = now
                    current_path = []
                    current_path_len = 0.0
                    add_draw_point(pos)

        # pen up
        elif (not pressed) and pen_down:
            pen_down = False
            reset_candidate()

            if segment_start_ms is not None and nxt is not None and (not need_return):
                picked, _ = nearest_node_within(nodes, pos, hit_r, hit_half)

                # 松手落在下一正确点：正确段
                if picked is not None and picked.node_id == nxt.node_id:
                    seg_end = now

                    if start_to_first_correct_s is None and idx == 0:
                        start_to_first_correct_s = (seg_end - task_start_ms) / 1000.0

                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="SEGMENT",
                        from_value=cur.value,
                        to_value=nxt.value,
                        from_shape=cur.shape,
                        to_shape=nxt.shape,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end,
                        duration_ms=seg_end - segment_start_ms,
                        path_length_px=float(current_path_len),
                        is_error=0,
                        error_type="none",
                        note="release inside correct next"
                    ))

                    commit_polyline(list(current_path))

                    idx += 1
                    last_progress_ms = now

                    if idx >= len(seq_nodes) - 1:
                        finished = 1
                        completion_time_s = (now - task_start_ms) / 1000.0
                        await_finish_enter = True

                # 松手落在错误点：错误 + 回退
                elif picked is not None and picked.node_id != cur.node_id:
                    total_errors += 1
                    et = classify_wrong(nxt, picked)
                    if et == "type":
                        type_errors += 1
                    else:
                        order_errors += 1

                    seg_end = now
                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="ERROR",
                        from_value=cur.value,
                        to_value=picked.value,
                        from_shape=cur.shape,
                        to_shape=picked.shape,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end,
                        duration_ms=seg_end - segment_start_ms,
                        path_length_px=float(current_path_len),
                        is_error=1,
                        error_type=et,
                        note="release inside wrong node -> require return"
                    ))

                    commit_polyline(list(current_path))
                    error_flash_node = picked
                    error_flash_until_ms = now + int(ERROR_FLASH_S * 1000)
                    need_return = True

            segment_start_ms = None
            current_path = []
            current_path_len = 0.0

        # 不断笔：更新轨迹 + dwell
        if pen_down and segment_start_ms is not None:
            # 更新长度
            if current_path:
                last_pt = current_path[-1]
                if dist(pos, last_pt) >= 0.1:
                    current_path_len += dist(pos, last_pt)
                    add_draw_point(pos)

            if (not need_return) and (nxt is not None):
                picked, picked_d = nearest_node_within(nodes, pos, hit_r, hit_half)

                if picked is None or picked.node_id == cur.node_id:
                    reset_candidate()
                else:
                    if cand_node is None or picked.node_id != cand_node.node_id:
                        cand_node = picked
                        cand_since = time.perf_counter()

                    dwell = (time.perf_counter() - cand_since) if cand_since is not None else 0.0

                    # 正确点：核心立即 or 短停留
                    if picked.node_id == nxt.node_id:
                        inside_core = False
                        if nxt.shape == "circle":
                            inside_core = (picked_d <= core_r)
                        else:
                            dx = abs(pos[0] - nxt.pos[0])
                            dy = abs(pos[1] - nxt.pos[1])
                            inside_core = (dx <= core_half and dy <= core_half)

                        if inside_core or (dwell >= RIGHT_DWELL_S):
                            seg_end = now
                            if start_to_first_correct_s is None and idx == 0:
                                start_to_first_correct_s = (seg_end - task_start_ms) / 1000.0

                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index,
                                stage_key=stage_key,
                                task_type=TASK_TYPE,
                                layout_id=layout_id,
                                kind="SEGMENT",
                                from_value=cur.value,
                                to_value=nxt.value,
                                from_shape=cur.shape,
                                to_shape=nxt.shape,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end,
                                duration_ms=seg_end - segment_start_ms,
                                path_length_px=float(current_path_len),
                                is_error=0,
                                error_type="none",
                                note="continuous confirm correct next"
                            ))

                            commit_polyline(list(current_path))

                            idx += 1
                            last_progress_ms = now
                            reset_candidate()

                            if idx >= len(seq_nodes) - 1:
                                finished = 1
                                completion_time_s = (now - task_start_ms) / 1000.0
                                await_finish_enter = True

                            # 不断笔续连：切新段
                            segment_start_ms = now
                            current_path = []
                            current_path_len = 0.0
                            add_draw_point(pos)

                    # 错误点：更敏感但要求进入"错误核心"才算明确选错
                    else:
                        inside_wrong_core = False
                        if picked.shape == "circle":
                            inside_wrong_core = (picked_d <= wrong_core_r)
                        else:
                            dx = abs(pos[0] - picked.pos[0])
                            dy = abs(pos[1] - picked.pos[1])
                            inside_wrong_core = (dx <= wrong_core_half and dy <= wrong_core_half)

                        if inside_wrong_core and (dwell >= WRONG_DWELL_S):
                            total_errors += 1
                            et = classify_wrong(nxt, picked)
                            if et == "type":
                                type_errors += 1
                            else:
                                order_errors += 1

                            seg_end = now
                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index,
                                stage_key=stage_key,
                                task_type=TASK_TYPE,
                                layout_id=layout_id,
                                kind="ERROR",
                                from_value=cur.value,
                                to_value=picked.value,
                                from_shape=cur.shape,
                                to_shape=picked.shape,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end,
                                duration_ms=seg_end - segment_start_ms,
                                path_length_px=float(current_path_len),
                                is_error=1,
                                error_type=et,
                                note="long dwell on wrong core -> require return"
                            ))

                            commit_polyline(list(current_path))
                            error_flash_node = picked
                            error_flash_until_ms = now + int(ERROR_FLASH_S * 1000)
                            need_return = True

                            # 错误后要求松手再继续（更清晰）
                            pen_down = False
                            segment_start_ms = None
                            current_path = []
                            current_path_len = 0.0
                            reset_candidate()

        # 绘制
        win.clearBuffer()

        for st in committed_path_stims:
            st.draw()

        if pen_down and len(current_path) >= 2:
            live_path.setVertices(current_path)
            live_path.draw()

        # 节点遮挡线
        for n in nodes:
            if n.shape == "square":
                squares[n.node_id].draw()
            else:
                circles[n.node_id].draw()
            labels[n.node_id].draw()

        # 10s 提示下一点
        if now <= hint_active_until_ms and nxt is not None:
            hint_ring.pos = nxt.pos
            hint_ring.draw()

        # 错误闪红
        if now <= error_flash_until_ms and error_flash_node is not None:
            error_ring.pos = error_flash_node.pos
            error_ring.draw()

        # 回退提示：高亮当前点
        if need_return:
            return_ring.pos = cur.pos
            return_ring.draw()
            msg.text = f"请回到 {cur.shape}{cur.value} 后继续"
        else:
            msg.text = ""

        hud.text = f"进度：{idx+1}/{len(seq_nodes)}"
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

        # 结束标记
    try:
        add_marker("BLOCK_END", f"finished={int(finished)}")
    except Exception:
        pass

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
        "subject_id", "session_id", "age", "task_type", "layout_id",
        "layout_file", "layout_sha1",
        "layout_node_diam_px", "render_node_diam_px",
        "finished",
        "completion_time_s", "start_to_first_correct_s",
        "total_errors", "order_errors", "type_errors",
        "timeout_errors", "invalid_start_count",
        "hard_limit_s",
        "timestamp"
    ]
    summary_row = {
        "subject_id": subject_id,
        "session_id": session_id,
        "task_type": TASK_TYPE,
        "layout_id": layout_id,
        "layout_file": str(layout_path),
        "layout_sha1": layout_hash,
        "layout_node_diam_px": int(layout_node_diam),
        "render_node_diam_px": int(render_diam),
        "finished": int(finished),
        "completion_time_s": round(float(completion_time_s), 4),
        "start_to_first_correct_s": round(float(start_to_first_correct_s), 4),
        "total_errors": int(total_errors),
        "order_errors": int(order_errors),
        "type_errors": int(type_errors),
        "timeout_errors": int(timeout_errors),
        "invalid_start_count": int(invalid_start_count),
        "hard_limit_s": float(hard_limit_s),
        "timestamp": time.strftime("%Y%m%d_%H%M%S")
    }
    write_csv(summary_path, summary_fields, [summary_row])

    seg_fields = [
        "subject_id", "session_id", "age",
        "segment_index", "stage_key", "task_type", "layout_id",
        "kind",
        "from_value", "to_value",
        "from_shape", "to_shape",
        "start_ts_ms", "end_ts_ms", "duration_ms",
        "path_length_px",
        "is_error", "error_type",
        "note"
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
            "from_value": r.from_value,
            "to_value": r.to_value,
            "from_shape": r.from_shape,
            "to_shape": r.to_shape,
            "start_ts_ms": r.start_ts_ms,
            "end_ts_ms": r.end_ts_ms,
            "duration_ms": r.duration_ms,
            "path_length_px": round(float(r.path_length_px), 3),
            "is_error": r.is_error,
            "error_type": r.error_type,
            "note": r.note
        })
    write_csv(segments_path, seg_fields, seg_out)

    raw_fields = [
        "subject_id", "session_id", "age", "task_type", "stage_key",
        "layout_id", "ts_ms", "x_px", "y_px", "is_pen_down", "started"
    ]
    write_csv(raw_path, raw_fields, raw_rows)

    # layout_nodes（节点坐标与布局文件追溯）
    layout_fields = ["subject_id","session_id","age","task_type","stage_key","style","layout_id",
                     "layout_file","layout_sha1","node_id","value","shape","role","k","x_px","y_px",
                     "layout_node_diam_px","render_node_diam_px"]
    layout_out: List[dict] = []
    for n in nodes:
        layout_out.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "stage_key": stage_key,
            "style": "bw",  # B2 无颜色版本
            "layout_id": layout_id,
            "layout_file": str(layout_path),
            "layout_sha1": layout_hash,
            "node_id": n.node_id,
            "value": int(n.value),
            "shape": n.shape,
            "role": n.role,
            "k": "" if (n.k is None) else int(n.k),
            "x_px": round(float(n.pos[0]), 3),
            "y_px": round(float(n.pos[1]), 3),
            "layout_node_diam_px": int(layout_node_diam),
            "render_node_diam_px": int(render_diam),
        })
    write_csv(layout_nodes_path, layout_fields, layout_out)

    # event_marker（关键事件）
    marker_fields = ["subject_id","session_id","age","task_type","stage_key","layout_id",
                     "ts_ms","event","from_k","to_k","note"]
    write_csv(event_marker_path, marker_fields, event_marker_rows)

    # =========================
    # 结束休息页（仅独立运行时显示，run_all 有自己的休息页）
    # =========================
    if not win_provided:
        zdy_dir = root / "stimuli" / "zdy"
        img_rest = zdy_dir / "3.png"
        if (not img_rest.exists()) and (zdy_dir / "A0_2.png").exists():
            img_rest = zdy_dir / "A0_2.png"
        if (not img_rest.exists()) and (zdy_dir / "B2_2.png").exists():
            img_rest = zdy_dir / "B2_2.png"
        show_image_wait(img_rest, key_list=("space", "return", "num_enter"), allow_escape=True)
    _close_win()

    print("\n[SAVED]")
    print("layout_file =", layout_path)
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
    ap.add_argument("--y_origin_bottom", action="store_true", help="若 y_norm 是 0=下 1=上，启用此项（覆盖JSON设置）")
    ap.add_argument("--node_diam", type=int, default=0, help="渲染用节点直径(px)。0=自动适中")
    ap.add_argument("--no_start_wait", action="store_true", help="关闭起始点等待（默认开启）")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    layout_id = args.layout if args.layout in (1, 2, 3) else pick_layout_id(args.subject)

    y_override = None
    if args.y_origin_bottom:
        y_override = False

    run_b2(
        subject_id=args.subject,
        session_id=args.session,
        age=args.age,
        layout_id=layout_id,
        hard_limit_s=float(args.hard_limit),
        windowed=bool(args.windowed),
        y_origin_top_override=y_override,
        node_diam_override=int(args.node_diam),
        show_start_wait=(not args.no_start_wait),
    )
    core.quit()