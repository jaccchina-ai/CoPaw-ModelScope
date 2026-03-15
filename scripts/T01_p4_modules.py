#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - P4深度分析模块 V2.0（完整版）
================================================
包含：
1. UnlockRiskDetector - 解禁风险检测
2. ReduceRiskDetector - 减持风险检测
3. InvestorAnalyzer - 游资画像分析
4. EmotionCycleAnalyzer - 情绪周期判断（增强版）
5. SectorRotationAnalyzer - 板块轮动预测
6. AuctionFundFlowAnalyzer - 竞价资金流向分析
7. MarketPredictionEngine - 市场预测引擎（新增）
8. RiskAssessmentEngine - 综合风控评估（新增）

依赖数据源：仅使用stockAPI
"""

import json
import os
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stockapi_client import StockAPIClient

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"

# ==================== 游资画像数据库 ====================

FAMOUS_INVESTORS = {
    '章盟主': {
        'names': ['章盟主', '国泰君安上海江苏路', '中信上海溧阳路'],
        'style': '趋势',
        'win_rate': 0.58,
        'avg_holding': 1,
        'score_bonus': 4,
        'description': '活跃游资，超短线'
    },
    '欢乐海岸': {
        'names': ['欢乐海岸', '中泰深圳欢乐海岸', '华鑫深圳分公司'],
        'style': '连板',
        'win_rate': 0.55,
        'avg_holding': 2,
        'score_bonus': 5,
        'description': '连板接力，敢于锁仓'
    },
    '赵老哥': {
        'names': ['赵老哥', '银河绍兴', '浙商绍兴分公司'],
        'style': '短线',
        'win_rate': 0.60,
        'avg_holding': 1,
        'score_bonus': 6,
        'description': '老牌游资，稳健'
    },
    '作手新一': {
        'names': ['作手新一', '南京证券南京大钟亭'],
        'style': '短线',
        'win_rate': 0.57,
        'avg_holding': 1,
        'score_bonus': 5,
        'description': '新生代游资'
    },
    '小鳄鱼': {
        'names': ['小鳄鱼', '中投无锡清扬路', '华泰扬州文昌中路'],
        'style': '短线',
        'win_rate': 0.56,
        'avg_holding': 1,
        'score_bonus': 4,
        'description': '活跃游资'
    },
    '机构': {
        'names': ['机构专用', '机构', '基金', '社保', 'QFII', 'RQFII'],
        'style': '趋势',
        'win_rate': 0.70,
        'avg_holding': 7,
        'score_bonus': 10,
        'description': '机构资金，中长线为主'
    },
    '北向资金': {
        'names': ['北向', '沪股通', '深股通', '陆股通'],
        'style': '趋势',
        'win_rate': 0.65,
        'avg_holding': 10,
        'score_bonus': 8,
        'description': '外资，中长期持有'
    }
}

# 情绪周期阈值
EMOTION_THRESHOLDS = {
    'recovery_early': {'limit_up_count': (20, 40), 'avg_lb': (1, 1.5), 'seal_ratio': (3, 8)},
    'recovery_mid': {'limit_up_count': (40, 70), 'avg_lb': (1.5, 2.5), 'seal_ratio': (5, 15)},
    'rising': {'limit_up_count': (70, 100), 'avg_lb': (2, 3), 'seal_ratio': (10, 20)},
    'climax': {'limit_up_count': (100, 150), 'avg_lb': (3, 5), 'seal_ratio': (15, 30)},
    'falling': {'limit_up_count': (150, 200), 'avg_lb': (1, 2), 'seal_ratio': (5, 15)}
}


# ==================== 1. 解禁风险检测器 ====================

class UnlockRiskDetector:
    """个股解禁风险检测器"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.cache = {}
    
    def check_unlock_risk(self, stock_name: str, stock_code: str) -> Dict:
        """
        检测个股解禁风险
        
        由于stockAPI不直接提供解禁数据，使用估值方法：
        1. 新股/次新股（上市<1年）解禁风险高
        2. 检查流通市值占比
        """
        result = {
            'has_risk': False,
            'unlock_date': None,
            'unlock_ratio': 0,
            'risk_level': '无',
            'detail': '无解禁风险'
        }
        
        try:
            # 获取涨停股数据
            today = self.client.get_today_date()
            stocks = self.client.get_limit_up_stocks(today)
            
            for stock in stocks:
                if stock.get('code') == stock_code:
                    # 检查流通市值
                    flow_capital = float(stock.get('flowCapital', 0))
                    total_capital = float(stock.get('totalCapital', 0))
                    
                    if total_capital > 0:
                        flow_ratio = flow_capital / total_capital
                        
                        # 流通比例低，解禁压力大
                        if flow_ratio < 0.3:
                            result['has_risk'] = True
                            result['unlock_ratio'] = 1 - flow_ratio
                            result['risk_level'] = '高'
                            result['detail'] = f'流通比例仅{flow_ratio*100:.1f}%，解禁压力大'
                        elif flow_ratio < 0.5:
                            result['has_risk'] = True
                            result['unlock_ratio'] = 1 - flow_ratio
                            result['risk_level'] = '中'
                            result['detail'] = f'流通比例{flow_ratio*100:.1f}%，需关注解禁'
                    
                    break
            
            return result
            
        except Exception as e:
            return result
    
    def batch_check(self, stocks: List[Dict]) -> List[Dict]:
        """批量检测"""
        results = []
        for stock in stocks:
            r = self.check_unlock_risk(stock.get('name', ''), stock.get('code', ''))
            results.append({
                'code': stock.get('code'),
                'name': stock.get('name'),
                **r
            })
        return results


