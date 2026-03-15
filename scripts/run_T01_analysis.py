#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01任务 - 龙头战法 - 使用指定日期数据进行分析
功能：分析指定日期的涨停股，选出前5名
"""

import json
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from stockapi_client import StockAPIClient

# 配置信息
DATA_DIR = "/mnt/workspace/working/data/T01"
STOCKS_FILE = os.path.join(DATA_DIR, "2024-02-02_stocks.json")
RESULT_FILE = os.path.join(DATA_DIR, "analysis_results.json")
TARGET_DATE = "2024-02-02"

def load_stocks():
    """加载涨停股数据"""
    if not os.path.exists(STOCKS_FILE):
        print(f"错误：未找到股票数据文件 {STOCKS_FILE}")
        return []

    with open(STOCKS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def calculate_score(stock_data, client, date):
    """
    计算股票的综合评分
    """
    score = 0.0
    details = {}

    try:
        stock_code = stock_data.get('code', '')

        # 1. 首次涨停时间（越早越好，满分20分）
        first_ceiling_time = stock_data.get('firstCeilingTime', '150000')
        time_minutes = client.parse_ceiling_time(first_ceiling_time)
        if 570 <= time_minutes <= 600:  # 10:00前
            score += 20
        elif 600 < time_minutes <= 630:  # 10:30前
            score += 15
        elif 630 < time_minutes <= 660:  # 11:00前
            score += 10
        elif 660 < time_minutes <= 720:  # 12:00前
            score += 5
        else:
            score += 0
        details['first_ceiling_time'] = first_ceiling_time
        details['first_ceiling_time_score'] = 20 if 570 <= time_minutes <= 600 else (15 if 600 < time_minutes <= 630 else (10 if 630 < time_minutes <= 660 else (5 if 660 < time_minutes <= 720 else 0)))

        # 2. 封成比（越大越好，满分15分）
        seal_ratio = client.calculate_seal_ratio(stock_data)
        if seal_ratio >= 10:
            score += 15
        elif seal_ratio >= 5:
            score += 10
        elif seal_ratio >= 3:
            score += 5
        else:
            score += 0
        details['seal_ratio'] = round(seal_ratio, 2)
        details['seal_ratio_score'] = 15 if seal_ratio >= 10 else (10 if seal_ratio >= 5 else (5 if seal_ratio >= 3 else 0))

        # 3. 封单金额/流通市值（越大越好，满分15分）
        seal_to_market_cap = client.calculate_seal_to_market_cap(stock_data)
        if seal_to_market_cap >= 0.05:
            score += 15
        elif seal_to_market_cap >= 0.03:
            score += 10
        elif seal_to_market_cap >= 0.01:
            score += 5
        else:
            score += 0
        details['seal_to_market_cap'] = round(seal_to_market_cap, 4)
        details['seal_to_market_cap_score'] = 15 if seal_to_market_cap >= 0.05 else (10 if seal_to_market_cap >= 0.03 else (5 if seal_to_market_cap >= 0.01 else 0))

        # 4. 龙虎榜数据（满分10分）
        try:
            top_list_data = client.check_stock_in_dragon_tiger(stock_code, date)
            if top_list_data:
                score += 10
                details['top_list_score'] = 10
            else:
                details['top_list_score'] = 0
        except:
            details['top_list_score'] = 0

        # 5. 主力资金净占比（越大越好，满分10分）
        try:
            capital_flow = client.get_stock_capital_flow(stock_code, date)
            main_net_ratio = 0
            if capital_flow:
                try:
                    main_net_ratio = float(capital_flow.get('mainAmountPercentage', 0))
                except:
                    pass

            if main_net_ratio >= 10:
                score += 10
            elif main_net_ratio >= 5:
                score += 7
            elif main_net_ratio >= 0:
                score += 3
            else:
                score += 0
            details['main_net_ratio'] = round(main_net_ratio, 2)
            details['main_net_ratio_score'] = 10 if main_net_ratio >= 10 else (7 if main_net_ratio >= 5 else (3 if main_net_ratio >= 0 else 0))
        except:
            details['main_net_ratio'] = 0
            details['main_net_ratio_score'] = 0

        # 6. 成交金额（适中为好，满分10分）
        amount = 0
        try:
            amount = float(stock_data.get('amount', 0)) / 10000
        except:
            pass

        if 50000 <= amount <= 200000:
            score += 10
        elif 20000 <= amount <= 500000:
            score += 5
        else:
            score += 0
        details['amount'] = round(amount, 0)
        details['amount_score'] = 10 if 50000 <= amount <= 200000 else (5 if 20000 <= amount <= 500000 else 0)

        # 7. 换手率（适中为好，满分10分）
        turnover_rate = 0
        try:
            turnover_rate = float(stock_data.get('turnoverRatio', 0))
        except:
            pass

        if 5 <= turnover_rate <= 15:
            score += 10
        elif 3 <= turnover_rate <= 20:
            score += 5
        else:
            score += 0
        details['turnover_rate'] = round(turnover_rate, 2)
        details['turnover_rate_score'] = 10 if 5 <= turnover_rate <= 15 else (5 if 3 <= turnover_rate <= 20 else 0)

        # 8. 量比（适中为好，满分10分）
        volume_ratio = 0
        details['volume_ratio'] = volume_ratio
        details['volume_ratio_score'] = 0

        # 9. 是否属于当日热点行业板块（满分10分）
        plate_name = stock_data.get('plate_name', '')
        if plate_name:
            score += 10
            details['hot_sector_score'] = 10
        else:
            details['hot_sector_score'] = 0

    except Exception as e:
        print(f"计算评分时出错: {e}")
        return (stock_data.get('code', ''), 0, {})

    return (stock_data.get('code', ''), score, details)

def select_top_stocks(stocks, client, date):
    """选出评分最高的前5名股票"""
    scored_stocks = []

    for i, stock in enumerate(stocks, 1):
        print(f"正在分析 {i}/{len(stocks)}: {stock.get('name')}({stock.get('code')})")
        code, score, details = calculate_score(stock, client, date)
        if score > 0:
            scored_stocks.append({
                'code': code,
                'name': stock.get('name', ''),
                'score': score,
                'details': details,
                'raw_data': stock
            })

    # 按评分降序排序
    scored_stocks.sort(key=lambda x: x['score'], reverse=True)

    # 返回前5名
    return scored_stocks[:5]

def save_results(selected_stocks, date):
    """保存分析结果"""
    result_data = {
        'date': date,
        'total_stocks': len(load_stocks()),
        'selected_count': len(selected_stocks),
        'stocks': selected_stocks
    }

    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {RESULT_FILE}")

def main():
    """主函数"""
    print("=" * 80)
    print(f"T01龙头战法 - 涨停股分析 - {TARGET_DATE}")
    print("=" * 80)

    # 加载股票数据
    print(f"\n正在加载股票数据...")
    stocks = load_stocks()

    if not stocks:
        print("未找到股票数据。")
        return

    print(f"成功加载 {len(stocks)} 只涨停股票。")

    # 初始化API客户端
    client = StockAPIClient()

    # 计算评分并选出前5名
    print(f"\n开始计算评分...")
    selected_stocks = select_top_stocks(stocks, client, TARGET_DATE)

    if not selected_stocks:
        print("没有符合条件的股票。")
        return

    # 显示结果
    print(f"\n" + "=" * 80)
    print(f"分析结果 - 选出前5名股票")
    print("=" * 80)

    for i, stock in enumerate(selected_stocks, 1):
        print(f"\n【{i}. {stock['name']}({stock['code']})】")
        print(f"  总评分: {stock['score']:.1f}")
        print(f"  首次涨停时间: {stock['details'].get('first_ceiling_time', 'N/A')} (得分: {stock['details'].get('first_ceiling_time_score', 0)})")
        print(f"  封成比: {stock['details'].get('seal_ratio', 'N/A')} (得分: {stock['details'].get('seal_ratio_score', 0)})")
        print(f"  封单/流通市值: {stock['details'].get('seal_to_market_cap', 'N/A')} (得分: {stock['details'].get('seal_to_market_cap_score', 0)})")
        print(f"  龙虎榜: {'有' if stock['details'].get('top_list_score', 0) > 0 else '无'} (得分: {stock['details'].get('top_list_score', 0)})")
        print(f"  主力资金净占比: {stock['details'].get('main_net_ratio', 'N/A')}% (得分: {stock['details'].get('main_net_ratio_score', 0)})")
        print(f"  成交金额: {stock['details'].get('amount', 'N/A')}万 (得分: {stock['details'].get('amount_score', 0)})")
        print(f"  换手率: {stock['details'].get('turnover_rate', 'N/A')}% (得分: {stock['details'].get('turnover_rate_score', 0)})")
        print(f"  热点板块: {'是' if stock['details'].get('hot_sector_score', 0) > 0 else '否'} (得分: {stock['details'].get('hot_sector_score', 0)})")

    # 保存结果
    save_results(selected_stocks, TARGET_DATE)

    print(f"\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
