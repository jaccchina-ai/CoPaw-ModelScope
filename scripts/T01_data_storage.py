#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 数据存储与胜率统计模块
功能：
1. 本地化存储每日股票数据
2. 统计选股系统胜率（T+1开盘买入，T+2收盘卖出）
3. 记录每笔交易的盈亏情况
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/mnt/workspace/working/scripts')
from stockapi_client import StockAPIClient

# 数据存储路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
DAILY_DATA_DIR = os.path.join(DATA_BASE_DIR, "daily")
TRADES_FILE = os.path.join(DATA_BASE_DIR, "trades.json")
STATS_FILE = os.path.join(DATA_BASE_DIR, "stats.json")
HISTORY_DIR = os.path.join(DATA_BASE_DIR, "history")

class DataStorage:
    """数据存储管理器"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保目录存在"""
        for dir_path in [DAILY_DATA_DIR, HISTORY_DIR]:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
    
    def save_daily_data(self, date, data_type, data):
        """
        保存每日数据
        
        Args:
            date: 日期 (YYYY-MM-DD)
            data_type: 数据类型 (limit_up, hot_sectors, emotion, etc.)
            data: 数据内容
        """
        file_path = os.path.join(DAILY_DATA_DIR, f"{date}_{data_type}.json")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                'date': date,
                'type': data_type,
                'timestamp': datetime.now().isoformat(),
                'data': data
            }, f, ensure_ascii=False, indent=2)
        
        print(f"  已保存: {file_path}")
    
    def load_daily_data(self, date, data_type):
        """加载每日数据"""
        file_path = os.path.join(DAILY_DATA_DIR, f"{date}_{data_type}.json")
        
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f).get('data', {})
        return None
    
    def save_selected_stocks(self, t_date, stocks, emotion, hot_sectors):
        """
        保存T日选出的股票
        
        Args:
            t_date: T日日期
            stocks: 选出的股票列表
            emotion: 情绪周期数据
            hot_sectors: 热点板块数据
        """
        # 保存选股记录
        selection_data = {
            't_date': t_date,
            'selected_at': datetime.now().isoformat(),
            'stocks': stocks,
            'emotion': emotion,
            'hot_sectors': hot_sectors
        }
        
        # 保存到历史记录
        history_file = os.path.join(HISTORY_DIR, f"selection_{t_date}.json")
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(selection_data, f, ensure_ascii=False, indent=2)
        
        print(f"  选股记录已保存: {history_file}")
    
    def get_selected_stocks(self, t_date):
        """获取T日选出的股票"""
        history_file = os.path.join(HISTORY_DIR, f"selection_{t_date}.json")
        
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None


class TradeTracker:
    """交易跟踪器 - 跟踪每笔交易的盈亏"""
    
    def __init__(self):
        self.client = StockAPIClient()
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
                    'win_rate': 0,
                    'total_profit': 0,
                    'avg_profit': 0
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
            
            return 0
        
        except Exception as e:
            print(f"获取股票价格失败: {stock_code} {date} - {e}")
            return 0
    
    def track_trade(self, stock_code, stock_name, t_date, t1_date, t2_date, t_score):
        """
        跟踪一笔交易
        
        逻辑：
        - T+1日开盘价买入
        - T+2日收盘价卖出
        - 计算盈亏
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            t_date: T日（选股日）
            t1_date: T+1日（买入日）
            t2_date: T+2日（卖出日）
            t_score: T日评分
        
        Returns:
            dict: 交易结果
        """
        print(f"\n  跟踪交易: {stock_name}({stock_code})")
        print(f"    T日: {t_date}, T+1: {t1_date}, T+2: {t2_date}")
        
        # 获取T+1日开盘价（买入价）
        buy_price = self.get_stock_price(stock_code, t1_date, 'open')
        print(f"    T+1开盘价(买入): {buy_price}")
        
        # 获取T+2日收盘价（卖出价）
        sell_price = self.get_stock_price(stock_code, t2_date, 'close')
        print(f"    T+2收盘价(卖出): {sell_price}")
        
        if buy_price <= 0 or sell_price <= 0:
            print(f"    无法获取价格数据，跳过")
            return None
        
        # 计算盈亏
        profit_pct = (sell_price - buy_price) / buy_price * 100
        is_win = profit_pct > 0
        
        print(f"    盈亏: {profit_pct:.2f}% ({'盈利' if is_win else '亏损'})")
        
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
        
        self._save_stats(stats)
    
    def get_stats(self):
        """获取统计数据"""
        return self._load_stats()
    
    def get_recent_trades(self, n=10):
        """获取最近N笔交易"""
        trades_data = self._load_trades()
        return trades_data['trades'][-n:]


def main():
    """测试数据存储和交易跟踪"""
    print("=" * 60)
    print("T01龙头战法 - 数据存储与胜率统计测试")
    print("=" * 60)
    
    storage = DataStorage()
    tracker = TradeTracker()
    
    # 测试用例：跟踪2026-02-12选出股票的交易
    t_date = '2026-02-12'
    t1_date = '2026-02-13'
    t2_date = '2026-02-14'  # 假设下一个交易日
    
    # 检查T+2是否为交易日
    is_t2_trade = storage.client.get_trading_day(t2_date)
    print(f"\nT+2日({t2_date})是否为交易日: {is_t2_trade}")
    
    # 获取T日选出的股票
    selection = storage.get_selected_stocks(t_date)
    
    if selection:
        print(f"\nT日({t_date})选出的股票:")
        stocks = selection.get('stocks', [])
        
        for stock in stocks:
            print(f"  {stock['name']}({stock['code']}) - 评分: {stock['score']:.2f}")
        
        print(f"\n当前统计:")
        stats = tracker.get_stats()
        print(f"  总交易次数: {stats['total_trades']}")
        print(f"  盈利次数: {stats['win_trades']}")
        print(f"  亏损次数: {stats['lose_trades']}")
        print(f"  胜率: {stats['win_rate']}%")
        print(f"  平均盈亏: {stats['avg_profit']}%")
    else:
        print(f"\n未找到T日({t_date})的选股记录")


if __name__ == "__main__":
    main()
