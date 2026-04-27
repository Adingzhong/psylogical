import argparse
import csv
import platform
import random
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from psychopy import core, data, event, gui, visual


LEFT_KEY = "q"
RIGHT_KEY = "p"
EXIT_KEY = "escape"
CONTINUE_KEY = "space"
RATING_KEYS = [str(i) for i in range(1, 10)]
TASK_KEYS = [LEFT_KEY, RIGHT_KEY]

BLACK = [0, 0, 0]
WHITE = [255, 255, 255]
POPOUT_YELLOW = [247, 236, 0]
BTN_NORMAL = [0.75, 0.75, 0.75]
BTN_HOVER = [0.85, 0.85, 0.85]
BTN_PRESS = [0.55, 0.55, 0.55]
BTN_BORDER = [0.3, 0.3, 0.3]

WINDOW_SIZE = [1280, 800]
CN_FONT = "PingFang SC" if platform.system() == "Darwin" else "Microsoft YaHei"
TEXT_FONT = CN_FONT
SYMBOL_FONT = "Arial"
DEFAULT_FULLSCREEN = True

WIN_UNITS = "height"
INSTRUCTION_HEIGHT = 0.048
COUNTDOWN_HEIGHT = 0.12
FIXATION_HEIGHT = 0.06
SYMBOL_HEIGHT = 0.09
SYMBOL_POSITIONS = [-0.16, -0.08, 0.0, 0.08, 0.16]
TEXT_WRAP_WIDTH = 1.3
INSTRUCTION_IMAGE_SIZE = (1920, 1080)
# The dev doc specifies a much smaller physical stimulus size than the raw PNGs.
# Without a calibrated monitor profile we cannot guarantee exact cm,
# so we use a smaller default pixel size that is visually closer to spec.
TRIAL_IMAGE_SIZE = (240, 39)
FEEDBACK_IMAGE_SIZE = (5760, 3240)

# 触摸按钮布局（height units）
RESP_BTN_Y = -0.38
RESP_BTN_X_OFFSET = 0.28
RESP_BTN_W = 0.30
RESP_BTN_H = 0.12
RESP_BTN_FONT_H = 0.045
CONTINUE_BTN_Y = -0.42
CONTINUE_BTN_W = 0.30
CONTINUE_BTN_H = 0.10

COUNTDOWN_SECONDS = 3
PRE_FIXATION_BLANK = 1.0
FIXATION_DURATION = 0.5
MAX_RESPONSE_WINDOW = 2.0
POST_RESPONSE_BLANK = 0.75
PRACTICE_ERROR_FEEDBACK_DURATION = 1.5
PRACTICE_TRIALS = 6
PRACTICE_PASS_ACCURACY = 0.70
MAX_PRACTICE_ROUNDS = 3


@dataclass
class TrialSpec:
    subject_id: str
    trial_index: int
    is_practice: bool
    trial_type: str
    is_popout: bool
    popout_type: str
    popout_position: str
    target_dir: str
    flanker_dir: str
    block_index: int
    practice_round: int
    phase_name: str


class ExperimentExit(Exception):
    pass


INSTRUCTION_FILES = {
    "welcome": "01.png",
    "practice_start": "02_practice_start.png",
    "practice_end": "03.png",
    "practice_retry": "04_practice_retry.png",
    "formal_start": "05_formal_start.png",
    "break_rating": "06_break_rating.png",
    "finish": "07.png",
}

PRACTICE_FEEDBACK_FILES = {
    "left": "q.png",
    "right": "p.png",
}


def quit_experiment() -> None:
    raise ExperimentExit()


def map_key_to_direction(key_name: str) -> str:
    if key_name == LEFT_KEY:
        return "left"
    if key_name == RIGHT_KEY:
        return "right"
    return "none"


# --------------- 触摸按钮 ---------------

def _make_btn(win, label, pos, w=CONTINUE_BTN_W, h=CONTINUE_BTN_H):
    rect = visual.Rect(win, width=w, height=h, pos=pos,
                       fillColor=BTN_NORMAL, lineColor=BTN_BORDER, lineWidth=2)
    txt = visual.TextStim(win, text=label, pos=pos, height=RESP_BTN_FONT_H,
                          color="black", font=CN_FONT, bold=True)
    return rect, txt


def _draw_btn(rect, txt, mouse_pos, pressed):
    hovering = rect.contains(mouse_pos)
    if pressed and hovering:
        rect.fillColor = BTN_PRESS
    elif hovering:
        rect.fillColor = BTN_HOVER
    else:
        rect.fillColor = BTN_NORMAL
    rect.draw()
    txt.draw()
    return hovering


