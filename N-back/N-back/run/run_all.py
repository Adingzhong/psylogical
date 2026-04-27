# -*- coding: utf-8 -*-
"""
run_all.py  (N-back battery controller)

目标：
- 每个 block 独立可运行；run_all 作为总控（统一窗口/统一推进方式）
- 过场页统一：按屏幕继续（支持触屏），并带最短等待时间（防误触秒过）
- block 间统一休息页（图片 2.png）
- B4 是否进入：由 run_all 控制（默认：B3 用时 <= 4分30秒 且 B2/B3 正确率均达到门槛）

说明：
- 本版优先导入你"原来的文件名"：run_B1_last.py / run_B2_last.py / run_B3_last.py / run_B4_last.py
  若缺失，会自动回退尝试 run_B1.py 等（不崩）。
- 图片路径一律相对项目根目录：
  assets/instruction/1.png   （开始页）
  assets/instruction/2.png   （休息页）
"""

from __future__ import annotations

import csv
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from psychopy import core, event, gui, visual

import sys as _sys

def _get_cjk_font():
    if _sys.platform == "darwin":
        for f in ["Heiti SC", "STHeiti", "PingFang SC", "Hiragino Sans GB"]:
            try:
                from matplotlib.font_manager import findfont, FontProperties
                if findfont(FontProperties(family=f)) != findfont(FontProperties()):
                    return f
            except Exception:
                pass
        return "Heiti SC"
    else:
        return "Microsoft YaHei"

CJK_FONT = _get_cjk_font()


# ----------------------------
# Path helpers
# ----------------------------
def _project_root() -> Path:
    """
    项目根目录：假设本文件在 <root>/run/run_all.py
    """
    here = Path(__file__).resolve()
    return here.parent.parent


def _resolve(root: Path, rel: str) -> Path:
    """
    优先 root/rel；若不存在，再尝试从当前文件所在目录起算（兼容从 run/ 直接运行）。
    """
    p1 = root / rel
    if p1.exists():
        return p1
    p2 = Path(rel)
    if p2.exists():
        return p2
    p3 = Path(__file__).resolve().parent / rel
    return p3


# ----------------------------
# UI / input helpers
# ----------------------------
@dataclass
class AdvanceConfig:
    min_wait_s: float = 0.8
    allow_mouse: bool = True
    allow_space: bool = True


def _wait_advance(win: visual.Window, cfg: AdvanceConfig):
    """
    等待：最短等待时间后，按空格或点击继续。
    支持 escape 退出。
    仅接受屏幕底部中央区域的点击（按钮区域），防止老年用户误触。
    """
    # 清事件，避免误触直接跳
    event.clearEvents()
    mouse = event.Mouse(win=win) if cfg.allow_mouse else None
    t0 = time.perf_counter()

    while True:
        # 允许先渲染（由外层负责 draw+flip），这里只负责判定推进
        now = time.perf_counter()
        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            core.quit()

        if now - t0 < cfg.min_wait_s:
            # 仍在最短等待期内，不响应推进
            win.flip()
            continue

        if cfg.allow_space and ("space" in keys):
            return

        if cfg.allow_mouse and mouse is not None:
            # getPressed() 会持续为 True；只要检测到按下即可推进
            if any(mouse.getPressed()):
                # 等待松开，避免连点造成下一页也被跳过
                while any(mouse.getPressed()):
                    win.flip()
                return

        win.flip()


def _fit_size_keep_ratio(img_w: int, img_h: int, max_w: float, max_h: float) -> Tuple[float, float]:
    if img_w <= 0 or img_h <= 0:
        return max_w, max_h
    scale = min(max_w / float(img_w), max_h / float(img_h))
    return img_w * scale, img_h * scale


