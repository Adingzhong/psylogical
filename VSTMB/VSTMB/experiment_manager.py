#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Experiment Manager for VSTMB Experiment
管理实验流程和用户界面
"""

import os
import random
from pathlib import Path
from typing import List, Dict, Any
from psychopy import visual, core, event
from stimulus_manager import StimulusManager
from data_manager import DataManager

class ExperimentManager:
    """管理实验流程"""
    
    def __init__(self, win, config, participant_info, object_images, colors, quadrants):
        self.win = win
        self.config = config
        self.participant_info = participant_info
        self.object_images = object_images  # 现在是字典，按条件存储
        self.colors = colors
        self.quadrants = quadrants
        
        # Initialize managers - 传递完整的图片字典
        self.stimulus_manager = StimulusManager(win, object_images, colors, quadrants, config['object_size'])
        self.data_manager = DataManager()

        # 设置按钮常驻回调（在所有刺激画面上叠加按钮）— 在按钮创建后设置
        # 延迟到按钮创建之后，见 __init__ 末尾
        
        # Create instruction text - 中文字体 + 自适应宽度
        win_w = self.win.size[0]
        self.instruction_text = visual.TextStim(
            self.win,
            text='',
            color=config['text_color'],
            height=int(36 * win_w / 2560),
            wrapWidth=int(win_w * 0.75),
            font='PingFang SC',
            units='pix'
        )
        
        # 触摸响应映射（替代键盘 Q/P）
        # key_mapping 保留用于数据记录兼容，但实际用触摸
        self.key_mapping = self._setup_key_mapping()

        # 缩放因子
        self._s = win_w / 2560
        s = self._s
        win_h = self.win.size[1]

        # ========== 触摸响应按钮（替代 Q/P 键盘） ==========
        # 位置：屏幕下方 1/4 处，左右各一个大圆，方便触摸
        btn_radius = int(110 * s)
        btn_y = int(-win_h * 0.32)  # 屏幕下方约 1/3 处
        btn_x = int(win_w * 0.22)   # 左右偏移

        self.left_btn_pos = (-btn_x, btn_y)
        self.right_btn_pos = (btn_x, btn_y)
        self.btn_radius = btn_radius

        # 左按钮 - "相同" (中性灰，避免 Stroop 干扰)
        self.left_btn_bg = visual.Circle(
            self.win, radius=btn_radius,
            pos=self.left_btn_pos,
            fillColor=[0.75, 0.75, 0.75], lineColor=[0.3, 0.3, 0.3],
            lineWidth=3, units='pix'
        )
        self.left_btn_label = visual.TextStim(
            self.win, text='相同', pos=self.left_btn_pos,
            color=[-1, -1, -1], height=int(38 * s), bold=True,
            font='PingFang SC', units='pix'
        )

        # 右按钮 - "不同" (中性灰)
        self.right_btn_bg = visual.Circle(
            self.win, radius=btn_radius,
            pos=self.right_btn_pos,
            fillColor=[0.75, 0.75, 0.75], lineColor=[0.3, 0.3, 0.3],
            lineWidth=3, units='pix'
        )
        self.right_btn_label = visual.TextStim(
            self.win, text='不同', pos=self.right_btn_pos,
            color=[-1, -1, -1], height=int(38 * s), bold=True,
            font='PingFang SC', units='pix'
        )

        # 按下状态颜色（微暗，纯亮度变化，无色相）
        self.left_btn_press_color = [0.55, 0.55, 0.55]
        self.left_btn_normal_color = [0.75, 0.75, 0.75]
        self.right_btn_press_color = [0.55, 0.55, 0.55]
        self.right_btn_normal_color = [0.75, 0.75, 0.75]

        # 鼠标/触摸
        self.mouse = event.Mouse(win=self.win, visible=True)

        # 提示文字
        self.response_prompt = visual.TextStim(
            self.win, text='请点击按钮作答',
            color=[-1, -1, -1],
            height=int(30 * s),
            pos=(0, int(btn_y + btn_radius + 40 * s)),
            font='PingFang SC', units='pix'
        )

        # 兼容：key_reminder 不再需要，但保留空方法
        self.key_reminder = visual.TextStim(
            self.win, text='', height=1, units='pix'
        )

        # 注册按钮常驻回调 — 所有刺激画面都会叠加按钮
        self.stimulus_manager.set_overlay_callback(self.show_key_reminder)
    
    def _setup_key_mapping(self):
        """设置按键映射"""
        if self.participant_info['key_mapping'] == 1:
            return {'same': 'q', 'different': 'p'}
        else:
            return {'same': 'p', 'different': 'q'}

    # ========== 图片指导语系统 ==========

    def _get_instruction_path(self, filename):
        """获取指导语图片路径"""
        return str(Path(__file__).parent / "assets" / "instructions" / filename)

    def _show_instruction_page(self, image_file, subtitle="", wait_keys=None):
        """
        显示指导语页面：上方图片 + 下方副标题 + 等待按键
        图片承载主要信息，副标题仅做简短补充
        """
        if wait_keys is None:
            wait_keys = ['space', 'escape']

        s = self._s
        drawables = []

        # 指导语图片（上半部分）
        img_path = self._get_instruction_path(image_file) if image_file else None
        if img_path and os.path.exists(img_path):
            img = visual.ImageStim(
                self.win, image=img_path,
                pos=(0, int(120 * s)),
                size=(int(900 * s), int(506 * s)),
                units='pix'
            )
            drawables.append(img)

        # 副标题（下方，简短文字）
        if subtitle:
            sub = visual.TextStim(
                self.win, text=subtitle,
                color=self.config['text_color'],
                height=int(34 * s),
                pos=(0, int(-200 * s)),
                wrapWidth=int(1200 * s),
                font='PingFang SC',
                units='pix'
            )
            drawables.append(sub)

        # 底部提示（在按钮上方）
        hint = visual.TextStim(
            self.win, text="点击屏幕继续",
            color=[0.3, 0.3, 0.3],
            height=int(22 * s),
            pos=(0, int(-300 * s)),
            font='PingFang SC',
            units='pix'
        )
        drawables.append(hint)

        # 绘制所有元素（指导语页面不显示响应按钮）
        for d in drawables:
            d.draw()
        self.win.flip()

        # 等待交互（键盘或鼠标点击）
        event.clearEvents()
        mouse = event.Mouse(win=self.win, visible=True)
        mouse.clickReset()
        prev_pressed = False
        while True:
            keys = event.getKeys(keyList=wait_keys + ['return'])
            if keys:
                if 'escape' in keys:
                    self.handle_escape_exit()
                    return
                break
            # 鼠标/触摸点击
            is_pressed = mouse.getPressed()[0] == 1
            if prev_pressed and not is_pressed:
                break
            prev_pressed = is_pressed
            core.wait(0.016)

    def show_welcome(self):
        """显示欢迎界面：流程图 + 触摸按钮说明"""
        # 第一页：任务流程
        self._show_instruction_page(
            "01_welcome.png",
            subtitle="观察物体 → 短暂消失 → 再次出现 → 判断是否一样"
        )

        # 第二页：触摸按钮说明
        self._show_instruction_page(
            "02_key_mapping_1.png",
            subtitle="一样 → 点左边【相同】        不一样 → 点右边【不同】"
        )

    def show_practice_instruction(self, condition):
        """显示练习指导语：条件对应图片 + 简短说明"""
        condition_config = {
            'Object': {
                'image': '03_focus_shape.png',
                'subtitle': '练习阶段（不计分）—— 留意【物体形状】是否变化'
            },
            'Color': {
                'image': '04_focus_color.png',
                'subtitle': '练习阶段（不计分）—— 留意【物体颜色】是否变化'
            },
            'Binding': {
                'image': '05_focus_binding.png',
                'subtitle': '练习阶段（不计分）—— 留意【哪个形状配哪个颜色】是否变化'
            }
        }
        cfg = condition_config[condition]

        # 先显示条件说明
        self._show_instruction_page(cfg['image'], subtitle=cfg['subtitle'])

        # 再显示 Practice 提示
        self._show_instruction_page("06_practice.png", subtitle="先来几道练习，熟悉一下")

    def show_formal_instruction(self, condition):
        """显示正式实验指导语"""
        self._show_instruction_page(
            "07_formal.png",
            subtitle="正式测试开始 —— 相同点左边  不同点右边"
        )

    def show_rest(self):
        """显示休息界面"""
        self._show_instruction_page("08_rest.png", subtitle="休息一下，准备好后继续")

    def handle_escape_exit(self):
        """处理ESC键退出"""
        print("用户按ESC键退出实验")

        # 保存部分数据
        if hasattr(self, 'data_manager') and self.data_manager.trial_data:
            import datetime

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"VSTMB_{self.participant_info['subject_id']}_{timestamp}_PARTIAL"

            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)

            csv_file = data_dir / f"{filename}.csv"
            self.data_manager.save_to_csv(str(csv_file))

            json_file = data_dir / f"{filename}_summary.json"
            self.data_manager.save_summary_to_json(str(json_file), self.participant_info)

            print(f"部分数据已保存到: {csv_file}")

        self.instruction_text.text = "实验已中断，数据已保存"
        self.instruction_text.draw()
        self.win.flip()
        core.wait(2.0)
        core.quit()

    def show_completion(self):
        """显示完成界面"""
        self._show_instruction_page("09_complete.png", subtitle="测试完成，感谢参与！")
    
    def run_block(self, condition, is_practice=False):
        """运行一个实验区块"""
        # 设置当前条件的图片库
        self.stimulus_manager.set_condition(condition)
        
        if is_practice:
            # 练习阶段
            self.run_practice_block(condition)
        else:
            # 正式实验阶段
            self.show_formal_instruction(condition)
            num_trials = self.config['formal_trials']
            
            # Generate trials - 正式试次50%相同50%不同，随机打乱
            trials = self.generate_trials(condition, num_trials)
            
            # Run trials
            for trial_idx, trial_info in enumerate(trials):
                self.run_trial(trial_info, trial_idx, condition, is_practice=False)
    
    def run_practice_block(self, condition):
        """运行练习区块 - 按手册要求的特定流程
        
        练习阶段共4个试次：
        - 试次1: 相同试次
        - 试次2: 不同试次
        - 试次3-4: 随机
        
        正确率不足50%时显示屏幕3.1，重新从试次1开始
        """
        # 显示练习开始指导语
        self.show_practice_instruction(condition)
        
        while True:  # 循环直到正确率达标
            num_trials = self.config['practice_trials']  # 4个练习试次
            correct_count = 0
            
            # 生成练习试次 - 按手册要求的特定顺序
            trials = []
            
            # 试次1: 相同试次
            trial1 = self.stimulus_manager.generate_trial_stimuli(condition, 'Same')
            trial1['trial_type'] = 'Same'
            trials.append(trial1)
            
            # 试次2: 不同试次
            trial2 = self.stimulus_manager.generate_trial_stimuli(condition, 'Different')
            trial2['trial_type'] = 'Different'
            trials.append(trial2)
            
            # 试次3-4: 随机
            for _ in range(num_trials - 2):
                trial_type = random.choice(['Same', 'Different'])
                trial = self.stimulus_manager.generate_trial_stimuli(condition, trial_type)
                trial['trial_type'] = trial_type
                trials.append(trial)
            
            # 运行练习试次
            for trial_idx, trial_info in enumerate(trials):
                # 显示试次开始前的提示（根据手册要求）
                self.show_practice_trial_prompt(trial_idx, condition)
                
                # 运行试次
                accuracy = self.run_trial(trial_info, trial_idx, condition, is_practice=True)
                if accuracy:
                    correct_count += 1
            
            # 检查练习正确率
            accuracy_rate = correct_count / num_trials
            if accuracy_rate < 0.5:  # 正确率低于50%
                # 显示屏幕3.1：重新练习提示
                self.show_retry_practice_instruction(condition)
                # 继续循环，重新从试次1开始
            else:
                # 正确率达标，显示练习结束过渡页面并退出循环
                self.show_practice_completion(condition)
                break
    
    def show_practice_trial_prompt(self, trial_idx, condition):
        """练习试次提示 — 直接跳过，不再显示单独页面"""
        # 欢迎页已经讲清楚了操作方式，不需要每个试次前再提示
        return
    
    def show_practice_completion(self, condition):
        """显示练习结束过渡页面"""
        self._show_instruction_page(
            "06_practice.png",
            subtitle="练习结束，做得不错！接下来是正式测试"
        )
    
    def show_retry_practice_instruction(self, condition):
        """显示重新练习提示"""
        condition_names = {
            'Object': '物体形状',
            'Color': '物体颜色',
            'Binding': '物体与颜色的组合'
        }
        self._show_instruction_page(
            None,
            subtitle=f"再练习一次，仔细看【{condition_names[condition]}】有没有变化"
        )
    
    def generate_trials(self, condition, num_trials):
        """生成试次列表"""
        trials = []
        
        # Generate equal numbers of Same and Different trials
        num_same = num_trials // 2
        num_different = num_trials - num_same
        
        trial_types = ['Same'] * num_same + ['Different'] * num_different
        random.shuffle(trial_types)
        
        for trial_type in trial_types:
            trial_info = self.stimulus_manager.generate_trial_stimuli(condition, trial_type)
            trial_info['trial_type'] = trial_type
            trials.append(trial_info)
        
        return trials
    
    def run_trial(self, trial_info, trial_idx, condition, is_practice):
        """运行单个试次
        
        Returns:
            int: 正确率 (1=正确, 0=错误)
        """
        # 导入辅助函数
        from main import TrialData, index_to_shape_id, index_to_color_id, key_to_response
        
        # 提取刺激信息
        study_positions = trial_info['study_positions']
        study_object_ids = trial_info['study_object_ids']
        study_color_ids = trial_info['study_color_ids']
        probe_positions = trial_info['probe_positions']
        probe_object_ids = trial_info['probe_object_ids']
        probe_color_ids = trial_info['probe_color_ids']
        
        # Create trial data object - 按手册要求的字段格式
        trial_data = TrialData(
            subject_id=self.participant_info['subject_id'],
            trial_index=trial_idx,
            is_practice=is_practice,
            condition=condition,
            trial_type=trial_info['trial_type'],
            # 学习阶段刺激信息
            study_pos_1=study_positions[0] if len(study_positions) > 0 else 0,
            study_obj_id_1=index_to_shape_id(study_object_ids[0]) if len(study_object_ids) > 0 else '',
            study_color_id_1=index_to_color_id(study_color_ids[0]) if len(study_color_ids) > 0 and study_color_ids[0] >= 0 else '',
            study_pos_2=study_positions[1] if len(study_positions) > 1 else 0,
            study_obj_id_2=index_to_shape_id(study_object_ids[1]) if len(study_object_ids) > 1 else '',
            study_color_id_2=index_to_color_id(study_color_ids[1]) if len(study_color_ids) > 1 and study_color_ids[1] >= 0 else '',
            # 探测阶段刺激信息
            probe_pos_1=probe_positions[0] if len(probe_positions) > 0 else 0,
            probe_obj_id_1=index_to_shape_id(probe_object_ids[0]) if len(probe_object_ids) > 0 else '',
            probe_color_id_1=index_to_color_id(probe_color_ids[0]) if len(probe_color_ids) > 0 and probe_color_ids[0] >= 0 else '',
            probe_pos_2=probe_positions[1] if len(probe_positions) > 1 else 0,
            probe_obj_id_2=index_to_shape_id(probe_object_ids[1]) if len(probe_object_ids) > 1 else '',
            probe_color_id_2=index_to_color_id(probe_color_ids[1]) if len(probe_color_ids) > 1 and probe_color_ids[1] >= 0 else '',
            # 位置约束
            pos_set_diff_ok=trial_info['position_constraint_ok']
        )
        
        # 清除之前的按键缓冲
        event.clearEvents()
        
        # 1. Fixation (500ms) - 锁定按键
        self.stimulus_manager.present_fixation(0.5)
        event.clearEvents()  # 清除注视点期间的按键
        
        # 2. Study phase (2000ms) - 锁定按键
        self.stimulus_manager.present_study_stimuli(
            trial_info['study_object_ids'],
            trial_info['study_color_ids'],
            trial_info['study_positions'],
            2.0
        )
        event.clearEvents()  # 清除学习阶段的按键
        
        # 3. Retention phase (900ms) - 锁定按键
        self.stimulus_manager.present_blank_screen(0.9)
        event.clearEvents()  # 清除保持阶段的按键
        
        # 4. Probe phase - 刺激持续显示直到被试按键
        # 先绘制探测刺激和按键提示
        self.draw_probe_with_reminder(
            trial_info['probe_object_ids'],
            trial_info['probe_color_ids'],
            trial_info['probe_positions'],
            is_practice=is_practice  # 传递练习阶段标志
        )
        
        # Record probe onset time
        trial_data.probe_onset_ts = core.getTime()
        
        # 5. Wait for response - 探测刺激持续显示直到按键
        response_data = self.wait_for_response_with_probe(
            trial_info['probe_object_ids'],
            trial_info['probe_color_ids'],
            trial_info['probe_positions'],
            is_practice=is_practice  # 传递练习阶段标志
        )
        
        # Update trial data with response - 将按键转换为'左'/'右'
        trial_data.response_key = key_to_response(response_data['key'], self.key_mapping)
        trial_data.reaction_time = response_data['rt']
        trial_data.response_ts = response_data['timestamp']
        trial_data.timeout = response_data['timeout']
        
        # Calculate accuracy and SDT classification
        self.calculate_trial_metrics(trial_data, response_data['judgment'])
        
        # Show feedback if practice
        if is_practice:
            self.show_feedback(trial_data.accuracy, trial_idx, condition, trial_data.trial_type)
        
        # 6. Transition phase
        self.stimulus_manager.present_blank_screen(1.0)
        
        # Save trial data
        self.data_manager.add_trial_data(trial_data)
        
        # 返回正确率
        return trial_data.accuracy
    
    def show_key_reminder(self):
        """绘制左右触摸按钮（相同/不同），始终显示在屏幕下方"""
        self.left_btn_bg.draw()
        self.left_btn_label.draw()
        self.right_btn_bg.draw()
        self.right_btn_label.draw()
        # 不在这里 flip

    def _point_in_circle(self, point, center, radius):
        """检查点是否在圆内"""
        dx = point[0] - center[0]
        dy = point[1] - center[1]
        return (dx * dx + dy * dy) <= radius * radius
    
    def draw_probe_with_reminder(self, object_ids, color_ids, positions, is_practice=False):
        """绘制探测刺激和圆圈（不等待）
        
        Args:
            object_ids: 物体ID列表
            color_ids: 颜色ID列表
            positions: 位置列表
            is_practice: 是否为练习阶段
        """
        print(f"[探测阶段] 位置: {positions}, 网格坐标: {[self.stimulus_manager.grid_positions_pix.get(p) for p in positions]}")
        print(f"[探测阶段] 图片尺寸: {self.stimulus_manager.pixel_size}")
        
        # 设置并绘制刺激
        for i, (shape_idx, color_idx, pos_id) in enumerate(zip(object_ids, color_ids, positions)):
            # 获取像素坐标（使用网格位置编号）
            pos = self.stimulus_manager.grid_positions_pix.get(pos_id, (0, 0))
            
            if i < len(self.stimulus_manager.visual_objects):
                obj = self.stimulus_manager.visual_objects[i]
                obj.pos = pos
                
                # 获取图片路径
                img_path = self.stimulus_manager.get_image_path(
                    shape_idx, 
                    color_idx if color_idx >= 0 else None
                )
                if img_path and Path(img_path).exists():
                    obj.image = str(img_path)
                
                # 确保每次都设置尺寸（在设置image之后）
                obj.size = self.stimulus_manager.pixel_size
                obj.draw()
        
        # 绘制圆圈（纯视觉元素）
        self.show_key_reminder()
        
        # 如果是练习阶段，在屏幕最下方显示"请按键反应"
        if is_practice:
            self.response_prompt.draw()
        
        self.win.flip()
    
    def wait_for_response_with_probe(self, object_ids, color_ids, positions, is_practice=False, timeout=5.0):
        """等待触摸响应，同时保持探测刺激显示（平板触摸版）"""
        start_time = core.getTime()
        timeout_shown = False
        prev_pressed = False

        while True:
            # ESC 退出（保留键盘 ESC）
            keys = event.getKeys(keyList=['escape'])
            if keys:
                self.handle_escape_exit()

            # 也支持键盘 Q/P 作为备用
            kb_keys = event.getKeys(keyList=['q', 'p'], timeStamped=True)
            if kb_keys:
                key, timestamp = kb_keys[0]
                judgment = 'Same' if key.lower() == self.key_mapping['same'].lower() else 'Different'
                rt = (timestamp - start_time) * 1000
                return {'key': key.lower(), 'judgment': judgment, 'rt': rt,
                        'timestamp': timestamp, 'timeout': False}

            # 触摸/鼠标检测
            is_pressed = self.mouse.getPressed()[0] == 1
            mouse_pos = self.mouse.getPos()

            if prev_pressed and not is_pressed:
                # 释放时检测在哪个按钮上
                if self._point_in_circle(mouse_pos, self.left_btn_pos, self.btn_radius):
                    # 点了"相同"
                    self.left_btn_bg.fillColor = self.left_btn_press_color
                    self.show_key_reminder()
                    self.win.flip()
                    core.wait(0.1)
                    self.left_btn_bg.fillColor = self.left_btn_normal_color
                    rt = (core.getTime() - start_time) * 1000
                    return {'key': 'same_btn', 'judgment': 'Same', 'rt': rt,
                            'timestamp': core.getTime(), 'timeout': False}

                elif self._point_in_circle(mouse_pos, self.right_btn_pos, self.btn_radius):
                    # 点了"不同"
                    self.right_btn_bg.fillColor = self.right_btn_press_color
                    self.show_key_reminder()
                    self.win.flip()
                    core.wait(0.1)
                    self.right_btn_bg.fillColor = self.right_btn_normal_color
                    rt = (core.getTime() - start_time) * 1000
                    return {'key': 'diff_btn', 'judgment': 'Different', 'rt': rt,
                            'timestamp': core.getTime(), 'timeout': False}

            prev_pressed = is_pressed

            # 超时提示
            elapsed = core.getTime() - start_time
            if elapsed > timeout and not timeout_shown:
                self.redraw_probe_with_timeout_prompt(object_ids, color_ids, positions, is_practice)
                timeout_shown = True

            core.wait(0.016)
    
    def redraw_probe_with_timeout_prompt(self, object_ids, color_ids, positions, is_practice=False):
        """重新绘制探测刺激并添加超时提示
        
        Args:
            object_ids: 物体ID列表
            color_ids: 颜色ID列表
            positions: 位置列表
            is_practice: 是否为练习阶段
        """
        # 重新绘制刺激 - 使用网格位置编号（1-9）
        for i, (shape_idx, color_idx, pos_id) in enumerate(zip(object_ids, color_ids, positions)):
            # 获取像素坐标（使用网格位置编号）
            pos = self.stimulus_manager.grid_positions_pix.get(pos_id, (0, 0))
            
            if i < len(self.stimulus_manager.visual_objects):
                obj = self.stimulus_manager.visual_objects[i]
                obj.pos = pos
                
                # 获取图片路径
                img_path = self.stimulus_manager.get_image_path(
                    shape_idx, 
                    color_idx if color_idx >= 0 else None
                )
                if img_path and Path(img_path).exists():
                    obj.image = str(img_path)
                
                # 确保每次都设置尺寸（在设置image之后）
                obj.size = self.stimulus_manager.pixel_size
                obj.draw()
        
        # 绘制圆圈（纯视觉元素）
        self.show_key_reminder()
        
        # 如果是练习阶段，显示"请按键反应"
        if is_practice:
            self.response_prompt.draw()
        
        # 添加超时提示
        prompt_text = visual.TextStim(
            self.win,
            text='请做出选择！',
            color=[1, 0, 0],
            height=int(50 * self._s),
            pos=(0, int(350 * self._s)),
            font='PingFang SC',
            units='pix'
        )
        prompt_text.draw()
        self.win.flip()
    
    def wait_for_response(self, timeout=5.0):
        """等待触摸响应（平板触摸版）"""
        start_time = core.getTime()
        timeout_shown = False
        prev_pressed = False

        while True:
            keys = event.getKeys(keyList=['escape'])
            if keys:
                self.handle_escape_exit()

            # 键盘备用
            kb_keys = event.getKeys(keyList=['q', 'p'], timeStamped=True)
            if kb_keys:
                key, timestamp = kb_keys[0]
                judgment = 'Same' if key.lower() == self.key_mapping['same'].lower() else 'Different'
                rt = (timestamp - start_time) * 1000
                return {'key': key.lower(), 'judgment': judgment, 'rt': rt,
                        'timestamp': timestamp, 'timeout': False}

            # 触摸检测
            is_pressed = self.mouse.getPressed()[0] == 1
            mouse_pos = self.mouse.getPos()

            if prev_pressed and not is_pressed:
                if self._point_in_circle(mouse_pos, self.left_btn_pos, self.btn_radius):
                    self.left_btn_bg.fillColor = self.left_btn_press_color
                    self.show_key_reminder()
                    self.win.flip()
                    core.wait(0.1)
                    self.left_btn_bg.fillColor = self.left_btn_normal_color
                    rt = (core.getTime() - start_time) * 1000
                    return {'key': 'same_btn', 'judgment': 'Same', 'rt': rt,
                            'timestamp': core.getTime(), 'timeout': False}
                elif self._point_in_circle(mouse_pos, self.right_btn_pos, self.btn_radius):
                    self.right_btn_bg.fillColor = self.right_btn_press_color
                    self.show_key_reminder()
                    self.win.flip()
                    core.wait(0.1)
                    self.right_btn_bg.fillColor = self.right_btn_normal_color
                    rt = (core.getTime() - start_time) * 1000
                    return {'key': 'diff_btn', 'judgment': 'Different', 'rt': rt,
                            'timestamp': core.getTime(), 'timeout': False}

            prev_pressed = is_pressed

            elapsed = core.getTime() - start_time
            if elapsed > timeout:
                if not timeout_shown:
                    # Show timeout prompt
                    self.show_timeout_prompt()
                    timeout_shown = True
                
                # Continue waiting but mark as timeout
                if elapsed > timeout + 2.0:  # Give extra 2 seconds after prompt
                    return {
                        'key': '',
                        'judgment': '',
                        'rt': elapsed * 1000,
                        'timestamp': core.getTime(),
                        'timeout': True
                    }
    
    def show_timeout_prompt(self):
        """显示超时提示"""
        prompt_text = visual.TextStim(
            self.win,
            text='请做出选择！',
            color=[1, 0, 0],
            height=int(50 * self._s),
            pos=(0, int(350 * self._s)),
            font='PingFang SC',
            units='pix'
        )
        
        # Redraw current stimuli, key reminder and add prompt
        for obj in self.stimulus_manager.visual_objects:
            if hasattr(obj, 'image') and obj.image is not None:
                obj.draw()
        
        self.show_key_reminder()
        prompt_text.draw()
        self.win.flip()
    
    def calculate_trial_metrics(self, trial_data, response_judgment=''):
        """计算试次指标
        
        Args:
            trial_data: 试次数据对象
            response_judgment: 被试的判断 ('Same' or 'Different')
        """
        # Determine accuracy
        correct_judgment = trial_data.trial_type
        trial_data.accuracy = 1 if response_judgment == correct_judgment else 0
        
        # Signal detection theory classification
        if trial_data.trial_type == 'Different' and response_judgment == 'Different':
            trial_data.sdt_classification = 'Hit'
        elif trial_data.trial_type == 'Different' and response_judgment == 'Same':
            trial_data.sdt_classification = 'Miss'
        elif trial_data.trial_type == 'Same' and response_judgment == 'Different':
            trial_data.sdt_classification = 'FA'  # False Alarm
        elif trial_data.trial_type == 'Same' and response_judgment == 'Same':
            trial_data.sdt_classification = 'CR'  # Correct Rejection
        else:
            trial_data.sdt_classification = 'Unknown'
    
    def show_feedback(self, accuracy, trial_idx, condition, trial_type):
        """显示练习反馈 - 正误反馈和指导语同时显示"""
        # 基本反馈
        feedback_text = "正确！" if accuracy == 1 else "错误！"
        feedback_color = [0, 1, 0] if accuracy == 1 else [1, 0, 0]
        
        # 根据试次和条件添加详细指导
        detailed_feedback = self.get_detailed_feedback(trial_idx, condition, trial_type, accuracy)
        
        # 创建正误反馈文本 - 中央靠上（像素坐标）
        feedback_stim = visual.TextStim(
            self.win,
            text=feedback_text,
            color=feedback_color,
            height=int(55 * self._s),
            pos=(0, int(200 * self._s)),
            font='PingFang SC',
            units='pix'
        )

        feedback_stim.draw()

        if detailed_feedback:
            detailed_stim = visual.TextStim(
                self.win,
                text=detailed_feedback,
                color=self.config['text_color'],
                height=int(32 * self._s),
                wrapWidth=int(self.win.size[0] * 0.7),
                pos=(0, int(-100 * self._s)),
                alignText='center',
                font='PingFang SC',
                units='pix'
            )
            detailed_stim.draw()
        
        self.show_key_reminder()  # 显示圆圈
        self.win.flip()
        # 等待触摸或键盘
        event.clearEvents()
        self.mouse.clickReset()
        prev = False
        while True:
            keys = event.getKeys()
            if keys:
                break
            pressed = self.mouse.getPressed()[0] == 1
            if prev and not pressed:
                break
            prev = pressed
            core.wait(0.016)
    
    def get_detailed_feedback(self, trial_idx, condition, trial_type, accuracy):
        """获取详细反馈内容（触摸版）"""
        condition_names = {
            'Object': '物体形状',
            'Color': '物体颜色',
            'Binding': '物体与颜色的组合'
        }
        cn = condition_names.get(condition, '')

        if trial_idx == 0:
            return f"{cn}和之前一样时，点左边【相同】\n\n点击屏幕继续"
        elif trial_idx == 1:
            return f"{cn}和之前不一样时，点右边【不同】\n\n点击屏幕继续"
        elif trial_idx >= 2:
            return "相同点左边，不同点右边\n\n点击屏幕继续"

        return None