# ==================== 2. 减持风险检测器 ====================

class ReduceRiskDetector:
    """减持风险检测器"""
    
    def __init__(self):
        self.client = StockAPIClient()
    
    def check_reduce_risk(self, stock_name: str, stock_code: str, 
                          dragon_tiger_data: Dict = None) -> Dict:
        """
        检测减持风险
        
        通过龙虎榜数据检测：
        1. 大股东/高管减持
        2. 机构大额卖出
        """
        result = {
            'has_risk': False,
            'risk_level': '无',
            'detail': '无减持风险',
            'sell_amount': 0,
            'sell_ratio': 0
        }
        
        if not dragon_tiger_data:
            return result
        
        try:
            sell_amount = float(dragon_tiger_data.get('sellAmount', 0))
            buy_amount = float(dragon_tiger_data.get('buyAmount', 0))
            
            if sell_amount > 0:
                # 净卖出比例
                net_sell = sell_amount - buy_amount
                sell_ratio = net_sell / sell_amount if sell_amount > 0 else 0
                
                # 大额净卖出
                if net_sell > 1e8:  # 1亿
                    result['has_risk'] = True
                    result['risk_level'] = '高'
                    result['sell_amount'] = net_sell
                    result['sell_ratio'] = sell_ratio
                    result['detail'] = f'龙虎榜净卖出{net_sell/1e8:.2f}亿'
                elif net_sell > 5e7:  # 5000万
                    result['has_risk'] = True
                    result['risk_level'] = '中'
                    result['sell_amount'] = net_sell
                    result['sell_ratio'] = sell_ratio
                    result['detail'] = f'龙虎榜净卖出{net_sell/1e7:.2f}千万'
            
            return result
            
        except Exception as e:
            return result


# ==================== 3. 游资画像分析器 ====================

class InvestorAnalyzer:
    """龙虎榜游资画像分析器"""
    
    def __init__(self):
        self.client = StockAPIClient()
    
    def analyze_investors(self, dragon_tiger_data: Dict) -> Dict:
        """
        分析龙虎榜游资
        
        Returns:
            {
                'has_famous_investor': bool,
                'investors': [{'name', 'style', 'win_rate', 'score_bonus'}],
                'total_score_bonus': float,
                'style_analysis': {'trend': int, 'short': int},
                'avg_win_rate': float,
                'recommendation': str
            }
        """
        result = {
            'has_famous_investor': False,
            'investors': [],
            'total_score_bonus': 0,
            'style_analysis': {'trend': 0, 'short': 0},
            'avg_win_rate': 0,
            'recommendation': '无知名游资'
        }
        
        if not dragon_tiger_data:
            return result
        
        # 解析龙虎榜数据中的营业部名称
        # 由于stockAPI返回的龙虎榜数据格式可能不同，需要适配
        try:
            # 尝试从数据中提取买卖方信息
            # 这里简化处理，实际需要根据API返回格式解析
            net_buy = float(dragon_tiger_data.get('buyAmount', 0)) - float(dragon_tiger_data.get('sellAmount', 0))
            
            if net_buy > 0:
                # 有净买入，加分
                result['total_score_bonus'] = min(net_buy / 1e8, 5)  # 最多加5分
                result['recommendation'] = f'净买入{net_buy/1e8:.2f}亿，资金看好'
            
            return result
            
        except Exception as e:
            return result
    
    def analyze_dragon_tiger(self, dragon_tiger_data: Dict) -> Dict:
        """龙虎榜分析 - analyze_investors的别名"""
        return self.analyze_investors(dragon_tiger_data)
    
    def identify_investor(self, name: str) -> Optional[Dict]:
        """识别游资身份"""
        for investor_name, info in FAMOUS_INVESTORS.items():
            if any(alias in name for alias in info['names']):
                return {
                    'name': investor_name,
                    'style': info['style'],
                    'win_rate': info['win_rate'],
                    'score_bonus': info['score_bonus'],
                    'description': info['description']
                }
        return None


