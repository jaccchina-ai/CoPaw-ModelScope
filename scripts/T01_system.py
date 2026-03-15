#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 完整流程集成脚本
整合：
1. T日晚间分析
2. T+1日竞价分析
3. 数据存储
4. 交易跟踪
5. AI进化优化
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/mnt/workspace/working/scripts')

from T01_evening_analysis import EveningAnalyzer
from T01_morning_analysis import MorningAnalyzer
from T01_data_storage import DataStorage, TradeTracker
from T01_ai_evolution import AIEvolution
from feishu_notifier import FeishuNotifier

class T01System:
    """T01龙头战法完整系统"""
    
    def __init__(self):
        self.storage = DataStorage()
        self.tracker = TradeTracker()
        self.ai = AIEvolution()
        self.feishu = FeishuNotifier()
    
    def run_evening_analysis(self, date=None):
        """
        运行T日晚间分析
        
        Args:
            date: 指定日期，默认今天
        """
        print("\n" + "=" * 60)
        print("T01龙头战法 - T日晚间分析")
        print("=" * 60)
        
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"\n分析日期: {date}")
        
        # 获取当前权重
        weights = self.ai.get_current_weights()
        print(f"使用权重版本: v{self.ai.current_weights['version']}")
        
        # 运行分析
        analyzer = EveningAnalyzer(date)
        result = analyzer.run_full_analysis()
        
        if result is None:
            print("分析失败或无涨停股")
            return None
        
        # 保存选股记录
        self.storage.save_selected_stocks(
            date,
            result['top_stocks'],
            result.get('emotion'),
            result.get('hot_sectors')
        )
        
        # 保存每日数据
        if result.get('limit_up_stocks'):
            self.storage.save_daily_data(date, 'limit_up', result['limit_up_stocks'])
        
        if result.get('hot_sectors'):
            self.storage.save_daily_data(date, 'hot_sectors', result['hot_sectors'])
        
        if result.get('emotion'):
            self.storage.save_daily_data(date, 'emotion', result['emotion'])
        
        # 发送飞书通知
        try:
            self.feishu.send_evening_report(result)
        except Exception as e:
            print(f"飞书通知失败: {e}")
        
        return result
    
    def run_morning_analysis(self, t_date=None, t1_date=None):
        """
        运行T+1日竞价分析
        
        Args:
            t_date: T日日期
            t1_date: T+1日日期
        """
        print("\n" + "=" * 60)
        print("T01龙头战法 - T+1日竞价分析")
        print("=" * 60)
        
        if t_date is None or t1_date is None:
            print("需要提供T日和T+1日日期")
            return None
        
        print(f"\nT日: {t_date}, T+1日: {t1_date}")
        
        # 运行分析
        analyzer = MorningAnalyzer(t_date, t1_date)
        result = analyzer.run_full_analysis()
        
        if result is None:
            print("分析失败")
            return None
        
        # 保存竞价数据
        self.storage.save_daily_data(t1_date, 'morning_auction', result)
        
        # 发送飞书通知
        try:
            self.feishu.send_morning_report(result)
        except Exception as e:
            print(f"飞书通知失败: {e}")
        
        return result
    
    def track_trades(self, t_date, t1_date, t2_date):
        """
        跟踪交易盈亏
        
        Args:
            t_date: T日（选股日）
            t1_date: T+1日（买入日）
            t2_date: T+2日（卖出日）
        """
        print("\n" + "=" * 60)
        print("T01龙头战法 - 交易跟踪")
        print("=" * 60)
        
        # 获取T日选股记录
        selection = self.storage.get_selected_stocks(t_date)
        
        if selection is None:
            print(f"未找到T日({t_date})的选股记录")
            return None
        
        stocks = selection.get('stocks', [])
        print(f"\n跟踪 {len(stocks)} 只股票的交易结果")
        
        results = []
        
        for stock in stocks:
            trade = self.tracker.track_trade(
                stock['code'],
                stock['name'],
                t_date,
                t1_date,
                t2_date,
                stock['score']
            )
            
            if trade:
                results.append(trade)
        
        # 打印统计
        stats = self.tracker.get_stats()
        print(f"\n当前统计:")
        print(f"  总交易: {stats['total_trades']} 笔")
        print(f"  盈利: {stats['win_trades']} 笔")
        print(f"  亏损: {stats['lose_trades']} 笔")
        print(f"  胜率: {stats['win_rate']}%")
        print(f"  平均盈亏: {stats['avg_profit']}%")
        
        return results
    
    def run_ai_evolution(self):
        """运行AI进化优化"""
        print("\n" + "=" * 60)
        print("T01龙头战法 - AI进化优化")
        print("=" * 60)
        
        # 策略反思
        reflection = self.ai.reflect_on_strategy()
        
        # 自动进化
        result = self.ai.auto_evolve(min_trades=20)
        
        print(f"\n进化结果: {result['message']}")
        
        return result
    
    def generate_report(self):
        """生成完整报告"""
        print(self.ai.generate_report())
        
        stats = self.tracker.get_stats()
        
        print("\n【近期交易记录】")
        recent_trades = self.tracker.get_recent_trades(10)
        
        for trade in recent_trades:
            status = "✅盈利" if trade['is_win'] else "❌亏损"
            print(f"  {trade['stock_name']}({trade['stock_code']}) "
                  f"T:{trade['t_date']} 评分:{trade['t_score']:.2f} "
                  f"{status} {trade['profit_pct']:+.2f}%")
    
    def run_full_cycle(self, t_date=None):
        """
        运行完整周期
        
        当天晚上：T日分析
        次日早上：T+1竞价分析
        次次日收盘后：跟踪交易盈亏
        """
        if t_date is None:
            t_date = datetime.now().strftime('%Y-%m-%d')
        
        print("\n" + "=" * 70)
        print("T01龙头战法 - 完整周期运行")
        print("=" * 70)
        print(f"\n参考日期: {t_date}")
        print("\n完整周期包括:")
        print("  1. T日晚间分析 → 选出股票")
        print("  2. T+1日竞价分析 → 买入决策")
        print("  3. T+2日收盘后 → 跟踪盈亏")
        print("  4. 数据积累足够后 → AI进化优化")
        
        return {
            't_date': t_date,
            'next_steps': [
                f"晚间运行: python T01_system.py --mode evening --date {t_date}",
                f"次日早上: python T01_system.py --mode morning --t-date {t_date} --t1-date <T+1>",
                f"T+2收盘后: python T01_system.py --mode track --t-date {t_date} --t1-date <T+1> --t2-date <T+2>",
                f"定期运行: python T01_system.py --mode evolve"
            ]
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='T01龙头战法系统')
    parser.add_argument('--mode', type=str, 
                        choices=['evening', 'morning', 'track', 'evolve', 'report', 'cycle'],
                        default='report', help='运行模式')
    parser.add_argument('--date', type=str, help='指定日期')
    parser.add_argument('--t-date', type=str, help='T日日期')
    parser.add_argument('--t1-date', type=str, help='T+1日日期')
    parser.add_argument('--t2-date', type=str, help='T+2日日期')
    
    args = parser.parse_args()
    
    system = T01System()
    
    if args.mode == 'evening':
        system.run_evening_analysis(args.date)
    
    elif args.mode == 'morning':
        system.run_morning_analysis(args.t_date, args.t1_date)
    
    elif args.mode == 'track':
        if not all([args.t_date, args.t1_date, args.t2_date]):
            print("错误: track模式需要提供 --t-date, --t1-date, --t2-date")
            return
        system.track_trades(args.t_date, args.t1_date, args.t2_date)
    
    elif args.mode == 'evolve':
        system.run_ai_evolution()
    
    elif args.mode == 'report':
        system.generate_report()
    
    elif args.mode == 'cycle':
        result = system.run_full_cycle(args.date)
        print("\n后续步骤:")
        for step in result['next_steps']:
            print(f"  {step}")


if __name__ == "__main__":
    main()
