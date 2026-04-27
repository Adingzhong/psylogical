"""
SART (Sustained Attention to Response Task)
持续注意反应任务 — 主程序入口

基于Robertson等人(1997)的经典Go/No-Go范式
适用人群：中老年人

运行方式：
    python main.py
"""

import json
import sys
from pathlib import Path

from psychopy import visual, gui, core, event

from experiment_manager import ExperimentManager
from stimulus_manager import StimulusManager
from data_manager import DataManager

SCRIPT_DIR = Path(__file__).parent
CONFIG_FILE = SCRIPT_DIR / 'config.json'
DATA_DIR = SCRIPT_DIR / 'data'


class SARTExperiment:
    """SART实验主控类"""

    def __init__(self):
        self.config = self._load_config()
        self.participant_info = None
        self.win = None
        self.exp_manager = None

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_chinese_font(preferred: str) -> str:
        """查找可用的中文字体，按优先级回退"""
        import matplotlib.font_manager as fm
        candidates = [preferred, 'Microsoft YaHei', 'SimHei', 'SimSun',
                       'Heiti SC', 'STHeiti', 'PingFang SC', 'Hiragino Sans GB']
        available = {f.name for f in fm.fontManager.ttflist}
        for name in candidates:
            if name in available:
                return name
        return preferred  # 都没找到就用原始值

    @staticmethod
    def _load_config() -> dict:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f'[WARN] 配置文件未找到: {CONFIG_FILE}，使用默认配置')
            return {
                'screen_size': [1024, 768],
                'fullscreen': True,
                'background_color': [-1, -1, -1],
                'stimulus_color': [1, 1, 1],
                'text_color': [1, 1, 1],
                'font_name': 'Courier New',
                'font_size_norm': 0.2,
                'chinese_font': 'Microsoft YaHei',
                'nogo_digit': 3,
                'timing': {
                    'stimulus_duration': 1.250,
                    'blank_duration': 1.250,
                    'trial_duration': 2.500,
                    'feedback_duration': 0.8,
                },
                'rt_valid_range': [150, 2000],
                'rt_outlier_sd': 3,
                'practice': {
                    'total_trials': 9, 'go_trials': 7, 'nogo_trials': 2,
                    'nogo_positions': [4, 7],
                    'go_min_correct': 6, 'nogo_min_correct': 1,
                    'max_attempts': 2,
                },
                'formal': {'total_trials': 36, 'repetitions': 4},
                'probe': {'min_rating': 1, 'max_rating': 9},
                'button': {
                    'width': 0.35, 'height': 0.12,
                    'position': [0.0, -0.85],
                    'color': [1, 1, 1], 'opacity': 0.9,
                },
            }

    # ------------------------------------------------------------------
    # 被试信息
    # ------------------------------------------------------------------

    def get_participant_info(self, subject_id: str = "") -> bool:
        """显示被试信息对话框，返回False表示取消。传入subject_id时跳过对话框。"""
        if subject_id:
            self.participant_info = {
                'subject_id': subject_id,
                'age': '',
                'sex': '',
                'group': '',
            }
            return True

        dlg = gui.Dlg(title='SART 持续注意反应任务')
        dlg.addField('被试编号：', '')

        result = dlg.show()
        if not dlg.OK or not result[0].strip():
            return False

        self.participant_info = {
            'subject_id': result[0].strip(),
            'age': '',
            'sex': '',
            'group': '',
        }
        return True

    # ------------------------------------------------------------------
    # 窗口设置
    # ------------------------------------------------------------------

    def setup_window(self):
        """创建PsychoPy窗口"""
        cfg = self.config
        # 解析可用的中文字体
        cfg['chinese_font'] = self._resolve_chinese_font(cfg['chinese_font'])
        print(f'使用中文字体: {cfg["chinese_font"]}')
        self.win = visual.Window(
            size=cfg['screen_size'],
            fullscr=cfg['fullscreen'],
            color=cfg['background_color'],
            units='norm',
            allowGUI=True,
            checkTiming=False,
        )
        self.win.mouseVisible = True  # 触屏交互需要显示光标

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def run(self, subject_id: str = ""):
        """执行完整实验流程"""
        # 1. 获取被试信息
        if not self.get_participant_info(subject_id):
            print('用户取消，退出实验')
            return

        subject_id = self.participant_info['subject_id']

        # 2. 初始化窗口和管理器
        self.setup_window()

        stim_mgr = StimulusManager(self.win, self.config)
        data_mgr = DataManager(subject_id, DATA_DIR)
        self.exp_manager = ExperimentManager(
            self.win, self.config, stim_mgr, data_mgr)

        try:
            # 3. 指导语
            self.exp_manager.show_welcome()
            self.exp_manager.show_rules()
            self.exp_manager.show_practice_intro()

            # 4. 练习阶段
            self.exp_manager.run_practice()
            # 无论练习是否通过，都进入正式阶段

            # 5. 正式阶段介绍
            self.exp_manager.show_formal_intro()

            # 6. 正式测试
            self.exp_manager.run_formal()

            # 7. Probe
            self.exp_manager.run_probe()

            # 8. 保存数据
            csv_path = data_mgr.save_csv()
            json_path = data_mgr.save_summary()
            print(f'数据已保存: {csv_path}')
            print(f'统计摘要: {json_path}')

            # 9. 结束
            self.exp_manager.show_completion()

        except KeyboardInterrupt:
            # ESC中断 → 保存已有数据
            print('实验被中断，保存部分数据...')
            csv_path = data_mgr.save_csv(tag='PARTIAL')
            print(f'部分数据已保存: {csv_path}')

        finally:
            self.win.close()
            core.quit()


if __name__ == '__main__':
    import argparse as _ap
    _parser = _ap.ArgumentParser(description="SART 持续注意反应任务")
    _parser.add_argument("--subject_id", type=str, default="", help="被试编号（传入后跳过对话框）")
    _args = _parser.parse_args()
    exp = SARTExperiment()
    exp.run(subject_id=_args.subject_id)