def build_response_buttons(win):
    """创建左右触摸响应按钮，返回 (left_rect, left_txt, right_rect, right_txt)"""
    lr, lt = _make_btn(win, "左", (-RESP_BTN_X_OFFSET, RESP_BTN_Y), RESP_BTN_W, RESP_BTN_H)
    rr, rt = _make_btn(win, "右", (RESP_BTN_X_OFFSET, RESP_BTN_Y), RESP_BTN_W, RESP_BTN_H)
    return lr, lt, rr, rt


def draw_response_buttons(btns, mouse_pos, pressed):
    """绘制左右按钮，返回 (left_hover, right_hover)"""
    lr, lt, rr, rt = btns
    lh = _draw_btn(lr, lt, mouse_pos, pressed)
    rh = _draw_btn(rr, rt, mouse_pos, pressed)
    return lh, rh


def build_continue_button(win):
    return _make_btn(win, "继续", (0, CONTINUE_BTN_Y))


def check_escape(keys: Iterable) -> None:
    for key in keys:
        key_name = getattr(key, "name", key)
        if isinstance(key, tuple):
            key_name = key[0]
        if key_name == EXIT_KEY:
            quit_experiment()


def wait_for_keypress(win: visual.Window, text: str, key_list: Optional[List[str]] = None) -> str:
    stimulus = visual.TextStim(
        win=win,
        text=text,
        color=WHITE,
        colorSpace="rgb255",
        font=TEXT_FONT,
        height=INSTRUCTION_HEIGHT,
        wrapWidth=TEXT_WRAP_WIDTH,
        bold=True,
    )
    stimulus.draw()
    win.flip()
    event.clearEvents()
    allowed_keys = list(key_list) if key_list is not None else [CONTINUE_KEY]
    if EXIT_KEY not in allowed_keys:
        allowed_keys.append(EXIT_KEY)
    keys = event.waitKeys(keyList=allowed_keys)
    if keys and EXIT_KEY in keys:
        quit_experiment()
    return keys[0]


def fit_size_within(win_size: Tuple[float, float], image_size: Tuple[float, float]) -> Tuple[float, float]:
    win_width, win_height = float(win_size[0]), float(win_size[1])
    image_width, image_height = float(image_size[0]), float(image_size[1])
    scale = min(win_width / image_width, win_height / image_height)
    return image_width * scale, image_height * scale


def build_instruction_image_stim(win: visual.Window, instructions_dir: Path) -> visual.ImageStim:
    initial_image = instructions_dir / INSTRUCTION_FILES["welcome"]
    return visual.ImageStim(
        win=win,
        image=str(initial_image),
        pos=(0, 0),
        units="pix",
        size=fit_size_within(tuple(win.size), INSTRUCTION_IMAGE_SIZE),
        interpolate=True,
    )


def build_feedback_image_stim(win: visual.Window, instructions_dir: Path) -> visual.ImageStim:
    initial_image = instructions_dir / PRACTICE_FEEDBACK_FILES["left"]
    return visual.ImageStim(
        win=win,
        image=str(initial_image),
        pos=(0, 0),
        units="pix",
        size=fit_size_within(tuple(win.size), FEEDBACK_IMAGE_SIZE),
        interpolate=True,
    )


def draw_instruction_image(instruction_stim: visual.ImageStim, image_path: Path) -> None:
    instruction_stim.image = str(image_path)
    instruction_stim.draw()
    instruction_stim.win.flip()


def show_instruction_image(
    instruction_stim: visual.ImageStim,
    image_path: Path,
    key_list: Optional[List[str]] = None,
    continue_btn=None,
    mouse=None,
) -> str:
    instruction_stim.image = str(image_path)
    # 有按钮则用触摸，否则回退键盘
    if continue_btn and mouse:
        btn_rect, btn_txt = continue_btn
        prev_pressed = False
        event.clearEvents()
        while True:
            keys = event.getKeys(keyList=[EXIT_KEY, CONTINUE_KEY])
            if EXIT_KEY in keys:
                quit_experiment()
            if CONTINUE_KEY in keys:
                return CONTINUE_KEY
            mouse_pos = mouse.getPos()
            is_pressed = mouse.getPressed()[0] == 1
            hovering = btn_rect.contains(mouse_pos)
            if prev_pressed and not is_pressed and hovering:
                btn_rect.fillColor = BTN_PRESS
                instruction_stim.draw(); btn_rect.draw(); btn_txt.draw()
                instruction_stim.win.flip()
                core.wait(0.12)
                return CONTINUE_KEY
            prev_pressed = is_pressed
            instruction_stim.draw()
            _draw_btn(btn_rect, btn_txt, mouse_pos, is_pressed)
            instruction_stim.win.flip()
            core.wait(0.016)
    else:
        draw_instruction_image(instruction_stim, image_path)
        event.clearEvents()
        allowed_keys = list(key_list) if key_list is not None else [CONTINUE_KEY]
        if EXIT_KEY not in allowed_keys:
            allowed_keys.append(EXIT_KEY)
        keys = event.waitKeys(keyList=allowed_keys)
        if keys and EXIT_KEY in keys:
            quit_experiment()
        return keys[0]


