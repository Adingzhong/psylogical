# -*- coding: utf-8 -*-
"""
gen_A1_layouts_color.py

A1：生成 3 套布局，并同时输出 bw 与 color 两套 JSON（节点位置一致，只换素材路径）。
并输出预览 PNG（stim/solution）。

默认：
- K=6
- 水果序列交替 apple/lemon（如需全 apple，改 FRUIT_SEQ）
"""

from __future__ import annotations
import json, math, random, time
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import numpy as np
from PIL import Image as PILImage
from psychopy import visual, core

VERSION="N6_v1"
TASK="A1"
K=6
CANVAS_W, CANVAS_H = 1400, 1000
MARGIN_PX=90
NODE_SIZE_PX=170

SEEDS={1:421031,2:642117,3:893019}

# 反规律/分散约束（比旧版更不集中）
MIN_CENTER_MULT=1.30
MIN_STEP_FRAC=0.26
MAX_STEP_FRAC=0.98
COVER_W_MIN=0.78
COVER_H_MIN=0.62
MIN_LONG_RATIO=0.42
LONG_STEP_FRAC=0.40
MIN_QUAD_SWITCH=5
MAX_RANK_CORR=0.62
MAX_NEAR_NBR=0.58

TRIES=4200
SEED_JITTER_MAX=120
TIME_LIMIT_S=18.0

BG_COLOR=(1,1,1)
LINE_COLOR=(-0.2,-0.2,-0.2)
LINE_WIDTH=8

FRUITS=("apple","lemon")
FRUIT_SEQ=[FRUITS[i%2] for i in range(K)]

Pt=Tuple[float,float]
Seg=Tuple[Pt,Pt]

def resolve_root()->Path:
    here=Path(__file__).resolve().parent
    for p in [here]+list(here.parents):
        if (p/"layouts").exists() and (p/"stimuli").exists():
            return p
    return here

def clamp(v,lo,hi): return lo if v<lo else hi if v>hi else v
def dist(a:Pt,b:Pt)->float: return math.hypot(a[0]-b[0],a[1]-b[1])

def point_to_segment_distance(p:Pt,a:Pt,b:Pt)->float:
    ax,ay=a; bx,by=b; px,py=p
    vx,vy=bx-ax,by-ay; wx,wy=px-ax,py-ay
    vv=vx*vx+vy*vy
    if vv<=1e-9: return math.hypot(px-ax,py-ay)
    t=(wx*vx+wy*vy)/vv
    t=clamp(t,0.0,1.0)
    cx,cy=ax+t*vx,ay+t*vy
    return math.hypot(px-cx,py-cy)

def _orient(a:Pt,b:Pt,c:Pt)->float:
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def _on_segment(a:Pt,b:Pt,c:Pt)->bool:
    return (min(a[0],b[0])-1e-9<=c[0]<=max(a[0],b[0])+1e-9 and
            min(a[1],b[1])-1e-9<=c[1]<=max(a[1],b[1])+1e-9)

def segments_intersect(s1:Seg,s2:Seg)->bool:
    a,b=s1; c,d=s2
    o1=_orient(a,b,c); o2=_orient(a,b,d); o3=_orient(c,d,a); o4=_orient(c,d,b)
    if (o1>0)!=(o2>0) and (o3>0)!=(o4>0): return True
    if abs(o1)<1e-9 and _on_segment(a,b,c): return True
    if abs(o2)<1e-9 and _on_segment(a,b,d): return True
    if abs(o3)<1e-9 and _on_segment(c,d,a): return True
    if abs(o4)<1e-9 and _on_segment(c,d,b): return True
    return False

def path_segments(pts:List[Pt])->List[Seg]:
    return [((pts[i][0],pts[i][1]),(pts[i+1][0],pts[i+1][1])) for i in range(len(pts)-1)]

def no_self_intersections(pts:List[Pt])->bool:
    segs=path_segments(pts)
    for i in range(len(segs)):
        for j in range(i+1,len(segs)):
            if abs(i-j)<=1: continue
            if segments_intersect(segs[i],segs[j]): return False
    return True

def avoids_line_through_nodes(pts:List[Pt],avoid:float)->bool:
    segs=path_segments(pts)
    for i,(a,b) in enumerate(segs):
        for j,p in enumerate(pts):
            if j==i or j==i+1: continue
            if point_to_segment_distance(p,a,b)<avoid: return False
    return True

def bbox_cover_ratio(pts:List[Pt])->Tuple[float,float]:
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    usable_w=CANVAS_W-2*MARGIN_PX; usable_h=CANVAS_H-2*MARGIN_PX
    return ((max(xs)-min(xs))/max(1.0,usable_w),(max(ys)-min(ys))/max(1.0,usable_h))

def _rankdata(vals:List[float])->List[int]:
    order=sorted(range(len(vals)), key=lambda i: vals[i])
    rk=[0]*len(vals)
    for r,idx in enumerate(order): rk[idx]=r
    return rk

