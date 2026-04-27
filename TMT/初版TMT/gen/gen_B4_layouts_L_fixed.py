# gen_B4_layouts_L.py
# B4 = 彩色水果交替（规则同B3）：A1 -> B1 -> A2 -> B2 ... -> A(N)
# N=6 => M=2*N-1=11
#
# 你的目录：
#   DTMT/stimuli/fruits/numbered/color/
# 输出：
#   DTMT/layouts/B4/N6_v1_layout1.json
#   DTMT/layouts/B4/N6_v1_layout2.json
#   DTMT/layouts/B4/N6_v1_layout3.json
#   DTMT/layouts/B4/_previews/N6_v1_layout*_stim.png (无红线)
#   DTMT/layouts/B4/_previews/N6_v1_layout*_dev.png  (有红线)

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
# 说明：B4-L 为“低冲突”布局，我们更希望生成成功且布局质量稳定。
# 你报错的原因就是：在你机器上（或当前随机种子/搜索路径下）约束+搜索预算不够。
# 这里把搜索预算拉高一点（仍然有上限，不会无限卡死）。
BEAM_WIDTH = 32                  # 束宽（越大越稳，但更慢）
CANDIDATES_PER_STATE = 32        # 每个状态扩展多少候选点
RESTARTS_PER_PROFILE = 220       # 每档重启次数上限
MAX_SECONDS_PER_PROFILE = 14.0   # 每档最多跑多久
MAX_SECONDS_PER_LAYOUT = 55.0    # 单个 layout 总上限（防卡死）


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
    # 优先挑“用得少”的格子 → 强制铺开
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
# B3 读取（避免布局一致）
# =========================
def load_layout_points_from_json(p: Path) -> Optional[List[Pt]]:
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        pts: List[Pt] = []
        for nd in data.get("nodes", []):
            if "x_px" in nd and "y_px" in nd:
                pts.append((float(nd["x_px"]), float(nd["y_px"])))
            elif "x_norm" in nd and "y_norm" in nd:
                pts.append((float(nd["x_norm"]) * CANVAS_W, float(nd["y_norm"]) * CANVAS_H))
            else:
                return None
        return pts
    except Exception:
        return None


# =========================
# 刺激文件查找（更鲁棒：不强依赖文件名必须带 _color_）
# =========================
def find_stim_path(stim_dir: Path, fruit: str, style: str, num: int) -> Path:
    # 优先常见命名
    cand = [
        stim_dir / style / f"{fruit}_{style}_{num}.png",  # apple_color_1.png
        stim_dir / style / f"{fruit}_{num}.png",          # apple_1.png
        stim_dir / style / f"{fruit}-{num}.png",          # apple-1.png
    ]
    for p in cand:
        if p.exists():
            return p

    # 兜底：宽松匹配（只要 fruit + num 在文件名里）
    folder = stim_dir / style
    hits = list(folder.glob(f"{fruit}*{num}*.png"))
    if hits:
        return hits[0]

    raise FileNotFoundError(f"缺少刺激：{fruit} {style} {num}（在 {folder} 下找不到）")


# =========================
# 约束检查（关键：新节点也要避开旧线段）
# =========================
def ok_min_center(p: Pt, pts: List[Pt], min_center: float) -> bool:
    return all(dist(p, q) >= min_center for q in pts)

def ok_new_segment_no_intersect(new_seg: Seg, segs: List[Seg]) -> bool:
    for s in segs:
        if segments_intersect(new_seg, s):
            return False
    return True

def ok_new_segment_avoid_nodes(new_seg: Seg, pts: List[Pt], prev_idx: int, avoid: float) -> bool:
    a, b = new_seg
    for i, p in enumerate(pts):
        if i == prev_idx:
            continue
        if point_to_segment_distance(p, a, b) < avoid:
            return False
    return True

def ok_new_point_avoid_old_segments(p: Pt, segs: List[Seg], avoid: float) -> bool:
    for (a, b) in segs:
        if point_to_segment_distance(p, a, b) < avoid:
            return False
    return True