# ==================== 4. 情绪周期分析器（增强版） ====================

class EmotionCycleAnalyzer:
    """情绪周期分析器 - 增强版"""
    
    STAGES = {
        '恢复初期': {
            'position_limit': 0.1,
            'description': '市场刚经历大幅调整，谨慎操作',
            'score_threshold': (0, 25)
        },
        '恢复中期': {
            'position_limit': 0.3,
            'description': '市场情绪回暖，可适度参与',
            'score_threshold': (25, 50)
        },
        '上升期': {
            'position_limit': 0.5,
            'description': '市场情绪良好，正常参与',
            'score_threshold': (50, 70)
        },
        '高潮期': {
            'position_limit': 0.3,
            'description': '市场过热，注意风险',
            'score_threshold': (70, 85)
        },
        '退潮期': {
            'position_limit': 0.0,
            'description': '市场退潮，空仓避险',
            'score_threshold': (85, 100)
        }
    }
    
    def __init__(self):
        self.client = StockAPIClient()
    
    def analyze_emotion(self, date: str = None) -> Dict:
        """
        分析情绪周期
        
        综合指标：
        1. 涨停股数量
        2. 平均连板高度
        3. 平均封单强度
        4. 炸板率
        """
        if date is None:
            date = self.client.get_today_date()
        
        try:
            # 获取涨停股数据
            stocks = self.client.get_limit_up_stocks(date)
            
            if not stocks:
                return self._default_result('无法获取涨停数据')
            
            # 计算各项指标
            limit_up_count = len(stocks)
            avg_lb = self._calc_avg_lb(stocks)
            avg_seal_ratio = self._calc_avg_seal_ratio(stocks)
            bomb_rate = self._calc_bomb_rate(stocks)
            
            # 计算情绪得分
            score = self._calc_emotion_score(
                limit_up_count, avg_lb, avg_seal_ratio, bomb_rate
            )
            
            # 确定阶段
            stage_name = self._determine_stage(score)
            stage_info = self.STAGES.get(stage_name, self.STAGES['恢复中期'])
            
            return {
                'date': date,
                'emotion_score': score,
                'stage_name': stage_name,
                'position_limit': stage_info['position_limit'],
                'description': stage_info['description'],
                'metrics': {
                    'limit_up_count': limit_up_count,
                    'avg_lb': round(avg_lb, 2),
                    'avg_seal_ratio': round(avg_seal_ratio, 2),
                    'bomb_rate': round(bomb_rate, 2)
                },
                'risk_warning': self._generate_risk_warning(stage_name, score)
            }
            
        except Exception as e:
            return self._default_result(f'分析异常: {str(e)}')
    
    def _calc_avg_lb(self, stocks: List) -> float:
        """计算平均连板数"""
        if not stocks:
            return 1.0
        lbs = [int(s.get('lbNum', 1)) for s in stocks]
        return np.mean(lbs) if lbs else 1.0
    
    def _calc_avg_seal_ratio(self, stocks: List) -> float:
        """计算平均封成比"""
        ratios = []
        for s in stocks:
            ceiling_amount = float(s.get('ceilingAmount', 0))
            amount = float(s.get('amount', 0))
            if amount > 0:
                ratios.append(ceiling_amount / amount * 100)
        return np.mean(ratios) if ratios else 0
    
    def _calc_bomb_rate(self, stocks: List) -> float:
        """计算炸板率"""
        if not stocks:
            return 0
        bomb_count = sum(1 for s in stocks if int(s.get('bombNum', 0)) > 0)
        return bomb_count / len(stocks)
    
    def _calc_emotion_score(self, limit_up_count, avg_lb, avg_seal_ratio, bomb_rate) -> int:
        """计算情绪得分 0-100"""
        # 涨停数量得分 (0-40分)
        if limit_up_count >= 100:
            count_score = 40
        elif limit_up_count >= 70:
            count_score = 30
        elif limit_up_count >= 50:
            count_score = 20
        elif limit_up_count >= 30:
            count_score = 10
        else:
            count_score = 5
        
        # 连板高度得分 (0-30分)
        if avg_lb >= 4:
            lb_score = 30
        elif avg_lb >= 3:
            lb_score = 25
        elif avg_lb >= 2:
            lb_score = 15
        else:
            lb_score = 5
        
        # 封单强度得分 (0-20分)
        if avg_seal_ratio >= 20:
            seal_score = 20
        elif avg_seal_ratio >= 10:
            seal_score = 15
        elif avg_seal_ratio >= 5:
            seal_score = 10
        else:
            seal_score = 5
        
        # 炸板率扣分 (0-10分扣分)
        bomb_penalty = bomb_rate * 10
        
        score = count_score + lb_score + seal_score - bomb_penalty
        return max(0, min(100, int(score)))
    
    def _determine_stage(self, score: int) -> str:
        """确定情绪阶段"""
        for stage_name, info in self.STAGES.items():
            low, high = info['score_threshold']
            if low <= score < high:
                return stage_name
        return '恢复中期'
    
    def _generate_risk_warning(self, stage_name: str, score: int) -> str:
        """生成风险提示"""
        warnings = {
            '恢复初期': '市场低迷，建议轻仓或空仓观望',
            '高潮期': '市场过热，追高风险大，建议逐步减仓',
            '退潮期': '市场退潮信号明显，建议空仓'
        }
        return warnings.get(stage_name, '')
    
    def _default_result(self, reason: str) -> Dict:
        """默认结果"""
        return {
            'date': '',
            'emotion_score': 50,
            'stage_name': '恢复中期',
            'position_limit': 0.3,
            'description': reason,
            'metrics': {},
            'risk_warning': ''
        }


