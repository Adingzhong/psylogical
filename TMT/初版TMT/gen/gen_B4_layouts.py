# -*- coding: utf-8 -*-
"""
gen_B4_layouts.py (anti-regularity + enforce uniqueness)
B4：彩色水果交替（规则同B3）：A1 -> B1 -> A2 -> B2 ... -> A(N)
N=6 => M=11

输出：
  layouts/B4/N6_v1_layout1~3.json
  layouts/B4/_previews/N6_v1_layout*_stim.png
  layouts/B4/_previews/N6_v1_layout*_dev.png

关键修复：
- 反规律：长跳比例、象限切换、去相关、减少“下一点是近邻”
- 三张唯一性：layout2/3 与已有布局“太像”就自动重生成（seed jitter + profile downgrade）
- B4 layoutk 默认参照 B3 layoutk（避免三张同质化）
"""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

TASK = "B4"
N = 6
M = 2 * N - 1
VERSION = "N6_v1"
STYLE = "color"

NODE_DIAM_PX = 170

CANVAS_W = 1400
CANVAS_H = 1000
MARGIN_PX = 80

SEEDS = {1: 510031, 2: 830117, 3: 120019}

# 稳健性
SEED_JITTER_MAX = 160
GLOBAL_TIME_LIMIT_S = 28.0
ENGINE_A_TRIES_SCALE = 1.0
ENGINE_B_TRIES = 5600

# 三张不许一样：若与已有布局平均点位距离过小，则判为“太像”
MIN_MEAN_POINT_DIST_PX = 90.0

Pt = Tuple[float, float]
Seg = Tuple[Pt, Pt]


@dataclass(frozen=True)
class Profile:
    name: str
    # 基本几何
    min_center_mult: float
    min_step_frac: float
    max_step_frac: float
    avoid_line_mult: float
    cover_w_min: float
    cover_h_min: float
    max_edge_points: int

    # 反规律
    long_step_frac: float
    min_long_ratio: float
    min_quad_switches: int
    max_abs_rank_corr: float
    max_near_neighbor_ratio: float

    triesA: int


PROFILES: List[Profile] = [
    Profile("strict",
            1.35, 0.28, 0.98, 0.62, 0.78, 0.62, 4,
            0.40, 0.45, 5, 0.62, 0.55,
            2600),
    Profile("mid",
            1.28, 0.25, 0.98, 0.58, 0.74, 0.58, 5,
            0.36, 0.40, 4, 0.68, 0.60,
            3000),
    Profile("easy",
            1.20, 0.22, 0.98, 0.54, 0.70, 0.54, 6,
            0.32, 0.34, 3, 0.75, 0.68,
            4200),
    Profile("fallback",
            1.10, 0.16, 0.98, 0.44, 0.62, 0.48, 9,
            0.26, 0.26, 2, 0.85, 0.78,
            6500),
]


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def dist(a: Pt, b: Pt) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def mean_point_dist(a: List[Pt], b: List[Pt]) -> float:
    # 同序点位平均距离（用于判“是否太像”）
    n = min(len(a), len(b))
    if n == 0:
        return 1e9
    return sum(dist(a[i], b[i]) for i in range(n)) / n


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


def path_segments(pts: List[Pt]) -> List[Seg]:
    return [((pts[i][0], pts[i][1]), (pts[i + 1][0], pts[i + 1][1])) for i in range(len(pts) - 1)]


def no_self_intersections(pts: List[Pt]) -> bool:
    segs = path_segments(pts)
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if abs(i - j) <= 1:
                continue
            if segments_intersect(segs[i], segs[j]):
                return False
    return True


def avoids_line_through_nodes(pts: List[Pt], avoid_dist: float) -> bool:
    segs = path_segments(pts)
    for i, (a, b) in enumerate(segs):
        for j, p in enumerate(pts):
            if j == i or j == i + 1:
                continue
            if point_to_segment_distance(p, a, b) < avoid_dist:
                return False
    return True


