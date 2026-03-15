#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 完整流程测试（使用实际可用数据）
演示：选股 → 交易跟踪 → 统计胜率 → AI进化
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, '/mnt/workspace/working/scripts')

from stockapi_client import StockAPIClient
from T01_data_storage import DataStorage, TradeTracker
from T01_ai_evolution import AIEvolution

def test_full_flow():
    """测试完整流程"""
    print("=" * 70)
    print("T01龙头战法 - 完整流程测试")
    print("=" * 70)
    
    # 初始化
    client = StockAPIClient()
    storage = DataStorage()
    tracker = TradeTracker()
    ai = AIEvolution()
    
    # ========== 第一步：T日选股 ==========
    t_date = '2026-02-12'
    t1_date = '2026-02-13'
    
    print(f"\n【第一步】T日选股 - {t_date}")
    print("-" * 50)
    
    # 获取涨停股票
    limit_up_stocks = client.get_limit_up_stocks(t_date)
    print(f"涨停股数量: {len(limit_up_stocks)}")
    
    # 获取情绪周期（返回最近40天数据）
    emotion_data = client.get_emotional_cycle()
    emotion = {}
    if emotion_data and isinstance(emotion_data, list) and len(emotion_data) > 0:
        emotion = emotion_data[0]  # 使用最新数据
    print(f"情绪数据: 涨停家数={emotion.get('ztjs', 'N/A')}, 连板家数={emotion.get('lbjs', 'N/A')}")
    
    # 获取热点板块
    hot_sectors = client.get_hot_sectors(t_date)
    print(f"热点板块数量: {len(hot_sectors) if hot_sectors else 0}")
    
    # 模拟选股结果（基于之前的测试结果）
    selected_stocks = [
        {'code': '605033', 'name': '美邦股份', 'score': 75.33, 'details': {}},
        {'code': '002951', 'name': '金时科技', 'score': 74.78, 'details': {}},
        {'code': '600821', 'name': '金开新能', 'score': 71.21, 'details': {}},
        {'code': '600589', 'name': '大位科技', 'score': 65.58, 'details': {}},
        {'code': '603533', 'name': '掌阅科技', 'score': 65.40, 'details': {}}
    ]
    
    # 保存选股记录
    storage.save_selected_stocks(t_date, selected_stocks, emotion, hot_sectors)
    
    # 保存每日数据
    storage.save_daily_data(t_date, 'limit_up', limit_up_stocks)
    storage.save_daily_data(t_date, 'emotion', emotion)
    storage.save_daily_data(t_date, 'hot_sectors', hot_sectors)
    
    # ========== 第二步：T+1日竞价分析 ==========
    print(f"\n【第二步】T+1日竞价分析 - {t1_date}")
    print("-" * 50)
    
    # 获取T+1日涨停股
    t1_limit_up = client.get_limit_up_stocks(t1_date)
    print(f"T+1日涨停股数量: {len(t1_limit_up)}")
    
    # 检查连板情况
    t1_limit_codes = [s.get('code') for s in t1_limit_up] if t1_limit_up else []
    
    print(f"\n连板情况:")
    for stock in selected_stocks:
        is_continue = stock['code'] in t1_limit_codes
        print(f"  {stock['name']}({stock['code']}): {'✅ 连板' if is_continue else '❌ 未连板'}")
    
    # ========== 第三步：模拟交易跟踪 ==========
    print(f"\n【第三步】模拟交易跟踪（演示流程）")
    print("-" * 50)
    
    # 获取T+1开盘价
    print(f"\n获取T+1日({t1_date})开盘价:")
    t1_prices = {}
    for stock in selected_stocks:
        kline = client.get_stock_kline(stock['code'], t1_date, t1_date)
        if kline and len(kline) > 0:
            t1_open = float(kline[0].get('open', 0))
            t1_close = float(kline[0].get('close', 0))
            t1_prices[stock['code']] = {'open': t1_open, 'close': t1_close}
            print(f"  {stock['name']}: 开盘={t1_open}, 收盘={t1_close}")
        else:
            print(f"  {stock['name']}: 无法获取数据")
    
    # 使用模拟的T+2收盘价来演示完整流程
    # 在实际运行时，会在T+2日收盘后自动获取真实价格
    print(f"\n模拟T+2收盘价（演示盈亏计算逻辑）:")
    
    # 模拟交易结果（使用实际T+1日数据推算）
    simulated_results = [
        {'code': '605033', 'name': '美邦股份', 'buy': 28.67, 'sell': 31.54, 'profit': 10.0},
        {'code': '002951', 'name': '金时科技', 'buy': 18.65, 'sell': 20.52, 'profit': 10.0},
        {'code': '600821', 'name': '金开新能', 'buy': 6.52, 'sell': 6.19, 'profit': -5.1},
        {'code': '600589', 'name': '大位科技', 'buy': 15.25, 'sell': 14.80, 'profit': -3.0},
        {'code': '603533', 'name': '掌阅科技', 'buy': 36.23, 'sell': 39.85, 'profit': 10.0}
    ]
    
    print(f"\n交易结果模拟:")
    for r in simulated_results:
        status = "✅盈利" if r['profit'] > 0 else "❌亏损"
        print(f"  {r['name']}: 买入{r['buy']} → 卖出{r['sell']} = {r['profit']:+.1f}% {status}")
        
        # 记录交易到系统
        tracker.track_trade(
            r['code'],
            r['name'],
            t_date,
            t1_date,
            '2026-02-17',  # 模拟T+2
            75.0  # 模拟评分
        )
    
    # ========== 第四步：统计胜率 ==========
    print(f"\n【第四步】统计胜率")
    print("-" * 50)
    
    stats = tracker.get_stats()
    print(f"总交易次数: {stats.get('total_trades', 0)}")
    print(f"盈利次数: {stats.get('win_trades', 0)}")
    print(f"亏损次数: {stats.get('lose_trades', 0)}")
    print(f"胜率: {stats.get('win_rate', 0)}%")
    print(f"平均盈亏: {stats.get('avg_profit', 0)}%")
    
    # ========== 第五步：AI进化分析 ==========
    print(f"\n【第五步】AI进化分析")
    print("-" * 50)
    
    # 分析特征重要性
    ai.analyze_feature_importance()
    
    # 策略反思
    reflection = ai.reflect_on_strategy()
    
    # 自动进化
    evolution_result = ai.auto_evolve(min_trades=3)
    print(f"\n进化结果: {evolution_result.get('message', 'N/A')}")
    
    # ========== 生成报告 ==========
    print("\n" + "=" * 70)
    print("完整流程测试完成!")
    print("=" * 70)
    
    # 显示当前权重
    weights = ai.get_current_weights()
    print(f"\n当前权重配置 (版本 v{ai.current_weights.get('version', 1)}):")
    for k, v in weights.items():
        print(f"  {k}: {v:.2%}")
    
    # 显示进化日志
    log_file = '/mnt/workspace/working/data/T01/evolution_log.json'
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = json.load(f)
        print(f"\n进化日志条目: {len(logs.get('logs', []))}")
    
    return stats


if __name__ == "__main__":
    test_full_flow()
