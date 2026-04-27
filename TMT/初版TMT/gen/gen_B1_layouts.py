
# -*- coding: utf-8 -*-

"""

gen_B1_layouts.py  (B1: 数-汉交替)  — 强制“相邻序列点不挨着”的生成器



N=6 表示数字到6；节点总数 M = 2*N-1 = 11

序列标签：1, 一, 2, 二, 3, 三, 4, 四, 5, 五, 6



输出：

DTMT/layouts/B1/N6_v1_layout{1..3}.json

DTMT/layouts/B1/_previews/N6_v1_layout{1..3}_stim.png

DTMT/layouts/B1/_previews/N6_v1_layout{1..3}_dev.png

"""



from __future__ import annotations

import json

import math

import random

from pathlib import Path

from typing import Dict, List, Tuple, Optional



from PIL import Image, ImageDraw, ImageFont





# ================== 你最常调的关键参数 ==================

W, H = 1536, 1152  # 4:3，空间更大更容易“散”



NODE_SIZE_PX = 165

R = NODE_SIZE_PX / 2.0

MARGIN_PX = 55



# 全屏散布要求

SPAN_X_MIN_PX = W * 0.72

SPAN_Y_MIN_PX = H * 0.60



# ✅ 关键：相邻序列点不要“挨着”

# 1) 连线段最短长度（越大越不挨着，但越难生成）

MIN_STEP_LEN_PX = 320  # 你若仍觉得“太近”，改 360/400



# 2) 相邻序列点不允许进入彼此的最近邻集合（K=2表示最近/次近都不行）

NEAR_NEIGHBOR_K = 2



# 点不重叠（别太夸张，否则 11 个点放不下）

MIN_CENTER_DIST_PX = NODE_SIZE_PX * 1.05



# 线段避开节点（可逐步放宽）

AVOID_LINE_FACTORS = [1.05, 0.95, 0.88, 0.80, 0.72, 0.65]  # *R



# 不规律（避免“从左到右一条龙”）

MAX_ABS_CORR = 0.78

MIN_DIR_CHANGES = 5

# ========================================================



TASK = "B1"

VERSION = "v1"



N = 6

M = 2 * N - 1  # 11



POINT_SAMPLE_TRIES = 6000

LAYOUT_TRIES = 650

PATH_BACKTRACK_LIMIT = 320000





# ================== 序列定义 ==================

HAN = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}



def build_sequence() -> Tuple[List[str], List[str], List[int]]:

    labels: List[str] = []

    kinds: List[str] = []

    values: List[int] = []

    for v in range(1, N + 1):

        labels.append(str(v)); kinds.append("digit"); values.append(v)

        if v < N:

            labels.append(HAN[v]); kinds.append("han"); values.append(v)

    return labels, kinds, values



LABELS, KINDS, VALUES = build_sequence()

assert len(LABELS) == M





# ================== 几何工具 ==================

def seg_intersect(a, b, c, d) -> bool:

    def orient(p, q, r):

        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])



    def on_seg(p, q, r):

        return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and

                min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))



    o1 = orient(a, b, c)

    o2 = orient(a, b, d)

    o3 = orient(c, d, a)

    o4 = orient(c, d, b)



    if (o1 * o2 < 0) and (o3 * o4 < 0):

        return True



    eps = 1e-9

    if abs(o1) < eps and on_seg(a, c, b): return True

    if abs(o2) < eps and on_seg(a, d, b): return True

    if abs(o3) < eps and on_seg(c, a, d): return True

    if abs(o4) < eps and on_seg(c, b, d): return True

    return False





def point_to_seg_dist(p, a, b) -> float:

    px, py = p

    ax, ay = a

    bx, by = b

    vx, vy = bx - ax, by - ay

    wx, wy = px - ax, py - ay

    vv = vx * vx + vy * vy

    if vv <= 1e-12:

        return math.hypot(px - ax, py - ay)

    t = (wx * vx + wy * vy) / vv

    t = max(0.0, min(1.0, t))

    cx, cy = ax + t * vx, ay + t * vy

    return math.hypot(px - cx, py - cy)





def pearson_corr(a: List[float], b: List[float]) -> float:

    n = len(a)

    if n < 2:

        return 0.0

    ma = sum(a) / n

    mb = sum(b) / n

    va = sum((x - ma) ** 2 for x in a)

    vb = sum((y - mb) ** 2 for y in b)

    if va <= 1e-12 or vb <= 1e-12:

        return 0.0

    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))

    return cov / math.sqrt(va * vb)





