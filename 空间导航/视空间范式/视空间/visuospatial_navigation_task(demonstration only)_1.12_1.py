#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Visuospatial navigation (path integration) task 
Modified: Formal phase structure update & Screen masking
"""

import argparse
import csv
import math
import os
import sys
from datetime import datetime

# numpy is used for math
import numpy as np

try:
    from psychopy import core, event, gui, visual
except Exception as exc:
    print("ERROR: PsychoPy is required to run this script.")
    print(f"Import error: {exc}")
    sys.exit(1)


def deg_wrap(angle_deg):
    """Wrap angle to [-180, 180]."""
    while angle_deg > 180:
        angle_deg -= 360
    while angle_deg < -180:
        angle_deg += 360
    return angle_deg


def generate_fixed_path_points(start_xy, heading, turns, lengths_m, px_per_m):
    points = [start_xy]
    cur_x, cur_y = start_xy
    cur_heading = heading
    lengths_px = [l * px_per_m for l in lengths_m]

    for idx, seg_len in enumerate(lengths_px):
        rad = math.radians(cur_heading)
        next_x = cur_x + math.cos(rad) * seg_len
        next_y = cur_y + math.sin(rad) * seg_len
        points.append((next_x, next_y))
        cur_x, cur_y = next_x, next_y

        if idx < len(turns):
            if turns[idx] == "L":
                cur_heading += 90
            elif turns[idx] == "R":
                cur_heading -= 90
    
    return points


def shift_points_to_center(points, target_xy=(0, 0)):
    end_x, end_y = points[-1]
    dx = target_xy[0] - end_x
    dy = target_xy[1] - end_y
    shifted = [(x + dx, y + dy) for x, y in points]
    return shifted

    
def draw_grid_lines(win, grid_spacing_px, line_color, masks=None, line_width=2):
    """Draw a full-screen grid aligned to the window center, optionally with masks."""
    
    background = visual.Rect(win, width=win.size[0]*2, height=win.size[1]*2, 
                             fillColor=[1, 1, 1], lineColor=None)
    background.draw()
    
    half_w = win.size[0] / 2
    half_h = win.size[1] / 2

    # Vertical lines
    x = -half_w
    while x <= half_w:
        line = visual.Line(win, start=(x, -half_h), end=(x, half_h),
                           lineColor=line_color, lineWidth=line_width)
        line.draw()
        x += grid_spacing_px

    # Horizontal lines
    y = -half_h
    while y <= half_h:
        line = visual.Line(win, start=(-half_w, y), end=(half_w, y),
                           lineColor=line_color, lineWidth=line_width)
        line.draw()
        y += grid_spacing_px
    
    # Draw screen masks (if any)
    if masks:
        for mask in masks:
            mask.draw()


def draw_local_grid(win, world_pos, window_size_px, grid_spacing_px, line_color, mask_bg, masks=None, line_width=2):
    """Draw the local view window, and apply screen masks on top."""
    half_w = window_size_px / 2
    half_h = window_size_px / 2
    
    world_left = world_pos[0] - half_w
    world_right = world_pos[0] + half_w
    world_bottom = world_pos[1] - half_h
    world_top = world_pos[1] + half_h

    # 1. Background mask 
    mask_bg.draw()

    # 2. Local window background
    window_bg = visual.Rect(win, width=window_size_px, height=window_size_px,
                            pos=(0, 0), fillColor=[1, 1, 1], lineColor=None)
    window_bg.draw()

    # 3. Grid lines inside local window
    inset = 2 
    start_x = math.floor(world_left / grid_spacing_px) * grid_spacing_px
    x = start_x
    while x <= world_right:
        screen_x = x - world_pos[0]
        if -half_w < screen_x < half_w:
            line = visual.Line(win, 
                               start=(screen_x, -half_h + inset),
                               end=(screen_x, half_h - inset),
                               lineColor=line_color, lineWidth=line_width)
            line.draw()
        x += grid_spacing_px

    start_y = math.floor(world_bottom / grid_spacing_px) * grid_spacing_px
    y = start_y
    while y <= world_top:
        screen_y = y - world_pos[1]
        if -half_h < screen_y < half_h:
            line = visual.Line(win, 
                               start=(-half_w + inset, screen_y),
                               end=(half_w - inset, screen_y),
                               lineColor=line_color, lineWidth=line_width)
            line.draw()
        y += grid_spacing_px

    # 4. Border
    border = visual.Rect(win, width=window_size_px, height=window_size_px,
                         pos=(0, 0), lineColor=[0.3, 0.3, 0.3], fillColor=None,
                         lineWidth=3)
    border.draw()

    # 5. Screen Masks
    if masks:
        for mask in masks:
            mask.draw()


def move_dot_along_path(win, marker, points, speed_px_s, draw_local_func, heading_offset_deg):
    """Animate marker along path points (Local View)."""
    total_duration = 0.0
    for i in range(len(points) - 1):
        start = points[i]
        end = points[i + 1]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        heading_deg = math.degrees(math.atan2(dy, dx))
        marker_heading = -heading_deg + heading_offset_deg
        seg_len = math.hypot(dx, dy)
        if seg_len <= 0:
            continue
        seg_time = seg_len / speed_px_s
        total_duration += seg_time

        seg_clock = core.Clock()
        while True:
            t = seg_clock.getTime()
            if t >= seg_time:
                break
            frac = t / seg_time
            world_pos = (start[0] + dx * frac, start[1] + dy * frac)
            
            draw_local_func(world_pos)
            
            marker.pos = (0, 0)
            marker.ori = marker_heading
            marker.draw()
            win.flip()
            if "escape" in event.getKeys():
                core.quit()

        # End of segment
        draw_local_func(end)
        marker.pos = (0, 0)
        marker.ori = marker_heading
        marker.draw()
        win.flip()

    return total_duration


def demo_move_and_trace(win, marker, trace_line, points, speed_px_s, draw_global_bg_func, heading_offset_deg):
    """
    Animate marker along path points (Global View) AND draw the trail.
    """
    total_duration = 0.0
    current_trail = [points[0]]
    
    for i in range(len(points) - 1):
        start = points[i]
        end = points[i + 1]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        heading_deg = math.degrees(math.atan2(dy, dx))
        marker_heading = -heading_deg + heading_offset_deg
        seg_len = math.hypot(dx, dy)
        if seg_len <= 0:
            continue
        seg_time = seg_len / speed_px_s
        total_duration += seg_time

        seg_clock = core.Clock()
        while True:
            t = seg_clock.getTime()
            if t >= seg_time:
                break
            frac = t / seg_time
            
            curr_x = start[0] + dx * frac
            curr_y = start[1] + dy * frac
            current_pos = (curr_x, curr_y)
            
            trace_vertices = current_trail + [current_pos]
            trace_line.vertices = trace_vertices
            
            draw_global_bg_func() 
            trace_line.draw()
            
            marker.pos = current_pos
            marker.ori = marker_heading
            marker.draw()
            
            win.flip()
            if "escape" in event.getKeys():
                core.quit()

        current_trail.append(end)
        trace_line.vertices = current_trail
        
        draw_global_bg_func()
        trace_line.draw()
        marker.pos = end
        marker.ori = marker_heading
        marker.draw()
        win.flip()

    return total_duration


def make_continue_button(win, pos=(0, -400), font="PingFang SC"):
    """Create a reusable '继续' button. Returns (rect, label, colors)."""
    colors = {
        'normal': [0.1, 0.55, 0.82],
        'hover': [0.25, 0.68, 0.95],
        'pressed': [-0.1, 0.35, 0.62],
    }
    rect = visual.Rect(
        win, width=200, height=60, pos=pos,
        fillColor=colors['normal'], lineWidth=0)
    label = visual.TextStim(
        win, text="继续", pos=pos, color=[1, 1, 1],
        height=28, bold=True, font=font)
    return rect, label, colors


def wait_for_button_or_space(win, mouse, draw_bg_func=None,
                             btn_pos=(0, -400), font="PingFang SC"):
    """Draw a '继续' button, wait for click or space. draw_bg_func redraws the background each frame."""
    btn_rect, btn_label, colors = make_continue_button(win, pos=btn_pos, font=font)
    prev_pressed = True
    event.clearEvents()
    while True:
        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            core.quit()
        if "space" in keys:
            return

        mouse_pos = mouse.getPos()
        hovering = btn_rect.contains(mouse_pos)
        curr = mouse.getPressed()[0]

        if curr and not prev_pressed and hovering:
            if draw_bg_func:
                draw_bg_func()
            btn_rect.fillColor = colors['pressed']
            btn_rect.draw()
            btn_label.draw()
            win.flip()
            core.wait(0.1)
            return

        if draw_bg_func:
            draw_bg_func()
        btn_rect.fillColor = colors['hover'] if hovering else colors['normal']
        btn_rect.draw()
        btn_label.draw()
        win.flip()
        prev_pressed = curr
        core.wait(0.016, hogCPUperiod=0)


def show_instruction(win, title, body="", hint="",
                     screen_masks=None, font="PingFang SC", mouse=None):
    """Display a structured instruction screen: title / body / button."""
    bg = visual.Rect(win, width=win.size[0] * 2, height=win.size[1] * 2,
                     fillColor=[1, 1, 1], lineColor=None)
    title_stim = visual.TextStim(
        win, text=title, pos=(0, 300), color=[-0.8, -0.8, -0.8],
        height=46, bold=True, wrapWidth=900, font=font, alignText='center')
    body_stim = visual.TextStim(
        win, text=body, pos=(0, 20), color=[-0.3, -0.3, -0.3],
        height=32, wrapWidth=820, font=font, alignText='center')
    if hint:
        hint_stim = visual.TextStim(
            win, text=hint, pos=(0, -330), color=[0.4, 0.4, 0.4],
            height=24, wrapWidth=800, font=font, alignText='center')

    def draw_frame():
        bg.draw()
        title_stim.draw()
        if body:
            body_stim.draw()
        if hint:
            hint_stim.draw()
        if screen_masks:
            for m in screen_masks:
                m.draw()

    if mouse is None:
        # No mouse — static frame + keyboard fallback
        btn_rect, btn_label, _ = make_continue_button(win, font=font)
        draw_frame()
        btn_rect.draw()
        btn_label.draw()
        win.flip()
        event.waitKeys(keyList=["space"])
        return

    wait_for_button_or_space(win, mouse, draw_bg_func=draw_frame, font=font)


def run_task(check_only=False, subject_id=None):
    # Task parameters
    px_per_m = 90
    speed_px_s = 90
    grid_spacing_px = 40
    local_window_px = 220
    grid_color = [0.5, 0.5, 0.5]
    grid_line_width = 2
    arrow_heading_offset = 0
    iti_s = 2.0

    # --- FIXED TRIALS DATA ---
    fixed_trials_data = [
        # Demo Phase
        {'id': 1, 'phase': 'demo', 'turnCount': 0, 'turns': [], 'lengths': [3], 'heading': 335, 'start_xy': (-244.70, 114.11), 'label': '不转向'},
        {'id': 2, 'phase': 'demo', 'turnCount': 1, 'turns': ['L'], 'lengths': [4, 2], 'heading': 45, 'start_xy': (-127.28, -381.84), 'label': '转向1次'},
        {'id': 3, 'phase': 'demo', 'turnCount': 2, 'turns': ['R', 'L'], 'lengths': [5, 2, 3], 'heading': 195, 'start_xy': (742.05, 12.48), 'label': '转向2次'},
        {'id': 4, 'phase': 'demo', 'turnCount': 3, 'turns': ['L', 'R', 'L'], 'lengths': [2, 3, 4, 5], 'heading': 105, 'start_xy': (835.23, -335.25), 'label': '转向3次'},

        # Practice Phase
        {'id': 5, 'phase': 'practice', 'turnCount': 1, 'turns': ['L'], 'lengths': [2, 4], 'heading': 225, 'start_xy': (-127.28, 381.84)},
        {'id': 6, 'phase': 'practice', 'turnCount': 1, 'turns': ['R'], 'lengths': [4, 3], 'heading': 245, 'start_xy': (396.85, 212.16)},

        # Formal Phase - Level 1 (0 turns)
        {'id': 7, 'phase': 'formal', 'turnCount': 0, 'turns': [], 'lengths': [2], 'heading': 140, 'start_xy': (137.89, -115.70)},
        {'id': 8, 'phase': 'formal', 'turnCount': 0, 'turns': [], 'lengths': [3], 'heading': 75, 'start_xy': (-69.88, -260.80)},
        {'id': 9, 'phase': 'formal', 'turnCount': 0, 'turns': [], 'lengths': [4], 'heading': 280, 'start_xy': (-62.51, 354.53)},
        {'id': 10, 'phase': 'formal', 'turnCount': 0, 'turns': [], 'lengths': [5], 'heading': 315, 'start_xy': (-318.20, 318.20)},

        # Formal Phase - Level 2 (1 turn)
        {'id': 11, 'phase': 'formal', 'turnCount': 1, 'turns': ['L'], 'lengths': [3, 3], 'heading': 10, 'start_xy': (-219.01, -312.78)},
        {'id': 12, 'phase': 'formal', 'turnCount': 1, 'turns': ['L'], 'lengths': [4, 3], 'heading': 170, 'start_xy': (401.42, 203.38)},
        {'id': 13, 'phase': 'formal', 'turnCount': 1, 'turns': ['R'], 'lengths': [2, 5], 'heading': 295, 'start_xy': (331.77, 353.31)},
        {'id': 14, 'phase': 'formal', 'turnCount': 1, 'turns': ['R'], 'lengths': [4, 2], 'heading': 25, 'start_xy': (-402.34, 10.99)},

        # Formal Phase - Level 3 (2 turns)
        {'id': 15, 'phase': 'formal', 'turnCount': 2, 'turns': ['L', 'R'], 'lengths': [4, 2, 4], 'heading': 155, 'start_xy': (728.61, -141.15)},
        {'id': 16, 'phase': 'formal', 'turnCount': 2, 'turns': ['L', 'R'], 'lengths': [3, 5, 2], 'heading': 325, 'start_xy': (-626.73, -110.51)},
        {'id': 17, 'phase': 'formal', 'turnCount': 2, 'turns': ['R', 'L'], 'lengths': [2, 4, 3], 'heading': 350, 'start_xy': (-380.65, 432.67)},
        {'id': 18, 'phase': 'formal', 'turnCount': 2, 'turns': ['R', 'L'], 'lengths': [3, 4, 3], 'heading': 200, 'start_xy': (630.56, -153.60)},

        # Formal Phase - Level 4 (3 turns)
        {'id': 19, 'phase': 'formal', 'turnCount': 3, 'turns': ['L', 'R', 'L'], 'lengths': [3, 3, 5, 2], 'heading': 125, 'start_xy': (781.59, -331.68)},
        {'id': 20, 'phase': 'formal', 'turnCount': 3, 'turns': ['L', 'R', 'L'], 'lengths': [3, 2, 4, 3], 'heading': 355, 'start_xy': (-666.82, -393.38)},
        {'id': 21, 'phase': 'formal', 'turnCount': 3, 'turns': ['R', 'L', 'R'], 'lengths': [2, 4, 2, 4], 'heading': 65, 'start_xy': (-804.68, -21.99)},
        {'id': 22, 'phase': 'formal', 'turnCount': 3, 'turns': ['R', 'L', 'R'], 'lengths': [4, 2, 4, 3], 'heading': 5, 'start_xy': (-756.48, 385.54)},
    ]

    if check_only:
        print("Check mode.")
        return

    if subject_id:
        participant_id = subject_id
    else:
        dlg = gui.Dlg(title="视空间导航任务")
        dlg.addField("被试编号:")
        dlg.show()
        if not dlg.OK:
            core.quit()
        participant_id = dlg.data[0].strip()
        if not participant_id:
            print("ERROR: ID is required.")
            core.quit()

    win = visual.Window(
        size=[1920, 1080],
        color=[1, 1, 1],
        units="pix",
        fullscr=False,
        allowGUI=True,
        useRetina=False,
    )

    # === Screen Masking for 1200p compatibility ===
    actual_w, actual_h = win.size
    screen_masks = []
    if actual_h > 1080:
        diff = actual_h - 1080
        bar_height = diff / 2
        top_y = 540 + (bar_height / 2)
        bottom_y = -540 - (bar_height / 2)
        top_mask = visual.Rect(win, width=actual_w, height=bar_height,
                               pos=(0, top_y),
                               fillColor=[-1, -1, -1], lineColor=None)
        bottom_mask = visual.Rect(win, width=actual_w, height=bar_height,
                                  pos=(0, bottom_y),
                                  fillColor=[-1, -1, -1], lineColor=None)
        screen_masks = [top_mask, bottom_mask]

    # Stimuli
    arrow_vertices = [
        (-18, -10), (0, -10), (0, -20), (20, 0), (0, 20), (0, 10), (-18, 10)
    ]
    marker = visual.ShapeStim(
        win,
        vertices=arrow_vertices,
        fillColor=[-1, 1, -1], 
        lineColor=[-1, 1, -1],
        lineWidth=1
    )

    end_marker = visual.Circle(
        win,
        radius=15,
        fillColor=[0, 0, 0], 
        lineColor=[0, 0, 0],
        edges=128
    )

    feedback_marker = visual.Circle(
        win,
        radius=15,
        fillColor=[1, -1, -1], 
        lineColor=[1, -1, -1],
        edges=128
    )
    
    # Fixation Cross
    fixation = visual.ShapeStim(
        win,
        vertices='cross',
        size=40, 
        lineColor=[0, 0, 0],
        fillColor=[0, 0, 0],
        lineWidth=2
    )

    trace_line = visual.ShapeStim(
        win,
        vertices=[(0, 0)], 
        lineColor=[0, 0, 0],
        lineWidth=3,
        closeShape=False,
        autoLog=False
    )

    instr = visual.TextStim(
        win,
        text="",
        pos=(0, 320),
        color=[0, 0, 0],
        height=36,
        wrapWidth=1000,
        font="PingFang SC",
    )

    mask_bg = visual.Rect(
        win,
        width=win.size[0] * 2,
        height=win.size[1] * 2,
        fillColor=[-1, -1, -1], 
        lineColor=None
    )

    mouse = event.Mouse(win=win)
    mouse.setVisible(True)

    data_dir = os.path.join(os.getcwd(), "data")
    os.makedirs(data_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    data_path = os.path.join(data_dir, f"visuospatial_navigation_{participant_id}_{ts}.csv")

    fieldnames = [
        "participantId", "sessionId", "phase", "trialIndex", "pathId",
        "turnCount", "turnDirections", "turnAnglesDeg", "segmentLengthsM",
        "totalPathLengthM", "startX", "startY", "endX", "endY",
        "movementDurationMs", "speedPxPerS", "gridSpacingPx", "localWindowPx",
        "clickX", "clickY", "clickRTms",
        "distanceErrorPx", "distanceErrorM", "angleErrorDeg", "deviceInfo",
    ]

    with open(data_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        trial_counter = 0
        session_id = ts
        device_info = f"{win.size[0]}x{win.size[1]}"

        # --- Intro ---
        show_instruction(
            win, mouse=mouse,
            title="欢迎参加导航游戏！",
            body=(
                "你将观看一段移动路径\n"
                "请专心观察，移动结束后找到起点\n\n"
                "游戏包含三个阶段：\n"
                "①  演示 — 观察路径移动，熟悉全局视角\n"
                "②  练习 — 熟悉操作，有反馈提示\n"
                "③  正式 — 专心完成任务，无反馈"
            ),
            screen_masks=screen_masks,
        )

        total_formal_trials = sum(1 for t in fixed_trials_data if t['phase'] == 'formal')
        demo_idx = 0
        practice_idx = 0
        formal_idx = 0

        for trial in fixed_trials_data:
            trial_counter += 1
            phase = trial['phase']
            path_id = trial['id']
            turn_count = trial['turnCount']
            turns = trial['turns']
            lengths_m = trial['lengths']
            heading = trial['heading']
            start_xy = trial['start_xy']
            
            # --- Path Generation ---
            raw_points = generate_fixed_path_points(
                start_xy,
                heading,
                turns,
                lengths_m,
                px_per_m
            )
            points = shift_points_to_center(raw_points, target_xy=(0, 0))
            actual_start_xy = points[0]
            end_xy = points[-1]

            if phase == "demo":
                # === DEMO PHASE ===
                demo_idx += 1
                
                if demo_idx == 1:
                    show_instruction(
                        win, mouse=mouse,
                        title="演示阶段",
                        body=(
                            "屏幕上的绿色箭头代表你自己\n\n"
                            "请盯着箭头，观察它的移动路线\n"
                            "移动停止后，记住起点在哪里"
                        ),
                        screen_masks=screen_masks,
                    )
                    
                label = trial.get("label", "")
                instr.text = f"现在演示移动过程，当前{label}，请认真观察移动过程。"
                
                
                # Draw initial
                draw_grid_lines(win, grid_spacing_px, line_color=grid_color, masks=screen_masks, line_width=grid_line_width)
                instr.draw()
                marker.pos = actual_start_xy
                marker.ori = 0
                marker.draw()
                win.flip()
                core.wait(1.5)

                def draw_demo_bg():
                    draw_grid_lines(win, grid_spacing_px, line_color=grid_color, masks=screen_masks, line_width=grid_line_width)
                    instr.draw()

                demo_move_and_trace(
                    win, marker, trace_line, points, speed_px_s,
                    draw_global_bg_func=draw_demo_bg,
                    heading_offset_deg=arrow_heading_offset
                )

                # Feedback
                instr.text = "演示结束：红色圆点为真实起点"

                def draw_demo_feedback():
                    draw_grid_lines(win, grid_spacing_px, line_color=grid_color, masks=screen_masks, line_width=grid_line_width)
                    trace_line.draw()
                    feedback_marker.pos = actual_start_xy
                    feedback_marker.draw()
                    instr.draw()

                wait_for_button_or_space(win, mouse, draw_bg_func=draw_demo_feedback, btn_pos=(0, -450))

            elif phase == "practice":
                # === PRACTICE PHASE (Keep instructions and feedback) ===
                practice_idx += 1
                
                if practice_idx == 1:
                    show_instruction(
                        win, mouse=mouse,
                        title="练习阶段",
                        body=(
                            "接下来，视野会跟随箭头移动\n"
                            "只能看到局部画面，轨迹线也会消失\n\n"
                            "移动结束后\n"
                            "请在完整画面中点击你出发的位置"
                        ),
                        screen_masks=screen_masks,
                    )
                    
                # Global Grid Instruction
                draw_grid_lines(win, grid_spacing_px, line_color=grid_color, masks=screen_masks, line_width=grid_line_width)
                win.flip()
                core.wait(1.0)

                # Start Display
                draw_local_grid(win, actual_start_xy, local_window_px, grid_spacing_px,
                                line_color=grid_color, mask_bg=mask_bg, masks=screen_masks, line_width=grid_line_width)
                marker.pos = (0, 0)
                marker.ori = 0
                marker.draw()
                win.flip()
                core.wait(1.5)

                # Move
                movement_time = move_dot_along_path(
                    win, marker, points, speed_px_s,
                    draw_local_func=lambda pos: draw_local_grid(
                        win, pos, local_window_px, grid_spacing_px,
                        line_color=grid_color, mask_bg=mask_bg, masks=screen_masks, line_width=grid_line_width
                    ),
                    heading_offset_deg=arrow_heading_offset,
                )

                # Response
                if practice_idx == 1:
                    show_instruction(
                        win, mouse=mouse,
                        title="移动结束",
                        body=(
                            "请在屏幕上点击你认为的出发位置\n\n"
                            "点击后会显示红色圆点\n"
                            "那是真正的起点"
                        ),
                        screen_masks=screen_masks,
                    )
                
                draw_grid_lines(win, grid_spacing_px, line_color=grid_color, masks=screen_masks, line_width=grid_line_width)
                end_marker.pos = (0, 0)
                end_marker.draw()
                instr.text = "请点击起点位置"
                instr.draw()
                win.flip()

                # Collect response
                mouse.clickReset()
                rt_clock = core.Clock()
                click_pos = None
                while click_pos is None:
                    if "escape" in event.getKeys():
                        core.quit()
                    buttons, times = mouse.getPressed(getTime=True)
                    if buttons[0]:
                        click_pos = mouse.getPos()
                click_rt = rt_clock.getTime() * 1000
                click_x, click_y = click_pos

                # 6. Feedback
                dist_error_px = math.hypot(click_x - actual_start_xy[0], click_y - actual_start_xy[1])
                dist_error_m = dist_error_px / px_per_m
                click_vec_x = click_x - end_xy[0]
                click_vec_y = click_y - end_xy[1]
                click_angle = math.degrees(math.atan2(click_vec_y, click_vec_x))
                correct_angle = math.degrees(math.atan2(actual_start_xy[1] - end_xy[1], actual_start_xy[0] - end_xy[0]))
                angle_error = deg_wrap(click_angle - correct_angle)

                draw_grid_lines(win, grid_spacing_px, line_color=grid_color, masks=screen_masks, line_width=grid_line_width)
                feedback_marker.pos = actual_start_xy
                feedback_marker.draw()
                instr.text = "红色圆点为正确位置"
                instr.draw()
                win.flip()
                core.wait(1.5)

            else:
                # === FORMAL PHASE (New Structure) ===
                formal_idx += 1
                # Instruction before first formal trial
                if formal_idx == 1:
                    show_instruction(
                        win, mouse=mouse,
                        title="正式阶段",
                        body=(
                            "练习结束，做得不错！\n\n"
                            "正式阶段不再显示反馈\n"
                            "请专心观察每一段路径"
                        ),
                        screen_masks=screen_masks,
                    )

                # 1. Fixation (1s)
                fixation.draw()
                if screen_masks: [m.draw() for m in screen_masks]
                win.flip()
                core.wait(1.0)

                # 2. Global Grid Familiarization (1s, No Text)
                draw_grid_lines(win, grid_spacing_px, line_color=grid_color, masks=screen_masks, line_width=grid_line_width)
                win.flip()
                core.wait(1.0)

                # 3. Local View Start (1.5s, No Text)
                draw_local_grid(win, actual_start_xy, local_window_px, grid_spacing_px,
                                line_color=grid_color, mask_bg=mask_bg, masks=screen_masks, line_width=grid_line_width)
                marker.pos = (0, 0)
                marker.ori = 0
                marker.draw()
                win.flip()
                core.wait(1.5)

                # 4. Movement
                movement_time = move_dot_along_path(
                    win, marker, points, speed_px_s,
                    draw_local_func=lambda pos: draw_local_grid(
                        win, pos, local_window_px, grid_spacing_px,
                        line_color=grid_color, mask_bg=mask_bg, masks=screen_masks, line_width=grid_line_width
                    ),
                    heading_offset_deg=arrow_heading_offset,
                )

                # 5. End Pause (1s) - Show End State
                draw_local_grid(win, end_xy, local_window_px, grid_spacing_px,
                                line_color=grid_color, mask_bg=mask_bg, masks=screen_masks, line_width=grid_line_width)
                marker.pos = (0, 0)
                marker.ori = 0 
                core.wait(1.0)

                # 6. Response Phase
                draw_grid_lines(win, grid_spacing_px, line_color=grid_color, masks=screen_masks, line_width=grid_line_width)
                end_marker.pos = (0, 0)
                end_marker.draw()
                instr.text = "请点击起点位置"
                instr.draw()
                win.flip()

                # Collect Response
                mouse.clickReset()
                rt_clock = core.Clock()
                click_pos = None
                while click_pos is None:
                    if "escape" in event.getKeys():
                        core.quit()
                    buttons, times = mouse.getPressed(getTime=True)
                    if buttons[0]:
                        click_pos = mouse.getPos()
                click_rt = rt_clock.getTime() * 1000
                click_x, click_y = click_pos

                # Calculate metrics (but no feedback shown)
                dist_error_px = math.hypot(click_x - actual_start_xy[0], click_y - actual_start_xy[1])
                dist_error_m = dist_error_px / px_per_m
                click_vec_x = click_x - end_xy[0]
                click_vec_y = click_y - end_xy[1]
                click_angle = math.degrees(math.atan2(click_vec_y, click_vec_x))
                correct_angle = math.degrees(math.atan2(actual_start_xy[1] - end_xy[1], actual_start_xy[0] - end_xy[0]))
                angle_error = deg_wrap(click_angle - correct_angle)

                # 7. ITI (2s) - Blank Screen
                # Skip if it's the very last trial
                if formal_idx != total_formal_trials:
                    if screen_masks: [m.draw() for m in screen_masks]
                    win.flip() # clear screen to background color (white) + masks
                    core.wait(iti_s)


            # Log Data (Common for all phases)
            writer.writerow({
                "participantId": participant_id,
                "sessionId": session_id,
                "phase": phase,
                "trialIndex": trial_counter,
                "pathId": path_id,
                "turnCount": turn_count,
                "turnDirections": "-".join(turns),
                "turnAnglesDeg": "-".join(["90"] * turn_count),
                "segmentLengthsM": ";".join([str(l) for l in lengths_m]),
                "totalPathLengthM": sum(lengths_m),
                "startX": f"{actual_start_xy[0]:.2f}",
                "startY": f"{actual_start_xy[1]:.2f}",
                "endX": f"{end_xy[0]:.2f}",
                "endY": f"{end_xy[1]:.2f}",
                "movementDurationMs": int(movement_time * 1000) if 'movement_time' in locals() else 0,
                "speedPxPerS": speed_px_s,
                "gridSpacingPx": grid_spacing_px,
                "localWindowPx": local_window_px,
                "clickX": f"{click_x:.2f}" if phase != 'demo' else "",
                "clickY": f"{click_y:.2f}" if phase != 'demo' else "",
                "clickRTms": int(click_rt) if phase != 'demo' else "",
                "distanceErrorPx": f"{dist_error_px:.2f}" if phase != 'demo' else "",
                "distanceErrorM": f"{dist_error_m:.3f}" if phase != 'demo' else "",
                "angleErrorDeg": f"{angle_error:.2f}" if phase != 'demo' else "",
                "deviceInfo": device_info,
            })

    bg = visual.Rect(win, width=win.size[0] * 2, height=win.size[1] * 2,
                     fillColor=[1, 1, 1], lineColor=None)
    end_title = visual.TextStim(
        win, text="游戏结束，谢谢参与！", pos=(0, 0),
        color=[-0.8, -0.8, -0.8], height=48, bold=True,
        wrapWidth=900, font="PingFang SC", alignText='center')
    bg.draw()
    end_title.draw()
    if screen_masks: [m.draw() for m in screen_masks]
    win.flip()
    core.wait(2.0)
    win.close()
    core.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Run a dry check without opening the window")
    parser.add_argument("--subject_id", type=str, default="", help="被试编号（传入后跳过对话框）")
    args = parser.parse_args()
    run_task(check_only=args.check, subject_id=args.subject_id or None)


if __name__ == "__main__":
    main()