def bbox_cover_ratio(pts: List[Pt]) -> Tuple[float, float]:
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    usable_w = CANVAS_W - 2 * MARGIN_PX
    usable_h = CANVAS_H - 2 * MARGIN_PX
    return (maxx - minx) / max(1.0, usable_w), (maxy - miny) / max(1.0, usable_h)


def count_edge_points(pts: List[Pt], edge_band_norm: float = 0.12) -> int:
    bandx = edge_band_norm * CANVAS_W
    bandy = edge_band_norm * CANVAS_H
    return sum(
        1 for (x, y) in pts
        if (x <= bandx or x >= CANVAS_W - bandx or y <= bandy or y >= CANVAS_H - bandy)
    )


def _rankdata(vals: List[float]) -> List[int]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    rank = [0] * len(vals)
    for r, idx in enumerate(order):
        rank[idx] = r
    return rank


def _spearman_abs(rank_a: List[int], rank_b: List[int]) -> float:
    n = len(rank_a)
    if n <= 1:
        return 0.0
    da = [rank_a[i] - (n - 1) / 2 for i in range(n)]
    db = [rank_b[i] - (n - 1) / 2 for i in range(n)]
    num = sum(da[i] * db[i] for i in range(n))
    den1 = math.sqrt(sum(x * x for x in da))
    den2 = math.sqrt(sum(x * x for x in db))
    if den1 < 1e-9 or den2 < 1e-9:
        return 0.0
    return abs(num / (den1 * den2))


def rank_correlations(pts: List[Pt]) -> Tuple[float, float]:
    step_rank = list(range(len(pts)))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    rx = _rankdata(xs)
    ry = _rankdata(ys)
    return _spearman_abs(step_rank, rx), _spearman_abs(step_rank, ry)


def quad_switches(pts: List[Pt]) -> int:
    cx = CANVAS_W / 2
    cy = CANVAS_H / 2

    def q(p: Pt) -> int:
        x, y = p
        return (0 if x < cx else 1) + (0 if y < cy else 2)

    qs = [q(p) for p in pts]
    return sum(1 for i in range(len(qs) - 1) if qs[i] != qs[i + 1])