def show_fullscreen_image_page(
    win: visual.Window,
    image_path: Path,
    cfg: AdvanceConfig,
):
    """
    图片页 + 底部交互按钮（有hover/press反馈）。
    图片缩小到82%并上移，按钮在底部。
    """
    if not image_path.exists():
        show_text_page(
            win,
            text=f"缺少图片：\n{image_path}\n\n请检查 assets/instruction 路径。",
            title=None,
            cfg=cfg,
        )
        return

    canvas_w, canvas_h = win.size

    try:
        from PIL import Image as PILImage
        iw, ih = PILImage.open(str(image_path)).size
    except Exception:
        iw, ih = 1920, 1080

    img_scale = 0.82
    max_w = canvas_w * img_scale
    max_h = canvas_h * img_scale
    w, h = _fit_size_keep_ratio(iw, ih, max_w, max_h)
    img_y = 0

    stim = visual.ImageStim(win, image=str(image_path),
                            size=(w, h), pos=(0, img_y), units="pix")

    # 交互按钮
    btn_w = int(canvas_w * 0.22)
    btn_h = int(canvas_h * 0.08)
    btn_y = -canvas_h // 2 + int(canvas_h * 0.10)
    _c_normal = [26, 140, 255]
    _c_hover = [64, 170, 255]
    _c_press = [10, 90, 180]

    btn = visual.Rect(win, width=btn_w, height=btn_h, pos=(0, btn_y),
                      fillColor=_c_normal, colorSpace="rgb255",
                      lineWidth=0, units="pix")
    btn_lbl = visual.TextStim(win, text="继续", font=CJK_FONT,
                               height=btn_h * 0.5, color=[255, 255, 255],
                               colorSpace="rgb255", pos=(0, btn_y),
                               units="pix", bold=True)

    mouse = event.Mouse(win=win)
    mouse.setVisible(True)
    event.clearEvents()
    t0 = time.perf_counter()
    prev = True

    while True:
        now = time.perf_counter()
        mpos = mouse.getPos()
        hovering = btn.contains(mpos)
        cur = any(mouse.getPressed())

        if cur and hovering:
            btn.fillColor = _c_press
        elif hovering:
            btn.fillColor = _c_hover
        else:
            btn.fillColor = _c_normal

        stim.draw()
        btn.draw()
        btn_lbl.draw()
        win.flip()

        if now - t0 < cfg.min_wait_s:
            prev = cur
            continue

        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            core.quit()
        if cfg.allow_space and "space" in keys:
            return

        if cur and not prev and hovering:
            btn.fillColor = _c_press
            stim.draw(); btn.draw(); btn_lbl.draw()
            win.flip()
            core.wait(0.12)
            return
        prev = cur


def _estimate_text_height_px(line_count: int, font_px: float) -> float:
    # 粗估：行高约 1.25 倍字体，且至少 1 行
    return max(1, line_count) * font_px * 1.25