def final_verify_no_line_through_any_node(pts: List[Pt], avoid: float) -> bool:
    m = len(pts)
    for i in range(m - 1):
        a, b = pts[i], pts[i + 1]
        for j in range(m):
            if j == i or j == i + 1:
                continue
            if point_to_segment_distance(pts[j], a, b) < avoid:
                return False
    return True



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
    """
    B4 节点编号规则：
      step 1=A1, step2=B1, step3=A2, step4=B2, ... , step(2N-1)=A(N)
    对每一次转移（current_step -> next_step）：
      - correct = next_step
      - competitor = 同 num 的另一种水果（next_step±1），若存在则计算竞争强度
    输出：
      mean_ratio = mean(d_comp / d_correct)（越小越“更容易被干扰吸走”）
      hi_conflict_steps = 满足 ratio<=0.90 且 angle<=25° 的步数
      lo_safe_steps = 满足 ratio>=1.20 且 angle>=35° 的步数
    """
    m = len(pts)
    ratios = []
    hi = 0
    lo = 0
    for cur_step in range(1, m):  # 1..m-1
        nxt_step = cur_step + 1
        if nxt_step > m:
            break
        # competitor step:
        if nxt_step % 2 == 0:
            comp_step = nxt_step - 1
        else:
            comp_step = nxt_step + 1
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
    min_ratio = float(min(ratios)) if ratios else 999.0
    return {
        "mean_ratio_comp_over_correct": mean_ratio,
        "min_ratio_comp_over_correct": min_ratio,
        "hi_conflict_steps": float(hi),
        "lo_safe_steps": float(lo),
        "ratio_samples": float(len(ratios)),
    }

def conflict_pass(pts: List[Pt], level: str) -> bool:
    cs = conflict_stats_for_b4(pts)
    # 经验阈值：N=6 时 ratio_samples≈10
    if level == "H":
        # 高干扰：至少 3 步是“竞争项更近且方向相似”
        return (cs["hi_conflict_steps"] >= 3.0) and (cs["mean_ratio_comp_over_correct"] <= 1.05)
    else:
        # 低干扰：尽量避免“竞争项更近且方向相似”的强冲突。
        # 但如果阈值卡得过死，生成会失败（你已经遇到）。
        # 因此这里采用“仍然明显低冲突，但更容易生成”的阈值：
        #   - 强冲突步数 <= 2
        #   - 平均距离比 >= 1.08（竞争项整体更远）
        return (cs["hi_conflict_steps"] <= 2.0) and (cs["mean_ratio_comp_over_correct"] >= 1.08)


# =========================
# 束搜索状态
# =========================
@dataclass
class State:
    pts: List[Pt]
    segs: List[Seg]
    used_cells: Dict[int, int]
    score: float

def heuristic_increment(p_new: Pt, prev: Pt, pts: List[Pt], used_cells: Dict[int, int], cid: int) -> float:
    # 距离更大、离其他点更远、换象限、使用新格子 => 加分
    s = 0.0
    step = dist(p_new, prev)
    s += 1.45 * step
    if pts:
        s += 0.75 * min(dist(p_new, q) for q in pts)
    if quadrant(p_new) != quadrant(prev):
        s += 170.0
    if used_cells.get(cid, 0) == 0:
        s += 120.0
    return s


