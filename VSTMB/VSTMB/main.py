#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VSTMB (Visual Short-Term Memory Binding) Experiment System
基于视觉短期记忆特征结合的"日常物体-颜色绑定"任务
用于阿尔茨海默病/轻度认知障碍早期筛查

Author: Generated for VSTMB Research Project
Date: 2024
"""

import os
import sys
import json
import random
import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Any

# PsychoPy imports
from psychopy import visual, core, event, data, gui, logging
from psychopy.constants import (NOT_STARTED, STARTED, PLAYING, PAUSED,
                                STOPPED, FINISHED, PRESSED, RELEASED, FOREVER)

# Set up logging
logging.console.setLevel(logging.WARNING)

# Constants
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
CONFIG_FILE = SCRIPT_DIR / "config.json"

# 实验图片根目录 - 使用本地的相对路径
EXPERIMENT_STIMULI_DIR = SCRIPT_DIR / "实验图片"

# 不同条件的图片库路径
# Object条件: 实验图片/形状/ - 6张黑白形状图片 (A-F.png)
OBJECT_STIMULI_DIR = EXPERIMENT_STIMULI_DIR / "形状"

# Color条件: 实验图片/颜色/ - 按颜色分组，每种颜色6个形状
# 结构: 颜色/{颜色ID 1-6}/{形状ID A-F}.png
COLOR_STIMULI_DIR = EXPERIMENT_STIMULI_DIR / "颜色"

# Binding条件: 实验图片/形状-颜色/ - 按形状分组，每个形状6种颜色
# 结构: 形状-颜色/{形状ID A-F}/{颜色ID 1-6}.png
BINDING_STIMULI_DIR = EXPERIMENT_STIMULI_DIR / "形状-颜色"

# 形状和颜色的标识符
# 根据范式编写手册：6种物体，6种颜色
SHAPE_IDS = ['A', 'B', 'C', 'D', 'E', 'F']  # 6种形状
COLOR_IDS = ['1', '2', '3', '4', '5', '6']  # 6种颜色
NUM_SHAPES = 6  # 形状数量
NUM_COLORS = 6  # 颜色数量

# ============================================
# 刺激尺寸和位置设置（按屏幕比例换算）
# ============================================
# 手册要求（基于15寸屏幕）：
# - 物体尺寸：0.85cm × 0.85cm
# - 网格总大小：3cm × 3cm（不是4cm！）
# - 观看距离：65cm
# 
# 原始15寸屏幕（4:3）：物理宽度约30.5cm
# 你的16寸屏幕（16:10，2560×1600）：物理宽度约34.5cm
# 
# 按屏幕比例换算：
# - 网格占屏幕比例 = 3/30.5 = 9.84% → 34.5×9.84% = 3.4cm
# - 物体占屏幕比例 = 0.85/30.5 = 2.79% → 34.5×2.79% = 0.96cm
# ============================================

# 显示器参数（16寸 2560×1600）
MONITOR_WIDTH_CM = 34.5  # 16寸显示器物理宽度（厘米）
SCREEN_WIDTH_PX = 2560   # 屏幕像素宽度
SCREEN_HEIGHT_PX = 1600  # 屏幕像素高度

# 计算像素/厘米比例
PX_PER_CM = SCREEN_WIDTH_PX / MONITOR_WIDTH_CM  # ≈ 74.2 px/cm

# 物体尺寸（方案B：适度放大）
OBJECT_SIZE_CM = 1.3
OBJECT_SIZE_PX = 96  # 固定为96px

# 网格设置（方案B：适度放大）
GRID_TOTAL_SIZE_CM = 5.1  # 网格总大小（厘米）
GRID_TOTAL_SIZE_PX = 380  # 网格总大小（像素）

# 3×3网格的间距计算
GRID_SPACING_PX = 190  # 网格单元间距（像素）

# 3×3网格位置（像素坐标，相对于屏幕中心）
# 网格编号从左至右、从上到下为1-9
GRID_POSITIONS_PX = {
    1: (-GRID_SPACING_PX, GRID_SPACING_PX),    # 左上 (-190, 190)
    2: (0, GRID_SPACING_PX),                    # 中上 (0, 190)
    3: (GRID_SPACING_PX, GRID_SPACING_PX),     # 右上 (190, 190)
    4: (-GRID_SPACING_PX, 0),                   # 左中 (-190, 0)
    5: (0, 0),                                   # 中心 (0, 0)
    6: (GRID_SPACING_PX, 0),                    # 右中 (190, 0)
    7: (-GRID_SPACING_PX, -GRID_SPACING_PX),   # 左下 (-190, -190)
    8: (0, -GRID_SPACING_PX),                   # 中下 (0, -190)
    9: (GRID_SPACING_PX, -GRID_SPACING_PX)     # 右下 (190, -190)
}

# 可用于呈现刺激的位置（排除中心位置5）
AVAILABLE_POSITIONS = [1, 2, 3, 4, 6, 7, 8, 9]

# 保留归一化坐标版本用于兼容
GRID_SPACING_NORM = GRID_SPACING_PX / (SCREEN_WIDTH_PX / 2)
GRID_POSITIONS = {
    1: (-GRID_SPACING_NORM, GRID_SPACING_NORM * (SCREEN_WIDTH_PX / SCREEN_HEIGHT_PX)),
    2: (0.0, GRID_SPACING_NORM * (SCREEN_WIDTH_PX / SCREEN_HEIGHT_PX)),
    3: (GRID_SPACING_NORM, GRID_SPACING_NORM * (SCREEN_WIDTH_PX / SCREEN_HEIGHT_PX)),
    4: (-GRID_SPACING_NORM, 0.0),
    5: (0.0, 0.0),
    6: (GRID_SPACING_NORM, 0.0),
    7: (-GRID_SPACING_NORM, -GRID_SPACING_NORM * (SCREEN_WIDTH_PX / SCREEN_HEIGHT_PX)),
    8: (0.0, -GRID_SPACING_NORM * (SCREEN_WIDTH_PX / SCREEN_HEIGHT_PX)),
    9: (GRID_SPACING_NORM, -GRID_SPACING_NORM * (SCREEN_WIDTH_PX / SCREEN_HEIGHT_PX))
}

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Experiment parameters
FIXATION_DURATION = 0.5  # 500ms
STUDY_DURATION = 2.0     # 2000ms
RETENTION_DURATION = 0.9  # 900ms
TRANSITION_DURATION = 1.0 # 1000ms
TIMEOUT_DURATION = 5.0    # 5000ms

# Colors from Parra et al. (2010) - RGB values
# 注意：现在颜色通过图片文件直接呈现，不再需要程序叠加颜色
# 颜色编号1-6，按手册要求
STANDARD_COLORS = [
    [137, 137, 0],      # 颜色1 - 橄榄色
    [137, 0, 137],      # 颜色2 - 紫色
    [65, 158, 45],      # 颜色3 - 绿色
    [78, 139, 187],     # 颜色4 - 蓝色
    [255, 219, 0],      # 颜色5 - 黄色
    [251, 137, 124],    # 颜色6 - 粉色
]

# Convert RGB to PsychoPy color space (-1 to 1) - 保留用于兼容
PSYCHOPY_COLORS = [[(c/255.0)*2-1 for c in color] for color in STANDARD_COLORS]

# Quadrant positions - 保留用于兼容，但实际使用GRID_POSITIONS
QUADRANTS = {
    'LU': (-0.3, 0.3),   # Left Upper (对应网格1)
    'RU': (0.3, 0.3),    # Right Upper (对应网格3)
    'LD': (-0.3, -0.3),  # Left Down (对应网格7)
    'RD': (0.3, -0.3)    # Right Down (对应网格9)
}

@dataclass
class TrialData:
    """Data structure for a single trial
    
    根据范式编写手册的数据输出要求设计
    字段名称和格式完全按照手册要求
    """
    subject_id: str
    trial_index: int
    is_practice: bool
    condition: str  # 'Object', 'Color', 'Binding'
    trial_type: str  # 'Same', 'Different'
    
    # Response data
    response_key: str = ''  # '左' or '右'
    accuracy: int = 0  # 1 or 0
    sdt_classification: str = ''  # 'Hit', 'Miss', 'FA', 'CR'
    reaction_time: float = 0.0  # milliseconds
    
    # Timestamps
    probe_onset_ts: float = 0.0
    response_ts: float = 0.0
    timeout: bool = False
    
    # 学习阶段刺激信息 - 拆分为单独字段
    study_pos_1: int = 0  # 网格编号（1-9）
    study_obj_id_1: str = ''  # 物体ID（A-F）
    study_color_id_1: str = ''  # 颜色ID（1-6），Object条件为空
    study_pos_2: int = 0
    study_obj_id_2: str = ''
    study_color_id_2: str = ''
    
    # 探测阶段刺激信息 - 拆分为单独字段
    probe_pos_1: int = 0
    probe_obj_id_1: str = ''
    probe_color_id_1: str = ''
    probe_pos_2: int = 0
    probe_obj_id_2: str = ''
    probe_color_id_2: str = ''
    
    # Quality control
    pos_set_diff_ok: bool = True  # 位置约束核查

# 辅助函数：将索引转换为ID
def index_to_shape_id(idx: int) -> str:
    """将形状索引(0-5)转换为ID(A-F)"""
    if 0 <= idx <= 5:
        return chr(ord('A') + idx)
    return ''

def index_to_color_id(idx: int) -> str:
    """将颜色索引(0-5)转换为ID(1-6)"""
    if 0 <= idx <= 5:
        return str(idx + 1)
    return ''

def key_to_response(key: str, key_mapping: dict) -> str:
    """将按键转换为'左'/'右'"""
    if key.lower() == key_mapping.get('same', 'q').lower():
        return '左'
    elif key.lower() == key_mapping.get('different', 'p').lower():
        return '右'
    return ''

class VSTMBExperiment:
    """Main experiment class for VSTMB task"""
    
    def __init__(self):
        self.win = None
        self.participant_info = {}
        self.config = {}
        self.trial_data = []
        self.current_trial = 0
        self.current_block = 0
        self.conditions = ['Object', 'Color', 'Binding']
        self.balance_orders = {
            'A': ['Object', 'Color', 'Binding'],
            'B': ['Color', 'Binding', 'Object'],
            'C': ['Binding', 'Object', 'Color']
        }
        
        # Load configuration
        self.load_config()
        
        # Initialize stimuli - 不同条件使用不同的图片库
        self.object_images = {}  # 改为字典，按条件存储
        self.load_all_stimuli()
        
    def load_config(self):
        """Load experiment configuration"""
        default_config = {
            "screen_size": [1920, 1080],   # 用户屏幕尺寸
            "fullscreen": False,
            "background_color": [0.5, 0.5, 0.5],  # 浅灰色背景（手册要求）
            "text_color": [-1, -1, -1],    # 黑色文字
            "fixation_size": 0.05,
            "object_size": 0.15,
            "practice_trials": 4,          # 每组块4个练习试次
            "formal_trials": 18            # 每组块18个正式试次（手册要求）
        }
        
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = default_config
            # Save default config
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    def load_all_stimuli(self):
        """加载所有条件的图片库
        
        图片结构：
        - Object条件: 实验图片/形状/{A-F}.png (6张黑白形状)
        - Color条件: 实验图片/颜色/{1-6}/{A-F}.png (按颜色分组)
        - Binding条件: 实验图片/形状-颜色/{A-F}/{1-6}.png (按形状分组)
        """
        # Object条件 - 简单的形状图片列表
        self.object_images['Object'] = self._load_object_images()
        
        # Color条件 - 二维结构: color_images[颜色索引][形状索引] = 图片路径
        self.object_images['Color'] = self._load_color_images()
        
        # Binding条件 - 二维结构: binding_images[形状索引][颜色索引] = 图片路径
        self.object_images['Binding'] = self._load_binding_images()
    
    def _load_object_images(self):
        """加载Object条件的形状图片"""
        images = []
        if not OBJECT_STIMULI_DIR.exists():
            print(f"Warning: Object条件图片目录不存在: {OBJECT_STIMULI_DIR}")
            return [f"shape_{i}.png" for i in range(6)]
        
        for shape_id in SHAPE_IDS:
            img_path = OBJECT_STIMULI_DIR / f"{shape_id}.png"
            if img_path.exists():
                images.append(img_path)
            else:
                print(f"Warning: Object图片不存在: {img_path}")
        
        print(f"已加载 Object 条件的 {len(images)} 张形状图片")
        return images
    
    def _load_color_images(self):
        """加载Color条件的图片 - 按颜色分组
        
        返回二维结构: images[颜色索引][形状索引] = 图片路径
        """
        images = {}
        if not COLOR_STIMULI_DIR.exists():
            print(f"Warning: Color条件图片目录不存在: {COLOR_STIMULI_DIR}")
            return {}
        
        for color_idx, color_id in enumerate(COLOR_IDS):
            images[color_idx] = {}
            color_dir = COLOR_STIMULI_DIR / color_id
            if color_dir.exists():
                for shape_idx, shape_id in enumerate(SHAPE_IDS):
                    img_path = color_dir / f"{shape_id}.png"
                    if img_path.exists():
                        images[color_idx][shape_idx] = img_path
                    else:
                        print(f"Warning: Color图片不存在: {img_path}")
        
        total = sum(len(shapes) for shapes in images.values())
        print(f"已加载 Color 条件的 {total} 张图片 (6颜色 x 6形状)")
        return images
    
    def _load_binding_images(self):
        """加载Binding条件的图片 - 按形状分组
        
        返回二维结构: images[形状索引][颜色索引] = 图片路径
        """
        images = {}
        if not BINDING_STIMULI_DIR.exists():
            print(f"Warning: Binding条件图片目录不存在: {BINDING_STIMULI_DIR}")
            return {}
        
        for shape_idx, shape_id in enumerate(SHAPE_IDS):
            images[shape_idx] = {}
            shape_dir = BINDING_STIMULI_DIR / shape_id
            if shape_dir.exists():
                for color_idx, color_id in enumerate(COLOR_IDS):
                    img_path = shape_dir / f"{color_id}.png"
                    if img_path.exists():
                        images[shape_idx][color_idx] = img_path
                    else:
                        print(f"Warning: Binding图片不存在: {img_path}")
        
        total = sum(len(colors) for colors in images.values())
        print(f"已加载 Binding 条件的 {total} 张图片 (6形状 x 6颜色)")
        return images
    
    def _load_images_from_dir(self, stimuli_dir, condition_name):
        """从指定目录加载图片 - 保留用于兼容"""
        if not stimuli_dir.exists():
            print(f"Warning: {condition_name}条件的图片目录不存在: {stimuli_dir}")
            return [f"object_{i}.png" for i in range(6)]
        
        image_extensions = ['.png', '.jpg', '.jpeg', '.bmp']
        image_files = []
        for ext in image_extensions:
            image_files.extend(list(stimuli_dir.glob(f"*{ext}")))
        
        images = sorted(image_files)[:6]
        print(f"已加载 {condition_name} 条件的 {len(images)} 张图片: {stimuli_dir}")
        return images
    
    def load_object_stimuli(self):
        """Load object images from stimuli directory - 保留兼容性"""
        # 这个方法保留用于兼容，实际使用load_all_stimuli
        pass
    
    def get_participant_info(self, subject_id: str = ""):
        """Get participant information through dialog. 传入subject_id时跳过对话框。"""
        if subject_id:
            base_info = {
                'phone_number': subject_id,
                'subject_id': subject_id,
                'age': '',
                'education_years': '',
                'group': '',
                'balance_order': 'A',
                'key_mapping': 1,
                'experiment_date': datetime.datetime.now().isoformat(),
                'is_continuation': False
            }
            # Check for existing data
            existing_data = self.check_existing_data(subject_id)
            if existing_data:
                self.participant_info = base_info
                self.load_existing_data(subject_id, existing_data)
                return True
            self.participant_info = base_info
            return True

        dlg = gui.Dlg(title="VSTMB Experiment")
        dlg.addField('被试编号:', '')

        dlg.show()

        if dlg.OK:
            subject_id = str(dlg.data[0]).strip()
            if not subject_id:
                error_dlg = gui.Dlg(title="错误")
                error_dlg.addText("被试编号不能为空！")
                error_dlg.show()
                return self.get_participant_info()

            base_info = {
                'phone_number': subject_id,
                'subject_id': subject_id,
                'age': '',
                'education_years': '',
                'group': '',
                'balance_order': 'A',
                'key_mapping': 1,
                'experiment_date': datetime.datetime.now().isoformat(),
                'is_continuation': False
            }

            # Check for existing data
            existing_data = self.check_existing_data(subject_id)
            if existing_data:
                continue_dlg = gui.Dlg(title="发现已有数据")
                continue_dlg.addText(f"发现被试 {subject_id} 的已有数据:")
                continue_dlg.addText(f"最后保存时间: {existing_data['last_save_time']}")
                continue_dlg.addText(f"已完成试次: {existing_data['completed_trials']}")
                continue_dlg.addField('选择操作:', choices=['继续实验', '重新开始'])

                continue_dlg.show()

                if continue_dlg.OK:
                    if continue_dlg.data[0] == '继续实验':
                        self.participant_info = base_info
                        self.load_existing_data(subject_id, existing_data)
                        return True
                    else:
                        self.participant_info = base_info
                        return True
                else:
                    return False

            self.participant_info = base_info
            return True
        else:
            return False
    
    def check_existing_data(self, subject_id):
        """检查是否存在该被试的数据"""
        import glob
        import os
        
        # Look for CSV files with this subject ID
        pattern = f"data/VSTMB_{subject_id}_*.csv"
        files = glob.glob(pattern)
        
        if files:
            # Get the most recent file
            latest_file = max(files, key=os.path.getctime)
            
            try:
                import pandas as pd
                df = pd.read_csv(latest_file)
                
                return {
                    'file_path': latest_file,
                    'last_save_time': datetime.datetime.fromtimestamp(os.path.getctime(latest_file)).strftime("%Y-%m-%d %H:%M:%S"),
                    'completed_trials': len(df),
                    'conditions_completed': df['condition'].unique().tolist() if len(df) > 0 else []
                }
            except:
                return None
        
        return None
    
    def load_existing_data(self, subject_id, existing_data):
        """加载已有数据并设置继续点"""
        try:
            import pandas as pd
            df = pd.read_csv(existing_data['file_path'])
            
            if len(df) > 0:
                # Get participant info from existing data
                last_row = df.iloc[-1]
                self.participant_info = {
                    'subject_id': subject_id,
                    'age': 25,  # Default, will be updated if available
                    'education_years': 12,  # Default
                    'group': 'HC',  # Default
                    'balance_order': 'A',  # Default
                    'key_mapping': 1,  # Default
                    'experiment_date': datetime.datetime.now().isoformat(),
                    'is_continuation': True,
                    'continuation_point': {
                        'last_condition': last_row['condition'],
                        'last_trial_index': last_row['trial_index'],
                        'completed_conditions': df['condition'].unique().tolist()
                    }
                }
                
                print(f"加载已有数据: {len(df)} 个试次")
                print(f"已完成条件: {self.participant_info['continuation_point']['completed_conditions']}")
            
        except Exception as e:
            print(f"加载数据失败: {e}")
            self.participant_info['is_continuation'] = False
    
    def setup_window(self):
        """Initialize PsychoPy window — 自动适配屏幕分辨率"""
        self.win = visual.Window(
            fullscr=self.config['fullscreen'],
            color=self.config['background_color'],
            units='pix',
            allowGUI=True,
            checkTiming=False,
            monitor='testMonitor'
        )
        self.win.mouseVisible = True

        # 获取实际屏幕尺寸，动态缩放所有像素坐标
        actual_w, actual_h = self.win.size
        config_w = self.config['screen_size'][0]
        self.scale = actual_w / config_w  # 缩放因子
        print(f"[VSTMB] 屏幕: {actual_w}x{actual_h}, 配置基准: {config_w}, 缩放: {self.scale:.2f}")

        # 更新全局像素常量
        global GRID_SPACING_PX, OBJECT_SIZE_PX, GRID_POSITIONS_PX
        GRID_SPACING_PX = int(190 * self.scale)
        OBJECT_SIZE_PX = int(96 * self.scale)
        GRID_POSITIONS_PX = {
            1: (-GRID_SPACING_PX, GRID_SPACING_PX),
            2: (0, GRID_SPACING_PX),
            3: (GRID_SPACING_PX, GRID_SPACING_PX),
            4: (-GRID_SPACING_PX, 0),
            5: (0, 0),
            6: (GRID_SPACING_PX, 0),
            7: (-GRID_SPACING_PX, -GRID_SPACING_PX),
            8: (0, -GRID_SPACING_PX),
            9: (GRID_SPACING_PX, -GRID_SPACING_PX)
        }

        # Set up basic visual elements — 中文字体
        self.fixation = visual.TextStim(
            self.win, text='+',
            color=self.config['text_color'],
            height=int(50 * self.scale),
            font='Arial',
            units='pix'
        )

        self.instruction_text = visual.TextStim(
            self.win, text='',
            color=self.config['text_color'],
            height=int(36 * self.scale),
            wrapWidth=int(actual_w * 0.75),
            font='PingFang SC',
            units='pix'
        )
    
    def show_welcome(self):
        """显示欢迎界面"""
        # Import managers here to avoid circular imports
        from experiment_manager import ExperimentManager
        
        # Initialize experiment manager
        self.exp_manager = ExperimentManager(
            self.win, self.config, self.participant_info, 
            self.object_images, PSYCHOPY_COLORS, QUADRANTS
        )
        
        # Show welcome screen
        self.exp_manager.show_welcome()
    
    def show_rest(self):
        """显示休息界面"""
        self.exp_manager.show_rest()
    
    def show_completion(self):
        """显示完成界面"""
        self.exp_manager.show_completion()
    
    def run_block(self, condition, is_practice=False):
        """运行一个实验区块"""
        self.exp_manager.run_block(condition, is_practice)
    
    def save_data(self):
        """保存实验数据"""
        # Generate filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"VSTMB_{self.participant_info['subject_id']}_{timestamp}"
        
        # Save trial data to CSV
        csv_file = DATA_DIR / f"{filename}.csv"
        self.exp_manager.data_manager.save_to_csv(str(csv_file))
        
        # Save summary data to JSON
        json_file = DATA_DIR / f"{filename}_summary.json"
        self.exp_manager.data_manager.save_summary_to_json(str(json_file), self.participant_info)
        
        print(f"Data saved to: {csv_file}")
        print(f"Summary saved to: {json_file}")

    def run(self, subject_id: str = ""):
        """Main experiment execution"""
        try:
            # Get participant information
            if not self.get_participant_info(subject_id):
                return
            
            # Setup window
            self.setup_window()
            
            # Show welcome screen
            self.show_welcome()
            
            # Get condition order based on balance
            condition_order = self.balance_orders[self.participant_info['balance_order']]
            
            # Check if this is a continuation
            start_condition_idx = 0
            if self.participant_info.get('is_continuation', False):
                continuation_point = self.participant_info.get('continuation_point', {})
                completed_conditions = continuation_point.get('completed_conditions', [])
                
                # Find where to continue
                for idx, condition in enumerate(condition_order):
                    if condition not in completed_conditions:
                        start_condition_idx = idx
                        break
                
                if start_condition_idx > 0:
                    continue_text = f"""欢迎回来！