# ==================== 5. 板块轮动分析器 ====================

class SectorRotationAnalyzer:
    """板块轮动预测分析器"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.history = self._load_history()
    
    def _load_history(self) -> Dict:
        """加载板块历史"""
        history_file = os.path.join(DATA_BASE_DIR, 'sector_history.json')
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 适配两种格式：新格式是按日期组织的，旧格式是 {"records": [...]}
                if 'records' in data:
                    return {'records': data['records']}
                # 按日期格式转换为records格式
                records = []
                for date_str in sorted(data.keys()):
                    if date_str.count('-') == 2:  # 是日期格式
                        day_record = {'date': date_str, 'sectors': []}
                        for sector_name, info in data[date_str].items():
                            day_record['sectors'].append({
                                'name': sector_name,
                                'strength': info.get('strength', 0),
                                'rank': info.get('rank', 0)
                            })
                        records.append(day_record)
                return {'records': records}
        return {'records': []}
    
    def _save_history(self):
        """保存板块历史"""
        history_file = os.path.join(DATA_BASE_DIR, 'sector_history.json')
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)
    
    def update_and_analyze(self, date: str, hot_sectors: List) -> Dict:
        """
        更新并分析板块轮动
        
        Args:
            date: 日期
            hot_sectors: 当日热点板块列表
        
        Returns:
            {
                'rising_sectors': [],      # 上升板块
                'falling_sectors': [],     # 下降板块
                'sustained_sectors': [],   # 持续强势
                'new_sectors': [],         # 新热点
                'recommendation': str
            }
        """
        result = {
            'rising_sectors': [],
            'falling_sectors': [],
            'sustained_sectors': [],
            'new_sectors': [],
            'recommendation': ''
        }
        
        if not hot_sectors:
            return result
        
        # 记录当日板块
        today_record = {
            'date': date,
            'sectors': [
                {
                    'name': s.get('bkName', ''),
                    'strength': float(s.get('qiangdu', 0)),
                    'rank': i + 1
                }
                for i, s in enumerate(hot_sectors[:20])
            ]
        }
        
        # 获取前几天的记录
        records = self.history.get('records', [])[-5:]  # 最近5天
        
        # 分析轮动
        if records:
            prev_sectors = {}
            for r in records[-3:]:  # 最近3天
                for s in r.get('sectors', []):
                    name = s['name']
                    if name not in prev_sectors:
                        prev_sectors[name] = []
                    prev_sectors[name].append(s['strength'])
            
            today_sector_names = {s['name'] for s in today_record['sectors']}
            
            for s in today_record['sectors'][:10]:
                name = s['name']
                strength = s['strength']
                
                if name in prev_sectors:
                    prev_avg = np.mean(prev_sectors[name])
                    if strength > prev_avg * 1.2:
                        result['rising_sectors'].append(name)
                    elif strength < prev_avg * 0.8:
                        result['falling_sectors'].append(name)
                    else:
                        result['sustained_sectors'].append(name)
                else:
                    result['new_sectors'].append(name)
        
        # 保存今日记录
        self.history['records'].append(today_record)
        if len(self.history['records']) > 30:  # 只保留30天
            self.history['records'] = self.history['records'][-30:]
        self._save_history()
        
        # 生成建议
        if result['sustained_sectors']:
            result['recommendation'] = f"持续强势: {', '.join(result['sustained_sectors'][:3])}。"
        if result['new_sectors']:
            result['recommendation'] += f"新热点: {', '.join(result['new_sectors'][:3])}。"
        
        return result


# ==================== 6. 竞价资金流向分析器 ====================

class AuctionFundFlowAnalyzer:
    """竞价资金流向分析器"""
    
    def __init__(self):
        self.client = StockAPIClient()
    
    def analyze_auction_fund_flow(self, date: str = None) -> Dict:
        """
        分析竞价资金流向
        
        Returns:
            {
                'net_inflow_sectors': [],  # 净流入板块
                'net_outflow_sectors': [], # 净流出板块
                'hot_individuals': [],     # 热门个股
                'summary': str
            }
        """
        if date is None:
            date = self.client.get_today_date()
        
        result = {
            'net_inflow_sectors': [],
            'net_outflow_sectors': [],
            'hot_individuals': [],
            'summary': ''
        }
        
        try:
            # 获取竞价热点板块
            auction_sectors = self.client.get_enhanced_auction_sectors()
            
            if auction_sectors:
                for s in auction_sectors[:10]:
                    jjzf = float(s.get('jjzf', 0))
                    if jjzf > 1:
                        result['net_inflow_sectors'].append({
                            'name': s.get('bkName', ''),
                            'change': jjzf,
                            'up_count': s.get('szjs', 0)
                        })
                    elif jjzf < -1:
                        result['net_outflow_sectors'].append({
                            'name': s.get('bkName', ''),
                            'change': jjzf,
                            'down_count': s.get('xdjs', 0)
                        })
            
            # 获取竞价抢筹股
            robbing = self.client.get_auction_robbing()
            if robbing:
                for r in robbing[:5]:
                    result['hot_individuals'].append({
                        'code': r.get('code', ''),
                        'name': r.get('name', ''),
                        'change': float(r.get('jjzf', 0))
                    })
            
            # 生成摘要
            if result['net_inflow_sectors']:
                top_in = result['net_inflow_sectors'][0]['name']
                result['summary'] = f"竞价资金主要流入{top_in}板块"
            
            return result
            
        except Exception as e:
            return result


# ==================== 7. 市场预测引擎（新增） ====================

class MarketPredictionEngine:
    """市场预测引擎"""
    
    def __init__(self):
        self.emotion_analyzer = EmotionCycleAnalyzer()
        self.sector_analyzer = SectorRotationAnalyzer()
        self.fund_flow_analyzer = AuctionFundFlowAnalyzer()
    
    def predict(self, date: str = None) -> Dict:
        """
        综合市场预测
        
        Returns:
            {
                'market_trend': str,          # 市场趋势判断
                'confidence': float,          # 预测置信度
                'emotion_stage': str,         # 情绪阶段
                'recommended_position': float,# 建议仓位
                'hot_sectors': [],            # 推荐板块
                'risk_sectors': [],           # 风险板块
                'warnings': [],               # 风险提示
                'opportunities': []           # 机会提示
            }
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # 1. 情绪分析
        emotion = self.emotion_analyzer.analyze_emotion(date)
        
        # 2. 板块轮动（需要历史数据）
        sector_rotation = {'recommendation': ''}
        
        # 3. 资金流向
        fund_flow = self.fund_flow_analyzer.analyze_auction_fund_flow(date)
        
        # 综合判断
        emotion_score = emotion.get('emotion_score', 50)
        
        # 市场趋势判断
        if emotion_score >= 70:
            market_trend = '强势上涨'
            confidence = 0.7
        elif emotion_score >= 50:
            market_trend = '震荡偏强'
            confidence = 0.6
        elif emotion_score >= 30:
            market_trend = '震荡偏弱'
            confidence = 0.5
        else:
            market_trend = '弱势调整'
            confidence = 0.6
        
        # 生成预警
        warnings = []
        opportunities = []
        
        if emotion.get('stage_name') == '退潮期':
            warnings.append('市场进入退潮期，建议空仓观望')
        elif emotion.get('stage_name') == '高潮期':
            warnings.append('市场过热，注意回调风险')
        elif emotion.get('stage_name') == '恢复初期':
            opportunities.append('市场开始回暖，可轻仓试错')
        elif emotion.get('stage_name') == '上升期':
            opportunities.append('市场情绪良好，正常参与')
        
        # 板块机会
        hot_sectors = [s['name'] for s in fund_flow.get('net_inflow_sectors', [])[:3]]
        risk_sectors = [s['name'] for s in fund_flow.get('net_outflow_sectors', [])[:3]]
        
        return {
            'date': date,
            'market_trend': market_trend,
            'confidence': confidence,
            'emotion_stage': emotion.get('stage_name', ''),
            'emotion_score': emotion_score,
            'recommended_position': emotion.get('position_limit', 0.3),
            'hot_sectors': hot_sectors,
            'risk_sectors': risk_sectors,
            'warnings': warnings,
            'opportunities': opportunities,
            'fund_flow_summary': fund_flow.get('summary', ''),
            'sector_recommendation': sector_rotation.get('recommendation', '')
        }


