#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - AI进化模块 V2.0（高级版）
================================================
新增功能：
1. 成功标准：T+2收盘/T+1开盘 > 1.03%
2. IC值监控：每周回测因子IC值，Alpha Decay应对
3. 因子正交化：防止多重共线性，保留90%方差
4. MoA策略反思：多Agent辩论反思策略有效性
5. 遗传算法权重优化
6. 新因子挖掘：相关性分析发现有效因子
7. 连续无选股预警
8. 阈值自适应调优
"""

import json
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import random
import warnings
warnings.filterwarnings('ignore')

# 使用scipy.stats，如果不可用则使用简化版
try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    # 简化版统计函数
    class SimpleStats:
        @staticmethod
        def spearmanr(a, b):
            """简化版Spearman相关系数"""
            if len(a) != len(b) or len(a) < 2:
                return (0.0, 1.0)
            # 转换为秩
            rank_a = np.argsort(np.argsort(a)).astype(float)
            rank_b = np.argsort(np.argsort(b)).astype(float)
            # Pearson相关
            mean_a, mean_b = np.mean(rank_a), np.mean(rank_b)
            std_a, std_b = np.std(rank_a), np.std(rank_b)
            if std_a == 0 or std_b == 0:
                return (0.0, 1.0)
            corr = np.mean((rank_a - mean_a) * (rank_b - mean_b)) / (std_a * std_b)
            return (corr, 0.05)  # 简化p值
    stats = SimpleStats()

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
TRADES_FILE = os.path.join(DATA_BASE_DIR, "trades.json")
STATS_FILE = os.path.join(DATA_BASE_DIR, "stats.json")
WEIGHTS_FILE = os.path.join(DATA_BASE_DIR, "weights.json")
EVOLUTION_LOG = os.path.join(DATA_BASE_DIR, "evolution_log.json")
FEATURES_FILE = os.path.join(DATA_BASE_DIR, "feature_importance.json")
IC_HISTORY_FILE = os.path.join(DATA_BASE_DIR, "ic_history.json")
FACTOR_CORRELATION_FILE = os.path.join(DATA_BASE_DIR, "factor_correlation.json")
SELECTED_STOCKS_FILE = os.path.join(DATA_BASE_DIR, "selected_stocks.json")
ALERTS_FILE = os.path.join(DATA_BASE_DIR, "alerts.json")

# ==================== 配置常量 ====================

# 成功标准：T+2收盘/T+1开盘 > 1.03%
SUCCESS_THRESHOLD = 1.03

# IC值阈值
IC_WARNING_THRESHOLD = 0.05   # IC < 0.05 预警
IC_FAILURE_THRESHOLD = 0.03   # IC < 0.03 标记失效

# 因子相关性阈值
CORRELATION_THRESHOLD = 0.8   # 相关性 > 0.8 需要正交化

# 遗传算法配置
GA_CONFIG = {
    'population_size': 50,      # 种群大小
    'generations': 100,         # 迭代代数
    'mutation_rate': 0.1,       # 变异率
    'crossover_rate': 0.8,      # 交叉率
    'elite_ratio': 0.1,         # 精英比例
}

# 因子定义
FACTORS = [
    'first_limit_time',      # 首次涨停时间
    'seal_ratio',            # 封成比
    'seal_market_cap',       # 封单金额/流通市值
    'dragon_tiger',          # 龙虎榜
    'main_fund_ratio',       # 主力资金净占比
    'amount',                # 成交金额
    'turnover_rate',         # 换手率
    'volume_ratio',          # 量比
    'hot_sector',            # 热点板块
]


@dataclass
class FactorStatus:
    """因子状态"""
    name: str
    ic_value: float
    status: str  # 'active', 'warning', 'failed'
    last_updated: str
    decay_trend: str  # 'improving', 'stable', 'declining'


@dataclass
class EvolutionResult:
    """进化结果"""
    timestamp: str
    version: int
    old_weights: Dict[str, float]
    new_weights: Dict[str, float]
    ic_improvement: float
    win_rate_change: float
    suggestions: List[str]
    moa_insights: List[str]


class ICAnalyzer:
    """IC值分析器 - 因子有效性监控"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.ic_history = self._load_ic_history()
    
    def _load_ic_history(self) -> Dict:
        """加载IC历史"""
        if os.path.exists(IC_HISTORY_FILE):
            with open(IC_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'history': []}
    
    def _save_ic_history(self):
        """保存IC历史"""
        with open(IC_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.ic_history, f, ensure_ascii=False, indent=2)
    
    def calculate_ic(self, factor_values: np.ndarray, returns: np.ndarray) -> float:
        """
        计算信息系数(IC)
        IC = 因子值与未来收益的相关系数
        
        Args:
            factor_values: 因子值数组
            returns: 未来收益数组
        
        Returns:
            IC值（-1到1之间）
        """
        if len(factor_values) != len(returns) or len(factor_values) < 5:
            return 0.0
        
        # Spearman秩相关（比Pearson更稳健）
        ic, _ = stats.spearmanr(factor_values, returns)
        
        return ic if not np.isnan(ic) else 0.0
    
    def analyze_all_factors(self, trades: List[Dict]) -> Dict[str, FactorStatus]:
        """
        分析所有因子的IC值
        
        Args:
            trades: 交易记录列表
        
        Returns:
            Dict[str, FactorStatus]: 各因子的状态
        """
        if len(trades) < 10:
            print("  ⚠️ 交易数据不足，需要至少10笔交易")
            return {}
        
        factor_status = {}
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 获取历史IC值用于趋势分析
        history_ic = {}
        for record in self.ic_history.get('history', [])[-4:]:  # 最近4周
            for factor, ic in record.get('factors', {}).items():
                if factor not in history_ic:
                    history_ic[factor] = []
                history_ic[factor].append(ic)
        
        for factor in FACTORS:
            # 提取因子值和收益
            factor_values = []
            returns = []
            
            for trade in trades:
                # 从trade中获取因子值（需要扩展trade数据结构）
                # 暂时用t_score作为综合因子
                factor_val = trade.get(f'factor_{factor}', trade.get('t_score', 0))
                ret = trade.get('profit_pct', 0)
                
                factor_values.append(factor_val)
                returns.append(ret)
            
            factor_values = np.array(factor_values)
            returns = np.array(returns)
            
            # 计算IC
            ic = self.calculate_ic(factor_values, returns)
            
            # 判断状态
            if ic < IC_FAILURE_THRESHOLD:
                status = 'failed'
            elif ic < IC_WARNING_THRESHOLD:
                status = 'warning'
            else:
                status = 'active'
            
            # 判断趋势
            if factor in history_ic and len(history_ic[factor]) >= 2:
                recent_ic = history_ic[factor][-1] if history_ic[factor] else ic
                if ic > recent_ic * 1.1:
                    trend = 'improving'
                elif ic < recent_ic * 0.9:
                    trend = 'declining'
                else:
                    trend = 'stable'
            else:
                trend = 'stable'
            
            factor_status[factor] = FactorStatus(
                name=factor,
                ic_value=round(ic, 4),
                status=status,
                last_updated=current_date,
                decay_trend=trend
            )
        
        # 保存IC历史
        ic_record = {
            'date': current_date,
            'total_trades': len(trades),
            'factors': {f: s.ic_value for f, s in factor_status.items()}
        }
        self.ic_history['history'].append(ic_record)
        self._save_ic_history()
        
        return factor_status
    
    def get_alpha_decay_report(self, factor_status: Dict[str, FactorStatus]) -> Dict:
        """
        生成Alpha Decay报告
        
        Returns:
            包含预警和建议的报告
        """
        report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_factors': len(factor_status),
                'active': 0,
                'warning': 0,
                'failed': 0
            },
            'failed_factors': [],
            'declining_factors': [],
            'recommendations': []
        }
        
        for factor, status in factor_status.items():
            if status.status == 'failed':
                report['summary']['failed'] += 1
                report['failed_factors'].append({
                    'name': factor,
                    'ic': status.ic_value,
                    'trend': status.decay_trend
                })
            elif status.status == 'warning':
                report['summary']['warning'] += 1
            else:
                report['summary']['active'] += 1
            
            if status.decay_trend == 'declining':
                report['declining_factors'].append({
                    'name': factor,
                    'ic': status.ic_value,
                    'status': status.status
                })
        
        # 生成建议
        if report['summary']['failed'] > 0:
            report['recommendations'].append(
                f"⚠️ {report['summary']['failed']}个因子已失效，建议重新优化权重或替换因子"
            )
        
        if report['declining_factors']:
            report['recommendations'].append(
                f"📉 {len(report['declining_factors'])}个因子呈下降趋势，需持续监控"
            )
        
        return report


