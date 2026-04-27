"""
SART Screen Preview Generator
-------------------------------
Renders each instruction / trial / probe screen to a PNG file
so they can be reviewed visually without running the full experiment.

Output directory: assets/preview_*.png

Usage (macOS with PsychoPy standalone app):
    PYTHONHOME=/Applications/PsychoPy.app/Contents/Resources \
    PYTHONPATH=/Applications/PsychoPy.app/Contents/Resources/lib/python3.10 \
    /Applications/PsychoPy.app/Contents/MacOS/python preview_screens.py
"""

import json
import sys
from pathlib import Path

# ── PsychoPy imports ──────────────────────────────────────────────
from psychopy import visual, core, event

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / 'config.json'
ASSETS_DIR = SCRIPT_DIR / 'assets'
PREVIEW_DIR = ASSETS_DIR  # save previews alongside icons


def load_config() -> dict:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_image(win, path: Path, pos: tuple):
    """Load an ImageStim if the file exists, else None."""
    if path.exists():
        return visual.ImageStim(win, image=str(path), pos=pos, size=(0.22, 0.22))
    return None


def save_screenshot(win, name: str):
    """Flip the window, capture the back-buffer, save to PNG."""
    win.flip()
    out = PREVIEW_DIR / f'preview_{name}.png'
    win.getMovieFrame()
    win.saveMovieFrames(str(out))
    print(f'  saved  {out.name}')


# ══════════════════════════════════════════════════════════════════
#  Common UI elements (mirror stimulus_manager.py / experiment_manager.py)
# ══════════════════════════════════════════════════════════════════

def draw_button(win, cfg):
    """Draw the blue response button with shadow and label (matches stimulus_manager)."""
    btn_cfg = cfg['button']
    # Shadow
    shadow = visual.Rect(
        win,
        width=btn_cfg['width'], height=btn_cfg['height'],
        pos=[btn_cfg['position'][0] + 0.005,
             btn_cfg['position'][1] - 0.008],
        fillColor=[0.6, 0.6, 0.6],
        lineWidth=0,
        opacity=0.3,
    )
    shadow.draw()
    # Button
    button = visual.Rect(
        win,
        width=btn_cfg['width'], height=btn_cfg['height'],
        pos=btn_cfg['position'],
        fillColor=btn_cfg['color_normal'],
        lineColor=btn_cfg['color_normal'],
        lineWidth=0,
    )
    button.draw()
    # Label
    label = visual.TextStim(
        win,
        text=btn_cfg.get('label', '\u6309'),
        font=cfg['chinese_font'],
        height=0.06,
        color=btn_cfg.get('label_color', [1, 1, 1]),
        pos=btn_cfg['position'],
        bold=True,
    )
    label.draw()


def make_title(win, cfg, text, pos=(0, 0.65)):
    """Title text matching experiment_manager._create_ui_elements."""
    return visual.TextStim(
        win, text=text, font=cfg['chinese_font'],
        height=0.09, color=cfg['text_color'],
        pos=pos, bold=True,
        wrapWidth=1.6, alignText='center',
    )


def make_body(win, cfg, text, pos=(0, 0.05)):
    """Body text matching experiment_manager._create_ui_elements."""
    return visual.TextStim(
        win, text=text, font=cfg['chinese_font'],
        height=0.055, color=cfg['text_color'],
        pos=pos, wrapWidth=1.4, alignText='center',
    )


def make_hint(win, cfg, text='\uff08\u6309\u6309\u94ae\u7ee7\u7eed\uff09'):
    """Bottom hint text matching experiment_manager._create_ui_elements."""
    return visual.TextStim(
        win, text=text, font=cfg['chinese_font'],
        height=0.038, color=[0.3, 0.3, 0.3],
        pos=(0, -0.72), wrapWidth=1.5, alignText='center',
    )


# ══════════════════════════════════════════════════════════════════
#  Screen renderers (mirror experiment_manager.py exactly)
# ══════════════════════════════════════════════════════════════════

