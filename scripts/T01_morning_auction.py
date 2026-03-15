#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - T+1日竞价分析脚本（增强版）
功能：
1. 获取T日选出的股票
2. 调用增强版竞价API获取实时竞价数据
3. 根据竞价表现重新评分排序
4. 结合风控给出最终买入建议
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
    """T+1日竞价分析器（增强版）"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.risk = RiskController()
        self.feishu = FeishuNotifier()
        
        # 竞价评分权重
        self.auction_weights = {
            'auction_change': 0.20,        # 竞价涨幅
            'auction_amount': 0.15,        # 竞价金额
            'in_hot_auction': 0.15,        # 是否竞价热点股
            'sector_auction_rank': 0.10,   # 所属板块竞价排名
            't_score_weight': 0.40         # T日评分权重
        }
    
    def load_t1_selected_stocks(self, t_date=None):
        """
        加载T日选出的股票
        
        Args:
            t_date: T日日期，如果为None则加载最新的选股记录
        
        Returns:
            dict: 选股记录
        """
        if t_date:
            history_file = os.path.join(DATA_BASE_DIR, "history", f"selection_{t_date}.json")
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        
        # 尝试加载最新的选股记录
        if os.path.exists(RESULT_FILE):
            with open(RESULT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
    
    def get_auction_data(self):
        """
        获取竞价数据
        
        Returns:
            tuple: (竞价板块数据, 竞价个股数据)
        """
        print("\n获取竞价数据...")
        
        # 获取增强版竞价板块数据
        auction_sectors = self.client.get_enhanced_auction_sectors()
        print(f"  竞价热点板块: {len(auction_sectors) if auction_sectors else 0} 个")
        
        # 获取增强版竞价个股数据
        auction_stocks = self.client.get_enhanced_auction_stocks()
        print(f"  竞价热点个股: {len(auction_stocks) if auction_stocks else 0} 只")
        
        return auction_sectors, auction_stocks
    
    def find_stock_in_auction(self, stock_code, auction_stocks):
        """
        在竞价个股中查找指定股票
        
        Args:
            stock_code: 股票代码
            auction_stocks: 竞价个股列表
        
        Returns:
            dict: 竞价数据，如果未找到返回None
        """
        if not auction_stocks:
            return None
        
        for stock in auction_stocks:
            if stock.get('code') == stock_code or stock.get('code', '').startswith(stock_code):
                return stock
        
        return None
    
    def find_sector_in_auction(self, sector_name, auction_sectors):
        """
        在竞价板块中查找指定板块
        
        Args:
            sector_name: 板块名称
            auction_sectors: 竞价板块列表
        
        Returns:
            tuple: (排名, 板块数据)
        """
        if not auction_sectors:
            return None, None
        
        for i, sector in enumerate(auction_sectors, 1):
            if sector.get('bkName') == sector_name or sector_name in sector.get('bkName', ''):
                return i, sector
        
        return None, None
    
    def calculate_auction_score(self, stock, auction_stocks, auction_sectors):
        """
        计算竞价评分
        
        Args:
            stock: T日选出的股票
            auction_stocks: 竞价个股列表
            auction_sectors: 竞价板块列表
        
        Returns:
            dict: 竞价评分详情
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
            'in_hot_auction': False,
            'sector_rank': None
        }
        
        # 1. T日评分贡献
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
                auction_change = float(auction_data.get('changeRatio', 0))
                if auction_change > 5:
                    auction_change_score = 20
                elif auction_change > 3:
                    auction_change_score = 15
                elif auction_change > 0:
                    auction_change_score = 10
                elif auction_change > -3:
                    auction_change_score = 5
                else:
                    auction_change_score = 0
                
                auction_score += auction_change_score * self.auction_weights['auction_change'] / 20
                score_detail['auction_change'] = auction_change
                score_detail['auction_change_score'] = auction_change_score
            except:
                pass
            
            # 竞价金额贡献
            try:
                auction_amount = float(auction_data.get('amount', 0))
                if auction_amount > 100000000:  # 1亿以上
                    amount_score = 15
                elif auction_amount > 50000000:  # 5000万以上
                    amount_score = 10
                elif auction_amount > 10000000:  # 1000万以上
                    amount_score = 5
                else:
                    amount_score = 2
                
                auction_score += amount_score * self.auction_weights['auction_amount'] / 15
                score_detail['auction_amount'] = auction_amount
                score_detail['auction_amount_score'] = amount_score
            except:
                pass
            
            # 竞价热点股加分
            auction_score += 20 * self.auction_weights['in_hot_auction']
        
        # 3. 检查所属板块竞价排名
        sector_name = stock.get('details', {}).get('hot_sector_name', '')
        if sector_name and auction_sectors:
            rank, sector_data = self.find_sector_in_auction(sector_name, auction_sectors)
            if rank:
                score_detail['sector_rank'] = rank
                score_detail['sector_data'] = sector_data
                
                # 板块排名贡献
                if rank <= 3:
                    sector_score = 10
                elif rank <= 5:
                    sector_score = 8
                elif rank <= 10:
                    sector_score = 5
                else:
                    sector_score = 2
                
                auction_score += sector_score * self.auction_weights['sector_auction_rank'] / 10
                score_detail['sector_score'] = sector_score
        
        score_detail['auction_score'] = round(auction_score, 2)
        score_detail['final_score'] = round(t_score_contrib + auction_score, 2)
        
        return score_detail
    
    def analyze_selected_stocks(self, t_date=None):
        """
        分析T日选出的股票在T+1日竞价中的表现
        
        Args:
            t_date: T日日期
        
        Returns:
            dict: 分析结果
        """
        print("=" * 70)
        print("T01龙头战法 - T+1日竞价分析（增强版）")
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
        
        for i, stock in enumerate(selected_stocks, 1):
            if isinstance(stock, dict):
                print(f"    {i}. {stock.get('name')}({stock.get('code')}) - T日评分: {stock.get('score', 0):.2f}")
        
        # 2. 获取竞价数据
        print("\n【步骤2】获取竞价数据")
        print("-" * 70)
        
        auction_sectors, auction_stocks = self.get_auction_data()
        
        if auction_sectors:
            print("\n  竞价热点板块TOP5:")
            for i, sector in enumerate(auction_sectors[:5], 1):
                print(f"    {i}. {sector.get('bkName', 'N/A')}")
        
        if auction_stocks:
            print("\n  竞价热点个股TOP5:")
            for i, stock in enumerate(auction_stocks[:5], 1):
                print(f"    {i}. {stock.get('name', 'N/A')}({stock.get('code', 'N/A')})")
        
        # 3. 计算竞价评分
        print("\n【步骤3】计算竞价评分")
        print("-" * 70)
        
        scored_stocks = []
        
        for stock in selected_stocks:
            if isinstance(stock, dict):
                score_detail = self.calculate_auction_score(stock, auction_stocks, auction_sectors)
                scored_stocks.append(score_detail)
                
                print(f"\n  {score_detail['stock_name']}({score_detail['stock_code']})")
                print(f"    T日评分贡献: {score_detail.get('t_score_contrib', 0):.2f}")
                print(f"    竞价评分: {score_detail['auction_score']:.2f}")
                print(f"    是否竞价热点: {'是' if score_detail['in_hot_auction'] else '否'}")
                if score_detail.get('sector_rank'):
                    print(f"    板块竞价排名: 第{score_detail['sector_rank']}名")
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
                'recommended_position': round(rec_position, 2),
                'action': '买入' if rec_position > 0 else '观望'
            }
            
            result['buy_recommendations'].append(rec)
            
            action_icon = '🟢' if rec['action'] == '买入' else '⚪'
            hot_icon = '🔥' if stock['in_hot_auction'] else ''
            
            print(f"\n  {action_icon} 第{i}名: {stock['stock_name']}({stock['stock_code']}) {hot_icon}")
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
        message += "━" * 30 + "\n"
        message += "【买入建议】\n"
        
        for rec in recs[:3]:
            if rec['action'] == '买入':
                hot = '🔥' if rec['in_hot_auction'] else ''
                message += f"\n  {rec['rank']}. {rec['stock_name']}{hot}\n"
                message += f"     评分: {rec['final_score']:.2f}\n"
                message += f"     建议仓位: {rec['recommended_position']*100:.1f}%\n"
        
        message += "\n━" * 30 + "\n"
        message += "⚠️ 竞价数据仅供参考，请结合盘面谨慎决策"
        
        try:
            # 使用正确的chat_id
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
