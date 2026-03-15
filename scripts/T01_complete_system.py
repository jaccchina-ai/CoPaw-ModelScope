#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 完整系统入口（整合风控）
整合：
1. T日晚间分析
2. T+1日竞价分析
3. 数据存储
4. 交易跟踪
5. AI进化优化
6. 多层风控系统
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/mnt/workspace/working/scripts')

from T01_evening_analysis_v2 import EveningAnalyzer
from T01_data_storage import DataStorage, TradeTracker
from T01_ai_evolution import AIEvolution
from T01_risk_controller import RiskController
from feishu_notifier import FeishuNotifier


class T01CompleteSystem:
    """T01龙头战法完整系统"""
    
    def __init__(self):
        self.storage = DataStorage()
        self.tracker = TradeTracker()
        self.ai = AIEvolution()
        self.risk = RiskController()
        self.feishu = FeishuNotifier()
    
    def run_evening_analysis(self, date=None):
        """
        运行T日晚间分析（含风控）
        
        Args:
            date: 指定日期，默认今天
        """
        print("\n" + "=" * 70)
        print("T01龙头战法 - T日晚间分析（风控版）")
        print("=" * 70)
        
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        # 先进行风控评估
        print(f"\n【风控评估】分析日期: {date}")
        risk_result = self.risk.full_risk_assessment(date)
        
        if not risk_result['trading_allowed']:
            print(f"\n⛔ 风控提示: 当前不建议交易")
            print(f"   原因: {risk_result['recommendation']}")
            
            # 发送风控警告
            self._send_risk_alert(risk_result)
            return None
        
        print(f"\n✅ 风控通过，建议仓位: {risk_result['final_position_limit']*100:.0f}%")
        
        # 运行选股分析
        analyzer = EveningAnalyzer(date)
        result = analyzer.run_full_analysis()
        
        if result is None:
            print("分析失败或无涨停股")
            return None
        
        # 添加风控信息到结果
        result['risk_assessment'] = risk_result
        
        # 保存数据
        self.storage.save_selected_stocks(
            date,
            result['top_stocks'],
            result.get('emotion'),
            result.get('hot_sectors')
        )
        
        # 发送通知
        self._send_evening_report(result)
        
        return result
    
    def check_position_stop(self, positions: list):
        """
        检查持仓止损止盈
        
        Args:
            positions: 持仓列表 [{code, name, buy_price, current_price}, ...]
        
        Returns:
            list: 需要操作的持仓
        """
        print("\n" + "=" * 70)
        print("持仓止损止盈检查")
        print("=" * 70)
        
        actions = []
        
        for pos in positions:
            code = pos['code']
            name = pos['name']
            buy_price = pos['buy_price']
            current_price = pos['current_price']
            
            # 计算止损止盈位
            stop_info = self.risk.calculate_stop_levels(buy_price, current_price)
            
            # 检查持仓风险
            risk_check = self.risk.check_position_risk(buy_price, current_price)
            
            print(f"\n{name}({code})")
            print(f"  买入价: {buy_price}")
            print(f"  当前价: {current_price}")
            print(f"  止损价: {stop_info['stop_loss_price']}")
            print(f"  止盈价: {stop_info['stop_profit_price']}")
            print(f"  当前盈亏: {risk_check['profit_pct']:+.2f}%")
            print(f"  操作建议: {risk_check['action']} - {risk_check['message']}")
            
            if risk_check['action'] in ['stop_loss', 'stop_profit']:
                actions.append({
                    'code': code,
                    'name': name,
                    'action': risk_check['action'],
                    'profit_pct': risk_check['profit_pct'],
                    'message': risk_check['message']
                })
        
        if actions:
            self._send_stop_alert(actions)
        
        return actions
    
    def record_trade_and_update_risk(self, stock_code, stock_name, is_win, profit_pct):
        """
        记录交易并更新风控状态
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            is_win: 是否盈利
            profit_pct: 盈亏比例
        """
        # 更新连续亏损计数
        self.risk.record_trade_result(is_win)
        
        print(f"\n交易记录: {stock_name}({stock_code})")
        print(f"  结果: {'盈利' if is_win else '亏损'} {profit_pct:+.2f}%")
        print(f"  连续亏损次数: {self.risk.status.get('consecutive_losses', 0)}")
    
    def _send_risk_alert(self, risk_result):
        """发送风控警报"""
        message = f"⛔ T01风控警报\n\n"
        message += f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += f"【交易建议】\n"
        message += f"  允许交易: {'是' if risk_result['trading_allowed'] else '否'}\n"
        message += f"  建议仓位: {risk_result['final_position_limit']*100:.0f}%\n\n"
        message += f"{risk_result['recommendation']}"
        
        try:
            self.feishu.send_message(message)
        except Exception as e:
            print(f"发送风控警报失败: {e}")
    
    def _send_evening_report(self, result):
        """发送晚间分析报告"""
        risk = result.get('risk_assessment', {})
        stocks = result.get('top_stocks', [])
        
        message = f"📊 T01龙头战法 - {result['date']} 晚间分析\n\n"
        message += "━" * 30 + "\n"
        message += "【风控评估】\n"
        message += f"  建议仓位: {risk.get('final_position_limit', 0)*100:.0f}%\n"
        message += f"  {risk.get('recommendation', '')}\n\n"
        message += "━" * 30 + "\n"
        message += f"【选股结果】选出 {len(stocks)} 只股票\n"
        message += "━" * 30 + "\n\n"
        
        for i, stock in enumerate(stocks, 1):
            message += f"【{i}. {stock['name']}({stock['code']})】\n"
            message += f"  评分: {stock['score']:.2f}分\n\n"
        
        message += "⚠️ 风险提示: 以上分析仅供参考，投资有风险"
        
        try:
            self.feishu.send_message(message)
        except Exception as e:
            print(f"发送报告失败: {e}")
    
    def _send_stop_alert(self, actions):
        """发送止损止盈警报"""
        message = f"🔔 T01止损止盈警报\n\n"
        message += f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        for action in actions:
            status = "🔴 止损" if action['action'] == 'stop_loss' else "🟢 止盈"
            message += f"{status} {action['name']}({action['code']})\n"
            message += f"  盈亏: {action['profit_pct']:+.2f}%\n"
            message += f"  {action['message']}\n\n"
        
        message += "⚠️ 请及时处理持仓"
        
        try:
            self.feishu.send_message(message)
        except Exception as e:
            print(f"发送警报失败: {e}")
    
    def generate_full_report(self):
        """生成完整报告"""
        print("\n" + "=" * 70)
        print("T01龙头战法 - 完整系统报告")
        print("=" * 70)
        
        # AI进化报告
        print(self.ai.generate_report())
        
        # 交易统计
        stats = self.tracker.get_stats()
        print("\n【交易统计】")
        print(f"  总交易: {stats.get('total_trades', 0)} 笔")
        print(f"  胜率: {stats.get('win_rate', 0)}%")
        print(f"  平均盈亏: {stats.get('avg_profit', 0)}%")
        
        # 风控状态
        risk_status = self.risk.status
        print("\n【风控状态】")
        print(f"  允许交易: {risk_status.get('is_trading_allowed', True)}")
        print(f"  连续亏损: {risk_status.get('consecutive_losses', 0)} 次")
        print(f"  仓位乘数: {risk_status.get('position_multiplier', 1.0)}")
        
        if risk_status.get('pause_until'):
            print(f"  暂停至: {risk_status['pause_until']}")
        
        # 最近交易
        print("\n【最近交易】")
        recent = self.tracker.get_recent_trades(5)
        for trade in recent:
            status = "✅" if trade['is_win'] else "❌"
            print(f"  {status} {trade['stock_name']} {trade['profit_pct']:+.2f}%")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='T01龙头战法完整系统')
    parser.add_argument('--mode', type=str, 
                        choices=['evening', 'risk', 'stop', 'report', 'all'],
                        default='report', help='运行模式')
    parser.add_argument('--date', type=str, help='指定日期')
    parser.add_argument('--positions', type=str, help='持仓JSON（止损检查用）')
    
    args = parser.parse_args()
    
    system = T01CompleteSystem()
    
    if args.mode == 'evening':
        system.run_evening_analysis(args.date)
    
    elif args.mode == 'risk':
        # 单独运行风控评估
        system.risk.full_risk_assessment(args.date)
    
    elif args.mode == 'stop':
        # 检查持仓止损止盈
        if args.positions:
            positions = json.loads(args.positions)
            system.check_position_stop(positions)
        else:
            print("请提供持仓数据: --positions '[{\"code\":\"000001\",\"name\":\"平安银行\",\"buy_price\":10.0,\"current_price\":11.0}]'")
    
    elif args.mode == 'report':
        system.generate_full_report()
    
    elif args.mode == 'all':
        # 完整流程
        system.run_evening_analysis(args.date)
        system.generate_full_report()


if __name__ == "__main__":
    main()
