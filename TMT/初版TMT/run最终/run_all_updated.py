#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DTMT run_all.py (Final Optimized Version)

优化内容：
1. 练习节点更大 (Radius 40 -> 70)。
2. 按键响应更灵敏 (缩短强制缓冲时间，解决"按几次才响应"的问题)。
3. 流程保持不变: all_1 -> 1(操作) -> all_2(练习说明) -> 练习 -> 2(正式提示) -> A0..B4 -> all_4。
"""

from __future__ import annotations
import argparse
import datetime as _dt
import os
import math
from psychopy import visual, core, event, gui
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

# ====== 导入子任务模块 ======
# 优先导入 *_updated 版本（若不存在则回退 *_last）
try:
    import run_A0_updated as A0
except Exception:
    import run_A0_last as A0

try:
    import run_B1_updated as B1
except Exception:
    import run_B1_last as B1

try:
    import run_B2_updated as B2
except Exception:
    import run_B2_last as B2

try:
    import run_A1_updated as A1
except Exception:
    import run_A1_last as A1

try:
    import run_B3_updated as B3
except Exception:
    import run_B3_last as B3

try:
    import run_B4_updated as B4
except Exception:
    import run_B4_last as B4



# ---------------- utils ----------------
def now_str() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stable_layout_id_from_subject(subject_id: str) -> int:
    h = 0
    for ch in subject_id:
        h = (h * 131 + ord(ch)) % 1000003
    return (h % 3) + 1


def append_log(log_path: str, line: str) -> None:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fp:
        fp.write(line.rstrip("\n") + "\n")


def ensure_cursor(win: visual.Window, visible: bool = True) -> event.Mouse:
    m = event.Mouse(win=win)
    try:
        m.setVisible(bool(visible))
    except Exception:
        pass
    return m


def resolve_project_root() -> str:
    """智能查找项目根目录(向上查找stimuli文件夹)"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "stimuli")):
        return script_dir
    parent_dir = os.path.dirname(script_dir)
    if os.path.exists(os.path.join(parent_dir, "stimuli")):
        return parent_dir
    return script_dir


def show_image_wait(
    win: visual.Window,
    img_path: str,
    key_list=("space", "return", "num_enter"),
    allow_escape: bool = True,
    min_wait: float = 0.3
) -> str:
    """
    显示全屏图片 + 底部蓝色按钮，等待按钮点击或按键。
    按钮有 hover/press 视觉反馈。
    """
    canvas_w, canvas_h = win.size

    # 1. 准备图片刺激
    stim = None
    if os.path.exists(img_path):
        try:
            img_scale = 0.82
            img_y_off = 0
            stim = visual.ImageStim(win=win, image=img_path, units="pix",
                                    size=(int(canvas_w * img_scale), int(canvas_h * img_scale)),
                                    pos=(0, img_y_off))
        except Exception as e:
            print(f"[WARN] Failed to load image: {img_path}, error: {e}")
    else:
        print(f"[WARN] Image not found: {img_path}")

    if stim is None:
        msg = f"[提示页缺失]\n{os.path.basename(img_path)}\n\n按屏幕继续"
        stim = visual.TextStim(win, text=msg, font=CJK_FONT, color=(-0.5, -0.5, -0.5), height=30)

    # 2. 创建底部按钮（大号）
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

    mouse = ensure_cursor(win, visible=True)

    # 3. 缓冲期（防连击）
    event.clearEvents()
    timer = core.Clock()
    prev_pressed = True  # 防止上一页残留按压
    while timer.getTime() < min_wait:
        stim.draw()
        btn_shadow.draw(); btn_rect.draw(); btn_label.draw()
        win.flip()
    event.clearEvents()
    prev_pressed = mouse.getPressed()[0]

    # 4. 等待按钮点击或按键
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

        # 点击检测（按下即触发，适合触屏）
        if cur_pressed and not prev_pressed and hovering:
            btn_rect.fillColor = _btn_press
            btn_shadow.opacity = 0
            stim.draw(); btn_rect.draw(); btn_label.draw()
            win.flip()
            core.wait(0.15)
            return "space"
        prev_pressed = cur_pressed

        # 键盘检测
        keys = event.getKeys()
        if allow_escape and "escape" in keys:
            return "escape"
        for k in key_list:
            if k in keys:
                return k

        core.wait(0.008)


