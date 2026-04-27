"""
SART Stimulus Manager
刺激呈现与试次序列生成
"""

import random
from pathlib import Path

from psychopy import visual, core, event


class StimulusManager:
    """管理SART刺激呈现和试次序列"""

    DIGITS = list(range(1, 10))  # 1-9
    GO_DIGITS = [d for d in DIGITS if d != 3]  # 1,2,4,5,6,7,8,9

    def __init__(self, win: visual.Window, config: dict):
        self.win = win
        self.config = config
        self.nogo_digit = config['nogo_digit']
        self._button_state = 'normal'
        self._create_stimuli()

    # ------------------------------------------------------------------
    # 视觉元素初始化
    # ------------------------------------------------------------------

    def _create_stimuli(self):
        """创建所有视觉元素"""
        cfg = self.config
        btn_cfg = cfg['button']

        # 数字刺激（白色 Courier New，黑色背景上）
        self.digit_stim = visual.TextStim(
            self.win,
            text='',
            font=cfg['font_name'],
            height=cfg['font_size_norm'],
            color=cfg['stimulus_color'],
            pos=(0, 0.05),
            bold=True,
        )

        # ---- 响应按钮（带状态的蓝色圆角按钮） ----
        self.response_button = visual.Rect(
            self.win,
            width=btn_cfg['width'],
            height=btn_cfg['height'],
            pos=btn_cfg['position'],
            fillColor=btn_cfg['color_normal'],
            lineColor=btn_cfg['color_normal'],
            lineWidth=0,
        )
        # 按钮内文字
        self.button_label = visual.TextStim(
            self.win,
            text=btn_cfg.get('label', '按'),
            font=cfg['chinese_font'],
            height=0.06,
            color=btn_cfg.get('label_color', [1, 1, 1]),
            pos=btn_cfg['position'],
            bold=True,
        )

        # 按钮阴影（轻微偏移，模拟立体感）
        self.button_shadow = visual.Rect(
            self.win,
            width=btn_cfg['width'],
            height=btn_cfg['height'],
            pos=[btn_cfg['position'][0] + 0.005,
                 btn_cfg['position'][1] - 0.008],
            fillColor=[0.4, 0.4, 0.4],
            lineWidth=0,
            opacity=0.3,
        )

        # 练习阶段反馈文字
        self.feedback_text = visual.TextStim(
            self.win,
            text='',
            font=cfg['chinese_font'],
            height=0.09,
            color=[1, 1, 1],
            pos=(0, 0.05),
            wrapWidth=1.6,
            bold=True,
        )

        # 注视点
        self.fixation = visual.TextStim(
            self.win,
            text='+',
            font=cfg['font_name'],
            height=0.1,
            color=cfg['stimulus_color'],
            pos=(0, 0),
        )

    # ------------------------------------------------------------------
    # 按钮状态管理
    # ------------------------------------------------------------------

    def set_button_state(self, state: str):
        """设置按钮视觉状态: 'normal', 'hover', 'pressed'"""
        btn_cfg = self.config['button']
        color_map = {
            'normal': btn_cfg['color_normal'],
            'hover': btn_cfg['color_hover'],
            'pressed': btn_cfg['color_pressed'],
        }
        color = color_map.get(state, color_map['normal'])
        self.response_button.fillColor = color
        self.response_button.lineColor = color
        self._button_state = state

        # pressed状态下按钮微缩 + 阴影消失（按下感）
        if state == 'pressed':
            self.button_shadow.opacity = 0
            self.response_button.size = (
                btn_cfg['width'] * 0.96, btn_cfg['height'] * 0.92)
        else:
            self.button_shadow.opacity = 0.3
            self.response_button.size = (btn_cfg['width'], btn_cfg['height'])

    def draw_button(self):
        """绘制按钮（含阴影和文字）"""
        if self._button_state != 'pressed':
            self.button_shadow.draw()
        self.response_button.draw()
        self.button_label.draw()

    # ------------------------------------------------------------------
    # 试次序列生成
    # ------------------------------------------------------------------

    def generate_practice_sequence(self) -> list[dict]:
        """
        生成练习序列（PDF 3.2节）
        9个trials: 7个go + 2个no-go
        no-go固定在第4和第7个trial（1-indexed）
        """
        pcfg = self.config['practice']
        nogo_positions = pcfg['nogo_positions']

        go_digits = random.sample(self.GO_DIGITS, pcfg['go_trials'])
        random.shuffle(go_digits)

        sequence = []
        go_idx = 0
        for i in range(1, pcfg['total_trials'] + 1):
            if i in nogo_positions:
                sequence.append({
                    'digit': self.nogo_digit,
                    'trial_type': 'nogo',
                    'trial_index': i,
                })
            else:
                sequence.append({
                    'digit': go_digits[go_idx],
                    'trial_type': 'go',
                    'trial_index': i,
                })
                go_idx += 1

        return sequence

    def generate_formal_sequence(self) -> list[dict]:
        """
        生成正式序列（PDF 3.3节）
        36 trials: 9个数字各出现4次，随机排列
        约束：数字3不连续出现
        """
        reps = self.config['formal']['repetitions']
        digits = self.DIGITS * reps

        for _ in range(1000):
            random.shuffle(digits)
            if not self._has_consecutive_nogo(digits):
                break

        sequence = []
        for i, d in enumerate(digits, 1):
            sequence.append({
                'digit': d,
                'trial_type': 'nogo' if d == self.nogo_digit else 'go',
                'trial_index': i,
            })

        return sequence

    def _has_consecutive_nogo(self, digits: list[int]) -> bool:
        for i in range(len(digits) - 1):
            if digits[i] == self.nogo_digit and digits[i + 1] == self.nogo_digit:
                return True
        return False

    # ------------------------------------------------------------------
    # 刺激呈现
    # ------------------------------------------------------------------

    def present_digit(self, digit: int):
        """呈现数字 + 按钮（不flip，由调用方统一flip）"""
        self.digit_stim.text = str(digit)
        self.digit_stim.draw()
        self.draw_button()

    def present_blank_with_button(self):
        """呈现空白屏 + 按钮（不flip）"""
        self.draw_button()

    def present_blank(self):
        """纯空白屏"""
        self.win.flip()

    def present_feedback(self, correct: bool, error_type: str | None):
        """练习阶段错误反馈"""
        if correct:
            self.feedback_text.text = '\u2713'
            self.feedback_text.color = [-0.3, 0.6, -0.3]  # 深绿
        elif error_type == 'commission':
            self.feedback_text.text = '\u2717 数字3别按！'
            self.feedback_text.color = [0.8, -0.4, -0.4]  # 红
        else:
            self.feedback_text.text = '\u2717 记得按键！'
            self.feedback_text.color = [0.8, -0.4, -0.4]

        self.feedback_text.draw()
        self.win.flip()
        core.wait(self.config['timing']['feedback_duration'])
