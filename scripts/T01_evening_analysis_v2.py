#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01任务 - 龙头战法 - T日晚上分析脚本 (进化版)
功能：
1. 分析当日涨停股，选出前5名作为次日观察标的
2. 使用AI进化模块的动态权重
3. 使用热点板块API判断板块热度
4. 集成情绪周期进行风控
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

class EveningAnalyzer:
    """T日晚间分析器"""
    
    def __init__(self, date=None):
        self.client = StockAPIClient()
        self.ai = AIEvolution()
        self.date = date or self.client.get_today_date()
        self.weights = self.ai.get_current_weights()
        self.hot_sectors = None
        self.emotion = None
        self.limit_up_stocks = None
        self.selected_stocks = []
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
    
    def _get_hot_sectors(self):
        """获取热点板块"""
        if self.hot_sectors is None:
            self.hot_sectors = self.client.get_hot_sectors(self.date)
        return self.hot_sectors
    
    def _get_emotion(self):
        """获取情绪周期"""
        if self.emotion is None:
            self.emotion = self.client.get_emotion_cycle(self.date)
        return self.emotion
    
    def _is_in_hot_sector(self, stock_data):
        """
        判断股票是否属于当日热点板块
        
        使用热点板块API匹配，而不是简单的涨停主题
        """
        stock_code = stock_data.get('code', '')
        plate_name = stock_data.get('plateName', '')
        gl = stock_data.get('gl', '')  # 概念标签
        industry = stock_data.get('industry', '')
        
        hot_sectors = self._get_hot_sectors()
        
        if not hot_sectors:
            return False, 0, ''
        
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
        
        for i, sector in enumerate(hot_sectors[:10], 1):  # 只看前10个热点板块
            sector_name = sector.get('bkName', '').lower()
            
            # 检查股票标签是否包含板块名称
            for tag in stock_tags:
                if sector_name in tag or tag in sector_name:
                    if best_rank == 0 or i < best_rank:
                        best_rank = i
                        best_match = sector
                    break
        
        if best_match:
            # 根据排名计算得分，第1名最高分
            sector_strength = best_match.get('ratio', 0)
            return True, 11 - best_rank, best_match.get('bkName', '')
        
        return False, 0, ''
    
    def calculate_score(self, stock_data):
        """
        计算股票的综合评分（使用动态权重）
        
        根据以下指标计算得分：
        1. 首次涨停时间（越早越好）
        2. 封成比（越大越好）
        3. 封单金额/流通市值（越大越好）
        4. 龙虎榜数据
        5. 主力资金净占比
        6. 成交金额
        7. 换手率
        8. 量比
        9. 是否属于当日热点板块
        
        每个指标的权重由AI进化模块动态调整
        """
        score = 0.0
        details = {}
        max_score = 100.0
        
        try:
            stock_code = stock_data.get('code', '')
            
            # 1. 首次涨停时间（越早越好）
            # 基础分：满分20分
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
            
            time_weighted = time_score * self.weights.get('first_limit_time', 0.15) / 0.20
            score += time_weighted
            details['first_ceiling_time'] = first_ceiling_time
            details['first_ceiling_time_score'] = round(time_weighted, 2)
            
            # 2. 封成比（越大越好）
            seal_ratio = self.client.calculate_seal_ratio(stock_data)
            if seal_ratio >= 10:
                seal_score = 15
            elif seal_ratio >= 5:
                seal_score = 10
            elif seal_ratio >= 3:
                seal_score = 5
            else:
                seal_score = 0
            
            seal_weighted = seal_score * self.weights.get('seal_ratio', 0.12) / 0.15
            score += seal_weighted
            details['seal_ratio'] = round(seal_ratio, 2)
            details['seal_ratio_score'] = round(seal_weighted, 2)
            
            # 3. 封单金额/流通市值
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
            
            # 4. 龙虎榜数据
            top_list_data = self.client.check_stock_in_dragon_tiger(stock_code, self.date)
            dragon_score = 10 if top_list_data else 0
            dragon_weighted = dragon_score * self.weights.get('dragon_tiger', 0.10) / 0.10
            score += dragon_weighted
            details['dragon_tiger'] = True if top_list_data else False
            details['dragon_tiger_score'] = round(dragon_weighted, 2)
            
            # 5. 主力资金净占比
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
            
            fund_weighted = fund_score * self.weights.get('main_fund_ratio', 0.12) / 0.10
            score += fund_weighted
            details['main_net_ratio'] = round(main_net_ratio, 2)
            details['main_net_ratio_score'] = round(fund_weighted, 2)
            
            # 6. 成交金额
            amount = 0
            try:
                amount = float(stock_data.get('amount', 0)) / 10000  # 转换为万
            except:
                pass
            
            if 50000 <= amount <= 200000:  # 5亿-20亿
                amount_score = 10
            elif 20000 <= amount <= 500000:
                amount_score = 5
            else:
                amount_score = 0
            
            amount_weighted = amount_score * self.weights.get('amount', 0.08) / 0.10
            score += amount_weighted
            details['amount'] = round(amount, 0)
            details['amount_score'] = round(amount_weighted, 2)
            
            # 7. 换手率
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
            
            turnover_weighted = turnover_score * self.weights.get('turnover_rate', 0.10) / 0.10
            score += turnover_weighted
            details['turnover_rate'] = round(turnover_rate, 2)
            details['turnover_rate_score'] = round(turnover_weighted, 2)
            
            # 8. 量比
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
            
            vol_weighted = vol_score * self.weights.get('volume_ratio', 0.13) / 0.10
            score += vol_weighted
            details['volume_ratio'] = round(volume_ratio, 2)
            details['volume_ratio_score'] = round(vol_weighted, 2)
            
            # 9. 热点板块（使用API判断）
            is_hot, hot_rank, hot_sector_name = self._is_in_hot_sector(stock_data)
            if is_hot:
                hot_score = hot_rank  # 1-10分
            else:
                hot_score = 0
            
            hot_weighted = hot_score * self.weights.get('hot_sector', 0.10) / 0.10
            score += hot_weighted
            details['is_hot_sector'] = is_hot
            details['hot_sector_name'] = hot_sector_name
            details['hot_sector_rank'] = hot_rank
            details['hot_sector_score'] = round(hot_weighted, 2)
            
            details['total_score'] = round(score, 2)
            
        except Exception as e:
            print(f"计算评分时出错: {e}")
            import traceback
            traceback.print_exc()
            return (stock_data.get('code', ''), 0, {})
        
        return (stock_data.get('code', ''), round(score, 2), details)
    
    def select_top_stocks(self, stocks, top_n=5):
        """
        选出评分最高的前N名股票
        
        Args:
            stocks: 股票列表
            top_n: 选出前N名
        
        Returns:
            list: 选出的股票列表
        """
        scored_stocks = []
        
        for stock in stocks:
            code, score, details = self.calculate_score(stock)
            if score > 0:
                scored_stocks.append({
                    'code': code,
                    'name': stock.get('name', ''),
                    'score': score,
                    'details': details,
                    'raw_data': stock
                })
        
        # 按评分降序排序
        scored_stocks.sort(key=lambda x: x['score'], reverse=True)
        
        return scored_stocks[:top_n]
    
    def get_risk_advice(self):
        """
        根据情绪周期生成风控建议
        
        Returns:
            dict: 风控建议
        """
        emotion = self._get_emotion()
        
        if not emotion:
            return {
                'level': 'unknown',
                'advice': '无法获取情绪周期数据，建议谨慎操作',
                'position': '50%'
            }
        
        score = emotion.get('score', 50)
        stage = emotion.get('stage', 'unknown')
        
        if score < 20:
            return {
                'level': 'critical',
                'advice': '市场情绪冰点，建议空仓观望',
                'position': '0%',
                'reason': f'情绪评分{score}分，处于冰点期'
            }
        elif score < 40:
            return {
                'level': 'high',
                'advice': '市场情绪低迷，建议轻仓试错',
                'position': '20%',
                'reason': f'情绪评分{score}分，处于低迷期'
            }
        elif score < 60:
            return {
                'level': 'medium',
                'advice': '市场情绪平稳，建议正常操作',
                'position': '50%',
                'reason': f'情绪评分{score}分，处于平稳期'
            }
        elif score < 80:
            return {
                'level': 'low',
                'advice': '市场情绪良好，可积极操作',
                'position': '80%',
                'reason': f'情绪评分{score}分，处于良好期'
            }
        else:
            return {
                'level': 'very_low',
                'advice': '市场情绪高涨，可满仓操作但需警惕回调',
                'position': '100%',
                'reason': f'情绪评分{score}分，处于高涨期'
            }
    
    def save_results(self):
        """保存选出的股票到JSON文件"""
        self._ensure_data_dir()
        
        result_data = {
            'date': self.date,
            'selected_count': len(self.selected_stocks),
            'stocks': self.selected_stocks,
            'weights_version': self.ai.current_weights.get('version', 1),
            'emotion': self.emotion,
            'hot_sectors': self.hot_sectors[:10] if self.hot_sectors else []
        }
        
        with open(RESULT_FILE, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        
        print(f"结果已保存到: {RESULT_FILE}")
    
    def run_full_analysis(self):
        """
        运行完整分析流程
        
        Returns:
            dict: 分析结果
        """
        print(f"\n开始T日分析: {self.date}")
        print(f"使用权重版本: v{self.ai.current_weights.get('version', 1)}")
        
        # 判断是否为交易日
        if not self.client.get_trading_day(self.date):
            print(f"{self.date} 不是交易日，跳过分析")
            return None
        
        # 获取涨停股票
        print(f"\n正在获取涨停股票...")
        self.limit_up_stocks = self.client.get_limit_up_stocks(self.date)
        
        if not self.limit_up_stocks:
            print("未获取到涨停股票数据")
            return None
        
        print(f"获取到 {len(self.limit_up_stocks)} 只涨停股票")
        
        # 获取情绪周期
        print(f"\n正在获取情绪周期...")
        self._get_emotion()
        if self.emotion:
            print(f"情绪评分: {self.emotion.get('score', 'N/A')} 分")
            print(f"周期阶段: {self.emotion.get('stage', 'N/A')}")
        
        # 获取热点板块
        print(f"\n正在获取热点板块...")
        self._get_hot_sectors()
        if self.hot_sectors:
            print(f"获取到 {len(self.hot_sectors)} 个热点板块")
            for i, sector in enumerate(self.hot_sectors[:5], 1):
                print(f"  {i}. {sector.get('bkName', '')} - 强度: {sector.get('ratio', 0)}")
        
        # 计算评分并选出前5名
        print(f"\n正在计算评分...")
        self.selected_stocks = self.select_top_stocks(self.limit_up_stocks, top_n=5)
        
        if not self.selected_stocks:
            print("没有符合条件的股票")
            return None
        
        print(f"\n选出了 {len(self.selected_stocks)} 只股票:")
        for i, stock in enumerate(self.selected_stocks, 1):
            print(f"  {i}. {stock['name']}({stock['code']}) - 评分: {stock['score']:.2f}")
        
        # 获取风控建议
        risk_advice = self.get_risk_advice()
        print(f"\n风控建议: {risk_advice['advice']}")
        print(f"建议仓位: {risk_advice['position']}")
        
        # 保存结果
        self.save_results()
        
        return {
            'date': self.date,
            'top_stocks': self.selected_stocks,
            'emotion': self.emotion,
            'hot_sectors': self.hot_sectors[:10] if self.hot_sectors else [],
            'risk_advice': risk_advice,
            'limit_up_stocks': self.limit_up_stocks,
            'weights_version': self.ai.current_weights.get('version', 1)
        }


def main():
    """主函数"""
    print("=" * 60)
    print(f"T01龙头战法 - T日分析 (进化版) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    analyzer = EveningAnalyzer()
    result = analyzer.run_full_analysis()
    
    if result:
        print("\n" + "=" * 60)
        print("分析完成!")
        print("=" * 60)


if __name__ == "__main__":
    main()
