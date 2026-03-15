#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票API工具函数
封装股票API的常用功能
"""

import requests
from datetime import datetime, timedelta

# API配置
API_BASE_URL = "https://www.stockapi.com.cn"
API_TOKEN = "516f4946db85f3f172e8ed29c6ad32f26148c58a38b33c74"

def is_trading_day(date=None):
    """
    查询指定日期是否为交易日

    Args:
        date: 日期字符串（格式：YYYY-MM-DD），默认为当天

    Returns:
        bool: True表示是交易日，False表示不是交易日
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    try:
        url = f"{API_BASE_URL}/v1/base/tradeDate"
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        }
        params = {
            "tradeDate": date
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # 检查返回码
        if data.get('code') == 20000:
            result = data.get('data', {})
            is_trade = result.get('isTradeDate', 0)
            return is_trade == 1
        else:
            print(f"API返回错误: {data.get('msg', '未知错误')}")
            return False

    except requests.exceptions.Timeout:
        print(f"查询交易日API超时: {date}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"查询交易日API失败: {e}")
        return False
    except Exception as e:
        print(f"查询交易日时发生错误: {e}")
        return False

def get_today_date():
    """获取今天的日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")

def get_yesterday_date():
    """获取昨天的日期字符串"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def get_tomorrow_date():
    """获取明天的日期字符串"""
    tomorrow = datetime.now() + timedelta(days=1)
    return tomorrow.strftime("%Y-%m-%d")

def find_previous_trading_day(start_date=None, max_days=10):
    """
    查找上一个交易日

    Args:
        start_date: 开始日期（格式：YYYY-MM-DD），默认为昨天
        max_days: 最多向前查找的天数

    Returns:
        str: 上一个交易日的日期字符串（YYYY-MM-DD），如果没有找到返回None
    """
    if start_date is None:
        start_date = get_yesterday_date()

    current_date = datetime.strptime(start_date, "%Y-%m-%d")

    for i in range(max_days):
        check_date = current_date - timedelta(days=i)
        date_str = check_date.strftime("%Y-%m-%d")

        if is_trading_day(date_str):
            return date_str

    return None

def find_next_trading_day(start_date=None, max_days=10):
    """
    查找下一个交易日

    Args:
        start_date: 开始日期（格式：YYYY-MM-DD），默认为明天
        max_days: 最多向后查找的天数

    Returns:
        str: 下一个交易日的日期字符串（YYYY-MM-DD），如果没有找到返回None
    """
    if start_date is None:
        start_date = get_tomorrow_date()

    current_date = datetime.strptime(start_date, "%Y-%m-%d")

    for i in range(max_days):
        check_date = current_date + timedelta(days=i)
        date_str = check_date.strftime("%Y-%m-%d")

        if is_trading_day(date_str):
            return date_str

    return None


def main():
    """测试函数"""
    print("测试交易日API...")

    # 测试今天是否为交易日
    today = get_today_date()
    print(f"\n今天 ({today}) 是否为交易日: {is_trading_day(today)}")

    # 测试昨天是否为交易日
    yesterday = get_yesterday_date()
    print(f"昨天 ({yesterday}) 是否为交易日: {is_trading_day(yesterday)}")

    # 测试查找上一个交易日
    prev_trade_date = find_previous_trading_day()
    print(f"上一个交易日: {prev_trade_date}")

    # 测试查找下一个交易日
    next_trade_date = find_next_trading_day()
    print(f"下一个交易日: {next_trade_date}")


if __name__ == "__main__":
    main()