def show_text_page(
    win: visual.Window,
    text: str,
    title: Optional[str],
    cfg: AdvanceConfig,
    footer: str = "按屏幕继续",
):
    """
    文字页：整体对称居中（title + body + footer 作为一个整体居中）。
    """
    W, H = win.size

    # 自适应字号：短文本更大，长文本稍小
    lines = text.strip().splitlines()
    n_lines = max(1, len(lines))

    body_px = 52
    if n_lines <= 2:
        body_px = 64
    elif n_lines <= 4:
        body_px = 58
    elif n_lines <= 8:
        body_px = 52
    else:
        body_px = 44

    title_px = 64 if title else 0
    footer_px = 38

    # 估计高度并做整体居中布局
    gap1 = H * 0.03 if title else 0
    gap2 = H * 0.04

    title_h = _estimate_text_height_px(1, title_px) if title else 0
    body_h = _estimate_text_height_px(n_lines, body_px)
    footer_h = _estimate_text_height_px(1, footer_px)

    total_h = title_h + gap1 + body_h + gap2 + footer_h
    top_y = total_h / 2.0

    y_title = top_y - title_h / 2.0 if title else None
    y_body = top_y - title_h - gap1 - body_h / 2.0
    y_footer = top_y - title_h - gap1 - body_h - gap2 - footer_h / 2.0

    if title:
        title_stim = visual.TextStim(
            win,
            text=title,
            height=title_px,
            color="white",
            pos=(0, y_title),
            font=CJK_FONT,
            units="pix",
            alignText="center",
            wrapWidth=W * 0.92,
        )
    else:
        title_stim = None

    body_stim = visual.TextStim(
        win,
        text=text,
        height=body_px,
        color="white",
        pos=(0, y_body),
        font=CJK_FONT,
        units="pix",
        alignText="center",
        wrapWidth=W * 0.92,
    )

    footer_stim = visual.TextStim(
        win,
        text=footer,
        height=footer_px,
        color="white",
        pos=(0, y_footer),
        font=CJK_FONT,
        units="pix",
        alignText="center",
        wrapWidth=W * 0.92,
    )

    # 循环等待推进（最短等待）
    event.clearEvents()
    mouse = event.Mouse(win=win) if cfg.allow_mouse else None
    t0 = time.perf_counter()

    while True:
        if title_stim:
            title_stim.draw()
        body_stim.draw()
        footer_stim.draw()
        win.flip()

        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            core.quit()

        if time.perf_counter() - t0 < cfg.min_wait_s:
            continue

        if cfg.allow_space and ("space" in keys):
            return

        if cfg.allow_mouse and mouse is not None and any(mouse.getPressed()):
            while any(mouse.getPressed()):
                if title_stim:
                    title_stim.draw()
                body_stim.draw()
                footer_stim.draw()
                win.flip()
            return


# ----------------------------
# Result helpers
# ----------------------------
def _pick_acc(d: Dict[str, Any], keys) -> Optional[float]:
    for k in keys:
        v = d.get(k, None)
        if v is None:
            continue
        try:
            return float(v)
        except Exception:
            continue
    return None


def _write_master_summary(root: Path, exp_info: Dict[str, Any], rows) -> Optional[Path]:
    out_dir = root / "data" / "summary"
    out_dir.mkdir(parents=True, exist_ok=True)

    pid = str(exp_info.get("participant", "unknown"))
    ses = str(exp_info.get("session", "1"))
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"summary_{pid}_S{ses}_{ts}.csv"

    # 合并字段
    fieldnames = set(["participant", "session"])
    for r in rows:
        fieldnames.update(r.keys())
    fieldnames = list(fieldnames)

    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            row = dict(r)
            row["participant"] = pid
            row["session"] = ses
            w.writerow(row)

    return out_path


# ----------------------------
# Import helpers (prefer *_last.py)
# ----------------------------
@dataclass
class BlockModule:
    name: str
    mod: Any
    err: Optional[Exception] = None


def _safe_import(run_dir: Path, module_candidates) -> Tuple[Optional[Any], Optional[str], Optional[Exception]]:
    if str(run_dir) not in sys.path:
        sys.path.insert(0, str(run_dir))

    last_err: Optional[Exception] = None
    for mname in module_candidates:
        try:
            mod = __import__(mname)
            return mod, mname, None
        except Exception as e:
            last_err = e
    return None, None, last_err


