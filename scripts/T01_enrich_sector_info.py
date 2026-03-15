#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 补充交易记录板块信息
从stockAPI获取涨停股板块数据，补充到交易记录中
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, '/mnt/workspace/working/scripts')
from stockapi_client import StockAPIClient

# 数据路径
DATA_BASE_DIR = "/mnt/workspace/working/data/T01"
TRADES_FILE = os.path.join(DATA_BASE_DIR, "trades.json")


def load_trades():
    """加载交易记录"""
    with open(TRADES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_trades(data):
    """保存交易记录"""
    with open(TRADES_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_sector_from_limit_up(client, stock_code, date):
    """
    从涨停股数据获取板块信息
    
    Args:
        client: StockAPIClient实例
        stock_code: 股票代码
        date: 日期
    
    Returns:
        板块名称或None
    """
    try:
        stocks = client.get_limit_up_stocks(date)
        if stocks:
            for s in stocks:
                if s.get('code') == stock_code:
                    return {
                        'sector': s.get('plateName', '') or s.get('industry', ''),
                        'plate_reason': s.get('plateReason', ''),
                        'industry': s.get('industry', '')
                    }
        return None
    except Exception as e:
        print(f"    获取涨停股数据失败: {date} - {e}")
        return None


def main():
    """主函数"""
    print("=" * 70)
    print("T01龙头战法 - 补充交易记录板块信息")
    print("=" * 70)
    
    client = StockAPIClient()
    data = load_trades()
    trades = data.get('trades', [])
    
    print(f"\n总交易数: {len(trades)}")
    
    # 按日期分组获取板块信息
    date_stocks = {}
    for trade in trades:
        t_date = trade.get('t_date', '')
        stock_code = trade.get('stock_code', '')
        
        if t_date and stock_code:
            if t_date not in date_stocks:
                date_stocks[t_date] = []
            date_stocks[t_date].append((stock_code, trade))
    
    print(f"\n需要处理 {len(date_stocks)} 个交易日")
    
    # 获取板块信息并更新
    updated_count = 0
    for date, stock_list in sorted(date_stocks.items()):
        print(f"\n处理 {date} ({len(stock_list)}只股票)...")
        
        # 检查是否已有板块信息
        all_have_sector = all(
            t.get('sector') or t.get('plate_name') 
            for _, t in stock_list
        )
        
        if all_have_sector:
            print(f"  已有板块信息，跳过")
            continue
        
        # 获取该日期的涨停股数据
        sector_data = {}
        try:
            stocks = client.get_limit_up_stocks(date)
            if stocks:
                for s in stocks:
                    sector_data[s.get('code')] = {
                        'sector': s.get('plateName', '') or s.get('industry', ''),
                        'plate_name': s.get('plateName', ''),
                        'plate_reason': s.get('plateReason', ''),
                        'industry': s.get('industry', '')
                    }
        except Exception as e:
            print(f"  ⚠️ 获取数据失败: {e}")
            continue
        
        # 更新交易记录
        for stock_code, trade in stock_list:
            if stock_code in sector_data:
                info = sector_data[stock_code]
                trade['sector'] = info['sector']
                trade['plate_name'] = info['plate_name']
                trade['plate_reason'] = info['plate_reason']
                trade['industry'] = info['industry']
                updated_count += 1
                print(f"  ✅ {trade.get('stock_name')}({stock_code}): {info['sector']}")
            else:
                # 尝试相邻日期
                found = False
                for delta in [-1, 1, -2, 2]:
                    from datetime import timedelta
                    try:
                        dt = datetime.strptime(date, '%Y-%m-%d')
                        check_date = (dt + timedelta(days=delta)).strftime('%Y-%m-%d')
                        stocks = client.get_limit_up_stocks(check_date)
                        if stocks:
                            for s in stocks:
                                if s.get('code') == stock_code:
                                    info = {
                                        'sector': s.get('plateName', '') or s.get('industry', ''),
                                        'plate_name': s.get('plateName', ''),
                                        'plate_reason': s.get('plateReason', ''),
                                        'industry': s.get('industry', '')
                                    }
                                    trade['sector'] = info['sector']
                                    trade['plate_name'] = info['plate_name']
                                    trade['plate_reason'] = info['plate_reason']
                                    trade['industry'] = info['industry']
                                    updated_count += 1
                                    print(f"  ✅ {trade.get('stock_name')}({stock_code}): {info['sector']} (from {check_date})")
                                    found = True
                                    break
                        if found:
                            break
                    except:
                        pass
                
                if not found:
                    print(f"  ❌ {trade.get('stock_name')}({stock_code}): 未找到板块信息")
    
    # 保存更新后的数据
    data['trades'] = trades
    data['sector_enriched_at'] = datetime.now().isoformat()
    save_trades(data)
    
    print(f"\n" + "=" * 70)
    print(f"✅ 完成! 更新了 {updated_count} 条记录")
    print("=" * 70)
    
    # 统计板块分布
    sector_count = {}
    for trade in trades:
        sector = trade.get('sector', '未知')
        if sector:
            sector_count[sector] = sector_count.get(sector, 0) + 1
    
    print(f"\n【板块分布】")
    for sector, count in sorted(sector_count.items(), key=lambda x: -x[1]):
        print(f"  {sector}: {count}笔")


if __name__ == "__main__":
    main()
