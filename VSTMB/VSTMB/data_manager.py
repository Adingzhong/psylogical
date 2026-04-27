#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data Manager for VSTMB Experiment
处理数据存储、分析和导出
"""

import csv
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import asdict
import datetime

class DataManager:
    """管理实验数据"""
    
    def __init__(self):
        self.trial_data_list = []
        self.performance_metrics = {}
    
    def add_trial_data(self, trial_data):
        """添加试次数据"""
        self.trial_data_list.append(trial_data)
    
    def save_data(self, participant_info, data_dir):
        """保存实验数据"""
        # Create filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        subject_id = participant_info['subject_id']
        filename = f"VSTMB_{subject_id}_{timestamp}"
        
        # Save trial data as CSV
        csv_file = data_dir / f"{filename}.csv"
        self.save_trial_data_csv(csv_file)
        
        # Save participant info and summary as JSON
        json_file = data_dir / f"{filename}_summary.json"
        self.save_summary_json(json_file, participant_info)
        
        print(f"Data saved to {csv_file} and {json_file}")
    
    def save_trial_data_csv(self, filepath):
        """保存试次数据为CSV格式"""
        if not self.trial_data_list:
            return
        
        # Convert trial data to dictionaries
        data_dicts = [asdict(trial) for trial in self.trial_data_list]
        
        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = data_dicts[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for row in data_dicts:
                writer.writerow(row)
    
    def save_summary_json(self, filepath, participant_info):
        """保存摘要信息为JSON格式"""
        # Calculate performance metrics
        metrics = self.calculate_performance_metrics()
        
        summary = {
            'participant_info': participant_info,
            'experiment_summary': {
                'total_trials': len(self.trial_data_list),
                'formal_trials': len([t for t in self.trial_data_list if not t.is_practice]),
                'practice_trials': len([t for t in self.trial_data_list if t.is_practice]),
                'conditions': list(set([t.condition for t in self.trial_data_list]))
            },
            'performance_metrics': metrics,
            'data_quality': self.assess_data_quality()
        }
        
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(summary, jsonfile, indent=2, ensure_ascii=False)
    
    def calculate_performance_metrics(self):
        """计算性能指标"""
        metrics = {}
        
        # Get formal trials only
        formal_trials = [t for t in self.trial_data_list if not t.is_practice]
        
        # Calculate metrics for each condition
        conditions = set([t.condition for t in formal_trials])
        
        for condition in conditions:
            condition_trials = [t for t in formal_trials if t.condition == condition]
            
            if not condition_trials:
                continue
            
            # Basic metrics
            total_trials = len(condition_trials)
            correct_trials = sum([t.accuracy for t in condition_trials])
            accuracy_rate = correct_trials / total_trials if total_trials > 0 else 0
            
            # Signal detection theory metrics
            hits = len([t for t in condition_trials if t.sdt_classification == 'Hit'])
            misses = len([t for t in condition_trials if t.sdt_classification == 'Miss'])
            false_alarms = len([t for t in condition_trials if t.sdt_classification == 'FA'])
            correct_rejections = len([t for t in condition_trials if t.sdt_classification == 'CR'])
            
            # Calculate hit rate and false alarm rate
            hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0
            fa_rate = false_alarms / (false_alarms + correct_rejections) if (false_alarms + correct_rejections) > 0 else 0
            
            # Calculate A' (sensitivity)
            a_prime = self.calculate_a_prime(hit_rate, fa_rate)
            
            # Calculate β (response bias)
            beta = self.calculate_beta(hit_rate, fa_rate)
            
            # Reaction time metrics (exclude timeouts)
            valid_rts = [t.reaction_time for t in condition_trials if not t.timeout and t.reaction_time > 0]
            
            rt_metrics = {}
            if valid_rts:
                rt_metrics = {
                    'mean_rt': np.mean(valid_rts),
                    'median_rt': np.median(valid_rts),
                    'rt_std': np.std(valid_rts),
                    'fast_responses': len([rt for rt in valid_rts if rt < 150]),  # < 150ms
                    'slow_responses': len([rt for rt in valid_rts if rt > (np.mean(valid_rts) + 3 * np.std(valid_rts))])
                }
            
            metrics[condition] = {
                'total_trials': total_trials,
                'correct_trials': correct_trials,
                'accuracy_rate': accuracy_rate,
                'hits': hits,
                'misses': misses,
                'false_alarms': false_alarms,
                'correct_rejections': correct_rejections,
                'hit_rate': hit_rate,
                'false_alarm_rate': fa_rate,
                'a_prime': a_prime,
                'beta': beta,
                **rt_metrics
            }
        
        return metrics
    
    def calculate_a_prime(self, hit_rate, fa_rate):
        """计算A'敏感度指标"""
        # Avoid extreme values
        h = max(0.01, min(0.99, hit_rate))
        g = max(0.01, min(0.99, fa_rate))
        
        if g <= h:
            a_prime = 0.5 + (h - g) * (1 + h - g) / (4 * h * (1 - g))
        else:
            a_prime = 0.5 - (g - h) * (1 + g - h) / (4 * g * (1 - h))
        
        return a_prime
    
    def calculate_beta(self, hit_rate, fa_rate):
        """计算β反应偏好指标"""
        # Avoid extreme values
        h = max(0.01, min(0.99, hit_rate))
        g = max(0.01, min(0.99, fa_rate))
        
        try:
            # Convert to z-scores
            z_h = self.inverse_normal_cdf(h)
            z_g = self.inverse_normal_cdf(g)
            
            # Calculate ln(β)
            ln_beta = (z_g**2 - z_h**2) / 2
            
            # Convert to β
            beta = np.exp(ln_beta)
            
            return beta
        except:
            return 1.0  # Default neutral bias
    
    def inverse_normal_cdf(self, p):
        """计算标准正态分布的逆累积分布函数（近似）"""
        # Simple approximation for inverse normal CDF
        # This is a simplified version - for production use, consider scipy.stats.norm.ppf
        if p <= 0.5:
            sign = -1
            p = 1 - p
        else:
            sign = 1
        
        # Approximation constants
        a0 = 2.515517
        a1 = 0.802853
        a2 = 0.010328
        b1 = 1.432788
        b2 = 0.189269
        b3 = 0.001308
        
        t = np.sqrt(-2 * np.log(p))
        z = t - (a0 + a1*t + a2*t**2) / (1 + b1*t + b2*t**2 + b3*t**3)
        
        return sign * z
    
    def assess_data_quality(self):
        """评估数据质量"""
        if not self.trial_data_list:
            return {}
        
        formal_trials = [t for t in self.trial_data_list if not t.is_practice]
        
        quality_metrics = {
            'total_trials': len(self.trial_data_list),
            'formal_trials': len(formal_trials),
            'timeout_rate': len([t for t in formal_trials if t.timeout]) / len(formal_trials) if formal_trials else 0,
            'fast_response_rate': len([t for t in formal_trials if t.reaction_time < 150 and not t.timeout]) / len(formal_trials) if formal_trials else 0,
            'position_constraint_violations': len([t for t in formal_trials if not t.position_constraint_ok]),
            'missing_responses': len([t for t in formal_trials if t.response_key == '']),
        }
        
        # Check for extreme response bias
        all_responses = [t.response_judgment for t in formal_trials if t.response_judgment != '']
        if all_responses:
            same_responses = len([r for r in all_responses if r == 'Same'])
            different_responses = len([r for r in all_responses if r == 'Different'])
            total_responses = len(all_responses)
            
            quality_metrics['same_response_rate'] = same_responses / total_responses
            quality_metrics['different_response_rate'] = different_responses / total_responses
            
            # Flag extreme bias (>90% one response type)
            quality_metrics['extreme_response_bias'] = (same_responses / total_responses > 0.9) or (different_responses / total_responses > 0.9)
        
        return quality_metrics
    
    @property
    def trial_data(self):
        """获取试次数据列表"""
        return self.trial_data_list
    
    def save_to_csv(self, filepath):
        """保存试次数据为CSV格式"""
        self.save_trial_data_csv(filepath)
    
    def save_summary_to_json(self, filepath, participant_info):
        """保存摘要信息为JSON格式"""
        self.save_summary_json(filepath, participant_info)
    
    def export_for_analysis(self, filepath, format='csv'):
        """导出数据用于统计分析"""
        if format == 'csv':
            self.save_trial_data_csv(filepath)
        elif format == 'json':
            # Export in a format suitable for statistical software
            analysis_data = []
            
            for trial in self.trial_data_list:
                if not trial.is_practice:  # Only formal trials
                    analysis_data.append({
                        'subject_id': trial.subject_id,
                        'condition': trial.condition,
                        'trial_type': trial.trial_type,
                        'accuracy': trial.accuracy,
                        'reaction_time': trial.reaction_time,
                        'sdt_classification': trial.sdt_classification,
                        'timeout': trial.timeout
                    })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False)