# -------------- 练习模块 --------------
def run_practice_1234(
    win: visual.Window,
    subject_id: str,
    session_id: str,
    age: str,
    layout_id: int,
    results_root: str,
    root_dir: str,
) -> str:
    """
    练习环节：1-2-3-4
    ★ 优化：节点变大，更易点击
    """
    import csv
    
    # 1. 欢迎页 (all_1.png)
    img_1 = os.path.join(root_dir, "stimuli", "zdy", "all_1.png")
    if show_image_wait(win, img_1) == "escape": return "escape"

    # 2. 通用操作方法 (1.png)
    img_howto = os.path.join(root_dir, "stimuli", "zdy", "1.png")
    if os.path.exists(img_howto):
        if show_image_wait(win, img_howto) == "escape": return "escape"

    # 3. 练习说明 (all_2.png)
    img_practice = os.path.join(root_dir, "stimuli", "zdy", "all_2.png")
    if os.path.exists(img_practice):
        if show_image_wait(win, img_practice) == "escape": return "escape"

    # 4. 执行练习逻辑
    # -------------------------------------------------
    canvas_w, canvas_h = float(win.size[0]), float(win.size[1])
    positions = [
        (0, 0.25 * canvas_h), 
        (-0.30 * canvas_w, -0.05 * canvas_h), 
        (0.30 * canvas_w, -0.05 * canvas_h), 
        (0, -0.30 * canvas_h)
    ]
    
    # ★ 优化点：节点半径变大 (40 -> 70)，线变粗
    node_r = 70.0
    line_w = 10
    font_h = 42
    
    circles = []
    labels = []
    for i, pos in enumerate(positions, start=1):
        circles.append(visual.Circle(win=win, radius=node_r, pos=pos, fillColor=(1,1,1), lineColor=(-1,-1,-1), lineWidth=4))
        labels.append(visual.TextStim(win=win, text=str(i), font=CJK_FONT, pos=pos, color=(-1,-1,-1), height=font_h, bold=True))
    
    # 高亮环也相应变大
    hl = visual.Circle(win=win, radius=node_r+15, lineColor=(-0.1,-0.6,-0.1), lineWidth=8, fillColor=None)
    
    instr_txt = visual.TextStim(win, text="练习：请依次连接 1 → 2 → 3 → 4", font=CJK_FONT, pos=(0, canvas_h*0.42), color=(-0.5,-0.5,-0.5), height=30)

    mouse = ensure_cursor(win, visible=True)
    mouse.clickReset()
    
    current_target = 0 
    drawing = False
    current_path = []
    completed_segments = []
    raw_data = []
    start_t = core.getTime()
    
    event.clearEvents()
    
    while current_target < 3: 
        if "escape" in event.getKeys(): return "escape"
        
        win.clearBuffer()
        instr_txt.draw()
        
        # 绘制线段 (位于节点下方)
        for seg in completed_segments:
            if len(seg) > 1:
                visual.ShapeStim(win, vertices=seg, lineColor=(-0.15,-0.15,-0.15), lineWidth=line_w, closeShape=False).draw()
        if drawing and len(current_path) > 1:
            visual.ShapeStim(win, vertices=current_path, lineColor=(-0.15,-0.15,-0.15), lineWidth=line_w, closeShape=False).draw()
            
        # 绘制节点
        for c in circles: c.draw()
        for l in labels: l.draw()
        
        # 高亮当前起点
        hl.pos = positions[current_target]
        hl.draw()
        
        win.flip()
        
        pressed = mouse.getPressed()[0]
        pos = mouse.getPos()
        raw_data.append([core.getTime()-start_t, pos[0], pos[1], int(pressed)])
        
        # 判定逻辑 (判定范围也随半径增大)
        hit_threshold = node_r * 1.3 
        
        if pressed:
            if not drawing:
                # 点击起点
                if math.hypot(pos[0]-positions[current_target][0], pos[1]-positions[current_target][1]) < hit_threshold:
                    drawing = True
                    current_path = [positions[current_target], pos]
            else:
                # 拖动中
                if math.hypot(pos[0]-current_path[-1][0], pos[1]-current_path[-1][1]) > 2.0:
                    current_path.append(pos)
                
                # 检查是否击中下一个点
                next_idx = current_target + 1
                if math.hypot(pos[0]-positions[next_idx][0], pos[1]-positions[next_idx][1]) < hit_threshold:
                    current_path.append(positions[next_idx])
                    completed_segments.append(current_path)
                    current_target += 1
                    
                    if current_target < 3:
                        current_path = [positions[current_target]]
                    else:
                        drawing = False
        else:
            drawing = False
            current_path = []

    # 保存练习数据
    try:
        p_dir = os.path.join(results_root, "PRACTICE")
        os.makedirs(p_dir, exist_ok=True)
        with open(os.path.join(p_dir, f"{subject_id}_{session_id}_practice.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time", "x", "y", "pressed"])
            w.writerows(raw_data)
    except: pass
    # 5. 正式任务提示 (2.png；若缺失则回退 all_3.png)
    img_formal = os.path.join(root_dir, "stimuli", "zdy", "2.png")
    if os.path.exists(img_formal):
        if show_image_wait(win, img_formal) == "escape": return "escape"
    else:
        img_3 = os.path.join(root_dir, "stimuli", "zdy", "all_3.png")
        if os.path.exists(img_3):
            if show_image_wait(win, img_3) == "escape": return "escape"

    return "ok"