def main(cli_subject_id: str = ""):
    root = _project_root()
    run_dir = root / "run"

    # 1) 只在 run_all 收集被试信息
    exp_info: Dict[str, Any] = {
        "participant": "test",
        "session": "1",
        "list_name": "ListA",          # A/B/C
        "auto_run_B4": True,           # run_all 控制是否进入 B4
        # 休息/推进
        "advance_min_s": 0.8,          # 过场页最短等待时间（秒）
        # B4 门槛（可改）
        "b4_gate_time_s": 270,         # 4分30秒
        "b4_gate_acc": 0.80,           # "正确率都比较高"的默认门槛（可改）
    }
    if cli_subject_id:
        exp_info["participant"] = cli_subject_id
    else:
        _dlg_info = {"被试编号": ""}
        dlg = gui.DlgFromDict(_dlg_info, title="N-back 工作记忆")
        if not dlg.OK:
            core.quit()
        exp_info["participant"] = _dlg_info["被试编号"].strip() or "test"

    list_name = str(exp_info.get("list_name", "ListA"))
    cfg = AdvanceConfig(
        min_wait_s=float(exp_info.get("advance_min_s", 0.8)),
        allow_mouse=True,
        allow_space=True,
    )

    # 2) 创建单一 Window（统一颜色/全屏）
    win = visual.Window(
        size=(1920, 1080),
        fullscr=True,
        color=[0, 0, 0],
        units="pix",
        allowGUI=False,
    )
    win.mouseVisible = True

    master_rows = []

    # 预先解析图片路径（相对项目根目录）
    start_img = _resolve(root, "assets/instruction/1.png")
    rest_img = _resolve(root, "assets/instruction/2.png")

    # 导入 blocks：优先 *_last.py
    b1_mod, b1_name, b1_err = _safe_import(run_dir, ["run_B1_last", "run_B1"])
    b2_mod, b2_name, b2_err = _safe_import(run_dir, ["run_B2_last", "run_B2"])
    b3_mod, b3_name, b3_err = _safe_import(run_dir, ["run_B3_last", "run_B3"])
    b4_mod, b4_name, b4_err = _safe_import(run_dir, ["run_B4_last", "run_B4"])

    try:
        # 开始页（图片全屏）
        show_fullscreen_image_page(win, start_img, cfg)

        # ----------------------------
        # B1
        # ----------------------------
        if (b1_mod is None) or (not hasattr(b1_mod, "run_B1")):
            master_rows.append({"block": "B1", "status": "skipped", "reason": f"导入失败：{b1_err}"})
            show_text_page(win, "B1 未运行（导入失败）。\n\n将跳过进入下一段。", title=None, cfg=cfg)
        else:
            t0 = time.perf_counter()
            s = b1_mod.run_B1(win=win, exp_info=exp_info, list_name=list_name)
            dur = time.perf_counter() - t0
            s = s if isinstance(s, dict) else {}
            s.setdefault("block", "B1")
            s.setdefault("status", "done")
            s["module"] = b1_name
            s["duration_s"] = round(dur, 3)
            master_rows.append(s)

        # 休息页
        show_fullscreen_image_page(win, rest_img, cfg)

        # ----------------------------
        # B2
        # ----------------------------
        if (b2_mod is None) or (not hasattr(b2_mod, "run_B2")):
            master_rows.append({"block": "B2", "status": "skipped", "reason": f"导入失败：{b2_err}"})
            show_text_page(win, "B2 未运行（导入失败）。\n\n将跳过进入下一段。", title=None, cfg=cfg)
            summary_b2 = {}
        else:
            t0 = time.perf_counter()
            summary_b2 = b2_mod.run_B2(win=win, exp_info=exp_info, list_name=list_name)
            dur = time.perf_counter() - t0
            summary_b2 = summary_b2 if isinstance(summary_b2, dict) else {}
            summary_b2.setdefault("block", "B2")
            summary_b2.setdefault("status", "done")
            summary_b2["module"] = b2_name
            summary_b2["duration_s"] = round(dur, 3)
            master_rows.append(summary_b2)

        # 休息页
        show_fullscreen_image_page(win, rest_img, cfg)

        # ----------------------------
        # B3
        # ----------------------------
        if (b3_mod is None) or (not hasattr(b3_mod, "run_B3")):
            master_rows.append({"block": "B3", "status": "skipped", "reason": f"导入失败：{b3_err}"})
            show_text_page(win, "B3 未运行（导入失败）。\n\n将进入结束页。", title=None, cfg=cfg)
            summary_b3 = {}
        else:
            t0 = time.perf_counter()
            summary_b3 = b3_mod.run_B3(win=win, exp_info=exp_info, list_name=list_name)
            dur = time.perf_counter() - t0
            summary_b3 = summary_b3 if isinstance(summary_b3, dict) else {}
            summary_b3.setdefault("block", "B3")
            summary_b3.setdefault("status", "done")
            summary_b3["module"] = b3_name
            summary_b3["duration_s"] = round(dur, 3)
            master_rows.append(summary_b3)

        # 休息页（无论是否进入 B4 都先休息）
        show_fullscreen_image_page(win, rest_img, cfg)

        # ----------------------------
        # B4（可选）
        # ----------------------------
        auto_run_B4 = bool(exp_info.get("auto_run_B4", True))
        gate_time_s = float(exp_info.get("b4_gate_time_s", 270))
        gate_acc = float(exp_info.get("b4_gate_acc", 0.80))

        acc_b2 = _pick_acc(summary_b2, ["acc_main", "acc"])
        acc_b3 = _pick_acc(summary_b3, ["acc_main_probe", "acc_main", "acc"])
        dur_b3 = None
        try:
            if isinstance(summary_b3, dict) and ("duration_s" in summary_b3):
                dur_b3 = float(summary_b3["duration_s"])
        except Exception:
            dur_b3 = None

        gate_ok = True
        gate_reason = []

        if acc_b2 is not None and acc_b2 < gate_acc:
            gate_ok = False
            gate_reason.append(f"B2 正确率 {acc_b2:.2f} < {gate_acc:.2f}")
        if acc_b3 is not None and acc_b3 < gate_acc:
            gate_ok = False
            gate_reason.append(f"B3 正确率 {acc_b3:.2f} < {gate_acc:.2f}")
        if dur_b3 is not None and dur_b3 > gate_time_s:
            gate_ok = False
            gate_reason.append(f"B3 用时 {dur_b3:.0f}s > {gate_time_s:.0f}s")

        if (not auto_run_B4) or (not gate_ok):
            reason = "；".join(gate_reason) if gate_reason else "run_all 设置为不进入 B4"
            master_rows.append({"block": "B4", "status": "skipped", "reason": reason})
            show_text_page(
                win,
                "请稍作休息，即将结束。",
                title=None,
                cfg=cfg,
            )
        else:
            if (b4_mod is None) or (not hasattr(b4_mod, "run_B4")):
                master_rows.append({"block": "B4", "status": "skipped", "reason": f"导入失败：{b4_err}"})
                show_text_page(win, "B4 未运行（导入失败）。\n\n将进入结束页。", title=None, cfg=cfg)
            else:
                t0 = time.perf_counter()
                summary_b4 = b4_mod.run_B4(win=win, exp_info=exp_info, list_name=list_name)
                dur = time.perf_counter() - t0
                summary_b4 = summary_b4 if isinstance(summary_b4, dict) else {}
                summary_b4.setdefault("block", "B4")
                summary_b4.setdefault("status", "done")
                summary_b4["module"] = b4_name
                summary_b4["duration_s"] = round(dur, 3)
                master_rows.append(summary_b4)

        # 结束页
        out_path = _write_master_summary(root, exp_info, master_rows)
        end_msg = "测验结束，谢谢您！"
        if out_path:
            end_msg += "\n\n结果已保存"
        show_text_page(win, end_msg, title=None, cfg=cfg)

    except Exception as e:
        # 兜底错误页（保证不黑屏）
        show_text_page(win, f"程序出现错误：\n\n{e}\n\n请记录报错信息。", title="错误", cfg=cfg)
    finally:
        try:
            win.close()
        except Exception:
            pass
        core.quit()


if __name__ == "__main__":
    import argparse as _ap
    _parser = _ap.ArgumentParser(description="N-back Battery")
    _parser.add_argument("--subject_id", type=str, default="", help="被试编号（传入后跳过对话框）")
    _args = _parser.parse_args()
    main(cli_subject_id=_args.subject_id)
