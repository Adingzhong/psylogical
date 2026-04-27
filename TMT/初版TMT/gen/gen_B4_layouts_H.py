from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

Pt = Tuple[float, float]
Seg = Tuple[Pt, Pt]


# =========================
# ✅ 你通常只改这里
# =========================
N = 6
VERSION = "N6_v1"
STYLE = "color"  # B4 固定 color

CANVAS_W = 1400
CANVAS_H = 1000
MARGIN_PX = 90

# 节点直径（尽量与你 A1 一致）
NODE_DIAM_PX = 200

# 三套布局固定种子
SEEDS = {1: 510031, 2: 830117, 3: 120019}

# 你要求：layout1/3 起点苹果；layout2 起点柠檬
START_FRUIT_A = {1: "apple", 2: "lemon", 3: "apple"}
OTHER_FRUIT = {"apple": "lemon", "lemon": "apple"}

# “全屏分散”用的网格（越大越分散，但也更难）
GRID_COLS = 5
GRID_ROWS = 4


# =========================
# ✅ 搜索控制：不会卡死
# =========================
BEAM_WIDTH = 26                  # 束宽（越大越稳，但更慢）
CANDIDATES_PER_STATE = 26        # 每个状态扩展多少候选点
RESTARTS_PER_PROFILE = 140       # 每档重启次数上限
MAX_SECONDS_PER_PROFILE = 10.0   # 每档最多跑多久
MAX_SECONDS_PER_LAYOUT = 32.0    # 单个 layout 总上限（防卡死）


# =========================
# 约束档位：从严到松（必要时自动降档）
# =========================
@dataclass(frozen=True)
class Constraints:
    name: str
    min_center_mult: float
    min_step_frac: float
    long_step_frac: float
    min_long_ratio: float
    min_cover_w: float
    min_cover_h: float
    max_abs_corr: float
    min_quad_switches: int
    avoid_line_mult: float              # 线段到“非端点节点”的最小距离（以直径倍数计）
    avoid_node_to_oldseg_mult: float    # 新节点到旧线段最小距离
    min_norm_dist_from_b3: float        # 与B3的平均归一化距离阈值（避免完全一致）

PROFILES: List[Constraints] = [
    Constraints("strict",   1.18, 0.24, 0.36, 0.42, 0.78, 0.58, 0.62, 7, 0.58, 0.58, 0.030),
    Constraints("mid",      1.14, 0.22, 0.35, 0.38, 0.75, 0.55, 0.66, 6, 0.56, 0.56, 0.025),
    Constraints("easy",     1.12, 0.20, 0.34, 0.34, 0.72, 0.52, 0.70, 5, 0.54, 0.54, 0.020),
    Constraints("fallback", 1.10, 0.18, 0.33, 0.28, 0.70, 0.50, 0.78, 4, 0.50, 0.50, 0.000),
]


# =========================
# 工具函数
# =========================
def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v

def dist(a: Pt, b: Pt) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])

