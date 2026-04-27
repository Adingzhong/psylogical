# -*- coding: utf-8 -*-
"""
Clock Drawing Task (CDT) on Windows tablet (finger touch) in PsychoPy (Python/Standalone)
Clean runnable script (no code-generation leftovers).

Flow:
1) Show instru1 image  -> press SPACE
2) Show instru2 image  -> press SPACE
3) Enter drawing page  -> draw with finger (mouse press/drag)
   Buttons: Clear / Undo-last-stroke / Done

Outputs (saved under: data/<participant>/<session>/):
- *_traj.csv            (final/active trajectory) columns: t,x,y,stroke_id,is_drawing
- *_traj_raw.csv        (full log incl. undo) columns: t,x,y,stroke_id,is_drawing,is_active,event
- *_stroke_summary.csv  (per-stroke summary for final/active strokes)
- *_undo_events.csv     (undo events)
- *_final_ui.png        (UI + drawing screenshot)
- *_clock_only.png      (drawing-only screenshot)

Optional:
- Video recording via psychopy.hardware.camera.Camera (may fail depending on PsychoPy version/camera backend).

Important (Windows):
- Put instru1.png and instru2.png in the SAME folder as this .py file (recommended).
- If you put them elsewhere, set INSTRU1_IMAGE / INSTRU2_IMAGE to absolute paths.
"""

from psychopy import visual, core, event, gui
import argparse
import os, csv, platform
import numpy as np

# 中文字体
CN_FONT = "PingFang SC" if platform.system() == "Darwin" else "Microsoft YaHei"

# -----------------------
# Optional Camera API
# -----------------------
try:
    from psychopy.hardware.camera import Camera
    CAMERA_AVAILABLE = True
except Exception:
    CAMERA_AVAILABLE = False

# -----------------------
# Config
# -----------------------
FULLSCREEN = True
BG_COLOR = "white"
INK_COLOR = "black"
LINE_WIDTH = 7.0
MOVE_THRESH = 0.0015           # smaller => denser drawing
BOX_W, BOX_H = 1.25, 0.80      # drawing area size in 'height' units

# Instruction images (缩小以留出按钮空间)
INSTRU1_IMAGE = "instru1.png"
INSTRU1_IMAGE_SIZE = (1.3, 0.72)

INSTRU2_IMAGE = "instru2.png"
INSTRU2_IMAGE_SIZE = (1.3, 0.8)

# Video config (optional)
RECORD_VIDEO = False  # set True if you want to try recording
CAMERA_DEVICE_CANDIDATES = [0, 1, 2, 3]
CAMERA_LIB_PREFS = [None, "ffpyplayer", "opencv"]
VIDEO_FPS = 30
VIDEO_SIZE = (640, 480)

# Undo/status config
UNDO_COOLDOWN_SEC = 0.5
STATUS_FLASH_SEC = 2.0

# -----------------------
# Participant info
# -----------------------
_parser = argparse.ArgumentParser(description="CDT (Touch)")
_parser.add_argument("--subject_id", type=str, default="", help="被试编号（传入后跳过对话框）")
_parser.add_argument("--session", type=str, default="S001", help="会话编号")
_cli_args, _ = _parser.parse_known_args()

if _cli_args.subject_id:
    info = {"participant": _cli_args.subject_id, "session": _cli_args.session}
else:
    _dlg_info = {"被试编号": ""}
    dlg = gui.DlgFromDict(_dlg_info, title="画钟测试")
    if not dlg.OK:
        core.quit()
    info = {"participant": _dlg_info["被试编号"].strip() or "P001", "session": "S001"}

out_dir = os.path.join("data", info["participant"], info["session"])
os.makedirs(out_dir, exist_ok=True)