def build_trial_image_stim(win: visual.Window, arrows_dir: Path) -> visual.ImageStim:
    initial_image = arrows_dir / "中性" / "c1.png"
    return visual.ImageStim(
        win=win,
        image=str(initial_image),
        pos=(0, 0),
        units="pix",
        size=TRIAL_IMAGE_SIZE,
        interpolate=True,
    )


def show_timed_feedback_image(feedback_stim: visual.ImageStim, image_path: Path, duration: float) -> None:
    feedback_stim.image = str(image_path)
    event.clearEvents()
    timer = core.CountdownTimer(duration)
    while timer.getTime() > 0:
        keys = event.getKeys(keyList=[EXIT_KEY])
        if keys:
            check_escape(keys)
        feedback_stim.draw()
        feedback_stim.win.flip()


def resolve_trial_image_path(arrows_dir: Path, spec: TrialSpec) -> Path:
    if spec.trial_type == "Congruent":
        if not spec.is_popout:
            return arrows_dir / "一致" / ("z.png" if spec.target_dir == "left" else "y.png")
        congruent_map = {
            "left": {"1": "d4.png", "2": "d3.png", "3": "b6.png", "4": "d5.png", "5": "d6.png"},
            "right": {"1": "5a.png", "2": "4a.png", "3": "3a.png", "4": "6a.png", "5": "7a.png"},
        }
        return arrows_dir / "一致-pop" / congruent_map[spec.target_dir][spec.popout_position]

    if spec.trial_type == "Incongruent":
        if not spec.is_popout:
            return arrows_dir / "不一致" / ("a2.png" if spec.target_dir == "left" else "a1.png")
        incongruent_map = {
            "left": {"1": "Z1.png", "2": "Z2.png", "3": "Z3.png", "4": "Z4.png", "5": "Z5.png"},
            "right": {"1": "Y1.png", "2": "Y2.png", "3": "Y3.png", "4": "Y4.png", "5": "Y5.png"},
        }
        return arrows_dir / "不一致-pop" / incongruent_map[spec.target_dir][spec.popout_position]

    if not spec.is_popout:
        return arrows_dir / "中性" / ("c2.png" if spec.target_dir == "left" else "c1.png")
    return arrows_dir / "中性-pop" / ("c4.png" if spec.target_dir == "left" else "c3.png")


def show_countdown(win: visual.Window) -> None:
    countdown_stim = visual.TextStim(
        win=win,
        text="",
        color=WHITE,
        colorSpace="rgb255",
        font=SYMBOL_FONT,
        height=COUNTDOWN_HEIGHT,
    )
    for number in range(COUNTDOWN_SECONDS, 0, -1):
        countdown_stim.text = str(number)
        countdown_stim.draw()
        win.flip()
        core.wait(1.0)
    win.flip()


def build_symbol_stims(win: visual.Window) -> List[visual.TextStim]:
    stims = []
    for pos_x in SYMBOL_POSITIONS:
        stim = visual.TextStim(
            win=win,
            text="",
            pos=(pos_x, 0),
            height=SYMBOL_HEIGHT,
            color=WHITE,
            colorSpace="rgb255",
            font=SYMBOL_FONT,
        )
        stims.append(stim)
    return stims


def get_flanker_direction(trial_type: str, target_dir: str) -> str:
    if trial_type == "Congruent":
        return target_dir
    if trial_type == "Incongruent":
        return "right" if target_dir == "left" else "left"
    return "neutral"


def arrow_symbol(direction: str) -> str:
    if direction == "left":
        return "←"
    if direction == "right":
        return "→"
    return "—"


def get_symbol_texts(spec: TrialSpec) -> List[str]:
    if spec.trial_type == "Neutral":
        return ["—", "—", arrow_symbol(spec.target_dir), "—", "—"]

    flank_symbol = arrow_symbol(spec.flanker_dir)
    target_symbol = arrow_symbol(spec.target_dir)
    return [flank_symbol, flank_symbol, target_symbol, flank_symbol, flank_symbol]


