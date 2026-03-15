#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - T+1日竞价分析脚本（P4深度分析版）
功能：
1. 获取T日选出的股票
2. 调用增强版竞价API获取实时竞价数据
3. 竞价抢筹数据分析
4. P3高级风控：连板高度风险、板块过热风险、市场环境适配、时间窗口风险
5. P4深度分析：情绪周期细化、板块轮动预测
6. 根据竞价表现和风控重新评分排序
7. 给出最终买入建议
"""

import json
import os
import sys
from datetime import datetime
import calendar

sys.path.insert(0, '/mnt/workspace/working/scripts')

from stockapi_client import StockAPIClient
from T01_risk_controller import RiskController
from feishu_notifier import FeishuNotifier
from T01_p4_modules import EmotionCycleAnalyzer, SectorRotationAnalyzer, AuctionFundFlowAnalyzer

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
RESULT_FILE = os.path.join(DATA_BASE_DIR, "selected_stocks.json")
AUCTION_RESULT_FILE = os.path.join(DATA_BASE_DIR, "auction_result.json")

# ==================== P3优化：高级风控配置 ====================
P3_RISK_CONFIG = {
    # 连板高度风险
    'high_board_penalty': {
        'enabled': True,
        '4_board_multiplier': 0.8,
        'warning_threshold': 4,
    },
    
    # 板块过热风险
    'sector_overheat': {
        'enabled': True,
        'overheat_threshold': 80000,  # 竞价板块强度阈值
        'overheat_penalty': 0.7,
    },
    
    # 市场环境适配
    'market_environment': {
        'enabled': True,
        'bear_market_threshold': -0.02,
        'bull_market_threshold': 0.02,
        'weak_market_penalty': 0.8,
        'weak_market_min_score': 3.0,  # 竞价最低入围分数
    },
    
    # 时间窗口风险
    'time_window': {
        'enabled': True,
        'month_end_days': 3,
        'quarter_end_months': [3, 6, 9, 12],
        'year_end_days': 5,
        'time_penalty': 0.9,
    },
    
    # 竞价风控
    'auction_risk': {
        'enabled': True,                 # 启用竞价风控
        'high_open_threshold': 7.0,     # 高开超过7%视为风险
        'low_open_threshold': -2.0,      # 低开超过-2%视为风险
        'high_open_penalty': 0.7,        # 高开过多降权
        'no_auction_penalty': 0.5,       # 无竞价数据降权
    }
}


class MorningAuctionAnalyzerV3:
    """T+1日竞价分析器（P4深度分析版）"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.risk = RiskController()
        self.feishu = FeishuNotifier()
        
        # 竞价评分权重（含竞价换手率、竞价量比、竞价资金流向指标）
        self.auction_weights = {
            'auction_change': 0.10,        # ↓ 竞价涨幅
            'auction_amount': 0.08,        # ↓ 竞价金额
            'in_hot_auction': 0.08,        # ↓ 是否竞价热点股
            'robbing_score': 0.08,         # ↓ 竞价抢筹评分
            'sector_auction_rank': 0.06,   # ↓ 所属板块竞价排名
            'open_position': 0.06,         # ↓ 开盘位置评分
            'auction_volume_ratio': 0.08,  # 竞价成交量/T日成交量
            'auction_turnover': 0.08,      # ★竞价换手率
            'auction_volume_ratio_5d': 0.06, # ★竞价量比（竞价换手率/5日均换手率）
            'auction_fund_flow': 0.04,     # ★P4新增 竞价资金流向
            't_score_weight': 0.28         # ↓ T日评分权重
        }
        
        # P3优化：风控状态
        self.risk_flags = []
        self.market_trend = 'neutral'
        self.market_data = None
        self.time_window_flags = []
        self.overheated_sectors = set()
        
        # ★P4新增：情绪周期和板块轮动
        self.emotion_analyzer = EmotionCycleAnalyzer()
        self.sector_rotation = SectorRotationAnalyzer()
        self.emotion_stage = None
        self.position_limit = 0.5
        self.sector_rotation_result = None
        
        # ★P4新增：竞价资金流向分析
        self.fund_flow_analyzer = AuctionFundFlowAnalyzer()
    
    def load_t1_selected_stocks(self, t_date=None):
        """加载T日选出的股票"""
        if t_date:
            history_file = os.path.join(DATA_BASE_DIR, "history", f"selection_{t_date}.json")
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        if os.path.exists(RESULT_FILE):
            with open(RESULT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
    
    # ==================== P3优化：高级风控功能 ====================
    
    def _check_time_window_risk(self, date_str):
        """检查时间窗口风险"""
        if not P3_RISK_CONFIG['time_window']['enabled']:
            return []
        
        flags = []
        today = datetime.strptime(date_str, '%Y-%m-%d')
        
        _, last_day = calendar.monthrange(today.year, today.month)
        days_to_month_end = last_day - today.day
        
        if days_to_month_end <= P3_RISK_CONFIG['time_window']['month_end_days']:
            flags.append('月末')
        
        if today.month in P3_RISK_CONFIG['time_window']['quarter_end_months']:
            if days_to_month_end <= P3_RISK_CONFIG['time_window']['month_end_days']:
                flags.append('季末')
        
        if today.month == 12 and today.day >= (31 - P3_RISK_CONFIG['time_window']['year_end_days']):
            flags.append('年末')
        
        self.time_window_flags = flags
        if flags:
            self.risk_flags.append(f"时间窗口风险: {', '.join(flags)}")
        
        return flags
    
    def _get_market_trend(self, date_str):
        """获取大盘走势判断"""
        if not P3_RISK_CONFIG['market_environment']['enabled']:
            return 'neutral'
        
        try:
            # 计算5天前的日期
            from datetime import datetime, timedelta
            end_date = datetime.strptime(date_str, '%Y-%m-%d')
            start_date = end_date - timedelta(days=7)  # 多取几天确保有5个交易日
            
            # 获取上证指数K线
            sh_kline = self.client.get_stock_kline('000001', start_date.strftime('%Y-%m-%d'), date_str)
            
            if sh_kline and len(sh_kline) > 0:
                today_data = sh_kline[-1]
                yesterday_data = sh_kline[-2] if len(sh_kline) > 1 else sh_kline[0]
                
                today_close = float(today_data.get('close', 0))
                yesterday_close = float(yesterday_data.get('close', 0))
                
                if yesterday_close > 0:
                    change_pct = (today_close - yesterday_close) / yesterday_close
                    
                    if change_pct >= P3_RISK_CONFIG['market_environment']['bull_market_threshold']:
                        self.market_trend = 'bull'
                    elif change_pct <= P3_RISK_CONFIG['market_environment']['bear_market_threshold']:
                        self.market_trend = 'bear'
                        self.risk_flags.append(f"弱势市场: 大盘跌幅{abs(change_pct)*100:.2f}%")
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
    
    def _detect_overheated_sectors(self, auction_sectors):
        """检测竞价过热板块"""
        if not P3_RISK_CONFIG['sector_overheat']['enabled']:
            return set()
        
        overheated = set()
        threshold = P3_RISK_CONFIG['sector_overheat']['overheat_threshold']
        
        for sector in auction_sectors[:3]:
            # 使用竞价涨幅判断过热
            jjzf = sector.get('jjzf', 0)
            try:
                jjzf = float(jjzf)
            except:
                jjzf = 0
            
            if jjzf >= 5.0:  # 竞价涨幅超过5%视为过热
                sector_name = sector.get('bkName', '')
                overheated.add(sector_name)
                self.risk_flags.append(f"板块过热: {sector_name} (竞价涨幅:{jjzf:.2f}%)")
        
        self.overheated_sectors = overheated
        return overheated
    
    def _apply_p3_risk_adjustment(self, score_detail, stock):
        """
        应用P3风险调整
        
        Returns:
            tuple: (调整后分数, 风险标记列表)
        """
        risk_tags = []
        adjusted_score = score_detail['final_score']
        config = P3_RISK_CONFIG
        
        # 1. 连板高度风险
        if config['high_board_penalty']['enabled']:
            lb_num = stock.get('details', {}).get('lb_num', 1)
            if lb_num >= config['high_board_penalty']['warning_threshold']:
                adjusted_score *= config['high_board_penalty']['4_board_multiplier']
                risk_tags.append(f"高位板({lb_num}板×0.8)")
        
        # 2. 板块过热风险
        if config['sector_overheat']['enabled'] and self.overheated_sectors:
            sector_name = stock.get('details', {}).get('hot_sector_name', '')
            if sector_name in self.overheated_sectors:
                adjusted_score *= config['sector_overheat']['overheat_penalty']
                risk_tags.append("过热板块(×0.7)")
        
        # 3. 市场环境风险
        if config['market_environment']['enabled'] and self.market_trend == 'bear':
            adjusted_score *= config['market_environment']['weak_market_penalty']
            risk_tags.append("弱势市场(×0.8)")
        
        # 4. 时间窗口风险
        if config['time_window']['enabled'] and self.time_window_flags:
            adjusted_score *= config['time_window']['time_penalty']
            risk_tags.append(f"时间窗口(×0.9)")
        
        # 5. 竞价风控
        if config['auction_risk']['enabled']:
            open_change = score_detail.get('open_change', 0)
            
            # 高开过多风险
            if open_change >= config['auction_risk']['high_open_threshold']:
                adjusted_score *= config['auction_risk']['high_open_penalty']
                risk_tags.append(f"高开过多({open_change:.1f}%×0.7)")
            
            # 无竞价数据风险
            if not score_detail.get('auction_data'):
                adjusted_score *= config['auction_risk']['no_auction_penalty']
                risk_tags.append("无竞价数据(×0.5)")
        
        return round(adjusted_score, 2), risk_tags
    
    def _apply_weak_market_filter(self, score):
        """弱势市场过滤"""
        if not P3_RISK_CONFIG['market_environment']['enabled']:
            return True
        
        if self.market_trend == 'bear':
            min_score = P3_RISK_CONFIG['market_environment']['weak_market_min_score']
            return score >= min_score
        
        return True
    
    # ==================== 原有竞价分析功能 ====================
    
    def get_auction_data(self):
        """获取竞价数据"""
        print("\n获取竞价数据...")
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 竞价热点板块
        try:
            auction_sectors = self.client.get_enhanced_auction_sectors(today)
        except Exception as e:
            print(f"  获取竞价板块失败: {e}")
            auction_sectors = []
        print(f"  竞价热点板块: {len(auction_sectors) if auction_sectors else 0} 个")
        
        # 竞价热点个股（会自动遍历热门板块获取）
        try:
            auction_stocks = self.client.get_enhanced_auction_stocks(today)
        except Exception as e:
            print(f"  获取竞价个股失败: {e}")
            auction_stocks = []
        print(f"  竞价热点个股: {len(auction_stocks) if auction_stocks else 0} 只")
        
        # 竞价抢筹榜
        try:
            robbing_data = self.client.get_auction_robbing(today, period=0, type=1)
        except Exception as e:
            print(f"  获取竞价抢筹失败: {e}")
            robbing_data = []
        print(f"  竞价抢筹榜: {len(robbing_data) if robbing_data else 0} 只")
        
        return auction_sectors or [], auction_stocks or [], robbing_data or []
    
    def find_stock_in_auction(self, stock_code, auction_stocks):
        """在竞价个股中查找指定股票"""
        if not auction_stocks:
            return None
        
        for stock in auction_stocks:
            code = stock.get('code', '')
            if '.' in code:
                code = code.split('.')[0]
            if code == stock_code:
                return stock
        
        return None
    
    def find_stock_in_robbing(self, stock_code, robbing_data):
        """在竞价抢筹榜中查找股票"""
        if not robbing_data:
            return None
        
        for item in robbing_data:
            code = item.get('code', '')
            if '.' in code:
                code = code.split('.')[0]
            if code == stock_code:
                return item
        
        return None
    
    def find_sector_in_auction(self, sector_name, auction_sectors):
        """在竞价板块中查找指定板块"""
        if not auction_sectors:
            return None, None
        
        for i, sector in enumerate(auction_sectors, 1):
            bk_name = sector.get('bkName', '')
            if bk_name == sector_name or (sector_name and sector_name in bk_name):
                return i, sector
        
        return None, None
    
    def calc_open_position_score(self, open_change):
        """计算开盘位置评分"""
        if open_change >= 9.8:
            return 0  # 一字板买不进
        elif open_change >= 7:
            return 3
        elif open_change >= 3:
            return 10
        elif open_change >= 0:
            return 7
        else:
            return 0
    
    def calc_robbing_score(self, robbing_data):
        """计算竞价抢筹评分"""
        if not robbing_data:
            return 0
        
        score = 0
        
        qczf = 0
        try:
            qczf = float(robbing_data.get('qczf', 0))
        except:
            pass
        
        if qczf >= 5:
            score += 5
        elif qczf >= 3:
            score += 3
        elif qczf > 0:
            score += 2
        
        qcwtje = 0
        try:
            qcwtje = float(robbing_data.get('qcwtje', 0))
        except:
            pass
        
        if qcwtje >= 100000000:
            score += 5
        elif qcwtje >= 50000000:
            score += 3
        elif qcwtje >= 10000000:
            score += 2
        
        return min(score, 10)
    
    def calc_auction_volume_ratio_score(self, robbing_data, t_day_amount):
        """
        计算竞价成交量/T日成交量比值评分
        
        Args:
            robbing_data: 竞价抢筹数据（包含openAmt字段）
            t_day_amount: T日成交额
        
        Returns:
            tuple: (比值, 评分)
        """
        if not robbing_data or not t_day_amount:
            return 0, 0
        
        try:
            # openAmt = 竞价成交金额
            open_amt = float(robbing_data.get('openAmt', 0))
            t_amount = float(t_day_amount)
            
            if t_amount <= 0:
                return 0, 0
            
            # 计算比值（百分比）
            ratio = (open_amt / t_amount) * 100
            
            # 评分逻辑
            # >10%: 竞价异常活跃，强看多信号
            # 5%-10%: 竞价活跃，关注度较高
            # 2%-5%: 正常水平
            # <2%: 竞价冷清
            
            if ratio >= 10:
                score = 15  # 竞价爆量，非常强
            elif ratio >= 7:
                score = 12  # 竞价很活跃
            elif ratio >= 5:
                score = 10  # 竞价活跃
            elif ratio >= 3:
                score = 7   # 正常偏强
            elif ratio >= 2:
                score = 5   # 正常
            elif ratio >= 1:
                score = 3   # 稍弱
            else:
                score = 0   # 竞价冷清
            
            return round(ratio, 2), score
            
        except Exception as e:
            print(f"计算竞价成交量比失败: {e}")
            return 0, 0
    
    def calc_auction_turnover_score(self, robbing_data, flow_capital):
        """
        ★新增：计算竞价换手率评分
        
        公式：竞价换手率 = 竞价成交金额 / 流通市值 × 100%
        
        Args:
            robbing_data: 竞价抢筹数据（包含openAmt字段）
            flow_capital: 流通市值
        
        Returns:
            tuple: (竞价换手率%, 评分)
        """
        if not robbing_data or not flow_capital:
            return 0, 0
        
        try:
            open_amt = float(robbing_data.get('openAmt', 0))
            flow_cap = float(flow_capital)
            
            if flow_cap <= 0:
                return 0, 0
            
            # 计算竞价换手率（百分比）
            auction_turnover = (open_amt / flow_cap) * 100
            
            # 评分逻辑
            if auction_turnover >= 3:
                score = 15  # 竞价极度活跃，资金抢筹剧烈
            elif auction_turnover >= 2:
                score = 12  # 竞价很活跃
            elif auction_turnover >= 1:
                score = 10  # 竞价活跃，资金积极参与
            elif auction_turnover >= 0.5:
                score = 7   # 竞价正常偏强
            elif auction_turnover >= 0.3:
                score = 5   # 竞价一般
            elif auction_turnover >= 0.1:
                score = 3   # 竞价偏弱
            else:
                score = 0   # 竞价冷清
            
            return round(auction_turnover, 4), score
            
        except Exception as e:
            print(f"计算竞价换手率失败: {e}")
            return 0, 0
    
    def calc_auction_volume_ratio_5d_score(self, auction_turnover, stock_code, t_date):
        """
        ★新增：计算竞价量比评分（竞价换手率/过去5日换手率均值）
        
        公式：竞价量比 = 竞价换手率 / 过去5日换手率均值
        
        Args:
            auction_turnover: 竞价换手率（%）
            stock_code: 股票代码
            t_date: T日日期
        
        Returns:
            tuple: (竞价量比, 评分, 5日平均换手率)
        """
        if not auction_turnover or auction_turnover <= 0:
            return 0, 0, 0
        
        try:
            # 获取过去5日K线数据计算平均换手率
            from datetime import datetime, timedelta
            
            t_date_obj = datetime.strptime(t_date, '%Y-%m-%d')
            start_date = (t_date_obj - timedelta(days=15)).strftime('%Y-%m-%d')
            end_date = t_date_obj.strftime('%Y-%m-%d')
            
            kline_data = self.client.get_stock_kline(stock_code, start_date, end_date, cycle=100)
            
            if not kline_data or not isinstance(kline_data, list):
                # 无法获取历史数据，使用默认值
                return 0, 0, 0
            
            # 提取过去5个交易日的换手率（排除当天）
            past_turnovers = []
            for item in kline_data:
                item_date = item.get('time', '')
                if item_date < t_date:  # 只取T日之前的数据
                    turnover = item.get('turnoverRatio', 0)
                    try:
                        past_turnovers.append(float(turnover))
                    except:
                        pass
            
            if len(past_turnovers) < 3:
                return 0, 0, 0
            
            # 取最近5个交易日的换手率
            recent_turnovers = past_turnovers[-5:] if len(past_turnovers) >= 5 else past_turnovers
            avg_turnover_5d = sum(recent_turnovers) / len(recent_turnovers)
            
            if avg_turnover_5d <= 0:
                return 0, 0, 0
            
            # 计算竞价量比
            volume_ratio_5d = auction_turnover / avg_turnover_5d
            
            # 评分逻辑
            if volume_ratio_5d >= 3.0:
                score = 15  # 竞价资金参与强度是平时3倍+，极度活跃
            elif volume_ratio_5d >= 2.0:
                score = 12  # 竞价资金参与强度是平时2-3倍，很活跃
            elif volume_ratio_5d >= 1.5:
                score = 10  # 竞价资金参与强度是平时1.5-2倍，活跃
            elif volume_ratio_5d >= 1.0:
                score = 7   # 竞价资金参与强度接近平时，正常偏强
            elif volume_ratio_5d >= 0.5:
                score = 5   # 竞价资金参与强度低于平时，稍弱
            else:
                score = 0   # 竞价冷清
            
            return round(volume_ratio_5d, 2), score, round(avg_turnover_5d, 2)
            
        except Exception as e:
            print(f"计算竞价量比(5日)失败: {e}")
            return 0, 0, 0
    
    def calculate_auction_score(self, stock, auction_stocks, auction_sectors, robbing_data, t_date):
        """计算竞价评分"""
        stock_code = stock.get('code', '')
        t_score = stock.get('score', 0)
        
        score_detail = {
            'stock_code': stock_code,
            'stock_name': stock.get('name', ''),
            't_score': t_score,
            'auction_score': 0,
            'final_score': 0,
            'adjusted_score': 0,
            'auction_data': None,
            'robbing_data': None,
            'in_hot_auction': False,
            'sector_rank': None,
            'risk_tags': [],
            'auction_volume_ratio': 0,
            'auction_volume_ratio_score': 0,
            'auction_turnover': 0,           # ★新增 竞价换手率
            'auction_turnover_score': 0,     # ★新增 竞价换手率评分
            'auction_volume_ratio_5d': 0,    # ★新增 竞价量比（/5日均值）
            'auction_volume_ratio_5d_score': 0, # ★新增 竞价量比评分
            'avg_turnover_5d': 0             # ★新增 5日平均换手率
        }
        
        # T日评分贡献
        t_score_contrib = t_score * self.auction_weights['t_score_weight'] / 100
        score_detail['t_score_contrib'] = round(t_score_contrib, 2)
        
        auction_score = 0
        
        # 检查是否在竞价热点个股中
        auction_data = self.find_stock_in_auction(stock_code, auction_stocks)
        
        if auction_data:
            score_detail['auction_data'] = auction_data
            score_detail['in_hot_auction'] = True
            
            try:
                auction_change = float(auction_data.get('changeRatio', 0) or auction_data.get('jjzf', 0))
                if auction_change > 5:
                    auction_change_score = 15
                elif auction_change > 3:
                    auction_change_score = 12
                elif auction_change > 0:
                    auction_change_score = 10
                elif auction_change > -3:
                    auction_change_score = 5
                else:
                    auction_change_score = 0
                
                auction_score += auction_change_score * self.auction_weights['auction_change'] / 15
                score_detail['auction_change'] = auction_change
                score_detail['auction_change_score'] = auction_change_score
            except:
                pass
            
            try:
                auction_amount = float(auction_data.get('amount', 0))
                if auction_amount > 100000000:
                    amount_score = 12
                elif auction_amount > 50000000:
                    amount_score = 8
                elif auction_amount > 10000000:
                    amount_score = 5
                else:
                    amount_score = 2
                
                auction_score += amount_score * self.auction_weights['auction_amount'] / 12
                score_detail['auction_amount'] = auction_amount
                score_detail['auction_amount_score'] = amount_score
            except:
                pass
            
            try:
                open_change = float(auction_data.get('changeRatio', 0) or auction_data.get('jjzf', 0))
                open_score = self.calc_open_position_score(open_change)
                auction_score += open_score * self.auction_weights['open_position'] / 10
                score_detail['open_change'] = open_change
                score_detail['open_position_score'] = open_score
            except:
                pass
        
        # 竞价抢筹评分
        stock_robbing = self.find_stock_in_robbing(stock_code, robbing_data)
        
        if stock_robbing:
            score_detail['robbing_data'] = stock_robbing
            robbing_score = self.calc_robbing_score(stock_robbing)
            auction_score += robbing_score * self.auction_weights['robbing_score'] / 10
            score_detail['robbing_score'] = robbing_score
            score_detail['robbing_rank'] = stock_robbing.get('type', 0)
            
            # 计算竞价成交量/T日成交量
            t_day_amount = stock.get('details', {}).get('amount', 0)
            if t_day_amount > 0:
                ratio, avr_score = self.calc_auction_volume_ratio_score(stock_robbing, t_day_amount)
                score_detail['auction_volume_ratio'] = ratio
                score_detail['auction_volume_ratio_score'] = avr_score
                auction_score += avr_score * self.auction_weights['auction_volume_ratio'] / 15
            
            # ★新增：计算竞价换手率
            flow_capital = stock.get('details', {}).get('seal_to_market_cap', 0)
            # 如果没有流通市值，尝试从原始数据获取
            if not flow_capital:
                flow_capital = stock.get('raw_data', {}).get('flowCapital', 0)
            else:
                # seal_to_market_cap是比例，需要换算
                t_day_amount_val = stock.get('details', {}).get('amount', 0)
                if t_day_amount_val > 0 and flow_capital > 0:
                    # 成交额/换手率 = 流通市值（近似）
                    t_turnover = stock.get('details', {}).get('turnover_rate', 5)
                    if t_turnover > 0:
                        flow_capital = t_day_amount_val / (t_turnover / 100)
            
            # 直接从T日涨停数据获取流通市值
            raw_flow_capital = stock.get('raw_data', {}).get('flowCapital', 0)
            if raw_flow_capital > 0:
                flow_capital = raw_flow_capital
            
            if flow_capital > 0:
                auction_turnover, at_score = self.calc_auction_turnover_score(stock_robbing, flow_capital)
                score_detail['auction_turnover'] = auction_turnover
                score_detail['auction_turnover_score'] = at_score
                auction_score += at_score * self.auction_weights['auction_turnover'] / 15
                
                # ★新增：计算竞价量比（竞价换手率/5日平均换手率）
                if auction_turnover > 0:
                    vr_5d, vr_5d_score, avg_5d = self.calc_auction_volume_ratio_5d_score(
                        auction_turnover, stock_code, t_date
                    )
                    score_detail['auction_volume_ratio_5d'] = vr_5d
                    score_detail['auction_volume_ratio_5d_score'] = vr_5d_score
                    score_detail['avg_turnover_5d'] = avg_5d
                    auction_score += vr_5d_score * self.auction_weights['auction_volume_ratio_5d'] / 15
        else:
            score_detail['robbing_score'] = 0
        
        # ★P4新增：竞价资金流向分析
        fund_flow_data = self.fund_flow_analyzer.analyze_fund_flow(stock_code)
        score_detail['fund_flow_data'] = fund_flow_data
        fund_flow_score = fund_flow_data.get('fund_flow_score', 0)
        if fund_flow_score > 0:
            score_detail['fund_flow_score'] = fund_flow_score
            score_detail['fund_flow_trend'] = fund_flow_data.get('trend', '未知')
            score_detail['big_net_buy'] = fund_flow_data.get('big_net_buy', 0)
            auction_score += fund_flow_score * self.auction_weights['auction_fund_flow'] / 15
        
        # 板块竞价排名
        sector_name = stock.get('details', {}).get('hot_sector_name', '')
        if sector_name and auction_sectors:
            rank, sector_data = self.find_sector_in_auction(sector_name, auction_sectors)
            if rank:
                score_detail['sector_rank'] = rank
                score_detail['sector_data'] = sector_data
                
                if rank <= 3:
                    sector_score = 8
                elif rank <= 5:
                    sector_score = 5
                elif rank <= 10:
                    sector_score = 3
                else:
                    sector_score = 1
                
                auction_score += sector_score * self.auction_weights['sector_auction_rank'] / 8
                score_detail['sector_score'] = sector_score
        
        # 汇总
        score_detail['auction_score'] = round(auction_score, 2)
        score_detail['final_score'] = round(t_score_contrib + auction_score, 2)
        
        # P3优化：应用风险调整
        adjusted_score, risk_tags = self._apply_p3_risk_adjustment(score_detail, stock)
        score_detail['adjusted_score'] = adjusted_score
        score_detail['risk_tags'] = risk_tags
        
        return score_detail
    
    def analyze_selected_stocks(self, t_date=None):
        """分析T日选出的股票在T+1日竞价中的表现"""
        
        print("=" * 70)
        print("T01龙头战法 - T+1日竞价分析（P4深度分析版）")
        print("=" * 70)
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # ========== 检查是否为交易日 ==========
        if not self.client.get_trading_day(today):
            print(f"⚠️ {today} 不是交易日，跳过竞价分析")
            return None
        
        # 1. 加载T日选股记录
        print("\n【步骤1】加载T日选股记录")
        print("-" * 70)
        
        selection = self.load_t1_selected_stocks(t_date)
        
        if not selection:
            print("未找到T日选股记录")
            return None
        
        t_date = selection.get('date', 'Unknown')
        selected_stocks = selection.get('stocks', selection.get('top_stocks', []))
        
        # ★P4新增：获取T日的情绪周期和仓位限制
        self.emotion_stage = selection.get('emotion_stage', None)
        self.position_limit = selection.get('position_limit', 0.5)
        self.sector_rotation_result = selection.get('sector_rotation', None)
        
        print(f"  T日: {t_date}")
        print(f"  选出股票: {len(selected_stocks)} 只")
        
        # ★P4新增：显示T日情绪阶段
        if self.emotion_stage:
            stage_name = self.emotion_stage.get('stage_name', '未知')
            print(f"  T日情绪阶段: {stage_name}")
            print(f"  建议仓位上限: {self.position_limit*100:.0f}%")
        
        # ========== P3优化：风险预检 ==========
        print(f"\n【P3风控】风险预检...")
        
        # 检查时间窗口风险
        self._check_time_window_risk(today)
        if self.time_window_flags:
            print(f"  ⚠️ 时间窗口风险: {', '.join(self.time_window_flags)}")
        
        # 获取大盘走势
        self._get_market_trend(today)
        if self.market_data:
            print(f"  大盘走势: 上证指数 {self.market_data['close']:.2f} ({self.market_data['change_pct']:+.2f}%)")
            if self.market_trend == 'bear':
                print(f"  ⚠️ 弱势市场模式: 启用降权保护")
        
        # 2. 获取竞价数据
        print("\n【步骤2】获取竞价数据")
        print("-" * 70)
        
        auction_sectors, auction_stocks, robbing_data = self.get_auction_data()
        
        # P3优化：检测过热板块
        print(f"\n【P3风控】检测竞价过热板块...")
        self._detect_overheated_sectors(auction_sectors)
        if self.overheated_sectors:
            print(f"  ⚠️ 过热板块: {', '.join(self.overheated_sectors)}")
        
        if auction_sectors:
            print("\n  竞价热点板块TOP5:")
            for i, sector in enumerate(auction_sectors[:5], 1):
                overheat_icon = '🔥' if sector.get('bkName') in self.overheated_sectors else ''
                print(f"    {i}. {sector.get('bkName', 'N/A')} - 竞价涨幅: {sector.get('jjzf', 0)}% {overheat_icon}")
        
        if robbing_data:
            print("\n  竞价抢筹榜TOP5:")
            for i, item in enumerate(robbing_data[:5], 1):
                print(f"    {i}. {item.get('name', 'N/A')}({item.get('code', 'N/A')}) - 抢筹涨幅: {item.get('qczf', 0)}%")
        
        # 3. 计算竞价评分
        print("\n【步骤3】计算竞价评分（含P3风控）")
        print("-" * 70)
        
        scored_stocks = []
        filtered_stocks = []
        
        for stock in selected_stocks:
            if isinstance(stock, dict):
                score_detail = self.calculate_auction_score(
                    stock, auction_stocks, auction_sectors, robbing_data, t_date
                )
                
                # P3优化：弱势市场过滤
                if not self._apply_weak_market_filter(score_detail['adjusted_score']):
                    filtered_stocks.append({
                        'stock_name': score_detail['stock_name'],
                        'reason': f"弱势市场过滤(分数{score_detail['adjusted_score']:.2f}<{P3_RISK_CONFIG['market_environment']['weak_market_min_score']})"
                    })
                    continue
                
                scored_stocks.append(score_detail)
                
                print(f"\n  {score_detail['stock_name']}({score_detail['stock_code']})")
                print(f"    T日评分贡献: {score_detail.get('t_score_contrib', 0):.2f}")
                print(f"    竞价评分: {score_detail['auction_score']:.2f}")
                print(f"    原始总分: {score_detail['final_score']:.2f}")
                print(f"    调整后分数: {score_detail['adjusted_score']:.2f}")
                
                # ★新增：显示竞价换手率
                at = score_detail.get('auction_turnover', 0)
                at_score = score_detail.get('auction_turnover_score', 0)
                if at > 0:
                    print(f"    📈 竞价换手率: {at:.4f}% (评分: {at_score})")
                
                # ★新增：显示竞价量比（/5日均值）
                vr_5d = score_detail.get('auction_volume_ratio_5d', 0)
                vr_5d_score = score_detail.get('auction_volume_ratio_5d_score', 0)
                avg_5d = score_detail.get('avg_turnover_5d', 0)
                if vr_5d > 0:
                    print(f"    📊 竞价量比(5日): {vr_5d:.2f}倍 (5日均换手:{avg_5d:.2f}%, 评分:{vr_5d_score})")
                
                # 显示竞价成交量/T日成交量
                avr = score_detail.get('auction_volume_ratio', 0)
                avr_score = score_detail.get('auction_volume_ratio_score', 0)
                if avr > 0:
                    print(f"    💹 竞价量/T日量: {avr:.2f}% (评分: {avr_score})")
                
                if score_detail.get('risk_tags'):
                    print(f"    ⚠️ 风险标记: {', '.join(score_detail['risk_tags'])}")
                
                if score_detail.get('robbing_data'):
                    print(f"    💰 竞价抢筹: 是 (评分: {score_detail.get('robbing_score', 0)})")
        
        # 打印过滤统计
        if filtered_stocks:
            print(f"\n  弱势市场过滤掉 {len(filtered_stocks)} 只股票")
        
        # 4. 排序（按调整后分数）
        scored_stocks.sort(key=lambda x: x['adjusted_score'], reverse=True)
        
        # 5. 获取风控建议
        print("\n【步骤4】风控评估")
        print("-" * 70)
        
        risk_result = self.risk.full_risk_assessment()
        
        # 6. 生成最终建议
        print("\n" + "=" * 70)
        print("【最终买入建议】")
        print("=" * 70)
        
        result = {
            't_date': t_date,
            't1_date': today,
            'analysis_time': datetime.now().isoformat(),
            'version': 'v3',
            'p3_risk_flags': self.risk_flags,
            'risk_assessment': {
                'trading_allowed': risk_result['trading_allowed'],
                'position_limit': risk_result['final_position_limit']
            },
            'auction_sectors': auction_sectors[:10] if auction_sectors else [],
            'auction_stocks_count': len(auction_stocks) if auction_stocks else 0,
            'robbing_count': len(robbing_data) if robbing_data else 0,
            'overheated_sectors': list(self.overheated_sectors),
            'buy_recommendations': [],
            'scored_stocks': scored_stocks  # 保存完整评分数据供飞书通知使用
        }
        
        # ★P4优化：使用情绪周期的position_limit和风控的position_limit的较小值
        risk_position_limit = risk_result['final_position_limit']
        emotion_position_limit = self.position_limit
        position_limit = min(risk_position_limit, emotion_position_limit)
        
        print(f"\n  【仓位控制】")
        print(f"    风控仓位上限: {risk_position_limit*100:.0f}%")
        print(f"    情绪周期仓位上限: {emotion_position_limit*100:.0f}%")
        print(f"    实际仓位上限: {position_limit*100:.0f}%")
        
        for i, stock in enumerate(scored_stocks, 1):
            # 根据排名和风控分配仓位
            if i == 1:
                rec_position = min(0.1, position_limit * 0.4)
            elif i == 2:
                rec_position = min(0.08, position_limit * 0.3)
            elif i == 3:
                rec_position = min(0.05, position_limit * 0.2)
            else:
                rec_position = 0
            
            rec = {
                'rank': i,
                'stock_code': stock['stock_code'],
                'stock_name': stock['stock_name'],
                't_score': stock['t_score'],
                'auction_score': stock['auction_score'],
                'final_score': stock['final_score'],
                'adjusted_score': stock['adjusted_score'],
                'in_hot_auction': stock['in_hot_auction'],
                'has_robbing': stock.get('robbing_data') is not None,
                'risk_tags': stock.get('risk_tags', []),
                'recommended_position': round(rec_position, 2),
                'action': '买入' if rec_position > 0 else '观望'
            }
            
            result['buy_recommendations'].append(rec)
            
            action_icon = '🟢' if rec['action'] == '买入' else '⚪'
            hot_icon = '🔥' if stock['in_hot_auction'] else ''
            robbing_icon = '💰' if stock.get('robbing_data') else ''
            
            # 竞价量比标记
            avr = stock.get('auction_volume_ratio', 0)
            volume_icon = '📊' if avr >= 5 else ''
            
            print(f"\n  {action_icon} 第{i}名: {stock['stock_name']}({stock['stock_code']}) {hot_icon}{robbing_icon}{volume_icon}")
            print(f"      T日评分: {stock['t_score']:.2f} → 竞价评分: {stock['auction_score']:.2f}")
            
            # ★新增：显示竞价量比
            if avr > 0:
                print(f"      竞价量比: {avr:.2f}% (竞价量/T日量)")
            
            print(f"      调整后分数: {stock['adjusted_score']:.2f}")
            print(f"      建议仓位: {rec['recommended_position']*100:.1f}%")
            print(f"      操作建议: {rec['action']}")
            
            if stock.get('risk_tags'):
                print(f"      ⚠️ 风险标记: {', '.join(stock['risk_tags'])}")
        
        # P3优化：打印风险汇总
        if self.risk_flags:
            print(f"\n" + "=" * 70)
            print(f"【P3风控预警】")
            for warning in self.risk_flags:
                print(f"  ⚠️ {warning}")
        
        # 7. 保存结果
        self._save_result(result)
        
        # 8. 发送通知
        self._send_notification(result)
        
        return result
    
    def _save_result(self, result):
        """保存竞价分析结果"""
        with open(AUCTION_RESULT_FILE, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存: {AUCTION_RESULT_FILE}")
    
    def _send_notification(self, result):
        """发送飞书通知"""
        risk = result['risk_assessment']
        recs = result['buy_recommendations']
        scored_stocks = result.get('scored_stocks', [])
        
        message = f"🔔 T01龙头战法 - T+1日竞价分析（P4深度版）\n\n"
        message += f"分析时间: {result['t1_date']} 9:26\n"
        message += f"T日选股: {result['t_date']}\n\n"
        message += "━" * 30 + "\n"
        
        # ★P4新增：显示情绪周期
        if self.emotion_stage:
            stage_name = self.emotion_stage.get('stage_name', '未知')
            message += f"【情绪周期】{stage_name}\n"
            message += f"  建议仓位: {self.position_limit*100:.0f}%\n\n"
        
        # P3优化：显示风控预警
        if result.get('p3_risk_flags'):
            message += "【P3风控预警】\n"
            for flag in result['p3_risk_flags']:
                message += f"  ⚠️ {flag}\n"
            message += "\n"
        
        message += "【风控评估】\n"
        message += f"  允许交易: {'✅' if risk['trading_allowed'] else '❌'}\n"
        message += f"  最大仓位: {risk['position_limit']*100:.0f}%\n\n"
        message += f"【竞价数据】\n"
        message += f"  竞价抢筹股: {result.get('robbing_count', 0)} 只\n"
        if result.get('overheated_sectors'):
            message += f"  ⚠️ 过热板块: {', '.join(result['overheated_sectors'])}\n"
        message += "\n" + "━" * 30 + "\n"
        message += "【买入建议】\n"
        
        for rec in recs[:3]:
            if rec['action'] == '买入':
                hot = '🔥' if rec['in_hot_auction'] else ''
                robbing = '💰' if rec['has_robbing'] else ''
                
                # 获取对应的stock数据以显示竞价指标
                stock_data = None
                for s in scored_stocks:
                    if s['stock_code'] == rec['stock_code']:
                        stock_data = s
                        break
                
                # 竞价换手率
                at = stock_data.get('auction_turnover', 0) if stock_data else 0
                # 竞价量比（5日）
                vr_5d = stock_data.get('auction_volume_ratio_5d', 0) if stock_data else 0
                # 竞价量/T日量
                avr = stock_data.get('auction_volume_ratio', 0) if stock_data else 0
                
                # 构建指标显示
                indicators = []
                if at > 0:
                    indicators.append(f"换手{at:.2f}%")
                if vr_5d > 0:
                    indicators.append(f"量比{vr_5d:.1f}倍")
                indicator_info = f" [{', '.join(indicators)}]" if indicators else ""
                
                risk_tags = ' ⚠️' + ', '.join(rec.get('risk_tags', [])) if rec.get('risk_tags') else ''
                message += f"\n  {rec['rank']}. {rec['stock_name']}{hot}{robbing}{indicator_info}{risk_tags}\n"
                message += f"     调整后分数: {rec['adjusted_score']:.2f}\n"
                message += f"     建议仓位: {rec['recommended_position']*100:.1f}%\n"
        
        message += "\n" + "━" * 30 + "\n"
        message += "⚠️ 竞价数据仅供参考，请结合盘面谨慎决策"
        
        try:
            chat_id = "oc_ff08c55a23630937869cd222dad0bf14"
            self.feishu.send_message(chat_id, message)
            print("\n飞书通知已发送")
        except Exception as e:
            print(f"\n飞书通知发送失败: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='T01龙头战法 - T+1日竞价分析（P3风控版）')
    parser.add_argument('--t-date', type=str, help='T日日期')
    
    args = parser.parse_args()
    
    analyzer = MorningAuctionAnalyzerV3()
    result = analyzer.analyze_selected_stocks(args.t_date)
    
    if result:
        print("\n" + "=" * 70)
        print("竞价分析完成!")
        print("=" * 70)


if __name__ == "__main__":
    main()