traj_path = os.path.join(out_dir, f"{info['participant']}_{info['session']}_traj.csv")
traj_raw_path = os.path.join(out_dir, f"{info['participant']}_{info['session']}_traj_raw.csv")
stroke_summary_path = os.path.join(out_dir, f"{info['participant']}_{info['session']}_stroke_summary.csv")
png_ui_path  = os.path.join(out_dir, f"{info['participant']}_{info['session']}_final_ui.png")
png_clock_only_path  = os.path.join(out_dir, f"{info['participant']}_{info['session']}_clock_only.png")
vid_path  = os.path.join(out_dir, f"{info['participant']}_{info['session']}_video.mp4")
meta_path = os.path.join(out_dir, f"{info['participant']}_{info['session']}_meta.txt")
undo_events_path = os.path.join(out_dir, f"{info['participant']}_{info['session']}_undo_events.csv")

# -----------------------
# Window & input
# -----------------------
win = visual.Window(size=(1280, 800), units="height", fullscr=FULLSCREEN, color=BG_COLOR)
mouse = event.Mouse(win=win)
mouse.setVisible(True)
global_clock = core.Clock()

# -----------------------
# UI elements
# -----------------------
draw_box = visual.Rect(win, width=BOX_W, height=BOX_H, pos=(0, -0.03),
                       lineColor="black", fillColor=None)
center_marker = visual.Circle(win, radius=0.006, pos=draw_box.pos,
                              fillColor="gray", lineColor=None, opacity=0.25)

instruction = visual.TextStim(
    win,
    text=(
        f"请在框内画一个钟表，写全数字，并把时间画成11:10。\n"
        f"尽量画得像真正的钟一样，请用手指在屏幕上操作。\n"
    ),
    pos=(0, 0.4),
    height=0.032,
    color="black",
    font=CN_FONT,
    wrapWidth=1.35
)

def make_button(label, pos, w=0.22, h=0.085):
    rect = visual.Rect(win, width=w, height=h, pos=pos,
                       lineColor="black", fillColor="#EEEEEE")
    txt  = visual.TextStim(win, text=label, pos=pos, height=0.03, color="black", font=CN_FONT)
    return rect, txt

btn_clear, btn_clear_txt = make_button("清空", pos=(0.53, 0.44))
btn_done,  btn_done_txt  = make_button("完成", pos=(0.53, -0.46))
btn_undo,  btn_undo_txt  = make_button("撤销", pos=(-0.53, -0.46))

status_txt = visual.TextStim(
    win, text="", pos=(-0.56, -0.46), height=0.03, color="black", font=CN_FONT, alignText="left"
)
status_until_t = 0.0

def set_status(msg, duration=STATUS_FLASH_SEC):
    global status_until_t
    status_txt.text = msg
    status_until_t = global_clock.getTime() + duration

def inside_box(xy):
    x, y = xy
    bx, by = draw_box.pos
    return (abs(x - bx) <= BOX_W/2) and (abs(y - by) <= BOX_H/2)

_prev_pressed = False
def just_pressed():
    """Touch-friendly rising-edge press detector."""
    global _prev_pressed
    pressed = mouse.getPressed()[0]
    jp = (pressed and not _prev_pressed)
    _prev_pressed = pressed
    return jp

def draw_ui():
    instruction.draw()
    draw_box.draw()
    center_marker.draw()
    btn_clear.draw(); btn_clear_txt.draw()
    btn_done.draw();  btn_done_txt.draw()
    btn_undo.draw();  btn_undo_txt.draw()
    if global_clock.getTime() <= status_until_t and status_txt.text:
        status_txt.draw()

# -----------------------
# Instruction screens (instru1 -> instru2 -> start)
# -----------------------
def _wait_for_space_or_escape():
    event.clearEvents(eventType="keyboard")
    while True:
        keys = event.getKeys()
        if "space" in keys:
            return "space"
        if "escape" in keys:
            win.close()
            core.quit()
        core.wait(0.01)

def _resolve_img_path(img_file):
    # absolute
    if os.path.isabs(img_file) and os.path.exists(img_file):
        return img_file
    # current working directory
    if os.path.exists(img_file):
        return img_file
    # script directory (works when running from PsychoPy Coder / python)
    try:
        here = os.path.dirname(__file__)
        cand = os.path.join(here, img_file)
        if os.path.exists(cand):
            return cand
    except Exception:
        pass
    return img_file

