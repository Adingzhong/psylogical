#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Stimulus Manager for VSTMB Experiment
处理视觉刺激的呈现和管理

图片结构：
- Object条件: 实验图片/形状/{A-F}.png (6张黑白形状)
- Color条件: 实验图片/颜色/{1-6}/{A-F}.png (按颜色分组)
- Binding条件: 实验图片/形状-颜色/{A-F}/{1-6}.png (按形状分组)

位置设置：
- 3×3网格，编号1-9（从左至右、从上到下）
- 排除中心位置5，可用位置为1,2,3,4,6,7,8,9
"""

import random
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any
from psychopy import visual, core

# 形状和颜色的数量
NUM_SHAPES = 6  # A-F
NUM_COLORS = 6  # 1-6

# ============================================
# 刺激尺寸和位置设置（根据范式编写手册）
# ============================================
# 手册要求：
# - 物体尺寸：0.85cm × 0.85cm（视角0.75°）
# - 物体之间最小间距：0.5°（在65cm距离下约0.57cm）
# - 网格总大小：4cm × 4cm
# - 观看距离：65cm
#
# 间距验证：
# - 网格单元间距 = 4cm / 2 = 2cm（从中心到相邻格子中心）
# - 相邻物体边缘间距 = 2cm - 0.85cm = 1.15cm > 0.57cm ✓
# - 满足0.5°最小间距要求
# ============================================

# 形状和颜色的数量
NUM_SHAPES = 6  # A-F
NUM_COLORS = 6  # 1-6

# ============================================
# 按屏幕比例换算（保持与原始15寸屏幕相同的视觉比例）
# 
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
# 注意：PsychoPy的坐标系是 x向右为正，y向上为正
# 网格编号：
#   1  2  3
#   4  5  6
#   7  8  9
GRID_POSITIONS_PX = {
    1: (-GRID_SPACING_PX, GRID_SPACING_PX),    # 左上 (-190, 190)
    2: (0, GRID_SPACING_PX),                    # 中上 (0, 190)
    3: (GRID_SPACING_PX, GRID_SPACING_PX),     # 右上 (190, 190)
    4: (-GRID_SPACING_PX, 0),                   # 左中 (-190, 0)
    5: (0, 0),                                   # 中心 (0, 0)
    6: (GRID_SPACING_PX, 0),                    # 右中 (190, 0)
    7: (-GRID_SPACING_PX, -GRID_SPACING_PX),   # 左下 (-190, -190)
    8: (0, -GRID_SPACING_PX),                   # 中下 (0, -190)
    9: (GRID_SPACING_PX, -GRID_SPACING_PX)     # 右下 (-190, -190)
}

# 可用于呈现刺激的位置（排除中心位置5）
AVAILABLE_POSITIONS = [1, 2, 3, 4, 6, 7, 8, 9]

class StimulusManager:
    """管理实验刺激的呈现"""
    
    def __init__(self, win, object_images, colors, quadrants, object_size=0.25):
        self.win = win
        # object_images 是字典，按条件存储不同结构的图片
        self.object_images_dict = object_images
        self.current_condition = 'Object'
        self.colors = colors
        self.quadrants = quadrants  # 保留用于兼容
        self.object_size = object_size
        
        # 使用3×3网格位置（像素坐标）
        self.grid_positions_pix = GRID_POSITIONS_PX
        self.available_positions = AVAILABLE_POSITIONS
        
        # 图片尺寸（像素）
        # 手册要求0.85cm，按36.2px/cm计算约31px
        # 但为保证清晰度，实际使用时可适当放大
        self.pixel_size = (OBJECT_SIZE_PX, OBJECT_SIZE_PX)
        
        # 获取窗口尺寸
        self.win_width = win.size[0]
        self.win_height = win.size[1]
        
        # 保留quadrants_pix用于兼容旧代码
        self.quadrants_pix = {}
        for key, (norm_x, norm_y) in quadrants.items():
            pix_x = norm_x * self.win_width / 2
            pix_y = norm_y * self.win_height / 2
            self.quadrants_pix[key] = (pix_x, pix_y)
        
        # Create visual stimuli objects
        self.visual_objects = []
        self.setup_visual_objects()
    
    def set_condition(self, condition):
        """设置当前条件"""
        self.current_condition = condition
    
    def get_image_path(self, shape_idx, color_idx=None):
        """根据当前条件获取图片路径
        
        Args:
            shape_idx: 形状索引 (0-5)
            color_idx: 颜色索引 (0-5)，Object条件不需要
        
        Returns:
            图片路径
        """
        condition = self.current_condition
        images = self.object_images_dict.get(condition, {})
        
        if condition == 'Object':
            # Object条件: 简单列表，只需形状索引
            if isinstance(images, list) and shape_idx < len(images):
                return images[shape_idx]
            return None
        
        elif condition == 'Color':
            # Color条件: images[颜色索引][形状索引]
            if color_idx is not None and color_idx in images:
                if shape_idx in images[color_idx]:
                    return images[color_idx][shape_idx]
            return None
        
        elif condition == 'Binding':
            # Binding条件: images[形状索引][颜色索引]
            if shape_idx in images and color_idx is not None:
                if color_idx in images[shape_idx]:
                    return images[shape_idx][color_idx]
            return None
        
        return None
    
    def setup_visual_objects(self):
        """创建视觉对象"""
        # 使用方案B的物体尺寸：96px × 96px（正方形）
        pixel_size = (OBJECT_SIZE_PX, OBJECT_SIZE_PX)
        
        for i in range(2):
            obj = visual.ImageStim(
                self.win,
                image=None,
                size=pixel_size,
                units='pix',  # 使用像素单位确保正方形不变形
                pos=(0, 0),
                interpolate=True  # 启用插值以提高缩放质量
            )
            self.visual_objects.append(obj)
        
        # 打印调试信息
        print(f"[方案B] 物体尺寸: {OBJECT_SIZE_PX}px × {OBJECT_SIZE_PX}px ({OBJECT_SIZE_CM}cm)")
        print(f"[方案B] 视角: 1.13° (原始0.75°的1.51倍)")
        print(f"[方案B] 网格间距: {GRID_SPACING_PX}px")
        print(f"[方案B] 网格总大小: {GRID_TOTAL_SIZE_PX}px ({GRID_TOTAL_SIZE_CM}cm)")
        print(f"[方案B] 相邻物体边缘间距: {GRID_SPACING_PX - OBJECT_SIZE_PX}px")
        print(f"[方案B] 网格位置: {GRID_POSITIONS_PX}")
    
    def set_overlay_callback(self, callback):
        """设置叠加绘制回调（用于常驻按钮等）"""
        self._overlay_cb = callback

    def _draw_overlay(self):
        """调用叠加绘制"""
        if hasattr(self, '_overlay_cb') and self._overlay_cb:
            self._overlay_cb()

    def present_fixation(self, duration=0.5):
        """呈现注视点"""
        fixation = visual.TextStim(
            self.win,
            text='+',
            color=[-1, -1, -1],
            height=50,
            font='Arial',
            units='pix'
        )

        fixation.draw()
        self._draw_overlay()
        self.win.flip()
        core.wait(duration)
    
    def present_study_stimuli(self, shape_ids, color_ids, positions, duration=2.0):
        """呈现学习阶段刺激
        
        Args:
            shape_ids: 形状索引列表 [0-5, 0-5]
            color_ids: 颜色索引列表 [0-5, 0-5] 或 [-1, -1] (Object条件)
            positions: 位置列表 [1-9, 1-9]（网格编号）
            duration: 呈现时长
        """
        print(f"[学习阶段] 位置: {positions}, 网格坐标: {[self.grid_positions_pix.get(p) for p in positions]}")
        print(f"[学习阶段] 图片尺寸: {self.pixel_size}")
        
        for i, (shape_idx, color_idx, pos_id) in enumerate(zip(shape_ids, color_ids, positions)):
            # 获取像素坐标
            pos = self.grid_positions_pix.get(pos_id, (0, 0))
            
            if i < len(self.visual_objects):
                obj = self.visual_objects[i]
                obj.pos = pos
                obj.size = self.pixel_size  # 确保每次都设置尺寸
                
                # 获取图片路径
                img_path = self.get_image_path(shape_idx, color_idx if color_idx >= 0 else None)
                if img_path and Path(img_path).exists():
                    obj.image = str(img_path)
                
                obj.draw()

        self._draw_overlay()
        self.win.flip()
        core.wait(duration)

    def present_probe_stimuli(self, shape_ids, color_ids, positions):
        """呈现探测阶段刺激"""
        print(f"[探测阶段] 位置: {positions}, 网格坐标: {[self.grid_positions_pix.get(p) for p in positions]}")
        print(f"[探测阶段] 图片尺寸: {self.pixel_size}")
        
        for i, (shape_idx, color_idx, pos_id) in enumerate(zip(shape_ids, color_ids, positions)):
            # 获取像素坐标
            pos = self.grid_positions_pix.get(pos_id, (0, 0))
            
            if i < len(self.visual_objects):
                obj = self.visual_objects[i]
                obj.pos = pos
                
                img_path = self.get_image_path(shape_idx, color_idx if color_idx >= 0 else None)
                if img_path and Path(img_path).exists():
                    obj.image = str(img_path)
                
                # 确保每次都设置尺寸（在设置image之后）
                obj.size = self.pixel_size
                obj.draw()

        self._draw_overlay()
        self.win.flip()

    def present_blank_screen(self, duration):
        """呈现空白屏幕（保持期）"""
        self._draw_overlay()
        self.win.flip()
        core.wait(duration)

    def generate_trial_stimuli(self, condition, trial_type):
        """生成试次刺激
        
        Args:
            condition: 'Object', 'Color', 'Binding'
            trial_type: 'Same', 'Different'
        
        Returns:
            dict: 包含学习和探测阶段刺激信息的字典
        """
        self.set_condition(condition)
        
        # 从可用位置（1-9，排除5）中随机选择两个位置用于学习阶段
        study_positions = random.sample(self.available_positions, 2)
        
        # 探测阶段位置：随机选择两个位置，与学习阶段独立
        # 手册要求：学习阶段与探测阶段的呈现位置均为随机生成，且两阶段相互独立
        probe_positions = random.sample(self.available_positions, 2)
        
        # 随机选择两个不同的形状 (0-5)
        study_shape_ids = random.sample(range(NUM_SHAPES), 2)
        
        # 根据条件设置颜色
        if condition == 'Object':
            # Object条件：不使用颜色
            study_color_ids = [-1, -1]
        else:
            # Color和Binding条件：随机选择两个不同的颜色 (0-5)
            study_color_ids = random.sample(range(NUM_COLORS), 2)
        
        # 生成探测阶段刺激
        if trial_type == 'Same':
            # 相同试次：探测刺激与学习刺激完全相同
            probe_shape_ids = study_shape_ids.copy()
            probe_color_ids = study_color_ids.copy()
        else:  # Different
            if condition == 'Object':
                # Object条件：改变形状
                probe_shape_ids = self._get_different_shapes(study_shape_ids)
                probe_color_ids = [-1, -1]
            elif condition == 'Color':
                # Color条件：保持形状不变，改变颜色
                probe_shape_ids = study_shape_ids.copy()
                probe_color_ids = self._get_different_colors(study_color_ids)
            elif condition == 'Binding':
                # Binding条件：保持形状和颜色不变，但交换绑定关系
                probe_shape_ids = study_shape_ids.copy()
                probe_color_ids = [study_color_ids[1], study_color_ids[0]]  # 交换颜色
        
        # 位置约束检查：学习和探测位置集合是否不同
        position_constraint_ok = set(study_positions) != set(probe_positions)
        
        return {
            'study_positions': study_positions,
            'study_object_ids': study_shape_ids,
            'study_color_ids': study_color_ids,
            'probe_positions': probe_positions,
            'probe_object_ids': probe_shape_ids,
            'probe_color_ids': probe_color_ids,
            'position_constraint_ok': position_constraint_ok
        }
    
    def _get_different_shapes(self, current_shapes):
        """获取不同的形状ID"""
        available_shapes = list(range(NUM_SHAPES))
        different_shapes = []
        
        for shape_id in current_shapes:
            candidates = [s for s in available_shapes if s != shape_id and s not in different_shapes]
            if candidates:
                different_shapes.append(random.choice(candidates))
            else:
                different_shapes.append((shape_id + 1) % NUM_SHAPES)
        
        return different_shapes
    
    def _get_different_colors(self, current_colors):
        """获取不同的颜色ID"""
        available_colors = list(range(NUM_COLORS))
        different_colors = []
        
        for color_id in current_colors:
            candidates = [c for c in available_colors if c != color_id and c not in different_colors]
            if candidates:
                different_colors.append(random.choice(candidates))
            else:
                different_colors.append((color_id + 1) % NUM_COLORS)
        
        return different_colors
    
    def get_current_images(self):
        """获取当前条件的图片数据 - 用于兼容"""
        return self.object_images_dict.get(self.current_condition, {})