# -------------- 主函数 --------------
def main() -> int:
    ap = argparse.ArgumentParser(description="DTMT run_all (Fixed)")
    ap.add_argument("--subject", type=str, default="", help="被试编号")
    ap.add_argument("--session", type=str, default="", help="会话编号")
    ap.add_argument("--age", type=str, default="", help="年龄")
    ap.add_argument("--group", type=int, choices=[1, 2], default=1, help="组别(1:B3->B4, 2:B4->B3)")
    ap.add_argument("--layout", type=int, default=0, help="布局(0=auto)")
    ap.add_argument("--windowed", action="store_true", help="窗口模式")
    ap.add_argument("--screen", type=int, default=0, help="屏幕索引")
    ap.add_argument("--hard_limit", type=float, default=40.0, help="限时(秒)")
    args = ap.parse_args()

    project_root = resolve_project_root()
    print(f"[INFO] Project Root: {project_root}")

    if not args.subject:
        _dlg_info = {"被试编号": ""}
        if not gui.DlgFromDict(_dlg_info, title="TMT 注意力转换").OK:
            return 1
        args.subject = _dlg_info["被试编号"].strip() or "S001"
    info = {"subject_id": args.subject, "session_id": args.session or "SES1", "age": args.age or "", "group": int(args.group)}

    sid = str(info["subject_id"]).strip()
    sess = str(info["session_id"]).strip()
    age = str(info["age"]).strip()
    grp = int(info["group"])
    layout_id = int(args.layout) if args.layout in (1, 2, 3) else stable_layout_id_from_subject(sid)

    results_root = os.path.join(project_root, "results")
    log_path = os.path.join(results_root, f"{sid}_{sess}_runall_log.txt")
    
    img_rest = os.path.join(project_root, "stimuli", "zdy", "3.png")
    if not os.path.exists(img_rest):
        img_rest = os.path.join(project_root, "stimuli", "zdy", "A0_2.png")
    img_end_all = os.path.join(project_root, "stimuli", "zdy", "all_4.png")

    win = visual.Window(
        fullscr=(not args.windowed),
        screen=int(args.screen),
        units="pix",
        color=(1, 1, 1),
        allowGUI=bool(args.windowed),
        size=(1024, 768)
    )
    
    aborted = False

    try:
        event.globalKeys.clear()
        append_log(log_path, f"[START] {now_str()} Subj={sid} Group={grp} Layout={layout_id}")

        # === 1. 练习环节 ===
        ret = run_practice_1234(win, sid, sess, age, layout_id, results_root, project_root)
        if ret == "escape": aborted = True

        # === 2. 正式任务 ===
        if not aborted:
            hard = float(args.hard_limit)
            a1_style = "bw" if grp == 1 else "color" 
            b_order_str = "B3B4" if grp == 1 else "B4B3"
            
            tasks = [
                ("A0", A0.run_a0, {}),
                ("B2", B2.run_b2, {"show_start_wait": True}),
                ("B1", B1.run_b1, {"show_start_wait": True}),
                ("A1", A1.run_a1, {"style": a1_style, "b_order": b_order_str, "show_start_wait": True}),
            ]
            if grp == 1:
                tasks.append(("B3", B3.run_b3, {}))
                tasks.append(("B4", B4.run_b4, {}))
            else:
                tasks.append(("B4", B4.run_b4, {}))
                tasks.append(("B3", B3.run_b3, {}))

            total_tasks = len(tasks)
            for idx, (name, func, kw) in enumerate(tasks):
                if aborted: break
                append_log(log_path, f"[RUN] {name}")
                ensure_cursor(win, visible=True)
                event.clearEvents()
                
                func(
                    win=win,
                    subject_id=sid,
                    session_id=sess,
                    age=age,
                    layout_id=layout_id,
                    hard_limit_s=hard,
                    windowed=args.windowed,
                    y_origin_top=True,
                    **kw
                )
                
                # 任务间休息 (A0_2.png)
                # ★ 优化：min_wait 设为 0.5s，休息够了按一下就走，不用多按
                if idx < total_tasks - 1:
                    ret = show_image_wait(win, img_rest, min_wait=0.5)
                    if ret == "escape": aborted = True; break

        # === 3. 最终结束 (all_4.png) ===
        if not aborted:
            print(f"[INFO] Showing Final Screen: {img_end_all}")
            append_log(log_path, "[INFO] Final Screen")
            # ★ 优化：最终页 min_wait 设为 0.5s，确保不误触退出，但也足够灵敏
            show_image_wait(win, img_end_all, key_list=["space", "return"], allow_escape=True, min_wait=0.5)
            
        append_log(log_path, f"[END] {now_str()} Finished.")

    except Exception as e:
        print(f"[ERROR] {e}")
        append_log(log_path, f"[ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        try: win.close()
        except: pass
        core.quit()

if __name__ == "__main__":
    try: main()
    except SystemExit: pass
    except Exception: core.quit()