def configure_symbol_stims(symbol_stims: List[visual.TextStim], spec: TrialSpec) -> None:
    texts = get_symbol_texts(spec)
    popout_index = None
    if spec.is_popout and spec.popout_position != "NA":
        popout_index = int(spec.popout_position) - 1

    for idx, stim in enumerate(symbol_stims):
        stim.text = texts[idx]
        stim.color = POPOUT_YELLOW if idx == popout_index else WHITE


def run_blank_with_key_check(win: visual.Window, duration: float) -> bool:
    event.clearEvents()
    timer = core.CountdownTimer(duration)
    had_keypress = False
    while timer.getTime() > 0:
        keys = event.getKeys(keyList=TASK_KEYS + [EXIT_KEY])
        if keys:
            check_escape(keys)
            had_keypress = True
        win.flip()
    return had_keypress


def run_fixation(win: visual.Window, fixation_stim: visual.TextStim) -> None:
    event.clearEvents()
    timer = core.CountdownTimer(FIXATION_DURATION)
    while timer.getTime() > 0:
        keys = event.getKeys(keyList=TASK_KEYS + [EXIT_KEY])
        if keys:
            check_escape(keys)
        fixation_stim.draw()
        win.flip()


def run_single_trial(
    win: visual.Window,
    trial_stim: visual.ImageStim,
    arrows_dir: Path,
    feedback_stim: visual.ImageStim,
    instructions_dir: Path,
    spec: TrialSpec,
    exp_clock: core.Clock,
    iti_response: bool,
    resp_btns=None,
    mouse=None,
) -> Tuple[dict, bool]:
    trial_stim.image = str(resolve_trial_image_path(arrows_dir, spec))
    response_clock = core.Clock()
    event.clearEvents()
    if mouse:
        mouse.clickReset()

    probe_onset = None
    response_ts = ""
    response_key = "none"
    key_pressed = "none"
    reaction_time_ms = ""
    accuracy = 0
    timeout = True
    is_anticipatory = 0
    responded = False
    stimulus_started = False
    prev_pressed = False

    while True:
        trial_stim.draw()
        if resp_btns and mouse:
            mouse_pos = mouse.getPos()
            is_pressed = mouse.getPressed()[0] == 1
            draw_response_buttons(resp_btns, mouse_pos, is_pressed)
        win.flip()

        if not stimulus_started:
            probe_onset = exp_clock.getTime()
            response_clock.reset()
            stimulus_started = True

        elapsed = response_clock.getTime()
        if elapsed >= MAX_RESPONSE_WINDOW:
            break

        # 键盘检测（fallback）
        keys = event.getKeys(keyList=TASK_KEYS + [EXIT_KEY], timeStamped=response_clock)
        if keys:
            check_escape(keys)
            first_key = keys[0]
            response_key = first_key[0]
            key_pressed = map_key_to_direction(response_key)
            response_ts = f"{exp_clock.getTime():.6f}"
            reaction_time_ms = round(first_key[1] * 1000, 3)
            timeout = False
            responded = True
            if first_key[1] < 0.2:
                is_anticipatory = 1

        # 触摸按钮检测
        if not responded and resp_btns and mouse:
            lr, lt, rr, rt = resp_btns
            if prev_pressed and not is_pressed:
                clicked_dir = None
                if lr.contains(mouse_pos):
                    clicked_dir = "left"
                    response_key = LEFT_KEY
                elif rr.contains(mouse_pos):
                    clicked_dir = "right"
                    response_key = RIGHT_KEY
                if clicked_dir:
                    key_pressed = clicked_dir
                    response_ts = f"{exp_clock.getTime():.6f}"
                    reaction_time_ms = round(elapsed * 1000, 3)
                    timeout = False
                    responded = True
                    if elapsed < 0.2:
                        is_anticipatory = 1
            prev_pressed = is_pressed

        if responded:
            if key_pressed == "left":
                accuracy = int(spec.target_dir == "left")
            elif key_pressed == "right":
                accuracy = int(spec.target_dir == "right")
            else:
                accuracy = 0
            break

    if not responded:
        win.flip()

    post_blank_had_key = False
    if responded:
        if spec.is_practice and accuracy == 0 and not timeout:
            feedback_image = instructions_dir / PRACTICE_FEEDBACK_FILES[spec.target_dir]
            show_timed_feedback_image(feedback_stim, feedback_image, PRACTICE_ERROR_FEEDBACK_DURATION)
        post_blank_had_key = run_blank_with_key_check(win, POST_RESPONSE_BLANK)

    record = asdict(spec)
    record.update(
        {
            "keyPressed": key_pressed,
            "response_key": response_key,
            "accuracy": accuracy,
            "reaction_time": reaction_time_ms,
            "probe_onset-ts": "" if probe_onset is None else f"{probe_onset:.6f}",
            "response-ts": response_ts,
            "timeout": timeout,
            "is_anticipatory": is_anticipatory,
            "iti_response": int(iti_response or post_blank_had_key),
        }
    )
    return record, responded


