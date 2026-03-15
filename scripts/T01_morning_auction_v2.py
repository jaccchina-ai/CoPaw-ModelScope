#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - T+1日竞价分析脚本（P1优化版）
功能：
1. 获取T日选出的股票
2. 调用增强版竞价API获取实时竞价数据
3. 新增：竞价抢筹数据分析
4. 根据竞价表现重新评分排序
5. 结合风控给出最终买入建议
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, '/mnt/workspace/working/scripts')

from stockapi_client import StockAPIClient
from T01_risk_controller import RiskController
from feishu_notifier import FeishuNotifier

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
RESULT_FILE = os.path.join(DATA_BASE_DIR, "selected_stocks.json")
AUCTION_RESULT_FILE = os.path.join(DATA_BASE_DIR, "auction_result.json")


class MorningAuctionAnalyzer:
    """T+1日竞价分析器（P1优化版）"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.risk = RiskController()
        self.feishu = FeishuNotifier()
        
        # 竞价评分权重（优化后）
        self.auction_weights = {
            'auction_change': 0.15,        # 竞价涨幅
            'auction_amount': 0.12,        # 竞价金额
            'in_hot_auction': 0.12,        # 是否竞价热点股
            'robbing_score': 0.15,         # ★新增 竞价抢筹评分
            'sector_auction_rank': 0.08,   # 所属板块竞价排名
            'open_position': 0.08,         # ★新增 开盘位置评分
            't_score_weight': 0.30         # T日评分权重（降权）
        }
    
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
    
    def get_auction_data(self):
        """获取竞价数据（增强版）"""
        print("\n获取竞价数据...")
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 1. 获取竞价板块数据
        try:
            auction_sectors = self.client.get_auction_sectors_enhanced(today, today, type=1)
        except:
            auction_sectors = []
        print(f"  竞价热点板块(看多): {len(auction_sectors) if auction_sectors else 0} 个")
        
        # 2. 获取竞价个股数据
        try:
            auction_stocks = self.client.get_enhanced_auction_stocks()
        except:
            auction_stocks = []
        print(f"  竞价热点个股: {len(auction_stocks) if auction_stocks else 0} 只")
        
        # 3. ★新增 获取竞价抢筹数据
        try:
            robbing_data = self.client.get_auction_robbing(today, period=0, type=1)
        except:
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
        """
        ★新增：在竞价抢筹榜中查找股票
        
        Returns:
            dict: 抢筹数据，包含抢筹涨幅、成交额等
        """
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
        """
        ★新增：计算开盘位置评分
        
        Args:
            open_change: 开盘涨幅（%）
        
        Returns:
            float: 评分
        """
        # 一字板（买不进）
        if open_change >= 9.8:
            return 0
        # 高开太多（追高风险大）
        elif open_change >= 7:
            return 3
        # 正常高开（理想状态）
        elif open_change >= 3:
            return 10
        # 小幅高开
        elif open_change >= 0:
            return 7
        # 低开（走弱信号）
        else:
            return 0
    
    def calc_robbing_score(self, robbing_data):
        """
        ★新增：计算竞价抢筹评分
        
        Args:
            robbing_data: 抢筹数据
        
        Returns:
            float: 评分
        """
        if not robbing_data:
            return 0
        
        score = 0
        
        # 1. 抢筹涨幅
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
        
        # 2. 抢筹委托金额
        qcwtje = 0
        try:
            qcwtje = float(robbing_data.get('qcwtje', 0))
        except:
            pass
        
        if qcwtje >= 100000000:  # 1亿以上
            score += 5
        elif qcwtje >= 50000000:  # 5000万以上
            score += 3
        elif qcwtje >= 10000000:  # 1000万以上
            score += 2
        
        return min(score, 10)  # 最高10分
    
    def calculate_auction_score(self, stock, auction_stocks, auction_sectors, robbing_data):
        """
        计算竞价评分（P1优化版）
        
        新增：
        - 竞价抢筹评分
        - 开盘位置评分
        """
        stock_code = stock.get('code', '')
        t_score = stock.get('score', 0)
        
        score_detail = {
            'stock_code': stock_code,
            'stock_name': stock.get('name', ''),
            't_score': t_score,
            'auction_score': 0,
            'final_score': 0,
            'auction_data': None,
            'robbing_data': None,
            'in_hot_auction': False,
            'sector_rank': None
        }
        
        # 1. T日评分贡献（降权到30%）
        t_score_contrib = t_score * self.auction_weights['t_score_weight'] / 100
        score_detail['t_score_contrib'] = round(t_score_contrib, 2)
        
        auction_score = 0
        
        # 2. 检查是否在竞价热点个股中
        auction_data = self.find_stock_in_auction(stock_code, auction_stocks)
        
        if auction_data:
            score_detail['auction_data'] = auction_data
            score_detail['in_hot_auction'] = True
            
            # 竞价涨幅贡献
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
            
            # 竞价金额贡献
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
            
            # ★新增 开盘位置评分
            try:
                open_change = float(auction_data.get('changeRatio', 0) or auction_data.get('jjzf', 0))
                open_score = self.calc_open_position_score(open_change)
                auction_score += open_score * self.auction_weights['open_position'] / 10
                score_detail['open_change'] = open_change
                score_detail['open_position_score'] = open_score
            except:
                pass
        
        # 3. ★新增 竞价抢筹评分
        stock_robbing = self.find_stock_in_robbing(stock_code, robbing_data)
        
        if stock_robbing:
            score_detail['robbing_data'] = stock_robbing
            robbing_score = self.calc_robbing_score(stock_robbing)
            auction_score += robbing_score * self.auction_weights['robbing_score'] / 10
            score_detail['robbing_score'] = robbing_score
            score_detail['robbing_rank'] = stock_robbing.get('type', 0)
        else:
            score_detail['robbing_score'] = 0
        
        # 4. 检查所属板块竞价排名
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
        
        return score_detail
    
    def analyze_selected_stocks(self, t_date=None):
        """分析T日选出的股票在T+1日竞价中的表现"""
        
        print("=" * 70)
        print("T01龙头战法 - T+1日竞价分析（P1优化版）")
        print("=" * 70)
        
        # 1. 加载T日选股记录
        print("\n【步骤1】加载T日选股记录")
        print("-" * 70)
        
        selection = self.load_t1_selected_stocks(t_date)
        
        if not selection:
            print("未找到T日选股记录")
            return None
        
        t_date = selection.get('date', 'Unknown')
        selected_stocks = selection.get('stocks', selection.get('top_stocks', []))
        
        print(f"  T日: {t_date}")
        print(f"  选出股票: {len(selected_stocks)} 只")
        
        # 2. 获取竞价数据
        print("\n【步骤2】获取竞价数据")
        print("-" * 70)
        
        auction_sectors, auction_stocks, robbing_data = self.get_auction_data()
        
        if auction_sectors:
            print("\n  竞价热点板块TOP5:")
            for i, sector in enumerate(auction_sectors[:5], 1):
                print(f"    {i}. {sector.get('bkName', 'N/A')} - 竞价涨幅: {sector.get('jjzf', 0)}%")
        
        if robbing_data:
            print("\n  竞价抢筹榜TOP5:")
            for i, item in enumerate(robbing_data[:5], 1):
                print(f"    {i}. {item.get('name', 'N/A')}({item.get('code', 'N/A')}) - 抢筹涨幅: {item.get('qczf', 0)}%")
        
        # 3. 计算竞价评分
        print("\n【步骤3】计算竞价评分")
        print("-" * 70)
        
        scored_stocks = []
        
        for stock in selected_stocks:
            if isinstance(stock, dict):
                score_detail = self.calculate_auction_score(
                    stock, auction_stocks, auction_sectors, robbing_data
                )
                scored_stocks.append(score_detail)
                
                print(f"\n  {score_detail['stock_name']}({score_detail['stock_code']})")
                print(f"    T日评分贡献: {score_detail.get('t_score_contrib', 0):.2f}")
                print(f"    竞价评分: {score_detail['auction_score']:.2f}")
                print(f"    是否竞价热点: {'是' if score_detail['in_hot_auction'] else '否'}")
                if score_detail.get('robbing_data'):
                    print(f"    ★竞价抢筹: 是 (评分: {score_detail.get('robbing_score', 0)})")
                print(f"    → 最终评分: {score_detail['final_score']:.2f}")
        
        # 4. 排序
        scored_stocks.sort(key=lambda x: x['final_score'], reverse=True)
        
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
            't1_date': datetime.now().strftime('%Y-%m-%d'),
            'analysis_time': datetime.now().isoformat(),
            'risk_assessment': {
                'trading_allowed': risk_result['trading_allowed'],
                'position_limit': risk_result['final_position_limit']
            },
            'auction_sectors': auction_sectors[:10] if auction_sectors else [],
            'auction_stocks_count': len(auction_stocks) if auction_stocks else 0,
            'robbing_count': len(robbing_data) if robbing_data else 0,
            'buy_recommendations': []
        }
        
        position_limit = risk_result['final_position_limit']
        
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
                'in_hot_auction': stock['in_hot_auction'],
                'has_robbing': stock.get('robbing_data') is not None,
                'recommended_position': round(rec_position, 2),
                'action': '买入' if rec_position > 0 else '观望'
            }
            
            result['buy_recommendations'].append(rec)
            
            action_icon = '🟢' if rec['action'] == '买入' else '⚪'
            hot_icon = '🔥' if stock['in_hot_auction'] else ''
            robbing_icon = '💰' if stock.get('robbing_data') else ''
            
            print(f"\n  {action_icon} 第{i}名: {stock['stock_name']}({stock['stock_code']}) {hot_icon}{robbing_icon}")
            print(f"      T日评分: {stock['t_score']:.2f} → 竞价评分: {stock['auction_score']:.2f}")
            print(f"      最终评分: {stock['final_score']:.2f}")
            print(f"      建议仓位: {rec['recommended_position']*100:.1f}%")
            print(f"      操作建议: {rec['action']}")
        
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
        
        message = f"🔔 T01龙头战法 - T+1日竞价分析\n\n"
        message += f"分析时间: {result['t1_date']} 9:26\n"
        message += f"T日选股: {result['t_date']}\n\n"
        message += "━" * 30 + "\n"
        message += "【风控评估】\n"
        message += f"  允许交易: {'✅' if risk['trading_allowed'] else '❌'}\n"
        message += f"  最大仓位: {risk['position_limit']*100:.0f}%\n\n"
        message += f"【竞价数据】\n"
        message += f"  竞价抢筹股: {result.get('robbing_count', 0)} 只\n\n"
        message += "━" * 30 + "\n"
        message += "【买入建议】\n"
        
        for rec in recs[:3]:
            if rec['action'] == '买入':
                hot = '🔥' if rec['in_hot_auction'] else ''
                robbing = '💰' if rec['has_robbing'] else ''
                message += f"\n  {rec['rank']}. {rec['stock_name']}{hot}{robbing}\n"
                message += f"     评分: {rec['final_score']:.2f}\n"
                message += f"     建议仓位: {rec['recommended_position']*100:.1f}%\n"
        
        message += "\n━" * 30 + "\n"
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
    
    parser = argparse.ArgumentParser(description='T01龙头战法 - T+1日竞价分析')
    parser.add_argument('--t-date', type=str, help='T日日期')
    
    args = parser.parse_args()
    
    analyzer = MorningAuctionAnalyzer()
    result = analyzer.analyze_selected_stocks(args.t_date)
    
    if result:
        print("\n" + "=" * 70)
        print("竞价分析完成!")
        print("=" * 70)


if __name__ == "__main__":
    main()