def count_dir_changes(seq: List[float]) -> int:

    if len(seq) < 3:

        return 0

    dif = [seq[i+1] - seq[i] for i in range(len(seq)-1)]

    sgn = []

    for d in dif:

        if abs(d) < 1e-6:

            sgn.append(0)

        else:

            sgn.append(1 if d > 0 else -1)

    changes = 0

    last = None

    for s in sgn:

        if s == 0:

            continue

        if last is None:

            last = s

        elif s != last:

            changes += 1

            last = s

    return changes





# ================== 字体（中文） ==================

def find_cn_font() -> Optional[Path]:

    root = Path(__file__).resolve().parent

    candidates = [

        root / "fonts" / "msyh.ttc",

        root / "fonts" / "msyh.ttf",

        root / "fonts" / "simhei.ttf",

        root / "fonts" / "simsun.ttc",

    ]

    win = Path(r"C:\\Windows\\Fonts")

    candidates += [

        win / "msyh.ttc",

        win / "msyh.ttf",

        win / "simhei.ttf",

        win / "simsun.ttc",

    ]

    for p in candidates:

        if p.exists():

            return p

    return None





def load_font(px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:

    fp = find_cn_font()

    if fp is not None:

        try:

            return ImageFont.truetype(str(fp), px)

        except Exception:

            pass

    return ImageFont.load_default()





# ================== 更分散的点集采样：Farthest-point ==================

def sample_points_spread(rng: random.Random) -> Optional[List[Tuple[float, float]]]:

    pts: List[Tuple[float, float]] = []

    xmin, xmax = MARGIN_PX + R, W - MARGIN_PX - R

    ymin, ymax = MARGIN_PX + R, H - MARGIN_PX - R



    K = 90



    for _ in range(M):

        best = None

        best_min_dist = -1.0



        for _k in range(K):

            x = rng.uniform(xmin, xmax)

            y = rng.uniform(ymin, ymax)

            if not pts:

                best = (x, y)

                best_min_dist = 1e9

                break



            mind = min(math.hypot(x - px, y - py) for (px, py) in pts)

            if mind > best_min_dist:

                best_min_dist = mind

                best = (x, y)



        if best is None:

            return None



        if pts:

            if min(math.hypot(best[0] - px, best[1] - py) for (px, py) in pts) < MIN_CENTER_DIST_PX:

                return None



        pts.append(best)



    xs = [p[0] for p in pts]

    ys = [p[1] for p in pts]

    if (max(xs) - min(xs)) < SPAN_X_MIN_PX:

        return None

    if (max(ys) - min(ys)) < SPAN_Y_MIN_PX:

        return None



    cols, rows = 3, 2

    occ = set()

    for (x, y) in pts:

        cx = min(cols - 1, int(cols * (x - xmin) / max(1.0, (xmax - xmin))))

        cy = min(rows - 1, int(rows * (y - ymin) / max(1.0, (ymax - ymin))))

        occ.add((cx, cy))

    if len(occ) < 5:

        return None



    return pts





# ================== 相邻点不能“挨着”的检查 ==================

def neighbors_k(pts: List[Tuple[float, float]], i: int) -> List[int]:

    di = []

    xi, yi = pts[i]

    for j in range(len(pts)):

        if j == i:

            continue

        xj, yj = pts[j]

        d = math.hypot(xj - xi, yj - yi)

        di.append((d, j))

    di.sort(key=lambda t: t[0])

    return [j for _, j in di[:NEAR_NEIGHBOR_K]]





def adjacent_not_near_enough(order: List[int], pts: List[Tuple[float, float]]) -> bool:

    """两条硬规则：

    1) 每个相邻序列点距离 >= MIN_STEP_LEN_PX

    2) 相邻序列点不允许是彼此的前K近邻

    """

    for t in range(len(order) - 1):

        a = order[t]

        b = order[t + 1]

        da = math.hypot(pts[a][0] - pts[b][0], pts[a][1] - pts[b][1])

        if da < MIN_STEP_LEN_PX:

            return False



        # b 不能是 a 的前K近邻，a 也不能是 b 的前K近邻

        if b in neighbors_k(pts, a):

            return False

        if a in neighbors_k(pts, b):

            return False



    return True





# ================== 路径搜索（回溯） ==================

def path_ok_add_segment(

    path: List[int],

    candidate: int,

    pts: List[Tuple[float, float]],

    avoid_line_px: float

) -> bool:

    if not path:

        return True



    a = pts[path[-1]]

    b = pts[candidate]



    # ✅ 新增：先卡“相邻太近”

    if math.hypot(a[0] - b[0], a[1] - b[1]) < MIN_STEP_LEN_PX:

        return False



    # 1) 与已有线段不自交

    for i in range(len(path) - 2):

        c = pts[path[i]]

        d = pts[path[i + 1]]

        if seg_intersect(a, b, c, d):

            return False



    # 2) 线段避开其它节点

    for k in range(len(pts)):

        if k == path[-1] or k == candidate:

            continue

        if point_to_seg_dist(pts[k], a, b) < avoid_line_px:

            return False



    return True





def find_non_intersecting_path(

    rng: random.Random,

    pts: List[Tuple[float, float]],

    avoid_line_px: float

) -> Optional[List[int]]:

    indices = list(range(M))

    rng.shuffle(indices)



    expanded = 0



    def backtrack(path: List[int], remaining: List[int]) -> Optional[List[int]]:

        nonlocal expanded

        expanded += 1

        if expanded > PATH_BACKTRACK_LIMIT:

            return None



        if not remaining:

            return path



        # ✅ 注意：不再“近邻优先”！改成更随机 + 偏向“长步长”

        cand = remaining[:]

        rng.shuffle(cand)



        if path:

            last = pts[path[-1]]

            # 优先尝试距离更远的点（避免 1 和 一贴一起）

            cand.sort(key=lambda i: -math.hypot(pts[i][0] - last[0], pts[i][1] - last[1]))



        for nxt in cand:

            if path and not path_ok_add_segment(path, nxt, pts, avoid_line_px):

                continue

            new_remaining = [x for x in remaining if x != nxt]

            res = backtrack(path + [nxt], new_remaining)

            if res is not None:

                return res

        return None



    for start in indices:

        remaining = [i for i in range(M) if i != start]

        res = backtrack([start], remaining)

        if res is not None:

            return res



    return None





def irregular_enough(ordered_pts: List[Tuple[float, float]]) -> bool:

    idx = list(range(1, M + 1))

    xs = [p[0] for p in ordered_pts]

    ys = [p[1] for p in ordered_pts]

    cx = pearson_corr(idx, xs)

    cy = pearson_corr(idx, ys)

    if abs(cx) > MAX_ABS_CORR or abs(cy) > MAX_ABS_CORR:

        return False

    ch = count_dir_changes(xs) + count_dir_changes(ys)

    if ch < MIN_DIR_CHANGES:

        return False

    return True





# ================== JSON / PNG 输出 ==================

def px_to_norm(p: Tuple[float, float]) -> Tuple[float, float]:

    return (p[0] / W, p[1] / H)





def build_json(layout_id: int, pts_ordered: List[Tuple[float, float]], used: Dict) -> Dict:

    nodes = []

    for i in range(M):

        xn, yn = px_to_norm(pts_ordered[i])

        nodes.append({

            "node_id": f"B1_{i+1:02d}",

            "k": i + 1,

            "label": LABELS[i],

            "value": VALUES[i],

            "kind": KINDS[i],

            "x_norm": round(xn, 6),

            "y_norm": round(yn, 6),

        })

    return {

        "task": TASK,

        "version": VERSION,

        "N": N,

        "M": M,

        "layout_id": layout_id,

        "node_size_px": NODE_SIZE_PX,

        "y_norm_origin": "top",

        "sequence": LABELS,

        "nodes": nodes,

        "gen_constraints_used": used,

        "preview_canvas_px": [W, H],

    }





def draw_centered_text(d: ImageDraw.ImageDraw, xy: Tuple[float, float], text: str, font, fill):

    x, y = xy

    try:

        d.text((x, y), text, font=font, fill=fill, anchor="mm")

        return

    except Exception:

        pass

    if hasattr(d, "textbbox"):

        b = d.textbbox((0, 0), text, font=font)

        tw, th = (b[2] - b[0], b[3] - b[1])

    else:

        tw, th = d.textsize(text, font=font)

    d.text((x - tw / 2, y - th / 2), text, font=font, fill=fill)





def draw_preview(out_png: Path, pts_ordered: List[Tuple[float, float]], draw_dev_line: bool) -> None:

    out_png.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (W, H), (255, 255, 255))

    d = ImageDraw.Draw(img)



    font = load_font(int(NODE_SIZE_PX * 0.52))

    small = load_font(28)



    if draw_dev_line:

        for i in range(M - 1):

            d.line([pts_ordered[i], pts_ordered[i + 1]], fill=(70, 70, 70), width=8)



    for i, (cx, cy) in enumerate(pts_ordered):

        bbox = [cx - R, cy - R, cx + R, cy + R]

        d.ellipse(bbox, fill=(255, 255, 255), outline=(70, 70, 70), width=6)

        draw_centered_text(d, (cx, cy), LABELS[i], font, (0, 0, 0))



    tag = "DEV" if draw_dev_line else "STIM"

    d.text((18, 14), f"{TASK} N{N} (M={M}) {tag}", fill=(80, 80, 80), font=small)

    img.save(out_png)