def has_valid_runs(trials: List[TrialSpec], attribute: str, max_run: int = 3) -> bool:
    run_length = 1
    for idx in range(1, len(trials)):
        if getattr(trials[idx], attribute) == getattr(trials[idx - 1], attribute):
            run_length += 1
            if run_length > max_run:
                return False
        else:
            run_length = 1
    return True


def shuffle_with_constraints(trials: List[TrialSpec], max_attempts: int = 10000) -> List[TrialSpec]:
    for _ in range(max_attempts):
        shuffled = random.sample(trials, len(trials))
        if has_valid_runs(shuffled, "trial_type") and has_valid_runs(shuffled, "target_dir"):
            return shuffled
    raise RuntimeError("无法在限定次数内生成满足约束的试次顺序。")


def create_trial(
    subject_id: str,
    trial_index: int,
    is_practice: bool,
    trial_type: str,
    target_dir: str,
    is_popout: bool,
    popout_type: str,
    popout_position: str,
    block_index: int,
    practice_round: int,
    phase_name: str,
) -> TrialSpec:
    return TrialSpec(
        subject_id=subject_id,
        trial_index=trial_index,
        is_practice=is_practice,
        trial_type=trial_type,
        is_popout=is_popout,
        popout_type=popout_type,
        popout_position=popout_position,
        target_dir=target_dir,
        flanker_dir=get_flanker_direction(trial_type, target_dir),
        block_index=block_index,
        practice_round=practice_round,
        phase_name=phase_name,
    )


def build_formal_blocks(subject_id: str) -> List[List[TrialSpec]]:
    congruent_left_positions = random.sample([1, 2], 2)
    congruent_right_positions = random.sample([4, 5], 2)
    incongruent_left_positions = random.sample([4, 5], 2)
    incongruent_right_positions = random.sample([1, 2], 2)

    blocks: List[List[TrialSpec]] = []
    global_index = 1
    presented_index = 1

    for block_idx in range(2):
        block_trials: List[TrialSpec] = []
        current_block = block_idx + 1

        for _ in range(2):
            block_trials.append(
                create_trial(subject_id, global_index, False, "Congruent", "left", False, "na", "NA", current_block, 0, "formal")
            )
            global_index += 1
        for _ in range(2):
            block_trials.append(
                create_trial(subject_id, global_index, False, "Congruent", "right", False, "na", "NA", current_block, 0, "formal")
            )
            global_index += 1

        block_trials.append(
            create_trial(subject_id, global_index, False, "Congruent", "left", True, "target", "3", current_block, 0, "formal")
        )
        global_index += 1
        block_trials.append(
            create_trial(subject_id, global_index, False, "Congruent", "right", True, "target", "3", current_block, 0, "formal")
        )
        global_index += 1
        block_trials.append(
            create_trial(
                subject_id,
                global_index,
                False,
                "Congruent",
                "left",
                True,
                "flanker",
                str(congruent_left_positions[block_idx]),
                current_block,
                0,
                "formal",
            )
        )
        global_index += 1
        block_trials.append(
            create_trial(
                subject_id,
                global_index,
                False,
                "Congruent",
                "right",
                True,
                "flanker",
                str(congruent_right_positions[block_idx]),
                current_block,
                0,
                "formal",
            )
        )
        global_index += 1

        for _ in range(2):
            block_trials.append(
                create_trial(subject_id, global_index, False, "Incongruent", "left", False, "na", "NA", current_block, 0, "formal")
            )
            global_index += 1
        for _ in range(2):
            block_trials.append(
                create_trial(subject_id, global_index, False, "Incongruent", "right", False, "na", "NA", current_block, 0, "formal")
            )
            global_index += 1

        block_trials.append(
            create_trial(subject_id, global_index, False, "Incongruent", "left", True, "target", "3", current_block, 0, "formal")
        )
        global_index += 1
        block_trials.append(
            create_trial(subject_id, global_index, False, "Incongruent", "right", True, "target", "3", current_block, 0, "formal")
        )
        global_index += 1
        block_trials.append(
            create_trial(
                subject_id,
                global_index,
                False,
                "Incongruent",
                "left",
                True,
                "flanker",
                str(incongruent_left_positions[block_idx]),
                current_block,
                0,
                "formal",
            )
        )
        global_index += 1
        block_trials.append(
            create_trial(
                subject_id,
                global_index,
                False,
                "Incongruent",
                "right",
                True,
                "flanker",
                str(incongruent_right_positions[block_idx]),
                current_block,
                0,
                "formal",
            )
        )
        global_index += 1

        for _ in range(2):
            block_trials.append(
                create_trial(subject_id, global_index, False, "Neutral", "left", False, "na", "NA", current_block, 0, "formal")
            )
            global_index += 1
        for _ in range(2):
            block_trials.append(
                create_trial(subject_id, global_index, False, "Neutral", "right", False, "na", "NA", current_block, 0, "formal")
            )
            global_index += 1
        for _ in range(2):
            block_trials.append(
                create_trial(subject_id, global_index, False, "Neutral", "left", True, "target", "3", current_block, 0, "formal")
            )
            global_index += 1
        for _ in range(2):
            block_trials.append(
                create_trial(subject_id, global_index, False, "Neutral", "right", True, "target", "3", current_block, 0, "formal")
            )
            global_index += 1

        shuffled_block = shuffle_with_constraints(block_trials)
        for trial in shuffled_block:
            trial.trial_index = presented_index
            presented_index += 1
        blocks.append(shuffled_block)

    return blocks


