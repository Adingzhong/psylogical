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
# 0) 任务参数（A0）
# =========================
TASK_TYPE = "A0"
N = 6

HARD_LIMIT_S_DEFAULT = 40.0

STALL_HINT_S = 10.0          # 卡住 10s 才提示
HINT_FLASH_S = 0.8           # 高亮闪烁时长

WIN_SIZE_DEFAULT = (1024, 768)  # 全屏也必须给 tuple（PsychoPy不允许 None）
BG_COLOR = (1, 1, 1)

# 节点大小：布局 JSON 里有 node_size_px，但你反馈"太大"
# 这里默认把"渲染直径"控制在 135px（B1/B2 后续也建议同样策略保持一致）
NODE_DIAMETER_PX_AUTO = 135

NODE_FILL = (1, 1, 1)        # 白底遮挡线条穿过节点内部的视觉干扰
NODE_BORDER = (-1, -1, -1)
NODE_BORDER_W = 4

TEXT_COLOR = (-1, -1, -1)
FONT_SIZE = 46

# 命中圈（适老化：避免误触）
HIT_RADIUS_MULT = 0.85
START_TOL_MULT = 1.10

# "路过过滤"参数
CORE_HIT_MULT = 0.45          # 进入核心圈几乎可认定命中
RIGHT_DWELL_S = 0.12          # 下一正确点：停留>=120ms 也算命中（不断笔可用）
WRONG_DWELL_S = 0.27          # ↓更敏感：错误点需停留≥320ms
WRONG_CORE_MULT = 0.62        # 但需更靠近错误节点中心才触发，避免误触

# 连线（轨迹）
LINE_W = 8
LINE_COLOR = (-0.15, -0.15, -0.15)

ERROR_FLASH_S = 0.30
ERROR_RING_W = 10
ERROR_RING_COLOR = (1, -0.3, -0.3)

HINT_RING_W = 10
HINT_RING_COLOR = (-0.2, 0.6, -0.2)


# 起始/回退高亮（用于"先点 1 开始"与"错误后回到上一正确点"）
FOCUS_RING_W = 12
FOCUS_RING_COLOR = (-0.2, 0.2, 0.8)
# 轨迹采样（raw 输出）
RAW_SAMPLE_DT = 1.0 / 60.0

# 前端轨迹点去冗余（绘制用，避免顶级性能浪费）
DRAW_MIN_MOVE_PX = 1.5


# =========================
# 1) 数据结构
# =========================
@dataclass
class Node:
    k: int
    pos: Tuple[float, float]


@dataclass
class SegmentRow:
    segment_index: int
    stage_key: str
    task_type: str
    layout_id: int
    kind: str              # SEGMENT / ERROR / MARKER
    from_k: int
    to_k: int
    start_ts_ms: int
    end_ts_ms: int
    duration_ms: int
    path_length_px: float
    is_error: int
    error_type: str        # none / order / timeout_hint / invalid_start
    hint_level: int
    note: str


# =========================
# 2) 基础工具函数
# =========================
def resolve_root() -> Path:
    """找到包含 layouts/ 的 DTMT 根目录。"""
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
    """同一 subject 稳定映射到 1..3。"""
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
    """
    将归一化坐标转换为像素坐标（win.units='pix'，原点中心）：
    - v in [0,1]：比例坐标（默认 y_origin_top=True -> 0在上1在下）
    - v in [-1,1]：norm 风格
    - 否则当成像素
    """
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
                # 若看起来是 0..1 归一化
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


def find_layout_file(root: Path, layout_id: int) -> Path:
    """
    兼容两种目录结构：
      layouts/A0/N6_v1_layout1.json
      layouts/A0/bw/N6_v1_layout1.json
    """
    cands = [
        root / "layouts" / "A0" / f"N{N}_v1_layout{layout_id}.json",
        root / "layouts" / "A0" / "bw" / f"N{N}_v1_layout{layout_id}.json",
    ]
    for p in cands:
        if p.exists():
            return p
    raise FileNotFoundError("找不到布局 JSON，尝试过：\n" + "\n".join(str(p) for p in cands))