def show_instruction_image(img_file, img_size):
    img_path = _resolve_img_path(img_file)
    if not os.path.exists(img_path):
        warn = visual.TextStim(
            win,
            text=f"未找到图片文件：{img_file}\n请把图片放在脚本同目录，或写绝对路径。\n\n按空格继续",
            color="black", height=0.04, font=CN_FONT, wrapWidth=1.4
        )
        while True:
            warn.draw()
            win.flip()
            if _wait_for_space_or_escape() == "space":
                return

    img = visual.ImageStim(win, image=img_path, size=img_size, pos=(0, 0.08))
    # 底部 "继续" 按钮
    btn_pos = (0, -0.42)
    btn_rect = visual.Rect(win, width=0.30, height=0.10, pos=btn_pos,
                           fillColor=[0.75, 0.75, 0.75], lineColor=[0.3, 0.3, 0.3], lineWidth=2)
    btn_label = visual.TextStim(win, text="继续", pos=btn_pos, height=0.045,
                                color="black", font=CN_FONT, bold=True)

    COLOR_NORMAL = [0.75, 0.75, 0.75]
    COLOR_HOVER = [0.85, 0.85, 0.85]
    COLOR_PRESS = [0.55, 0.55, 0.55]
    prev_pressed = False

    while True:
        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            win.close(); core.quit()
        if "space" in keys:
            return

        mouse_pos = mouse.getPos()
        is_pressed = mouse.getPressed()[0] == 1
        hovering = btn_rect.contains(mouse_pos)

        # 松开鼠标时触发
        if prev_pressed and not is_pressed and hovering:
            btn_rect.fillColor = COLOR_PRESS
            img.draw(); btn_rect.draw(); btn_label.draw()
            win.flip()
            core.wait(0.12)
            return

        if is_pressed and hovering:
            btn_rect.fillColor = COLOR_PRESS
        elif hovering:
            btn_rect.fillColor = COLOR_HOVER
        else:
            btn_rect.fillColor = COLOR_NORMAL

        prev_pressed = is_pressed

        img.draw()
        btn_rect.draw()
        btn_label.draw()
        win.flip()
        core.wait(0.016)

# Show instruction images
show_instruction_image(INSTRU1_IMAGE, INSTRU1_IMAGE_SIZE)
show_instruction_image(INSTRU2_IMAGE, INSTRU2_IMAGE_SIZE)

# -----------------------
# Video setup (optional)
# -----------------------
cam = None
video_started_t = None
video_stopped_t = None

def try_open_camera():
    if (not CAMERA_AVAILABLE) or (not RECORD_VIDEO):
        return None
    last_err = None
    for dev in CAMERA_DEVICE_CANDIDATES:
        for lib in CAMERA_LIB_PREFS:
            try:
                c = Camera(
                    device=dev,
                    cameraLib=lib,
                    frameRate=VIDEO_FPS,
                    frameSize=VIDEO_SIZE,
                    win=None,
                    name="cdt_cam",
                    usageMode="video"
                )
                c.open()
                return c
            except Exception as e:
                last_err = e
    print(f"[WARN] Could not open any camera. Last error: {repr(last_err)}")
    return None

cam = try_open_camera()
if cam is not None:
    try:
        cam.record()
        video_started_t = global_clock.getTime()
        set_status("录像：进行中", duration=999999)
    except Exception:
        cam = None
        set_status("录像：启动失败", duration=STATUS_FLASH_SEC)
else:
    set_status("录像：未启用/不可用", duration=999999)

# -----------------------
# Drawing data
# -----------------------
stroke_id = -1
active_stroke_ids = set()
stroke_segments = {}           # stroke_id -> list[visual.Line]
stroke_point_counts = {}       # stroke_id -> point count (active)

traj_active_rows = []          # t,x,y,stroke_id,is_drawing (active only)
traj_raw_rows = []             # t,x,y,stroke_id,is_drawing,is_active,event

undo_count = 0
undo_events = []               # undo_time, undone_stroke_id, active_strokes_before_undo, undo_event_id
last_undo_time = -999.0

is_drawing = False
last_pos = None
last_saved_pos = None
current_stroke = None

def log_point(t, pos, sid, is_draw, is_active, event_name):
    traj_raw_rows.append([t, pos[0], pos[1], sid, int(is_draw), int(is_active), event_name])
    if is_active:
        traj_active_rows.append([t, pos[0], pos[1], sid, int(is_draw)])