def build_practice_trials(subject_id: str, practice_round: int) -> List[TrialSpec]:
    round_templates = {
        1: [
            ("Congruent", "left", False, "na", "NA"),
            ("Congruent", "right", True, "target", "3"),
            ("Incongruent", "right", False, "na", "NA"),
            ("Incongruent", "left", True, "flanker", "4"),
            ("Neutral", "left", False, "na", "NA"),
            ("Neutral", "right", True, "target", "3"),
        ],
        2: [
            ("Congruent", "right", False, "na", "NA"),
            ("Congruent", "left", True, "flanker", "1"),
            ("Incongruent", "left", False, "na", "NA"),
            ("Incongruent", "right", True, "target", "3"),
            ("Neutral", "right", False, "na", "NA"),
            ("Neutral", "left", True, "target", "3"),
        ],
        3: [
            ("Congruent", "left", False, "na", "NA"),
            ("Congruent", "right", True, "flanker", "5"),
            ("Incongruent", "right", False, "na", "NA"),
            ("Incongruent", "left", True, "target", "3"),
            ("Neutral", "right", False, "na", "NA"),
            ("Neutral", "left", True, "target", "3"),
        ],
    }
    round_index = ((practice_round - 1) % MAX_PRACTICE_ROUNDS) + 1
    selected_template = round_templates[round_index]

    practice_trials = []
    for trial_index, (trial_type, target_dir, is_popout, popout_type, popout_position) in enumerate(selected_template, start=1):
        practice_trials.append(
            create_trial(
                subject_id,
                trial_index,
                True,
                trial_type,
                target_dir,
                is_popout,
                popout_type,
                popout_position,
                0,
                practice_round,
                "practice",
            )
        )

    shuffled_trials = shuffle_with_constraints(practice_trials)
    for idx, trial in enumerate(shuffled_trials, start=1):
        trial.trial_index = idx
    return shuffled_trials


def run_trial_list(
    win: visual.Window,
    trial_stim: visual.ImageStim,
    arrows_dir: Path,
    feedback_stim: visual.ImageStim,
    instructions_dir: Path,
    fixation_stim: visual.TextStim,
    exp_clock: core.Clock,
    trials: List[TrialSpec],
    writer: csv.DictWriter,
    data_file,
    show_initial_countdown: bool,
    global_trial_start: int,
    resp_btns=None,
    mouse=None,
) -> Tuple[List[dict], int]:
    records: List[dict] = []
    global_trial_index = global_trial_start

    if show_initial_countdown:
        show_countdown(win)

    for trial_idx, spec in enumerate(trials):
        pre_blank_response = run_blank_with_key_check(win, PRE_FIXATION_BLANK)
        run_fixation(win, fixation_stim)
        record, _ = run_single_trial(
            win,
            trial_stim,
            arrows_dir,
            feedback_stim,
            instructions_dir,
            spec,
            exp_clock,
            pre_blank_response,
            resp_btns=resp_btns,
            mouse=mouse,
        )
        record["trial_index_global"] = global_trial_index
        writer.writerow(record)
        data_file.flush()
        records.append(record)
        global_trial_index += 1

    return records, global_trial_index


