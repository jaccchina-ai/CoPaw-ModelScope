#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 风控逻辑详解（简化版）
以实际数据演示风控计算过程
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, '/mnt/workspace/working/scripts')

from stockapi_client import StockAPIClient
from T01_risk_controller import RiskController


def detailed_risk_explanation(date='2026-02-13'):
    """详细解释风控逻辑"""
    
    print("=" * 70)
    print(f"T01龙头战法 - 风控逻辑详解")
    print(f"分析日期: {date}")
    print("=" * 70)
    
    client = StockAPIClient()
    
    # ==================== 第一层：情绪周期风控 ====================
    print("\n" + "═" * 70)
    print("【第一层】情绪周期风控")
    print("═" * 70)
    print("""
┌────────────────────────────────────────────────────────────────────┐
│ 原理说明                                                           │
├────────────────────────────────────────────────────────────────────┤
│ 情绪周期反映市场整体氛围，由API综合计算得出：                       │
│   • 涨停家数、连板家数、上涨比例                                    │
│   • 打板成功率、大面情绪、大肉情绪                                  │
│                                                                    │
│ 输出：情绪评分 (0-100分)                                           │
└────────────────────────────────────────────────────────────────────┘
""")
    
    print("【步骤1】调用情绪周期API")
    print("-" * 70)
    
    emotion_data = client.get_emotional_cycle()
    
    if emotion_data and isinstance(emotion_data, list):
        latest = emotion_data[0]
        print(f"API返回数据:")
        print(f"  涨停家数: {latest.get('ztjs', 'N/A')}")
        print(f"  连板家数: {latest.get('lbjs', 'N/A')}")
        print(f"  上涨比例: {latest.get('szbl', 'N/A')}")
        print(f"  打板成功率: {latest.get('dbcgl', 'N/A')}")
        
        score = latest.get('score', 50)
        if score is None:
            score = 50
    else:
        score = 50
        print("API未返回数据，使用默认值50分")
    
    print(f"\n【步骤2】根据评分确定仓位")
    print("-" * 70)
    print("""
┌─────────────┬─────────────┬─────────────┬─────────────────────────┐
│  评分区间   │   阶段      │  仓位限制   │       操作建议          │
├─────────────┼─────────────┼─────────────┼─────────────────────────┤
│   0-19分    │   冰点期    │     0%      │ 空仓观望                │
│  20-39分    │   低迷期    │    20%      │ 轻仓试错                │
│  40-59分    │   平稳期    │    50%      │ 正常操作                │
│  60-79分    │   良好期    │    80%      │ 积极操作                │
│  80-100分   │   高涨期    │   100%      │ 满仓操作                │
└─────────────┴─────────────┴─────────────┴─────────────────────────┘
""")
    
    if score < 20:
        emotion_position, stage = 0.0, "冰点期"
    elif score < 40:
        emotion_position, stage = 0.2, "低迷期"
    elif score < 60:
        emotion_position, stage = 0.5, "平稳期"
    elif score < 80:
        emotion_position, stage = 0.8, "良好期"
    else:
        emotion_position, stage = 1.0, "高涨期"
    
    print(f"【{date}计算结果】")
    print(f"  情绪评分: {score} 分")
    print(f"  市场阶段: {stage}")
    print(f"  仓位限制: {emotion_position*100:.0f}%")
    
    # ==================== 第二层：大盘走势风控 ====================
    print("\n\n" + "═" * 70)
    print("【第二层】大盘走势风控")
    print("═" * 70)
    print("""
┌────────────────────────────────────────────────────────────────────┐
│ 原理说明                                                           │
├────────────────────────────────────────────────────────────────────┤
│ 大盘走势反映市场整体趋势：                                         │
│   • 获取上证指数K线数据                                            │
│   • 计算5日、10日、20日均线                                        │
│   • 判断指数与均线的位置关系                                       │
│                                                                    │
│ 逻辑：跌破均线说明趋势走弱，需要降低仓位                           │
└────────────────────────────────────────────────────────────────────┘
""")
    
    print("【步骤1】获取上证指数K线数据")
    print("-" * 70)
    
    # 获取最近30天数据
    end_date = date
    start_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')
    
    index_data = client.get_index_sh(start_date, end_date)
    
    if index_data and len(index_data) >= 20:
        print(f"获取到 {len(index_data)} 天的K线数据\n")
        
        # 显示最近5天数据
        print("最近5个交易日数据:")
        print("  日期         开盘      最高      最低      收盘")
        print("  " + "-" * 50)
        for d in index_data[-5:]:
            print(f"  {d['time']}  {float(d['open']):>8.2f}  {float(d['high']):>8.2f}  {float(d['low']):>8.2f}  {float(d['close']):>8.2f}")
        
        print(f"\n【步骤2】计算均线")
        print("-" * 70)
        
        closes = [float(d['close']) for d in index_data[-20:]]
        current_close = closes[-1]
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        
        print(f"  当前收盘价: {current_close:.2f}")
        print(f"  5日均线(MA5): {ma5:.2f}")
        print(f"  10日均线(MA10): {ma10:.2f}")
        print(f"  20日均线(MA20): {ma20:.2f}")
        
        print(f"\n【步骤3】判断均线位置关系")
        print("-" * 70)
        
        above_ma5 = current_close > ma5
        above_ma10 = current_close > ma10
        above_ma20 = current_close > ma20
        
        print(f"  收盘价 {current_close:.2f} vs MA5 {ma5:.2f}: {'↑ 站上' if above_ma5 else '↓ 跌破'}")
        print(f"  收盘价 {current_close:.2f} vs MA10 {ma10:.2f}: {'↑ 站上' if above_ma10 else '↓ 跌破'}")
        print(f"  收盘价 {current_close:.2f} vs MA20 {ma20:.2f}: {'↑ 站上' if above_ma20 else '↓ 跌破'}")
        
        print(f"\n【步骤4】根据均线位置确定仓位")
        print("-" * 70)
        print("""
┌─────────────────────┬─────────────┬─────────────────────────────┐
│       条件          │  仓位限制   │           说明              │
├─────────────────────┼─────────────┼─────────────────────────────┤
│ 跌破20日均线        │    30%      │ 趋势严重走弱                │
│ 跌破10日均线        │    50%      │ 短期趋势走弱                │
│ 跌破5日均线         │    70%      │ 短期调整                    │
│ 站上所有均线        │   100%      │ 趋势良好                    │
└─────────────────────┴─────────────┴─────────────────────────────┘
""")
        
        if not above_ma20:
            market_position = 0.3
            signal = "跌破20日均线"
        elif not above_ma10:
            market_position = 0.5
            signal = "跌破10日均线"
        elif not above_ma5:
            market_position = 0.7
            signal = "跌破5日均线"
        else:
            market_position = 1.0
            signal = "站上所有均线"
        
        trend = "up" if above_ma5 and above_ma10 else ("down" if not above_ma10 else "sideways")
        
        print(f"【{date}计算结果】")
        print(f"  上证指数: {current_close:.2f}")
        print(f"  趋势判断: {trend}")
        print(f"  风险信号: {signal}")
        print(f"  仓位限制: {market_position*100:.0f}%")
    else:
        market_position = 0.5
        print("无法获取大盘数据，使用默认仓位50%")
    
    # ==================== 最终综合计算 ====================
    print("\n\n" + "═" * 70)
    print("【最终综合计算】")
    print("═" * 70)
    print("""
┌────────────────────────────────────────────────────────────────────┐
│ 综合计算公式                                                       │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│        最终仓位 = min(情绪仓位, 大盘仓位)                          │
│                                                                    │
│ 解释：取两层风控中最严格的限制                                     │
└────────────────────────────────────────────────────────────────────┘
""")
    
    print("【步骤1】汇总各层风控结果")
    print("-" * 70)
    print(f"  情绪周期仓位: {emotion_position*100:.0f}%")
    print(f"  大盘走势仓位: {market_position*100:.0f}%")
    
    print(f"\n【步骤2】计算最终仓位")
    print("-" * 70)
    
    final_position = min(emotion_position, market_position)
    trading_allowed = final_position > 0
    
    print(f"  min({emotion_position*100:.0f}%, {market_position*100:.0f}%) = {final_position*100:.0f}%")
    
    print(f"\n" + "═" * 70)
    print(f"【{date}最终风控结论】")
    print("═" * 70)
    print(f"""
┌────────────────────────────────────────────────────────────────────┐
│  允许交易: {'✅ 是' if trading_allowed else '❌ 否'}                                              │
│  建议仓位: {final_position*100:.0f}%                                               │
│                                                                    │
│  风控明细:                                                         │
│    • 情绪周期: {score}分 ({stage}) → 仓位限制 {emotion_position*100:.0f}%                      │
│    • 大盘走势: {current_close:.2f}点 ({signal}) → 仓位限制 {market_position*100:.0f}%          │
│                                                                    │
│  取两者最小值: {final_position*100:.0f}%                                            │
└────────────────────────────────────────────────────────────────────┘
""")
    
    return {
        'date': date,
        'trading_allowed': trading_allowed,
        'final_position': final_position,
        'emotion': {'score': score, 'stage': stage, 'position': emotion_position},
        'market': {'price': current_close, 'signal': signal, 'position': market_position}
    }


if __name__ == "__main__":
    result = detailed_risk_explanation('2026-02-13')
