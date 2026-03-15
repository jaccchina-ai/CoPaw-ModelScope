#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01任务 - 龙头战法 - T日晚上分析脚本
功能：分析当日涨停股，选出前5名作为次日观察标的
"""

import json
import requests
from datetime import datetime, timedelta
import os
import sys

# 添加 scripts 目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from stockapi_client import StockAPIClient
from feishu_notifier import send_feishu_message

# 配置信息
DATA_DIR = "/mnt/workspace/working/data/T01"
RESULT_FILE = os.path.join(DATA_DIR, "selected_stocks.json")
FEISHU_USER_ID = "董欣#ad16"
FEISHU_SESSION_ID = "6661ad16"

def ensure_data_dir():
    """确保数据目录存在"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def calculate_score(stock_data, client, date):
    """
    计算股票的综合评分
    根据以下指标计算得分：
    1. 首次涨停时间（越早越好）- 20分
    2. 封成比（越大越好）- 15分
    3. 封单金额/流通市值（越大越好）- 15分
    4. 龙虎榜数据（如果有龙虎榜加分）- 10分
    5. 主力资金净占比（越大越好）- 10分
    6. 成交金额（适中为好）- 10分
    7. 换手率（适中为好）- 10分
    8. 量比（越大越好）- 10分
    9. 是否属于当日热点行业板块（是则加分）- 10分

    总分：100分

    返回：(股票代码, 评分, 详细数据)
    """
    score = 0.0
    details = {}

    try:
        stock_code = stock_data.get('code', '')

        # 1. 首次涨停时间（越早越好，满分20分）
        first_ceiling_time = stock_data.get('firstCeilingTime', '150000')
        time_minutes = client.parse_ceiling_time(first_ceiling_time)
        # 9:30开盘，最早9:30=570分钟，最晚15:00=900分钟
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
        if seal_to_market_cap >= 0.05:  # 5%以上
            score += 15
        elif seal_to_market_cap >= 0.03:  # 3%以上
            score += 10
        elif seal_to_market_cap >= 0.01:  # 1%以上
            score += 5
        else:
            score += 0
        details['seal_to_market_cap'] = round(seal_to_market_cap, 4)
        details['seal_to_market_cap_score'] = 15 if seal_to_market_cap >= 0.05 else (10 if seal_to_market_cap >= 0.03 else (5 if seal_to_market_cap >= 0.01 else 0))

        # 4. 龙虎榜数据（满分10分）
        top_list_data = client.check_stock_in_dragon_tiger(stock_code, date)
        if top_list_data:
            score += 10
            details['top_list_score'] = 10
        else:
            details['top_list_score'] = 0

        # 5. 主力资金净占比（越大越好，满分10分）
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

        # 6. 成交金额（适中为好，满分10分）
        amount = 0
        try:
            amount = float(stock_data.get('amount', 0)) / 10000  # 转换为万
        except:
            pass

        if 50000 <= amount <= 200000:  # 5亿-20亿
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

        # 8. 量比（越大越好，满分10分）
        volume_ratio = client.get_volume_ratio(stock_code, date)
        if volume_ratio >= 5:
            score += 10
        elif volume_ratio >= 3:
            score += 8
        elif volume_ratio >= 2:
            score += 5
        elif volume_ratio >= 1.5:
            score += 3
        else:
            score += 0
        details['volume_ratio'] = volume_ratio
        details['volume_ratio_score'] = 10 if volume_ratio >= 5 else (8 if volume_ratio >= 3 else (5 if volume_ratio >= 2 else (3 if volume_ratio >= 1.5 else 0)))

        # 9. 是否属于当日热点行业板块（满分10分）
        # 这里可以根据涨停主题判断，简单起见，如果有涨停主题就加分
        plate_name = stock_data.get('plateName', '')
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
    """
    选出评分最高的前5名股票
    """
    scored_stocks = []

    for stock in stocks:
        code, score, details = calculate_score(stock, client, date)
        if score > 0:  # 只保留有得分的股票
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
    """
    保存选出的股票到JSON文件，供T+1日使用
    """
    ensure_data_dir()

    result_data = {
        'date': date,
        'selected_count': len(selected_stocks),
        'stocks': selected_stocks
    }

    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {RESULT_FILE}")