# ================== 生成 ==================

def generate_one_layout(seed: int) -> Tuple[List[Tuple[float, float]], Dict]:

    rng = random.Random(seed)



    for attempt in range(1, LAYOUT_TRIES + 1):

        pts = sample_points_spread(rng)

        if pts is None:

            continue



        for f in AVOID_LINE_FACTORS:

            avoid_line_px = R * f

            path = find_non_intersecting_path(rng, pts, avoid_line_px)

            if path is None:

                continue



            # ✅ 核心：相邻序列点不挨着（距离 + 近邻集合）

            if not adjacent_not_near_enough(path, pts):

                continue



            ordered = [pts[i] for i in path]



            if not irregular_enough(ordered):

                continue



            used = {

                "min_center_dist_px": MIN_CENTER_DIST_PX,

                "avoid_line_to_node_px": avoid_line_px,

                "avoid_line_factor": f,

                "layout_tries": attempt,

                "point_sampler": "farthest_point",

                "path_solver": "backtracking_hamiltonian_long_step",

                "path_backtrack_limit": PATH_BACKTRACK_LIMIT,

                "span_x_min_px": SPAN_X_MIN_PX,

                "span_y_min_px": SPAN_Y_MIN_PX,

                "min_step_len_px": MIN_STEP_LEN_PX,

                "near_neighbor_k": NEAR_NEIGHBOR_K,

                "note": "强制相邻序列点不挨着：最短步长 + 互不为前K近邻；并保持不自交/线避点/不规律。",

            }

            return ordered, used



    raise RuntimeError(

        "采样失败：约束仍较严。\\n"

        "建议优先放宽：MIN_STEP_LEN_PX（例如 320→280），或把 NEAR_NEIGHBOR_K 从 2 改 1。"

    )