def reset_drawing():
    nonlocal_vars = None  # placeholder to avoid accidental indentation errors
    global stroke_id, active_stroke_ids, stroke_segments, stroke_point_counts
    global traj_active_rows, traj_raw_rows, undo_count, undo_events, last_undo_time
    global is_drawing, last_pos, last_saved_pos, current_stroke

    stroke_id = -1
    active_stroke_ids = set()
    stroke_segments = {}
    stroke_point_counts = {}

    traj_active_rows = []
    traj_raw_rows = []

    undo_count = 0
    undo_events = []
    last_undo_time = -999.0

    is_drawing = False
    last_pos = None
    last_saved_pos = None
    current_stroke = None

def undo_last_stroke():
    global undo_count, last_undo_time, traj_active_rows
    if not active_stroke_ids:
        set_status("没有可撤销的笔画")
        return
    now = global_clock.getTime()
    if now - last_undo_time < UNDO_COOLDOWN_SEC:
        set_status("操作太快，请稍后再试")
        return
    last_undo_time = now

    last_sid = max(active_stroke_ids)
    active_before = len(active_stroke_ids)

    active_stroke_ids.remove(last_sid)
    if last_sid in stroke_segments:
        del stroke_segments[last_sid]
    if last_sid in stroke_point_counts:
        del stroke_point_counts[last_sid]

    traj_active_rows = [r for r in traj_active_rows if r[3] != last_sid]

    undo_event_id = len(undo_events)
    undo_events.append([now, last_sid, active_before, undo_event_id])
    undo_count += 1
    log_point(now, mouse.getPos(), last_sid, 0, 0, "UNDO")
    set_status("已撤销上一个笔画")

# -----------------------
# Main loop
# -----------------------
while True:
    if cam is not None:
        try:
            cam.update()
        except Exception:
            cam = None
            set_status("录像：中断", duration=STATUS_FLASH_SEC)

    keys = event.getKeys()
    if "escape" in keys:
        break

    pos = mouse.getPos()
    t = global_clock.getTime()

    if just_pressed():
        if btn_clear.contains(pos):
            reset_drawing()
            mouse.clickReset()
            _prev_pressed = False
            set_status("已清空所有绘图")
            log_point(t, pos, -1, 0, 0, "CLEAR")
            continue

        if btn_undo.contains(pos):
            undo_last_stroke()
            mouse.clickReset()
            _prev_pressed = False
            continue

        if btn_done.contains(pos):
            log_point(t, pos, -1, 0, 0, "DONE")
            break

    pressed = mouse.getPressed()[0]

    if pressed and inside_box(pos):
        if not is_drawing:
            stroke_id += 1
            current_stroke = stroke_id
            active_stroke_ids.add(current_stroke)
            stroke_segments[current_stroke] = []
            stroke_point_counts[current_stroke] = 0

            is_drawing = True
            last_pos = pos
            last_saved_pos = pos

            stroke_point_counts[current_stroke] += 1
            log_point(t, pos, current_stroke, 1, 1, "DOWN")
        else:
            dist = np.linalg.norm(np.array(pos) - np.array(last_saved_pos))
            if dist >= MOVE_THRESH:
                seg = visual.Line(win, start=last_pos, end=pos,
                                  lineColor=INK_COLOR, lineWidth=LINE_WIDTH)
                stroke_segments[current_stroke].append(seg)
                last_pos = pos
                last_saved_pos = pos

                stroke_point_counts[current_stroke] += 1
                log_point(t, pos, current_stroke, 1, 1, "MOVE")
    else:
        if is_drawing and current_stroke is not None:
            log_point(t, pos, current_stroke, 0, 1, "UP")
        is_drawing = False
        last_pos = None
        last_saved_pos = None
        current_stroke = None

    draw_ui()
    for sid in sorted(stroke_segments.keys()):
        for seg in stroke_segments[sid]:
            seg.draw()
    win.flip()

# -----------------------
# Stop recording & save
# -----------------------
if cam is not None:
    try:
        cam.stop()
        video_stopped_t = global_clock.getTime()
        cam.save(vid_path)
        cam.close()
    except Exception:
        cam = None

