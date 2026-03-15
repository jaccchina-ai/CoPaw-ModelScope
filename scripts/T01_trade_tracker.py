#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 交易跟踪与胜率统计 V2.0
================================================
修改内容：
1. 统计范围：T+1日竞价阶段最终推荐的前3个股票（action="买入"）
2. 成功标准：T+2收盘价 / T+1开盘价 > 1.03%（即盈利 > 3%）
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
AUCTION_RESULT_FILE = os.path.join(DATA_BASE_DIR, "auction_result.json")

# ==================== 核心配置 ====================

# 成功标准：盈利 > 3%
SUCCESS_THRESHOLD = 0.03  # 3%

# 统计范围：竞价推荐的前N只股票
TOP_N_STOCKS = 3


class TradeTrackerV2:
    """交易跟踪器 V2 - 按新标准统计"""
    
    def __init__(self):
        self.client = StockAPIClient()
        self.feishu = FeishuNotifier()
        self._ensure_files()

    def _get_stock_sector(self, stock_code, t_date):
        """从选股记录获取股票板块"""
        # 从当前选股记录获取
        if os.path.exists(SELECTED_STOCKS_FILE):
            with open(SELECTED_STOCKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for stock in data.get('stocks', []):
                    if stock.get('code') == stock_code:
                        return stock.get('details', {}).get('hot_sector_name', '未知')
        
        # 从历史选股记录获取
        history_dir = os.path.join(DATA_BASE_DIR, 'history')
        if os.path.exists(history_dir):
            for f in os.listdir(history_dir):
                if f.startswith('selection_') and f.endswith('.json'):
                    date = f.replace('selection_', '').replace('.json', '')
                    if date == t_date:
                        filepath = os.path.join(history_dir, f)
                        with open(filepath, 'r', encoding='utf-8') as fp:
                            data = json.load(fp)
                            for stock in data.get('stocks', []):
                                if stock.get('code') == stock_code:
                                    return stock.get('details', {}).get('hot_sector_name', '未知')
        
        return '未知'

    def _get_stock_details(self, stock_code, t_date):
        """从选股记录获取股票完整指标"""
        # 从当前选股记录获取
        if os.path.exists(SELECTED_STOCKS_FILE):
            with open(SELECTED_STOCKS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for stock in data.get('stocks', []):
                    if stock.get('code') == stock_code:
                        return stock.get('details', {})
        
        # 从历史选股记录获取
        history_dir = os.path.join(DATA_BASE_DIR, 'history')
        if os.path.exists(history_dir):
            for f in os.listdir(history_dir):
                if f.startswith('selection_') and f.endswith('.json'):
                    date = f.replace('selection_', '').replace('.json', '')
                    if date == t_date:
                        filepath = os.path.join(history_dir, f)
                        with open(filepath, 'r', encoding='utf-8') as fp:
                            data = json.load(fp)
                            for stock in data.get('stocks', []):
                                if stock.get('code') == stock_code:
                                    return stock.get('details', {})
        
        return {}

    def _ensure_files(self):
        """确保文件存在"""
        if not os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, 'w', encoding='utf-8') as f:
                json.dump({'trades': [], 'version': 'v2'}, f, ensure_ascii=False, indent=2)
        
        if not os.path.exists(STATS_FILE):
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': 'v2',
                    'success_threshold': f'>{SUCCESS_THRESHOLD*100}%',
                    'total_trades': 0,
                    'win_trades': 0,
                    'lose_trades': 0,
                    'win_rate': 0.0,
                    'total_profit': 0.0,
                    'avg_profit': 0.0,
                    'avg_win': 0.0,
                    'avg_loss': 0.0,
                    'profit_ratio': 0.0,  # 盈亏比
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
        """
        try:
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
            print(f"    ⚠️ 获取价格失败: {stock_code} {date} - {e}")
            return 0
    
    def find_next_trading_day(self, date_str):
        """找到下一个交易日"""
        current_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        for i in range(1, 10):
            check_date = (current_date + timedelta(days=i)).strftime('%Y-%m-%d')
            is_trading = self.client.get_trading_day(check_date)
            if is_trading:
                return check_date
        
        return None
    
    def load_auction_results(self):
        """加载所有竞价结果"""
        results = {}
        
        # 从主文件加载
        if os.path.exists(AUCTION_RESULT_FILE):
            with open(AUCTION_RESULT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                t_date = data.get('t_date')
                if t_date:
                    results[t_date] = data
        
        # 从历史目录加载
        if os.path.exists(HISTORY_DIR):
            for f in os.listdir(HISTORY_DIR):
                if f.startswith('auction_') and f.endswith('.json'):
                    date = f.replace('auction_', '').replace('.json', '')
                    filepath = os.path.join(HISTORY_DIR, f)
                    with open(filepath, 'r', encoding='utf-8') as fp:
                        results[date] = json.load(fp)
        
        return results
    
    def get_top3_buy_recommendations(self, auction_data):
        """
        从竞价结果中提取前3个买入推荐的股票
        
        Args:
            auction_data: 竞价分析结果
        
        Returns:
            list: 前3个买入推荐的股票列表
        """
        recommendations = auction_data.get('buy_recommendations', [])
        
        # 筛选 action="买入" 的股票，取前3个
        buy_stocks = [r for r in recommendations if r.get('action') == '买入'][:TOP_N_STOCKS]
        
        return buy_stocks
    
    def check_pending_trades(self):
        """
        检查待跟踪的交易
        
        只统计竞价阶段最终推荐买入的前3只股票
        """
        today = datetime.now().strftime('%Y-%m-%d')
        trades_data = self._load_trades()
        existing_trades = {(t['stock_code'], t['t_date']) for t in trades_data.get('trades', [])}
        
        pending = []
        
        # 加载所有竞价结果
        auction_results = self.load_auction_results()
        
        for t_date, auction_data in auction_results.items():
            t1_date = auction_data.get('t1_date')
            if not t1_date:
                t1_date = self.find_next_trading_day(t_date)
            
            if not t1_date:
                continue
            
            # 找T+2日
            t2_date = self.find_next_trading_day(t1_date)
            if not t2_date:
                continue
            
            # 检查T+2是否已到
            if t2_date > today:
                print(f"  {t_date}: T+2({t2_date})未到，跳过")
                continue
            
            # 获取前3个买入推荐的股票
            top3_stocks = self.get_top3_buy_recommendations(auction_data)
            
            if not top3_stocks:
                print(f"  {t_date}: 无买入推荐，跳过")
                continue
            
            print(f"  {t_date}: 找到{len(top3_stocks)}只买入推荐股票")
            
            for stock in top3_stocks:
                stock_code = stock.get('stock_code', '')
                stock_name = stock.get('stock_name', '')
                rank = stock.get('rank', 0)
                
                # 检查是否已跟踪
                if (stock_code, t_date) in existing_trades:
                    print(f"    - {stock_name}({stock_code}): 已跟踪，跳过")
                    continue
                
                pending.append({
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    't_date': t_date,
                    't1_date': t1_date,
                    't2_date': t2_date,
                    't_score': stock.get('t_score', 0),
                    'auction_score': stock.get('auction_score', 0),
                    'final_score': stock.get('final_score', 0),
                    'rank': rank,
                    'recommended_position': stock.get('recommended_position', 0)
                })
        
        return pending
    
    def track_trade(self, trade_info):
        """
        跟踪一笔交易
        
        逻辑：
        - T+1日开盘价买入
        - T+2日收盘价卖出
        - 成功标准：盈利 > 3%
        """
        stock_code = trade_info['stock_code']
        stock_name = trade_info['stock_name']
        t_date = trade_info['t_date']
        t1_date = trade_info['t1_date']
        t2_date = trade_info['t2_date']
        
        print(f"\n  跟踪: {stock_name}({stock_code}) 第{trade_info['rank']}名")
        print(f"    T日: {t_date}, T+1: {t1_date}, T+2: {t2_date}")
        
        # 获取T+1日开盘价（买入价）
        buy_price = self.get_stock_price(stock_code, t1_date, 'open')
        print(f"    T+1开盘价(买入): {buy_price:.2f}")
        
        # 获取T+2日收盘价（卖出价）
        sell_price = self.get_stock_price(stock_code, t2_date, 'close')
        print(f"    T+2收盘价(卖出): {sell_price:.2f}")
        
        if buy_price <= 0 or sell_price <= 0:
            print(f"    ⚠️ 无法获取价格数据，跳过")
            return None
        
        # 计算盈亏
        profit_pct = (sell_price - buy_price) / buy_price * 100
        
        # ★ 核心修改：成功标准 = 盈利 > 3%
        is_win = profit_pct > SUCCESS_THRESHOLD * 100
        
        print(f"    盈亏: {profit_pct:+.2f}%")
        print(f"    成功标准: >{SUCCESS_THRESHOLD*100}%")
        print(f"    结果: {'✅成功' if is_win else '❌失败'}")
        
        # 记录交易
        # 获取板块信息
        sector = self._get_stock_sector(stock_code, t_date)
        
        # ★获取完整选股指标（用于机器学习）
        stock_details = self._get_stock_details(stock_code, t_date)
        
        trade = {
            'stock_code': stock_code,
            'stock_name': stock_name,
            't_date': t_date,
            'sector': sector,
            't1_date': t1_date,
            't2_date': t2_date,
            't_score': trade_info.get('t_score', 0),
            'auction_score': trade_info.get('auction_score', 0),
            'final_score': trade_info.get('final_score', 0),
            'rank': trade_info.get('rank', 0),
            'recommended_position': trade_info.get('recommended_position', 0),
            'buy_price': buy_price,
            'sell_price': sell_price,
            'profit_pct': round(profit_pct, 2),
            'is_win': is_win,
            'success_threshold': SUCCESS_THRESHOLD * 100,
            'tracked_at': datetime.now().isoformat(),
            # ★分项指标（用于机器学习进化）- 自动保存所有指标
            'metrics': stock_details  # 直接保存完整的details，新增指标自动包含
        }
        
        # 保存交易记录
        trades_data = self._load_trades()
        if 'trades' not in trades_data:
            trades_data['trades'] = []
        trades_data['trades'].append(trade)
        trades_data['version'] = 'v2'
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
        
        # 计算累计数据
        trades_data = self._load_trades()
        trades = trades_data.get('trades', [])
        
        wins = [t for t in trades if t.get('is_win')]
        losses = [t for t in trades if not t.get('is_win')]
        
        stats['total_profit'] = round(sum(t.get('profit_pct', 0) for t in trades), 2)
        stats['win_rate'] = round(stats['win_trades'] / stats['total_trades'] * 100, 2) if stats['total_trades'] > 0 else 0
        stats['avg_profit'] = round(stats['total_profit'] / stats['total_trades'], 2) if stats['total_trades'] > 0 else 0
        
        # 计算平均盈利和平均亏损
        if wins:
            stats['avg_win'] = round(sum(t.get('profit_pct', 0) for t in wins) / len(wins), 2)
        if losses:
            stats['avg_loss'] = round(sum(t.get('profit_pct', 0) for t in losses) / len(losses), 2)
        
        # 计算盈亏比
        if stats.get('avg_loss', 0) != 0:
            stats['profit_ratio'] = round(abs(stats.get('avg_win', 0) / stats['avg_loss']), 2)
        else:
            stats['profit_ratio'] = 0
        
        # 更新最大盈利/亏损
        profits = [t.get('profit_pct', 0) for t in trades]
        stats['max_profit'] = round(max(profits), 2) if profits else 0
        stats['max_loss'] = round(min(profits), 2) if profits else 0
        
        stats['last_updated'] = datetime.now().isoformat()
        stats['version'] = 'v2'
        stats['success_threshold'] = f'>{SUCCESS_THRESHOLD*100}%'
        
        self._save_stats(stats)
    
    def recalculate_all_stats(self):
        """重新计算所有统计数据（按新标准）"""
        trades_data = self._load_trades()
        trades = trades_data.get('trades', [])
        
        if not trades:
            return None
        
        # 按新标准重新判断成功/失败
        for trade in trades:
            trade['is_win'] = trade.get('profit_pct', 0) > SUCCESS_THRESHOLD * 100
            trade['success_threshold'] = SUCCESS_THRESHOLD * 100
        
        # 保存更新后的交易记录
        self._save_trades(trades_data)
        
        # 重新计算统计
        wins = [t for t in trades if t.get('is_win')]
        losses = [t for t in trades if not t.get('is_win')]
        
        stats = {
            'version': 'v2',
            'success_threshold': f'>{SUCCESS_THRESHOLD*100}%',
            'total_trades': len(trades),
            'win_trades': len(wins),
            'lose_trades': len(losses),
            'win_rate': round(len(wins) / len(trades) * 100, 2) if trades else 0,
            'total_profit': round(sum(t.get('profit_pct', 0) for t in trades), 2),
            'avg_profit': round(sum(t.get('profit_pct', 0) for t in trades) / len(trades), 2) if trades else 0,
            'avg_win': round(sum(t.get('profit_pct', 0) for t in wins) / len(wins), 2) if wins else 0,
            'avg_loss': round(sum(t.get('profit_pct', 0) for t in losses) / len(losses), 2) if losses else 0,
            'profit_ratio': 0.0,
            'max_profit': round(max(t.get('profit_pct', 0) for t in trades), 2) if trades else 0,
            'max_loss': round(min(t.get('profit_pct', 0) for t in trades), 2) if trades else 0,
            'last_updated': datetime.now().isoformat()
        }
        
        # 计算盈亏比
        if stats['avg_loss'] != 0:
            stats['profit_ratio'] = round(abs(stats['avg_win'] / stats['avg_loss']), 2)
        
        self._save_stats(stats)
        return stats
    
    def get_stats(self):
        """获取统计数据"""
        return self._load_stats()
    
    def get_recent_trades(self, n=10):
        """获取最近N笔交易"""
        trades_data = self._load_trades()
        return trades_data.get('trades', [])[-n:]
    
    def send_notification(self, new_trades, stats):
        """发送飞书通知"""
        message = f"📊 T01龙头战法 - 交易跟踪报告 V2\n\n"
        message += f"跟踪时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        message += f"成功标准: 盈利 > {SUCCESS_THRESHOLD*100}%\n"
        message += f"统计范围: 竞价推荐前{TOP_N_STOCKS}只\n"
        message += "━" * 30 + "\n\n"
        
        if new_trades:
            message += f"【本次跟踪交易】{len(new_trades)} 笔\n"
            for trade in new_trades:
                icon = '✅' if trade['is_win'] else '❌'
                message += f"\n  {icon} 第{trade['rank']}名 {trade['stock_name']}({trade['stock_code']})\n"
                message += f"     T日: {trade['t_date']}\n"
                message += f"     买入: {trade['buy_price']:.2f} → 卖出: {trade['sell_price']:.2f}\n"
                message += f"     盈亏: {trade['profit_pct']:+.2f}%\n"
        else:
            message += "【本次跟踪交易】无新增\n"
        
        message += "\n" + "━" * 30 + "\n"
        message += f"\n【累计统计】\n"
        message += f"  总交易次数: {stats['total_trades']} 笔\n"
        message += f"  成功/失败: {stats['win_trades']}/{stats['lose_trades']}\n"
        message += f"  胜率: {stats['win_rate']}%\n"
        message += f"  平均盈亏: {stats['avg_profit']:+.2f}%\n"
        message += f"  平均盈利: {stats.get('avg_win', 0):+.2f}%\n"
        message += f"  平均亏损: {stats.get('avg_loss', 0):+.2f}%\n"
        message += f"  盈亏比: {stats.get('profit_ratio', 0):.2f}\n"
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
    
    def print_summary(self):
        """打印统计摘要"""
        stats = self.get_stats()
        trades = self.get_recent_trades(20)
        
        print("\n" + "=" * 70)
        print("T01龙头战法 - 胜率统计 V2")
        print("=" * 70)
        
        print(f"\n【统计标准】")
        print(f"  成功标准: 盈利 > {SUCCESS_THRESHOLD*100}%")
        print(f"  统计范围: 竞价推荐前{TOP_N_STOCKS}只股票")
        
        print(f"\n【累计统计】")
        print(f"  总交易次数: {stats.get('total_trades', 0)} 笔")
        print(f"  成功/失败: {stats.get('win_trades', 0)}/{stats.get('lose_trades', 0)}")
        print(f"  胜率: {stats.get('win_rate', 0)}%")
        print(f"  平均盈亏: {stats.get('avg_profit', 0):+.2f}%")
        print(f"  平均盈利: {stats.get('avg_win', 0):+.2f}%")
        print(f"  平均亏损: {stats.get('avg_loss', 0):+.2f}%")
        print(f"  盈亏比: {stats.get('profit_ratio', 0):.2f}")
        
        if trades:
            print(f"\n【最近{len(trades)}笔交易】")
            for t in trades:
                icon = '✅' if t.get('is_win') else '❌'
                rank = t.get('rank', '-')
                print(f"  {icon} 第{rank}名 {t['stock_name']} - {t.get('profit_pct', 0):+.2f}%")


def main():
    """主函数"""
    print("=" * 70)
    print("T01龙头战法 - 交易跟踪与胜率统计 V2")
    print("=" * 70)
    print(f"成功标准: 盈利 > {SUCCESS_THRESHOLD*100}%")
    print(f"统计范围: 竞价推荐前{TOP_N_STOCKS}只股票")
    
    tracker = TradeTrackerV2()
    
    # 1. 检查待跟踪的交易
    print("\n【步骤1】检查待跟踪交易...")
    pending = tracker.check_pending_trades()
    print(f"\n待跟踪交易: {len(pending)} 笔")
    
    # 2. 跟踪交易
    new_trades = []
    if pending:
        print("\n【步骤2】跟踪交易...")
        for trade_info in pending:
            trade = tracker.track_trade(trade_info)
            if trade:
                new_trades.append(trade)
    
    # 3. 获取统计
    print("\n【步骤3】统计结果...")
    stats = tracker.get_stats()
    
    # 4. 发送通知
    if new_trades:
        print("\n【步骤4】发送通知...")
        tracker.send_notification(new_trades, stats)
    
    # 5. 打印摘要
    tracker.print_summary()
    
    print("\n" + "=" * 70)
    print("交易跟踪完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