def long_ratio(pts: List[Pt], long_step: float) -> float:
    if len(pts) < 2:
        return 0.0
    segs = [dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    return sum(1 for s in segs if s >= long_step) / len(segs)


def near_neighbor_ratio(pts: List[Pt], k: int = 3) -> float:
    if len(pts) < 2:
        return 0.0
    hits = 0
    for i in range(len(pts) - 1):
        cur = pts[i]
        nxt = pts[i + 1]
        dists = []
        for j in range(len(pts)):
            if j == i:
                continue
            dists.append(dist(cur, pts[j]))
        dists.sort()
        dn = dist(cur, nxt)
        thresh = dists[min(k - 1, len(dists) - 1)] + 1e-6
        if dn <= thresh:
            hits += 1
    return hits / (len(pts) - 1)


def is_valid(pts: List[Pt], prof: Profile) -> Optional[Dict[str, float]]:
    min_dim = min(CANVAS_W, CANVAS_H)
    max_dim = math.hypot(CANVAS_W, CANVAS_H)

    min_center = NODE_DIAM_PX * prof.min_center_mult
    min_step = min_dim * prof.min_step_frac
    max_step = max_dim * prof.max_step_frac
    avoid = NODE_DIAM_PX * prof.avoid_line_mult

    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if dist(pts[i], pts[j]) < min_center:
                return None

    seglens = []
    for i in range(len(pts) - 1):
        s = dist(pts[i], pts[i + 1])
        if s < min_step or s > max_step:
            return None
        seglens.append(s)

    cw, ch = bbox_cover_ratio(pts)
    if cw < prof.cover_w_min or ch < prof.cover_h_min:
        return None

    if count_edge_points(pts) > prof.max_edge_points:
        return None

    if not no_self_intersections(pts):
        return None

    if not avoids_line_through_nodes(pts, avoid):
        return None

    long_step = prof.long_step_frac * min_dim
    lr = long_ratio(pts, long_step=long_step)
    if lr < prof.min_long_ratio:
        return None

    qs = quad_switches(pts)
    if qs < prof.min_quad_switches:
        return None

    cx, cy = rank_correlations(pts)
    if max(cx, cy) > prof.max_abs_rank_corr:
        return None

    nnr = near_neighbor_ratio(pts, k=3)
    if nnr > prof.max_near_neighbor_ratio:
        return None

    mean_s = sum(seglens) / max(1, len(seglens))
    std_s = math.sqrt(sum((s - mean_s) ** 2 for s in seglens) / max(1, len(seglens)))

    return {
        "cover_w": float(cw),
        "cover_h": float(ch),
        "long_ratio": float(lr),
        "quad_switches": float(qs),
        "corr_x": float(cx),
        "corr_y": float(cy),
        "near_neighbor_ratio": float(nnr),
        "mean_step": float(mean_s),
        "cv_step": float(std_s / max(1e-6, mean_s)),
    }


def score_layout(metrics: Dict[str, float], mean_dist_from_b3: float, mean_dist_from_prev: float) -> float:
    return (
        16.0 * min(metrics["cover_w"], metrics["cover_h"])
        + 5.2 * metrics["long_ratio"]
        + 0.40 * metrics["quad_switches"]
        + 1.0 * metrics["cv_step"]
        + 1.2 * mean_dist_from_b3
        + 1.8 * mean_dist_from_prev
        - 2.2 * (metrics["corr_x"] + metrics["corr_y"])
        - 3.2 * metrics["near_neighbor_ratio"]
    )


GRID_COLS = 4
GRID_ROWS = 3
GRID_N = GRID_COLS * GRID_ROWS


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


def sample_point_in_cell(rng: random.Random, cid: int) -> Pt:
    c = CELLS[cid]
    pad = 0.14
    x = rng.uniform(c.x0 + (c.x1 - c.x0) * pad, c.x1 - (c.x1 - c.x0) * pad)
    y = rng.uniform(c.y0 + (c.y1 - c.y0) * pad, c.y1 - (c.y1 - c.y0) * pad)
    return (x, y)


def engineA_generate(
    rng: random.Random,
    prof: Profile,
    b3_pts: Optional[List[Pt]],
    prev_pts_list: List[List[Pt]],
) -> Optional[Tuple[List[Pt], Dict[str, float], float, float]]:
    min_center = NODE_DIAM_PX * prof.min_center_mult
    tries = int(prof.triesA * ENGINE_A_TRIES_SCALE)

    best_pts = None
    best_sc = -1e18
    best_metrics = None
    best_db3 = 0.0
    best_dprev = 0.0

    for _ in range(tries):
        cell_seq = [rng.randrange(0, GRID_N) for _ in range(M)]
        pts: List[Pt] = []
        ok = True
        for cid in cell_seq:
            placed = False
            for _k in range(220):
                p = sample_point_in_cell(rng, cid)
                if all(dist(p, q) >= min_center for q in pts):
                    pts.append(p)
                    placed = True
                    break
            if not placed:
                ok = False
                break
        if not ok:
            continue

        metrics = is_valid(pts, prof)
        if metrics is None:
            continue

        db3 = 0.0
        if b3_pts is not None:
            db3 = mean_point_dist(pts, b3_pts)

        dprev = 0.0
        if prev_pts_list:
            dprev = min(mean_point_dist(pts, p) for p in prev_pts_list)

        sc = score_layout(metrics, mean_dist_from_b3=db3, mean_dist_from_prev=dprev)
        if sc > best_sc:
            best_sc = sc
            best_pts = pts
            best_metrics = metrics
            best_db3 = db3
            best_dprev = dprev

    if best_pts is None:
        return None
    return best_pts, best_metrics, best_db3, best_dprev  # type: ignore


def random_point(rng: random.Random) -> Pt:
    x = rng.uniform(MARGIN_PX, CANVAS_W - MARGIN_PX)
    y = rng.uniform(MARGIN_PX, CANVAS_H - MARGIN_PX)
    return (x, y)


def poisson_points(rng: random.Random, min_center: float) -> Optional[List[Pt]]:
    pts: List[Pt] = []
    for _ in range(12000):
        p = random_point(rng)
        if all(dist(p, q) >= min_center for q in pts):
            pts.append(p)
            if len(pts) >= M:
                return pts[:M]
    return None


def reorder_try_many(
    rng: random.Random,
    point_set: List[Pt],
    prof: Profile,
    b3_pts: Optional[List[Pt]],
    prev_pts_list: List[List[Pt]],
) -> Optional[Tuple[List[Pt], Dict[str, float], float, float]]:
    best_pts = None
    best_sc = -1e18
    best_metrics = None
    best_db3 = 0.0
    best_dprev = 0.0

    for _ in range(520):
        pts = point_set[:]
        rng.shuffle(pts)
        for _k in range(28):
            i = rng.randrange(0, M - 1)
            pts[i], pts[i + 1] = pts[i + 1], pts[i]

        metrics = is_valid(pts, prof)
        if metrics is None:
            continue

        db3 = 0.0
        if b3_pts is not None:
            db3 = mean_point_dist(pts, b3_pts)

        dprev = 0.0
        if prev_pts_list:
            dprev = min(mean_point_dist(pts, p) for p in prev_pts_list)

        sc = score_layout(metrics, mean_dist_from_b3=db3, mean_dist_from_prev=dprev)
        if sc > best_sc:
            best_sc = sc
            best_pts = pts
            best_metrics = metrics
            best_db3 = db3
            best_dprev = dprev

    if best_pts is None:
        return None
    return best_pts, best_metrics, best_db3, best_dprev  # type: ignore


def engineB_generate(
    rng: random.Random,
    prof: Profile,
    b3_pts: Optional[List[Pt]],
    prev_pts_list: List[List[Pt]],
) -> Optional[Tuple[List[Pt], Dict[str, float], float, float]]:
    min_center = NODE_DIAM_PX * prof.min_center_mult

    best_pts = None
    best_sc = -1e18
    best_metrics = None
    best_db3 = 0.0
    best_dprev = 0.0

    for _ in range(ENGINE_B_TRIES):
        ps = poisson_points(rng, min_center=min_center)
        if ps is None:
            continue
        ret = reorder_try_many(rng, ps, prof, b3_pts, prev_pts_list)
        if ret is None:
            continue
        pts, metrics, db3, dprev = ret
        sc = score_layout(metrics, mean_dist_from_b3=db3, mean_dist_from_prev=dprev)
        if sc > best_sc:
            best_sc = sc
            best_pts = pts
            best_metrics = metrics
            best_db3 = db3
            best_dprev = dprev

        if best_metrics is not None and best_metrics["near_neighbor_ratio"] < 0.58 and min(best_metrics["cover_w"], best_metrics["cover_h"]) > 0.74:
            break

    if best_pts is None:
        return None
    return best_pts, best_metrics, best_db3, best_dprev  # type: ignore


def generate_best_layout(
    seed0: int,
    b3_pts: Optional[List[Pt]],
    prev_pts_list: List[List[Pt]],
) -> Tuple[List[Pt], Dict[str, float], bool]:
    t0 = time.perf_counter()
    best_any: Optional[Tuple[List[Pt], Dict[str, float], bool, float]] = None

    for jitter in range(SEED_JITTER_MAX + 1):
        if (time.perf_counter() - t0) > GLOBAL_TIME_LIMIT_S:
            break
        seed = seed0 + jitter

        for pi, prof in enumerate(PROFILES):
            if (time.perf_counter() - t0) > GLOBAL_TIME_LIMIT_S:
                break

            rng = random.Random(seed)
            ret = engineA_generate(rng, prof, b3_pts, prev_pts_list)
            used_engine = "A"

            if ret is None:
                rng = random.Random(seed * 131 + 17)
                ret = engineB_generate(rng, prof, b3_pts, prev_pts_list)
                used_engine = "B"

            if ret is None:
                continue

            pts, metrics, db3, dprev = ret
            sc = score_layout(metrics, mean_dist_from_b3=db3, mean_dist_from_prev=dprev)
            degraded = (pi > 0) or (jitter > 0)

            out_metrics = dict(metrics)
            out_metrics.update({
                "profile": prof.name,
                "engine": used_engine,
                "seed_used": seed,
                "seed_base": seed0,
                "seed_jitter": jitter,
                "node_diam_px": float(NODE_DIAM_PX),
                "score": float(sc),
                "mean_dist_from_b3": float(db3),
                "mean_dist_from_prev": float(dprev),
            })

            # 额外：如果与已有 B4 布局太像，则直接丢弃（强制三张不一致）
            if prev_pts_list:
                if min(mean_point_dist(pts, p) for p in prev_pts_list) < MIN_MEAN_POINT_DIST_PX:
                    continue

            if prof.name == "strict" and jitter == 0:
                return pts, out_metrics, degraded

            if best_any is None or sc > best_any[3]:
                best_any = (pts, out_metrics, degraded, sc)

            if prof.name in ("strict", "mid") and out_metrics["near_neighbor_ratio"] < 0.60:
                return pts, out_metrics, degraded

    if best_any is not None:
        return best_any[0], best_any[1], best_any[2]

    rng = random.Random(seed0 + 99991)
    pts = [(rng.uniform(MARGIN_PX, CANVAS_W - MARGIN_PX), rng.uniform(MARGIN_PX, CANVAS_H - MARGIN_PX)) for _ in range(M)]
    metrics = {"profile": "emergency", "engine": "E", "seed_used": seed0 + 99991, "node_diam_px": float(NODE_DIAM_PX)}
    return pts, metrics, True


def resolve_root() -> Path:
    here = Path(__file__).resolve().parent
    for p in [here] + list(here.parents):
        if (p / "layouts").exists() and (p / "stimuli").exists():
            return p
    return here


def stim_filename(fruit: str, style: str, num: int) -> str:
    return f"{fruit}_{style}_{num}.png"


def load_stim_img(stim_root: Path, fruit: str, style: str, num: int) -> Image.Image:
    p1 = stim_root / style / stim_filename(fruit, style, num)
    p2 = stim_root / style / f"{fruit}_{style}_{num:02d}.png"
    if p1.exists():
        return Image.open(p1).convert("RGBA")
    if p2.exists():
        return Image.open(p2).convert("RGBA")
    raise FileNotFoundError(f"缺少刺激图片：{p1} / {p2}")


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

    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.text((14, 10), title, fill=(30, 30, 30, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")


def write_json(out_path: Path, pts: List[Pt], fruit_a: str, fruit_b: str, metrics: Dict[str, float], degraded: bool) -> None:
    nodes = []
    for step in range(1, M + 1):
        if step % 2 == 1:
            fruit = fruit_a
            num = (step + 1) // 2
        else:
            fruit = fruit_b
            num = step // 2

        x_px, y_px = pts[step - 1]
        nodes.append({
            "node_id": step,
            "step": step,
            "fruit": fruit,
            "num": num,
            "style": STYLE,
            "stim_rel": f"stimuli/fruits/numbered/{STYLE}/{stim_filename(fruit, STYLE, num)}",
            "x_norm": x_px / CANVAS_W,
            "y_norm": y_px / CANVAS_H,
            "x_px": x_px,
            "y_px": y_px,
        })

    payload = {
        "task": TASK,
        "version": VERSION,
        "N": N,
        "M": M,
        "style": STYLE,
        "fruitA": fruit_a,
        "fruitB": fruit_b,
        "canvas_px": {"w": CANVAS_W, "h": CANVAS_H},
        "node_diam_px": NODE_DIAM_PX,
        "path_node_ids": list(range(1, M + 1)),
        "degraded": bool(degraded),
        "metrics": metrics,
        "nodes": nodes,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_b3_pts(root: Path, lid: int) -> Optional[List[Pt]]:
    # 默认让 B4 layoutk 对齐参考 B3 layoutk（避免三张趋同）
    p = root / "layouts" / "B3" / f"{VERSION}_layout{lid}.json"
    if not p.exists():
        return None
    obj = json.loads(p.read_text(encoding="utf-8"))
    pts = [(float(n["x_px"]), float(n["y_px"])) for n in obj["nodes"]]
    if len(pts) == M:
        return pts
    return None


def main() -> None:
    root = resolve_root()
    layout_dir = root / "layouts" / "B4"
    preview_dir = layout_dir / "_previews"
    stim_root = root / "stimuli" / "fruits" / "numbered"

    if not (stim_root / STYLE).exists():
        raise FileNotFoundError(f"找不到刺激目录：{stim_root / STYLE}")

    prev_pts_list: List[List[Pt]] = []

    for lid in (1, 2, 3):
        seed0 = SEEDS[lid]
        fruit_a = "apple"   # B4 一律用 apple/lemon（如你项目里不同，可改）
        fruit_b = "lemon"

        b3_pts = load_b3_pts(root, lid)

        pts, metrics, degraded = generate_best_layout(seed0, b3_pts=b3_pts, prev_pts_list=prev_pts_list)

        # 再次保险：如果还是太像，则继续加 jitter（极少发生）
        guard = 0
        while prev_pts_list and min(mean_point_dist(pts, p) for p in prev_pts_list) < MIN_MEAN_POINT_DIST_PX and guard < 6:
            guard += 1
            pts, metrics, degraded = generate_best_layout(seed0 + guard * 997, b3_pts=b3_pts, prev_pts_list=prev_pts_list)

        prev_pts_list.append(pts)

        node_imgs: List[Image.Image] = []
        for step in range(1, M + 1):
            if step % 2 == 1:
                fruit = fruit_a
                num = (step + 1) // 2
            else:
                fruit = fruit_b
                num = step // 2
            node_imgs.append(load_stim_img(stim_root, fruit, STYLE, num))

        json_path = layout_dir / f"{VERSION}_layout{lid}.json"
        write_json(json_path, pts, fruit_a, fruit_b, metrics, degraded)

        title = (
            f"B4 {VERSION} layout{lid} node={NODE_DIAM_PX}px "
            f"profile={metrics.get('profile')} engine={metrics.get('engine')} "
            f"seed={metrics.get('seed_used')} jitter={metrics.get('seed_jitter')} "
            f"nnr={metrics.get('near_neighbor_ratio'):.2f} long={metrics.get('long_ratio'):.2f} "
            f"qs={metrics.get('quad_switches')} degraded={degraded}"
        )
        stim_png = preview_dir / f"{VERSION}_layout{lid}_stim.png"
        dev_png = preview_dir / f"{VERSION}_layout{lid}_dev.png"
        draw_preview(title, pts, node_imgs, stim_png, dev_lines=False)
        draw_preview(title, pts, node_imgs, dev_png, dev_lines=True)

        print(f"[OK] layout{lid} base_seed={seed0}")
        print(f"  profile={metrics.get('profile')} engine={metrics.get('engine')} degraded={degraded}")
        print(f"  seed_used={metrics.get('seed_used')} jitter={metrics.get('seed_jitter')}")
        print(f"  nnr={metrics.get('near_neighbor_ratio'):.3f} long={metrics.get('long_ratio'):.3f} qs={metrics.get('quad_switches')}")
        if prev_pts_list and len(prev_pts_list) >= 2:
            md = min(mean_point_dist(pts, p) for p in prev_pts_list[:-1])
            print(f"  min_mean_dist_from_prev={md:.2f}px (threshold={MIN_MEAN_POINT_DIST_PX}px)")
        print(f"  json: {json_path}")
        print(f"  stim: {stim_png}")
        print(f"  dev : {dev_png}")

    print("Done.")


if __name__ == "__main__":
    main()