# -----------------------
# Save outputs
# -----------------------
with open(traj_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["t", "x", "y", "stroke_id", "is_drawing"])
    w.writerows(traj_active_rows)

with open(traj_raw_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["t", "x", "y", "stroke_id", "is_drawing", "is_active", "event"])
    w.writerows(traj_raw_rows)

with open(undo_events_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["undo_time", "undone_stroke_id", "active_strokes_before_undo", "undo_event_id"])
    for row in undo_events:
        w.writerow(row)

def _stroke_times(active_rows, sid):
    ts = [r[0] for r in active_rows if r[3] == sid]
    return (min(ts), max(ts)) if ts else (None, None)

def _stroke_path_length(active_rows, sid):
    pts = [(r[1], r[2]) for r in active_rows if r[3] == sid and r[4] == 1]
    if len(pts) < 2:
        return 0.0
    pts_xy = np.array(pts, dtype=float)
    dif = pts_xy[1:] - pts_xy[:-1]
    return float(np.sum(np.sqrt((dif**2).sum(axis=1))))

with open(stroke_summary_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["stroke_id", "t_start", "t_end", "duration", "point_count", "path_length"])
    for sid in sorted(active_stroke_ids):
        t0, t1 = _stroke_times(traj_active_rows, sid)
        if t0 is None:
            continue
        dur = float(t1 - t0)
        pc = int(stroke_point_counts.get(sid, 0))
        L = _stroke_path_length(traj_active_rows, sid)
        w.writerow([sid, t0, t1, dur, pc, L])

# Screenshots
draw_ui()
for sid in sorted(stroke_segments.keys()):
    for seg in stroke_segments[sid]:
        seg.draw()
win.flip()
try:
    img = win.getMovieFrame()
    img.save(png_ui_path)
except Exception:
    win.getMovieFrame()
    win.saveMovieFrames(png_ui_path)

win.color = BG_COLOR
for sid in sorted(stroke_segments.keys()):
    for seg in stroke_segments[sid]:
        seg.draw()
win.flip()
try:
    img2 = win.getMovieFrame()
    img2.save(png_clock_only_path)
except Exception:
    win.getMovieFrame()
    win.saveMovieFrames(png_clock_only_path)
win.color = BG_COLOR

with open(meta_path, "w", encoding="utf-8") as f:
    f.write(f"participant={info['participant']}\n")
    f.write(f"session={info['session']}\n")
    f.write(f"clock_time=11:10\n")
    f.write(f"traj_csv={traj_path}\n")
    f.write(f"traj_raw_csv={traj_raw_path}\n")
    f.write(f"stroke_summary_csv={stroke_summary_path}\n")
    f.write(f"final_ui_png={png_ui_path}\n")
    f.write(f"clock_only_png={png_clock_only_path}\n")
    f.write(f"undo_events_csv={undo_events_path}\n")
    f.write(f"total_undo_count={undo_count}\n")
    f.write(f"video_mp4={vid_path if cam is not None else 'NA'}\n")
    f.write(f"video_started_t={video_started_t if video_started_t is not None else 'NA'}\n")
    f.write(f"video_stopped_t={video_stopped_t if video_stopped_t is not None else 'NA'}\n")
    f.write("\n# Geometry\n")
    f.write("units=height\n")
    f.write(f"win_size={tuple(win.size)}\n")
    f.write(f"box_w={BOX_W}\n")
    f.write(f"box_h={BOX_H}\n")
    f.write(f"box_pos={tuple(draw_box.pos)}\n")
    f.write(f"line_width={LINE_WIDTH}\n")
    f.write(f"move_thresh={MOVE_THRESH}\n")
    f.write("\n# Instruction images\n")
    f.write(f"instru1_image={INSTRU1_IMAGE}\n")
    f.write(f"instru2_image={INSTRU2_IMAGE}\n")

bye = visual.TextStim(win, text="完成！谢谢。", height=0.06, color="black", font=CN_FONT)
bye.draw()
win.flip()
core.wait(2.0)
win.close()
core.quit()
