
# -*- coding: utf-8 -*-

"""

gen_B2_layouts.py  (B2: 方圆交替)



N=6 表示数字到6；总节点 M = 2*N-1 = 11

默认：1 为 square；正确序列：1□ → 2○ → 3□ → 4○ → 5□ → 6○

每个 2..N 还有一个同数字的 lure（另一种形状）。



输出：

DTMT/layouts/B2/N6_v1_layout{1..3}.json

DTMT/layouts/B2/_previews/N6_v1_layout{1..3}_stim.png

DTMT/layouts/B2/_previews/N6_v1_layout{1..3}_dev.png

"""



from __future__ import annotations

import json

import math

import random

from pathlib import Path

from typing import Dict, List, Tuple, Optional



from PIL import Image, ImageDraw, ImageFont



# ================== 可调参数（优先改这里） ==================

W, H = 1536, 1152           # 预览画布（4:3，贴近 iPad）

NODE_SIZE_PX = 165          # 节点直径

MARGIN_PX = 55              # 边距

R = NODE_SIZE_PX / 2.0



N = 6                       # 你的 N 固定 6



START_SHAPE = "square"      # "square" or "circle"：决定 1 的形状，以及全局交替



# “全屏散布”约束

SPAN_X_MIN_PX = W * 0.72

SPAN_Y_MIN_PX = H * 0.60



# ✅ 关键：避免“1旁边就是下一步”那种规律

MIN_STEP_LEN_PX = 320       # 正确路径相邻两点最短距离（太近就拒绝）

NEAR_NEIGHBOR_K = 2         # 正确相邻两点不允许互为前K近邻（K=2=最近/次近都不行）



# 点不重叠

MIN_CENTER_DIST_PX = NODE_SIZE_PX * 1.05



# 线段避开节点（可逐步放宽）

AVOID_LINE_FACTORS = [1.05, 0.95, 0.88, 0.80, 0.72, 0.65]  # *R



# 不规律（避免“从左到右一条龙”）

MAX_ABS_CORR = 0.78

MIN_DIR_CHANGES = 5



# 生成策略

LAYOUT_TARGET = 3           # 需要 3 张布局

MAX_SEED_TRIES = 80         # 自动换 seed 的最大次数

LAYOUT_TRIES_PER_SEED = 260 # 每个 seed 内部尝试次数



PATH_BACKTRACK_LIMIT = 260000

# ===========================================================



TASK = "B2"

VERSION = "v1"



# ========= 序列定义 =========

def shape_for_step(v: int) -> str:

    """

    v=1..N 的目标形状（正确路径上的那个）

    START_SHAPE 决定 v=1 是啥，之后交替。

    """

    if START_SHAPE not in ("square", "circle"):

        raise ValueError("START_SHAPE must be 'square' or 'circle'")

    if v == 1:

        return START_SHAPE

    # v 增加一次，形状翻一次

    # 若 START=square：奇数 square，偶数 circle

    # 若 START=circle：奇数 circle，偶数 square

    if START_SHAPE == "square":

        return "square" if (v % 2 == 1) else "circle"

    else:

        return "circle" if (v % 2 == 1) else "square"



def other_shape(s: str) -> str:

    return "circle" if s == "square" else "square"



# tokens：11 个节点（含 main + lure）

# main: v=1..N，每个一个（shape_for_step）

# lure: v=2..N，每个一个（另一形状）

def build_tokens() -> Tuple[List[Dict], List[Dict]]:

    main = []

    lure = []

    for v in range(1, N + 1):

        main.append({"value": v, "shape": shape_for_step(v), "role": "main"})

        if v >= 2:

            lure.append({"value": v, "shape": other_shape(shape_for_step(v)), "role": "lure"})

    return main, lure



MAIN_TOKENS, LURE_TOKENS = build_tokens()

M = len(MAIN_TOKENS) + len(LURE_TOKENS)

assert M == 2 * N - 1



# ========= 几何工具 =========

def seg_intersect(a, b, c, d) -> bool:

    def orient(p, q, r):

        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_seg(p, q, r):

        return (min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and

                min(p[1], r[1]) <= q[1] <= max(p[1], r[1]))

    o1 = orient(a, b, c); o2 = orient(a, b, d)

    o3 = orient(c, d, a); o4 = orient(c, d, b)

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



