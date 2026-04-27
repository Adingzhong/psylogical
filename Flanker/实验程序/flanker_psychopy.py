import argparse
import csv
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

WINDOW_SIZE = [1280, 800]
TEXT_FONT = "Microsoft YaHei"
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

COUNTDOWN_SECONDS = 3
PRE_FIXATION_BLANK = 1.0
FIXATION_DURATION = 0.5
MAX_RESPONSE_WINDOW = 2.0
POST_RESPONSE_BLANK = 0.75
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
    "welcome": "01_welcome_intro.png",
    "practice_start": "02_practice_start.png",
    "practice_end": "03_practice_end.png",
    "practice_retry": "04_practice_retry.png",
    "formal_start": "05_formal_start.png",
    "break_rating": "06_break_rating.png",
    "finish": "07_finish.png",
}


def quit_experiment() -> None:
    raise ExperimentExit()


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


def draw_instruction_image(instruction_stim: visual.ImageStim, image_path: Path) -> None:
    instruction_stim.image = str(image_path)
    instruction_stim.draw()
    instruction_stim.win.flip()


def show_instruction_image(
    instruction_stim: visual.ImageStim,
    image_path: Path,
    key_list: Optional[List[str]] = None,
) -> str:
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
    spec: TrialSpec,
    exp_clock: core.Clock,
    iti_response: bool,
) -> Tuple[dict, bool]:
    trial_stim.image = str(resolve_trial_image_path(arrows_dir, spec))
    response_clock = core.Clock()
    event.clearEvents()

    probe_onset = None
    response_ts = ""
    key_pressed = "none"
    reaction_time_ms = ""
    accuracy = 0
    timeout = True
    is_anticipatory = 0
    responded = False
    stimulus_started = False

    while True:
        trial_stim.draw()
        win.flip()

        if not stimulus_started:
            probe_onset = exp_clock.getTime()
            response_clock.reset()
            stimulus_started = True

        if response_clock.getTime() >= MAX_RESPONSE_WINDOW:
            break

        keys = event.getKeys(keyList=TASK_KEYS + [EXIT_KEY], timeStamped=response_clock)
        if not keys:
            continue

        check_escape(keys)
        first_key = keys[0]
        key_pressed = first_key[0]
        response_ts = f"{exp_clock.getTime():.6f}"
        reaction_time_ms = round(first_key[1] * 1000, 3)
        timeout = False
        responded = True

        if key_pressed == LEFT_KEY:
            accuracy = int(spec.target_dir == "left")
        elif key_pressed == RIGHT_KEY:
            accuracy = int(spec.target_dir == "right")
        else:
            accuracy = 0

        if first_key[1] < 0.2:
            is_anticipatory = 1
        break

    if not responded:
        win.flip()

    post_blank_had_key = False
    if responded:
        post_blank_had_key = run_blank_with_key_check(win, POST_RESPONSE_BLANK)

    record = asdict(spec)
    record.update(
        {
            "keyPressed": key_pressed,
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
    fixation_stim: visual.TextStim,
    exp_clock: core.Clock,
    trials: List[TrialSpec],
    writer: csv.DictWriter,
    data_file,
    show_initial_countdown: bool,
) -> List[dict]:
    records: List[dict] = []

    if show_initial_countdown:
        show_countdown(win)

    for trial_idx, spec in enumerate(trials):
        pre_blank_response = run_blank_with_key_check(win, PRE_FIXATION_BLANK)
        run_fixation(win, fixation_stim)
        record, _ = run_single_trial(win, trial_stim, arrows_dir, spec, exp_clock, pre_blank_response)
        writer.writerow(record)
        data_file.flush()
        records.append(record)

    return records


def run_focus_rating(
    instruction_stim: visual.ImageStim,
    image_path: Path,
    ratings_writer: csv.DictWriter,
    ratings_file,
    subject_id: str,
    block_index: int,
    exp_clock: core.Clock,
) -> str:
    draw_instruction_image(instruction_stim, image_path)
    event.clearEvents()
    keys = event.waitKeys(keyList=RATING_KEYS + [EXIT_KEY])
    if keys and keys[0] == EXIT_KEY:
        quit_experiment()

    rating = keys[0]
    ratings_writer.writerow(
        {
            "subject_id": subject_id,
            "block_index": block_index,
            "focus_rating": rating,
            "rating_ts": f"{exp_clock.getTime():.6f}",
        }
    )
    ratings_file.flush()
    show_instruction_image(instruction_stim, image_path, key_list=[CONTINUE_KEY])
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
            allowGUI=False,
            checkTiming=False,
        )
        win.mouseVisible = False

        exp_clock = core.Clock()
        instruction_stim = build_instruction_image_stim(win, instructions_dir)
        trial_stim = build_trial_image_stim(win, arrows_dir)
        fixation_stim = visual.TextStim(
            win=win,
            text="+",
            color=WHITE,
            colorSpace="rgb255",
            font=SYMBOL_FONT,
            height=FIXATION_HEIGHT,
        )

        show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["welcome"])

        practice_round = 1
        move_to_formal = False

        while not move_to_formal and practice_round <= MAX_PRACTICE_ROUNDS:
            show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["practice_start"])

            practice_trials = build_practice_trials(subject_id, practice_round)
            practice_records = run_trial_list(
                win=win,
                trial_stim=trial_stim,
                arrows_dir=arrows_dir,
                fixation_stim=fixation_stim,
                exp_clock=exp_clock,
                trials=practice_trials,
                writer=trial_writer,
                data_file=trial_file,
                show_initial_countdown=True,
            )
            practice_accuracy = compute_practice_accuracy(practice_records)

            if practice_accuracy >= PRACTICE_PASS_ACCURACY or practice_round == MAX_PRACTICE_ROUNDS:
                move_to_formal = True
                show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["practice_end"])
            else:
                show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["practice_retry"])
                practice_round += 1

        show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["formal_start"])

        formal_blocks = build_formal_blocks(subject_id)
        for block_number, block_trials in enumerate(formal_blocks, start=1):
            run_trial_list(
                win=win,
                trial_stim=trial_stim,
                arrows_dir=arrows_dir,
                fixation_stim=fixation_stim,
                exp_clock=exp_clock,
                trials=block_trials,
                writer=trial_writer,
                data_file=trial_file,
                show_initial_countdown=(block_number == 1),
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
                )

        show_instruction_image(instruction_stim, instructions_dir / INSTRUCTION_FILES["finish"])
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
