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
# 0) 任务参数（B1）
# =========================
TASK_TYPE = "B1"
N = 6
VERSION = f"N{N}_v1"

HARD_LIMIT_S_DEFAULT = 40.0

STALL_HINT_S = 10.0
HINT_FLASH_S = 0.8

WIN_SIZE_DEFAULT = (1024, 768)   # 全屏也给 tuple
BG_COLOR = (1, 1, 1)

# 节点样式
NODE_FILL = (1, 1, 1)
NODE_BORDER = (-1, -1, -1)
NODE_BORDER_W = 4
TEXT_COLOR = (-1, -1, -1)

# 字号
NODE_FONT_SIZE = 62
HUD_SIZE = 22

# 命中判定（与 A0 的"更稳健"策略一致）
HIT_RADIUS_MULT = 0.85
START_TOL_MULT = 1.10

CORE_HIT_MULT = 0.45
RIGHT_DWELL_S = 0.12

# 错误：更敏感，但加"核心圈"约束避免擦边误触
WRONG_DWELL_S = 0.27
WRONG_CORE_MULT = 0.55

# 连线（真实轨迹）
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

# 节点大小：默认"适中"，如果 layout 里太大则下调；可用 --node_diam 覆盖
NODE_DIAMETER_PX_AUTO = 150


# =========================
# 1) 数据结构
# =========================
CHN2NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12
}


@dataclass
class Node:
    node_id: str
    label: str
    kind: str            # "arabic" / "chinese"
    value: int
    pos: Tuple[float, float]   # pix（原点中心）


@dataclass
class SegmentRow:
    segment_index: int
    stage_key: str
    task_type: str
    layout_id: int
    kind: str              # SEGMENT / ERROR / MARKER
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
    error_type: str        # none / order / type / timeout_hint / invalid_start / return_required
    note: str


# =========================
# 2) 基础工具函数
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


def label_to_value_and_kind(label: str, category: Optional[str] = None) -> Tuple[int, str]:
    lab = str(label).strip()

    if category:
        c = str(category).strip().lower()
        if c in ("arabic", "digit", "number"):
            if lab.isdigit():
                return int(lab), "arabic"
        if c in ("chinese", "han", "hanzi"):
            if lab in CHN2NUM:
                return CHN2NUM[lab], "chinese"

    if lab.isdigit():
        return int(lab), "arabic"
    if lab in CHN2NUM:
        return CHN2NUM[lab], "chinese"
    return -1, "unknown"


def find_layout_file(root: Path, layout_id: int) -> Path:
    p = root / "layouts" / "B1" / f"{VERSION}_layout{layout_id}.json"
    if p.exists():
        return p
    raise FileNotFoundError(f"找不到布局 JSON：{p}")


def _norm_to_pix(v: float, span: float, axis: str, y_origin_top: bool) -> float:
    if 0.0 <= v <= 1.0:
        if axis == "x":
            return (v - 0.5) * span
        return (0.5 - v) * span if y_origin_top else (v - 0.5) * span
    if -1.0 <= v <= 1.0:
        return v * (span / 2.0)
    return v


def parse_node_pos_as_pix(nd: Dict[str, Any], canvas_w: float, canvas_h: float, y_origin_top: bool) -> Tuple[float, float]:
    if "x_px" in nd and "y_px" in nd:
        return float(nd["x_px"]), float(nd["y_px"])

    if "x_norm" in nd and "y_norm" in nd:
        x = _norm_to_pix(float(nd["x_norm"]), canvas_w, "x", y_origin_top)
        y = _norm_to_pix(float(nd["y_norm"]), canvas_h, "y", y_origin_top)
        return x, y

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