def send_notification(selected_stocks, date):
    """
    发送通知给用户
    """
    if not selected_stocks:
        message = f"📊 T01龙头战法 - {date} 晚间分析\n\n今日未选出符合条件的股票"
    else:
        # 评分逻辑说明
        message = f"📊 T01龙头战法 - {date} 晚间分析\n\n"
        message += "━" * 30 + "\n"
        message += "📋 评分逻辑（满分100分）\n"
        message += "━" * 30 + "\n"
        message += "1️⃣ 首次涨停时间（20分）\n"
        message += "   10:00前=20分, 10:30前=15分\n"
        message += "   11:00前=10分, 12:00前=5分\n\n"
        message += "2️⃣ 封成比（15分）\n"
        message += "   ≥10倍=15分, ≥5倍=10分, ≥3倍=5分\n\n"
        message += "3️⃣ 封单金额/流通市值（15分）\n"
        message += "   ≥5%=15分, ≥3%=10分, ≥1%=5分\n\n"
        message += "4️⃣ 龙虎榜数据（10分）\n"
        message += "   有龙虎榜=10分\n\n"
        message += "5️⃣ 主力资金净占比（10分）\n"
        message += "   ≥10%=10分, ≥5%=7分, ≥0%=3分\n\n"
        message += "6️⃣ 成交金额（10分）\n"
        message += "   5-20亿=10分, 2-50亿=5分\n\n"
        message += "7️⃣ 换手率（10分）\n"
        message += "   5%-15%=10分, 3%-20%=5分\n\n"
        message += "8️⃣ 量比（10分）\n"
        message += "   1.5-5倍=10分, 1-8倍=5分\n\n"
        message += "9️⃣ 热点板块（10分）\n"
        message += "   属于热点板块=10分\n\n"
        message += "━" * 30 + "\n"
        message += f"今日选出 {len(selected_stocks)} 只观察标的\n"
        message += "━" * 30 + "\n\n"

        for i, stock in enumerate(selected_stocks, 1):
            details = stock['details']
            raw_data = stock.get('raw_data', {})

            # 获取板块信息
            industry = raw_data.get('industry', 'N/A')
            plate_name = raw_data.get('plateName', 'N/A')
            gl = raw_data.get('gl', '')

            message += f"【{i}. {stock['name']}({stock['code']})】\n"
            message += f"📊 总评分: {stock['score']:.0f}分\n\n"

            # 详细指标
            message += "📈 详细指标:\n"

            # 1. 首次涨停时间
            first_time = details.get('first_ceiling_time', 'N/A')
            time_score = details.get('first_ceiling_time_score', 0)
            message += f"  ⏰ 首次涨停: {first_time} ({time_score}分)\n"

            # 2. 封成比
            seal_ratio = details.get('seal_ratio', 0)
            seal_score = details.get('seal_ratio_score', 0)
            message += f"  📊 封成比: {seal_ratio}倍 ({seal_score}分)\n"

            # 3. 封单金额/流通市值
            seal_cap = details.get('seal_to_market_cap', 0)
            seal_cap_score = details.get('seal_to_market_cap_score', 0)
            message += f"  💰 封单/流通市值: {seal_cap*100:.2f}% ({seal_cap_score}分)\n"

            # 4. 龙虎榜
            top_list_score = details.get('top_list_score', 0)
            message += f"  🐯 龙虎榜: {'有' if top_list_score > 0 else '无'} ({top_list_score}分)\n"

            # 5. 主力资金净占比
            main_ratio = details.get('main_net_ratio', 0)
            main_score = details.get('main_net_ratio_score', 0)
            message += f"  💵 主力资金净比: {main_ratio}% ({main_score}分)\n"

            # 6. 成交金额
            amount = details.get('amount', 0)
            amount_score = details.get('amount_score', 0)
            message += f"  💵 成交金额: {amount:.0f}万 ({amount_score}分)\n"

            # 7. 换手率
            turnover = details.get('turnover_rate', 0)
            turnover_score = details.get('turnover_rate_score', 0)
            message += f"  🔄 换手率: {turnover}% ({turnover_score}分)\n"

            # 8. 热点板块
            hot_score = details.get('hot_sector_score', 0)
            message += f"  🔥 热点板块: {'是' if hot_score > 0 else '否'} ({hot_score}分)\n"

            # 所属板块
            message += f"\n🏢 所属板块:\n"
            message += f"  行业: {industry}\n"
            if plate_name and plate_name != 'N/A':
                message += f"  涨停主题: {plate_name}\n"
            if gl:
                concepts = gl.split(',')[:5]  # 只显示前5个概念
                message += f"  概念: {', '.join(concepts)}\n"

            message += "\n" + "─" * 30 + "\n\n"

        message += f"⏰ 明日早盘9:25将进行竞价分析，请关注推送消息。\n"
        message += f"⚠️ 风险提示: 以上分析仅供参考，投资有风险，请谨慎决策。"

    print(message)

    # 发送到飞书
    send_feishu_message(FEISHU_USER_ID, FEISHU_SESSION_ID, message)

def main():
    """主函数"""
    print("=" * 60)
    print(f"T01龙头战法 - T日分析脚本 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 初始化API客户端
    client = StockAPIClient()

    # 获取今天的日期
    today = client.get_today_date()

    # 判断是否为交易日
    print(f"\n正在检查今天 ({today}) 是否为交易日...")
    if not client.get_trading_day(today):
        print("今天不是交易日，跳过分析。")
        return

    print("今天是交易日，开始分析...")

    # 获取涨停股票
    print(f"\n正在获取 {today} 的涨停股票...")
    stocks = client.get_limit_up_stocks(today)

    if not stocks:
        print("未获取到涨停股票数据。")
        return

    print(f"获取到 {len(stocks)} 只涨停股票。")

    # 计算评分并选出前5名
    print("\n正在计算评分...")
    selected_stocks = select_top_stocks(stocks, client, today)

    if not selected_stocks:
        print("没有符合条件的股票。")
        return

    print(f"选出了 {len(selected_stocks)} 只股票：")
    for i, stock in enumerate(selected_stocks, 1):
        print(f"  {i}. {stock['name']}({stock['code']}) - 评分: {stock['score']:.1f}")

    # 保存结果
    print("\n正在保存结果...")
    save_results(selected_stocks, today)

    # 发送通知
    print("\n正在发送通知...")
    send_notification(selected_stocks, today)

    print("\n" + "=" * 60)
    print("T01龙头战法 - T日分析完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