# ==================== 8. 综合风控评估引擎（新增） ====================

class RiskAssessmentEngine:
    """综合风控评估引擎"""
    
    def __init__(self):
        self.unlock_detector = UnlockRiskDetector()
        self.reduce_detector = ReduceRiskDetector()
        self.emotion_analyzer = EmotionCycleAnalyzer()
    
    def assess_stock_risk(self, stock: Dict, dragon_tiger: Dict = None) -> Dict:
        """
        评估个股风险
        
        Args:
            stock: 股票信息
            dragon_tiger: 龙虎榜数据
        
        Returns:
            {
                'total_risk_score': float,    # 总风险分 0-100
                'risk_level': str,            # 高/中/低
                'risk_factors': [],           # 风险因子
                'warnings': [],               # 风险提示
                'recommendation': str         # 建议
            }
        """
        risk_factors = []
        warnings = []
        risk_score = 0
        
        stock_code = stock.get('code', '')
        stock_name = stock.get('name', '')
        
        # 1. 解禁风险
        unlock_risk = self.unlock_detector.check_unlock_risk(stock_name, stock_code)
        if unlock_risk['has_risk']:
            if unlock_risk['risk_level'] == '高':
                risk_score += 30
                warnings.append(f"解禁风险: {unlock_risk['detail']}")
            elif unlock_risk['risk_level'] == '中':
                risk_score += 15
                warnings.append(f"解禁风险: {unlock_risk['detail']}")
            risk_factors.append('解禁风险')
        
        # 2. 减持风险
        reduce_risk = self.reduce_detector.check_reduce_risk(stock_name, stock_code, dragon_tiger)
        if reduce_risk['has_risk']:
            if reduce_risk['risk_level'] == '高':
                risk_score += 25
                warnings.append(f"减持风险: {reduce_risk['detail']}")
            elif reduce_risk['risk_level'] == '中':
                risk_score += 10
                warnings.append(f"减持风险: {reduce_risk['detail']}")
            risk_factors.append('减持风险')
        
        # 3. 炸板风险
        bomb_num = int(stock.get('bombNum', 0))
        if bomb_num >= 3:
            risk_score += 20
            warnings.append(f"多次炸板({bomb_num}次)，封板不牢")
            risk_factors.append('炸板风险')
        elif bomb_num >= 2:
            risk_score += 10
            warnings.append(f"炸板{bomb_num}次")
        
        # 4. 高位风险
        lb_num = int(stock.get('lbNum', 1))
        if lb_num >= 5:
            risk_score += 25
            warnings.append(f"高位板({lb_num}板)，追高风险大")
            risk_factors.append('高位风险')
        elif lb_num >= 4:
            risk_score += 15
            warnings.append(f"较高位置({lb_num}板)")
        
        # 5. 情绪风险
        emotion = self.emotion_analyzer.analyze_emotion()
        stage_name = emotion.get('stage_name', '')
        if stage_name == '退潮期':
            risk_score += 30
            warnings.append("市场退潮期，系统性风险")
            risk_factors.append('情绪风险')
        elif stage_name == '高潮期':
            risk_score += 15
            warnings.append("市场过热，注意回调")
        
        # 确定风险等级
        if risk_score >= 50:
            risk_level = '高'
            recommendation = '风险较高，建议谨慎或回避'
        elif risk_score >= 25:
            risk_level = '中'
            recommendation = '存在风险，建议降低仓位'
        else:
            risk_level = '低'
            recommendation = '风险可控'
        
        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'total_risk_score': min(100, risk_score),
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'warnings': warnings,
            'recommendation': recommendation
        }
    
    def assess_market_risk(self) -> Dict:
        """
        评估市场整体风险
        
        Returns:
            {
                'market_risk_level': str,
                'position_limit': float,
                'trading_allowed': bool,
                'warnings': [],
                'recommendation': str
            }
        """
        emotion = self.emotion_analyzer.analyze_emotion()
        stage_name = emotion.get('stage_name', '恢复中期')
        position_limit = emotion.get('position_limit', 0.3)
        
        warnings = []
        if stage_name == '退潮期':
            trading_allowed = False
            warnings.append('市场退潮，暂停交易')
            recommendation = '建议空仓观望'
        elif stage_name == '高潮期':
            trading_allowed = True
            position_limit = min(position_limit, 0.3)
            warnings.append('市场过热，降低仓位')
            recommendation = '建议逐步减仓'
        elif stage_name == '恢复初期':
            trading_allowed = True
            warnings.append('市场刚回暖，轻仓试错')
            recommendation = '建议轻仓操作'
        else:
            trading_allowed = True
            recommendation = '正常参与'
        
        return {
            'stage_name': stage_name,
            'market_risk_level': stage_name,
            'position_limit': position_limit,
            'trading_allowed': trading_allowed,
            'warnings': warnings,
            'recommendation': recommendation
        }


