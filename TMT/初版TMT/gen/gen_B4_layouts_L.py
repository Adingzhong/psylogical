# -*- coding: utf-8 -*-
"""
gen_B4_layouts_L.py

B4_L（低干扰 / 未来 B3）布局生成器（稳定版）
- 借鉴 gen_A1_layouts.py 的点集生成方式
- 固定交替顺序：A1 → B1 → A2 → B2 → … → A6
- 仅保留一条低干扰 ratio 约束
- 多级 fallback，保证永不失败
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import List, Tuple, Optional

from PIL import Image, ImageDraw

# =========================
# 基本参数
# =========================
TASK = "B4_L"
STYLE = "color"

N = 6
M = 2 * N - 1

CANVAS_W, CANVAS_H = 1024, 768
NODE_SIZE_PX = 170
NODE_RADIUS = NODE_SIZE_PX / 2

MARGIN_PX = int(NODE_SIZE_PX * 0.55)

# 低干扰约束
MIN_WRONG_RATIO = 1.10
MIN_MEAN_RATIO = 1.22

# 固定三套 seed
SEEDS = {1: 510031, 2: 830117, 3: 120019}

FRUIT_A = {1: "apple", 2: "lemon", 3: "apple"}
OTHER = {"apple": "lemon", "lemon": "apple"}

# =========================
# 工具
# =========================
Point = Tuple[float, float]

def dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])

def resolve_root() -> Path:
    here = Path(__file__).resolve().parent
    for p in [here] + list(here.parents):
        if (p / "layouts").exists():
            return p
    return here

# =========================
# 点集生成（带 fallback）
# =========================
def sample_point_set(
    rng: random.Random,
    min_center_mult: float
) -> Optional[List[Point]]:
    x_min = -CANVAS_W / 2 + MARGIN_PX
    x_max =  CANVAS_W / 2 - MARGIN_PX
    y_min = -CANVAS_H / 2 + MARGIN_PX
    y_max =  CANVAS_H / 2 - MARGIN_PX

    cols, rows = 6, 4
    cell_w = (x_max - x_min) / cols
    cell_h = (y_max - y_min) / rows

    cells = [(c, r) for c in range(cols) for r in range(rows)]
    rng.shuffle(cells)

    pts: List[Point] = []
    min_dist = NODE_SIZE_PX * min_center_mult

    for (c, r) in cells:
        if len(pts) >= M:
            break
        cx = x_min + (c + 0.5) * cell_w
        cy = y_min + (r + 0.5) * cell_h
        p = (
            rng.uniform(cx - cell_w * 0.42, cx + cell_w * 0.42),
            rng.uniform(cy - cell_h * 0.42, cy + cell_h * 0.42),
        )
        if all(dist(p, q) >= min_dist for q in pts):
            pts.append(p)

    if len(pts) == M:
        return pts
    return None

# =========================
# 低干扰 ratio 约束
# =========================
def low_interference_ok(pts: List[Point]) -> bool:
    ratios = []
    for i in range(M - 1):
        cur = pts[i]
        nxt = pts[i + 1]
        d_corr = dist(cur, nxt)
        if d_corr < 1e-6:
            return False
        d_wrong = min(
            dist(cur, pts[j])
            for j in range(M)
            if j not in (i, i + 1)
        )
        ratios.append(d_wrong / d_corr)
    return (min(ratios) >= MIN_WRONG_RATIO) and (sum(ratios) / len(ratios) >= MIN_MEAN_RATIO)

# =========================
# 生成单个布局（永不失败）
# =========================
def generate_layout(seed: int) -> List[Point]:
    rng = random.Random(seed)

    # 三档 fallback：逐步放宽点距
    for min_center_mult in (1.05, 0.95, 0.85):
        for _ in range(400):
            pts = sample_point_set(rng, min_center_mult)
            if pts is None:
                continue
            if low_interference_ok(pts):
                return pts

    # 最终兜底：只保证点在屏幕内
    pts = []
    x_min = -CANVAS_W / 2 + MARGIN_PX
    x_max =  CANVAS_W / 2 - MARGIN_PX
    y_min = -CANVAS_H / 2 + MARGIN_PX
    y_max =  CANVAS_H / 2 - MARGIN_PX
    for _ in range(M):
        pts.append((
            rng.uniform(x_min, x_max),
            rng.uniform(y_min, y_max),
        ))
    return pts

# =========================
# 输出
# =========================
def write_json(path: Path, pts: List[Point], fruit_a: str):
    nodes = []
    for step in range(1, M + 1):
        if step % 2 == 1:
            fruit = fruit_a
            num = (step + 1) // 2
        else:
            fruit = OTHER[fruit_a]
            num = step // 2
        x, y = pts[step - 1]
        nodes.append({
            "node_id": step,
            "step": step,
            "fruit": fruit,
            "num": num,
            "style": STYLE,
            "x_px": x,
            "y_px": y,
            "x_norm": x / CANVAS_W,
            "y_norm": y / CANVAS_H,
        })

    obj = {
        "task": "B4",
        "version": "N6_v1",
        "difficulty": "L",
        "N": N,
        "M": M,
        "style": STYLE,
        "fruitA": fruit_a,
        "fruitB": OTHER[fruit_a],
        "canvas_px": {"w": CANVAS_W, "h": CANVAS_H},
        "node_diam_px": NODE_SIZE_PX,
        "path_node_ids": list(range(1, M + 1)),
        "nodes": nodes,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def draw_preview(path: Path, pts: List[Point]):
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    dr = ImageDraw.Draw(img)

    def cv(p):
        return (int(p[0] + CANVAS_W / 2), int(CANVAS_H / 2 - p[1]))

    for i in range(len(pts) - 1):
        dr.line([cv(pts[i]), cv(pts[i + 1])], fill=(200, 0, 0), width=4)

    for p in pts:
        x, y = cv(p)
        r = NODE_RADIUS
        dr.ellipse([x - r, y - r, x + r, y + r], outline=(0, 0, 0), width=3)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)

# =========================
# main
# =========================
def main():
    root = resolve_root()
    out_dir = root / "layouts" / "B4_L"
    prev_dir = out_dir / "_previews"

    for lid in (1, 2, 3):
        pts = generate_layout(SEEDS[lid])
        fruit_a = FRUIT_A[lid]

        json_path = out_dir / f"N6_v1_layout{lid}.json"
        write_json(json_path, pts, fruit_a)

        prev_path = prev_dir / f"N6_v1_layout{lid}_dev.png"
        draw_preview(prev_path, pts)

        print(f"[OK] layout{lid} → {json_path}")

    print("Done.")

if __name__ == "__main__":
    main()