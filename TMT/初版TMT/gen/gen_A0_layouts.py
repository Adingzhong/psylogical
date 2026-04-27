
# gen_A0_layouts.py

# -*- coding: utf-8 -*-



from __future__ import annotations

import json, math, random

from dataclasses import dataclass

from datetime import datetime

from itertools import permutations

from pathlib import Path

from typing import List, Tuple, Optional



# =========================

# 基本参数（A0）

# =========================

TASK = "A0"

VERSION = "N6_v1"

N = 6



# 三张固定图：改 seed 就等于换三张图

SEEDS = [2025121901, 2025121902, 2025121903]



# 约束（A0 预览更像经典 TMT：点位尽量铺满整个屏幕/纸面）
# 重要：A0 / B1 / B2 统一节点像素大小（对齐你最新要求）
# - B1/B2 当前使用 1536×1152 画布 + NODE_SIZE_PX=165
# - A0 也使用同一组参数；但为了避免“点集中在中间”，采样与约束统一改用像素空间

CANVAS_W, CANVAS_H = 1536, 1152
NODE_SIZE_PX = 165
NODE_RADIUS_PX = NODE_SIZE_PX / 2.0

# 额外安全边距（像素）：保证节点不会贴边/被裁切，同时允许更靠近边缘，视觉更“遍布全屏”
MARGIN_PX = 35

# 兼容字段：归一化半径（以最短边归一化），用于 JSON 的 render_hints
NODE_RADIUS_NORM = NODE_RADIUS_PX / float(min(CANVAS_W, CANVAS_H))



# 点间距下限（更大=更松更易点）
# 说明：A0 以前的 NODE_RADIUS 较小（0.035），用 2.7 会得到约 0.189 的最小中心距。
# 现在 NODE_RADIUS 由 NODE_SIZE_PX 推导后变大，若仍用 2.7 会导致约束过严生成失败。
# 这里把 multiplier 调整到约 1.32，用于保持“像素尺度上的最小中心距”大致不变。
MIN_SPACING_MULT = 1.32

AVOID_R_MULT      = 1.10   # 线段避开其他点的距离下限



BBOX_AREA_MIN   = 0.40     # 覆盖率：提高下限，让点更“遍布全屏”

BBOX_AREA_MAX   = 0.88     # 上限不动（主要靠 margin 控制别贴边）



# “不规律”门槛：比你之前更严格

CORR_ABS_MAX     = 0.60    # |corr(index,x/y)| 过大则太像提示

STRAIGHT_MAX     = 0.78    # 太直像提示

MIN_TURN_MEAN    = 0.55    # 平均转角（弧度）至少这么大（越大越不直）

MIN_SIGN_CHANGES = 2       # dx/dy 或转向符号的变化次数（避免单调走）



# 采样次数（因为我们每次都做720排列评分，所以不用太大）

MAX_POINT_TRIES = 8000



EXPORT_PREVIEWS = True



# =========================

# 输出路径（放 DTMT 根目录运行最稳）

# =========================

BASE_DIR   = Path(__file__).resolve().parent

LAYOUT_DIR = BASE_DIR / "layouts" / TASK

PREVIEW_DIR = LAYOUT_DIR / "_previews"

LAYOUT_DIR.mkdir(parents=True, exist_ok=True)

if EXPORT_PREVIEWS:

    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)



# =========================

# 工具函数

# =========================

def dist(a,b): return math.hypot(a[0]-b[0], a[1]-b[1])



def pearson(xs, ys):

    n = len(xs)

    mx = sum(xs)/n; my = sum(ys)/n

    num = sum((x-mx)*(y-my) for x,y in zip(xs,ys))

    denx = math.sqrt(sum((x-mx)**2 for x in xs))

    deny = math.sqrt(sum((y-my)**2 for y in ys))

    if denx < 1e-12 or deny < 1e-12: return 0.0

    return num/(denx*deny)



def point_to_seg_dist(p, a, b):

    ax,ay=a; bx,by=b; px,py=p

    abx,aby = bx-ax, by-ay

    apx,apy = px-ax, py-ay

    ab2 = abx*abx + aby*aby

    if ab2 < 1e-12:

        return math.hypot(px-ax, py-ay)

    t = (apx*abx + apy*aby)/ab2

    t = max(0.0, min(1.0, t))

    cx,cy = ax + t*abx, ay + t*aby

    return math.hypot(px-cx, py-cy)



