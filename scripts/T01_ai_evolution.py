#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - AI进化模块
功能：
1. 分析历史交易数据，识别成功/失败特征
2. 使用机器学习优化评分权重
3. 自动生成新的权重因子
4. 定期反思和改进策略
"""

import json
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
TRADES_FILE = os.path.join(DATA_BASE_DIR, "trades.json")
STATS_FILE = os.path.join(DATA_BASE_DIR, "stats.json")
WEIGHTS_FILE = os.path.join(DATA_BASE_DIR, "weights.json")
EVOLUTION_LOG = os.path.join(DATA_BASE_DIR, "evolution_log.json")
FEATURES_FILE = os.path.join(DATA_BASE_DIR, "feature_importance.json")

class AIEvolution:
    """AI进化引擎"""
    
    def __init__(self):
        self._ensure_files()
        self.current_weights = self._load_weights()
    
    def _ensure_files(self):
        """确保必要文件存在"""
        if not os.path.exists(WEIGHTS_FILE):
            # 初始权重配置
            initial_weights = {
                'version': 1,
                'created_at': datetime.now().isoformat(),
                'weights': {
                    'first_limit_time': 0.15,      # 首次涨停时间
                    'seal_ratio': 0.12,            # 封成比
                    'seal_market_cap': 0.10,       # 封单金额/流通市值
                    'dragon_tiger': 0.10,          # 龙虎榜
                    'main_fund_ratio': 0.12,       # 主力资金净占比
                    'amount': 0.08,                # 成交金额
                    'turnover_rate': 0.10,         # 换手率
                    'volume_ratio': 0.13,          # 量比
                    'hot_sector': 0.10             # 热点板块
                },
                'performance': {
                    'win_rate': 0,
                    'total_trades': 0,
                    'avg_profit': 0
                },
                'evolution_history': []
            }
            with open(WEIGHTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(initial_weights, f, ensure_ascii=False, indent=2)
        
        if not os.path.exists(EVOLUTION_LOG):
            with open(EVOLUTION_LOG, 'w', encoding='utf-8') as f:
                json.dump({'logs': []}, f, ensure_ascii=False, indent=2)
        
        if not os.path.exists(FEATURES_FILE):
            with open(FEATURES_FILE, 'w', encoding='utf-8') as f:
                json.dump({'features': []}, f, ensure_ascii=False, indent=2)
    
    def _load_trades(self) -> List[Dict]:
        """加载交易记录"""
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('trades', [])
        return []
    
    def _load_weights(self) -> Dict:
        """加载当前权重"""
        with open(WEIGHTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_weights(self, weights_data: Dict):
        """保存权重"""
        with open(WEIGHTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(weights_data, f, ensure_ascii=False, indent=2)
    
    def _log_evolution(self, log_entry: Dict):
        """记录进化日志"""
        with open(EVOLUTION_LOG, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        log_data['logs'].append(log_entry)
        
        with open(EVOLUTION_LOG, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    def analyze_feature_importance(self) -> Dict:
        """
        分析各特征对盈亏的重要性
        
        使用简单的统计分析方法：
        - 对比盈利组和亏损组的特征平均值
        - 计算特征差异度
        """
        trades = self._load_trades()
        
        if len(trades) < 10:
            print("  交易数据不足，需要至少10笔交易才能分析")
            return {}
        
        # 分离盈利和亏损交易
        win_trades = [t for t in trades if t['is_win']]
        lose_trades = [t for t in trades if not t['is_win']]
        
        print(f"\n  分析数据:")
        print(f"    总交易数: {len(trades)}")
        print(f"    盈利交易: {len(win_trades)}")
        print(f"    亏损交易: {len(lose_trades)}")
        
        if len(win_trades) == 0 or len(lose_trades) == 0:
            print("  盈利或亏损数据不完整，无法分析")
            return {}
        
        # ★自动识别所有指标（从第一笔有metrics的交易中提取）
        features = [('t_score', '总评分', None)]
        
        # 自动收集所有指标字段
        all_metrics_keys = set()
        for t in trades:
            if t.get('metrics'):
                all_metrics_keys.update(t['metrics'].keys())
        
        # 过滤掉非数值字段和列表字段
        skip_keys = {'first_ceiling_time', 'hot_sector_name', 'plate_reason', 'plate_reason_type', 
                     'plate_reason_keywords', 'news_list', 'famous_investors', 'investor_analysis',
                     'investor_recommendation', 'news_sentiment', 'stock_name'}
        
        for key in sorted(all_metrics_keys):
            if key not in skip_keys:
                # 自动生成中文名
                name = key.replace('_', ' ').replace('score', '评分').replace('num', '数').title()
                features.append((key, name, 'metrics'))
        
        feature_importance = {}
        
        for feature_key, feature_name, sub_key in features:
            # 提取特征值
            if sub_key == 'metrics':
                win_vals = [t.get('metrics', {}).get(feature_key, 0) for t in win_trades if t.get('metrics')]
                lose_vals = [t.get('metrics', {}).get(feature_key, 0) for t in lose_trades if t.get('metrics')]
            elif sub_key:
                win_vals = [t.get(sub_key, {}).get(feature_key, 0) for t in win_trades]
                lose_vals = [t.get(sub_key, {}).get(feature_key, 0) for t in lose_trades]
            else:
                win_vals = [t.get(feature_key, 0) for t in win_trades]
                lose_vals = [t.get(feature_key, 0) for t in lose_trades]
            
            if not win_vals or not lose_vals:
                continue
            
            win_avg = np.mean(win_vals)
            lose_avg = np.mean(lose_vals)
            
            # 计算差异度
            diff = win_avg - lose_avg
            max_avg = max(abs(win_avg), abs(lose_avg), 0.01)
            importance = abs(diff) / max_avg
            
            feature_importance[feature_key] = {
                'name': feature_name,
                'win_avg': round(win_avg, 2),
                'lose_avg': round(lose_avg, 2),
                'diff': round(diff, 2),
                'importance': round(importance, 4),
                'direction': 'positive' if diff > 0 else 'negative'
            }
            
            # 只打印有意义的差异
            if importance > 0.05:
                print(f"\n  特征: {feature_name}")
                print(f"    盈利组平均: {win_avg:.2f}")
                print(f"    亏损组平均: {lose_avg:.2f}")
                print(f"    差异度: {importance:.2%} ({'正相关' if diff > 0 else '负相关'})")
            print(f"    差异度: {diff:.2f}")
            print(f"    重要性: {importance:.4f}")
            print(f"    方向: {'正相关' if diff > 0 else '负相关'}")
        
        # 保存特征重要性分析
        with open(FEATURES_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'analyzed_at': datetime.now().isoformat(),
                'total_trades': len(trades),
                'features': feature_importance
            }, f, ensure_ascii=False, indent=2)
        
        return feature_importance
    
    def optimize_weights_ml(self) -> Dict:
        """
        使用机器学习方法优化权重
        
        采用梯度下降思想：
        - 如果盈利交易的某个特征普遍较高，增加该特征权重
        - 如果亏损交易的某个特征普遍较高，降低该特征权重
        """
        trades = self._load_trades()
        
        if len(trades) < 20:
            print("\n  交易数据不足，需要至少20笔交易才能优化权重")
            return self.current_weights
        
        print("\n" + "=" * 50)
        print("开始AI权重优化...")
        print("=" * 50)
        
        # 当前权重
        weights = self.current_weights['weights'].copy()
        
        # 计算当前胜率
        win_trades = [t for t in trades if t['is_win']]
        current_win_rate = len(win_trades) / len(trades) * 100
        
        print(f"\n  当前胜率: {current_win_rate:.2f}%")
        print(f"  当前权重:")
        for k, v in weights.items():
            print(f"    {k}: {v:.3f}")
        
        # 简单的权重调整策略
        # 基于总评分与盈亏的关系调整
        win_scores = [t['t_score'] for t in win_trades]
        lose_scores = [t['t_score'] for t in trades if not t['is_win']]
        
        win_avg_score = np.mean(win_scores)
        lose_avg_score = np.mean(lose_scores)
        
        print(f"\n  盈利组平均评分: {win_avg_score:.2f}")
        print(f"  亏损组平均评分: {lose_avg_score:.2f}")
        
        # 如果盈利组评分普遍更高，说明评分系统有效
        # 但可以微调权重来提高区分度
        adjustment_factor = 0.01  # 调整幅度
        
        # 随机扰动优化（模拟退火思想）
        new_weights = weights.copy()
        
        # 对每个权重进行小幅随机调整
        np.random.seed(int(datetime.now().timestamp()))
        
        for key in new_weights:
            # 添加小幅随机扰动
            delta = np.random.uniform(-adjustment_factor, adjustment_factor)
            new_weights[key] = max(0.01, min(0.25, new_weights[key] + delta))
        
        # 归一化权重（总和为1）
        total = sum(new_weights.values())
        new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}
        
        print(f"\n  新权重:")
        for k, v in new_weights.items():
            old_v = weights.get(k, 0)
            change = v - old_v
            print(f"    {k}: {v:.4f} (变化: {change:+.4f})")
        
        # 记录进化日志
        evolution_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': 'weight_optimization',
            'trigger': f'数据积累: {len(trades)}笔交易',
            'old_weights': weights,
            'new_weights': new_weights,
            'performance_before': {
                'win_rate': current_win_rate,
                'total_trades': len(trades)
            },
            'expected_improvement': '基于随机扰动优化'
        }
        
        self._log_evolution(evolution_entry)
        
        # 更新权重文件
        self.current_weights['version'] += 1
        self.current_weights['weights'] = new_weights
        self.current_weights['performance'] = {
            'win_rate': current_win_rate,
            'total_trades': len(trades),
            'avg_profit': np.mean([t['profit_pct'] for t in trades])
        }
        self.current_weights['evolution_history'].append({
            'version': self.current_weights['version'],
            'timestamp': datetime.now().isoformat(),
            'win_rate': current_win_rate
        })
        
        self._save_weights(self.current_weights)
        
        print(f"\n  权重已更新! 版本: {self.current_weights['version']}")
        
        return self.current_weights
    
    def reflect_on_strategy(self) -> Dict:
        """
        策略反思 - 分析当前策略的问题并提出改进建议
        
        Returns:
            Dict: 反思报告
        """
        trades = self._load_trades()
        stats = self._load_stats()
        
        print("\n" + "=" * 50)
        print("策略反思分析")
        print("=" * 50)
        
        if len(trades) < 5:
            return {
                'status': 'insufficient_data',
                'message': '数据不足，需要积累更多交易记录'
            }
        
        # 分析维度
        reflection = {
            'timestamp': datetime.now().isoformat(),
            'total_trades': len(trades),
            'analysis': {},
            'suggestions': []
        }
        
        # 1. 胜率分析
        win_rate = stats.get('win_rate', 0)
        reflection['analysis']['win_rate'] = {
            'value': win_rate,
            'status': 'good' if win_rate > 60 else ('warning' if win_rate > 40 else 'critical')
        }
        
        if win_rate < 40:
            reflection['suggestions'].append({
                'type': 'win_rate_critical',
                'message': '胜率过低(<40%)，建议重新审视选股逻辑',
                'action': '考虑增加更严格的筛选条件'
            })
        elif win_rate > 60:
            reflection['suggestions'].append({
                'type': 'win_rate_good',
                'message': '胜率良好(>60%)，策略运行正常',
                'action': '继续积累数据，可考虑适当放宽筛选条件以增加交易机会'
            })
        
        # 2. 盈亏比分析
        win_trades = [t for t in trades if t['is_win']]
        lose_trades = [t for t in trades if not t['is_win']]
        
        if win_trades and lose_trades:
            avg_win = np.mean([t['profit_pct'] for t in win_trades])
            avg_lose = abs(np.mean([t['profit_pct'] for t in lose_trades]))
            profit_ratio = avg_win / avg_lose if avg_lose > 0 else 0
            
            reflection['analysis']['profit_ratio'] = {
                'avg_win': round(avg_win, 2),
                'avg_lose': round(avg_lose, 2),
                'ratio': round(profit_ratio, 2),
                'status': 'good' if profit_ratio > 1 else 'warning'
            }
            
            if profit_ratio < 1:
                reflection['suggestions'].append({
                    'type': 'profit_ratio_low',
                    'message': f'盈亏比({profit_ratio:.2f})过低，平均盈利({avg_win:.2f}%)小于平均亏损({avg_lose:.2f}%)',
                    'action': '考虑增加止盈条件或减少高风险交易'
                })
        
        # 3. 评分有效性分析
        if win_trades and lose_trades:
            win_avg_score = np.mean([t['t_score'] for t in win_trades])
            lose_avg_score = np.mean([t['t_score'] for t in lose_trades])
            score_diff = win_avg_score - lose_avg_score
            
            reflection['analysis']['score_effectiveness'] = {
                'win_avg_score': round(win_avg_score, 2),
                'lose_avg_score': round(lose_avg_score, 2),
                'diff': round(score_diff, 2),
                'status': 'effective' if score_diff > 5 else 'ineffective'
            }
            
            if score_diff < 0:
                reflection['suggestions'].append({
                    'type': 'score_ineffective',
                    'message': f'评分系统可能失效：亏损交易平均评分({lose_avg_score:.2f})高于盈利交易({win_avg_score:.2f})',
                    'action': '建议重新优化评分权重'
                })
        
        # 4. 连续亏损分析
        consecutive_losses = 0
        max_consecutive_losses = 0
        for t in trades:
            if t['is_win']:
                consecutive_losses = 0
            else:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        
        reflection['analysis']['consecutive_losses'] = {
            'max': max_consecutive_losses,
            'status': 'warning' if max_consecutive_losses >= 3 else 'normal'
        }
        
        if max_consecutive_losses >= 3:
            reflection['suggestions'].append({
                'type': 'consecutive_losses',
                'message': f'出现连续{max_consecutive_losses}次亏损',
                'action': '建议检查该时间段的市场环境和选股逻辑'
            })
        
        # 打印反思报告
        print(f"\n  总交易数: {len(trades)}")
        print(f"  胜率: {win_rate}% ({reflection['analysis']['win_rate']['status']})")
        
        if 'profit_ratio' in reflection['analysis']:
            pr = reflection['analysis']['profit_ratio']
            print(f"  盈亏比: {pr['ratio']} (盈利{pr['avg_win']}% vs 亏损{pr['avg_lose']}%)")
        
        if 'score_effectiveness' in reflection['analysis']:
            se = reflection['analysis']['score_effectiveness']
            print(f"  评分有效性: {'有效' if se['status'] == 'effective' else '待优化'}")
            print(f"    盈利组平均评分: {se['win_avg_score']}")
            print(f"    亏损组平均评分: {se['lose_avg_score']}")
        
        print(f"\n  改进建议 ({len(reflection['suggestions'])}条):")
        for i, suggestion in enumerate(reflection['suggestions'], 1):
            print(f"    {i}. [{suggestion['type']}] {suggestion['message']}")
            print(f"       行动: {suggestion['action']}")
        
        return reflection
    
    def _load_stats(self) -> Dict:
        """加载统计数据"""
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def get_current_weights(self) -> Dict:
        """获取当前权重"""
        return self.current_weights['weights']
    
    def auto_evolve(self, min_trades: int = 20) -> Dict:
        """
        自动进化流程
        
        当交易数据足够时自动触发优化
        
        Args:
            min_trades: 触发优化的最小交易数
        
        Returns:
            Dict: 进化结果
        """
        trades = self._load_trades()
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'action': 'none',
            'message': ''
        }
        
        if len(trades) < min_trades:
            result['message'] = f'交易数据不足({len(trades)}/{min_trades})，继续积累数据'
            return result
        
        # 触发自动优化
        result['action'] = 'optimize_weights'
        result['weights'] = self.optimize_weights_ml()
        result['reflection'] = self.reflect_on_strategy()
        result['message'] = f'完成权重优化，当前版本: v{self.current_weights["version"]}'
        
        return result
    
    def generate_report(self) -> str:
        """生成进化报告"""
        trades = self._load_trades()
        stats = self._load_stats()
        weights = self.current_weights
        
        report = []
        report.append("=" * 60)
        report.append("T01龙头战法 - AI进化报告")
        report.append("=" * 60)
        report.append(f"\n报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"权重版本: v{weights['version']}")
        report.append(f"创建时间: {weights['created_at']}")
        
        report.append("\n【当前权重配置】")
        for k, v in weights['weights'].items():
            report.append(f"  {k}: {v:.2%}")
        
        report.append("\n【交易统计】")
        report.append(f"  总交易次数: {stats.get('total_trades', 0)}")
        report.append(f"  盈利次数: {stats.get('win_trades', 0)}")
        report.append(f"  亏损次数: {stats.get('lose_trades', 0)}")
        report.append(f"  胜率: {stats.get('win_rate', 0)}%")
        report.append(f"  平均盈亏: {stats.get('avg_profit', 0)}%")
        
        if weights.get('evolution_history'):
            report.append("\n【进化历史】")
            for evo in weights['evolution_history'][-5:]:
                report.append(f"  v{evo['version']} - {evo['timestamp']} - 胜率: {evo['win_rate']}%")
        
        return "\n".join(report)


def main():
    """测试AI进化模块"""
    print("测试AI进化模块...")
    
    ai = AIEvolution()
    
    # 分析特征重要性
    ai.analyze_feature_importance()
    
    # 策略反思
    ai.reflect_on_strategy()
    
    # 自动进化
    result = ai.auto_evolve(min_trades=10)
    print(f"\n自动进化结果: {result['message']}")
    
    # 生成报告
    print("\n" + ai.generate_report())


if __name__ == "__main__":
    main()
