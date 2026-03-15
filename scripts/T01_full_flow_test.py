#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 完整流程测试
T日: 2026-02-12
T+1日: 2026-02-13
"""

import json
import sys
import os
from datetime import datetime

sys.path.insert(0, '/mnt/workspace/working/scripts')
from stockapi_client import StockAPIClient
from feishu_notifier import send_feishu_message

# 配置
DATA_DIR = "/mnt/workspace/working/data/T01"
RESULT_FILE = os.path.join(DATA_DIR, "selected_stocks.json")
FEISHU_CHAT_ID = "oc_ff08c55a23630937869cd222dad0bf14"

# 测试日期
T_DATE = '2026-02-12'
T1_DATE = '2026-02-13'


# ==================== T日分析函数 ====================

def calculate_score(stock_data, client, date, hot_sectors=None):
    """计算股票评分"""
    score = 0.0
    details = {}

    try:
        stock_code = stock_data.get('code', '')
        plate_name = stock_data.get('plateName', '')

        # 1. 首次涨停时间（20分）
        first_ceiling_time = stock_data.get('firstCeilingTime', '150000')
        time_minutes = client.parse_ceiling_time(first_ceiling_time)
        if time_minutes <= 570:
            time_score = 20.0
        elif time_minutes <= 600:
            time_score = 20.0 - (time_minutes - 570) * 0.167
        elif time_minutes <= 630:
            time_score = 15.0 - (time_minutes - 600) * 0.167
        elif time_minutes <= 660:
            time_score = 10.0 - (time_minutes - 630) * 0.167
        elif time_minutes <= 720:
            time_score = 5.0 - (time_minutes - 660) * 0.083
        else:
            time_score = 0.0
        score += time_score
        details['first_ceiling_time'] = first_ceiling_time
        details['first_ceiling_time_score'] = round(time_score, 2)

        # 2. 封成比（15分）
        seal_ratio = client.calculate_seal_ratio(stock_data)
        if seal_ratio >= 10:
            seal_score = 15.0
        elif seal_ratio >= 5:
            seal_score = 10.0 + (seal_ratio - 5) * 1.0
        elif seal_ratio >= 3:
            seal_score = 5.0 + (seal_ratio - 3) * 2.5
        elif seal_ratio >= 1:
            seal_score = seal_ratio * 1.67
        else:
            seal_score = seal_ratio * 1.67
        score += seal_score
        details['seal_ratio'] = round(seal_ratio, 2)
        details['seal_ratio_score'] = round(seal_score, 2)

        # 3. 封单/流通市值（15分）
        seal_to_market_cap = client.calculate_seal_to_market_cap(stock_data)
        if seal_to_market_cap >= 0.05:
            cap_score = 15.0
        elif seal_to_market_cap >= 0.03:
            cap_score = 10.0 + (seal_to_market_cap - 0.03) * 250
        elif seal_to_market_cap >= 0.01:
            cap_score = 5.0 + (seal_to_market_cap - 0.01) * 250
        else:
            cap_score = seal_to_market_cap * 500
        score += cap_score
        details['seal_to_market_cap'] = round(seal_to_market_cap, 4)
        details['seal_to_market_cap_score'] = round(cap_score, 2)

        # 4. 龙虎榜（10分）
        top_list_data = client.check_stock_in_dragon_tiger(stock_code, date)
        if top_list_data:
            score += 10.0
            details['top_list_score'] = 10.0
        else:
            details['top_list_score'] = 0.0

        # 5. 主力资金净占比（10分）
        capital_flow = client.get_stock_capital_flow(stock_code, date)
        main_net_ratio = 0
        if capital_flow:
            try:
                main_net_ratio = float(capital_flow.get('mainAmountPercentage', 0))
            except:
                pass
        if main_net_ratio >= 10:
            main_score = 10.0
        elif main_net_ratio >= 5:
            main_score = 7.0 + (main_net_ratio - 5) * 0.6
        elif main_net_ratio >= 0:
            main_score = 3.0 + main_net_ratio * 0.8
        elif main_net_ratio >= -5:
            main_score = 3.0 + main_net_ratio * 0.3
        else:
            main_score = 1.5 + main_net_ratio * 0.1
        score += max(0, main_score)
        details['main_net_ratio'] = round(main_net_ratio, 2)
        details['main_net_ratio_score'] = round(max(0, main_score), 2)

        # 6. 成交金额（10分）
        amount = 0
        try:
            amount = float(stock_data.get('amount', 0)) / 10000
        except:
            pass
        if 50000 <= amount <= 200000:
            amount_score = 10.0
        elif 20000 <= amount < 50000:
            amount_score = 7.0 + (amount - 20000) / 30000 * 3
        elif 200000 < amount <= 500000:
            amount_score = 7.0 - (amount - 200000) / 300000 * 2
        else:
            amount_score = max(0, 5.0 - abs(amount - 100000) / 100000 * 5)
        score += amount_score
        details['amount'] = round(amount, 0)
        details['amount_score'] = round(amount_score, 2)

        # 7. 换手率（10分）
        turnover_rate = 0
        try:
            turnover_rate = float(stock_data.get('turnoverRatio', 0))
        except:
            pass
        if 5 <= turnover_rate <= 15:
            turnover_score = 10.0
        elif 3 <= turnover_rate < 5:
            turnover_score = 7.0 + (turnover_rate - 3) * 1.5
        elif 15 < turnover_rate <= 20:
            turnover_score = 7.0 - (turnover_rate - 15) * 0.4
        elif 1 <= turnover_rate < 3:
            turnover_score = turnover_rate * 2.33
        else:
            turnover_score = max(0, 5.0 - abs(turnover_rate - 10) * 0.5)
        score += turnover_score
        details['turnover_rate'] = round(turnover_rate, 2)
        details['turnover_rate_score'] = round(turnover_score, 2)

        # 8. 量比（10分）
        volume_ratio = client.get_volume_ratio(stock_code, date)
        if volume_ratio >= 5:
            volume_score = 10.0
        elif volume_ratio >= 3:
            volume_score = 8.0 + (volume_ratio - 3) * 1.0
        elif volume_ratio >= 2:
            volume_score = 5.0 + (volume_ratio - 2) * 1.5
        elif volume_ratio >= 1.5:
            volume_score = 3.0 + (volume_ratio - 1.5) * 4.0
        elif volume_ratio >= 1:
            volume_score = volume_ratio * 2.0
        else:
            volume_score = volume_ratio * 2.0
        score += volume_score
        details['volume_ratio'] = volume_ratio
        details['volume_ratio_score'] = round(volume_score, 2)

        # 9. 热点板块（10分）
        invalid_themes = ['其他', '公告', '复牌', '新股', 'ST', '']
        is_valid_theme = plate_name and plate_name not in invalid_themes
        
        is_hot_sector = False
        matched_sector = None
        
        if hot_sectors and is_valid_theme:
            gl = stock_data.get('gl', '')
            concepts = gl.split(',') if gl else []
            
            for hot_sector in hot_sectors:
                sector_name = hot_sector['name']
                if plate_name and sector_name in plate_name:
                    is_hot_sector = True
                    matched_sector = sector_name
                    break
                if plate_name and plate_name in sector_name:
                    is_hot_sector = True
                    matched_sector = sector_name
                    break
                for concept in concepts:
                    if sector_name in concept or concept in sector_name:
                        is_hot_sector = True
                        matched_sector = sector_name
                        break
                if is_hot_sector:
                    break
        
        if is_hot_sector:
            score += 10.0
            details['hot_sector_score'] = 10.0
            details['is_hot_sector'] = True
            details['matched_sector'] = matched_sector
        else:
            details['hot_sector_score'] = 0.0
            details['is_hot_sector'] = False
            details['matched_sector'] = None

    except Exception as e:
        print(f"计算评分时出错: {e}")
        return (stock_data.get('code', ''), 0, {})

    return (stock_data.get('code', ''), round(score, 2), details)


def get_hot_sectors(client, date, top_n=5):
    """获取热点板块"""
    hot_sectors_data = client.get_hot_sectors(date)
    if not hot_sectors_data:
        return []
    
    hot_sectors_data.sort(key=lambda x: float(x.get('qiangdu', 0)), reverse=True)
    top_sectors = hot_sectors_data[:top_n]
    
    hot_sectors = []
    for sector in top_sectors:
        hot_sectors.append({
            'name': sector.get('bkName', ''),
            'code': sector.get('bkCode', ''),
            'change': float(sector.get('qjzf', 0)),
            'net_flow': float(sector.get('qjje', 0)),
            'strength': float(sector.get('qiangdu', 0)),
            'flow_days': int(sector.get('jlrts', 0))
        })
    
    return hot_sectors


def get_emotion_analysis(client):
    """获取情绪周期分析"""
    emotion_data = client.get_latest_emotion()
    if not emotion_data:
        return {}
    
    szbl = float(emotion_data.get('szbl', 0))
    lbjs = int(emotion_data.get('lbjs', 0))
    dmqx = float(emotion_data.get('dmqx', 0))
    drqx = float(emotion_data.get('drqx', 0))
    ztjs = int(emotion_data.get('ztjs', 0))
    dbcgl = float(emotion_data.get('dbcgl', 0))
    dtjs = int(emotion_data.get('dtjs', 0))
    zxgd = int(emotion_data.get('zxgd', 0))
    
    emotion_score = 0
    
    if szbl >= 80: emotion_score += 30
    elif szbl >= 60: emotion_score += 25
    elif szbl >= 40: emotion_score += 15
    elif szbl >= 20: emotion_score += 5
    
    if dbcgl >= 80: emotion_score += 25
    elif dbcgl >= 60: emotion_score += 20
    elif dbcgl >= 40: emotion_score += 10
    
    if lbjs >= 50: emotion_score += 15
    elif lbjs >= 30: emotion_score += 10
    elif lbjs >= 10: emotion_score += 5
    
    if drqx >= 100: emotion_score += 15
    elif drqx >= 50: emotion_score += 10
    elif drqx >= 20: emotion_score += 5
    
    if dmqx >= 100: emotion_score -= 15
    elif dmqx >= 50: emotion_score -= 10
    elif dmqx >= 20: emotion_score -= 5
    
    if ztjs > 0 and dtjs == 0: emotion_score += 15
    elif ztjs > dtjs * 3: emotion_score += 10
    elif ztjs > dtjs: emotion_score += 5
    
    emotion_score = max(0, min(100, emotion_score))
    
    if emotion_score >= 80:
        cycle_stage, risk_level, position_advice = "高潮期", "低", "可满仓操作"
    elif emotion_score >= 60:
        cycle_stage, risk_level, position_advice = "上升期", "中低", "可7-8成仓位"
    elif emotion_score >= 40:
        cycle_stage, risk_level, position_advice = "震荡期", "中", "建议5成仓位"
    elif emotion_score >= 20:
        cycle_stage, risk_level, position_advice = "退潮期", "中高", "建议3成仓位"
    else:
        cycle_stage, risk_level, position_advice = "冰点期", "高", "建议空仓观望"
    
    return {
        'emotion_score': emotion_score,
        'cycle_stage': cycle_stage,
        'risk_level': risk_level,
        'position_advice': position_advice,
        'szbl': szbl, 'lbjs': lbjs, 'dmqx': dmqx, 'drqx': drqx,
        'ztjs': ztjs, 'dtjs': dtjs, 'dbcgl': dbcgl, 'zxgd': zxgd
    }


def t_day_analysis(client, t_date):
    """T日晚上分析"""
    print("\n" + "=" * 60)
    print(f"T日分析 - {t_date}")
    print("=" * 60)
    
    # 获取涨停股
    print(f"\n获取 {t_date} 涨停股...")
    stocks = client.get_limit_up_stocks(t_date)
    print(f"获取到 {len(stocks)} 只涨停股")
    
    # 获取热点板块
    print("\n获取热点板块...")
    hot_sectors = get_hot_sectors(client, t_date)
    for i, s in enumerate(hot_sectors, 1):
        print(f"  {i}. {s['name']} - 强度: {s['strength']:.0f}")
    
    # 获取情绪周期
    print("\n获取情绪周期...")
    emotion = get_emotion_analysis(client)
    if emotion:
        print(f"  情绪评分: {emotion['emotion_score']}分")
        print(f"  周期阶段: {emotion['cycle_stage']}")
    
    # 计算评分
    print("\n计算评分...")
    scored_stocks = []
    for stock in stocks:
        code, score, details = calculate_score(stock, client, t_date, hot_sectors)
        if score > 0:
            scored_stocks.append({
                'code': code,
                'name': stock.get('name', ''),
                'score': score,
                'details': details,
                'raw_data': stock
            })
    
    # 排序选前5
    scored_stocks.sort(key=lambda x: x['score'], reverse=True)
    top5 = scored_stocks[:5]
    
    print(f"\n选出前5名:")
    for i, s in enumerate(top5, 1):
        print(f"  {i}. {s['name']}({s['code']}) - {s['score']:.2f}分")
    
    # 保存结果
    os.makedirs(DATA_DIR, exist_ok=True)
    result = {
        't_date': t_date,
        't1_date': T1_DATE,
        'emotion': emotion,
        'hot_sectors': hot_sectors,
        'selected_stocks': top5
    }
    
    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存")
    
    return top5, emotion, hot_sectors


def t1_day_analysis(client, t1_date, t_data):
    """T+1日早上竞价分析"""
    print("\n" + "=" * 60)
    print(f"T+1日分析 - {t1_date}")
    print("=" * 60)
    
    t_stocks = t_data.get('selected_stocks', [])
    t_emotion = t_data.get('emotion', {})
    
    print(f"\nT日选出的 {len(t_stocks)} 只股票:")
    for i, s in enumerate(t_stocks, 1):
        print(f"  {i}. {s['name']}({s['code']}) - T日评分: {s['score']:.2f}")
    
    # 获取T+1日涨停股
    print(f"\n获取 {t1_date} 涨停股...")
    t1_stocks = client.get_limit_up_stocks(t1_date)
    t1_codes = [s.get('code') for s in t1_stocks]
    print(f"T+1日涨停股数量: {len(t1_stocks)}")
    
    # 分析每只股票的表现
    print("\n分析T日选出股票在T+1日的表现:")
    results = []
    
    for stock in t_stocks:
        code = stock['code']
        name = stock['name']
        t_score = stock['score']
        
        # 检查是否继续涨停
        is_continue_limit = code in t1_codes
        
        if is_continue_limit:
            # 找到T+1日数据
            t1_data = None
            for s in t1_stocks:
                if s.get('code') == code:
                    t1_data = s
                    break
            
            result = {
                'code': code,
                'name': name,
                't_score': t_score,
                'status': '继续涨停',
                'is_success': True,
                't1_data': t1_data
            }
            print(f"  ✅ {name}({code}) - 继续涨停")
        else:
            result = {
                'code': code,
                'name': name,
                't_score': t_score,
                'status': '未涨停',
                'is_success': False,
                't1_data': None
            }
            print(f"  ❌ {name}({code}) - 未涨停")
        
        results.append(result)
    
    # 统计
    success_count = sum(1 for r in results if r['is_success'])
    success_rate = success_count / len(results) * 100 if results else 0
    
    print(f"\n统计结果:")
    print(f"  成功连板: {success_count}/{len(results)}")
    print(f"  成功率: {success_rate:.1f}%")
    
    return results, success_rate


def generate_report(t_results, t1_results, t_emotion, t1_emotion, t_hot_sectors):
    """生成完整报告"""
    print("\n" + "=" * 60)
    print("生成完整报告")
    print("=" * 60)
    
    # 构建消息
    message = f"📊 T01龙头战法 - 完整流程测试报告\n\n"
    
    # T日信息
    message += f"📅 T日: {T_DATE}\n"
    message += f"📅 T+1日: {T1_DATE}\n\n"
    
    # T日情绪
    if t_emotion:
        message += "📈 T日情绪周期\n"
        message += "━" * 30 + "\n"
        message += f"情绪评分: {t_emotion['emotion_score']}分\n"
        message += f"周期阶段: {t_emotion['cycle_stage']}\n"
        message += f"风险等级: {t_emotion['risk_level']}\n\n"
    
    # T日热点板块
    if t_hot_sectors:
        message += "🔥 T日热点板块\n"
        message += "━" * 30 + "\n"
        for i, s in enumerate(t_hot_sectors, 1):
            message += f"{i}. {s['name']} - 强度: {s['strength']:.0f}\n"
        message += "\n"
    
    # T日选股结果
    message += "📊 T日选股结果\n"
    message += "━" * 30 + "\n"
    for i, s in enumerate(t_results, 1):
        message += f"{i}. {s['name']}({s['code']}) - {s['score']:.2f}分\n"
    message += "\n"
    
    # T+1日表现
    message += "📈 T+1日表现\n"
    message += "━" * 30 + "\n"
    success_count = sum(1 for r in t1_results if r['is_success'])
    for r in t1_results:
        status = "✅ 继续涨停" if r['is_success'] else "❌ 未涨停"
        message += f"{r['name']}({r['code']}): {status}\n"
    message += f"\n连板成功率: {success_count}/{len(t1_results)} = {success_count/len(t1_results)*100:.1f}%\n\n"
    
    # 总结
    message += "📌 总结\n"
    message += "━" * 30 + "\n"
    message += f"T日选出 {len(t_results)} 只股票\n"
    message += f"T+1日连板 {success_count} 只\n"
    message += f"成功率: {success_count/len(t1_results)*100:.1f}%\n"
    
    return message


def main():
    """主函数"""
    print("=" * 60)
    print("T01龙头战法 - 完整流程测试")
    print(f"T日: {T_DATE} | T+1日: {T1_DATE}")
    print("=" * 60)
    
    client = StockAPIClient()
    
    # Step 1: T日分析
    t_results, t_emotion, t_hot_sectors = t_day_analysis(client, T_DATE)
    
    # Step 2: 读取T日结果
    with open(RESULT_FILE, 'r', encoding='utf-8') as f:
        t_data = json.load(f)
    
    # Step 3: T+1日分析
    t1_results, success_rate = t1_day_analysis(client, T1_DATE, t_data)
    
    # Step 4: 生成报告
    t1_emotion = get_emotion_analysis(client)
    report = generate_report(t_results, t1_results, t_emotion, t1_emotion, t_hot_sectors)
    
    print("\n报告内容:")
    print(report)
    
    # 发送到飞书
    print("\n发送报告到飞书...")
    success = send_feishu_message(FEISHU_CHAT_ID, report)
    
    if success:
        print("✅ 报告发送成功")
    else:
        print("❌ 报告发送失败")
    
    print("\n" + "=" * 60)
    print("完整流程测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