# ── 1. Welcome ────────────────────────────────────────────────────
def render_welcome(win, cfg):
    """Matches ExperimentManager.show_welcome()"""
    title = make_title(win, cfg, '\u6b22\u8fce\u53c2\u52a0\u201c\u773c\u75be\u624b\u5feb\u201d\u6311\u6218\uff01')
    body = make_body(win, cfg,
        '\u5c4f\u5e55\u4f1a\u4f9d\u6b21\u51fa\u73b0\u6570\u5b57 1 - 9\n\n'
        '\u770b\u5230\u6570\u5b57 \u2192 \u6309\u4e0b\u9762\u7684\u6309\u94ae\n\n'
        '\u4f46\u6709\u4e00\u4e2a\u6570\u5b57\u662f\u4f8b\u5916\u2026\u2026')
    hint = make_hint(win, cfg)

    title.draw()
    body.draw()
    hint.draw()
    draw_button(win, cfg)
    save_screenshot(win, '01_welcome')


# ── 2. Rules ──────────────────────────────────────────────────────
def render_rules(win, cfg):
    """Matches ExperimentManager.show_rules()"""
    title = make_title(win, cfg, '\u8bb0\u4f4f\u8fd9\u4e2a\u6363\u4e71\u6570\u5b57\uff1a')
    hint = make_hint(win, cfg)

    # Big red "3"
    big3 = visual.TextStim(
        win, text='3', font=cfg['font_name'],
        height=0.22, color=[0.85, -0.6, -0.6],
        pos=(-0.12, 0.30), bold=True,
    )
    # Stop icon
    stop_icon = load_image(win, ASSETS_DIR / 'stop_icon.png', (0.22, 0.30))

    # Two rule lines (bold, colored)
    rule1 = visual.TextStim(
        win, font=cfg['chinese_font'],
        height=0.07, color=[0.85, -0.6, -0.6],
        pos=(0, -0.05), bold=True,
        text='\u770b\u5230 3 \u2192 \u522b\u6309\uff01\u5fcd\u4f4f\uff01',
    )
    rule2 = visual.TextStim(
        win, font=cfg['chinese_font'],
        height=0.07, color=[-0.2, 0.5, -0.2],
        pos=(0, -0.22), bold=True,
        text='\u5176\u4ed6\u6570\u5b57 \u2192 \u5feb\u6309\uff01',
    )

    title.draw()
    big3.draw()
    if stop_icon:
        stop_icon.draw()
    rule1.draw()
    rule2.draw()
    hint.draw()
    draw_button(win, cfg)
    save_screenshot(win, '02_rules')


# ── 3. Practice intro ────────────────────────────────────────────
def render_practice_intro(win, cfg):
    """Matches ExperimentManager.show_practice_intro()"""
    title = make_title(win, cfg, '\u5148\u7ec3\u4e60\u51e0\u4e0b')

    # Left: digit 7 + "-> \u6309\uff01" + tap icon
    d7 = visual.TextStim(
        win, text='7', font=cfg['font_name'],
        height=0.16, color=cfg['stimulus_color'],
        pos=(-0.35, 0.38), bold=True)
    l7 = visual.TextStim(
        win, text='\u2192 \u6309\uff01', font=cfg['chinese_font'],
        height=0.055, color=[-0.2, 0.5, -0.2],
        pos=(-0.35, 0.18), bold=True)
    tap_icon = load_image(win, ASSETS_DIR / 'tap_icon.png', (-0.35, -0.02))

    # Right: digit 3 + "-> \u522b\u6309\uff01" + stop icon
    d3 = visual.TextStim(
        win, text='3', font=cfg['font_name'],
        height=0.16, color=[0.85, -0.6, -0.6],
        pos=(0.35, 0.38), bold=True)
    l3 = visual.TextStim(
        win, text='\u2192 \u522b\u6309\uff01', font=cfg['chinese_font'],
        height=0.055, color=[0.85, -0.6, -0.6],
        pos=(0.35, 0.18), bold=True)
    stop_icon = load_image(win, ASSETS_DIR / 'stop_icon.png', (0.35, -0.02))

    # Body text (positioned below examples, matching _show_screen body pos)
    body = make_body(win, cfg,
        '\u6309\u9519\u4e86\u5c4f\u5e55\u4f1a\u63d0\u9192\u60a8\uff0c\u6ca1\u5173\u7cfb\u7684\uff01',
        pos=(0, -0.28))
    hint = make_hint(win, cfg, '\uff08\u51c6\u5907\u597d\u4e86\uff1f\u6309\u6309\u94ae\u5f00\u59cb\u7ec3\u4e60\uff09')

    title.draw()
    d7.draw(); l7.draw()
    if tap_icon:
        tap_icon.draw()
    d3.draw(); l3.draw()
    if stop_icon:
        stop_icon.draw()
    body.draw()
    hint.draw()
    draw_button(win, cfg)
    save_screenshot(win, '03_practice_intro')