def _spearman_abs(a:List[int],b:List[int])->float:
    n=len(a)
    if n<=1: return 0.0
    da=[a[i]-(n-1)/2 for i in range(n)]
    db=[b[i]-(n-1)/2 for i in range(n)]
    num=sum(da[i]*db[i] for i in range(n))
    den1=math.sqrt(sum(x*x for x in da)); den2=math.sqrt(sum(x*x for x in db))
    if den1<1e-9 or den2<1e-9: return 0.0
    return abs(num/(den1*den2))

def rank_correlations(pts:List[Pt])->Tuple[float,float]:
    step=list(range(len(pts)))
    rx=_rankdata([p[0] for p in pts]); ry=_rankdata([p[1] for p in pts])
    return _spearman_abs(step,rx), _spearman_abs(step,ry)

def quad_switches(pts:List[Pt])->int:
    cx=CANVAS_W/2; cy=CANVAS_H/2
    def q(p:Pt)->int:
        return (0 if p[0]<cx else 1)+(0 if p[1]<cy else 2)
    qs=[q(p) for p in pts]
    return sum(1 for i in range(len(qs)-1) if qs[i]!=qs[i+1])

def long_ratio(pts:List[Pt], long_step:float)->float:
    segs=[dist(pts[i],pts[i+1]) for i in range(len(pts)-1)]
    return sum(1 for s in segs if s>=long_step)/max(1,len(segs))

def near_neighbor_ratio(pts:List[Pt],k:int=3)->float:
    hits=0
    for i in range(len(pts)-1):
        cur=pts[i]; nxt=pts[i+1]
        dists=[dist(cur,pts[j]) for j in range(len(pts)) if j!=i]
        dists.sort()
        dn=dist(cur,nxt)
        thresh=dists[min(k-1,len(dists)-1)] + 1e-6
        if dn<=thresh: hits+=1
    return hits/max(1,(len(pts)-1))

def valid_metrics(pts:List[Pt])->Optional[Dict[str,float]]:
    min_dim=min(CANVAS_W,CANVAS_H)
    max_dim=math.hypot(CANVAS_W,CANVAS_H)
    min_center=NODE_SIZE_PX*MIN_CENTER_MULT
    min_step=min_dim*MIN_STEP_FRAC
    max_step=max_dim*MAX_STEP_FRAC
    avoid=NODE_SIZE_PX*0.58

    for i in range(len(pts)):
        for j in range(i+1,len(pts)):
            if dist(pts[i],pts[j])<min_center: return None

    seglens=[]
    for i in range(len(pts)-1):
        s=dist(pts[i],pts[i+1])
        if s<min_step or s>max_step: return None
        seglens.append(s)

    cw,ch=bbox_cover_ratio(pts)
    if cw<COVER_W_MIN or ch<COVER_H_MIN: return None
    if not no_self_intersections(pts): return None
    if not avoids_line_through_nodes(pts, avoid): return None

    lr=long_ratio(pts, LONG_STEP_FRAC*min_dim)
    if lr<MIN_LONG_RATIO: return None
    qs=quad_switches(pts)
    if qs<MIN_QUAD_SWITCH: return None
    cx,cy=rank_correlations(pts)
    if max(cx,cy)>MAX_RANK_CORR: return None
    nnr=near_neighbor_ratio(pts,3)
    if nnr>MAX_NEAR_NBR: return None

    mean_s=sum(seglens)/max(1,len(seglens))
    std_s=math.sqrt(sum((s-mean_s)**2 for s in seglens)/max(1,len(seglens)))
    cv=std_s/max(1e-6,mean_s)

    return {"cover_w":float(cw),"cover_h":float(ch),"long_ratio":float(lr),
            "quad_switches":float(qs),"corr_x":float(cx),"corr_y":float(cy),
            "near_neighbor_ratio":float(nnr),"mean_step":float(mean_s),"cv_step":float(cv)}

def score(m:Dict[str,float])->float:
    return (14.0*min(m["cover_w"],m["cover_h"]) + 5.4*m["long_ratio"] + 0.45*m["quad_switches"]
            + 1.4*m["cv_step"] - 2.1*(m["corr_x"]+m["corr_y"]) - 3.0*m["near_neighbor_ratio"])

def random_point(rng:random.Random)->Pt:
    return (rng.uniform(MARGIN_PX,CANVAS_W-MARGIN_PX),
            rng.uniform(MARGIN_PX,CANVAS_H-MARGIN_PX))