class FactorOrthogonalizer:
    """因子正交化处理器 - 纯numpy实现"""
    
    def __init__(self, variance_threshold: float = 0.9):
        """
        Args:
            variance_threshold: 保留的方差比例阈值（默认90%）
        """
        self.variance_threshold = variance_threshold
        self.components = None
        self.mean = None
        self.std = None
        self.explained_variance_ratio = None
        self.factor_names = None
        self.loadings = None
    
    def analyze_correlation(self, factor_data: np.ndarray, factor_names: List[str] = None) -> Dict:
        """
        分析因子相关性
        
        Args:
            factor_data: 因子数据矩阵 (n_samples, n_factors)
            factor_names: 因子名称列表
        
        Returns:
            相关性分析报告
        """
        if factor_names is None:
            factor_names = [f'factor_{i}' for i in range(factor_data.shape[1])]
        
        self.factor_names = factor_names
        
        # 计算相关系数矩阵
        n = factor_data.shape[1]
        corr_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    corr_matrix[i, j] = 1.0
                else:
                    corr = self._pearson_corr(factor_data[:, i], factor_data[:, j])
                    corr_matrix[i, j] = corr
        
        # 找出高相关因子对
        high_corr_pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                corr = abs(corr_matrix[i, j])
                if corr > CORRELATION_THRESHOLD:
                    high_corr_pairs.append({
                        'factor1': factor_names[i],
                        'factor2': factor_names[j],
                        'correlation': round(corr, 4)
                    })
        
        # 保存相关性报告
        report = {
            'timestamp': datetime.now().isoformat(),
            'correlation_matrix': {factor_names[i]: {factor_names[j]: round(corr_matrix[i, j], 4) 
                                                      for j in range(n)} for i in range(n)},
            'high_correlation_pairs': high_corr_pairs,
            'recommendations': []
        }
        
        if high_corr_pairs:
            report['recommendations'].append(
                f"发现{len(high_corr_pairs)}对高相关因子(>0.8)，建议进行正交化处理"
            )
        
        with open(FACTOR_CORRELATION_FILE, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        return report
    
    def _pearson_corr(self, x: np.ndarray, y: np.ndarray) -> float:
        """计算Pearson相关系数"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        mean_x, mean_y = np.mean(x), np.mean(y)
        std_x, std_y = np.std(x), np.std(y)
        if std_x == 0 or std_y == 0:
            return 0.0
        return np.mean((x - mean_x) * (y - mean_y)) / (std_x * std_y)
    
    def orthogonalize(self, factor_data: np.ndarray, factor_names: List[str] = None) -> Tuple[np.ndarray, Dict]:
        """
        因子正交化处理 - 使用SVD实现PCA
        
        Args:
            factor_data: 因子数据矩阵 (n_samples, n_factors)
            factor_names: 因子名称列表
        
        Returns:
            (正交化后的因子, 处理信息)
        """
        if factor_names is None:
            factor_names = [f'factor_{i}' for i in range(factor_data.shape[1])]
        
        self.factor_names = factor_names
        
        # 标准化
        self.mean = np.mean(factor_data, axis=0)
        self.std = np.std(factor_data, axis=0) + 1e-8
        factor_scaled = (factor_data - self.mean) / self.std
        
        # 使用SVD实现PCA
        U, S, Vt = np.linalg.svd(factor_scaled, full_matrices=False)
        
        # 计算方差解释率
        total_var = np.sum(S ** 2)
        self.explained_variance_ratio = (S ** 2) / total_var
        
        # 选择保留的成分数量（保留90%方差）
        cumsum = np.cumsum(self.explained_variance_ratio)
        n_components = np.argmax(cumsum >= self.variance_threshold) + 1
        n_components = max(1, min(n_components, len(S)))
        
        # 主成分
        factor_orthogonal = U[:, :n_components] * S[:n_components]
        
        # 载荷矩阵
        self.components = Vt[:n_components, :]
        self.loadings = self.components.T  # (n_factors, n_components)
        
        info = {
            'original_dimensions': factor_data.shape[1],
            'reduced_dimensions': n_components,
            'variance_explained': self.explained_variance_ratio[:n_components].tolist(),
            'total_variance_explained': float(cumsum[n_components-1]),
            'loadings': {factor_names[i]: {f'PC{j+1}': round(self.loadings[i, j], 4) 
                                           for j in range(n_components)} 
                        for i in range(len(factor_names))}
        }
        
        return factor_orthogonal, info
    
    def get_factor_importance(self) -> Dict[str, float]:
        """
        获取因子重要性（基于PCA载荷）
        
        Returns:
            各因子的重要性得分
        """
        if self.loadings is None or self.explained_variance_ratio is None:
            return {}
        
        # 计算每个因子的综合重要性
        importance = {}
        n_components = self.loadings.shape[1]
        
        for i, factor in enumerate(self.factor_names):
            weighted_importance = sum(
                (self.loadings[i, j] ** 2) * self.explained_variance_ratio[j]
                for j in range(n_components)
            )
            importance[factor] = round(weighted_importance, 4)
        
        return importance


class GeneticAlgorithmOptimizer:
    """遗传算法权重优化器"""
    
    def __init__(self, config: Dict = None):
        self.config = config or GA_CONFIG
        self.best_solution = None
        self.evolution_history = []
    
    def _initialize_population(self, num_factors: int) -> List[np.ndarray]:
        """初始化种群"""
        population = []
        for _ in range(self.config['population_size']):
            # 随机生成权重，确保和为1
            weights = np.random.random(num_factors)
            weights = weights / weights.sum()
            population.append(weights)
        return population
    
    def _fitness(self, weights: np.ndarray, factor_returns: np.ndarray, 
                 actual_returns: np.ndarray) -> float:
        """
        适应度函数
        
        计算权重组合的预测能力
        """
        # 加权因子得分
        weighted_score = np.dot(factor_returns, weights)
        
        # 计算与实际收益的相关性（IC）
        ic, _ = stats.spearmanr(weighted_score, actual_returns)
        
        # 计算夏普比率作为辅助指标
        if np.std(actual_returns) > 0:
            sharpe = np.mean(actual_returns) / np.std(actual_returns)
        else:
            sharpe = 0
        
        # 综合适应度
        fitness = abs(ic) * 0.7 + (sharpe / 10) * 0.3
        
        return fitness if not np.isnan(fitness) else 0
    
    def _selection(self, population: List[np.ndarray], fitnesses: List[float]) -> List[np.ndarray]:
        """选择操作（轮盘赌选择）"""
        selected = []
        
        # 精英保留
        elite_size = int(self.config['population_size'] * self.config['elite_ratio'])
        elite_indices = np.argsort(fitnesses)[-elite_size:]
        for idx in elite_indices:
            selected.append(population[idx].copy())
        
        # 轮盘赌选择
        fitnesses = np.array(fitnesses)
        fitnesses = fitnesses - fitnesses.min() + 1  # 确保非负
        probs = fitnesses / fitnesses.sum()
        
        while len(selected) < self.config['population_size']:
            idx = np.random.choice(len(population), p=probs)
            selected.append(population[idx].copy())
        
        return selected
    
    def _crossover(self, parent1: np.ndarray, parent2: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """交叉操作"""
        if np.random.random() > self.config['crossover_rate']:
            return parent1.copy(), parent2.copy()
        
        # 单点交叉
        point = np.random.randint(1, len(parent1) - 1)
        
        child1 = np.concatenate([parent1[:point], parent2[point:]])
        child2 = np.concatenate([parent2[:point], parent1[point:]])
        
        # 归一化
        child1 = child1 / child1.sum()
        child2 = child2 / child2.sum()
        
        return child1, child2
    
    def _mutate(self, individual: np.ndarray) -> np.ndarray:
        """变异操作"""
        if np.random.random() > self.config['mutation_rate']:
            return individual.copy()
        
        # 随机选择一个基因进行变异
        mutated = individual.copy()
        idx = np.random.randint(len(mutated))
        mutated[idx] = np.random.random()
        
        # 归一化
        mutated = mutated / mutated.sum()
        
        return mutated
    
    def optimize(self, factor_data: np.ndarray, returns: np.ndarray,
                 current_weights: Dict[str, float]) -> Dict[str, float]:
        """
        执行遗传算法优化
        
        Args:
            factor_data: 因子数据矩阵 (n_samples, n_factors)
            returns: 实际收益数组
            current_weights: 当前权重
        
        Returns:
            优化后的权重
        """
        num_factors = factor_data.shape[1] if len(factor_data.shape) > 1 else 1
        
        # 初始化种群
        population = self._initialize_population(num_factors)
        
        # 将当前权重加入种群（作为精英种子）
        current_weight_array = np.array([current_weights.get(f, 1/num_factors) 
                                          for f in FACTORS[:num_factors]])
        current_weight_array = current_weight_array / current_weight_array.sum()
        population[0] = current_weight_array
        
        best_fitness = 0
        best_weights = current_weight_array.copy()
        
        # 迭代进化
        for gen in range(self.config['generations']):
            # 计算适应度
            fitnesses = [
                self._fitness(ind, factor_data, returns) 
                for ind in population
            ]
            
            # 记录最佳
            max_idx = np.argmax(fitnesses)
            if fitnesses[max_idx] > best_fitness:
                best_fitness = fitnesses[max_idx]
                best_weights = population[max_idx].copy()
            
            # 选择
            population = self._selection(population, fitnesses)
            
            # 交叉和变异
            new_population = []
            for i in range(0, len(population) - 1, 2):
                child1, child2 = self._crossover(population[i], population[i+1])
                new_population.extend([self._mutate(child1), self._mutate(child2)])
            
            population = new_population[:self.config['population_size']]
            
            # 记录进化历史
            self.evolution_history.append({
                'generation': gen,
                'best_fitness': best_fitness,
                'avg_fitness': np.mean(fitnesses)
            })
        
        self.best_solution = best_weights
        
        # 转换为字典格式
        optimized_weights = {
            FACTORS[i]: round(best_weights[i], 4) 
            for i in range(len(FACTORS)) if i < len(best_weights)
        }
        
        # 归一化确保和为1
        total = sum(optimized_weights.values())
        optimized_weights = {k: round(v/total, 4) for k, v in optimized_weights.items()}
        
        return optimized_weights


class MoAReflector:
    """MoA策略反思器 - 多Agent辩论"""
    
    def __init__(self, moa_skill_path: str = "/mnt/workspace/working/active_skills/moa"):
        self.moa_skill_path = moa_skill_path
    
    def reflect(self, trades: List[Dict], stats: Dict, 
                factor_status: Dict[str, FactorStatus],
                ic_report: Dict) -> Dict:
        """
        执行MoA策略反思
        
        Returns:
            包含多角度分析结论的报告
        """
        # 准备反思材料
        reflection_data = {
            'trades_summary': {
                'total': len(trades),
                'wins': sum(1 for t in trades if t.get('is_win')),
                'losses': sum(1 for t in trades if not t.get('is_win')),
                'win_rate': stats.get('win_rate', 0),
                'avg_profit': stats.get('avg_profit', 0),
            },
            'factor_health': {
                'active': ic_report['summary']['active'],
                'warning': ic_report['summary']['warning'],
                'failed': ic_report['summary']['failed'],
            },
            'recent_performance': self._analyze_recent_performance(trades),
            'issues_identified': self._identify_issues(trades, factor_status),
        }
        
        # 如果有MoA skill，调用它进行深度分析
        # 这里我们模拟多角度分析
        perspectives = self._multi_perspective_analysis(reflection_data)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'reflection_data': reflection_data,
            'perspectives': perspectives,
            'consensus_recommendations': self._build_consensus(perspectives),
        }
    
    def _analyze_recent_performance(self, trades: List[Dict], recent_days: int = 10) -> Dict:
        """分析近期表现"""
        recent_trades = trades[-recent_days:] if len(trades) > recent_days else trades
        
        if not recent_trades:
            return {'status': 'no_data'}
        
        wins = [t for t in recent_trades if t.get('is_win')]
        losses = [t for t in recent_trades if not t.get('is_win')]
        
        return {
            'period_trades': len(recent_trades),
            'win_rate': len(wins) / len(recent_trades) * 100 if recent_trades else 0,
            'avg_win': np.mean([t['profit_pct'] for t in wins]) if wins else 0,
            'avg_loss': np.mean([t['profit_pct'] for t in losses]) if losses else 0,
            'trend': 'improving' if len(wins) > len(losses) else 'declining'
        }
    
    def _identify_issues(self, trades: List[Dict], 
                         factor_status: Dict[str, FactorStatus]) -> List[str]:
        """识别问题"""
        issues = []
        
        # 检查连续亏损
        max_consecutive = 0
        current_consecutive = 0
        for t in trades:
            if not t.get('is_win'):
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        if max_consecutive >= 3:
            issues.append(f"连续亏损: 出现{max_consecutive}次连续亏损")
        
        # 检查因子失效
        failed_factors = [f for f, s in factor_status.items() if s.status == 'failed']
        if failed_factors:
            issues.append(f"因子失效: {', '.join(failed_factors)}")
        
        # 检查评分有效性
        wins = [t for t in trades if t.get('is_win')]
        losses = [t for t in trades if not t.get('is_win')]
        
        if wins and losses:
            win_avg_score = np.mean([t['t_score'] for t in wins])
            lose_avg_score = np.mean([t['t_score'] for t in losses])
            
            if lose_avg_score >= win_avg_score:
                issues.append(f"评分失效: 亏损交易评分({lose_avg_score:.1f})>=盈利交易({win_avg_score:.1f})")
        
        return issues
    
    def _multi_perspective_analysis(self, data: Dict) -> Dict:
        """多角度分析（模拟MoA）"""
        perspectives = {
            'quantitative_analyst': self._quantitative_view(data),
            'risk_manager': self._risk_view(data),
            'market_strategist': self._strategy_view(data),
        }
        return perspectives
    
    def _quantitative_view(self, data: Dict) -> Dict:
        """量化分析师视角"""
        view = {
            'role': '量化分析师',
            'analysis': [],
            'recommendations': []
        }
        
        # 胜率分析
        win_rate = data['trades_summary']['win_rate']
        if win_rate < 40:
            view['analysis'].append(f"胜率{win_rate}%偏低，模型预测能力不足")
            view['recommendations'].append("建议增加筛选条件，提高选股门槛")
        elif win_rate > 60:
            view['analysis'].append(f"胜率{win_rate}%良好，模型有效")
        
        # 因子健康度
        failed = data['factor_health']['failed']
        if failed > 0:
            view['analysis'].append(f"{failed}个因子失效，需要替换或优化")
            view['recommendations'].append("运行遗传算法重新优化权重")
        
        return view
    
    def _risk_view(self, data: Dict) -> Dict:
        """风险管理师视角"""
        view = {
            'role': '风险管理师',
            'analysis': [],
            'recommendations': []
        }
        
        # 近期表现
        recent = data['recent_performance']
        if recent.get('trend') == 'declining':
            view['analysis'].append(f"近期趋势下行，需警惕")
            view['recommendations'].append("建议降低仓位或暂停交易")
        
        # 问题识别
        issues = data['issues_identified']
        for issue in issues:
            if '连续亏损' in issue:
                view['analysis'].append(issue)
                view['recommendations'].append("连续亏损后建议暂停1-2天")
        
        return view
    
    def _strategy_view(self, data: Dict) -> Dict:
        """市场策略师视角"""
        view = {
            'role': '市场策略师',
            'analysis': [],
            'recommendations': []
        }
        
        # 盈亏比分析
        recent = data['recent_performance']
        avg_win = recent.get('avg_win', 0)
        avg_loss = abs(recent.get('avg_loss', 0))
        
        if avg_loss > 0:
            profit_ratio = avg_win / avg_loss
            if profit_ratio < 1:
                view['analysis'].append(f"盈亏比{profit_ratio:.2f}过低")
                view['recommendations'].append("优化止盈策略，减少过早卖出")
        
        return view
    
    def _build_consensus(self, perspectives: Dict) -> List[str]:
        """构建共识建议"""
        all_recommendations = []
        for perspective in perspectives.values():
            all_recommendations.extend(perspective.get('recommendations', []))
        
        # 去重并排序
        unique_recommendations = list(dict.fromkeys(all_recommendations))
        
        return unique_recommendations[:5]  # 返回前5条


class AlphaMiner:
    """新因子挖掘器"""
    
    def __init__(self):
        self.discovered_factors = []
    
    def mine_new_factors(self, trades: List[Dict], 
                         factor_data: np.ndarray = None) -> List[Dict]:
        """
        挖掘新因子
        
        通过相关性分析发现潜在有效因子
        """
        new_factors = []
        
        if len(trades) < 20:
            return new_factors
        
        # 提取收益
        returns = np.array([t['profit_pct'] for t in trades])
        
        # 分析现有因子的衍生因子
        # 例如：封成比的平方、封单市值比的对数等
        
        potential_factors = [
            ('seal_ratio_squared', '封成比平方', 
             lambda t: t.get('factor_seal_ratio', 0) ** 2),
            ('seal_ratio_log', '封成比对数', 
             lambda t: np.log1p(abs(t.get('factor_seal_ratio', 0)))),
            ('time_seal_interaction', '时间×封单交互', 
             lambda t: t.get('factor_first_limit_time', 0) * t.get('factor_seal_ratio', 0)),
            ('momentum_3day', '3日动量', 
             lambda t: t.get('profit_pct', 0)),  # 简化示例
        ]
        
        for factor_name, factor_desc, calc_func in potential_factors:
            try:
                # 计算因子值
                factor_values = np.array([calc_func(t) for t in trades])
                
                # 计算与收益的相关性
                if len(factor_values) == len(returns) and len(factor_values) > 5:
                    result = stats.spearmanr(factor_values, returns)
                    # 兼容scipy返回格式
                    if isinstance(result, tuple):
                        corr, pvalue = result
                    else:
                        corr = result.correlation if hasattr(result, 'correlation') else result
                        pvalue = result.pvalue if hasattr(result, 'pvalue') else 0.05
                    
                    if not np.isnan(corr) and abs(corr) > 0.1 and pvalue < 0.1:
                        new_factors.append({
                            'name': factor_name,
                            'description': factor_desc,
                            'correlation': round(corr, 4),
                            'p_value': round(pvalue, 4),
                            'direction': 'positive' if corr > 0 else 'negative',
                            'potential': 'high' if abs(corr) > 0.2 else 'medium'
                        })
            except Exception as e:
                continue
        
        self.discovered_factors = new_factors
        return new_factors


class AlertSystem:
    """预警系统"""
    
    def __init__(self):
        self.alerts = self._load_alerts()
    
    def _load_alerts(self) -> List[Dict]:
        """加载预警记录"""
        if os.path.exists(ALERTS_FILE):
            with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('alerts', [])
        return []
    
    def _save_alerts(self):
        """保存预警记录"""
        with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'alerts': self.alerts}, f, ensure_ascii=False, indent=2)
    
    def check_no_selection_alert(self, days: int = 3) -> Optional[Dict]:
        """
        检查连续无选股预警
        
        Args:
            days: 连续无选股天数阈值
        
        Returns:
            预警信息或None
        """
        if not os.path.exists(SELECTED_STOCKS_FILE):
            return None
        
        with open(SELECTED_STOCKS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        last_date = data.get('date', '')
        
        if last_date:
            last_dt = datetime.strptime(last_date, '%Y-%m-%d')
            days_since = (datetime.now() - last_dt).days
            
            if days_since >= days:
                alert = {
                    'type': 'no_selection',
                    'level': 'warning',
                    'message': f'策略失效预警: 连续{days_since}天无选股',
                    'timestamp': datetime.now().isoformat(),
                    'details': {
                        'last_selection_date': last_date,
                        'days_without_selection': days_since
                    }
                }
                self.alerts.append(alert)
                self._save_alerts()
                return alert
        
        return None
    
    def add_alert(self, alert_type: str, level: str, message: str, details: Dict = None):
        """添加预警"""
        alert = {
            'type': alert_type,
            'level': level,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'details': details or {}
        }
        self.alerts.append(alert)
        self._save_alerts()
        return alert


class AIEvolutionV2:
    """AI进化引擎 V2.0"""
    
    def __init__(self):
        self.data_dir = DATA_BASE_DIR
        self._ensure_files()
        self.current_weights = self._load_weights()
        
        # 初始化各模块
        self.ic_analyzer = ICAnalyzer(DATA_BASE_DIR)
        self.orthogonalizer = FactorOrthogonalizer()
        self.ga_optimizer = GeneticAlgorithmOptimizer()
        self.moa_reflector = MoAReflector()
        self.alpha_miner = AlphaMiner()
        self.alert_system = AlertSystem()
    
    def _ensure_files(self):
        """确保必要文件存在"""
        if not os.path.exists(WEIGHTS_FILE):
            initial_weights = {
                'version': 1,
                'created_at': datetime.now().isoformat(),
                'weights': {f: round(1/len(FACTORS), 4) for f in FACTORS},
                'thresholds': {
                    'success_threshold': SUCCESS_THRESHOLD,
                    'ic_warning': IC_WARNING_THRESHOLD,
                    'ic_failure': IC_FAILURE_THRESHOLD,
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
        
        for file_path in [EVOLUTION_LOG, FEATURES_FILE, IC_HISTORY_FILE, 
                          FACTOR_CORRELATION_FILE, ALERTS_FILE]:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({'logs': []} if 'log' in file_path else {}, f)
    
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
    
    def _load_stats(self) -> Dict:
        """加载统计数据"""
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _log_evolution(self, log_entry: Dict):
        """记录进化日志"""
        with open(EVOLUTION_LOG, 'r', encoding='utf-8') as f:
            log_data = json.load(f)
        
        if 'logs' not in log_data:
            log_data['logs'] = []
        log_data['logs'].append(log_entry)
        
        with open(EVOLUTION_LOG, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
    
    def evaluate_trade_success(self, trade: Dict) -> bool:
        """
        评估交易是否成功
        
        成功标准：T+2收盘价 / T+1开盘价 > 1.03%
        """
        # 获取价格数据（需要从trade或外部获取）
        t2_close = trade.get('t2_close_price', trade.get('sell_price', 0))
        t1_open = trade.get('t1_open_price', trade.get('buy_price', 0))
        
        if t1_open > 0:
            ratio = t2_close / t1_open
            return ratio > SUCCESS_THRESHOLD
        
        # 回退到使用profit_pct
        return trade.get('profit_pct', 0) > 3
    
    def run_full_evolution(self) -> EvolutionResult:
        """
        执行完整的进化流程
        
        Returns:
            EvolutionResult: 进化结果
        """
        print("\n" + "=" * 70)
        print("T01龙头战法 - AI进化系统 V2.0")
        print("=" * 70)
        
        trades = self._load_trades()
        stats = self._load_stats()
        
        if len(trades) < 10:
            print("  ⚠️ 交易数据不足，需要至少10笔交易")
            return None
        
        # ========== 步骤1: IC值分析 ==========
        print("\n【步骤1】因子IC值分析...")
        factor_status = self.ic_analyzer.analyze_all_factors(trades)
        ic_report = self.ic_analyzer.get_alpha_decay_report(factor_status)
        
        print(f"  因子状态统计:")
        print(f"    - 有效: {ic_report['summary']['active']}个")
        print(f"    - 预警: {ic_report['summary']['warning']}个")
        print(f"    - 失效: {ic_report['summary']['failed']}个")
        
        for factor, status in factor_status.items():
            status_emoji = "✅" if status.status == 'active' else ("⚠️" if status.status == 'warning' else "❌")
            trend_emoji = "📈" if status.decay_trend == 'improving' else ("📉" if status.decay_trend == 'declining' else "➡️")
            print(f"    {status_emoji} {factor}: IC={status.ic_value:.4f} {trend_emoji}")
        
        # ========== 步骤2: 因子相关性分析 ==========
        print("\n【步骤2】因子相关性分析...")
        # 构建因子数据矩阵（简化处理）
        factor_data = self._build_factor_data(trades)
        
        if factor_data is not None and len(factor_data) > 0:
            corr_report = self.orthogonalizer.analyze_correlation(factor_data)
            
            if corr_report['high_correlation_pairs']:
                print(f"  发现{len(corr_report['high_correlation_pairs'])}对高相关因子:")
                for pair in corr_report['high_correlation_pairs'][:3]:
                    print(f"    - {pair['factor1']} vs {pair['factor2']}: {pair['correlation']:.4f}")
            else:
                print("  ✅ 无高相关因子对")
        
        # ========== 步骤3: 因子正交化 ==========
        print("\n【步骤3】因子正交化处理...")
        if factor_data is not None and len(factor_data) > 5:
            ortho_factors, ortho_info = self.orthogonalizer.orthogonalize(factor_data)
            print(f"  原始维度: {ortho_info['original_dimensions']}")
            print(f"  降维后维度: {ortho_info['reduced_dimensions']}")
            print(f"  方差解释率: {ortho_info['total_variance_explained']*100:.1f}%")
            
            factor_importance = self.orthogonalizer.get_factor_importance()
            print(f"  因子重要性:")
            for factor, imp in sorted(factor_importance.items(), key=lambda x: -x[1])[:5]:
                print(f"    - {factor}: {imp:.4f}")
        
        # ========== 步骤4: 遗传算法权重优化 ==========
        print("\n【步骤4】遗传算法权重优化...")
        current_weights = self.current_weights['weights']
        
        # 准备优化数据
        returns = np.array([t['profit_pct'] for t in trades])
        factor_matrix = self._build_factor_matrix(trades)
        
        if factor_matrix is not None and len(factor_matrix) > 0:
            optimized_weights = self.ga_optimizer.optimize(
                factor_matrix, returns, current_weights
            )
            
            print(f"  优化完成:")
            print(f"    权重变化:")
            for factor in FACTORS:
                old_w = current_weights.get(factor, 0)
                new_w = optimized_weights.get(factor, 0)
                change = new_w - old_w
                print(f"      {factor}: {old_w:.4f} → {new_w:.4f} ({change:+.4f})")
        else:
            optimized_weights = current_weights
            print("  ⚠️ 数据不足，保持当前权重")
        
        # ========== 步骤5: MoA策略反思 ==========
        print("\n【步骤5】MoA策略反思...")
        reflection = self.moa_reflector.reflect(trades, stats, factor_status, ic_report)
        
        print(f"  多角度分析:")
        for role, perspective in reflection['perspectives'].items():
            if perspective['analysis']:
                print(f"    【{perspective['role']}】")
                for analysis in perspective['analysis']:
                    print(f"      - {analysis}")
        
        print(f"\n  共识建议:")
        for i, rec in enumerate(reflection['consensus_recommendations'], 1):
            print(f"    {i}. {rec}")
        
        # ========== 步骤6: 新因子挖掘 ==========
        print("\n【步骤6】新因子挖掘...")
        new_factors = self.alpha_miner.mine_new_factors(trades, factor_data)
        
        if new_factors:
            print(f"  发现{len(new_factors)}个潜在有效因子:")
            for nf in new_factors:
                print(f"    - {nf['description']}: 相关性={nf['correlation']:.4f} ({nf['direction']})")
        else:
            print("  未发现新的有效因子")
        
        # ========== 步骤7: 预警检查 ==========
        print("\n【步骤7】预警检查...")
        no_selection_alert = self.alert_system.check_no_selection_alert(3)
        
        if no_selection_alert:
            print(f"  ⚠️ {no_selection_alert['message']}")
        else:
            print("  ✅ 无预警")
        
        # ========== 保存进化结果 ==========
        old_weights = current_weights.copy()
        
        # 更新权重
        self.current_weights['version'] += 1
        self.current_weights['weights'] = optimized_weights
        self.current_weights['performance'] = {
            'win_rate': stats.get('win_rate', 0),
            'total_trades': len(trades),
            'avg_profit': stats.get('avg_profit', 0)
        }
        self.current_weights['evolution_history'].append({
            'version': self.current_weights['version'],
            'timestamp': datetime.now().isoformat(),
            'win_rate': stats.get('win_rate', 0),
            'ic_avg': np.mean([s.ic_value for s in factor_status.values()]) if factor_status else 0
        })
        
        self._save_weights(self.current_weights)
        
        # 记录进化日志
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'version': self.current_weights['version'],
            'type': 'full_evolution',
            'old_weights': old_weights,
            'new_weights': optimized_weights,
            'ic_report': {
                'summary': ic_report['summary'],
                'failed_factors': ic_report['failed_factors']
            },
            'reflection': reflection['consensus_recommendations'],
            'new_factors': new_factors,
            'alerts': [no_selection_alert] if no_selection_alert else []
        }
        self._log_evolution(log_entry)
        
        print("\n" + "=" * 70)
        print(f"✅ 进化完成! 版本: v{self.current_weights['version']}")
        print("=" * 70)
        
        return EvolutionResult(
            timestamp=datetime.now().isoformat(),
            version=self.current_weights['version'],
            old_weights=old_weights,
            new_weights=optimized_weights,
            ic_improvement=0,  # 需要计算
            win_rate_change=0,
            suggestions=reflection['consensus_recommendations'],
            moa_insights=[a for p in reflection['perspectives'].values() for a in p['analysis']]
        )
    
    def _build_factor_data(self, trades: List[Dict]) -> Optional[np.ndarray]:
        """构建因子数据矩阵"""
        # 从交易记录中提取因子值
        factor_rows = []
        
        for trade in trades:
            row = []
            for factor in FACTORS:
                # 尝试从trade中获取因子值
                value = trade.get(f'factor_{factor}', trade.get('t_score', 0))
                row.append(float(value))
            factor_rows.append(row)
        
        if factor_rows:
            return np.array(factor_rows)
        return None
    
    def _build_factor_matrix(self, trades: List[Dict]) -> Optional[np.ndarray]:
        """构建因子数据矩阵"""
        df = self._build_factor_data(trades)
        if df is not None:
            return df.values
        return None
    
    def generate_evolution_report(self) -> str:
        """生成进化报告"""
        trades = self._load_trades()
        stats = self._load_stats()
        
        report = []
        report.append("=" * 70)
        report.append("T01龙头战法 - AI进化报告 V2.0")
        report.append("=" * 70)
        report.append(f"\n报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"权重版本: v{self.current_weights['version']}")
        
        report.append("\n【当前权重配置】")
        for k, v in self.current_weights['weights'].items():
            report.append(f"  {k}: {v:.2%}")
        
        report.append("\n【交易统计】")
        report.append(f"  总交易次数: {stats.get('total_trades', 0)}")
        report.append(f"  胜率: {stats.get('win_rate', 0)}%")
        report.append(f"  平均盈亏: {stats.get('avg_profit', 0)}%")
        
        # IC历史
        if os.path.exists(IC_HISTORY_FILE):
            with open(IC_HISTORY_FILE, 'r', encoding='utf-8') as f:
                ic_history = json.load(f)
            
            if ic_history.get('history'):
                report.append("\n【IC历史趋势】")
                for record in ic_history['history'][-5:]:
                    report.append(f"  {record['date']}: " + 
                                ", ".join([f"{k}={v:.3f}" for k, v in record['factors'].items()[:3]]))
        
        # 进化历史
        if self.current_weights.get('evolution_history'):
            report.append("\n【进化历史】")
            for evo in self.current_weights['evolution_history'][-5:]:
                report.append(f"  v{evo['version']} - {evo['timestamp']} - 胜率: {evo['win_rate']}%")
        
        # 预警记录
        if self.alert_system.alerts:
            report.append("\n【预警记录】")
            for alert in self.alert_system.alerts[-5:]:
                report.append(f"  [{alert['level']}] {alert['message']}")
        
        return "\n".join(report)


def main():
    """主函数"""
    print("启动AI进化系统 V2.0...")
    
    evolution = AIEvolutionV2()
    
    # 执行完整进化
    result = evolution.run_full_evolution()
    
    if result:
        print(f"\n进化结果:")
        print(f"  版本: v{result.version}")
        print(f"  建议: {result.suggestions[:3]}")
    
    # 生成报告
    print("\n" + evolution.generate_evolution_report())


if __name__ == "__main__":
    main()