def seg_intersect(p1,p2,q1,q2):

    def orient(a,b,c):

        v = (b[1]-a[1])*(c[0]-b[0]) - (b[0]-a[0])*(c[1]-b[1])

        if abs(v) < 1e-12: return 0

        return 1 if v > 0 else 2

    def on_seg(a,b,c):

        return (min(a[0],c[0])-1e-12 <= b[0] <= max(a[0],c[0])+1e-12 and

                min(a[1],c[1])-1e-12 <= b[1] <= max(a[1],c[1])+1e-12)

    o1=orient(p1,p2,q1); o2=orient(p1,p2,q2); o3=orient(q1,q2,p1); o4=orient(q1,q2,p2)

    if o1!=o2 and o3!=o4: return True

    if o1==0 and on_seg(p1,q1,p2): return True

    if o2==0 and on_seg(p1,q2,p2): return True

    if o3==0 and on_seg(q1,p1,q2): return True

    if o4==0 and on_seg(q1,p2,q2): return True

    return False



def angle_between(v1, v2):

    x1,y1=v1; x2,y2=v2

    n1=math.hypot(x1,y1); n2=math.hypot(x2,y2)

    if n1 < 1e-12 or n2 < 1e-12: return 0.0

    c = max(-1.0, min(1.0, (x1*x2+y1*y2)/(n1*n2)))

    return math.acos(c)  # 0~pi，越大转得越厉害



def sign_changes(vals, eps=1e-8):

    s=[]

    for v in vals:

        if abs(v) < eps: continue

        s.append(1 if v>0 else -1)

    if len(s) <= 1: return 0

    return sum(1 for i in range(1,len(s)) if s[i]!=s[i-1])



# =========================

# 单条路径（已指定顺序）校验+评分

# =========================

@dataclass

class Report:

    min_pairwise: float

    min_required: float

    min_node_to_seg: float

    avoid_required: float

    bbox_area: float

    corr_ix: float

    corr_iy: float

    straightness: float

    turn_mean: float

    dx_changes: int

    dy_changes: int

    turn_changes: int

    score: float



