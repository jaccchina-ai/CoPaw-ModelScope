#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 概率预测模块
================================================
功能：
1. 基于历史数据预测板块成功率
2. 结合异常事件调整概率
3. 计算预测置信度
4. 自动判断样本是否足够

数据需求：
- 历史交易记录（trades.json）
- 选股记录（selected_stocks.json）- 获取板块信息
- 竞价结果（auction_result.json）- 获取推荐股票
"""

import json
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
TRADES_FILE = os.path.join(DATA_BASE_DIR, "trades.json")
STATS_FILE = os.path.join(DATA_BASE_DIR, "stats.json")
SELECTED_STOCKS_FILE = os.path.join(DATA_BASE_DIR, "selected_stocks.json")
AUCTION_RESULT_FILE = os.path.join(DATA_BASE_DIR, "auction_result.json")
SECTOR_HISTORY_FILE = os.path.join(DATA_BASE_DIR, "sector_stats.json")
PROBABILITY_CACHE_FILE = os.path.join(DATA_BASE_DIR, "probability_cache.json")

# ==================== 配置参数 ====================

# 成功标准（与trade_tracker一致）
SUCCESS_THRESHOLD = 0.03  # 3%

# 样本量阈值
SAMPLE_THRESHOLDS = {
    'high': 50,        # 高置信度需要50+样本
    'medium': 20,      # 中置信度需要20+样本
    'low': 10,         # 低置信度需要10+样本
    'minimum': 5       # 最小样本数
}

# 异常事件影响因子
ANOMALY_FACTORS = {
    'consecutive_limit_down': {
        'description': '连续跌停后反弹',
        'factor': lambda count: min(1.3, 1.0 + count * 0.1),  # 每次跌停+10%，上限30%
        'direction': 'positive'  # 有利于反弹
    },
    'consecutive_limit_up': {
        'description': '连续涨停后回调',
        'factor': lambda count: max(0.7, 1.0 - count * 0.1),  # 每次涨停-10%，下限70%
        'direction': 'negative'  # 风险增加
    },
    'sector_overheat': {
        'description': '板块过热',
        'factor': lambda strength: max(0.6, 1.0 - strength / 100000),  # 强度越高风险越大
        'direction': 'negative'
    },
    'policy_positive': {
        'description': '政策利好',
        'factor': lambda: 1.2,
        'direction': 'positive'
    },
    'policy_negative': {
        'description': '政策利空',
        'factor': lambda: 0.8,
        'direction': 'negative'
    }
}

# 情绪周期影响因子
EMOTION_FACTORS = {
    '恢复初期': 0.9,   # 谨慎
    '恢复中期': 1.0,   # 正常
    '上升期': 1.1,     # 乐观
    '高潮期': 0.8,     # 风险增加
    '退潮期': 0.5      # 强制降权
}


@dataclass
class SectorStats:
    """板块统计数据"""
    sector_name: str
    total_trades: int
    win_trades: int
    lose_trades: int
    win_rate: float
    avg_profit: float
    avg_win: float
    avg_loss: float
    confidence: str  # high/medium/low/insufficient


@dataclass
class ProbabilityPrediction:
    """概率预测结果"""
    sector: str
    probability: float           # 成功概率 0-1
    confidence: str              # 置信度等级
    confidence_score: float      # 置信度分数 0-1
    base_rate: float             # 基础胜率
    adjustments: Dict            # 调整因子
    sample_size: int             # 样本量
    recommendation: str          # 建议操作


class SectorDataBuilder:
    """板块数据构建器 - 从交易记录构建板块统计"""
    
    def __init__(self):
        self.trades = self._load_trades()
        self.selected_stocks = self._load_selected_stocks()
        self.sector_stats = {}
    
    def _load_trades(self) -> List[Dict]:
        """加载交易记录"""
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('trades', [])
        return []
    
    def _load_selected_stocks(self) -> Dict:
        """加载选股记录（按日期索引）"""
        stocks_by_date = {}
        
        # 加载当前选股
        if os.path.exists(SELECTED_STOCKS_FILE):
            with open(SELECTED_STOCKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                date = data.get('date', '')
                if date:
                    stocks_by_date[date] = data.get('stocks', [])
        
        # 加载历史选股
        history_dir = os.path.join(DATA_BASE_DIR, 'history')
        if os.path.exists(history_dir):
            for f in os.listdir(history_dir):
                if f.startswith('selection_') and f.endswith('.json'):
                    date = f.replace('selection_', '').replace('.json', '')
                    filepath = os.path.join(history_dir, f)
                    with open(filepath, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                        stocks_by_date[date] = data.get('stocks', [])
        
        return stocks_by_date
    
    def _get_stock_sector(self, stock_code: str, t_date: str) -> str:
        """获取股票对应的板块"""
        # 从选股记录中查找
        if t_date in self.selected_stocks:
            for stock in self.selected_stocks[t_date]:
                if stock.get('code') == stock_code:
                    return stock.get('details', {}).get('hot_sector_name', '未知')
        
        # 尝试相邻日期
        for delta in [-1, 1, -2, 2]:
            try:
                dt = datetime.strptime(t_date, '%Y-%m-%d') + timedelta(days=delta)
                check_date = dt.strftime('%Y-%m-%d')
                if check_date in self.selected_stocks:
                    for stock in self.selected_stocks[check_date]:
                        if stock.get('code') == stock_code:
                            return stock.get('details', {}).get('hot_sector_name', '未知')
            except:
                pass
        
        return '未知'
    
    def build_sector_stats(self) -> Dict[str, SectorStats]:
        """构建板块统计数据"""
        sector_trades = defaultdict(list)
        
        # 按板块分组交易
        for trade in self.trades:
            stock_code = trade.get('stock_code', '')
            t_date = trade.get('t_date', '')
            sector = self._get_stock_sector(stock_code, t_date)
            
            sector_trades[sector].append({
                'profit_pct': trade.get('profit_pct', 0),
                'is_win': trade.get('is_win', False)
            })
        
        # 计算每个板块的统计
        stats = {}
        for sector, trades in sector_trades.items():
            if sector == '未知' or len(trades) < SAMPLE_THRESHOLDS['minimum']:
                continue
            
            total = len(trades)
            wins = [t for t in trades if t.get('is_win')]
            losses = [t for t in trades if not t.get('is_win')]
            
            win_rate = len(wins) / total if total > 0 else 0
            avg_profit = np.mean([t['profit_pct'] for t in trades]) if trades else 0
            avg_win = np.mean([t['profit_pct'] for t in wins]) if wins else 0
            avg_loss = np.mean([t['profit_pct'] for t in losses]) if losses else 0
            
            # 判断置信度
            if total >= SAMPLE_THRESHOLDS['high']:
                confidence = 'high'
            elif total >= SAMPLE_THRESHOLDS['medium']:
                confidence = 'medium'
            elif total >= SAMPLE_THRESHOLDS['low']:
                confidence = 'low'
            else:
                confidence = 'insufficient'
            
            stats[sector] = SectorStats(
                sector_name=sector,
                total_trades=total,
                win_trades=len(wins),
                lose_trades=len(losses),
                win_rate=win_rate,
                avg_profit=avg_profit,
                avg_win=avg_win,
                avg_loss=avg_loss,
                confidence=confidence
            )
        
        self.sector_stats = stats
        return stats
    
    def save_sector_stats(self):
        """保存板块统计"""
        data = {}
        for sector, stats in self.sector_stats.items():
            data[sector] = {
                'sector_name': stats.sector_name,
                'total_trades': stats.total_trades,
                'win_trades': stats.win_trades,
                'lose_trades': stats.lose_trades,
                'win_rate': round(stats.win_rate, 4),
                'avg_profit': round(stats.avg_profit, 2),
                'avg_win': round(stats.avg_win, 2),
                'avg_loss': round(stats.avg_loss, 2),
                'confidence': stats.confidence,
                'updated_at': datetime.now().isoformat()
            }
        
        with open(SECTOR_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return data


class ProbabilityPredictor:
    """概率预测器"""
    
    def __init__(self):
        self.sector_builder = SectorDataBuilder()
        self.sector_stats = {}
        self._load_or_build_stats()
    
    def _load_or_build_stats(self):
        """加载或构建板块统计"""
        if os.path.exists(SECTOR_HISTORY_FILE):
            with open(SECTOR_HISTORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 检查是否过期（超过1天）
                first_sector = list(data.values())[0] if data else {}
                updated_at = first_sector.get('updated_at', '')
                if updated_at:
                    update_time = datetime.fromisoformat(updated_at)
                    if (datetime.now() - update_time).days < 1:
                        # 使用缓存
                        self.sector_stats = {
                            sector: SectorStats(**stats) 
                            for sector, stats in data.items()
                        }
                        return
        
        # 重新构建
        self.sector_stats = self.sector_builder.build_sector_stats()
        self.sector_builder.save_sector_stats()
    
    def check_data_sufficiency(self) -> Tuple[bool, Dict]:
        """
        检查数据是否足够进行概率预测
        
        Returns:
            (是否足够, 统计信息)
        """
        total_trades = sum(s.total_trades for s in self.sector_stats.values())
        total_sectors = len(self.sector_stats)
        high_conf_sectors = sum(1 for s in self.sector_stats.values() if s.confidence == 'high')
        medium_conf_sectors = sum(1 for s in self.sector_stats.values() if s.confidence == 'medium')
        
        # 判断标准：至少有3个板块达到中置信度
        sufficient = medium_conf_sectors + high_conf_sectors >= 3
        
        info = {
            'total_trades': total_trades,
            'total_sectors': total_sectors,
            'high_confidence_sectors': high_conf_sectors,
            'medium_confidence_sectors': medium_conf_sectors,
            'sector_breakdown': {
                sector: {
                    'samples': stats.total_trades,
                    'win_rate': f"{stats.win_rate*100:.1f}%",
                    'confidence': stats.confidence
                }
                for sector, stats in sorted(
                    self.sector_stats.items(), 
                    key=lambda x: -x[1].total_trades
                )
            }
        }
        
        return sufficient, info
    
    def calculate_confidence_score(self, sample_size: int) -> Tuple[str, float]:
        """
        计算置信度分数
        
        Returns:
            (置信度等级, 置信度分数0-1)
        """
        if sample_size >= SAMPLE_THRESHOLDS['high']:
            return 'high', 0.9
        elif sample_size >= SAMPLE_THRESHOLDS['medium']:
            # 线性插值 0.6-0.9
            score = 0.6 + 0.3 * (sample_size - SAMPLE_THRESHOLDS['medium']) / (SAMPLE_THRESHOLDS['high'] - SAMPLE_THRESHOLDS['medium'])
            return 'medium', round(score, 2)
        elif sample_size >= SAMPLE_THRESHOLDS['low']:
            # 线性插值 0.3-0.6
            score = 0.3 + 0.3 * (sample_size - SAMPLE_THRESHOLDS['low']) / (SAMPLE_THRESHOLDS['medium'] - SAMPLE_THRESHOLDS['low'])
            return 'low', round(score, 2)
        else:
            return 'insufficient', 0.1
    
    def predict_probability(self, sector: str, 
                           emotion_stage: str = '恢复中期',
                           anomalies: List[Dict] = None) -> ProbabilityPrediction:
        """
        预测单个板块的成功概率
        
        Args:
            sector: 板块名称
            emotion_stage: 当前情绪周期
            anomalies: 异常事件列表
        
        Returns:
            ProbabilityPrediction
        """
        # 获取板块基础统计
        if sector in self.sector_stats:
            stats = self.sector_stats[sector]
            base_rate = stats.win_rate
            sample_size = stats.total_trades
        else:
            # 无历史数据，使用默认值
            base_rate = 0.4  # 保守估计
            sample_size = 0
        
        # 计算置信度
        confidence, confidence_score = self.calculate_confidence_score(sample_size)
        
        # 如果数据不足，直接返回低置信度预测
        if confidence == 'insufficient':
            return ProbabilityPrediction(
                sector=sector,
                probability=base_rate,
                confidence=confidence,
                confidence_score=confidence_score,
                base_rate=base_rate,
                adjustments={},
                sample_size=sample_size,
                recommendation='数据不足，建议观望'
            )
        
        # 计算调整因子
        adjustments = {
            'base_rate': base_rate,
            'emotion_factor': EMOTION_FACTORS.get(emotion_stage, 1.0),
            'anomaly_factor': 1.0,
            'anomaly_details': []
        }
        
        # 异常事件调整
        if anomalies:
            for anomaly in anomalies:
                anomaly_type = anomaly.get('type')
                if anomaly_type in ANOMALY_FACTORS:
                    factor_config = ANOMALY_FACTORS[anomaly_type]
                    factor_func = factor_config['factor']
                    
                    # 根据异常类型计算因子
                    if anomaly_type in ['consecutive_limit_down', 'consecutive_limit_up']:
                        count = anomaly.get('count', 1)
                        factor = factor_func(count)
                    elif anomaly_type == 'sector_overheat':
                        strength = anomaly.get('strength', 50000)
                        factor = factor_func(strength)
                    else:
                        factor = factor_func()
                    
                    adjustments['anomaly_factor'] *= factor
                    adjustments['anomaly_details'].append({
                        'type': anomaly_type,
                        'description': factor_config['description'],
                        'factor': round(factor, 3),
                        'direction': factor_config['direction']
                    })
        
        # 综合概率计算
        probability = base_rate * adjustments['emotion_factor'] * adjustments['anomaly_factor']
        probability = max(0.1, min(0.95, probability))  # 限制在10%-95%
        
        # 生成建议
        if probability >= 0.6 and confidence in ['high', 'medium']:
            recommendation = '建议买入'
        elif probability >= 0.5 and confidence == 'high':
            recommendation = '可考虑买入'
        elif probability < 0.4:
            recommendation = '建议观望'
        else:
            recommendation = '谨慎参与'
        
        return ProbabilityPrediction(
            sector=sector,
            probability=round(probability, 3),
            confidence=confidence,
            confidence_score=confidence_score,
            base_rate=round(base_rate, 3),
            adjustments=adjustments,
            sample_size=sample_size,
            recommendation=recommendation
        )
    
    def predict_batch(self, sectors: List[str], 
                     emotion_stage: str = '恢复中期',
                     sector_anomalies: Dict = None) -> Dict[str, ProbabilityPrediction]:
        """
        批量预测多个板块
        
        Args:
            sectors: 板块列表
            emotion_stage: 情绪周期
            sector_anomalies: {板块: [异常事件列表]}
        
        Returns:
            {板块: 预测结果}
        """
        results = {}
        
        for sector in sectors:
            anomalies = sector_anomalies.get(sector, []) if sector_anomalies else []
            results[sector] = self.predict_probability(sector, emotion_stage, anomalies)
        
        return results
    
    def get_top_sectors(self, n: int = 5, 
                       min_confidence: str = 'medium') -> List[Tuple[str, ProbabilityPrediction]]:
        """
        获取成功率最高的N个板块
        
        Args:
            n: 返回数量
            min_confidence: 最低置信度要求
        """
        confidence_order = {'high': 3, 'medium': 2, 'low': 1, 'insufficient': 0}
        min_level = confidence_order.get(min_confidence, 1)
        
        valid_sectors = [
            (sector, self.predict_probability(sector))
            for sector in self.sector_stats.keys()
            if confidence_order.get(self.sector_stats[sector].confidence, 0) >= min_level
        ]
        
        # 按概率排序
        sorted_sectors = sorted(valid_sectors, key=lambda x: -x[1].probability)
        
        return sorted_sectors[:n]
    
    def print_prediction_report(self, predictions: Dict[str, ProbabilityPrediction]):
        """打印预测报告"""
        print("\n" + "=" * 70)
        print("T01龙头战法 - 概率预测报告")
        print("=" * 70)
        
        # 数据充分性检查
        sufficient, info = self.check_data_sufficiency()
        
        print(f"\n【数据充分性】{'✅ 足够' if sufficient else '⚠️ 不足'}")
        print(f"  总交易数: {info['total_trades']}")
        print(f"  板块数: {info['total_sectors']}")
        print(f"  高/中置信度板块: {info['high_confidence_sectors']}/{info['medium_confidence_sectors']}")
        
        print(f"\n【板块统计详情】")
        for sector, details in list(info['sector_breakdown'].items())[:10]:
            conf_icon = '✅' if details['confidence'] == 'high' else ('🔶' if details['confidence'] == 'medium' else '⚠️')
            print(f"  {conf_icon} {sector}: {details['samples']}笔, 胜率{details['win_rate']}, {details['confidence']}")
        
        print(f"\n【概率预测结果】")
        for sector, pred in sorted(predictions.items(), key=lambda x: -x[1].probability):
            conf_icon = '✅' if pred.confidence == 'high' else ('🔶' if pred.confidence == 'medium' else '⚠️')
            print(f"\n  {conf_icon} {sector}")
            print(f"    成功概率: {pred.probability*100:.1f}%")
            print(f"    置信度: {pred.confidence} ({pred.confidence_score:.2f})")
            print(f"    基础胜率: {pred.base_rate*100:.1f}%")
            print(f"    样本量: {pred.sample_size}笔")
            if pred.adjustments.get('anomaly_details'):
                print(f"    异常调整:")
                for adj in pred.adjustments['anomaly_details']:
                    print(f"      - {adj['description']}: x{adj['factor']}")
            print(f"    建议: {pred.recommendation}")


def run_probability_prediction(sector_anomalies: Dict = None, 
                               emotion_stage: str = None) -> Dict:
    """
    运行概率预测（入口函数）
    
    自动判断数据是否足够：
    - 不足：返回提示信息
    - 足够：返回预测结果
    """
    predictor = ProbabilityPredictor()
    
    # 检查数据充分性
    sufficient, info = predictor.check_data_sufficiency()
    
    if not sufficient:
        return {
            'status': 'insufficient_data',
            'message': f"数据不足，需要更多交易记录。当前{info['total_trades']}笔交易，{info['medium_confidence_sectors']}个板块达到中置信度。",
            'required': f"至少需要3个板块达到中置信度（每板块20+笔交易）",
            'current_stats': info
        }
    
    # 获取情绪周期（如果未提供）
    if emotion_stage is None:
        # 尝试从风控状态获取
        risk_file = os.path.join(DATA_BASE_DIR, 'risk_status.json')
        if os.path.exists(risk_file):
            with open(risk_file, 'r', encoding='utf-8') as f:
                risk_data = json.load(f)
                emotion_stage = risk_data.get('emotion_stage', '恢复中期')
        else:
            emotion_stage = '恢复中期'
    
    # 获取需要预测的板块
    if sector_anomalies:
        sectors = list(sector_anomalies.keys())
    else:
        # 预测所有有数据的板块
        sectors = list(predictor.sector_stats.keys())
    
    # 执行预测
    predictions = predictor.predict_batch(sectors, emotion_stage, sector_anomalies)
    
    # 转换为可序列化格式
    result = {
        'status': 'success',
        'emotion_stage': emotion_stage,
        'predictions': {
            sector: {
                'probability': pred.probability,
                'confidence': pred.confidence,
                'confidence_score': pred.confidence_score,
                'base_rate': pred.base_rate,
                'sample_size': pred.sample_size,
                'recommendation': pred.recommendation,
                'adjustments': pred.adjustments
            }
            for sector, pred in predictions.items()
        },
        'top_sectors': [
            {'sector': sector, 'probability': pred.probability, 'recommendation': pred.recommendation}
            for sector, pred in predictor.get_top_sectors(5)
        ],
        'data_info': info
    }
    
    # 保存缓存
    with open(PROBABILITY_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    
    return result


def main():
    """测试入口"""
    print("=" * 70)
    print("T01龙头战法 - 概率预测模块测试")
    print("=" * 70)
    
    # 运行预测
    result = run_probability_prediction()
    
    if result['status'] == 'insufficient_data':
        print(f"\n⚠️ {result['message']}")
        print(f"   要求: {result['required']}")
        print(f"\n   当前统计:")
        for sector, details in list(result['current_stats']['sector_breakdown'].items())[:5]:
            print(f"     - {sector}: {details['samples']}笔, {details['confidence']}")
    else:
        # 打印报告
        predictor = ProbabilityPredictor()
        
        predictions = {
            sector: ProbabilityPrediction(
                sector=sector,
                probability=data['probability'],
                confidence=data['confidence'],
                confidence_score=data['confidence_score'],
                base_rate=data['base_rate'],
                adjustments=data['adjustments'],
                sample_size=data['sample_size'],
                recommendation=data['recommendation']
            )
            for sector, data in result['predictions'].items()
        }
        
        predictor.print_prediction_report(predictions)
        
        print(f"\n【Top 5 推荐板块】")
        for item in result['top_sectors']:
            print(f"  {item['sector']}: {item['probability']*100:.1f}% - {item['recommendation']}")


if __name__ == "__main__":
    main()