def load_b1_layout(root: Path, layout_id: int, canvas_w: float, canvas_h: float, y_origin_top: bool) -> Tuple[List[Node], int, Path]:
    p = find_layout_file(root, layout_id)
    obj = json.loads(p.read_text(encoding="utf-8"))

    node_diam = int(obj.get("node_diam_px", 180))
    nodes_obj = obj.get("nodes", None)
    if nodes_obj is None or not isinstance(nodes_obj, list):
        raise ValueError(f"布局 JSON 缺少 nodes 列表：{p}")

    nodes: List[Node] = []
    for nd in nodes_obj:
        if not isinstance(nd, dict):
            continue
        node_id = str(nd.get("node_id", nd.get("id", ""))).strip() or f"node_{len(nodes)+1:02d}"
        label = str(nd.get("label", nd.get("text", ""))).strip()
        category = nd.get("category", None)

        x, y = parse_node_pos_as_pix(nd, canvas_w, canvas_h, y_origin_top)

        val, kind = label_to_value_and_kind(label, category)
        if kind not in ("arabic", "chinese") or val < 0:
            raise ValueError(f"无法识别节点标签/类型：label={label}, category={category}")

        nodes.append(Node(
            node_id=node_id,
            label=label,
            kind=kind,
            value=int(val),
            pos=(x, y)
        ))

    if len(nodes) != (2 * N - 1):
        raise ValueError(f"B1 节点数不对：期望 {2*N-1}，实际 {len(nodes)}（文件：{p}）")

    have_ar = {n.value for n in nodes if n.kind == "arabic"}
    have_ch = {n.value for n in nodes if n.kind == "chinese"}
    need_ar = set(range(1, N + 1))
    need_ch = set(range(1, N))

    if need_ar - have_ar:
        raise ValueError(f"B1 缺少阿拉伯数字：{sorted(list(need_ar - have_ar))}")
    if need_ch - have_ch:
        raise ValueError(f"B1 缺少汉字数字：{sorted(list(need_ch - have_ch))}")

    return nodes, node_diam, p


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
# 4) 主任务
# =========================
def run_b1(
    win: Optional[visual.Window] = None,
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
            allowGUI=windowed
    )
    canvas_w, canvas_h = float(win.size[0]), float(win.size[1])

    nodes, layout_node_diam, layout_path = load_b1_layout(root, layout_id, canvas_w, canvas_h, y_origin_top)

    # 渲染直径：默认适中（不改变布局位置，只调节点大小）
    if node_diam_override > 0:
        render_diam = int(node_diam_override)
    else:
        render_diam = min(int(layout_node_diam), int(NODE_DIAMETER_PX_AUTO))

    node_radius = render_diam / 2.0
    hit_radius = node_radius * HIT_RADIUS_MULT
    core_radius = node_radius * CORE_HIT_MULT
    start_tol = node_radius * START_TOL_MULT
    wrong_core_radius = node_radius * WRONG_CORE_MULT

    # 正确序列：1 → 一 → 2 → 二 ... → 6
    seq: List[Tuple[str, int]] = []
    for k in range(1, N + 1):
        seq.append(("arabic", k))
        if k <= N - 1:
            seq.append(("chinese", k))

    kv = {(n.kind, n.value): n for n in nodes}

    def node_at(i: int) -> Node:
        return kv[seq[i]]

    def next_of(i: int) -> Optional[Node]:
        if i + 1 >= len(seq):
            return None
        return kv[seq[i + 1]]

    # 输出路径
    out_dir = root / "results" / "B1"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = f"{subject_id}_{session_id}_{TASK_TYPE}_layout{layout_id}_{stamp}"

    summary_path = out_dir / f"{base}_summary.csv"
    segments_path = out_dir / f"{base}_segments.csv"
    raw_path = out_dir / f"{base}_raw_path.csv"

    layout_nodes_path = out_dir / f"{base}_layout_nodes.csv"
    event_marker_path = out_dir / f"{base}_event_marker.csv"

    # 记录本次 layout 节点（用于复现/质控）
    try:
        layout_rows: List[dict] = []
        layout_sha1 = sha1_of_file(layout_path)
        for nd in nodes:
            layout_rows.append({
                "subject_id": subject_id,
                "session_id": session_id,
                "age": age,
                "task_type": TASK_TYPE,
                "stage_key": "B1_formal",
                "layout_id": layout_id,
                "layout_file": str(layout_path),
                "layout_sha1": layout_sha1,
                "node_id": nd.node_id,
                "label": nd.label,
                "kind": nd.kind,
                "value": nd.value,
                "x_px": nd.pos[0],
                "y_px": nd.pos[1],
            })
        if layout_rows:
            write_csv(layout_nodes_path, list(layout_rows[0].keys()), layout_rows)
    except Exception:
        pass


    mouse = event.Mouse(win=win)
    mouse.setVisible(True)

    def _close_win() -> None:
        if (not win_provided) and (win is not None):
            win.close()
    
    # 视觉对象：节点（用渲染直径）
    circles: Dict[str, visual.Circle] = {}
    labels: Dict[str, visual.TextStim] = {}
    for n in nodes:
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
            text=n.label,
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


    # =========================
    # 指导语（图片版；仅改呈现，不改任务逻辑）
    # =========================
    def _show_fullscreen_image(img_path: Path, accept_keys: Tuple[str, ...] = ("space", "return", "num_enter")) -> bool:
        """显示全屏指导语图片 + 底部蓝色按钮；按按钮/accept_keys 继续；按 ESC 退出。
        按钮有 hover/press 视觉反馈。返回 True=继续，False=退出。
        """
        stim = visual.ImageStim(
            win=win,
            image=str(img_path),
            units="pix",
            size=(canvas_w, canvas_h)
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

        # 缓冲期（防连击）
        event.clearEvents()
        timer = core.Clock()
        prev_pressed = True
        min_wait = 0.3
        while timer.getTime() < min_wait:
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
                return True
            prev_pressed = cur_pressed

            # 键盘检测
            keys = event.getKeys()
            if "escape" in keys:
                return False
            for k in accept_keys:
                if k in keys:
                    return True

            core.wait(0.008)

    # run_all 调用时默认不重复展示通用页；独立运行时展示通用页
    show_common = bool(kwargs.get("show_common_instructions", False))
    if not win_provided:
        show_common = True

    if show_common:
        p1 = root / "stimuli" / "zdy" / "1.png"
        if p1.exists():
            if not _show_fullscreen_image(p1):
                _close_win()
                return
        p2 = root / "stimuli" / "zdy" / "2.png"
        if p2.exists():
            if not _show_fullscreen_image(p2):
                _close_win()
                return

    # B1 专属指导语图片
    instr_image_path = root / "stimuli" / "zdy" / "B1_1.png"
    if instr_image_path.exists():
        if not _show_fullscreen_image(instr_image_path):
            _close_win()
            return

    # 正式阶段：先进入"起始点高亮等待"——直到按在 1 上才开始计时
    stage_key = "B1_formal"
    global_clock = core.Clock()
    started = False
    task_start_ms = 0

    # 状态
    idx = 0  # 当前节点在 seq 的索引（起点）
    finished = 0
    need_return = False  # 错误后必须回到当前正确点

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
        event_marker_rows.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "stage_key": stage_key,
            "layout_id": layout_id,
            "ts_ms": now_ms(global_clock),
            "event": event_name,
            "from_k": k_from,
            "to_k": k_to,
            "note": note,
        })

    # 绘制/轨迹
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
    cand_since: Optional[float] = None  # perf time

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

    def classify_wrong(cur: Node, wrong: Node) -> str:
        nxt = next_of(idx)
        if nxt is None:
            return "order"
        if wrong.kind != nxt.kind:
            return "type"
        return "order"

    # 起始等待：高亮 1（seq[0]）
    if show_start_wait:
        start_node = node_at(0)

        event.clearEvents()
        while True:
            keys = event.getKeys()
            if "escape" in keys:
                _close_win()
                return

            pressed = mouse.getPressed()[0]
            pos = mouse.getPos()

            win.clearBuffer()
            for n in nodes:
                circles[n.node_id].draw()
                labels[n.node_id].draw()

            start_ring.pos = start_node.pos
            start_ring.draw()

            hud.text = "请先点到 1 开始"
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

    # ===== 正式循环 =====
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

        cur = node_at(idx)
        nxt = next_of(idx)

        # 卡住提示：10s 无进展
        if started and (not need_return) and (nxt is not None) and (now - last_progress_ms >= int(STALL_HINT_S * 1000)):
            timeout_errors += 1
            hint_active_until_ms = now + int(HINT_FLASH_S * 1000)
            last_progress_ms = now

            add_marker("TIMEOUT_PROMPT", "stall>=10s", k_from=cur.value, k_to=(nxt.value if nxt else -1))

            seg_index += 1
            seg_rows.append(SegmentRow(
                segment_index=seg_index,
                stage_key=stage_key,
                task_type=TASK_TYPE,
                layout_id=layout_id,
                kind="MARKER",
                from_label=cur.label,
                to_label=nxt.label,
                from_kind=cur.kind,
                to_kind=nxt.kind,
                from_value=cur.value,
                to_value=nxt.value,
                start_ts_ms=now,
                end_ts_ms=now,
                duration_ms=0,
                path_length_px=0.0,
                is_error=0,
                error_type="timeout_hint",
                note="stall>=10s -> highlight next"
            ))

        # pen down
        if pressed and not pen_down:
            pen_down = True
            reset_candidate()

            if need_return:
                # 错误回退阶段：必须从当前正确点附近重新开始（不计 invalid_start）
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
                # 正常：必须从当前点起笔，否则记 invalid_start
                if dist(pos, cur.pos) > start_tol:
                    invalid_start_count += 1
                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="ERROR",
                        from_label=cur.label,
                        to_label=cur.label,
                        from_kind=cur.kind,
                        to_kind=cur.kind,
                        from_value=cur.value,
                        to_value=cur.value,
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
                picked, picked_d = nearest_node_within(nodes, pos, hit_radius)

                # 松手落在下一正确点：正确段
                if picked is not None and (picked.kind == nxt.kind and picked.value == nxt.value):
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
                        from_label=cur.label,
                        to_label=nxt.label,
                        from_kind=cur.kind,
                        to_kind=nxt.kind,
                        from_value=cur.value,
                        to_value=nxt.value,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end,
                        duration_ms=seg_dur,
                        path_length_px=float(current_path_len),
                        is_error=0,
                        error_type="none",
                        note="release inside correct next"
                    ))

                    commit_polyline(list(current_path))

                    idx += 1
                    last_progress_ms = now

                    if idx >= len(seq) - 1:
                        finished = 1
                        completion_time_s = (now - task_start_ms) / 1000.0
                        break

                # 松手落在错误点：错误 + 回退
                elif picked is not None and picked.node_id != cur.node_id:
                    total_errors += 1
                    et = classify_wrong(cur, picked)
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
                        from_label=cur.label,
                        to_label=picked.label,
                        from_kind=cur.kind,
                        to_kind=picked.kind,
                        from_value=cur.value,
                        to_value=picked.value,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end,
                        duration_ms=seg_dur,
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
            if current_path:
                last_pt = current_path[-1]
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

                    # 正确点：核心圈 or 短停留 -> 命中
                    if picked.kind == nxt.kind and picked.value == nxt.value:
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
                                from_label=cur.label,
                                to_label=nxt.label,
                                from_kind=cur.kind,
                                to_kind=nxt.kind,
                                from_value=cur.value,
                                to_value=nxt.value,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end,
                                duration_ms=seg_dur,
                                path_length_px=float(current_path_len),
                                is_error=0,
                                error_type="none",
                                note="continuous confirm correct next"
                            ))

                            commit_polyline(list(current_path))

                            idx += 1
                            last_progress_ms = now
                            reset_candidate()

                            if idx >= len(seq) - 1:
                                finished = 1
                                completion_time_s = (now - task_start_ms) / 1000.0
                                break

                            # 不断笔续连：切新段
                            segment_start_ms = now
                            current_path = []
                            current_path_len = 0.0
                            add_draw_point(pos)

                    # 错误点：更敏感但必须进入核心圈才算"长停留选错"
                    else:
                        if (picked_d <= wrong_core_radius) and (dwell >= WRONG_DWELL_S):
                            total_errors += 1
                            et = classify_wrong(cur, picked)
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
                                from_label=cur.label,
                                to_label=picked.label,
                                from_kind=cur.kind,
                                to_kind=picked.kind,
                                from_value=cur.value,
                                to_value=picked.value,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end,
                                duration_ms=seg_dur,
                                path_length_px=float(current_path_len),
                                is_error=1,
                                error_type=et,
                                note="long dwell on wrong node core -> require return"
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

        # ===== 绘制 =====
        win.clearBuffer()

        # 固化轨迹
        for st in committed_path_stims:
            st.draw()

        # 当前段轨迹
        if pen_down and len(current_path) >= 2:
            live_path.setVertices(current_path)
            live_path.draw()

        # 节点（白底遮挡线穿过节点内部）
        for n in nodes:
            circles[n.node_id].draw()
            labels[n.node_id].draw()

        # 卡住提示：高亮下一正确点
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
            msg.text = f"请回到 {cur.label} 后继续"
        else:
            msg.text = ""

        hud.text = f"进度：{idx+1}/{len(seq)}"
        hud.draw()
        msg.draw()

        win.flip()

    add_marker("BLOCK_END", f"finished={finished}")

    # ===== 保存 =====
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
        "from_label", "to_label",
        "from_kind", "to_kind",
        "from_value", "to_value",
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
            "from_label": r.from_label,
            "to_label": r.to_label,
            "from_kind": r.from_kind,
            "to_kind": r.to_kind,
            "from_value": r.from_value,
            "to_value": r.to_value,
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

    # event markers
    try:
        marker_fields = ["subject_id","session_id","age","task_type","stage_key","layout_id","ts_ms","event","from_k","to_k","note"]
        write_csv(event_marker_path, marker_fields, event_marker_rows)
    except Exception:
        pass



    # ===== 结束休息页（仅独立运行时显示，run_all 有自己的休息页）=====
    if not win_provided:
        end_image_path = root / "stimuli" / "zdy" / "3.png"
        if not end_image_path.exists():
            end_image_path = root / "stimuli" / "zdy" / "A0_2.png"
        _show_fullscreen_image(end_image_path, accept_keys=("space", "return", "num_enter"))

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
    ap.add_argument("--y_origin_bottom", action="store_true", help="若 y_norm 是 0=下 1=上，启用此项")
    ap.add_argument("--node_diam", type=int, default=0, help="渲染用节点直径(px)。0=自动适中")
    ap.add_argument("--no_start_wait", action="store_true", help="关闭起始点等待（默认开启）")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    layout_id = args.layout if args.layout in (1, 2, 3) else pick_layout_id(args.subject)

    run_b1(
        subject_id=args.subject,
        session_id=args.session,
        age=args.age,
        layout_id=layout_id,
        hard_limit_s=float(args.hard_limit),
        windowed=bool(args.windowed),
        y_origin_top=(not args.y_origin_bottom),
        node_diam_override=int(args.node_diam),
        show_start_wait=(not args.no_start_wait),
    )