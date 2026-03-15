#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试评分逻辑
"""

import json
import sys
sys.path.append('/mnt/workspace/working/scripts')
from stockapi_client import StockAPIClient

# 加载测试数据
with open('/mnt/workspace/working/data/T01/test_stocks.json', 'r') as f:
    stocks = json.load(f)

client = StockAPIClient()
test_date = '2024-02-02'

print('开始计算评分...')
scored_stocks = []

for stock in stocks:
    code = stock.get('code')
    name = stock.get('name')

    # 简化评分测试
    score = 0
    details = {}

    # 1. 首次涨停时间
    first_time = stock.get('firstCeilingTime', '150000')
    time_minutes = client.parse_ceiling_time(first_time)
    if 570 <= time_minutes <= 600:
        score += 20
        details['time_score'] = 20

    # 2. 封成比
    seal_ratio = client.calculate_seal_ratio(stock)
    if seal_ratio >= 5:
        score += 10
        details['seal_score'] = 10

    # 3. 封单金额/流通市值
    seal_cap = client.calculate_seal_to_market_cap(stock)
    if seal_cap >= 0.03:
        score += 10
        details['cap_score'] = 10

    scored_stocks.append({
        'code': code,
        'name': name,
        'score': score,
        'details': details
    })

    print(f'{name}({code}): {score}分')

# 按评分排序
scored_stocks.sort(key=lambda x: x['score'], reverse=True)

print(f'\n前3名:')
for i, stock in enumerate(scored_stocks[:3], 1):
    print(f'{i}. {stock["name"]}({stock["code"]}) - {stock["score"]}分')