def neighbors_k(pts: List[Tuple[float, float]], i: int, k: int) -> List[int]:

    di = []

    xi, yi = pts[i]

    for j in range(len(pts)):

        if j == i:

            continue

        xj, yj = pts[j]

        d = math.hypot(xj - xi, yj - yi)

        di.append((d, j))

    di.sort(key=lambda t: t[0])

    return [j for _, j in di[:k]]



# ========= 字体 =========

def find_font() -> Optional[Path]:

    root = Path(__file__).resolve().parent

    candidates = [

        root / "fonts" / "arialbd.ttf",

        root / "fonts" / "arial.ttf",

    ]

    win = Path(r"C:\\Windows\\Fonts")

    candidates += [

        win / "arialbd.ttf",

        win / "arial.ttf",

        win / "calibrib.ttf",

        win / "calibri.ttf",

    ]

    for p in candidates:

        if p.exists():

            return p

    return None



def load_font(px: int):

    fp = find_font()

    if fp is not None:

        try:

            return ImageFont.truetype(str(fp), px)

        except Exception:

            pass

    return ImageFont.load_default()



def draw_centered_text(d: ImageDraw.ImageDraw, xy, text, font, fill):

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



# ========= 采样：farthest-point 分散 =========

def sample_points_spread(rng: random.Random, count: int) -> Optional[List[Tuple[float, float]]]:

    pts: List[Tuple[float, float]] = []

    xmin, xmax = MARGIN_PX + R, W - MARGIN_PX - R

    ymin, ymax = MARGIN_PX + R, H - MARGIN_PX - R

    Kcand = 90



    for _ in range(count):

        best = None

        best_min_dist = -1.0

        for _k in range(Kcand):

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



    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]

    if (max(xs) - min(xs)) < SPAN_X_MIN_PX:

        return None

    if (max(ys) - min(ys)) < SPAN_Y_MIN_PX:

        return None



    # 3x2 网格占用至少 5 格

    cols, rows = 3, 2

    occ = set()

    for (x, y) in pts:

        cx = min(cols - 1, int(cols * (x - xmin) / max(1.0, (xmax - xmin))))

        cy = min(rows - 1, int(rows * (y - ymin) / max(1.0, (ymax - ymin))))

        occ.add((cx, cy))

    if len(occ) < 5:

        return None



    return pts



# ========= 正确路径选 6 个点（回溯），其它 5 个点做 lure =========

def path_ok_add_segment(path_idx: List[int], cand: int, pts: List[Tuple[float, float]], avoid_line_px: float) -> bool:

    if not path_idx:

        return True

    a = pts[path_idx[-1]]

    b = pts[cand]



    # 相邻步长太短直接拒绝

    if math.hypot(a[0] - b[0], a[1] - b[1]) < MIN_STEP_LEN_PX:

        return False



    # 相邻不允许互为前K近邻

    if cand in neighbors_k(pts, path_idx[-1], NEAR_NEIGHBOR_K):

        return False

    if path_idx[-1] in neighbors_k(pts, cand, NEAR_NEIGHBOR_K):

        return False



    # 与已有正确线段不自交

    for i in range(len(path_idx) - 2):

        c = pts[path_idx[i]]

        d = pts[path_idx[i + 1]]

        if seg_intersect(a, b, c, d):

            return False



    # 新线段避开所有其它节点（包括 lure 点）

    for k in range(len(pts)):

        if k == path_idx[-1] or k == cand:

            continue

        if point_to_seg_dist(pts[k], a, b) < avoid_line_px:

            return False



    return True



def irregular_enough(ordered_pts: List[Tuple[float, float]]) -> bool:

    idx = list(range(1, len(ordered_pts) + 1))

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