def try_build_with_beam(rng: random.Random, m: int, c: Constraints, b3_pts: Optional[List[Pt]]) -> Optional[Tuple[List[Pt], Dict[str, float]]]:
    min_dim = min(CANVAS_W, CANVAS_H)

    min_center = NODE_DIAM_PX * c.min_center_mult
    min_step = min_dim * c.min_step_frac
    long_step = min_dim * c.long_step_frac

    avoid_line_to_node = NODE_DIAM_PX * c.avoid_line_mult
    avoid_node_to_oldseg = NODE_DIAM_PX * c.avoid_node_to_oldseg_mult

    # 起点：随机选一个“少用格子”
    used0: Dict[int, int] = {}
    cid0 = choose_cell(rng, used0)
    p0 = sample_in_cell(rng, cid0)
    used0[cid0] = 1

    beam: List[State] = [State(pts=[p0], segs=[], used_cells=used0, score=0.0)]

    for step_idx in range(1, m):
        new_beam: List[State] = []
        for st in beam:
            prev = st.pts[-1]
            prev_idx = len(st.pts) - 1

            # 生成候选
            cand_list: List[Tuple[float, Pt, int]] = []
            for _ in range(CANDIDATES_PER_STATE * 3):
                cid = choose_cell(rng, st.used_cells)
                p = sample_in_cell(rng, cid)

                if not ok_min_center(p, st.pts, min_center):
                    continue
                if dist(p, prev) < min_step:
                    continue

                # ✅ 新点避开旧线段（修复你说的“线穿节点”常见来源）
                if st.segs and (not ok_new_point_avoid_old_segments(p, st.segs, avoid_node_to_oldseg)):
                    continue

                new_seg = (prev, p)

                # 不与旧线相交（忽略最后一段的相邻性：直接用 segs 全量也行，这里用 segs[:-1] 更稳）
                if st.segs:
                    if not ok_new_segment_no_intersect(new_seg, st.segs[:-1]):
                        continue

                # 新线段避开已放节点
                if not ok_new_segment_avoid_nodes(new_seg, st.pts, prev_idx=prev_idx, avoid=avoid_line_to_node):
                    continue

                inc = heuristic_increment(p, prev, st.pts, st.used_cells, cid)
                cand_list.append((inc, p, cid))

                if len(cand_list) >= CANDIDATES_PER_STATE:
                    break

            if not cand_list:
                continue

            cand_list.sort(key=lambda x: x[0], reverse=True)
            topk = cand_list[:min(CANDIDATES_PER_STATE, len(cand_list))]

            for inc, p, cid in topk:
                pts2 = st.pts + [p]
                segs2 = st.segs + [(prev, p)]
                used2 = dict(st.used_cells)
                used2[cid] = used2.get(cid, 0) + 1
                new_beam.append(State(pts=pts2, segs=segs2, used_cells=used2, score=st.score + inc))

        if not new_beam:
            return None

        # 保留束宽
        new_beam.sort(key=lambda s: s.score, reverse=True)
        beam = new_beam[:BEAM_WIDTH]

    # 终态验收：从 beam 里挑真正合格的
    best: Optional[Tuple[float, List[Pt], Dict[str, float]]] = None
    for st in beam:
        pts = st.pts
        cw, ch = bbox_cover_ratio(pts)
        if cw < c.min_cover_w or ch < c.min_cover_h:
            continue

        steps = [dist(pts[i], pts[i + 1]) for i in range(m - 1)]
        long_ratio = sum(1 for s in steps if s >= long_step) / max(1, len(steps))
        if long_ratio < c.min_long_ratio:
            continue

        idx = list(range(1, m + 1))
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        corrx = abs(pearson_corr(idx, xs))
        corry = abs(pearson_corr(idx, ys))
        if corrx > c.max_abs_corr or corry > c.max_abs_corr:
            continue

        qs = quadrant_switches(pts)
        if qs < c.min_quad_switches:
            continue

        # 兜底：所有线段不穿过任何非端点节点
        if not final_verify_no_line_through_any_node(pts, avoid=avoid_line_to_node):
            continue

        dn = 1.0
        if b3_pts is not None and c.min_norm_dist_from_b3 > 1e-12:
            dn = mean_norm_distance(pts, b3_pts)
            if dn < c.min_norm_dist_from_b3:
                continue
        # 冲突强度约束（B4_L / B4_H）
        if not conflict_pass(pts, "L"):
            continue


        # 最终评分（用于选最好的那个）
        score = 0.0
        score += 15.0 * min(cw, ch)
        score += 4.5 * long_ratio
        score += 0.35 * qs
        score += 1.8 * dn
        score -= 2.1 * (corrx + corry)

        metrics = {
            "conflict_level": "low",
            **conflict_stats_for_b4(pts),
            "profile": c.name,
            "cover_w": float(cw),
            "cover_h": float(ch),
            "long_ratio": float(long_ratio),
            "corr_x": float(corrx),
            "corr_y": float(corry),
            "quad_switches": float(qs),
            "mean_step": float(sum(steps) / max(1, len(steps))),
            "mean_norm_dist_from_b3": float(dn),
            "params": {
                "min_center_mult": c.min_center_mult,
                "min_step_frac": c.min_step_frac,
                "min_cover_w": c.min_cover_w,
                "min_cover_h": c.min_cover_h,
                "avoid_line_mult": c.avoid_line_mult,
                "avoid_node_to_oldseg_mult": c.avoid_node_to_oldseg_mult,
                "min_norm_dist_from_b3": c.min_norm_dist_from_b3,
            }
        }

        if best is None or score > best[0]:
            best = (score, pts, metrics)

    if best is None:
        return None
    return best[1], best[2]


