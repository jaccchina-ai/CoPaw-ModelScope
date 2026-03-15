#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01任务 - 龙头战法 - T+1日竞价分析脚本
功能：分析竞价数据，对T日选出的股票进行打分排序，推送买卖建议
"""

import json
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

def get_previous_trading_day():
    """获取上一个交易日的日期"""
    # 从RESULT_FILE中读取日期
    if os.path.exists(RESULT_FILE):
        with open(RESULT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('date', '')
    return ''

def get_selected_stocks():
    """
    获取T日选出的观察标的
    """
    if not os.path.exists(RESULT_FILE):
        print("错误：未找到T日选出的股票数据。")
        return []

    with open(RESULT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('stocks', [])

def get_stock_kline(stock_code, date):
    """
    获取股票日K线数据（用于获取量比等指标）

    Args:
        stock_code: 股票代码
        date: 日期字符串（格式：YYYY-MM-DD）

    Returns:
        dict: K线数据
    """
    try:
        client = StockAPIClient()
        # 这里需要调用股票K线接口
        # API文档：https://www.stockapi.com.cn/menu/11
        url = f"https://www.stockapi.com.cn/v1/base/dayK"
        params = {
            "code": stock_code,
            "date": date
        }

        response = requests.get(url, headers=client.headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data.get('code') == 20000:
            kline_data = data.get('data', {})
            if isinstance(kline_data, list) and len(kline_data) > 0:
                return kline_data[0]
            return kline_data

        return {}

    except Exception as e:
        print(f"获取股票K线数据时出错: {e}")
        return {}

def get_auction_analysis(stock_code):
    """
    获取指定股票的竞价分析数据

    Args:
        stock_code: 股票代码

    Returns:
        dict: 竞价数据
    """
    try:
        client = StockAPIClient()

        # 获取早盘热点板块竞价所属个股
        hot_sector_stocks = client.get_hot_sector_stocks()

        # 查找目标股票
        for stock in hot_sector_stocks:
            if stock.get('code') == stock_code:
                return stock

        return {}

    except Exception as e:
        print(f"获取股票 {stock_code} 竞价数据时出错: {e}")
        return {}

def calculate_morning_score(auction_data, t_score, t_stock_details):
    """
    计算竞价阶段的评分
    根据以下指标计算得分：
    1. 竞价开盘涨幅（适中为好，高开不宜过多）
    2. 竞价量比（越大越好）
    3. 竞价换手率（适中为好）
    4. 竞价金额（越大越好）

    综合T日评分，给出最终评分和建议

    返回：(股票代码, 最终评分, 竞价评分, 买卖建议, 详细信息)
    """
    auction_score = 0.0
    details = {}

    try:
        # 1. 竞价开盘涨幅（适中为好，满分25分）
        # 2%-8%之间比较好，过高容易被砸盘
        open_change_rate = auction_data.get('changeRatio', 0)
        try:
            open_change_rate = float(open_change_rate)
        except:
            open_change_rate = 0

        if 2 <= open_change_rate <= 8:
            auction_score += 25
        elif 1 <= open_change_rate <= 10:
            auction_score += 15
        elif 0 <= open_change_rate <= 12:
            auction_score += 5
        elif open_change_rate > 12:  # 高开过多风险大
            auction_score -= 10
        elif open_change_rate < -2:  # 低开不看
            auction_score -= 20
        else:
            auction_score += 0

        details['open_change_rate'] = round(open_change_rate, 2)
        details['open_change_rate_score'] = 25 if 2 <= open_change_rate <= 8 else (15 if 1 <= open_change_rate <= 10 else (5 if 0 <= open_change_rate <= 12 else (-10 if open_change_rate > 12 else (-20 if open_change_rate < -2 else 0))))

        # 2. 竞价量比（越大越好，满分25分）
        volume_ratio = auction_data.get('volumeRatio', 0)
        try:
            volume_ratio = float(volume_ratio)
        except:
            volume_ratio = 0

        if volume_ratio >= 5:
            auction_score += 25
        elif volume_ratio >= 3:
            auction_score += 20
        elif volume_ratio >= 2:
            auction_score += 15
        elif volume_ratio >= 1.5:
            auction_score += 10
        elif volume_ratio >= 1:
            auction_score += 5
        else:
            auction_score += 0

        details['volume_ratio'] = round(volume_ratio, 2)
        details['volume_ratio_score'] = 25 if volume_ratio >= 5 else (20 if volume_ratio >= 3 else (15 if volume_ratio >= 2 else (10 if volume_ratio >= 1.5 else (5 if volume_ratio >= 1 else 0))))

        # 3. 竞价换手率（适中为好，满分25分）
        turnover_rate = auction_data.get('turnoverRatio', 0)
        try:
            turnover_rate = float(turnover_rate)
        except:
            turnover_rate = 0

        if 1 <= turnover_rate <= 3:
            auction_score += 25
        elif 0.5 <= turnover_rate <= 5:
            auction_score += 20
        elif 0.3 <= turnover_rate <= 7:
            auction_score += 10
        elif turnover_rate > 7:  # 换手率过高风险大
            auction_score -= 10
        else:
            auction_score += 0

        details['turnover_rate'] = round(turnover_rate, 2)
        details['turnover_rate_score'] = 25 if 1 <= turnover_rate <= 3 else (20 if 0.5 <= turnover_rate <= 5 else (10 if 0.3 <= turnover_rate <= 7 else (-10 if turnover_rate > 7 else 0)))

        # 4. 竞价金额（越大越好，满分25分）
        amount = auction_data.get('amount', 0)
        try:
            amount = float(amount) / 10000  # 转换为万
        except:
            amount = 0

        if amount >= 5000:
            auction_score += 25
        elif amount >= 3000:
            auction_score += 20
        elif amount >= 1000:
            auction_score += 10
        elif amount >= 500:
            auction_score += 5
        else:
            auction_score += 0

        details['amount'] = round(amount, 0)
        details['amount_score'] = 25 if amount >= 5000 else (20 if amount >= 3000 else (10 if amount >= 1000 else (5 if amount >= 500 else 0)))

        # 计算综合评分（T日评分占40%，竞价评分占60%）
        final_score = t_score * 0.4 + auction_score * 0.6

        # 给出买卖建议
        if final_score >= 80:
            suggestion = "🔥 强烈建议买入"
            position = "30%"
        elif final_score >= 70:
            suggestion = "⭐ 建议买入"
            position = "20%"
        elif final_score >= 60:
            suggestion = "👀 可以考虑"
            position = "10%"
        elif final_score >= 50:
            suggestion = "⚠️ 观望为主"
            position = "0%"
        else:
            suggestion = "❌ 不建议买入"
            position = "0%"

        return final_score, auction_score, suggestion, position, details

    except Exception as e:
        print(f"计算竞价评分时出错: {e}")
        return 0, 0, "❌ 数据异常", "0%", {}

def analyze_and_rank(stocks, today):
    """
    对T日选出的股票进行竞价分析并排序
    """
    analyzed_stocks = []

    for stock in stocks:
        code = stock['code']
        t_score = stock['score']
        name = stock['name']
        t_details = stock.get('details', {})

        print(f"\n正在分析 {name}({code})...")

        # 获取竞价数据
        auction_data = get_auction_analysis(code)

        if not auction_data:
            print(f"  未获取到竞价数据，跳过。")
            continue

        # 计算竞价评分
        final_score, auction_score, suggestion, position, details = calculate_morning_score(auction_data, t_score, t_details)

        analyzed_stocks.append({
            'code': code,
            'name': name,
            't_score': t_score,
            'auction_score': auction_score,
            'final_score': final_score,
            'suggestion': suggestion,
            'position': position,
            'details': details,
            'raw_auction_data': auction_data
        })

        print(f"  T日评分: {t_score:.1f}")
        print(f"  竞价评分: {auction_score:.1f}")
        print(f"  最终评分: {final_score:.1f}")
        print(f"  建议: {suggestion}")

    # 按最终评分降序排序
    analyzed_stocks.sort(key=lambda x: x['final_score'], reverse=True)

    return analyzed_stocks

def generate_recommendation(analyzed_stocks):
    """
    生成买卖建议
    """
    recommendations = []

    for stock in analyzed_stocks:
        # 只推荐评分>=60且仓位>0的股票
        if stock['final_score'] >= 60 and stock['position'] != '0%':
            # 生成买入理由
            reasons = []

            # 竞价开盘涨幅
            open_rate = stock['details'].get('open_change_rate', 0)
            if 2 <= open_rate <= 8:
                reasons.append(f"竞价涨幅{open_rate:.1f}%合理")

            # 竞价量比
            volume_ratio = stock['details'].get('volume_ratio', 0)
            if volume_ratio >= 3:
                reasons.append(f"竞价量比{volume_ratio:.1f}较高")

            # 竞价换手率
            turnover = stock['details'].get('turnover_rate', 0)
            if 1 <= turnover <= 3:
                reasons.append(f"竞价换手{turnover:.1f}%适中")

            # 竞价金额
            amount = stock['details'].get('amount', 0)
            if amount >= 3000:
                reasons.append(f"竞价金额{amount:.0f}万较大")

            # T日评分
            if stock['t_score'] >= 70:
                reasons.append("T日质量较高")

            reasons_str = "、".join(reasons) if reasons else "综合指标良好"

            recommendations.append({
                'code': stock['code'],
                'name': stock['name'],
                'position': stock['position'],
                'suggestion': stock['suggestion'],
                'final_score': stock['final_score'],
                'reasons': reasons_str
            })

    return recommendations

def send_recommendation(recommendations, today):
    """
    发送买卖建议给用户
    """
    if not recommendations:
        message = f"📊 T01龙头战法 - {today} 早盘建议\n\n今日观察标的中暂无强烈买入信号，建议保持谨慎。"
    else:
        message = f"📊 T01龙头战法 - {today} 早盘建议\n\n今日推荐买入股票：\n\n"

        for i, rec in enumerate(recommendations, 1):
            message += f"【{i}. {rec['name']}({rec['code']})】\n"
            message += f"  📈 建议: {rec['suggestion']}\n"
            message += f"  💰 仓位: {rec['position']}\n"
            message += f"  🎯 理由: {rec['reasons']}\n"
            message += f"  📊 评分: {rec['final_score']:.1f}\n\n"

        message += f"⚠️ 提醒：以上建议仅供参考，投资有风险，请结合实际情况决策。"

    print(message)

    # 发送到飞书
    send_feishu_message(FEISHU_USER_ID, FEISHU_SESSION_ID, message)

def main():
    """主函数"""
    print("=" * 60)
    print(f"T01龙头战法 - T+1日竞价分析脚本 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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

    # 获取T日选出的股票
    print("\n正在获取T日选出的观察标的...")
    stocks = get_selected_stocks()

    if not stocks:
        print("未找到T日选出的股票数据。")
        return

    print(f"获取到 {len(stocks)} 只观察标的。")

    # 进行竞价分析
    print("\n正在进行竞价分析...")
    analyzed_stocks = analyze_and_rank(stocks, today)

    if not analyzed_stocks:
        print("没有可分析的股票。")
        return

    # 生成买卖建议
    print("\n正在生成买卖建议...")
    recommendations = generate_recommendation(analyzed_stocks)

    # 发送建议
    print("\n正在发送建议...")
    send_recommendation(recommendations, today)

    print("\n" + "=" * 60)
    print("T01龙头战法 - T+1日竞价分析完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