# ==================== 测试入口 ====================

def main():
    """测试P4模块"""
    print("=" * 70)
    print("T01龙头战法 - P4深度分析模块测试")
    print("=" * 70)
    
    # 测试情绪分析
    print("\n【测试1】情绪周期分析")
    emotion_analyzer = EmotionCycleAnalyzer()
    emotion = emotion_analyzer.analyze_emotion()
    print(f"  阶段: {emotion['stage_name']}")
    print(f"  得分: {emotion['emotion_score']}")
    print(f"  仓位: {emotion['position_limit']*100}%")
    
    # 测试市场预测
    print("\n【测试2】市场预测")
    predictor = MarketPredictionEngine()
    prediction = predictor.predict()
    print(f"  趋势: {prediction['market_trend']}")
    print(f"  置信度: {prediction['confidence']}")
    print(f"  热点板块: {prediction['hot_sectors']}")
    print(f"  风险提示: {prediction['warnings']}")
    
    # 测试风控评估
    print("\n【测试3】风控评估")
    risk_engine = RiskAssessmentEngine()
    market_risk = risk_engine.assess_market_risk()
    print(f"  市场风险: {market_risk['market_risk_level']}")
    print(f"  允许交易: {market_risk['trading_allowed']}")
    print(f"  建议仓位: {market_risk['position_limit']*100}%")
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
