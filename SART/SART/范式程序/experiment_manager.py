"""
SART Experiment Manager
实验流程控制：指导语、练习、正式测试、Probe
"""

from pathlib import Path

from psychopy import visual, core, event

from stimulus_manager import StimulusManager
from data_manager import DataManager


class ExperimentManager:
    """控制SART实验全流程"""

    def __init__(self, win: visual.Window, config: dict,
                 stim_mgr: StimulusManager, data_mgr: DataManager):
        self.win = win
        self.config = config
        self.stim = stim_mgr
        self.data = data_mgr
        self.mouse = event.Mouse(win=win)
        self.global_clock = core.Clock()
        self._press_flash_until = 0.0
        self._create_ui_elements()

    # ------------------------------------------------------------------
    # UI元素
    # ------------------------------------------------------------------

    def _create_ui_elements(self):
        cfg = self.config
        font = cfg['chinese_font']
        tc = cfg['text_color']

        # 主标题（大号）
        self.title_text = visual.TextStim(
            self.win, text='', font=font, height=0.09,
            color=tc, pos=(0, 0.65), bold=True,
            wrapWidth=1.6, alignText='center',
        )

        # 正文（中号）
        self.body_text = visual.TextStim(
            self.win, text='', font=font, height=0.055,
            color=tc, pos=(0, 0.05),
            wrapWidth=1.4, alignText='center',
        )

        # 底部提示
        self.hint_text = visual.TextStim(
            self.win, text='', font=font, height=0.038,
            color=[0.5, 0.5, 0.5], pos=(0, -0.55),
            wrapWidth=1.5, alignText='center',
        )

        # 大号数字（规则屏用）
        self.big_digit = visual.TextStim(
            self.win, text='', font=cfg['font_name'], height=0.22,
            color=cfg['stimulus_color'], pos=(0, 0), bold=True,
        )

        # 加载图标
        assets = Path(__file__).parent / 'assets'
        self.tap_icon = self._load_image(assets / 'tap_icon.png', (0, 0))
        self.stop_icon = self._load_image(assets / 'stop_icon.png', (0, 0))

    def _load_image(self, path: Path, pos: tuple) -> visual.ImageStim | None:
        if path.exists():
            return visual.ImageStim(
                self.win, image=str(path), pos=pos, size=(0.22, 0.22))
        return None

    # ------------------------------------------------------------------
    # 通用辅助
    # ------------------------------------------------------------------

    def _wait_for_button(self):
        """等待按钮或空格继续"""
        prev_pressed = True
        event.clearEvents()

        while True:
            keys = event.getKeys(keyList=['space', 'escape'])
            if 'escape' in keys:
                raise KeyboardInterrupt
            if 'space' in keys:
                return

            # 按钮hover效果
            mouse_pos = self.mouse.getPos()
            if self.stim.response_button.contains(mouse_pos):
                self.stim.set_button_state('hover')
            else:
                self.stim.set_button_state('normal')

            curr_pressed = self.mouse.getPressed()[0]
            if curr_pressed and not prev_pressed:
                if self.stim.response_button.contains(mouse_pos):
                    # 点击反馈
                    self.stim.set_button_state('pressed')
                    self.stim.draw_button()
                    self.win.flip()
                    core.wait(0.1)
                    self.stim.set_button_state('normal')
                    return
            prev_pressed = curr_pressed

            # 重绘按钮
            self.stim.draw_button()
            self.win.flip()
            core.wait(0.01, hogCPUperiod=0)

    def _show_screen(self, title: str, body: str = '',
                     hint: str = '（按按钮继续）',
                     extra_draw=None, body_pos: tuple | None = None):
        """显示指导语页面"""
        self.title_text.text = title
        self.body_text.text = body
        self.hint_text.text = hint
        if body_pos:
            self.body_text.pos = body_pos
        else:
            self.body_text.pos = (0, 0.05)

        # 先绘制一帧完整画面，然后等待
        while True:
            self.title_text.draw()
            if body:
                self.body_text.draw()
            if extra_draw:
                extra_draw()
            self.hint_text.draw()

            # 按钮hover
            mouse_pos = self.mouse.getPos()
            if self.stim.response_button.contains(mouse_pos):
                self.stim.set_button_state('hover')
            else:
                self.stim.set_button_state('normal')
            self.stim.draw_button()
            self.win.flip()

            # 检测按钮点击 / 空格
            keys = event.getKeys(keyList=['space', 'escape'])
            if 'escape' in keys:
                raise KeyboardInterrupt
            if 'space' in keys:
                return

            curr_pressed = self.mouse.getPressed()[0]
            if curr_pressed:
                if self.stim.response_button.contains(mouse_pos):
                    self.stim.set_button_state('pressed')
                    self.stim.draw_button()
                    self.win.flip()
                    core.wait(0.12)
                    self.stim.set_button_state('normal')
                    return

            core.wait(0.016, hogCPUperiod=0)

    # ------------------------------------------------------------------
    # 指导语屏幕（精简版，适合老年人）
    # ------------------------------------------------------------------

    def show_welcome(self):
        """屏幕1：欢迎（极简）"""
        self._show_screen(
            title='欢迎参加"眼疾手快"挑战！',
            body='屏幕会依次出现数字 1 - 9\n\n'
                 '看到数字 → 按下面的按钮\n\n'
                 '但有一个数字是例外……',
        )

    def show_rules(self):
        """屏幕2：核心规则（视觉化）"""
        cfg = self.config

        def draw_rule_visuals():
            # 大号红色 "3" + 禁止图标
            self.big_digit.text = '3'
            self.big_digit.color = [0.85, -0.6, -0.6]  # 醒目红色
            self.big_digit.pos = (-0.12, 0.30)
            self.big_digit.draw()

            if self.stop_icon:
                self.stop_icon.pos = (0.22, 0.30)
                self.stop_icon.draw()

            # 两行口诀（大字）— 留足间距
            rule1 = visual.TextStim(
                self.win, font=cfg['chinese_font'],
                height=0.07, color=[0.85, -0.6, -0.6],
                pos=(0, -0.05), bold=True,
                text='看到 3 → 别按！忍住！',
            )
            rule2 = visual.TextStim(
                self.win, font=cfg['chinese_font'],
                height=0.07, color=[-0.2, 0.5, -0.2],
                pos=(0, -0.22), bold=True,
                text='其他数字 → 快按！',
            )
            rule1.draw()
            rule2.draw()

        self.title_text.text = '记住这个捣乱数字：'
        self.hint_text.text = '（按按钮继续）'

        while True:
            self.title_text.draw()
            draw_rule_visuals()
            self.hint_text.draw()

            mouse_pos = self.mouse.getPos()
            if self.stim.response_button.contains(mouse_pos):
                self.stim.set_button_state('hover')
            else:
                self.stim.set_button_state('normal')
            self.stim.draw_button()
            self.win.flip()

            keys = event.getKeys(keyList=['space', 'escape'])
            if 'escape' in keys:
                raise KeyboardInterrupt
            if 'space' in keys:
                break
            if self.mouse.getPressed()[0]:
                if self.stim.response_button.contains(mouse_pos):
                    self.stim.set_button_state('pressed')
                    self.stim.draw_button()
                    self.win.flip()
                    core.wait(0.12)
                    break

            core.wait(0.016, hogCPUperiod=0)

        # 恢复
        self.big_digit.color = cfg['stimulus_color']

    def show_practice_intro(self):
        """屏幕3：练习介绍（简短 + 示例）"""
        cfg = self.config

        def draw_examples():
            # 左：数字7 + 按！ + 手势图标（间距加大）
            d7 = visual.TextStim(
                self.win, text='7', font=cfg['font_name'],
                height=0.16, color=cfg['stimulus_color'],
                pos=(-0.35, 0.38), bold=True)
            l7 = visual.TextStim(
                self.win, text='→ 按！', font=cfg['chinese_font'],
                height=0.055, color=[-0.2, 0.5, -0.2],
                pos=(-0.35, 0.18), bold=True)
            d7.draw()
            l7.draw()
            if self.tap_icon:
                self.tap_icon.pos = (-0.35, -0.02)
                self.tap_icon.draw()

            # 右：数字3 + 别按！ + 禁止图标
            d3 = visual.TextStim(
                self.win, text='3', font=cfg['font_name'],
                height=0.16, color=[0.85, -0.6, -0.6],
                pos=(0.35, 0.38), bold=True)
            l3 = visual.TextStim(
                self.win, text='→ 别按！', font=cfg['chinese_font'],
                height=0.055, color=[0.85, -0.6, -0.6],
                pos=(0.35, 0.18), bold=True)
            d3.draw()
            l3.draw()
            if self.stop_icon:
                self.stop_icon.pos = (0.35, -0.02)
                self.stop_icon.draw()

        self._show_screen(
            title='先练习几下',
            body='按错了屏幕会提醒您，没关系的！',
            hint='（准备好了？按按钮开始练习）',
            extra_draw=draw_examples,
            body_pos=(0, -0.28),
        )

    def show_practice_retry(self):
        """屏幕3.1：再练一次"""
        self._show_screen(
            title='再练习一次！',
            body='看到 3 别按，其他数字快按',
            hint='（按按钮开始）',
        )

    def show_formal_intro(self):
        """屏幕4：正式开始"""
        self._show_screen(
            title='练习结束，做得不错！',
            body='正式开始（约2分钟）\n\n'
                 '这次按错不会提示\n'
                 '请坚持做完\n\n'
                 '记住：看到 3 别按！',
            hint='（按按钮开始正式测试）',
        )

    def show_completion(self):
        """结束"""
        self._show_screen(
            title='测试结束！',
            body='感谢您的参与！',
            hint='（按按钮退出）',
        )

    # ------------------------------------------------------------------
    # Trial执行（含按钮反馈）
    # ------------------------------------------------------------------

    def run_trial(self, trial_info: dict, block_type: str,
                  show_feedback: bool = False) -> dict:
        """
        执行单个trial

        时序（PDF 2.2节）：
        1. 数字呈现 1250ms（可响应）
        2. 空白屏幕 1250ms（可响应）
        整个2500ms都是反应窗口
        """
        timing = self.config['timing']
        digit = trial_info['digit']
        trial_type = trial_info['trial_type']

        # 重置状态
        event.clearEvents()
        self.mouse.clickReset()
        prev_pressed = self.mouse.getPressed()[0]
        self.stim.set_button_state('normal')

        response_made = False
        reaction_time_ms = None
        self._press_flash_until = 0.0
        trial_clock = core.Clock()

        # ---- Phase 1: 数字呈现（1250ms）----
        stim_onset_ts = self.global_clock.getTime()
        trial_clock.reset()

        while trial_clock.getTime() < timing['stimulus_duration']:
            # 检测响应
            if not response_made:
                got_resp, rt, prev_pressed = self._check_response(
                    trial_clock, prev_pressed)
                if got_resp:
                    response_made = True
                    reaction_time_ms = rt
                    self._press_flash_until = trial_clock.getTime() + 0.1

            # 更新按钮外观
            self._update_button_visual(trial_clock)

            # 绘制
            self.stim.digit_stim.text = str(digit)
            self.stim.digit_stim.draw()
            self.stim.draw_button()
            self.win.flip()

        stim_offset_ts = self.global_clock.getTime()

        # ---- Phase 2: 空白屏幕（1250ms）----
        while trial_clock.getTime() < timing['trial_duration']:
            if not response_made:
                got_resp, rt, prev_pressed = self._check_response(
                    trial_clock, prev_pressed)
                if got_resp:
                    response_made = True
                    reaction_time_ms = rt
                    self._press_flash_until = trial_clock.getTime() + 0.1

            self._update_button_visual(trial_clock)
            self.stim.draw_button()
            self.win.flip()

        # 恢复按钮状态
        self.stim.set_button_state('normal')

        # ---- 计算准确性 ----
        is_nogo = trial_type == 'nogo'
        accuracy = (0 if response_made else 1) if is_nogo else (
            1 if response_made else 0)

        error_type = None
        if is_nogo and response_made:
            error_type = 'commission'
        elif not is_nogo and not response_made:
            error_type = 'omission'

        # ---- 练习反馈 ----
        if show_feedback and not accuracy:
            self.stim.present_feedback(correct=False, error_type=error_type)

        return {
            'block_type': block_type,
            'trial_index': trial_info['trial_index'],
            'digit': digit,
            'trial_type': trial_type,
            'stim_onset_ts': round(stim_onset_ts * 1000, 1),
            'stim_offset_ts': round(stim_offset_ts * 1000, 1),
            'response_made': response_made,
            'reaction_time_ms': round(reaction_time_ms, 1) if reaction_time_ms else None,
            'accuracy': accuracy,
            'error_type': error_type,
        }

    def _update_button_visual(self, trial_clock: core.Clock):
        """根据鼠标状态和按下闪烁更新按钮外观"""
        now = trial_clock.getTime()
        if now < self._press_flash_until:
            self.stim.set_button_state('pressed')
        else:
            mouse_pos = self.mouse.getPos()
            if self.stim.response_button.contains(mouse_pos):
                self.stim.set_button_state('hover')
            else:
                self.stim.set_button_state('normal')

    def _check_response(self, trial_clock: core.Clock,
                        prev_pressed: bool) -> tuple[bool, float | None, bool]:
        """检测响应（按钮点击 + 键盘空格）"""
        keys = event.getKeys(keyList=['space', 'escape'], timeStamped=trial_clock)
        for key, t in keys:
            if key == 'escape':
                raise KeyboardInterrupt
            if key == 'space':
                return True, t * 1000, prev_pressed

        curr_pressed = self.mouse.getPressed()[0]
        if curr_pressed and not prev_pressed:
            pos = self.mouse.getPos()
            if self.stim.response_button.contains(pos):
                rt = trial_clock.getTime() * 1000
                return True, rt, curr_pressed

        return False, None, curr_pressed

    # ------------------------------------------------------------------
    # 练习阶段
    # ------------------------------------------------------------------

    def run_practice(self) -> bool:
        pcfg = self.config['practice']
        max_attempts = pcfg['max_attempts']

        for attempt in range(1, max_attempts + 1):
            sequence = self.stim.generate_practice_sequence()
            go_correct = 0
            nogo_correct = 0

            for trial_info in sequence:
                result = self.run_trial(
                    trial_info,
                    block_type=f'practice{attempt}',
                    show_feedback=True,
                )
                self.data.add_trial(result)

                if result['trial_type'] == 'go' and result['accuracy']:
                    go_correct += 1
                elif result['trial_type'] == 'nogo' and result['accuracy']:
                    nogo_correct += 1

            if (go_correct >= pcfg['go_min_correct']
                    and nogo_correct >= pcfg['nogo_min_correct']):
                return True

            if attempt < max_attempts:
                self.show_practice_retry()

        return False

    # ------------------------------------------------------------------
    # 正式阶段
    # ------------------------------------------------------------------

    def run_formal(self):
        sequence = self.stim.generate_formal_sequence()
        for trial_info in sequence:
            result = self.run_trial(
                trial_info, block_type='formal', show_feedback=False)
            self.data.add_trial(result)

    # ------------------------------------------------------------------
    # Probe
    # ------------------------------------------------------------------

    def run_probe(self):
        """思维探测（1-9专注度滑轨）"""
        pcfg = self.config['probe']
        cfg = self.config

        prompt = visual.TextStim(
            self.win, font=cfg['chinese_font'],
            height=0.065, color=cfg['text_color'],
            pos=(0, 0.45), wrapWidth=1.5, alignText='center',
            text='请评价刚才对任务的专注程度',
            bold=True,
        )
        sub_prompt = visual.TextStim(
            self.win, font=cfg['chinese_font'],
            height=0.045, color=[0.5, 0.5, 0.5],
            pos=(0, 0.32), wrapWidth=1.5, alignText='center',
            text='1 = 完全不专注　　　9 = 非常专注',
        )

        slider = visual.Slider(
            self.win,
            ticks=list(range(pcfg['min_rating'], pcfg['max_rating'] + 1)),
            labels=[str(i) for i in range(1, 10)],
            pos=(0, 0.05),
            size=(1.2, 0.08),
            style='rating',
            granularity=1,
            color=cfg['text_color'],
            fillColor=[1, 1, 1],
            borderColor=cfg['text_color'],
            font=cfg['chinese_font'],
        )

        confirm_btn = visual.Rect(
            self.win, width=0.3, height=0.1,
            pos=(0, -0.35),
            fillColor=[1, 1, 1],
            lineWidth=0,
        )
        confirm_label = visual.TextStim(
            self.win, text='确认', font=cfg['chinese_font'],
            height=0.05, color=[-1, -1, -1], pos=(0, -0.35), bold=True,
        )

        probe_onset = self.global_clock.getTime()
        event.clearEvents()
        prev_pressed = False

        while True:
            prompt.draw()
            sub_prompt.draw()
            slider.draw()

            if slider.getRating() is not None:
                # hover效果
                mouse_pos = self.mouse.getPos()
                if confirm_btn.contains(mouse_pos):
                    confirm_btn.fillColor = [0.85, 0.85, 0.85]
                else:
                    confirm_btn.fillColor = [1, 1, 1]
                confirm_btn.draw()
                confirm_label.draw()

            self.win.flip()

            if slider.getRating() is not None:
                curr = self.mouse.getPressed()[0]
                if curr and not prev_pressed:
                    if confirm_btn.contains(self.mouse.getPos()):
                        break
                prev_pressed = curr

                keys = event.getKeys(keyList=['return', 'escape'])
                if 'escape' in keys:
                    raise KeyboardInterrupt
                if 'return' in keys:
                    break
            else:
                prev_pressed = self.mouse.getPressed()[0]

            core.wait(0.016, hogCPUperiod=0)

        probe_response = self.global_clock.getTime()
        self.data.set_probe(
            probe_onset_ts=probe_onset,
            probe_response_ts=probe_response,
            attention_rating=int(slider.getRating()),
        )