def load_a0_layout(
    root: Path,
    layout_id: int,
    canvas_w: float,
    canvas_h: float,
    y_origin_top: bool
) -> Tuple[List[Node], int, Path]:
    p = find_layout_file(root, layout_id)
    obj = json.loads(p.read_text(encoding="utf-8"))

    node_size_px = int(obj.get("node_size_px", obj.get("node_diam_px", NODE_DIAMETER_PX_AUTO)))
    nodes_obj = obj.get("nodes", None)
    if nodes_obj is None:
        raise ValueError(f"布局 JSON 缺少 nodes 字段：{p}")

    nodes: List[Node] = []
    if isinstance(nodes_obj, list):
        auto_k = 1
        for nd in nodes_obj:
            if not isinstance(nd, dict):
                raise ValueError(f"nodes 列表元素不是 dict：{nd}")

            pos = parse_node_pos(nd, canvas_w, canvas_h, y_origin_top)
            if pos is None:
                raise ValueError(f"节点无法解析坐标字段（pos/pos_px/x,y/x_norm,y_norm）：keys={list(nd.keys())}")

            k = parse_node_k(nd, fallback_k=auto_k)
            if k is None:
                raise ValueError(f"节点无法解析编号：keys={list(nd.keys())}")

            nodes.append(Node(k=int(k), pos=pos))
            auto_k += 1
    elif isinstance(nodes_obj, dict):
        for key, val in nodes_obj.items():
            k = _try_parse_int(key)
            if k is None:
                continue
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                pos = (float(val[0]), float(val[1]))
            elif isinstance(val, dict):
                pos = parse_node_pos(val, canvas_w, canvas_h, y_origin_top)
                if pos is None:
                    raise ValueError(f"nodes dict 节点 {key} 无法解析坐标：keys={list(val.keys())}")
            else:
                raise ValueError(f"nodes dict 节点 {key} 坐标格式不支持：{val}")
            nodes.append(Node(k=int(k), pos=pos))
    else:
        raise ValueError(f"nodes 字段类型不支持：{type(nodes_obj)}（文件：{p}）")

    if len(nodes) != N:
        raise ValueError(f"节点数不等于 N={N}：实际 {len(nodes)}（文件：{p}）")

    ks = sorted(n.k for n in nodes)
    if ks != list(range(1, N + 1)):
        raise ValueError(f"节点编号必须覆盖 1..{N} 且不重复，但现在是：{ks}（文件：{p}）")

    nodes = sorted(nodes, key=lambda n: n.k)
    return nodes, node_size_px, p


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
# 5) 主任务（A0）
# =========================
def run_a0(
    win: Optional[visual.Window] = None,
    subject_id: str = "S001",
    session_id: str = "SES1",
    age: str = "",
    layout_id: int = 0,
    hard_limit_s: float = HARD_LIMIT_S_DEFAULT,
    windowed: bool = False,
    y_origin_top: bool = True,
    node_diam_override: int = 0,
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

    # 读取布局
    nodes, layout_node_diam, layout_file = load_a0_layout(root, layout_id, canvas_w, canvas_h, y_origin_top)

    # 渲染直径：默认"适中"，也可 CLI 覆盖
    render_diam = layout_node_diam
    if node_diam_override > 0:
        render_diam = int(node_diam_override)
    else:
        render_diam = min(int(layout_node_diam), int(NODE_DIAMETER_PX_AUTO))

    node_radius = render_diam / 2.0
    hit_radius = node_radius * HIT_RADIUS_MULT
    core_radius = node_radius * CORE_HIT_MULT
    wrong_core_radius = node_radius * WRONG_CORE_MULT
    start_tol = node_radius * START_TOL_MULT

    # 输出路径
    out_dir = root / "results" / "A0"
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = f"{subject_id}_{session_id}_{TASK_TYPE}_layout{layout_id}_{stamp}"

    summary_path = out_dir / f"{base}_summary.csv"
    segments_path = out_dir / f"{base}_segments.csv"
    raw_path = out_dir / f"{base}_raw_path.csv"

    layout_nodes_path = out_dir / f"{base}_layout_nodes.csv"
    event_marker_path = out_dir / f"{base}_event_marker.csv"


    # layout_nodes 输出（便于质控/复现）
    layout_rows: List[dict] = []
    for n in nodes:
        layout_rows.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "stage_key": "A0_formal",
            "layout_id": int(layout_id),
            "layout_file": str(layout_file),
            "node_k": int(n.k),
            "x_px": float(n.pos[0]),
            "y_px": float(n.pos[1]),
            "render_node_diam_px": int(render_diam),
        })
    write_csv(
        layout_nodes_path,
        ["subject_id","session_id","age","task_type","stage_key","layout_id","layout_file","node_k","x_px","y_px","render_node_diam_px"],
        layout_rows,
    )
    # 鼠标
    mouse = event.Mouse(win=win)
    mouse.setVisible(True)

    def _close_win() -> None:
        if (not win_provided) and (win is not None):
            win.close()
    
    # 视觉对象：节点
    circles: Dict[int, visual.Circle] = {}
    labels: Dict[int, visual.TextStim] = {}
    for n in nodes:
        circles[n.k] = visual.Circle(
            win=win,
            radius=node_radius,
            pos=n.pos,
            lineColor=NODE_BORDER,
            lineWidth=NODE_BORDER_W,
            fillColor=NODE_FILL
        )
        labels[n.k] = visual.TextStim(
            win=win,
            text=str(n.k),
            font=CJK_FONT,
            pos=n.pos,
            color=TEXT_COLOR,
            height=FONT_SIZE,
            bold=True
        )

    # 轨迹：每段用 ShapeStim（polyline）显示
    committed_path_stims: List[visual.ShapeStim] = []

    # 当前段 live path
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

    focus_ring = visual.Circle(
        win=win,
        radius=node_radius * 1.18,
        pos=(0, 0),
        lineColor=FOCUS_RING_COLOR,
        lineWidth=FOCUS_RING_W,
        fillColor=None
    )

    # =========================
    # 指导语（全屏图片）
    # - 独立运行 A0 时：展示通用"操作方法/正式任务提示"(若存在) + A0 专属指导页。
    # - run_all 调用 A0 时：默认只展示 A0 专属指导页，避免与前置练习/总说明重复。
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
                height=FONT_SIZE,
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
    img_a0 = zdy_dir / "A0_1.png"

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
    pages.append(img_a0)

    for p in pages:
        ret = show_image_wait(p)
        if ret == "escape":
            _close_win()
            return

    # =========================
    # 正式阶段
    # =========================
    global_clock = core.Clock()
    # 计时从"触碰起始点 1"开始（更符合纸笔TMT，也便于首点高亮）
    task_start_ms = 0

    stage_key = "A0_formal"
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


    # 错误后需回到"上一正确点"再继续（不计 invalid_start，避免适老化误罚）
    need_return = False
    raw_rows: List[dict] = []
    seg_rows: List[SegmentRow] = []

    # event_marker：记录关键事件（开始/结束/提示/退出等）
    event_marker_rows: List[dict] = []
    def add_marker(event_name: str, note: str = "", k_from: int = -1, k_to: int = -1, ts_ms: Optional[int] = None) -> None:
        nonlocal event_marker_rows
        if ts_ms is None:
            ts_ms = now_ms(global_clock)
        event_marker_rows.append({
            "subject_id": subject_id,
            "session_id": session_id,
            "age": age,
            "task_type": TASK_TYPE,
            "stage_key": stage_key,
            "layout_id": int(layout_id),
            "ts_ms": int(ts_ms),
            "event": event_name,
            "from_k": int(k_from),
            "to_k": int(k_to),
            "note": note,
        })
    seg_index = 0

    pen_down = False
    segment_start_ms: Optional[int] = None

    # 当前段轨迹（绘制 + 统计）
    current_path_draw: List[Tuple[float, float]] = []
    current_path_len = 0.0

    last_sample_ms = task_start_ms
    last_progress_ms = task_start_ms

    hint_active_until_ms = 0
    error_flash_until_ms = 0
    error_flash_k = -1

    # 候选节点停留计时（过滤"路过"）
    cand_node: Optional[Node] = None
    cand_since: Optional[float] = None  # perf_counter

    hud = visual.TextStim(
        win=win,
        text="",
        font=CJK_FONT,
        color=(-0.25, -0.25, -0.25),
        height=20,
        pos=(0, canvas_h / 2 - 26),
        wrapWidth=canvas_w * 0.90
    )

    start_msg = visual.TextStim(
        win=win,
        text="请触碰并按住 1 开始",
        font=CJK_FONT,
        color=(-0.25, -0.25, -0.25),
        height=26,
        pos=(0, -canvas_h * 0.36),
        wrapWidth=canvas_w * 0.90
    )
    return_msg = visual.TextStim(
        win=win,
        text="",
        font=CJK_FONT,
        color=(0.0, 0.0, 0.0),
        height=24,
        pos=(0, -canvas_h * 0.40),
        wrapWidth=canvas_w * 0.92
    )

    def reset_candidate():
        nonlocal cand_node, cand_since
        cand_node = None
        cand_since = None

    def add_draw_point(pt: Tuple[float, float]):
        """前端绘制轨迹点：去冗余。"""
        nonlocal current_path_draw
        if not current_path_draw:
            current_path_draw = [pt]
            return
        if dist(pt, current_path_draw[-1]) >= DRAW_MIN_MOVE_PX:
            current_path_draw.append(pt)

    def commit_segment_polyline(poly: List[Tuple[float, float]]):
        """把一段轨迹固定成 ShapeStim，用于后续全程展示。"""
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
    # 起始节点高亮：必须先触碰 1 才开始计时（直到点到为止）
    # =========================
    event.clearEvents()
    prev_press = False
    while True:
        # 画静态节点（此时还未开始计时）
        win.clearBuffer()
        for k in range(1, N + 1):
            circles[k].draw()
            labels[k].draw()

        focus_ring.pos = circles[1].pos
        focus_ring.draw()
        start_msg.draw()
        # layout_note 可以在这里画，也可以省略，这里省略保持界面干净
        win.flip()

        keys = event.getKeys()
        if "escape" in keys:
            _close_win()
            return

        pressed0 = mouse.getPressed()[0]
        pos0 = mouse.getPos()
        if pressed0 and (not prev_press):
            # 只有触碰起点才开始
            if dist(pos0, circles[1].pos) <= start_tol:
                global_clock.reset()
                add_marker("BLOCK_START", "start timing at node 1", k_from=1, k_to=1, ts_ms=0)
                task_start_ms = 0
                pen_down = True
                segment_start_ms = 0
                current_path_draw = []
                add_draw_point(pos0)
                current_path_len = 0.0
                last_sample_ms = 0
                last_progress_ms = 0
                reset_candidate()
                break
        prev_press = pressed0

    # 主循环
    while True:
        now = now_ms(global_clock)
        elapsed_s = (now - task_start_ms) / 1000.0

        # 硬上限
        if elapsed_s >= hard_limit_s and finished == 0:
            finished = 0
            completion_time_s = hard_limit_s
            break

        keys = event.getKeys()
        if "escape" in keys:
            add_marker("EXIT_EARLY", "escape pressed", k_from=current_k, k_to=next_k, ts_ms=now)
            finished = 0
            completion_time_s = min(elapsed_s, hard_limit_s)
            break

        pressed = mouse.getPressed()[0]
        pos = mouse.getPos()

        # 错误更正：若刚发生错误，必须先回到当前正确节点（上一正确点）再继续
        blocked_press = False
        if pressed and (not pen_down) and need_return:
            cur_pos = circles[current_k].pos
            if dist(pos, cur_pos) > start_tol:
                blocked_press = True
            else:
                need_return = False

        # raw_path 采样（节流）
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
                "is_pen_down": 1 if pressed else 0
            })
            last_sample_ms = now

        # 卡住提示：10s无进展 → 高亮下一目标
        if (finished == 0) and (next_k <= N) and (now - last_progress_ms >= int(STALL_HINT_S * 1000)):
            timeout_errors += 1
            hint_active_until_ms = now + int(HINT_FLASH_S * 1000)
            add_marker("TIMEOUT_PROMPT", "stall>=10s -> highlight next", k_from=current_k, k_to=next_k, ts_ms=now)
            last_progress_ms = now

            seg_index += 1
            seg_rows.append(SegmentRow(
                segment_index=seg_index,
                stage_key=stage_key,
                task_type=TASK_TYPE,
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
                note="stall>=10s -> highlight next"
            ))

        # pen down
        if pressed and not pen_down and (not blocked_press):
            pen_down = True
            reset_candidate()

            # 起笔检查：必须从当前正确节点附近开始（适老：减少误触）
            cur_pos = circles[current_k].pos
            if dist(pos, cur_pos) > start_tol:
                invalid_start_count += 1

                seg_index += 1
                seg_rows.append(SegmentRow(
                    segment_index=seg_index,
                    stage_key=stage_key,
                    task_type=TASK_TYPE,
                    layout_id=layout_id,
                    kind="ERROR",
                    from_k=current_k,
                    to_k=current_k,
                    start_ts_ms=now,
                    end_ts_ms=now,
                    duration_ms=0,
                    path_length_px=0.0,
                    is_error=1,
                    error_type="invalid_start",
                    hint_level=0,
                    note="pen down not near current node"
                ))

                # 直接忽略本次按下，等他重新开始
                pen_down = False
                segment_start_ms = None
                current_path_draw = []
                current_path_len = 0.0
            else:
                segment_start_ms = now
                current_path_draw = []
                add_draw_point(pos)
                current_path_len = 0.0

        # pen up（松手：若松手落点在某节点命中圈内，视为"明确选择"）
        elif (not pressed) and pen_down:
            pen_down = False
            reset_candidate()

            if segment_start_ms is not None and next_k <= N:
                picked, picked_d = nearest_node_within(nodes, pos, hit_radius)

                # 松手落在下一正确点：确认
                if picked is not None and picked.k == next_k:
                    seg_end_ms = now
                    seg_dur = seg_end_ms - segment_start_ms

                    if start_to_first_correct_s is None and current_k == 1 and next_k == 2:
                        start_to_first_correct_s = (seg_end_ms - task_start_ms) / 1000.0

                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="SEGMENT",
                        from_k=current_k,
                        to_k=next_k,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end_ms,
                        duration_ms=seg_dur,
                        path_length_px=float(current_path_len),
                        is_error=0,
                        error_type="none",
                        hint_level=0,
                        note="release inside correct next"
                    ))

                    commit_segment_polyline(list(current_path_draw))

                    current_k = next_k
                    next_k = current_k + 1
                    last_progress_ms = now

                    if current_k == N:
                        finished = 1
                        completion_time_s = (now - task_start_ms) / 1000.0
                        await_finish_enter = True

                # 松手落在错误点：记一次错误（明确选错）
                elif picked is not None and picked.k != current_k:
                    total_errors += 1
                    order_errors += 1

                    seg_end_ms = now
                    seg_dur = seg_end_ms - segment_start_ms

                    seg_index += 1
                    seg_rows.append(SegmentRow(
                        segment_index=seg_index,
                        stage_key=stage_key,
                        task_type=TASK_TYPE,
                        layout_id=layout_id,
                        kind="ERROR",
                        from_k=current_k,
                        to_k=picked.k,
                        start_ts_ms=segment_start_ms,
                        end_ts_ms=seg_end_ms,
                        duration_ms=seg_dur,
                        path_length_px=float(current_path_len),
                        is_error=1,
                        error_type="order",
                        hint_level=0,
                        note="release inside wrong node"
                    ))

                    commit_segment_polyline(list(current_path_draw))
                    need_return = True
                    last_progress_ms = now

                    error_flash_k = picked.k
                    error_flash_until_ms = now + int(ERROR_FLASH_S * 1000)

            # 重置当前段
            segment_start_ms = None
            current_path_draw = []
            current_path_len = 0.0

        # 不断笔：更新轨迹 + 候选停留判定（防"路过"误判）
        if pen_down and segment_start_ms is not None:
            # 更新轨迹与长度
            if current_path_draw:
                last_pt = current_path_draw[-1]
                if dist(pos, last_pt) >= 0.1:
                    current_path_len += dist(pos, last_pt)
                    add_draw_point(pos)

            if next_k <= N:
                picked, picked_d = nearest_node_within(nodes, pos, hit_radius)
                cur_node_obj = nodes[current_k - 1]  # 已经按k排序

                if picked is None or picked.k == current_k:
                    reset_candidate()
                else:
                    # 候选变化
                    if cand_node is None or picked.k != cand_node.k:
                        cand_node = picked
                        cand_since = time.perf_counter()

                    dwell = (time.perf_counter() - cand_since) if cand_since is not None else 0.0

                    # 下一正确点：核心圈立即确认；否则短停留确认
                    if picked.k == next_k:
                        if (picked_d <= core_radius) or (dwell >= RIGHT_DWELL_S):
                            seg_end_ms = now
                            seg_dur = seg_end_ms - segment_start_ms

                            if start_to_first_correct_s is None and current_k == 1 and next_k == 2:
                                start_to_first_correct_s = (seg_end_ms - task_start_ms) / 1000.0

                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index,
                                stage_key=stage_key,
                                task_type=TASK_TYPE,
                                layout_id=layout_id,
                                kind="SEGMENT",
                                from_k=current_k,
                                to_k=next_k,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end_ms,
                                duration_ms=seg_dur,
                                path_length_px=float(current_path_len),
                                is_error=0,
                                error_type="none",
                                hint_level=0,
                                note="continuous confirm correct next"
                            ))

                            commit_segment_polyline(list(current_path_draw))

                            current_k = next_k
                            next_k = current_k + 1
                            last_progress_ms = now
                            reset_candidate()

                            if current_k == N:
                                finished = 1
                                completion_time_s = (now - task_start_ms) / 1000.0
                                await_finish_enter = True

                            # 不断笔续连：切换到新段（保持 pen_down）
                            segment_start_ms = now
                            current_path_draw = []
                            add_draw_point(pos)
                            current_path_len = 0.0

                    # 错误点：长停留才算"明确选错"
                    else:
                        if (picked_d <= wrong_core_radius) and (dwell >= WRONG_DWELL_S):
                            total_errors += 1
                            order_errors += 1

                            seg_end_ms = now
                            seg_dur = seg_end_ms - segment_start_ms

                            seg_index += 1
                            seg_rows.append(SegmentRow(
                                segment_index=seg_index,
                                stage_key=stage_key,
                                task_type=TASK_TYPE,
                                layout_id=layout_id,
                                kind="ERROR",
                                from_k=current_k,
                                to_k=picked.k,
                                start_ts_ms=segment_start_ms,
                                end_ts_ms=seg_end_ms,
                                duration_ms=seg_dur,
                                path_length_px=float(current_path_len),
                                is_error=1,
                                error_type="order",
                                hint_level=0,
                                note="long dwell on wrong node"
                            ))

                            commit_segment_polyline(list(current_path_draw))
                            need_return = True
                            last_progress_ms = now

                            error_flash_k = picked.k
                            error_flash_until_ms = now + int(ERROR_FLASH_S * 1000)

                            # 为了稳定：错误后要求松手再继续
                            pen_down = False
                            segment_start_ms = None
                            current_path_draw = []
                            current_path_len = 0.0
                            reset_candidate()

        # ===== 绘制 =====
        win.clearBuffer()

        # 已确认轨迹（在节点下方）
        for st in committed_path_stims:
            st.draw()

        # 当前段轨迹（在节点下方）
        if pen_down and len(current_path_draw) >= 2:
            live_path.setVertices(current_path_draw)
            live_path.draw()

        # 节点（白底遮挡线穿过节点内部）
        for k in range(1, N + 1):
            circles[k].draw()
            labels[k].draw()

        # 提示/错误
        if now <= hint_active_until_ms and next_k <= N:
            hint_ring.pos = circles[next_k].pos
            hint_ring.draw()

        if now <= error_flash_until_ms and error_flash_k in circles:
            error_ring.pos = circles[error_flash_k].pos
            error_ring.draw()

        # 错误更正提示：高亮上一正确点，要求回退后继续
        if need_return and (current_k in circles):
            focus_ring.pos = circles[current_k].pos
            focus_ring.draw()
            return_msg.text = f"刚才连错了，请回到 {current_k} 后继续"
            return_msg.draw()

        # HUD：只显示进度
        hud.text = f"进度：{current_k}/{N}"
        hud.draw()

        win.flip()
        if await_finish_enter:
            # Show completion message and redraw
            return_msg.text = "完成！请点击屏幕继续"
            return_msg.draw()
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

    # 记录结束标记（无论完成/退出/超时）
    add_marker("BLOCK_END", f"finished={int(finished)}", k_from=current_k, k_to=min(next_k, N), ts_ms=now_ms(global_clock))
    # 保存（保持三类输出）
    # =========================
    if completion_time_s is None:
        completion_time_s = min((now_ms(global_clock) - task_start_ms) / 1000.0, hard_limit_s)
    if start_to_first_correct_s is None:
        start_to_first_correct_s = float(completion_time_s)

    layout_hash = ""
    try:
        layout_hash = sha1_of_file(layout_file)
    except Exception:
        layout_hash = ""

    summary_fields = [
        "subject_id", "session_id", "age", "task_type", "layout_id",
        "layout_file", "layout_sha1",
        "layout_node_diam_px", "render_node_diam_px",
        "canvas_w", "canvas_h", "y_origin_top",
        "finished",
        "completion_time_s", "start_to_first_correct_s",
        "total_errors", "order_errors", "timeout_errors",
        "invalid_start_count",
        "hard_limit_s",
        "timestamp"
    ]
    summary_row = {
        "subject_id": subject_id,
        "session_id": session_id,
        "age": age,
                "task_type": TASK_TYPE,
        "layout_id": int(layout_id),
        "layout_file": str(layout_file),
        "layout_sha1": layout_hash,
        "layout_node_diam_px": int(layout_node_diam),
        "render_node_diam_px": int(render_diam),
        "canvas_w": int(canvas_w),
        "canvas_h": int(canvas_h),
        "y_origin_top": int(1 if y_origin_top else 0),
        "finished": int(finished),
        "completion_time_s": round(float(completion_time_s), 4),
        "start_to_first_correct_s": round(float(start_to_first_correct_s), 4),
        "total_errors": int(total_errors),
        "order_errors": int(order_errors),
        "timeout_errors": int(timeout_errors),
        "invalid_start_count": int(invalid_start_count),
        "hard_limit_s": float(hard_limit_s),
        "timestamp": time.strftime("%Y%m%d_%H%M%S")
    }
    write_csv(summary_path, summary_fields, [summary_row])

    seg_fields = [
        "subject_id", "session_id", "age",
        "segment_index", "stage_key", "task_type", "layout_id",
        "kind", "from_k", "to_k",
        "start_ts_ms", "end_ts_ms", "duration_ms",
        "path_length_px",
        "is_error", "error_type",
        "hint_level", "note"
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
            "from_k": r.from_k,
            "to_k": r.to_k,
            "start_ts_ms": r.start_ts_ms,
            "end_ts_ms": r.end_ts_ms,
            "duration_ms": r.duration_ms,
            "path_length_px": round(float(r.path_length_px), 3),
            "is_error": r.is_error,
            "error_type": r.error_type,
            "hint_level": r.hint_level,
            "note": r.note
        })
    write_csv(segments_path, seg_fields, seg_out)

    raw_fields = [
        "subject_id", "session_id", "age", "task_type", "stage_key",
        "layout_id", "ts_ms", "x_px", "y_px", "is_pen_down"
    ]
    write_csv(raw_path, raw_fields, raw_rows)

    # event_marker 输出
    marker_fields = ["subject_id","session_id","age","task_type","stage_key","layout_id","ts_ms","event","from_k","to_k","note"]
    write_csv(event_marker_path, marker_fields, event_marker_rows)

    # =========================
    # 结束休息页（仅独立运行时显示，run_all 有自己的休息页）
    # =========================
    if not win_provided:
        end_image_path = root / "stimuli" / "zdy" / "3.png"
        if not end_image_path.exists():
            end_image_path = root / "stimuli" / "zdy" / "A0_2.png"
        show_image_wait(end_image_path, key_list=("space", "return", "num_enter"), allow_escape=True, min_wait=0.25)

    _close_win()

    print("\n[SAVED]")
    print("layout_file =", layout_file)
    print(summary_path)
    print(segments_path)
    print(raw_path)


