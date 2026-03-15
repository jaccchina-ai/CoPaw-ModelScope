#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01任务 - 龙头战法 - T日晚上分析脚本 (优化版 v3)
功能：
1. 分析当日涨停股，选出前5名作为次日观察标的
2. 使用AI进化模块的动态权重
3. 新增P0优化：连板数评分、炸板次数评分、预过滤
4. 集成情绪周期和大盘走势风控
"""

import json
import requests
from datetime import datetime, timedelta
import os
import sys

# 添加 scripts 目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from stockapi_client import StockAPIClient
from feishu_notifier import send_feishu_message
from T01_ai_evolution import AIEvolution

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

# ==================== P0优化：新权重配置 ====================
NEW_WEIGHTS = {
    'first_limit_time': 0.12,    # ↓ 首次涨停时间
    'seal_ratio': 0.10,          # ↓ 封成比
    'seal_market_cap': 0.10,     # - 封单/市值
    'lb_num': 0.12,              # ★新增 连板数
    'bomb_num': 0.08,            # ★新增 炸板次数
    'dragon_tiger': 0.08,        # ↓ 龙虎榜
    'main_fund_ratio': 0.10,     # ↓ 主力资金
    'amount': 0.05,              # ↓ 成交金额
    'turnover_rate': 0.08,       # ↓ 换手率
    'volume_ratio': 0.10,        # ↓ 量比
    'hot_sector': 0.12,          # ↑ 板块强度
    'fund_flow_days': 0.05,      # ★新增 资金流入天数
}


class EveningAnalyzer:
    """T日晚间分析器（优化版v3）"""
    
    def __init__(self, date=None):
        self.client = StockAPIClient()
        self.ai = AIEvolution()
        self.date = date or self.client.get_today_date()
        # 使用新权重
        self.weights = self._init_weights()
        self.hot_sectors = None
        self.emotion = None
        self.limit_up_stocks = None
        self.selected_stocks = []
        self.filtered_count = {'st': 0, 'new': 0, 'high_board': 0, 'multi_bomb': 0}
    
    def _init_weights(self):
        """初始化权重（优先使用AI进化权重，补充新指标）"""
        ai_weights = self.ai.get_current_weights()
        
        # 合并AI权重和新权重
        weights = NEW_WEIGHTS.copy()
        
        # 如果AI有权重，用AI的权重覆盖（除了新增的指标）
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
            # 使用增强版接口，获取更多字段
            self.hot_sectors = self.client.get_hot_sectors_enhanced(self.date)
        return self.hot_sectors
    
    def _get_emotion(self):
        """获取情绪周期"""
        if self.emotion is None:
            self.emotion = self.client.get_emotional_cycle()
        return self.emotion
    
    # ==================== P0优化：预过滤功能 ====================
    
    def _is_st_stock(self, stock_data):
        """判断是否为ST股"""
        name = stock_data.get('name', '')
        if 'ST' in name or 'st' in name:
            return True
        # 检查代码前缀（有些ST股名字不带ST）
        # ST股通常有特殊标记
        return False
    
    def _is_new_stock(self, stock_data):
        """判断是否为新股（上市不足20天）"""
        # 次新股池中有标记
        # 或者根据涨停原因判断
        plate_reason = stock_data.get('plate_reason', '')
        if '次新' in plate_reason or '新股' in plate_reason:
            return True
        # 也可以通过API查询上市日期
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
        """
        预过滤股票
        
        Returns:
            tuple: (是否通过, 过滤原因)
        """
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
        
        return True, None
    
    # ==================== P0优化：新评分指标 ====================
    
    def _calc_lb_num_score(self, lb_num):
        """
        计算连板数评分
        
        逻辑：
        - 首板：10分（一般）
        - 2板：20分（最优质，经过首板检验）
        - 3-4板：15分（高位，谨慎）
        - 5板以上：过滤掉，不参与评分
        """
        try:
            lb_num = int(lb_num)
        except:
            lb_num = 1
        
        if lb_num >= 5:
            return 0   # 高位板已过滤，这里是防御性代码
        elif lb_num >= 3:
            return 15  # 3-4板
        elif lb_num == 2:
            return 20  # 2板最优
        else:
            return 10  # 首板
    
    def _calc_bomb_num_score(self, bomb_num):
        """
        计算炸板次数评分
        
        逻辑：
        - 0次（一字板或首封）：10分
        - 1次（回封）：5分
        - 2次：2分
        - 3次以上：过滤掉
        """
        try:
            bomb_num = int(bomb_num)
        except:
            bomb_num = 0
        
        if bomb_num >= 3:
            return 0   # 多次炸板已过滤
        elif bomb_num == 2:
            return 2
        elif bomb_num == 1:
            return 5
        else:
            return 10  # 一字板或首封
    
    def _calc_sector_strength_score(self, sector_data):
        """
        计算板块强度评分
        
        使用API返回的qiangdu字段
        """
        if not sector_data:
            return 0
        
        strength = sector_data.get('qiangdu', 0)
        try:
            strength = float(strength)
        except:
            return 0
        
        if strength > 50000:
            return 15  # 超强板块
        elif strength > 30000:
            return 12  # 很强
        elif strength > 20000:
            return 10  # 强板块
        elif strength > 10000:
            return 5   # 中等
        else:
            return 0
    
    def _calc_fund_flow_score(self, sector_data):
        """
        计算资金流入天数评分（P2优化：已实现）
        """
        if not sector_data:
            return 0
        
        jlrts = sector_data.get('jlrts', 0)
        try:
            jlrts = int(jlrts)
        except:
            return 0
        
        if jlrts >= 5:
            return 10  # 连续5天以上流入
        elif jlrts >= 3:
            return 8   # 连续3天流入
        elif jlrts >= 1:
            return 5   # 今日流入
        else:
            return 0
    
    # ==================== P2优化：涨停原因分析 ====================
    
    def _analyze_plate_reason(self, stock_data):
        """
        分析涨停原因（P2优化新增）
        
        根据涨停原因判断是否有硬核逻辑
        
        Returns:
            dict: {reason_text, reason_score, reason_type}
        """
        plate_reason = stock_data.get('plate_reason', '')
        plate_name = stock_data.get('plate_name', '')
        stock_reason = stock_data.get('stock_reason', '')
        
        # 合并所有原因文本
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
        
        # 定义硬核逻辑关键词
        hard_core_keywords = {
            # 业绩相关（最硬核）
            '业绩': 15,
            '预增': 12,
            '扭亏': 12,
            '利润': 10,
            '年报': 8,
            '季报': 8,
            
            # 政策利好（较硬核）
            '政策': 10,
            '利好': 8,
            '扶持': 8,
            '补贴': 7,
            '重组': 10,
            '并购': 10,
            '收购': 8,
            
            # 技术突破（中等）
            '突破': 8,
            '技术': 7,
            '专利': 6,
            '研发': 5,
            
            # 订单/合作（中等）
            '订单': 7,
            '中标': 7,
            '合作': 6,
            '签约': 5,
            
            # 热门概念（一般）
            'AI': 5,
            '人工智能': 5,
            '芯片': 5,
            '新能源': 5,
            '光伏': 4,
            '锂电': 4,
        }
        
        # 纯炒作关键词（扣分）
        hype_keywords = ['炒作', '蹭热点', '概念']
        
        # 计算得分
        score = 0
        matched_reasons = []
        
        reason_lower = reason_text.lower()
        
        for keyword, keyword_score in hard_core_keywords.items():
            if keyword.lower() in reason_lower:
                score += keyword_score
                matched_reasons.append(keyword)
        
        # 检查炒作关键词
        for hype in hype_keywords:
            if hype in reason_text:
                score -= 5
        
        # 判断类型
        if score >= 12:
            reason_type = '硬核逻辑'
        elif score >= 6:
            reason_type = '中等逻辑'
        elif score > 0:
            reason_type = '一般逻辑'
        else:
            reason_type = '纯概念炒作'
        
        # 限制最高分
        score = min(score, 15)
        
        return {
            'reason_text': reason_text[:100] if reason_text else '',
            'reason_score': score,
            'reason_type': reason_type,
            'matched_keywords': matched_reasons
        }
    
    def _find_matching_sector(self, stock_data):
        """
        查找股票对应的热点板块（优化版）
        
        返回匹配度最高的板块及其数据
        """
        stock_code = stock_data.get('code', '')
        plate_name = stock_data.get('plateName', '')
        gl = stock_data.get('gl', '')  # 概念标签
        industry = stock_data.get('industry', '')
        
        hot_sectors = self._get_hot_sectors()
        
        if not hot_sectors:
            return None, None, None
        
        # 将股票的所有标签整合
        stock_tags = set()
        if plate_name:
            stock_tags.add(plate_name.lower())
        if gl:
            for tag in gl.split(','):
                stock_tags.add(tag.strip().lower())
        if industry:
            stock_tags.add(industry.lower())
        
        # 匹配热点板块
        best_match = None
        best_rank = 0
        best_sector_data = None
        
        for i, sector in enumerate(hot_sectors[:15], 1):  # 扩大到前15个
            sector_name = sector.get('bkName', '').lower()
            
            # 检查股票标签是否包含板块名称
            for tag in stock_tags:
                if sector_name in tag or tag in sector_name:
                    if best_rank == 0 or i < best_rank:
                        best_rank = i
                        best_match = sector.get('bkName', '')
                        best_sector_data = sector
                    break
        
        return best_match, best_rank, best_sector_data
    
    def calculate_score(self, stock_data):
        """
        计算股票的综合评分（优化版v3）
        
        评分指标（12个）：
        1. 首次涨停时间
        2. 封成比
        3. 封单金额/流通市值
        4. 连板数 ★新增
        5. 炸板次数 ★新增
        6. 龙虎榜数据
        7. 主力资金净占比
        8. 成交金额
        9. 换手率
        10. 量比
        11. 板块强度 ★优化
        12. 资金流入天数 ★新增
        """
        score = 0.0
        details = {}
        
        try:
            stock_code = stock_data.get('code', '')
            stock_name = stock_data.get('name', '')
            
            # ========== 1. 首次涨停时间 ==========
            first_ceiling_time = stock_data.get('firstCeilingTime', '150000')
            time_minutes = self.client.parse_ceiling_time(first_ceiling_time)
            
            if 570 <= time_minutes <= 600:  # 10:00前
                time_score = 20
            elif 600 < time_minutes <= 630:  # 10:30前
                time_score = 15
            elif 630 < time_minutes <= 660:  # 11:00前
                time_score = 10
            elif 660 < time_minutes <= 720:  # 12:00前
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
            
            # ========== 4. 连板数 ★新增 ==========
            lb_num = stock_data.get('lbNum', 1)
            lb_score = self._calc_lb_num_score(lb_num)
            lb_weighted = lb_score * self.weights.get('lb_num', 0.12) / 0.20
            score += lb_weighted
            details['lb_num'] = lb_num
            details['lb_num_score'] = round(lb_weighted, 2)
            
            # ========== 5. 炸板次数 ★新增 ==========
            bomb_num = stock_data.get('bombNum', 0)
            bomb_score = self._calc_bomb_num_score(bomb_num)
            bomb_weighted = bomb_score * self.weights.get('bomb_num', 0.08) / 0.10
            score += bomb_weighted
            details['bomb_num'] = bomb_num
            details['bomb_num_score'] = round(bomb_weighted, 2)
            
            # ========== 6. 龙虎榜（P1优化：细化评分） ==========
            dragon_detail = self.client.get_dragon_tiger_detail(stock_code, self.date)
            
            if dragon_detail:
                # 龙虎榜详细评分
                buy_amount = 0
                sell_amount = 0
                try:
                    buy_amount = float(dragon_detail.get('buyAmount', 0))
                    sell_amount = float(dragon_detail.get('sellAmount', 0))
                except:
                    pass
                
                # 净买入金额
                net_buy = buy_amount - sell_amount
                
                # 根据净买入金额评分
                if net_buy > 5000:  # 净买入5000万以上
                    dragon_score = 15
                elif net_buy > 2000:  # 净买入2000万以上
                    dragon_score = 12
                elif net_buy > 0:  # 净买入
                    dragon_score = 10
                elif net_buy > -2000:  # 小幅净卖出
                    dragon_score = 5
                else:  # 大幅净卖出
                    dragon_score = 2
                
                details['dragon_tiger'] = True
                details['dragon_tiger_data'] = dragon_detail
                details['dragon_net_buy'] = round(net_buy, 2)
            else:
                dragon_score = 0
                details['dragon_tiger'] = False
                details['dragon_net_buy'] = 0
            
            dragon_weighted = dragon_score * self.weights.get('dragon_tiger', 0.08) / 0.15
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
            
            if 50000 <= amount <= 200000:  # 5亿-20亿
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
            
            # ========== 11. 板块强度 ★优化 ==========
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
            
            # ========== 12. 资金流入天数 ★新增 ==========
            fund_flow_score = self._calc_fund_flow_score(sector_data)
            fund_flow_weighted = fund_flow_score * self.weights.get('fund_flow_days', 0.05) / 0.10
            score += fund_flow_weighted
            details['fund_flow_days'] = sector_data.get('jlrts', 0) if sector_data else 0
            details['fund_flow_days_score'] = round(fund_flow_weighted, 2)
            
            # ========== 13. 涨停原因分析 ★P2优化新增 ==========
            plate_analysis = self._analyze_plate_reason(stock_data)
            plate_reason_score = plate_analysis['reason_score']
            plate_reason_weighted = plate_reason_score * 0.03  # 3%权重
            score += plate_reason_weighted
            details['plate_reason'] = plate_analysis['reason_text']
            details['plate_reason_type'] = plate_analysis['reason_type']
            details['plate_reason_score'] = round(plate_reason_weighted, 2)
            details['plate_reason_keywords'] = plate_analysis.get('matched_keywords', [])
            
            # 汇总
            details['total_score'] = round(score, 2)
            details['stock_name'] = stock_name
            
        except Exception as e:
            print(f"计算评分时出错: {e}")
            import traceback
            traceback.print_exc()
            return (stock_data.get('code', ''), 0, {})
        
        return (stock_data.get('code', ''), round(score, 2), details)
    
    def select_top_stocks(self, stocks, top_n=5):
        """
        选出评分最高的前N名股票（含预过滤）
        """
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
            if score > 0:
                scored_stocks.append({
                    'code': code,
                    'name': stock.get('name', ''),
                    'score': score,
                    'details': details,
                    'raw_data': stock
                })
        
        # 打印过滤统计
        print(f"  过滤掉 {len(filtered_out)} 只股票:")
        print(f"    - ST股: {self.filtered_count['st']} 只")
        print(f"    - 新股: {self.filtered_count['new']} 只")
        print(f"    - 高位板(≥5板): {self.filtered_count['high_board']} 只")
        print(f"    - 多次炸板(≥3次): {self.filtered_count['multi_bomb']} 只")
        print(f"  剩余 {len(scored_stocks)} 只股票参与评分")
        
        # 按评分降序排序
        scored_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_stocks[:top_n]
    
    def save_results(self):
        """保存选出的股票到JSON文件"""
        self._ensure_data_dir()
        
        result_data = {
            'date': self.date,
            'version': 'v3',
            'selected_count': len(self.selected_stocks),
            'stocks': self.selected_stocks,
            'weights': self.weights,
            'emotion': self.emotion,
            'hot_sectors': self.hot_sectors[:10] if self.hot_sectors else [],
            'filter_stats': self.filtered_count
        }
        
        with open(RESULT_FILE, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到: {RESULT_FILE}")
    
    def run_full_analysis(self):
        """运行完整分析流程"""
        print("=" * 70)
        print(f"T01龙头战法 - T日分析 (优化版v3) - {self.date}")
        print("=" * 70)
        
        # 判断是否为交易日
        if not self.client.get_trading_day(self.date):
            print(f"{self.date} 不是交易日，跳过分析")
            return None
        
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
        
        # 获取热点板块
        print(f"\n【步骤3】获取热点板块...")
        self._get_hot_sectors()
        if self.hot_sectors:
            print(f"获取到 {len(self.hot_sectors)} 个热点板块")
        
        # 计算评分并选出前5名（含预过滤）
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
            print(f"\n{i}. {stock['name']}({stock['code']}) - 总分: {stock['score']:.2f}")
            print(f"   ├─ 连板数: {d.get('lb_num', 1)}板 ({d.get('lb_num_score', 0):.2f}分)")
            print(f"   ├─ 炸板次数: {d.get('bomb_num', 0)}次 ({d.get('bomb_num_score', 0):.2f}分)")
            print(f"   ├─ 首次封板: {d.get('first_ceiling_time', '')} ({d.get('first_ceiling_time_score', 0):.2f}分)")
            print(f"   ├─ 封成比: {d.get('seal_ratio', 0):.2f} ({d.get('seal_ratio_score', 0):.2f}分)")
            print(f"   ├─ 热点板块: {d.get('hot_sector_name', '无')} ({d.get('hot_sector_score', 0):.2f}分)")
            print(f"   ├─ 资金流入: {d.get('fund_flow_days', 0)}天 ({d.get('fund_flow_days_score', 0):.2f}分)")
            print(f"   ├─ 主力资金: {d.get('main_net_ratio', 0):.2f}% ({d.get('main_net_ratio_score', 0):.2f}分)")
            print(f"   ├─ 龙虎榜: {'有' if d.get('dragon_tiger') else '无'} ({d.get('dragon_tiger_score', 0):.2f}分)")
            # P2优化：显示涨停原因
            reason_type = d.get('plate_reason_type', '未知')
            reason_score = d.get('plate_reason_score', 0)
            print(f"   └─ 涨停逻辑: {reason_type} ({reason_score:.2f}分)")
        
        # 保存结果
        self.save_results()
        
        return {
            'date': self.date,
            'top_stocks': self.selected_stocks,
            'emotion': self.emotion,
            'hot_sectors': self.hot_sectors[:10] if self.hot_sectors else [],
            'limit_up_stocks': self.limit_up_stocks,
            'filter_stats': self.filtered_count
        }


def main():
    """主函数"""
    analyzer = EveningAnalyzer()
    result = analyzer.run_full_analysis()
    
    if result:
        print("\n" + "=" * 70)
        print("分析完成!")
        print("=" * 70)


if __name__ == "__main__":
    main()