def run_focus_rating(
    instruction_stim: visual.ImageStim,
    image_path: Path,
    ratings_writer: csv.DictWriter,
    ratings_file,
    subject_id: str,
    block_index: int,
    exp_clock: core.Clock,
    mouse=None,
    continue_btn=None,
) -> str:
    win = instruction_stim.win
    instruction_stim.image = str(image_path)

    # 构建 1-9 评分按钮行
    rating_btns = []
    total_w = 9 * 0.09 + 8 * 0.02  # 9 buttons with gaps
    start_x = -total_w / 2 + 0.045
    rating_y = -0.38
    for i in range(1, 10):
        bx = start_x + (i - 1) * 0.11
        br = visual.Rect(win, width=0.09, height=0.09, pos=(bx, rating_y),
                         fillColor=BTN_NORMAL, lineColor=BTN_BORDER, lineWidth=2)
        bt = visual.TextStim(win, text=str(i), pos=(bx, rating_y), height=0.04,
                             color="black", font=CN_FONT, bold=True)
        rating_btns.append((i, br, bt))

    prev_pressed = False
    rating = None
    event.clearEvents()

    while rating is None:
        # 键盘 fallback
        keys = event.getKeys(keyList=RATING_KEYS + [EXIT_KEY])
        if EXIT_KEY in keys:
            quit_experiment()
        for k in keys:
            if k in RATING_KEYS:
                rating = k
                break

        mouse_pos = mouse.getPos() if mouse else (0, 0)
        is_pressed = mouse.getPressed()[0] == 1 if mouse else False

        instruction_stim.draw()
        for val, br, bt in rating_btns:
            _draw_btn(br, bt, mouse_pos, is_pressed)

        # 松开检测
        if mouse and prev_pressed and not is_pressed:
            for val, br, bt in rating_btns:
                if br.contains(mouse_pos):
                    rating = str(val)
                    br.fillColor = BTN_PRESS
                    instruction_stim.draw()
                    for v2, b2, t2 in rating_btns:
                        b2.draw(); t2.draw()
                    win.flip()
                    core.wait(0.15)
                    break
        prev_pressed = is_pressed

        win.flip()
        core.wait(0.016)

    ratings_writer.writerow(
        {
            "subject_id": subject_id,
            "block_index": block_index,
            "focus_rating": rating,
            "rating_ts": f"{exp_clock.getTime():.6f}",
        }
    )
    ratings_file.flush()
    # 点击后继续
    show_instruction_image(instruction_stim, image_path,
                           continue_btn=continue_btn, mouse=mouse)
    return rating


def compute_practice_accuracy(records: List[dict]) -> float:
    if not records:
        return 0.0
    correct = sum(int(record["accuracy"]) for record in records)
    return correct / len(records)


def ensure_directories(base_dir: Path) -> Tuple[Path, Path]:
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return base_dir, data_dir


def create_data_writers(
    data_dir: Path,
    subject_id: str,
) -> Tuple[csv.DictWriter, csv.DictWriter, object, object]:
    timestamp = data.getDateStr()
    trial_path = data_dir / f"{subject_id}_flanker_trials_{timestamp}.csv"
    rating_path = data_dir / f"{subject_id}_flanker_ratings_{timestamp}.csv"

    trial_file = trial_path.open("w", newline="", encoding="utf-8-sig")
    rating_file = rating_path.open("w", newline="", encoding="utf-8-sig")

    trial_fields = [
        "subject_id",
        "trial_index",
        "trial_index_global",
        "is_practice",
        "trial_type",
        "is_popout",
        "popout_type",
        "popout_position",
        "target_dir",
        "flanker_dir",
        "block_index",
        "practice_round",
        "phase_name",
        "keyPressed",
        "response_key",
        "accuracy",
        "reaction_time",
        "probe_onset-ts",
        "response-ts",
        "timeout",
        "is_anticipatory",
        "iti_response",
    ]
    rating_fields = ["subject_id", "block_index", "focus_rating", "rating_ts"]

    trial_writer = csv.DictWriter(trial_file, fieldnames=trial_fields)
    rating_writer = csv.DictWriter(rating_file, fieldnames=rating_fields)
    trial_writer.writeheader()
    rating_writer.writeheader()
    return trial_writer, rating_writer, trial_file, rating_file


def get_default_subject_id() -> str:
    return "subj_{0}".format(datetime.now().strftime("%Y%m%d_%H%M%S"))


def collect_subject_info(subject_id: str = "") -> str:
    if subject_id:
        return subject_id
    default_subject_id = get_default_subject_id()
    dialog = gui.Dlg(title="Flanker实验")
    dialog.addText("请输入被试编号")
    dialog.addField("被试编号:", initial="")
    dialog.show()

    if not dialog.OK:
        quit_experiment()

    subject_id = str(dialog.data[0]).strip()
    if not subject_id:
        subject_id = default_subject_id
    return subject_id