def generate_layout(seed: int, m: int, b3_pts: Optional[List[Pt]]) -> Tuple[List[Pt], Dict[str, float], bool]:
    rng = random.Random(seed)
    t0 = time.perf_counter()

    best_any: Optional[Tuple[List[Pt], Dict[str, float], bool, float]] = None

    for pi, c in enumerate(PROFILES):
        prof_start = time.perf_counter()

        for _ in range(RESTARTS_PER_PROFILE):
            if (time.perf_counter() - prof_start) > MAX_SECONDS_PER_PROFILE:
                break
            if (time.perf_counter() - t0) > MAX_SECONDS_PER_LAYOUT:
                break

            # 轻微扰动，避免重复路径
            rng.random()

            ret = try_build_with_beam(rng=rng, m=m, c=c, b3_pts=b3_pts)
            if ret is None:
                continue
            pts, metrics = ret

            # 记录本档 / 全局最优
            final_score = (
                15.0 * min(metrics["cover_w"], metrics["cover_h"])
                + 4.5 * metrics["long_ratio"]
                + 0.35 * metrics["quad_switches"]
                + 1.8 * metrics["mean_norm_dist_from_b3"]
                - 2.1 * (metrics["corr_x"] + metrics["corr_y"])
            )
            degraded = (pi > 0)

            if best_any is None or final_score > best_any[3]:
                best_any = (pts, metrics, degraded, final_score)

            # 若非常好，直接返回
            if metrics["cover_w"] > max(0.80, c.min_cover_w + 0.02) and metrics["long_ratio"] > max(0.45, c.min_long_ratio + 0.05):
                return pts, metrics, degraded

        if (time.perf_counter() - t0) > MAX_SECONDS_PER_LAYOUT:
            break

    if best_any is not None:
        return best_any[0], best_any[1], best_any[2]

    raise RuntimeError(
        "B4 生成失败：在当前约束 + 时间上限下仍找不到布局。\n"
        "这不是颜色的问题，是『约束太强 + 搜索空间太小』。\n"
        "你可以把 MAX_SECONDS_PER_LAYOUT 提到 45 或把 BEAM_WIDTH 提到 32 再试。"
    )