# ── 3.1 Practice retry ───────────────────────────────────────────
def render_practice_retry(win, cfg):
    """Matches ExperimentManager.show_practice_retry()"""
    title = make_title(win, cfg, '\u518d\u7ec3\u4e60\u4e00\u6b21\uff01')
    body = make_body(win, cfg,
        '\u770b\u5230 3 \u522b\u6309\uff0c\u5176\u4ed6\u6570\u5b57\u5feb\u6309')
    hint = make_hint(win, cfg, '\uff08\u6309\u6309\u94ae\u5f00\u59cb\uff09')

    title.draw()
    body.draw()
    hint.draw()
    draw_button(win, cfg)
    save_screenshot(win, '04_practice_retry')


# ── 4. Formal intro ──────────────────────────────────────────────
def render_formal_intro(win, cfg):
    """Matches ExperimentManager.show_formal_intro()"""
    title = make_title(win, cfg, '\u7ec3\u4e60\u7ed3\u675f\uff0c\u505a\u5f97\u4e0d\u9519\uff01')
    body = make_body(win, cfg,
        '\u6b63\u5f0f\u5f00\u59cb\uff08\u7ea62\u5206\u949f\uff09\n\n'
        '\u8fd9\u6b21\u6309\u9519\u4e0d\u4f1a\u63d0\u793a\n'
        '\u8bf7\u575a\u6301\u505a\u5b8c\n\n'
        '\u8bb0\u4f4f\uff1a\u770b\u5230 3 \u522b\u6309\uff01')
    hint = make_hint(win, cfg, '\uff08\u6309\u6309\u94ae\u5f00\u59cb\u6b63\u5f0f\u6d4b\u8bd5\uff09')

    title.draw()
    body.draw()
    hint.draw()
    draw_button(win, cfg)
    save_screenshot(win, '05_formal_intro')


# ── 5. Trial - go digit ──────────────────────────────────────────
def render_trial_go(win, cfg):
    """Matches stimulus_manager digit display for go trial."""
    digit = visual.TextStim(
        win, text='7', font=cfg['font_name'],
        height=cfg['font_size_norm'], color=cfg['stimulus_color'],
        pos=(0, 0.05), bold=True,
    )
    digit.draw()
    draw_button(win, cfg)
    save_screenshot(win, '06_trial_go')


# ── 5b. Trial - nogo digit ───────────────────────────────────────
def render_trial_nogo(win, cfg):
    """Matches stimulus_manager digit display for nogo trial."""
    digit = visual.TextStim(
        win, text='3', font=cfg['font_name'],
        height=cfg['font_size_norm'], color=cfg['stimulus_color'],
        pos=(0, 0.05), bold=True,
    )
    digit.draw()
    draw_button(win, cfg)
    save_screenshot(win, '07_trial_nogo')


# ── 5c. Feedback - commission error ──────────────────────────────
def render_feedback_commission(win, cfg):
    """Matches stimulus_manager.present_feedback commission."""
    fb = visual.TextStim(
        win, text='\u2717 \u6570\u5b573\u522b\u6309\uff01', font=cfg['chinese_font'],
        height=0.09, color=[0.8, -0.4, -0.4],
        pos=(0, 0.05), wrapWidth=1.6, bold=True,
    )
    fb.draw()
    save_screenshot(win, '08_feedback_commission')


# ── 5d. Feedback - omission error ────────────────────────────────
def render_feedback_omission(win, cfg):
    """Matches stimulus_manager.present_feedback omission."""
    fb = visual.TextStim(
        win, text='\u2717 \u8bb0\u5f97\u6309\u952e\uff01', font=cfg['chinese_font'],
        height=0.09, color=[0.8, -0.4, -0.4],
        pos=(0, 0.05), wrapWidth=1.6, bold=True,
    )
    fb.draw()
    save_screenshot(win, '09_feedback_omission')