# =========================
# 6) CLI
# =========================
def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", type=str, default="S001", help="被试编号")
    ap.add_argument("--session", type=str, default="SES1", help="会话编号")
    ap.add_argument("--age", type=str, default="", help="年龄（可空）")


    # ✅ 更换布局：--layout 1/2/3；0=按subject稳定映射
    ap.add_argument("--layout", type=int, default=0, help="布局编号1-3；0=按subject稳定映射到1-3")
    ap.add_argument("--hard_limit", type=float, default=HARD_LIMIT_S_DEFAULT, help="正式阶段硬上限（秒）")
    ap.add_argument("--windowed", action="store_true", help="窗口模式（仅用于电脑调试）")

    # 如果你发现 y_norm 上下颠倒，加这个（y_norm=0在下、1在上）
    ap.add_argument("--y_origin_bottom", action="store_true", help="若 y_norm 是 0=下 1=上，启用此项")

    # 节点直径：<=0 表示自动（取 min(layout, NODE_DIAMETER_PX_AUTO)）
    ap.add_argument("--node_diam", type=int, default=0, help="渲染用节点直径(px)。0=自动（默认更适中）")
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()
    layout_id = args.layout if args.layout in (1, 2, 3) else pick_layout_id(args.subject)

    run_a0(
        subject_id=args.subject,
        session_id=args.session,
        age=args.age,
        layout_id=layout_id,
        hard_limit_s=float(args.hard_limit),
        windowed=bool(args.windowed),
        y_origin_top=(not args.y_origin_bottom),
        node_diam_override=int(args.node_diam)
    )

    # 作为脚本运行时，退出 PsychoPy
    core.quit()