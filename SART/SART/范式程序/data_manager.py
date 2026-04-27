"""
SART Data Manager
数据收集、存储与统计分析
"""

import csv
import json
import math
import os
from datetime import datetime
from pathlib import Path

import numpy as np


class DataManager:
    """管理SART实验数据的收集、清洗、统计和导出"""

    # CSV字段顺序（与PDF 4.1节一致）
    RAW_FIELDS = [
        'subject_id', 'block_type', 'trial_index', 'digit', 'trial_type',
        'stim_onset_ts', 'stim_offset_ts',
        'response_made', 'reaction_time_ms',
        'accuracy', 'error_type',
        'probe_onset_ts', 'probe_response_ts', 'probe_rt_ms', 'attention_rating',
    ]

    def __init__(self, subject_id: str, data_dir: str | Path):
        self.subject_id = subject_id
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trial_data: list[dict] = []
        self.probe_data: dict | None = None
        self._timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ------------------------------------------------------------------
    # 数据收集
    # ------------------------------------------------------------------

    def add_trial(self, data: dict):
        """添加一条trial数据"""
        data['subject_id'] = self.subject_id
        # 根据PDF判断error_type
        data['error_type'] = self._classify_error(data)
        self.trial_data.append(data)

    def set_probe(self, probe_onset_ts: float, probe_response_ts: float,
                  attention_rating: int):
        """记录probe数据"""
        self.probe_data = {
            'probe_onset_ts': round(probe_onset_ts, 3),
            'probe_response_ts': round(probe_response_ts, 3),
            'probe_rt_ms': round((probe_response_ts - probe_onset_ts) * 1000, 1),
            'attention_rating': attention_rating,
        }

    @staticmethod
    def _classify_error(data: dict) -> str | None:
        """按PDF 4.1节判断error_type"""
        is_nogo = data['trial_type'] == 'nogo'
        responded = data['response_made']
        if is_nogo:
            return 'commission' if responded else None
        else:
            return 'omission' if not responded else None

    # ------------------------------------------------------------------
    # 导出：原始CSV
    # ------------------------------------------------------------------

    def save_csv(self, tag: str = '') -> Path:
        """保存原始trial级数据为CSV"""
        suffix = f'_{tag}' if tag else ''
        filename = f'SART_{self.subject_id}_{self._timestamp}{suffix}.csv'
        filepath = self.data_dir / filename

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.RAW_FIELDS,
                                    extrasaction='ignore')
            writer.writeheader()
            for row in self.trial_data:
                out = dict(row)
                # 将probe数据合并到最后一个trial行
                if self.probe_data and row is self.trial_data[-1]:
                    out.update(self.probe_data)
                writer.writerow(out)

        return filepath

    # ------------------------------------------------------------------
    # 导出：统计JSON
    # ------------------------------------------------------------------

    def save_summary(self) -> Path:
        """保存统计摘要为JSON"""
        filename = f'SART_{self.subject_id}_{self._timestamp}_summary.json'
        filepath = self.data_dir / filename

        summary = {
            'participant_info': {'subject_id': self.subject_id},
            'behavioral_metrics': self._compute_behavioral(),
            'rt_metrics': self._compute_rt_metrics(),
            'sequential_effects': self._compute_sequential(),
            'composite_metrics': self._compute_composite(),
            'probe': self.probe_data,
            'data_quality': self._compute_quality(),
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        return filepath

    # ------------------------------------------------------------------
    # 统计计算（PDF 4.2节）
    # ------------------------------------------------------------------

    def _formal_trials(self) -> list[dict]:
        """只取正式阶段数据"""
        return [t for t in self.trial_data if t.get('block_type') == 'formal']

    def _compute_behavioral(self) -> dict:
        """PDF 4.2(1) 基础行为指标"""
        trials = self._formal_trials()
        if not trials:
            return {}

        go = [t for t in trials if t['trial_type'] == 'go']
        nogo = [t for t in trials if t['trial_type'] == 'nogo']
        go_correct = sum(1 for t in go if t['accuracy'] == 1)
        nogo_correct = sum(1 for t in nogo if t['accuracy'] == 1)
        commission_n = sum(1 for t in nogo if t['error_type'] == 'commission')
        omission_n = sum(1 for t in go if t['error_type'] == 'omission')

        return {
            'total_trials': len(trials),
            'go_trials_n': len(go),
            'nogo_trials_n': len(nogo),
            'go_accuracy': round(go_correct / len(go), 4) if go else 0,
            'nogo_accuracy': round(nogo_correct / len(nogo), 4) if nogo else 0,
            'overall_accuracy': round(
                (go_correct + nogo_correct) / len(trials), 4),
            'commission_errors_n': commission_n,
            'commission_error_rate': round(
                commission_n / len(nogo), 4) if nogo else 0,
            'omission_errors_n': omission_n,
            'omission_error_rate': round(
                omission_n / len(go), 4) if go else 0,
        }

    def _get_clean_go_rts(self) -> list[float]:
        """获取清洗后的Go正确trial RT列表（PDF 5.1节）"""
        trials = self._formal_trials()
        rts = [t['reaction_time_ms'] for t in trials
               if t['trial_type'] == 'go' and t['accuracy'] == 1
               and t['reaction_time_ms'] is not None]

        if not rts:
            return []

        # 绝对阈值：150-2000ms
        rts = [rt for rt in rts if 150 <= rt <= 2000]

        if len(rts) < 3:
            return rts

        # 相对阈值：±3SD
        mean = np.mean(rts)
        sd = np.std(rts, ddof=1)
        rts = [rt for rt in rts if abs(rt - mean) <= 3 * sd]

        return rts

    def _compute_rt_metrics(self) -> dict:
        """PDF 4.2(2) 反应时指标"""
        rts = self._get_clean_go_rts()
        if not rts:
            return {}

        go_mean = float(np.mean(rts))
        go_sd = float(np.std(rts, ddof=1)) if len(rts) > 1 else 0.0

        # 虚报错误的RT
        trials = self._formal_trials()
        commission_rts = [
            t['reaction_time_ms'] for t in trials
            if t['error_type'] == 'commission'
            and t['reaction_time_ms'] is not None
            and 150 <= t['reaction_time_ms'] <= 2000
        ]

        result = {
            'go_rt_mean': round(go_mean, 2),
            'go_rt_sd': round(go_sd, 2),
            'go_rt_cov': round(go_sd / go_mean, 4) if go_mean > 0 else 0,
        }
        if commission_rts:
            result['commission_rt_mean'] = round(float(np.mean(commission_rts)), 2)
            result['commission_rt_sd'] = round(
                float(np.std(commission_rts, ddof=1)), 2) if len(commission_rts) > 1 else 0.0

        return result

    def _compute_sequential(self) -> dict:
        """PDF 4.2(3) 序列效应指标"""
        trials = self._formal_trials()
        if len(trials) < 5:
            return {}

        result = {}

        # 找出所有nogo trial的位置
        nogo_indices = [i for i, t in enumerate(trials)
                        if t['trial_type'] == 'nogo']

        pre_error_rts = []
        pre_correct_rts = []
        post_error_rts = []
        post_correct_rts = []

        for idx in nogo_indices:
            is_commission = trials[idx]['error_type'] == 'commission'

            # Pre: 该nogo前4个go trial的RT
            pre_rts = []
            count = 0
            for j in range(idx - 1, -1, -1):
                if count >= 4:
                    break
                t = trials[j]
                if (t['trial_type'] == 'go' and t['accuracy'] == 1
                        and t['reaction_time_ms'] is not None):
                    pre_rts.append(t['reaction_time_ms'])
                    count += 1

            if pre_rts:
                mean_pre = float(np.mean(pre_rts))
                if is_commission:
                    pre_error_rts.append(mean_pre)
                else:
                    pre_correct_rts.append(mean_pre)

            # Post: 该nogo后第1个go trial的RT
            for j in range(idx + 1, len(trials)):
                t = trials[j]
                if (t['trial_type'] == 'go' and t['accuracy'] == 1
                        and t['reaction_time_ms'] is not None):
                    if is_commission:
                        post_error_rts.append(t['reaction_time_ms'])
                    else:
                        post_correct_rts.append(t['reaction_time_ms'])
                    break

        if pre_error_rts:
            result['pre_error_rt_mean'] = round(float(np.mean(pre_error_rts)), 2)
        if pre_correct_rts:
            result['pre_correct_rt_mean'] = round(float(np.mean(pre_correct_rts)), 2)
        if pre_error_rts and pre_correct_rts:
            result['pre_error_speeding'] = round(
                float(np.mean(pre_correct_rts)) - float(np.mean(pre_error_rts)), 2)

        if post_error_rts:
            result['post_error_rt'] = round(float(np.mean(post_error_rts)), 2)
        if post_correct_rts:
            result['post_correct_rt'] = round(float(np.mean(post_correct_rts)), 2)

        return result

    def _compute_composite(self) -> dict:
        """PDF 4.2(4) 综合指标"""
        beh = self._compute_behavioral()
        rt = self._compute_rt_metrics()
        if not beh or not rt:
            return {}

        result = {}

        # Skill Index = (No-Go准确率 / Go RT均值) * 1000
        nogo_acc = beh.get('nogo_accuracy', 0)
        go_rt_mean = rt.get('go_rt_mean', 0)
        if go_rt_mean > 0:
            result['skill_index'] = round(nogo_acc / go_rt_mean * 1000, 4)

        # d' 和 criterion c（信号检测论）
        trials = self._formal_trials()
        go = [t for t in trials if t['trial_type'] == 'go']
        nogo = [t for t in trials if t['trial_type'] == 'nogo']

        if go and nogo:
            # SART中：No-Go正确抑制 = Hit, Go正确按键对应False Alarm逻辑反转
            # 按照标准SDT: Hit = 正确检测到target(3)并抑制
            #              FA = 错误地对go刺激未按键（omission）
            # 但SART文献通常用：
            #   Hit rate = Go正确率 (correctly responding to go)
            #   FA rate = Commission error rate (incorrectly responding to nogo)
            hit_rate = beh.get('go_accuracy', 0)
            fa_rate = beh.get('commission_error_rate', 0)

            # 校正极端值
            n_go = len(go)
            n_nogo = len(nogo)
            hit_rate = max(0.5 / n_go, min(1 - 0.5 / n_go, hit_rate))
            fa_rate = max(0.5 / n_nogo, min(1 - 0.5 / n_nogo, fa_rate))

            from scipy.stats import norm as scipy_norm
            try:
                z_hit = scipy_norm.ppf(hit_rate)
                z_fa = scipy_norm.ppf(fa_rate)
                result['d_prime'] = round(z_hit - z_fa, 4)
                result['criterion_c'] = round(-0.5 * (z_hit + z_fa), 4)
            except Exception:
                # scipy不可用时的备选方案
                pass

        return result

    def _compute_quality(self) -> dict:
        """数据质量信息"""
        trials = self._formal_trials()
        if not trials:
            return {}

        all_rts = [t['reaction_time_ms'] for t in trials
                   if t['reaction_time_ms'] is not None]
        excluded_abs = sum(1 for rt in all_rts if rt < 150 or rt > 2000)

        clean_rts = [rt for rt in all_rts if 150 <= rt <= 2000]
        excluded_rel = 0
        if len(clean_rts) >= 3:
            mean = np.mean(clean_rts)
            sd = np.std(clean_rts, ddof=1)
            excluded_rel = sum(1 for rt in clean_rts if abs(rt - mean) > 3 * sd)

        return {
            'total_formal_trials': len(trials),
            'trials_with_response': sum(1 for t in trials if t['response_made']),
            'rt_excluded_absolute': excluded_abs,
            'rt_excluded_relative': excluded_rel,
        }