def evaluate_path(path_pts: List[Tuple[float,float]]) -> Optional[Report]:

    # 1) margin

    min_x = NODE_RADIUS_PX + MARGIN_PX
    max_x = CANVAS_W - NODE_RADIUS_PX - MARGIN_PX
    min_y = NODE_RADIUS_PX + MARGIN_PX
    max_y = CANVAS_H - NODE_RADIUS_PX - MARGIN_PX
    for x,y in path_pts:
        if not (min_x <= x <= max_x and min_y <= y <= max_y):
            return None



    # 2) spacing

    # 以像素计：中心距至少为 node_diam * multiplier
    min_spacing = NODE_SIZE_PX * MIN_SPACING_MULT

    min_d=1e9

    for i in range(N):

        for j in range(i+1,N):

            d=dist(path_pts[i], path_pts[j])

            min_d=min(min_d,d)

            if d < min_spacing:

                return None



    # 3) non-self-intersection

    segs=[(path_pts[i], path_pts[i+1]) for i in range(N-1)]

    for i in range(len(segs)):

        for j in range(i+1,len(segs)):

            if abs(i-j) <= 1:

                continue

            if seg_intersect(segs[i][0],segs[i][1],segs[j][0],segs[j][1]):

                return None



    # 4) avoid other nodes near segments

    avoid_r = NODE_RADIUS_PX * AVOID_R_MULT

    min_ns=1e9

    for si,(a,b) in enumerate(segs):

        for pi,p in enumerate(path_pts):

            if pi==si or pi==si+1: 

                continue

            d=point_to_seg_dist(p,a,b)

            min_ns=min(min_ns,d)

            if d < avoid_r:

                return None



    # 5) bbox coverage

    xs=[p[0] for p in path_pts]; ys=[p[1] for p in path_pts]
    xs_n=[x/float(CANVAS_W) for x in xs]
    ys_n=[y/float(CANVAS_H) for y in ys]

    # bbox 覆盖率：用归一化面积（0~1）表征是否“遍布全屏”
    bbox=((max(xs)-min(xs))/float(CANVAS_W))*((max(ys)-min(ys))/float(CANVAS_H))

    if not (BBOX_AREA_MIN <= bbox <= BBOX_AREA_MAX):

        return None



    # 6) anti-regular (corr, straightness, turns)

    idx=list(range(1,N+1))

    corr_ix = pearson(idx, xs_n)
    corr_iy = pearson(idx, ys_n)

    if abs(corr_ix) > CORR_ABS_MAX or abs(corr_iy) > CORR_ABS_MAX:

        return None



    direct = dist(path_pts[0], path_pts[-1])

    segsum = sum(dist(path_pts[i], path_pts[i+1]) for i in range(N-1))

    straight = 1.0 if segsum < 1e-12 else direct/segsum

    if straight > STRAIGHT_MAX:

        return None



    # turn stats

    turns=[]

    turn_sign=[]

    dxs=[]; dys=[]

    for i in range(N-1):

        dxs.append(path_pts[i+1][0]-path_pts[i][0])

        dys.append(path_pts[i+1][1]-path_pts[i][1])

    for i in range(1,N-1):

        v1=(path_pts[i][0]-path_pts[i-1][0], path_pts[i][1]-path_pts[i-1][1])

        v2=(path_pts[i+1][0]-path_pts[i][0], path_pts[i+1][1]-path_pts[i][1])

        ang = angle_between(v1,v2)

        turns.append(ang)

        cross = v1[0]*v2[1]-v1[1]*v2[0]

        if abs(cross) > 1e-8:

            turn_sign.append(1 if cross>0 else -1)



    turn_mean = sum(turns)/len(turns) if turns else 0.0

    if turn_mean < MIN_TURN_MEAN:

        return None



    dx_changes = sign_changes(dxs)

    dy_changes = sign_changes(dys)

    turn_changes = sign_changes(turn_sign)



    if max(dx_changes, dy_changes, turn_changes) < MIN_SIGN_CHANGES:

        return None



    # 评分：越“转得多”、越“去单调”、越“不直”分越高

    score = (

        1.4*turn_mean

        + 0.7*max(dx_changes, dy_changes)

        + 0.7*turn_changes

        + 0.6*(bbox)

        - 1.0*abs(corr_ix)

        - 1.0*abs(corr_iy)

        - 1.2*straight

    )



    return Report(

        min_pairwise=round(min_d,4),

        min_required=round(min_spacing,4),

        min_node_to_seg=round(min_ns,4),

        avoid_required=round(avoid_r,4),

        bbox_area=round(bbox,4),

        corr_ix=round(corr_ix,4),

        corr_iy=round(corr_iy,4),

        straightness=round(straight,4),

        turn_mean=round(turn_mean,4),

        dx_changes=dx_changes,

        dy_changes=dy_changes,

        turn_changes=turn_changes,

        score=round(score,4),

    )



# =========================

# 生成：先采点，再全排列挑最不规律

# =========================

def sample_best_layout(seed: int) -> Tuple[List[Tuple[float,float]], Report]:

    rng = random.Random(seed)

    min_x = NODE_RADIUS_PX + MARGIN_PX
    max_x = CANVAS_W - NODE_RADIUS_PX - MARGIN_PX
    min_y = NODE_RADIUS_PX + MARGIN_PX
    max_y = CANVAS_H - NODE_RADIUS_PX - MARGIN_PX



    best_pts=None

    best_rep=None



    for _ in range(MAX_POINT_TRIES):

        # 先采 N 个点（无序集合）

        pts=[(rng.uniform(min_x, max_x), rng.uniform(min_y, max_y)) for _ in range(N)]



        # 在这 N 点上做全排列，找“最不规律且通过约束”的顺序

        local_best_rep=None

        local_best_order=None

        for perm in permutations(range(N)):

            path=[pts[i] for i in perm]

            rep=evaluate_path(path)

            if rep is None:

                continue

            if (local_best_rep is None) or (rep.score > local_best_rep.score):

                local_best_rep = rep

                local_best_order = perm



        if local_best_rep is not None:

            # 找到一条合格路径就收下；也可以继续找更好，但这样更快

            best_pts=[pts[i] for i in local_best_order]

            best_rep=local_best_rep

            return best_pts, best_rep



    raise RuntimeError("采样失败：约束过严。可适当降低 MIN_SPACING_MULT 或 MIN_TURN_MEAN。")



# =========================

# 保存 JSON + 预览图

# =========================

