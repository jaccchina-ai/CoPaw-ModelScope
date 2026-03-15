#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01任务完整测试
测试从T日分析到T+1日竞价分析的完整流程
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, '/mnt/workspace/working/scripts')
from stockapi_client import StockAPIClient

# 配置
DATA_DIR = "/mnt/workspace/working/data/T01"
RESULT_FILE = os.path.join(DATA_DIR, "selected_stocks.json")

def test_evening_analysis():
    """测试T日晚上分析"""
    print("=" * 60)
    print("T01龙头战法 - T日分析测试")
    print("=" * 60)

    client = StockAPIClient()
    test_date = '2026-02-13'

    # 检查是否为交易日
    print(f'\n检查 {test_date} 是否为交易日...')
    is_trade = client.get_trading_day(test_date)
    print(f'结果: {"是" if is_trade else "否"}')

    if not is_trade:
        print('不是交易日，跳过分析。')
        return

    # 获取涨停股票
    print(f'\n获取涨停股票...')
    stocks = client.get_limit_up_stocks(test_date)
    print(f'获取到 {len(stocks)} 只涨停股票')

    # 计算评分
    print('\n计算评分中...')
    scored_stocks = []

    for stock in stocks:
        code = stock.get('code')
        name = stock.get('name')
        score = 0
        details = {}

        # 1. 首次涨停时间（满分20分）
        first_time = stock.get('firstCeilingTime', '150000')
        time_minutes = client.parse_ceiling_time(first_time)
        if 570 <= time_minutes <= 600:
            score += 20
        elif 600 < time_minutes <= 630:
            score += 15
        elif 630 < time_minutes <= 660:
            score += 10
        elif 660 < time_minutes <= 720:
            score += 5
        details['first_ceiling_time'] = first_time

        # 2. 封成比（满分15分）
        seal_ratio = client.calculate_seal_ratio(stock)
        if seal_ratio >= 10:
            score += 15
        elif seal_ratio >= 5:
            score += 10
        elif seal_ratio >= 3:
            score += 5
        details['seal_ratio'] = round(seal_ratio, 2)

        # 3. 封单金额/流通市值（满分15分）
        seal_cap = client.calculate_seal_to_market_cap(stock)
        if seal_cap >= 0.05:
            score += 15
        elif seal_cap >= 0.03:
            score += 10
        elif seal_cap >= 0.01:
            score += 5
        details['seal_to_market_cap'] = round(seal_cap, 4)

        # 4. 换手率（满分10分）
        turnover = float(stock.get('turnoverRatio', 0))
        if 5 <= turnover <= 15:
            score += 10
        elif 3 <= turnover <= 20:
            score += 5
        details['turnover_rate'] = round(turnover, 2)

        # 5. 涨停主题（满分10分）
        if stock.get('plateName'):
            score += 10
            details['plate_name'] = stock.get('plateName')

        scored_stocks.append({
            'code': code,
            'name': name,
            'score': score,
            'details': details,
            'raw_data': stock
        })

    # 排序并选出前5名
    scored_stocks.sort(key=lambda x: x['score'], reverse=True)
    top5 = scored_stocks[:5]

    print(f'\n选出前5名：')
    for i, stock in enumerate(top5, 1):
        print(f'{i}. {stock["name"]}({stock["code"]}) - 评分: {stock["score"]}')
        print(f'   首次涨停: {stock["details"].get("first_ceiling_time")}, 封成比: {stock["details"].get("seal_ratio")}, 换手率: {stock["details"].get("turnover_rate")}%')

    # 保存结果
    os.makedirs(DATA_DIR, exist_ok=True)
    result_data = {
        'date': test_date,
        'selected_count': len(top5),
        'stocks': top5
    }

    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f'\n结果已保存到: {RESULT_FILE}')

    return top5

def test_morning_analysis():
    """测试T+1日早上竞价分析"""
    print("\n" + "=" * 60)
    print("T01龙头战法 - T+1日竞价分析测试")
    print("=" * 60)

    # 读取T日选出的股票
    if not os.path.exists(RESULT_FILE):
        print('错误：未找到T日选出的股票数据')
        return

    with open(RESULT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    stocks = data.get('stocks', [])
    print(f'\n读取到 {len(stocks)} 只T日选出的股票')

    # 模拟竞价分析
    print('\n模拟竞价分析...')
    recommendations = []

    for stock in stocks:
        code = stock['code']
        name = stock['name']
        t_score = stock['score']

        # 模拟竞价数据（实际应从API获取）
        # 这里使用T日数据作为示例
        print(f'\n分析 {name}({code})...')
        print(f'  T日评分: {t_score}')

        # 计算综合评分（示例）
        final_score = t_score * 0.6  # 简化计算

        if final_score >= 30:
            suggestion = "🔥 强烈建议买入"
            position = "30%"
        elif final_score >= 25:
            suggestion = "⭐ 建议买入"
            position = "20%"
        elif final_score >= 20:
            suggestion = "👀 可以考虑"
            position = "10%"
        else:
            suggestion = "⚠️ 观望为主"
            position = "0%"

        print(f'  最终评分: {final_score:.1f}')
        print(f'  建议: {suggestion}')

        recommendations.append({
            'code': code,
            'name': name,
            'position': position,
            'suggestion': suggestion,
            'final_score': final_score
        })

    # 排序
    recommendations.sort(key=lambda x: x['final_score'], reverse=True)

    print('\n' + "=" * 60)
    print("最终推荐")
    print("=" * 60)

    for i, rec in enumerate(recommendations[:3], 1):
        print(f'\n【{i}. {rec["name"]}({rec["code"]})】')
        print(f'  📈 建议: {rec["suggestion"]}')
        print(f'  💰 仓位: {rec["position"]}')
        print(f'  📊 评分: {rec["final_score"]:.1f}')

    return recommendations

def main():
    """主测试函数"""
    print("开始T01任务完整测试...\n")

    # 测试T日分析
    top5 = test_evening_analysis()

    if top5:
        # 测试T+1日分析
        recommendations = test_morning_analysis()

    print("\n" + "=" * 60)
    print("T01任务完整测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