def pick_main_path(rng: random.Random, pts: List[Tuple[float, float]], avoid_line_px: float) -> Optional[List[int]]:

    expanded = 0

    all_idx = list(range(len(pts)))

    rng.shuffle(all_idx)



    def backtrack(path_idx: List[int], remaining: List[int], need_len: int) -> Optional[List[int]]:

        nonlocal expanded

        expanded += 1

        if expanded > PATH_BACKTRACK_LIMIT:

            return None

        if len(path_idx) == need_len:

            return path_idx



        cand = remaining[:]

        rng.shuffle(cand)



        # 倾向“远一些”的点（避免贴着走）

        if path_idx:

            last = pts[path_idx[-1]]

            cand.sort(key=lambda i: -math.hypot(pts[i][0] - last[0], pts[i][1] - last[1]))



        for nxt in cand:

            if path_idx and not path_ok_add_segment(path_idx, nxt, pts, avoid_line_px):

                continue

            new_rem = [x for x in remaining if x != nxt]

            res = backtrack(path_idx + [nxt], new_rem, need_len)

            if res is not None:

                return res

        return None



    # 尝试不同起点

    for start in all_idx:

        rem = [i for i in range(len(pts)) if i != start]

        res = backtrack([start], rem, N)  # 正确路径长度 = N(=6)

        if res is not None:

            ordered = [pts[i] for i in res]

            if irregular_enough(ordered):

                return res

    return None



# ========= JSON/PNG =========

def px_to_norm(p: Tuple[float, float]) -> Tuple[float, float]:

    return (p[0] / W, p[1] / H)



def build_json(layout_id: int, all_nodes: List[Dict], used: Dict) -> Dict:

    return {

        "task": TASK,

        "version": VERSION,

        "N": N,

        "M": M,

        "layout_id": layout_id,

        "node_size_px": NODE_SIZE_PX,

        "y_norm_origin": "top",

        "start_shape": START_SHAPE,

        "main_sequence": [{"value": t["value"], "shape": t["shape"]} for t in MAIN_TOKENS],

        "nodes": all_nodes,

        "gen_constraints_used": used,

        "preview_canvas_px": [W, H],

    }



def draw_preview(out_png: Path, nodes: List[Dict], draw_dev_line: bool) -> None:

    out_png.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (W, H), (255, 255, 255))

    d = ImageDraw.Draw(img)

    font = load_font(int(NODE_SIZE_PX * 0.52))

    small = load_font(28)



    # 画 dev 的正确线

    if draw_dev_line:

        # 按 main 的 value=1..N 顺序找节点

        main_nodes = []

        for v in range(1, N + 1):

            sh = shape_for_step(v)

            nd = next(x for x in nodes if x["value"] == v and x["shape"] == sh)

            main_nodes.append((nd["x_px"], nd["y_px"]))

        for i in range(len(main_nodes) - 1):

            d.line([main_nodes[i], main_nodes[i + 1]], fill=(70, 70, 70), width=8)



    # 画节点

    for nd in nodes:

        cx, cy = nd["x_px"], nd["y_px"]

        bbox = [cx - R, cy - R, cx + R, cy + R]

        if nd["shape"] == "circle":

            d.ellipse(bbox, fill=(255, 255, 255), outline=(70, 70, 70), width=6)

        else:

            d.rectangle(bbox, fill=(255, 255, 255), outline=(70, 70, 70), width=6)



        draw_centered_text(d, (cx, cy), str(nd["value"]), font, (0, 0, 0))



    tag = "DEV" if draw_dev_line else "STIM"

    d.text((18, 14), f"{TASK} N{N} (M={M}) {tag}", fill=(80, 80, 80), font=small)

    img.save(out_png)



# ========= 生成单张布局 =========