# ── 6. Probe ─────────────────────────────────────────────────────
def render_probe(win, cfg):
    """Matches ExperimentManager.run_probe()"""
    pcfg = cfg['probe']

    prompt = visual.TextStim(
        win, font=cfg['chinese_font'],
        height=0.065, color=cfg['text_color'],
        pos=(0, 0.45), wrapWidth=1.5, alignText='center',
        text='\u8bf7\u8bc4\u4ef7\u521a\u624d\u5bf9\u4efb\u52a1\u7684\u4e13\u6ce8\u7a0b\u5ea6',
        bold=True,
    )
    sub_prompt = visual.TextStim(
        win, font=cfg['chinese_font'],
        height=0.045, color=[0.3, 0.3, 0.3],
        pos=(0, 0.32), wrapWidth=1.5, alignText='center',
        text='1 = \u5b8c\u5168\u4e0d\u4e13\u6ce8\u3000\u3000\u30009 = \u975e\u5e38\u4e13\u6ce8',
    )

    slider = visual.Slider(
        win,
        ticks=list(range(pcfg['min_rating'], pcfg['max_rating'] + 1)),
        labels=[str(i) for i in range(1, 10)],
        pos=(0, 0.05), size=(1.2, 0.08),
        style='rating', granularity=1,
        color=cfg['text_color'],
        fillColor=[0.1, 0.55, 0.82],
        borderColor=cfg['text_color'],
        font=cfg['chinese_font'],
    )

    confirm_btn = visual.Rect(
        win, width=0.3, height=0.1, pos=(0, -0.35),
        fillColor=[0.1, 0.55, 0.82],
        lineWidth=0,
    )
    confirm_label = visual.TextStim(
        win, text='\u786e\u8ba4', font=cfg['chinese_font'],
        height=0.05, color=[1, 1, 1], pos=(0, -0.35), bold=True,
    )

    # Set a rating so the confirm button appears (for preview purposes)
    slider.markerPos = 5
    slider.rating = 5

    prompt.draw()
    sub_prompt.draw()
    slider.draw()
    confirm_btn.draw()
    confirm_label.draw()
    save_screenshot(win, '10_probe')


# ── 7. Completion ─────────────────────────────────────────────────
def render_completion(win, cfg):
    """Matches ExperimentManager.show_completion()"""
    title = make_title(win, cfg, '\u6d4b\u8bd5\u7ed3\u675f\uff01')
    body = make_body(win, cfg, '\u611f\u8c22\u60a8\u7684\u53c2\u4e0e\uff01')
    hint = make_hint(win, cfg, '\uff08\u6309\u6309\u94ae\u9000\u51fa\uff09')

    title.draw()
    body.draw()
    hint.draw()
    draw_button(win, cfg)
    save_screenshot(win, '11_completion')


# ══════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════

def main():
    cfg = load_config()
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    print('Creating PsychoPy window ...')
    win = visual.Window(
        size=cfg['screen_size'],
        fullscr=False,
        color=cfg['background_color'],
        units='norm',
        allowGUI=False,
        checkTiming=False,
    )
    win.mouseVisible = False

    renderers = [
        ('welcome',             render_welcome),
        ('rules',               render_rules),
        ('practice_intro',      render_practice_intro),
        ('practice_retry',      render_practice_retry),
        ('formal_intro',        render_formal_intro),
        ('trial_go',            render_trial_go),
        ('trial_nogo',          render_trial_nogo),
        ('feedback_commission', render_feedback_commission),
        ('feedback_omission',   render_feedback_omission),
        ('probe',               render_probe),
        ('completion',          render_completion),
    ]

    print(f'Rendering {len(renderers)} screens ...')
    for label, fn in renderers:
        try:
            fn(win, cfg)
        except Exception as e:
            print(f'  ERROR on {label}: {e}')

    win.close()
    print('Done - all previews saved to', PREVIEW_DIR)
    core.quit()


if __name__ == '__main__':
    main()