# =========================
# 预览输出
# =========================
def draw_preview(title: str, pts: List[Pt], node_imgs: List[Image.Image], out_path: Path, dev_lines: bool) -> None:
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    if dev_lines:
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=(220, 40, 40, 255), width=6)

    d = NODE_DIAM_PX
    for (x, y), img in zip(pts, node_imgs):
        im = img.resize((d, d), resample=Image.LANCZOS)
        canvas.alpha_composite(im, (int(x - d / 2), int(y - d / 2)))

    draw.text((12, 10), title, fill=(40, 40, 40, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")


# =========================
# JSON 输出
# =========================
def write_json(out_path: Path, pts: List[Pt], fruit_a: str, fruit_b: str, style: str,
              stim_numbered_dir: Path, metrics: Dict[str, float], degraded: bool) -> None:
    m = len(pts)
    nodes = []

    for step in range(1, m + 1):
        if step % 2 == 1:
            fruit = fruit_a
            num = (step + 1) // 2
        else:
            fruit = fruit_b
            num = step // 2

        stim_abs = find_stim_path(stim_numbered_dir, fruit, style, num)
        stim_rel = str(stim_abs.relative_to(out_path.parents[2]))  # 相对 DTMT/

        x_px, y_px = pts[step - 1]
        nodes.append({
            "node_id": step,
            "step": step,
            "fruit": fruit,
            "num": num,
            "style": style,
            "stim_rel": stim_rel.replace("\\", "/"),
            "x_norm": x_px / CANVAS_W,
            "y_norm": y_px / CANVAS_H,
            "x_px": x_px,
            "y_px": y_px,
        })

    payload = {
        "task": "B4",
        "conflict_level": "l",
        "version": VERSION,
        "N": N,
        "M": m,
        "style": style,
        "fruitA": fruit_a,
        "fruitB": fruit_b,
        "canvas_px": {"w": CANVAS_W, "h": CANVAS_H},
        "node_diam_px": NODE_DIAM_PX,
        "path_node_ids": list(range(1, m + 1)),
        "degraded": degraded,
        "metrics": metrics,
        "nodes": nodes,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# =========================
# main
# =========================
def main() -> None:
    root = Path(__file__).resolve().parent  # DTMT/

    stim_numbered = root / "stimuli" / "fruits" / "numbered"
    color_dir = stim_numbered / STYLE
    if not color_dir.exists():
        raise FileNotFoundError(f"找不到目录：{color_dir}")

    layout_dir = root / "layouts" / "B4_L"
    preview_dir = layout_dir / "_previews"
    b3_dir = root / "layouts" / "B3"

    m = 2 * N - 1

    # 缓存图片
    cache: Dict[str, Image.Image] = {}

    def get_img(fruit: str, num: int) -> Image.Image:
        key = f"{fruit}_{STYLE}_{num}"
        if key not in cache:
            p = find_stim_path(stim_numbered, fruit, STYLE, num)
            cache[key] = Image.open(p).convert("RGBA")
        return cache[key]

    for lid in (1, 2, 3):
        seed = SEEDS[lid]
        fruit_a = START_FRUIT_A[lid]
        fruit_b = OTHER_FRUIT[fruit_a]

        # 读取 B3（若没有就不做“差异”约束）
        b3_json = b3_dir / f"{VERSION}_layout{lid}.json"
        b3_pts = load_layout_points_from_json(b3_json)

        pts, metrics, degraded = generate_layout(seed=seed, m=m, b3_pts=b3_pts)

        # 组装节点图片（按交替顺序）
        node_imgs: List[Image.Image] = []
        for step in range(1, m + 1):
            if step % 2 == 1:
                fruit = fruit_a
                num = (step + 1) // 2
            else:
                fruit = fruit_b
                num = step // 2
            node_imgs.append(get_img(fruit, num))

        json_path = layout_dir / f"{VERSION}_layout{lid}.json"
        write_json(json_path, pts, fruit_a, fruit_b, STYLE, stim_numbered, metrics, degraded)

        title = f"B4 {VERSION} (N={N}, M={m}) color layout{lid} start={fruit_a}"
        stim_png = preview_dir / f"{VERSION}_layout{lid}_stim.png"
        dev_png = preview_dir / f"{VERSION}_layout{lid}_dev.png"
        draw_preview(title, pts, node_imgs, stim_png, dev_lines=False)
        draw_preview(title, pts, node_imgs, dev_png, dev_lines=True)

        print(f"[OK] B4 layout{lid} start={fruit_a}  profile={metrics.get('profile')}  degraded={degraded}")
        print(f"  json:  {json_path}")
        print(f"  stim:  {stim_png}")
        print(f"  dev :  {dev_png}")
        print(f"  cover=({metrics.get('cover_w',0):.3f},{metrics.get('cover_h',0):.3f})  "
              f"long_ratio={metrics.get('long_ratio',0):.3f}  "
              f"corr=({metrics.get('corr_x',0):.3f},{metrics.get('corr_y',0):.3f})  "
              f"quad={metrics.get('quad_switches',0):.0f}  "
              f"distB3={metrics.get('mean_norm_dist_from_b3',0):.3f}")

    print("Done.")


if __name__ == "__main__":
    main()
