#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01任务 - 龙头战法 - T日晚上分析脚本 (优化版 v4 - P3高级风控)
功能：
1. 分析当日涨停股，选出前5名作为次日观察标的
2. P0优化：连板数评分、炸板次数评分、预过滤
3. P1优化：龙虎榜细化、板块强度数值化、竞价抢筹
4. P2优化：资金流入天数、涨停原因分析
5. P3优化：高级风控体系
   - 连板高度风险控制（4板降权）
   - 板块过热风险控制
   - 市场环境适配
   - 个股特有风险（解禁、减持）
   - 时间窗口风险
"""

import json
import requests
from datetime import datetime, timedelta
import os
import sys
import calendar

# 添加 scripts 目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from stockapi_client import StockAPIClient
from feishu_notifier import send_feishu_message
from T01_ai_evolution import AIEvolution
from T01_p4_modules import (
    UnlockRiskDetector, 
    ReduceRiskDetector,
    InvestorAnalyzer,
    EmotionCycleAnalyzer,
    SectorRotationAnalyzer,
    AuctionFundFlowAnalyzer,
    MarketPredictionEngine,
    RiskAssessmentEngine
)

# 配置信息
DATA_DIR = "/mnt/workspace/working/data/T01"
RESULT_FILE = os.path.join(DATA_DIR, "selected_stocks.json")
FEISHU_USER_ID = "董欣#ad16"
FEISHU_SESSION_ID = "6661ad16"

# ==================== P0优化：预过滤配置 ====================
FILTER_CONFIG = {
    'exclude_st': True,           # 排除ST股
    'exclude_new_stock': True,    # 排除新股（上市<20天）
    'exclude_high_board': True,   # 排除高位板（≥5连板）
    'exclude_multi_bomb': True,   # 排除多次炸板（≥3次）
    'high_board_threshold': 5,    # 高位板阈值
    'multi_bomb_threshold': 3,    # 多次炸板阈值
}

# ==================== P3优化：高级风控配置 ====================
P3_RISK_CONFIG = {
    # 连板高度风险
    'high_board_penalty': {
        'enabled': True,
        '4_board_multiplier': 0.8,    # 4板评分×0.8
        'warning_threshold': 4,        # 4板及以上标记预警
    },
    
    # 板块过热风险
    'sector_overheat': {
        'enabled': True,
        'consecutive_days': 3,         # 连续N日领涨视为过热
        'min_rise_pct': 5.0,           # 最小涨幅百分比
        'overheat_penalty': 0.7,       # 过热板块评分×0.7
    },
    
    # 市场环境适配
    'market_environment': {
        'enabled': True,
        'bear_market_threshold': -0.02,   # 大盘跌幅>2%视为弱势
        'bull_market_threshold': 0.02,    # 大盘涨幅>2%视为强势
        'weak_market_penalty': 0.8,       # 弱势市场评分×0.8
        'weak_market_min_score': 15,      # 弱势市场最低入围分数
    },
    
    # 时间窗口风险
    'time_window': {
        'enabled': True,
        'month_end_days': 3,            # 月末最后N天
        'quarter_end_months': [3, 6, 9, 12],  # 季末月份
        'year_end_days': 5,             # 年末最后N天
        'time_penalty': 0.9,            # 特殊时间窗口评分×0.9
    },
}

# ==================== P0优化：新权重配置 ====================
NEW_WEIGHTS = {
    'first_limit_time': 0.10,    # ↓ 首次涨停时间
    'seal_ratio': 0.08,          # ↓ 封成比
    'seal_market_cap': 0.08,     # ↓ 封单/市值
    'lb_num': 0.10,              # ↓ 连板数
    'bomb_num': 0.06,            # ↓ 炸板次数
    'dragon_tiger': 0.06,        # ↓ 龙虎榜
    'main_fund_ratio': 0.08,     # ↓ 主力资金
    'amount': 0.04,              # ↓ 成交金额
    'turnover_rate': 0.06,       # ↓ 换手率
    'volume_ratio': 0.08,        # ↓ 量比
    'hot_sector': 0.10,          # ↓ 板块强度
    'fund_flow_days': 0.04,      # ↓ 资金流入天数
    'news_sentiment': 0.06,      # ★P4新增 新闻舆情评分
}

# ==================== P4优化：新闻舆情分析配置 ====================
NEWS_ANALYSIS_CONFIG = {
    'enabled': True,
    'max_news_count': 10,         # 最多获取新闻条数
    'timeout': 15,                # 超时时间（秒）
    
    # 权威媒体列表
    'authoritative_media': [
        '财联社', '证券时报', '证券日报', '中国证券报', '上海证券报',
        '新华网', '人民网', '央视财经', '第一财经', '经济日报',
        '证监会', '交易所', '上交所', '深交所'
    ],
    
    # 正面关键词
    'positive_keywords': [
        '利好', '突破', '创新', '增长', '盈利', '订单', '中标',
        '合作', '收购', '重组', '政策支持', '行业龙头', '领先',
        '业绩大增', '扭亏', '超预期', '获批', '签约'
    ],
    
    # 负面关键词
    'negative_keywords': [
        '利空', '亏损', '下滑', '风险', '处罚', '违规', '调查',
        '减持', '质押', '诉讼', '预警', '下降', '不及预期'
    ],
}


class EveningAnalyzerV4:
    """T日晚间分析器（优化版v4 - P3高级风控 + P4深度分析）"""
    
    def __init__(self, date=None):
        self.client = StockAPIClient()
        self.ai = AIEvolution()
        self.date = date or self.client.get_today_date()
        self.weights = self._init_weights()
        self.hot_sectors = None
        self.emotion = None
        self.limit_up_stocks = None
        self.selected_stocks = []
        self.filtered_count = {'st': 0, 'new': 0, 'high_board': 0, 'multi_bomb': 0}
        
        # P3优化：新增风险统计
        self.risk_stats = {
            'high_board_penalty': 0,
            'sector_overheat': 0,
            'weak_market': False,
            'time_window_risk': False,
            'warnings': [],
        }
        
        # P3优化：大盘数据
        self.market_data = None
        self.market_trend = 'neutral'
        
        # P3优化：板块过热记录
        self.overheated_sectors = set()
        
        # P3优化：时间窗口标记
        self.time_window_flags = []
        
        # P4优化：新增分析器
        self.unlock_detector = UnlockRiskDetector()
        self.reduce_detector = ReduceRiskDetector()
        self.investor_analyzer = InvestorAnalyzer()
        self.emotion_analyzer = EmotionCycleAnalyzer()
        self.sector_rotation = SectorRotationAnalyzer()
        self.market_predictor = MarketPredictionEngine()
        self.risk_engine = RiskAssessmentEngine()
        
        # P4优化：情绪周期阶段
        self.emotion_stage = None
        self.position_limit = 0.5
        
        # P4优化：板块轮动分析结果
        self.sector_rotation_result = None
        
        # P4优化：市场预测结果
        self.market_prediction = None
        
        # P4优化：综合风控评估
        self.risk_assessment = None
    
    def _init_weights(self):
        """初始化权重（优先使用AI进化权重）"""
        ai_weights = self.ai.get_current_weights()
        weights = NEW_WEIGHTS.copy()
        for key in ai_weights:
            if key in weights:
                weights[key] = ai_weights[key]
        return weights
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
    
    def _get_hot_sectors(self):
        """获取热点板块（增强版）"""
        if self.hot_sectors is None:
            self.hot_sectors = self.client.get_hot_sectors_enhanced(self.date)
        return self.hot_sectors
    
    def _get_emotion(self):
        """获取情绪周期"""
        if self.emotion is None:
            self.emotion = self.client.get_emotional_cycle()
        return self.emotion
    
    # ==================== P3优化：高级风控功能 ====================
    
    def _check_time_window_risk(self):
        """
        P3优化：检查时间窗口风险
        
        识别月末、季末、年末等特殊时间窗口
        """
        if not P3_RISK_CONFIG['time_window']['enabled']:
            return []
        
        flags = []
        today = datetime.strptime(self.date, '%Y-%m-%d')
        
        # 获取当月最后一天
        _, last_day = calendar.monthrange(today.year, today.month)
        days_to_month_end = last_day - today.day
        
        # 月末风险
        if days_to_month_end <= P3_RISK_CONFIG['time_window']['month_end_days']:
            flags.append('月末')
        
        # 季末风险
        if today.month in P3_RISK_CONFIG['time_window']['quarter_end_months']:
            if days_to_month_end <= P3_RISK_CONFIG['time_window']['month_end_days']:
                flags.append('季末')
        
        # 年末风险
        if today.month == 12 and today.day >= (31 - P3_RISK_CONFIG['time_window']['year_end_days']):
            flags.append('年末')
        
        self.time_window_flags = flags
        if flags:
            self.risk_stats['time_window_risk'] = True
            self.risk_stats['warnings'].append(f"时间窗口风险: {', '.join(flags)}")
        
        return flags
    
    def _get_market_trend(self):
        """
        P3优化：获取大盘走势判断
        
        使用上证指数判断市场环境
        """
        if not P3_RISK_CONFIG['market_environment']['enabled']:
            return 'neutral'
        
        try:
            # 获取上证指数K线数据（需要计算日期范围）
            from datetime import datetime, timedelta
            end_date_obj = datetime.strptime(self.date, '%Y-%m-%d')
            start_date_obj = end_date_obj - timedelta(days=10)  # 多取几天确保有5个交易日
            start_date = start_date_obj.strftime('%Y-%m-%d')
            
            sh_kline = self.client.get_stock_kline('000001', start_date, self.date)
            
            if sh_kline and len(sh_kline) > 0:
                today_data = sh_kline[-1]
                yesterday_data = sh_kline[-2] if len(sh_kline) > 1 else sh_kline[0]
                
                # 计算涨跌幅
                today_close = float(today_data.get('close', 0))
                yesterday_close = float(yesterday_data.get('close', 0))
                
                if yesterday_close > 0:
                    change_pct = (today_close - yesterday_close) / yesterday_close
                    
                    if change_pct >= P3_RISK_CONFIG['market_environment']['bull_market_threshold']:
                        self.market_trend = 'bull'
                    elif change_pct <= P3_RISK_CONFIG['market_environment']['bear_market_threshold']:
                        self.market_trend = 'bear'
                        self.risk_stats['weak_market'] = True
                        self.risk_stats['warnings'].append(f"弱势市场: 大盘跌幅{abs(change_pct)*100:.2f}%")
                    else:
                        self.market_trend = 'neutral'
                
                self.market_data = {
                    'index': '000001',
                    'close': today_close,
                    'change_pct': round(change_pct * 100, 2)
                }
        except Exception as e:
            print(f"获取大盘数据失败: {e}")
        
        return self.market_trend
    
    def _detect_overheated_sectors(self):
        """
        P3优化：检测过热板块
        
        连续多日涨幅较大的板块视为过热
        """
        if not P3_RISK_CONFIG['sector_overheat']['enabled']:
            return set()
        
        hot_sectors = self._get_hot_sectors()
        if not hot_sectors:
            return set()
        
        overheated = set()
        config = P3_RISK_CONFIG['sector_overheat']
        
        # 简化判断：板块强度极高且排名TOP3视为过热
        for i, sector in enumerate(hot_sectors[:3]):
            strength = sector.get('qiangdu', 0)
            try:
                strength = float(strength)
            except:
                strength = 0
            
            # 强度超过阈值且排名靠前
            if strength > 80000:  # 超高热度
                sector_name = sector.get('bkName', '')
                overheated.add(sector_name)
                self.risk_stats['warnings'].append(f"板块过热: {sector_name} (强度:{strength:.0f})")
        
        self.overheated_sectors = overheated
        self.risk_stats['sector_overheat'] = len(overheated)
        
        return overheated
    
    def _apply_p3_risk_adjustment(self, stock_data, score, details):
        """
        P3优化：应用高级风控调整
        
        Returns:
            tuple: (调整后分数, 风险标记列表)
        """
        risk_flags = []
        adjusted_score = score
        config = P3_RISK_CONFIG
        
        # 1. 连板高度风险控制
        if config['high_board_penalty']['enabled']:
            lb_num = details.get('lb_num', 1)
            if lb_num >= config['high_board_penalty']['warning_threshold']:
                # 4板降权
                adjusted_score *= config['high_board_penalty']['4_board_multiplier']
                risk_flags.append(f"高位板降权({lb_num}板×0.8)")
                self.risk_stats['high_board_penalty'] += 1
        
        # 2. 板块过热风险控制
        if config['sector_overheat']['enabled'] and self.overheated_sectors:
            sector_name = details.get('hot_sector_name', '')
            if sector_name in self.overheated_sectors:
                adjusted_score *= config['sector_overheat']['overheat_penalty']
                risk_flags.append(f"过热板块降权(×0.7)")
        
        # 3. 市场环境适配
        if config['market_environment']['enabled'] and self.market_trend == 'bear':
            adjusted_score *= config['market_environment']['weak_market_penalty']
            risk_flags.append("弱势市场降权(×0.8)")
        
        # 4. 时间窗口风险
        if config['time_window']['enabled'] and self.time_window_flags:
            adjusted_score *= config['time_window']['time_penalty']
            risk_flags.append(f"时间窗口降权(×0.9)")
        
        return round(adjusted_score, 2), risk_flags
    
    def _apply_weak_market_filter(self, score):
        """
        P3优化：弱势市场过滤
        
        在弱势市场中提高入围门槛
        """
        if not P3_RISK_CONFIG['market_environment']['enabled']:
            return True
        
        if self.market_trend == 'bear':
            min_score = P3_RISK_CONFIG['market_environment']['weak_market_min_score']
            return score >= min_score
        
        return True
    
    # ==================== P0优化：预过滤功能 ====================
    
    def _is_st_stock(self, stock_data):
        """判断是否为ST股"""
        name = stock_data.get('name', '')
        if 'ST' in name or 'st' in name:
            return True
        return False
    
    def _is_new_stock(self, stock_data):
        """判断是否为新股（上市不足20天）"""
        plate_reason = stock_data.get('plate_reason', '')
        if '次新' in plate_reason or '新股' in plate_reason:
            return True
        return False
    
    def _is_high_board(self, stock_data):
        """判断是否为高位板"""
        lb_num = stock_data.get('lbNum', 1)
        try:
            lb_num = int(lb_num)
        except:
            lb_num = 1
        return lb_num >= FILTER_CONFIG['high_board_threshold']
    
    def _is_multi_bomb(self, stock_data):
        """判断是否多次炸板"""
        bomb_num = stock_data.get('bombNum', 0)
        try:
            bomb_num = int(bomb_num)
        except:
            bomb_num = 0
        return bomb_num >= FILTER_CONFIG['multi_bomb_threshold']
    
    def _pre_filter_stock(self, stock_data):
        """预过滤股票（含P4新增风险检测）"""
        # 1. 排除ST股
        if FILTER_CONFIG['exclude_st'] and self._is_st_stock(stock_data):
            self.filtered_count['st'] += 1
            return False, 'ST股'
        
        # 2. 排除新股
        if FILTER_CONFIG['exclude_new_stock'] and self._is_new_stock(stock_data):
            self.filtered_count['new'] += 1
            return False, '新股'
        
        # 3. 排除高位板
        if FILTER_CONFIG['exclude_high_board'] and self._is_high_board(stock_data):
            self.filtered_count['high_board'] += 1
            return False, f"高位板({stock_data.get('lbNum', 1)}连板)"
        
        # 4. 排除多次炸板
        if FILTER_CONFIG['exclude_multi_bomb'] and self._is_multi_bomb(stock_data):
            self.filtered_count['multi_bomb'] += 1
            return False, f"多次炸板({stock_data.get('bombNum', 0)}次)"
        
        # 5. ★P4新增：排除解禁高风险股
        stock_name = stock_data.get('name', '')
        stock_code = stock_data.get('code', '')
        unlock_risk = self.unlock_detector.check_unlock_risk(stock_name, stock_code)
        if unlock_risk.get('risk_level') == '高':
            return False, f"解禁风险({unlock_risk.get('unlock_ratio', 0)}%)"
        
        # 6. ★P4新增：排除减持高风险股
        reduce_risk = self.reduce_detector.check_reduce_risk(stock_name, stock_code)
        if reduce_risk.get('risk_level') == '高':
            return False, f"减持风险({reduce_risk.get('reduce_ratio', 0)}%)"
        
        return True, None
    
    # ==================== P0-P2优化：评分指标 ====================
    
    def _calc_lb_num_score(self, lb_num):
        """计算连板数评分"""
        try:
            lb_num = int(lb_num)
        except:
            lb_num = 1
        
        if lb_num >= 5:
            return 0
        elif lb_num >= 3:
            return 15
        elif lb_num == 2:
            return 20
        else:
            return 10
    
    def _calc_bomb_num_score(self, bomb_num):
        """计算炸板次数评分"""
        try:
            bomb_num = int(bomb_num)
        except:
            bomb_num = 0
        
        if bomb_num >= 3:
            return 0
        elif bomb_num == 2:
            return 2
        elif bomb_num == 1:
            return 5
        else:
            return 10
    
    def _calc_sector_strength_score(self, sector_data):
        """计算板块强度评分"""
        if not sector_data:
            return 0
        
        strength = sector_data.get('qiangdu', 0)
        try:
            strength = float(strength)
        except:
            return 0
        
        if strength > 50000:
            return 15
        elif strength > 30000:
            return 12
        elif strength > 20000:
            return 10
        elif strength > 10000:
            return 5
        else:
            return 0
    
    def _calc_fund_flow_score(self, sector_data):
        """计算资金流入天数评分"""
        if not sector_data:
            return 0
        
        jlrts = sector_data.get('jlrts', 0)
        try:
            jlrts = int(jlrts)
        except:
            return 0
        
        if jlrts >= 5:
            return 10
        elif jlrts >= 3:
            return 8
        elif jlrts >= 1:
            return 5
        else:
            return 0
    
    def _analyze_plate_reason(self, stock_data):
        """分析涨停原因"""
        plate_reason = stock_data.get('plate_reason', '')
        plate_name = stock_data.get('plate_name', '')
        stock_reason = stock_data.get('stock_reason', '')
        
        all_reasons = []
        if plate_reason:
            all_reasons.append(plate_reason)
        if plate_name:
            all_reasons.append(plate_name)
        if stock_reason:
            all_reasons.append(stock_reason)
        
        reason_text = ' '.join(all_reasons)
        
        if not reason_text:
            return {'reason_text': '', 'reason_score': 0, 'reason_type': '未知'}
        
        hard_core_keywords = {
            '业绩': 15, '预增': 12, '扭亏': 12, '利润': 10, '年报': 8, '季报': 8,
            '政策': 10, '利好': 8, '扶持': 8, '补贴': 7, '重组': 10, '并购': 10, '收购': 8,
            '突破': 8, '技术': 7, '专利': 6, '研发': 5,
            '订单': 7, '中标': 7, '合作': 6, '签约': 5,
            'AI': 5, '人工智能': 5, '芯片': 5, '新能源': 5, '光伏': 4, '锂电': 4,
        }
        
        hype_keywords = ['炒作', '蹭热点', '概念']
        
        score = 0
        matched_reasons = []
        reason_lower = reason_text.lower()
        
        for keyword, keyword_score in hard_core_keywords.items():
            if keyword.lower() in reason_lower:
                score += keyword_score
                matched_reasons.append(keyword)
        
        for hype in hype_keywords:
            if hype in reason_text:
                score -= 5
        
        if score >= 12:
            reason_type = '硬核逻辑'
        elif score >= 6:
            reason_type = '中等逻辑'
        elif score > 0:
            reason_type = '一般逻辑'
        else:
            reason_type = '纯概念炒作'
        
        score = min(score, 15)
        
        return {
            'reason_text': reason_text[:100] if reason_text else '',
            'reason_score': score,
            'reason_type': reason_type,
            'matched_keywords': matched_reasons
        }
    
    # ==================== P4优化：新闻舆情分析 ====================
    
    def _analyze_news_sentiment(self, stock_name, stock_code, plate_reason_keywords):
        """
        P4优化：分析新闻舆情（融合方案A+B）
        
        方案A：新闻数量统计（轻量级）
        方案B：情感分析 + 时效性 + 权威性（深度分析）
        
        Args:
            stock_name: 股票名称
            stock_code: 股票代码
            plate_reason_keywords: 涨停原因关键词列表
        
        Returns:
            dict: 新闻舆情分析结果
        """
        if not NEWS_ANALYSIS_CONFIG['enabled']:
            return {
                'news_count': 0,
                'news_score': 0,
                'sentiment': '未知',
                'timeliness': 0,
                'authority': 0,
                'news_list': []
            }
        
        result = {
            'news_count': 0,
            'news_score': 0,
            'sentiment': '中性',
            'timeliness': 0,
            'authority': 0,
            'news_list': [],
            'positive_count': 0,
            'negative_count': 0,
            'today_news_count': 0
        }
        
        try:
            # 构建搜索关键词
            search_query = f"{stock_name}"
            if plate_reason_keywords:
                # 取前2个关键词加入搜索
                search_query += " " + " ".join(plate_reason_keywords[:2])
            
            # 调用搜索API
            from tavily import TavilyClient
            client = TavilyClient()
            
            search_result = client.search(
                query=search_query,
                max_results=NEWS_ANALYSIS_CONFIG['max_news_count'],
                search_depth='basic'
            )
            
            if not search_result or 'results' not in search_result:
                return result
            
            news_list = search_result.get('results', [])
            result['news_count'] = len(news_list)
            
            if not news_list:
                return result
            
            # 分析每条新闻
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            sentiment_score = 0
            timeliness_score = 0
            authority_score = 0
            
            analyzed_news = []
            
            for news in news_list:
                news_title = news.get('title', '')
                news_content = news.get('content', '')
                news_url = news.get('url', '')
                news_date = news.get('published_date', '')
                
                # 合并标题和内容分析
                full_text = f"{news_title} {news_content}".lower()
                
                # 1. 情感分析
                positive_count = 0
                negative_count = 0
                
                for keyword in NEWS_ANALYSIS_CONFIG['positive_keywords']:
                    if keyword in full_text:
                        positive_count += 1
                
                for keyword in NEWS_ANALYSIS_CONFIG['negative_keywords']:
                    if keyword in full_text:
                        negative_count += 1
                
                news_sentiment = '中性'
                if positive_count > negative_count:
                    news_sentiment = '正面'
                    sentiment_score += 10
                    result['positive_count'] += 1
                elif negative_count > positive_count:
                    news_sentiment = '负面'
                    result['negative_count'] += 1
                else:
                    sentiment_score += 5
                
                # 2. 时效性分析
                if today in str(news_date) or '小时前' in str(news_date) or '分钟前' in str(news_date):
                    timeliness_score += 10
                    result['today_news_count'] += 1
                elif yesterday in str(news_date) or '昨天' in str(news_date) or '1天前' in str(news_date):
                    timeliness_score += 6
                else:
                    timeliness_score += 2
                
                # 3. 权威性分析
                is_authoritative = False
                for media in NEWS_ANALYSIS_CONFIG['authoritative_media']:
                    if media in news_title or media in news_url:
                        is_authoritative = True
                        authority_score += 5
                        break
                
                if not is_authoritative:
                    authority_score += 1
                
                analyzed_news.append({
                    'title': news_title[:50] if news_title else '',
                    'sentiment': news_sentiment,
                    'is_authoritative': is_authoritative,
                    'date': news_date
                })
            
            result['news_list'] = analyzed_news[:5]  # 只保存前5条
            
            # 计算平均分
            news_count = len(news_list)
            result['timeliness'] = round(timeliness_score / news_count, 1) if news_count > 0 else 0
            result['authority'] = round(authority_score / news_count, 1) if news_count > 0 else 0
            
            # 计算情感得分
            avg_sentiment = sentiment_score / news_count if news_count > 0 else 5
            if avg_sentiment >= 8:
                result['sentiment'] = '正面'
            elif avg_sentiment >= 4:
                result['sentiment'] = '中性'
            else:
                result['sentiment'] = '负面'
            
            # 计算综合新闻评分
            # 新闻数量评分（满分15分）
            if news_count >= 10:
                count_score = 15
            elif news_count >= 5:
                count_score = 12
            elif news_count >= 2:
                count_score = 8
            elif news_count >= 1:
                count_score = 4
            else:
                count_score = 0
            
            # 时效性评分（满分10分）
            timeliness_final = min(result['timeliness'], 10)
            
            # 情感评分（满分10分）
            if result['sentiment'] == '正面':
                sentiment_final = 10
            elif result['sentiment'] == '中性':
                sentiment_final = 5
            else:
                sentiment_final = 0
            
            # 权威性评分（满分5分）
            authority_final = min(result['authority'], 5)
            
            # 综合评分（加权）
            # 数量40% + 时效性25% + 情感20% + 权威性15%
            total_score = (
                count_score * 0.40 +
                timeliness_final * 0.25 +
                sentiment_final * 0.20 +
                authority_final * 0.15
            )
            
            result['news_score'] = round(total_score, 2)
            result['count_score'] = count_score
            result['timeliness_final'] = timeliness_final
            result['sentiment_final'] = sentiment_final
            result['authority_final'] = authority_final
            
        except Exception as e:
            print(f"    新闻舆情分析失败 [{stock_name}]: {e}")
        
        return result
    
    def _find_matching_sector(self, stock_data):
        """查找股票对应的热点板块"""
        stock_code = stock_data.get('code', '')
        plate_name = stock_data.get('plateName', '')
        gl = stock_data.get('gl', '')
        industry = stock_data.get('industry', '')
        
        hot_sectors = self._get_hot_sectors()
        
        if not hot_sectors:
            return None, None, None
        
        stock_tags = set()
        if plate_name:
            stock_tags.add(plate_name.lower())
        if gl:
            for tag in gl.split(','):
                stock_tags.add(tag.strip().lower())
        if industry:
            stock_tags.add(industry.lower())
        
        best_match = None
        best_rank = 0
        best_sector_data = None
        
        for i, sector in enumerate(hot_sectors[:15], 1):
            sector_name = sector.get('bkName', '').lower()
            
            for tag in stock_tags:
                if sector_name in tag or tag in sector_name:
                    if best_rank == 0 or i < best_rank:
                        best_rank = i
                        best_match = sector.get('bkName', '')
                        best_sector_data = sector
                    break
        
        return best_match, best_rank, best_sector_data
    
    def calculate_score(self, stock_data):
        """计算股票的综合评分（优化版v4）"""
        score = 0.0
        details = {}
        
        try:
            stock_code = stock_data.get('code', '')
            stock_name = stock_data.get('name', '')
            
            # ========== 1. 首次涨停时间 ==========
            first_ceiling_time = stock_data.get('firstCeilingTime', '150000')
            time_minutes = self.client.parse_ceiling_time(first_ceiling_time)
            
            if 570 <= time_minutes <= 600:
                time_score = 20
            elif 600 < time_minutes <= 630:
                time_score = 15
            elif 630 < time_minutes <= 660:
                time_score = 10
            elif 660 < time_minutes <= 720:
                time_score = 5
            else:
                time_score = 0
            
            time_weighted = time_score * self.weights.get('first_limit_time', 0.12) / 0.20
            score += time_weighted
            details['first_ceiling_time'] = first_ceiling_time
            details['first_ceiling_time_score'] = round(time_weighted, 2)
            
            # ========== 2. 封成比 ==========
            seal_ratio = self.client.calculate_seal_ratio(stock_data)
            if seal_ratio >= 10:
                seal_score = 15
            elif seal_ratio >= 5:
                seal_score = 10
            elif seal_ratio >= 3:
                seal_score = 5
            else:
                seal_score = 0
            
            seal_weighted = seal_score * self.weights.get('seal_ratio', 0.10) / 0.15
            score += seal_weighted
            details['seal_ratio'] = round(seal_ratio, 2)
            details['seal_ratio_score'] = round(seal_weighted, 2)
            
            # ========== 3. 封单/流通市值 ==========
            seal_to_market_cap = self.client.calculate_seal_to_market_cap(stock_data)
            if seal_to_market_cap >= 0.05:
                cap_score = 15
            elif seal_to_market_cap >= 0.03:
                cap_score = 10
            elif seal_to_market_cap >= 0.01:
                cap_score = 5
            else:
                cap_score = 0
            
            cap_weighted = cap_score * self.weights.get('seal_market_cap', 0.10) / 0.15
            score += cap_weighted
            details['seal_to_market_cap'] = round(seal_to_market_cap, 4)
            details['seal_to_market_cap_score'] = round(cap_weighted, 2)
            
            # ========== 4. 连板数 ==========
            lb_num = stock_data.get('lbNum', 1)
            lb_score = self._calc_lb_num_score(lb_num)
            lb_weighted = lb_score * self.weights.get('lb_num', 0.12) / 0.20
            score += lb_weighted
            details['lb_num'] = lb_num
            details['lb_num_score'] = round(lb_weighted, 2)
            
            # ========== 5. 炸板次数 ==========
            bomb_num = stock_data.get('bombNum', 0)
            bomb_score = self._calc_bomb_num_score(bomb_num)
            bomb_weighted = bomb_score * self.weights.get('bomb_num', 0.08) / 0.10
            score += bomb_weighted
            details['bomb_num'] = bomb_num
            details['bomb_num_score'] = round(bomb_weighted, 2)
            
            # ========== 6. 龙虎榜（含P4游资画像分析）==========
            dragon_detail = self.client.get_dragon_tiger_detail(stock_code, self.date)
            
            if dragon_detail:
                buy_amount = 0
                sell_amount = 0
                try:
                    buy_amount = float(dragon_detail.get('buyAmount', 0))
                    sell_amount = float(dragon_detail.get('sellAmount', 0))
                except:
                    pass
                
                net_buy = buy_amount - sell_amount
                
                if net_buy > 5000:
                    dragon_score = 15
                elif net_buy > 2000:
                    dragon_score = 12
                elif net_buy > 0:
                    dragon_score = 10
                elif net_buy > -2000:
                    dragon_score = 5
                else:
                    dragon_score = 2
                
                details['dragon_tiger'] = True
                details['dragon_tiger_data'] = dragon_detail
                details['dragon_net_buy'] = round(net_buy, 2)
                
                # ★P4新增：游资画像分析
                investor_analysis = self.investor_analyzer.analyze_dragon_tiger(dragon_detail)
                details['investor_analysis'] = investor_analysis
                
                if investor_analysis.get('has_famous_investor'):
                    # 游资加分
                    investor_bonus = investor_analysis.get('total_score_bonus', 0)
                    dragon_score += investor_bonus
                    details['famous_investors'] = investor_analysis.get('investors', [])
                    details['investor_recommendation'] = investor_analysis.get('recommendation', '')
                else:
                    details['famous_investors'] = []
                    details['investor_recommendation'] = ''
            else:
                dragon_score = 0
                details['dragon_tiger'] = False
                details['dragon_net_buy'] = 0
                details['investor_analysis'] = {}
                details['famous_investors'] = []
                details['investor_recommendation'] = ''
            
            dragon_weighted = dragon_score * self.weights.get('dragon_tiger', 0.06) / 0.15
            score += dragon_weighted
            details['dragon_tiger_score'] = round(dragon_weighted, 2)
            
            # ========== 7. 主力资金净占比 ==========
            capital_flow = self.client.get_stock_capital_flow(stock_code, self.date)
            main_net_ratio = 0
            if capital_flow:
                try:
                    main_net_ratio = float(capital_flow.get('mainAmountPercentage', 0))
                except:
                    pass
            
            if main_net_ratio >= 10:
                fund_score = 10
            elif main_net_ratio >= 5:
                fund_score = 7
            elif main_net_ratio >= 0:
                fund_score = 3
            else:
                fund_score = 0
            
            fund_weighted = fund_score * self.weights.get('main_fund_ratio', 0.10) / 0.10
            score += fund_weighted
            details['main_net_ratio'] = round(main_net_ratio, 2)
            details['main_net_ratio_score'] = round(fund_weighted, 2)
            
            # ========== 8. 成交金额 ==========
            amount = 0
            try:
                amount = float(stock_data.get('amount', 0)) / 10000
            except:
                pass
            
            if 50000 <= amount <= 200000:
                amount_score = 10
            elif 20000 <= amount <= 500000:
                amount_score = 5
            else:
                amount_score = 0
            
            amount_weighted = amount_score * self.weights.get('amount', 0.05) / 0.10
            score += amount_weighted
            details['amount'] = round(amount, 0)
            details['amount_score'] = round(amount_weighted, 2)
            
            # ========== 9. 换手率 ==========
            turnover_rate = 0
            try:
                turnover_rate = float(stock_data.get('turnoverRatio', 0))
            except:
                pass
            
            if 5 <= turnover_rate <= 15:
                turnover_score = 10
            elif 3 <= turnover_rate <= 20:
                turnover_score = 5
            else:
                turnover_score = 0
            
            turnover_weighted = turnover_score * self.weights.get('turnover_rate', 0.08) / 0.10
            score += turnover_weighted
            details['turnover_rate'] = round(turnover_rate, 2)
            details['turnover_rate_score'] = round(turnover_weighted, 2)
            
            # ========== 10. 量比 ==========
            volume_ratio = self.client.get_volume_ratio(stock_code, self.date)
            if volume_ratio >= 5:
                vol_score = 10
            elif volume_ratio >= 3:
                vol_score = 8
            elif volume_ratio >= 2:
                vol_score = 5
            elif volume_ratio >= 1.5:
                vol_score = 3
            else:
                vol_score = 0
            
            vol_weighted = vol_score * self.weights.get('volume_ratio', 0.10) / 0.10
            score += vol_weighted
            details['volume_ratio'] = round(volume_ratio, 2)
            details['volume_ratio_score'] = round(vol_weighted, 2)
            
            # ========== 11. 板块强度 ==========
            hot_sector_name, hot_rank, sector_data = self._find_matching_sector(stock_data)
            
            if sector_data:
                sector_strength_score = self._calc_sector_strength_score(sector_data)
                hot_score = max(sector_strength_score, 11 - hot_rank if hot_rank else 0)
            else:
                hot_score = 0
                sector_strength_score = 0
            
            hot_weighted = hot_score * self.weights.get('hot_sector', 0.12) / 0.15
            score += hot_weighted
            details['hot_sector_name'] = hot_sector_name
            details['hot_sector_rank'] = hot_rank
            details['sector_strength'] = sector_data.get('qiangdu', 0) if sector_data else 0
            details['hot_sector_score'] = round(hot_weighted, 2)
            
            # ========== 12. 资金流入天数 ==========
            fund_flow_score = self._calc_fund_flow_score(sector_data)
            fund_flow_weighted = fund_flow_score * self.weights.get('fund_flow_days', 0.05) / 0.10
            score += fund_flow_weighted
            details['fund_flow_days'] = sector_data.get('jlrts', 0) if sector_data else 0
            details['fund_flow_days_score'] = round(fund_flow_weighted, 2)
            
            # ========== 13. 涨停原因分析 ==========
            plate_analysis = self._analyze_plate_reason(stock_data)
            plate_reason_score = plate_analysis['reason_score']
            plate_reason_weighted = plate_reason_score * 0.03
            score += plate_reason_weighted
            details['plate_reason'] = plate_analysis['reason_text']
            details['plate_reason_type'] = plate_analysis['reason_type']
            details['plate_reason_score'] = round(plate_reason_weighted, 2)
            details['plate_reason_keywords'] = plate_analysis.get('matched_keywords', [])
            
            # ========== 14. 新闻舆情分析 ★P4新增 ==========
            plate_keywords = plate_analysis.get('matched_keywords', [])
            news_analysis = self._analyze_news_sentiment(stock_name, stock_code, plate_keywords)
            
            news_score = news_analysis.get('news_score', 0)
            news_weighted = news_score * self.weights.get('news_sentiment', 0.06) / 10
            score += news_weighted
            
            details['news_count'] = news_analysis.get('news_count', 0)
            details['news_score'] = round(news_score, 2)
            details['news_weighted_score'] = round(news_weighted, 2)
            details['news_sentiment'] = news_analysis.get('sentiment', '未知')
            details['news_timeliness'] = news_analysis.get('timeliness', 0)
            details['news_authority'] = news_analysis.get('authority', 0)
            details['today_news_count'] = news_analysis.get('today_news_count', 0)
            details['positive_news_count'] = news_analysis.get('positive_count', 0)
            details['news_list'] = news_analysis.get('news_list', [])
            
            # 汇总原始分数
            details['raw_score'] = round(score, 2)
            details['stock_name'] = stock_name
            
        except Exception as e:
            print(f"计算评分时出错: {e}")
            import traceback
            traceback.print_exc()
            return (stock_data.get('code', ''), 0, {})
        
        return (stock_data.get('code', ''), round(score, 2), details)
    
    def select_top_stocks(self, stocks, top_n=5):
        """选出评分最高的前N名股票（含P3风控）"""
        scored_stocks = []
        filtered_out = []
        
        print(f"\n【预过滤】开始...")
        
        for stock in stocks:
            # P0优化：预过滤
            passed, filter_reason = self._pre_filter_stock(stock)
            
            if not passed:
                filtered_out.append({
                    'code': stock.get('code'),
                    'name': stock.get('name'),
                    'reason': filter_reason
                })
                continue
            
            # 计算评分
            code, score, details = self.calculate_score(stock)
            if score <= 0:
                continue
            
            # P3优化：应用风险调整
            adjusted_score, risk_flags = self._apply_p3_risk_adjustment(stock, score, details)
            
            # P3优化：弱势市场过滤
            if not self._apply_weak_market_filter(adjusted_score):
                filtered_out.append({
                    'code': code,
                    'name': stock.get('name', ''),
                    'reason': f"弱势市场过滤(分数{adjusted_score:.2f}<{P3_RISK_CONFIG['market_environment']['weak_market_min_score']})"
                })
                continue
            
            scored_stocks.append({
                'code': code,
                'name': stock.get('name', ''),
                'score': adjusted_score,
                'raw_score': score,
                'details': details,
                'risk_flags': risk_flags,
                'raw_data': stock
            })
        
        # 打印过滤统计
        print(f"  过滤掉 {len(filtered_out)} 只股票:")
        print(f"    - ST股: {self.filtered_count['st']} 只")
        print(f"    - 新股: {self.filtered_count['new']} 只")
        print(f"    - 高位板(≥5板): {self.filtered_count['high_board']} 只")
        print(f"    - 多次炸板(≥3次): {self.filtered_count['multi_bomb']} 只")
        print(f"  剩余 {len(scored_stocks)} 只股票参与评分")
        
        # 按调整后评分降序排序
        scored_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_stocks[:top_n]
    
    def save_results(self):
        """保存选出的股票到JSON文件"""
        self._ensure_data_dir()
        
        result_data = {
            'date': self.date,
            'version': 'v4',
            'selected_count': len(self.selected_stocks),
            'stocks': self.selected_stocks,
            'weights': self.weights,
            'emotion': self.emotion,
            'hot_sectors': self.hot_sectors[:10] if self.hot_sectors else [],
            'filter_stats': self.filtered_count,
            'risk_stats': self.risk_stats,
            'market_data': self.market_data,
            'overheated_sectors': list(self.overheated_sectors),
            'time_window_flags': self.time_window_flags,
            # ★P4新增
            'emotion_stage': self.emotion_stage,
            'position_limit': self.position_limit,
            'sector_rotation': self.sector_rotation_result,
        }
        
        with open(RESULT_FILE, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到: {RESULT_FILE}")
    
    def run_full_analysis(self):
        """运行完整分析流程"""
        print("=" * 70)
        print(f"T01龙头战法 - T日分析 (P4深度分析版) - {self.date}")
        print("=" * 70)
        
        # 判断是否为交易日
        if not self.client.get_trading_day(self.date):
            print(f"\n⚠️ {self.date} 不是交易日，跳过晚间选股")
            print("  等待下一个交易日执行")
            return None
        
        # ========== P3优化：风险预检 ==========
        print(f"\n【P3风控】风险预检...")
        
        # 检查时间窗口风险
        self._check_time_window_risk()
        if self.time_window_flags:
            print(f"  ⚠️ 时间窗口风险: {', '.join(self.time_window_flags)}")
        
        # 获取大盘走势
        self._get_market_trend()
        if self.market_data:
            print(f"  大盘走势: 上证指数 {self.market_data['close']:.2f} ({self.market_data['change_pct']:+.2f}%)")
            if self.market_trend == 'bear':
                print(f"  ⚠️ 弱势市场模式: 启用降权保护")
        
        # 获取涨停股票
        print(f"\n【步骤1】获取涨停股票...")
        self.limit_up_stocks = self.client.get_limit_up_stocks(self.date)
        
        if not self.limit_up_stocks:
            print("未获取到涨停股票数据")
            return None
        
        print(f"获取到 {len(self.limit_up_stocks)} 只涨停股票")
        
        # 获取情绪周期
        print(f"\n【步骤2】获取情绪周期...")
        self._get_emotion()
        
        # ★P4新增：情绪周期细化分析
        print(f"\n【P4分析】情绪周期细化...")
        self.emotion_stage = self.emotion_analyzer.analyze(self.emotion)
        self.position_limit = self.emotion_stage.get('position_limit', 0.5)
        stage_name = self.emotion_stage.get('stage_name', '恢复中期')
        print(f"  当前阶段: {stage_name}")
        print(f"  建议仓位: {self.position_limit*100:.0f}%")
        print(f"  {self.emotion_stage.get('description', '')}")
        
        # 获取热点板块
        print(f"\n【步骤3】获取热点板块...")
        self._get_hot_sectors()
        if self.hot_sectors:
            print(f"获取到 {len(self.hot_sectors)} 个热点板块")
        
        # P3优化：检测过热板块
        print(f"\n【P3风控】检测过热板块...")
        self._detect_overheated_sectors()
        if self.overheated_sectors:
            print(f"  ⚠️ 过热板块: {', '.join(self.overheated_sectors)}")
        
        # ★P4新增：板块轮动预测
        print(f"\n【P4分析】板块轮动预测...")
        self.sector_rotation_result = self.sector_rotation.update_and_analyze(self.date, self.hot_sectors or [])
        if self.sector_rotation_result.get('recommendation'):
            print(f"  {self.sector_rotation_result['recommendation']}")
        
        # 计算评分并选出前5名
        print(f"\n【步骤4】评分选股...")
        self.selected_stocks = self.select_top_stocks(self.limit_up_stocks, top_n=5)
        
        if not self.selected_stocks:
            print("没有符合条件的股票")
            return None
        
        # 打印结果
        print(f"\n" + "=" * 70)
        print(f"【选股结果】选出 {len(self.selected_stocks)} 只股票:")
        print("=" * 70)
        
        for i, stock in enumerate(self.selected_stocks, 1):
            d = stock['details']
            rf = stock.get('risk_flags', [])
            
            # 显示原始分数和调整后分数
            score_display = f"{stock['score']:.2f}"
            if stock['score'] != stock.get('raw_score', stock['score']):
                score_display += f" (原{stock['raw_score']:.2f})"
            
            print(f"\n{i}. {stock['name']}({stock['code']}) - 总分: {score_display}")
            print(f"   ├─ 连板数: {d.get('lb_num', 1)}板 ({d.get('lb_num_score', 0):.2f}分)")
            print(f"   ├─ 炸板次数: {d.get('bomb_num', 0)}次 ({d.get('bomb_num_score', 0):.2f}分)")
            print(f"   ├─ 首次封板: {d.get('first_ceiling_time', '')} ({d.get('first_ceiling_time_score', 0):.2f}分)")
            print(f"   ├─ 封成比: {d.get('seal_ratio', 0):.2f} ({d.get('seal_ratio_score', 0):.2f}分)")
            print(f"   ├─ 热点板块: {d.get('hot_sector_name', '无')} ({d.get('hot_sector_score', 0):.2f}分)")
            print(f"   ├─ 资金流入: {d.get('fund_flow_days', 0)}天 ({d.get('fund_flow_days_score', 0):.2f}分)")
            print(f"   ├─ 主力资金: {d.get('main_net_ratio', 0):.2f}% ({d.get('main_net_ratio_score', 0):.2f}分)")
            print(f"   ├─ 龙虎榜: {'有' if d.get('dragon_tiger') else '无'} ({d.get('dragon_tiger_score', 0):.2f}分)")
            
            # ★P4新增：显示游资信息
            famous_investors = d.get('famous_investors', [])
            if famous_investors:
                investor_names = [inv['name'] for inv in famous_investors[:3]]
                investor_str = '、'.join(investor_names)
                print(f"   ├─ 知名游资: {investor_str}")
            
            reason_type = d.get('plate_reason_type', '未知')
            reason_score = d.get('plate_reason_score', 0)
            print(f"   ├─ 涨停逻辑: {reason_type} ({reason_score:.2f}分)")
            
            # P4优化：显示新闻舆情
            news_count = d.get('news_count', 0)
            news_sentiment = d.get('news_sentiment', '未知')
            today_news = d.get('today_news_count', 0)
            if news_count > 0:
                sentiment_icon = '📈' if news_sentiment == '正面' else ('📉' if news_sentiment == '负面' else '📊')
                today_icon = '🔥' if today_news > 0 else ''
                print(f"   ├─ 新闻舆情: {news_count}条 {sentiment_icon} {news_sentiment} {today_icon}(今日{today_news}条)")
            else:
                print(f"   ├─ 新闻舆情: 暂无相关新闻")
            
            # P3优化：显示风险标记
            if rf:
                print(f"   └─ ⚠️ 风险标记: {', '.join(rf)}")
            else:
                print(f"   └─ 风险标记: 无")
        
        # P3优化：打印风险汇总
        if self.risk_stats['warnings']:
            print(f"\n" + "=" * 70)
            print(f"【P3风控预警】")
            for warning in self.risk_stats['warnings']:
                print(f"  ⚠️ {warning}")
        
        # 保存结果
        self.save_results()
        
        return {
            'date': self.date,
            'top_stocks': self.selected_stocks,
            'emotion': self.emotion,
            'hot_sectors': self.hot_sectors[:10] if self.hot_sectors else [],
            'limit_up_stocks': self.limit_up_stocks,
            'filter_stats': self.filtered_count,
            'risk_stats': self.risk_stats,
            'market_data': self.market_data,
        }


def main():
    """主函数"""
    analyzer = EveningAnalyzerV4()
    result = analyzer.run_full_analysis()
    
    if result:
        print("\n" + "=" * 70)
        print("分析完成!")
        print("=" * 70)


if __name__ == "__main__":
    main()
