#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 交易跟踪与胜率统计
功能：
1. 检查前日选股的T+2盈亏情况
2. 更新胜率统计
3. 发送飞书通知
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/mnt/workspace/working/scripts')

from stockapi_client import StockAPIClient
from feishu_notifier import FeishuNotifier

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
HISTORY_DIR = os.path.join(DATA_BASE_DIR, "history")
TRADES_FILE = os.path.join(DATA_BASE_DIR, "trades.json")
STATS_FILE = os.path.join(DATA_BASE_DIR, "stats.json")


class TradeTracker:
    """交易跟踪器"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.feishu = FeishuNotifier()
        self._ensure_files()
    
    def _ensure_files(self):
        """确保文件存在"""
        if not os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, 'w', encoding='utf-8') as f:
                json.dump({'trades': []}, f, ensure_ascii=False, indent=2)
        
        if not os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'total_trades': 0,
                    'win_trades': 0,
                    'lose_trades': 0,
                    'win_rate': 0.0,
                    'total_profit': 0.0,
                    'avg_profit': 0.0,
                    'max_profit': 0.0,
                    'max_loss': 0.0,
                    'last_updated': ''
                }, f, ensure_ascii=False, indent=2)
    
    def _load_trades(self):
        """加载交易记录"""
        with open(TRADES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_trades(self, data):
        """保存交易记录"""
        with open(TRADES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load_stats(self):
        """加载统计数据"""
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_stats(self, data):
        """保存统计数据"""
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_stock_price(self, stock_code, date, price_type='close'):
        """
        获取股票指定日期的开盘价或收盘价
        
        Args:
            stock_code: 股票代码
            date: 日期
            price_type: 'open' 或 'close'
        
        Returns:
            float: 股票价格
        """
        try:
            # 使用K线API获取数据
            kline_data = self.client.get_stock_kline(stock_code, date, date)
            
            if kline_data and isinstance(kline_data, list) and len(kline_data) > 0:
                item = kline_data[0]
                if price_type == 'open':
                    return float(item.get('open', 0))
                else:
                    return float(item.get('close', 0))
            
            # 尝试获取前几天的数据
            for i in range(1, 5):
                prev_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=i)).strftime('%Y-%m-%d')
                kline_data = self.client.get_stock_kline(stock_code, prev_date, prev_date)
                if kline_data and isinstance(kline_data, list) and len(kline_data) > 0:
                    item = kline_data[0]
                    if price_type == 'open':
                        return float(item.get('open', 0))
                    else:
                        return float(item.get('close', 0))
            
            return 0
        
        except Exception as e:
            print(f"  获取股票价格失败: {stock_code} {date} - {e}")
            return 0
    
    def find_t2_date(self, t1_date):
        """找到T+2日（下一个交易日）"""
        current_date = datetime.strptime(t1_date, '%Y-%m-%d')
        
        for i in range(1, 10):  # 最多往后找10天
            check_date = (current_date + timedelta(days=i)).strftime('%Y-%m-%d')
            is_trading = self.client.get_trading_day(check_date)
            if is_trading:
                return check_date
        
        return None
    
    def find_t1_date(self, t_date):
        """找到T+1日（下一个交易日）"""
        return self.find_t2_date(t_date)  # 逻辑相同
    
    def get_selection_dates(self):
        """获取所有选股日期"""
        dates = []
        if os.path.exists(HISTORY_DIR):
            for f in os.listdir(HISTORY_DIR):
                if f.startswith('selection_') and f.endswith('.json'):
                    date = f.replace('selection_', '').replace('.json', '')
                    dates.append(date)
        return sorted(dates)
    
    def check_pending_trades(self):
        """
        检查待跟踪的交易（T+2已到的交易）
        
        Returns:
            list: 待跟踪的交易列表
        """
        today = datetime.now().strftime('%Y-%m-%d')
        trades_data = self._load_trades()
        existing_trades = {(t['stock_code'], t['t_date']) for t in trades_data['trades']}
        
        pending = []
        
        # 遍历所有选股记录
        for t_date in self.get_selection_dates():
            selection_file = os.path.join(HISTORY_DIR, f"selection_{t_date}.json")
            
            with open(selection_file, 'r', encoding='utf-8') as f:
                selection = json.load(f)
            
            stocks = selection.get('stocks', selection.get('top_stocks', []))
            
            # 找T+1和T+2
            t1_date = self.find_t1_date(t_date)
            if not t1_date:
                continue
            
            t2_date = self.find_t2_date(t1_date)
            if not t2_date:
                continue
            
            # 检查T+2是否已到
            if t2_date > today:
                continue
            
            # 检查是否已跟踪
            for stock in stocks[:5]:  # 只跟踪前5只
                stock_code = stock.get('code', '')
                if (stock_code, t_date) in existing_trades:
                    continue
                
                pending.append({
                    'stock_code': stock_code,
                    'stock_name': stock.get('name', ''),
                    't_date': t_date,
                    't1_date': t1_date,
                    't2_date': t2_date,
                    't_score': stock.get('score', 0)
                })
        
        return pending
    
    def track_trade(self, stock_code, stock_name, t_date, t1_date, t2_date, t_score):
        """
        跟踪一笔交易
        
        逻辑：
        - T+1日开盘价买入
        - T+2日收盘价卖出
        - 计算盈亏
        """
        print(f"\n  跟踪: {stock_name}({stock_code})")
        print(f"    T日: {t_date}, T+1: {t1_date}, T+2: {t2_date}")
        
        # 获取T+1日开盘价（买入价）
        buy_price = self.get_stock_price(stock_code, t1_date, 'open')
        print(f"    T+1开盘价(买入): {buy_price}")
        
        # 获取T+2日收盘价（卖出价）
        sell_price = self.get_stock_price(stock_code, t2_date, 'close')
        print(f"    T+2收盘价(卖出): {sell_price}")
        
        if buy_price <= 0 or sell_price <= 0:
            print(f"    ⚠️ 无法获取价格数据，跳过")
            return None
        
        # 计算盈亏
        profit_pct = (sell_price - buy_price) / buy_price * 100
        is_win = profit_pct > 0
        
        print(f"    盈亏: {profit_pct:+.2f}% ({'✅盈利' if is_win else '❌亏损'})")
        
        # 记录交易
        trade = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            't_date': t_date,
            't1_date': t1_date,
            't2_date': t2_date,
            't_score': t_score,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'profit_pct': round(profit_pct, 2),
            'is_win': is_win,
            'tracked_at': datetime.now().isoformat()
        }
        
        # 保存交易记录
        trades_data = self._load_trades()
        trades_data['trades'].append(trade)
        self._save_trades(trades_data)
        
        # 更新统计
        self._update_stats(trade)
        
        return trade
    
    def _update_stats(self, trade):
        """更新统计数据"""
        stats = self._load_stats()
        
        stats['total_trades'] += 1
        
        if trade['is_win']:
            stats['win_trades'] += 1
        else:
            stats['lose_trades'] += 1
        
        stats['total_profit'] += trade['profit_pct']
        stats['win_rate'] = round(stats['win_trades'] / stats['total_trades'] * 100, 2)
        stats['avg_profit'] = round(stats['total_profit'] / stats['total_trades'], 2)
        
        # 更新最大盈利/亏损
        if trade['profit_pct'] > stats.get('max_profit', 0):
            stats['max_profit'] = trade['profit_pct']
        if trade['profit_pct'] < stats.get('max_loss', 0):
            stats['max_loss'] = trade['profit_pct']
        
        stats['last_updated'] = datetime.now().isoformat()
        
        self._save_stats(stats)
    
    def recalculate_stats(self):
        """重新计算统计数据"""
        trades_data = self._load_trades()
        trades = trades_data['trades']
        
        if not trades:
            return
        
        stats = {
            'total_trades': len(trades),
            'win_trades': sum(1 for t in trades if t.get('is_win')),
            'lose_trades': sum(1 for t in trades if not t.get('is_win')),
            'win_rate': 0.0,
            'total_profit': 0.0,
            'avg_profit': 0.0,
            'max_profit': 0.0,
            'max_loss': 0.0,
            'last_updated': datetime.now().isoformat()
        }
        
        profits = [t.get('profit_pct', 0) for t in trades]
        stats['total_profit'] = round(sum(profits), 2)
        stats['win_rate'] = round(stats['win_trades'] / stats['total_trades'] * 100, 2) if stats['total_trades'] > 0 else 0
        stats['avg_profit'] = round(stats['total_profit'] / stats['total_trades'], 2) if stats['total_trades'] > 0 else 0
        stats['max_profit'] = round(max(profits), 2) if profits else 0
        stats['max_loss'] = round(min(profits), 2) if profits else 0
        
        self._save_stats(stats)
        return stats
    
    def get_stats(self):
        """获取统计数据"""
        return self._load_stats()
    
    def get_recent_trades(self, n=10):
        """获取最近N笔交易"""
        trades_data = self._load_trades()
        return trades_data['trades'][-n:]
    
    def send_notification(self, new_trades, stats):
        """发送飞书通知"""
        message = f"📊 T01龙头战法 - 交易跟踪报告\n\n"
        message += f"跟踪时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        message += "━" * 30 + "\n\n"
        
        if new_trades:
            message += f"【本次跟踪交易】{len(new_trades)} 笔\n"
            for trade in new_trades:
                icon = '✅' if trade['is_win'] else '❌'
                message += f"\n  {icon} {trade['stock_name']}({trade['stock_code']})\n"
                message += f"     T日: {trade['t_date']}\n"
                message += f"     买入: {trade['buy_price']:.2f} → 卖出: {trade['sell_price']:.2f}\n"
                message += f"     盈亏: {trade['profit_pct']:+.2f}%\n"
        else:
            message += "【本次跟踪交易】无新增\n"
        
        message += "\n" + "━" * 30 + "\n"
        message += f"\n【累计统计】\n"
        message += f"  总交易次数: {stats['total_trades']} 笔\n"
        message += f"  盈利/亏损: {stats['win_trades']}/{stats['lose_trades']}\n"
        message += f"  胜率: {stats['win_rate']}%\n"
        message += f"  平均盈亏: {stats['avg_profit']:+.2f}%\n"
        message += f"  最大盈利: {stats.get('max_profit', 0):+.2f}%\n"
        message += f"  最大亏损: {stats.get('max_loss', 0):+.2f}%\n"
        
        message += "\n━" * 30 + "\n"
        message += "⚠️ 交易有风险，投资需谨慎"
        
        try:
            chat_id = "oc_ff08c55a23630937869cd222dad0bf14"
            self.feishu.send_message(chat_id, message)
            print("\n飞书通知已发送")
        except Exception as e:
            print(f"\n飞书通知发送失败: {e}")


def main():
    """主函数"""
    print("=" * 70)
    print("T01龙头战法 - 交易跟踪与胜率统计")
    print("=" * 70)
    
    tracker = TradeTracker()
    
    # 1. 检查待跟踪的交易
    print("\n【步骤1】检查待跟踪交易...")
    pending = tracker.check_pending_trades()
    print(f"  待跟踪交易: {len(pending)} 笔")
    
    # 2. 跟踪交易
    print("\n【步骤2】跟踪交易...")
    new_trades = []
    
    for trade_info in pending:
        trade = tracker.track_trade(
            trade_info['stock_code'],
            trade_info['stock_name'],
            trade_info['t_date'],
            trade_info['t1_date'],
            trade_info['t2_date'],
            trade_info['t_score']
        )
        if trade:
            new_trades.append(trade)
    
    # 3. 获取统计
    print("\n【步骤3】统计结果...")
    stats = tracker.get_stats()
    
    print(f"\n  累计交易: {stats['total_trades']} 笔")
    print(f"  盈利/亏损: {stats['win_trades']}/{stats['lose_trades']}")
    print(f"  胜率: {stats['win_rate']}%")
    print(f"  平均盈亏: {stats['avg_profit']:+.2f}%")
    
    # 4. 发送通知
    print("\n【步骤4】发送通知...")
    tracker.send_notification(new_trades, stats)
    
    # 5. 显示最近交易
    print("\n【最近5笔交易】")
    recent = tracker.get_recent_trades(5)
    for t in recent:
        icon = '✅' if t.get('is_win') else '❌'
        print(f"  {icon} {t['stock_name']} - {t.get('profit_pct', 0):+.2f}%")
    
    print("\n" + "=" * 70)
    print("交易跟踪完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