def main():

    root = Path(__file__).resolve().parent  # DTMT 根目录

    layout_dir = root / "layouts" / "B1"

    preview_dir = layout_dir / "_previews"



    layout_dir.mkdir(parents=True, exist_ok=True)

    preview_dir.mkdir(parents=True, exist_ok=True)



    print("=== GEN B1 (NO-ADJACENT-NEAR) ===")

    print("root       :", root)

    print("layout_dir :", layout_dir)

    print("preview_dir:", preview_dir)



    seeds = [1107, 2231, 3399]



    for layout_id, sd in enumerate(seeds, start=1):

        pts_ordered, used = generate_one_layout(sd)

        obj = build_json(layout_id, pts_ordered, used)



        json_path = layout_dir / f"N{N}_{VERSION}_layout{layout_id}.json"

        json_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")



        stim_png = preview_dir / f"N{N}_{VERSION}_layout{layout_id}_stim.png"

        dev_png  = preview_dir / f"N{N}_{VERSION}_layout{layout_id}_dev.png"

        draw_preview(stim_png, pts_ordered, draw_dev_line=False)

        draw_preview(dev_png,  pts_ordered, draw_dev_line=True)



        print(f"[OK] layout{layout_id}")

        print(" json:", json_path)

        print(" stim:", stim_png)

        print(" dev :", dev_png)

        print(" used:", used)



    print("Done.")





if __name__ == "__main__":

    main()