def save_json(points: List[Tuple[float,float]], rep: Report, layout_id: int, seed: int) -> Path:

    layout = {

        "meta": {

            "task_type": TASK,

            "layout_version": VERSION,

            "layout_id": layout_id,

            "n_nodes": N,

            "seed": seed,

            "created_at": datetime.now().isoformat(timespec="seconds"),

            "validation": rep.__dict__,

        },

        "canvas": {"coord_system": "norm_0_1"},

        # A0/B1/B2 统一节点大小（像素）
        "node_size_px": int(NODE_SIZE_PX),

        "render_hints": {
            "node_radius_norm": float(NODE_RADIUS_NORM),
            "node_radius_norm_x": float(NODE_RADIUS_PX / float(CANVAS_W)),
            "node_radius_norm_y": float(NODE_RADIUS_PX / float(CANVAS_H)),
            "node_radius_px": float(NODE_RADIUS_PX),
        },

        "nodes": [

            {

                "node_id": f"n{i:02d}",

                "label": str(i),

                "x_norm": float(points[i-1][0] / float(CANVAS_W)),

                "y_norm": float(points[i-1][1] / float(CANVAS_H)),

                "shape": "circle",

                "category": "digit",

            }

            for i in range(1, N+1)

        ],

        "sequence": [f"n{i:02d}" for i in range(1, N+1)],

    }

    out = LAYOUT_DIR / f"{VERSION}_layout{layout_id}.json"

    out.write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")

    return out



def export_previews(points: List[Tuple[float,float]], rep: Report, base_name: str):

    import matplotlib

    matplotlib.use("Agg")

    import matplotlib.pyplot as plt



    def draw(ax, with_path=False, with_info=False):

        # 用像素坐标画预览，避免 0~1 正方形预览导致“看起来都挤在中间”
        ax.set_xlim(0, CANVAS_W)
        ax.set_ylim(0, CANVAS_H)
        ax.set_aspect("equal")
        ax.axis("off")

        if with_path:

            ax.plot([p[0] for p in points],[p[1] for p in points], alpha=0.45, linewidth=1.5)

        for i,(x,y) in enumerate(points, start=1):

            circ=plt.Circle((x,y), NODE_RADIUS_PX, fill=False, linewidth=2)

            ax.add_patch(circ)

            ax.text(x,y,str(i),ha="center",va="center",fontsize=14)

        if with_info:

            info = (

                f"score={rep.score}\\n"

                f"corr=({rep.corr_ix},{rep.corr_iy}) straight={rep.straightness}\\n"

                f"turnMean={rep.turn_mean} dxChg={rep.dx_changes} dyChg={rep.dy_changes} turnChg={rep.turn_changes}\\n"

                f"minD={rep.min_pairwise} req={rep.min_required}  avoidMin={rep.min_node_to_seg} req={rep.avoid_required}\\n"

                f"bbox={rep.bbox_area}"

            )

            ax.text(0.02,0.02,info,transform=ax.transAxes,fontsize=9,

                    va="bottom",ha="left",

                    bbox=dict(boxstyle="round,pad=0.3",facecolor="white",alpha=0.85))



    # stim

    fig,ax=plt.subplots(figsize=(6.67,5.0))

    draw(ax, with_path=False, with_info=False)

    fig.savefig(PREVIEW_DIR/f"{base_name}_stim.png", dpi=200, bbox_inches="tight", pad_inches=0.05)

    plt.close(fig)



    # dev

    fig,ax=plt.subplots(figsize=(6.67,5.0))

    draw(ax, with_path=True, with_info=True)

    fig.savefig(PREVIEW_DIR/f"{base_name}_dev.png", dpi=200, bbox_inches="tight", pad_inches=0.05)

    plt.close(fig)



def main():

    print(f"[GEN] {TASK} N={N} {VERSION}")

    for lid, seed in enumerate(SEEDS, start=1):

        pts, rep = sample_best_layout(seed)

        p = save_json(pts, rep, lid, seed)

        if EXPORT_PREVIEWS:

            export_previews(pts, rep, f"{VERSION}_layout{lid}")

        print(f"  layout{lid} seed={seed} -> {p.name}  score={rep.score}  corr=({rep.corr_ix},{rep.corr_iy}) straight={rep.straightness}")



    print("DONE.")

    print("JSON:", LAYOUT_DIR)

    if EXPORT_PREVIEWS:

        print("PNG :", PREVIEW_DIR)



if __name__ == "__main__":

    main()