def pearson_corr(xs: List[float], ys: List[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx < 1e-9 or deny < 1e-9:
        return 0.0
    return num / (denx * deny)

def bbox_cover_ratio(pts: List[Pt]) -> Tuple[float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    usable_w = CANVAS_W - 2 * MARGIN_PX
    usable_h = CANVAS_H - 2 * MARGIN_PX
    return (maxx - minx) / max(1.0, usable_w), (maxy - miny) / max(1.0, usable_h)

def quadrant(p: Pt) -> int:
    cx, cy = CANVAS_W / 2.0, CANVAS_H / 2.0
    x, y = p
    return (1 if x >= cx else 0) + (2 if y >= cy else 0)  # 0..3

def quadrant_switches(pts: List[Pt]) -> int:
    qs = [quadrant(p) for p in pts]
    return sum(1 for i in range(len(qs) - 1) if qs[i] != qs[i + 1])

def point_to_segment_distance(p: Pt, a: Pt, b: Pt) -> float:
    ax, ay = a
    bx, by = b
    px, py = p
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    vv = vx * vx + vy * vy
    if vv <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = (wx * vx + wy * vy) / vv
    t = clamp(t, 0.0, 1.0)
    cx, cy = ax + t * vx, ay + t * vy
    return math.hypot(px - cx, py - cy)

def _orient(a: Pt, b: Pt, c: Pt) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

def _on_segment(a: Pt, b: Pt, c: Pt) -> bool:
    return (
        min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9
        and min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9
    )

def segments_intersect(s1: Seg, s2: Seg) -> bool:
    (a, b) = s1
    (c, d) = s2
    o1 = _orient(a, b, c)
    o2 = _orient(a, b, d)
    o3 = _orient(c, d, a)
    o4 = _orient(c, d, b)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True
    if abs(o1) < 1e-9 and _on_segment(a, b, c):
        return True
    if abs(o2) < 1e-9 and _on_segment(a, b, d):
        return True
    if abs(o3) < 1e-9 and _on_segment(c, d, a):
        return True
    if abs(o4) < 1e-9 and _on_segment(c, d, b):
        return True
    return False

def mean_norm_distance(a: List[Pt], b: List[Pt]) -> float:
    if len(a) != len(b):
        return 1.0
    ds = []
    for (ax, ay), (bx, by) in zip(a, b):
        dx = (ax - bx) / CANVAS_W
        dy = (ay - by) / CANVAS_H
        ds.append(math.hypot(dx, dy))
    return sum(ds) / max(1, len(ds))


# =========================
# 网格采样（鼓励铺满屏幕）
# =========================
@dataclass(frozen=True)
class Cell:
    x0: float
    x1: float
    y0: float
    y1: float

def build_cells() -> List[Cell]:
    usable_w = CANVAS_W - 2 * MARGIN_PX
    usable_h = CANVAS_H - 2 * MARGIN_PX
    cells: List[Cell] = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            x0 = MARGIN_PX + usable_w * (c / GRID_COLS)
            x1 = MARGIN_PX + usable_w * ((c + 1) / GRID_COLS)
            y0 = MARGIN_PX + usable_h * (r / GRID_ROWS)
            y1 = MARGIN_PX + usable_h * ((r + 1) / GRID_ROWS)
            cells.append(Cell(x0, x1, y0, y1))
    return cells

CELLS = build_cells()
GRID_N = GRID_COLS * GRID_ROWS

def choose_cell(rng: random.Random, used_counts: Dict[int, int]) -> int:
    arr = [(used_counts.get(i, 0), i) for i in range(GRID_N)]
    arr.sort()
    top = [i for _, i in arr[:min(10, len(arr))]]
    return rng.choice(top)

def sample_in_cell(rng: random.Random, cid: int) -> Pt:
    c = CELLS[cid]
    pad = 0.14
    x = rng.uniform(c.x0 + (c.x1 - c.x0) * pad, c.x1 - (c.x1 - c.x0) * pad)
    y = rng.uniform(c.y0 + (c.y1 - c.y0) * pad, c.y1 - (c.y1 - c.y0) * pad)
    return (x, y)


# =========================
# 冲突/干扰强度（B4-L vs B4-H）
# =========================
def _angle_deg(v1: Pt, v2: Pt) -> float:
    x1, y1 = v1
    x2, y2 = v2
    n1 = math.hypot(x1, y1)
    n2 = math.hypot(x2, y2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 180.0
    c = clamp((x1 * x2 + y1 * y2) / (n1 * n2), -1.0, 1.0)
    return math.degrees(math.acos(c))

def conflict_stats_for_b4(pts: List[Pt]) -> Dict[str, float]:
    m = len(pts)
    ratios = []
    hi = 0
    lo = 0
    for cur_step in range(1, m):  # 1..m-1
        nxt_step = cur_step + 1
        if nxt_step > m:
            break
        comp_step = nxt_step - 1 if nxt_step % 2 == 0 else nxt_step + 1
        if comp_step < 1 or comp_step > m:
            continue

        cur = pts[cur_step - 1]
        cor = pts[nxt_step - 1]
        com = pts[comp_step - 1]

        d_cor = dist(cur, cor)
        d_com = dist(cur, com)
        if d_cor < 1e-6:
            continue
        ratio = d_com / d_cor
        ratios.append(ratio)

        v_cor = (cor[0] - cur[0], cor[1] - cur[1])
        v_com = (com[0] - cur[0], com[1] - cur[1])
        ang = _angle_deg(v_cor, v_com)

        if (ratio <= 0.90) and (ang <= 25.0):
            hi += 1
        if (ratio >= 1.20) and (ang >= 35.0):
            lo += 1

    mean_ratio = float(sum(ratios) / max(1, len(ratios)))
    return {"mean_ratio_comp_over_correct": mean_ratio, "hi_conflict_steps": float(hi), "lo_safe_steps": float(lo)}