def generate_one_layout(seed: int) -> Tuple[List[Dict], Dict]:

    rng = random.Random(seed)



    for attempt in range(1, LAYOUT_TRIES_PER_SEED + 1):

        pts = sample_points_spread(rng, M)

        if pts is None:

            continue



        for f in AVOID_LINE_FACTORS:

            avoid_line_px = R * f



            main_idx = pick_main_path(rng, pts, avoid_line_px)

            if main_idx is None:

                continue



            main_pts = [pts[i] for i in main_idx]

            # 剩余点做 lure

            rest_idx = [i for i in range(M) if i not in main_idx]

            rng.shuffle(rest_idx)

            lure_pts = [pts[i] for i in rest_idx]



            # 组装 nodes（把 token 绑定到点）

            # main：按 v=1..N 对应 main_pts 的顺序

            nodes: List[Dict] = []

            for j, tok in enumerate(MAIN_TOKENS):

                xpx, ypx = main_pts[j]

                xn, yn = px_to_norm((xpx, ypx))

                nodes.append({

                    "node_id": f"B2_main_{tok['value']:02d}",

                    "k": tok["value"],

                    "value": tok["value"],

                    "shape": tok["shape"],

                    "role": "main",

                    "x_norm": round(xn, 6),

                    "y_norm": round(yn, 6),

                    "x_px": float(xpx),

                    "y_px": float(ypx),

                })



            # lure：v=2..N，顺序无所谓（但写清 value/shape/role）

            for j, tok in enumerate(LURE_TOKENS):

                xpx, ypx = lure_pts[j]

                xn, yn = px_to_norm((xpx, ypx))

                nodes.append({

                    "node_id": f"B2_lure_{tok['value']:02d}_{tok['shape']}",

                    "k": None,

                    "value": tok["value"],

                    "shape": tok["shape"],

                    "role": "lure",

                    "x_norm": round(xn, 6),

                    "y_norm": round(yn, 6),

                    "x_px": float(xpx),

                    "y_px": float(ypx),

                })



            used = {

                "seed": seed,

                "attempt_in_seed": attempt,

                "min_center_dist_px": MIN_CENTER_DIST_PX,

                "avoid_line_to_node_px": avoid_line_px,

                "avoid_line_factor": f,

                "min_step_len_px": MIN_STEP_LEN_PX,

                "near_neighbor_k": NEAR_NEIGHBOR_K,

                "span_x_min_px": SPAN_X_MIN_PX,

                "span_y_min_px": SPAN_Y_MIN_PX,

                "note": "固定正确序列(1..N形状交替)；选择N个点做main路径，不自交+线避点；相邻不贴近(最短步长+互不为前K近邻)。",

            }

            return nodes, used



    raise RuntimeError("该 seed 下生成失败（约束偏严）。")



# ========= 主函数：保证凑齐 3 张 =========

def main():

    root = Path(__file__).resolve().parent  # DTMT 根目录

    layout_dir = root / "layouts" / "B2"

    preview_dir = layout_dir / "_previews"

    layout_dir.mkdir(parents=True, exist_ok=True)

    preview_dir.mkdir(parents=True, exist_ok=True)



    print("=== GEN B2 (square/circle alternating) ===")

    print("root       :", root)

    print("layout_dir :", layout_dir)

    print("preview_dir:", preview_dir)



    made = 0

    used_seeds = []

    base_seed = 5201



    seed_try = 0

    while made < LAYOUT_TARGET and seed_try < MAX_SEED_TRIES:

        seed = base_seed + seed_try * 97

        seed_try += 1

        try:

            nodes, used = generate_one_layout(seed)

        except Exception as e:

            print(f"[FAIL] seed={seed} -> {e}")

            continue



        layout_id = made + 1

        used_seeds.append(seed)



        # 写 JSON（注意：把 x_px/y_px 保留在 json 里方便你肉眼查；之后 run 阶段也可以忽略）

        json_path = layout_dir / f"N{N}_{VERSION}_layout{layout_id}.json"

        obj = build_json(layout_id, nodes, used)

        json_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")



        stim_png = preview_dir / f"N{N}_{VERSION}_layout{layout_id}_stim.png"

        dev_png  = preview_dir / f"N{N}_{VERSION}_layout{layout_id}_dev.png"

        draw_preview(stim_png, nodes, draw_dev_line=False)

        draw_preview(dev_png,  nodes, draw_dev_line=True)



        print(f"[OK] layout{layout_id} seed={seed}")

        print(" json:", json_path)

        print(" stim:", stim_png)

        print(" dev :", dev_png)

        made += 1



    if made < LAYOUT_TARGET:

        raise RuntimeError(

            f"只生成了 {made}/{LAYOUT_TARGET} 张。"

            f"建议先放宽 MIN_STEP_LEN_PX（320→280）或 NEAR_NEIGHBOR_K（2→1）。"

        )



    print("Done. seeds:", used_seeds)



if __name__ == "__main__":

    main()