def main(cli_subject_id: str = "") -> None:
    base_dir = Path(__file__).resolve().parent
    instructions_dir = base_dir / "instructions"
    arrows_dir = base_dir / "arrows"
    _, data_dir = ensure_directories(base_dir)
    trial_file = None
    rating_file = None
    win = None

    try:
        subject_id = collect_subject_info(cli_subject_id)
        trial_writer, rating_writer, trial_file, rating_file = create_data_writers(data_dir, subject_id)

        win = visual.Window(
            size=WINDOW_SIZE,
            fullscr=DEFAULT_FULLSCREEN,
            units=WIN_UNITS,
            color=BLACK,
            colorSpace="rgb255",
            allowGUI=True,
            checkTiming=False,
        )
        win.mouseVisible = True
        mouse = event.Mouse(win=win, visible=True)

        exp_clock = core.Clock()
        instruction_stim = build_instruction_image_stim(win, instructions_dir)
        feedback_stim = build_feedback_image_stim(win, instructions_dir)
        trial_stim = build_trial_image_stim(win, arrows_dir)
        fixation_stim = visual.TextStim(
            win=win,
            text="+",
            color=WHITE,
            colorSpace="rgb255",
            font=SYMBOL_FONT,
            height=FIXATION_HEIGHT,
        )

        # 触摸按钮
        resp_btns = build_response_buttons(win)
        continue_btn = build_continue_button(win)

        show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["welcome"],
                               continue_btn=continue_btn, mouse=mouse)

        practice_round = 1
        move_to_formal = False
        global_trial_index = 1

        while not move_to_formal and practice_round <= MAX_PRACTICE_ROUNDS:
            show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["practice_start"],
                                   continue_btn=continue_btn, mouse=mouse)

            practice_trials = build_practice_trials(subject_id, practice_round)
            practice_records, global_trial_index = run_trial_list(
                win=win,
                trial_stim=trial_stim,
                arrows_dir=arrows_dir,
                feedback_stim=feedback_stim,
                instructions_dir=instructions_dir,
                fixation_stim=fixation_stim,
                exp_clock=exp_clock,
                trials=practice_trials,
                writer=trial_writer,
                data_file=trial_file,
                show_initial_countdown=True,
                global_trial_start=global_trial_index,
                resp_btns=resp_btns,
                mouse=mouse,
            )
            practice_accuracy = compute_practice_accuracy(practice_records)

            if practice_accuracy >= PRACTICE_PASS_ACCURACY or practice_round == MAX_PRACTICE_ROUNDS:
                move_to_formal = True
                show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["practice_end"],
                                       continue_btn=continue_btn, mouse=mouse)
            else:
                show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["practice_retry"],
                                       continue_btn=continue_btn, mouse=mouse)
                practice_round += 1

        show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["formal_start"],
                               continue_btn=continue_btn, mouse=mouse)

        formal_blocks = build_formal_blocks(subject_id)
        for block_number, block_trials in enumerate(formal_blocks, start=1):
            _, global_trial_index = run_trial_list(
                win=win,
                trial_stim=trial_stim,
                arrows_dir=arrows_dir,
                feedback_stim=feedback_stim,
                instructions_dir=instructions_dir,
                fixation_stim=fixation_stim,
                exp_clock=exp_clock,
                trials=block_trials,
                writer=trial_writer,
                data_file=trial_file,
                show_initial_countdown=(block_number == 1),
                global_trial_start=global_trial_index,
                resp_btns=resp_btns,
                mouse=mouse,
            )

            if block_number == 1:
                run_focus_rating(
                    instruction_stim,
                    instructions_dir / INSTRUCTION_FILES["break_rating"],
                    rating_writer,
                    rating_file,
                    subject_id,
                    block_number,
                    exp_clock,
                    mouse=mouse,
                    continue_btn=continue_btn,
                )

        show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["finish"],
                               continue_btn=continue_btn, mouse=mouse)
    except ExperimentExit:
        pass
    except Exception:
        error_path = base_dir / "run_error.log"
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        if trial_file is not None:
            trial_file.close()
        if rating_file is not None:
            rating_file.close()
        if win is not None:
            win.close()


if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="Flanker实验")
    _parser.add_argument("--subject_id", type=str, default="", help="被试编号（传入后跳过对话框）")
    _args = _parser.parse_args()
    main(cli_subject_id=_args.subject_id)