def generate_best(seed0:int):
    import time as _t
    t0=_t.perf_counter()
    best=None; best_m=None; best_sc=-1e18; degraded=False
    for jitter in range(SEED_JITTER_MAX+1):
        if _t.perf_counter()-t0 > TIME_LIMIT_S: break
        rng=random.Random(seed0+jitter)
        for _ in range(TRIES):
            pts=[random_point(rng) for _ in range(K)]
            m=valid_metrics(pts)
            if m is None: continue
            sc=score(m)
            if sc>best_sc:
                best_sc=sc; best=pts; best_m=m; degraded=(jitter>0)
            if best_m and best_m["near_neighbor_ratio"]<0.55 and min(best_m["cover_w"],best_m["cover_h"])>0.78:
                out=dict(best_m); out.update({"seed_base":seed0,"degraded":degraded,"score":float(best_sc),"node_size_px":float(NODE_SIZE_PX)})
                return best,out,degraded
    if best is None:
        rng=random.Random(seed0+99991)
        best=[random_point(rng) for _ in range(K)]
        best_m={"profile":"emergency"}
        degraded=True
    out=dict(best_m); out.update({"seed_base":seed0,"degraded":degraded,"score":float(best_sc),"node_size_px":float(NODE_SIZE_PX)})
    return best,out,degraded

def stim_rel(style:str, fruit:str, k:int)->str:
    return f"stimuli/fruits/numbered/{style}/{fruit}_{style}_{k}.png"

def write_json(out_path:Path, pts:List[Pt], style:str, metrics:Dict[str,float])->None:
    nodes=[]
    for i in range(K):
        k=i+1; fruit=FRUIT_SEQ[i]
        x,y=pts[i]
        nodes.append({"node_id":k,"k":k,"fruit":fruit,"style":style,
                      "stim_rel":stim_rel(style,fruit,k),
                      "x_norm":x/CANVAS_W,"y_norm":y/CANVAS_H,"pos_px":[x,y]})
    payload={"task":TASK,"version":VERSION,"style":style,"K":K,
             "canvas_px":{"w":CANVAS_W,"h":CANVAS_H},
             "node_size_px":NODE_SIZE_PX,"metrics":metrics,"nodes":nodes,
             "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def find_img(root:Path, style:str, fruit:str, num:int)->Path:
    base=root/"stimuli"/"fruits"/"numbered"/style
    c1=base/f"{fruit}_{style}_{num}.png"
    c2=base/f"{fruit}_{style}_{num:02d}.png"
    if c1.exists(): return c1
    if c2.exists(): return c2
    raise FileNotFoundError(f"找不到素材：{c1} 或 {c2}")

def save_frame(win:visual.Window, out_path:Path)->None:
    win.getMovieFrame(buffer="front")
    frame=win.movieFrames[-1]
    win.movieFrames=[]
    if isinstance(frame, PILImage.Image):
        img=frame.copy()
    else:
        img=PILImage.fromarray(np.array(frame))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path), format="PNG")

def draw_nodes(win:visual.Window, root:Path, nodes:List[dict], style:str)->None:
    stim=visual.ImageStim(win=win, image=None, size=(NODE_SIZE_PX,NODE_SIZE_PX), units="pix", interpolate=True)
    for nd in nodes:
        k=int(nd["k"]); fruit=nd["fruit"]
        x,y=float(nd["pos_px"][0]), float(nd["pos_px"][1])
        stim.image=str(find_img(root, style, fruit, k))
        stim.pos=(x,y)
        stim.draw()

def draw_solution(win:visual.Window, nodes:List[dict])->None:
    sn=sorted(nodes, key=lambda d:d["k"])
    pts=[(float(nd["pos_px"][0]), float(nd["pos_px"][1])) for nd in sn]
    for i in range(len(pts)-1):
        visual.Line(win=win, start=pts[i], end=pts[i+1], lineColor=LINE_COLOR, lineWidth=LINE_WIDTH, units="pix").draw()

def main():
    root=resolve_root()
    out_bw=root/"layouts"/"A1"/"bw"
    out_color=root/"layouts"/"A1"/"color"
    prev=root/"layouts"/"A1"/"_previews"
    out_bw.mkdir(parents=True, exist_ok=True)
    out_color.mkdir(parents=True, exist_ok=True)
    prev.mkdir(parents=True, exist_ok=True)

    win=visual.Window(size=(CANVAS_W,CANVAS_H), units="pix", color=BG_COLOR, fullscr=False, allowGUI=True)

    for lid in (1,2,3):
        pts,metrics,degraded=generate_best(SEEDS[lid])
        for style in ("bw","color"):
            outp=(out_bw if style=="bw" else out_color)/f"{VERSION}_layout{lid}.json"
            write_json(outp, pts, style, dict(metrics))
            obj=json.loads(outp.read_text(encoding="utf-8"))
            nodes=obj["nodes"]

            win.clearBuffer(); draw_nodes(win, root, nodes, style); win.flip()
            save_frame(win, prev/f"{style}_{VERSION}_layout{lid}_stim.png")

            win.clearBuffer(); draw_solution(win, nodes); draw_nodes(win, root, nodes, style); win.flip()
            save_frame(win, prev/f"{style}_{VERSION}_layout{lid}_solution.png")

        print(f"[OK] A1 layout{lid} degraded={degraded} metrics={metrics}")

    win.close(); core.quit()

if __name__=="__main__":
    main()