检测到您之前的进度。

已完成条件: {', '.join(completed_conditions)}

按空格键继续"""
                    
                    self.exp_manager.instruction_text.text = continue_text
                    self.exp_manager.instruction_text.draw()
                    self.win.flip()
                    event.waitKeys(keyList=['space', 'Space'])
            
            # Run each condition starting from continuation point
            for block_idx in range(start_condition_idx, len(condition_order)):
                condition = condition_order[block_idx]
                self.current_block = block_idx
                
                # Practice phase
                self.run_block(condition, is_practice=True)
                
                # Formal phase
                self.run_block(condition, is_practice=False)
                
                # Rest between blocks (except after last block)
                if block_idx < len(condition_order) - 1:
                    self.show_rest()
            
            # Show completion message
            self.show_completion()
            
            # Save data
            self.save_data()
            
        except KeyboardInterrupt:
            print("实验被用户中断")
            self.save_partial_data()
        except Exception as e:
            import traceback
            print(f"实验错误: {e}")
            traceback.print_exc()
            self.save_partial_data()
            raise
        finally:
            if self.win:
                self.win.close()
            core.quit()
    
    def save_partial_data(self):
        """保存部分完成的实验数据"""
        if hasattr(self, 'exp_manager') and self.exp_manager.data_manager.trial_data:
            # Generate filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"VSTMB_{self.participant_info['subject_id']}_{timestamp}_PARTIAL"
            
            # Save trial data to CSV
            csv_file = DATA_DIR / f"{filename}.csv"
            self.exp_manager.data_manager.save_to_csv(str(csv_file))
            
            # Save summary data to JSON
            json_file = DATA_DIR / f"{filename}_summary.json"
            self.exp_manager.data_manager.save_summary_to_json(str(json_file), self.participant_info)
            
            print(f"部分数据已保存到: {csv_file}")
            print(f"部分汇总已保存到: {json_file}")
        else:
            print("没有数据需要保存")

if __name__ == '__main__':
    import argparse as _ap
    _parser = _ap.ArgumentParser(description="VSTMB Experiment")
    _parser.add_argument("--subject_id", type=str, default="", help="被试编号（传入后跳过对话框）")
    _args = _parser.parse_args()
    experiment = VSTMBExperiment()
    experiment.run(subject_id=_args.subject_id)