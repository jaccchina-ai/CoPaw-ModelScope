#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
T01龙头战法 - 测试发送飞书消息
使用指定日期的数据进行分析并发送消息到飞书
"""

import json
import sys
import os

sys.path.insert(0, '/mnt/workspace/working/scripts')
from stockapi_client import StockAPIClient
from feishu_notifier import send_feishu_message

# 配置
DATA_DIR = "/mnt/workspace/working/data/T01"
RESULT_FILE = os.path.join(DATA_DIR, "selected_stocks.json")
FEISHU_CHAT_ID = "oc_ff08c55a23630937869cd222dad0bf14"

def calculate_score(stock_data, client, date, hot_sectors=None):
    """
    计算股票的综合评分（精确到小数点后两位）
    
    Args:
        stock_data: 股票数据
        client: API客户端
        date: 日期
        hot_sectors: 热点板块列表（如果为None，则该股票不属于热点板块）
    """
    score = 0.0
    details = {}

    try:
        stock_code = stock_data.get('code', '')
        plate_name = stock_data.get('plateName', '')

        # 1. 首次涨停时间（越早越好，满分20分）
        first_ceiling_time = stock_data.get('firstCeilingTime', '150000')
        time_minutes = client.parse_ceiling_time(first_ceiling_time)
        # 精确计算：越早得分越高，每早1分钟多得0.1分
        if time_minutes <= 570:  # 9:30前（不可能，但作为边界）
            time_score = 20.0
        elif time_minutes <= 600:  # 10:00前
            # 570-600分钟区间，得分从20到15递减
            time_score = 20.0 - (time_minutes - 570) * 0.167
        elif time_minutes <= 630:  # 10:30前
            time_score = 15.0 - (time_minutes - 600) * 0.167
        elif time_minutes <= 660:  # 11:00前
            time_score = 10.0 - (time_minutes - 630) * 0.167
        elif time_minutes <= 720:  # 12:00前
            time_score = 5.0 - (time_minutes - 660) * 0.083
        else:
            time_score = 0.0
        score += time_score
        details['first_ceiling_time'] = first_ceiling_time
        details['first_ceiling_time_score'] = round(time_score, 2)

        # 2. 封成比（越大越好，满分15分）
        seal_ratio = client.calculate_seal_ratio(stock_data)
        # 精确计算：封成比越高得分越高
        if seal_ratio >= 10:
            seal_score = 15.0
        elif seal_ratio >= 5:
            seal_score = 10.0 + (seal_ratio - 5) * 1.0  # 5-10区间，10-15分
        elif seal_ratio >= 3:
            seal_score = 5.0 + (seal_ratio - 3) * 2.5  # 3-5区间，5-10分
        elif seal_ratio >= 1:
            seal_score = seal_ratio * 1.67  # 1-3区间，1.67-5分
        else:
            seal_score = seal_ratio * 1.67  # 0-1区间，0-1.67分
        score += seal_score
        details['seal_ratio'] = round(seal_ratio, 2)
        details['seal_ratio_score'] = round(seal_score, 2)

        # 3. 封单金额/流通市值（越大越好，满分15分）
        seal_to_market_cap = client.calculate_seal_to_market_cap(stock_data)
        # 精确计算
        if seal_to_market_cap >= 0.05:
            cap_score = 15.0
        elif seal_to_market_cap >= 0.03:
            cap_score = 10.0 + (seal_to_market_cap - 0.03) * 250  # 3%-5%区间
        elif seal_to_market_cap >= 0.01:
            cap_score = 5.0 + (seal_to_market_cap - 0.01) * 250  # 1%-3%区间
        else:
            cap_score = seal_to_market_cap * 500  # 0-1%区间
        score += cap_score
        details['seal_to_market_cap'] = round(seal_to_market_cap, 4)
        details['seal_to_market_cap_score'] = round(cap_score, 2)

        # 4. 龙虎榜数据（满分10分）
        top_list_data = client.check_stock_in_dragon_tiger(stock_code, date)
        if top_list_data:
            score += 10.0
            details['top_list_score'] = 10.0
        else:
            details['top_list_score'] = 0.0

        # 5. 主力资金净占比（越大越好，满分10分）
        capital_flow = client.get_stock_capital_flow(stock_code, date)
        main_net_ratio = 0
        if capital_flow:
            try:
                main_net_ratio = float(capital_flow.get('mainAmountPercentage', 0))
            except:
                pass
        # 精确计算
        if main_net_ratio >= 10:
            main_score = 10.0
        elif main_net_ratio >= 5:
            main_score = 7.0 + (main_net_ratio - 5) * 0.6  # 5-10%区间
        elif main_net_ratio >= 0:
            main_score = 3.0 + main_net_ratio * 0.8  # 0-5%区间
        elif main_net_ratio >= -5:
            main_score = 3.0 + main_net_ratio * 0.3  # -5-0%区间
        else:
            main_score = 1.5 + main_net_ratio * 0.1  # -5%以下
        score += max(0, main_score)
        details['main_net_ratio'] = round(main_net_ratio, 2)
        details['main_net_ratio_score'] = round(max(0, main_score), 2)

        # 6. 成交金额（适中为好，满分10分）
        amount = 0
        try:
            amount = float(stock_data.get('amount', 0)) / 10000
        except:
            pass
        # 精确计算：最优区间5-20亿
        if 50000 <= amount <= 200000:
            amount_score = 10.0
        elif 20000 <= amount < 50000:
            amount_score = 7.0 + (amount - 20000) / 30000 * 3  # 2-5亿区间
        elif 200000 < amount <= 500000:
            amount_score = 7.0 - (amount - 200000) / 300000 * 2  # 20-50亿区间
        else:
            amount_score = max(0, 5.0 - abs(amount - 100000) / 100000 * 5)
        score += amount_score
        details['amount'] = round(amount, 0)
        details['amount_score'] = round(amount_score, 2)

        # 7. 换手率（适中为好，满分10分）
        turnover_rate = 0
        try:
            turnover_rate = float(stock_data.get('turnoverRatio', 0))
        except:
            pass
        # 精确计算：最优区间5%-15%
        if 5 <= turnover_rate <= 15:
            turnover_score = 10.0
        elif 3 <= turnover_rate < 5:
            turnover_score = 7.0 + (turnover_rate - 3) * 1.5  # 3-5%区间
        elif 15 < turnover_rate <= 20:
            turnover_score = 7.0 - (turnover_rate - 15) * 0.4  # 15-20%区间
        elif 1 <= turnover_rate < 3:
            turnover_score = turnover_rate * 2.33  # 1-3%区间
        else:
            turnover_score = max(0, 5.0 - abs(turnover_rate - 10) * 0.5)
        score += turnover_score
        details['turnover_rate'] = round(turnover_rate, 2)
        details['turnover_rate_score'] = round(turnover_score, 2)

        # 8. 量比（越大越好，满分10分）
        volume_ratio = client.get_volume_ratio(stock_code, date)
        # 精确计算
        if volume_ratio >= 5:
            volume_score = 10.0
        elif volume_ratio >= 3:
            volume_score = 8.0 + (volume_ratio - 3) * 1.0  # 3-5倍区间
        elif volume_ratio >= 2:
            volume_score = 5.0 + (volume_ratio - 2) * 1.5  # 2-3倍区间
        elif volume_ratio >= 1.5:
            volume_score = 3.0 + (volume_ratio - 1.5) * 4.0  # 1.5-2倍区间
        elif volume_ratio >= 1:
            volume_score = volume_ratio * 2.0  # 1-1.5倍区间
        else:
            volume_score = volume_ratio * 2.0  # 0-1倍区间
        score += volume_score
        details['volume_ratio'] = volume_ratio
        details['volume_ratio_score'] = round(volume_score, 2)

        # 9. 是否属于当日热点行业板块（满分10分）
        # 判断逻辑：
        # 1. 涨停主题不能是"其他"、"公告"等无效标签
        # 2. 该股票的涨停主题或概念标签包含热点板块名称
        
        # 排除无效的涨停主题
        invalid_themes = ['其他', '公告', '复牌', '新股', 'ST', '']
        is_valid_theme = plate_name and plate_name not in invalid_themes
        
        # 判断是否属于热点板块
        is_hot_sector = False
        matched_sector = None
        
        if hot_sectors and is_valid_theme:
            # 获取股票的概念标签
            gl = stock_data.get('gl', '')
            concepts = gl.split(',') if gl else []
            
            for hot_sector in hot_sectors:
                sector_name = hot_sector['name']
                
                # 检查涨停主题是否匹配
                if plate_name and sector_name in plate_name:
                    is_hot_sector = True
                    matched_sector = sector_name
                    break
                
                # 检查涨停主题是否匹配（反向）
                if plate_name and plate_name in sector_name:
                    is_hot_sector = True
                    matched_sector = sector_name
                    break
                
                # 检查概念标签是否包含热点板块名称
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


def analyze_emotional_cycle(client):
    """
    分析情绪周期，用于风控和仓位判断
    
    情绪周期指标：
    - szbl: 上涨比例（越高市场越强）
    - lbjs: 连板家数（越多短线情绪越高）
    - dmqx: 大面情绪（越大风险越高）
    - drqx: 大肉情绪（越大赚钱效应越强）
    - ztjs: 涨停家数
    - dbcgl: 打板成功率（越高市场越强）
    - dtjs: 跌停家数
    
    Returns:
        dict: 情绪分析结果
    """
    print("\n正在获取情绪周期数据...")
    
    emotion_data = client.get_latest_emotion()
    
    if not emotion_data:
        print("  未获取到情绪周期数据")
        return {}
    
    # 解析数据
    szbl = float(emotion_data.get('szbl', 0))  # 上涨比例
    lbjs = int(emotion_data.get('lbjs', 0))  # 连板家数
    dmqx = float(emotion_data.get('dmqx', 0))  # 大面情绪
    drqx = float(emotion_data.get('drqx', 0))  # 大肉情绪
    ztjs = int(emotion_data.get('ztjs', 0))  # 涨停家数
    dbcgl = float(emotion_data.get('dbcgl', 0))  # 打板成功率
    dtjs = int(emotion_data.get('dtjs', 0))  # 跌停家数
    zxgd = int(emotion_data.get('zxgd', 0))  # 最新高度
    
    print(f"\n  情绪周期指标:")
    print(f"    上涨比例: {szbl:.2f}%")
    print(f"    涨停家数: {ztjs}只")
    print(f"    跌停家数: {dtjs}只")
    print(f"    连板家数: {lbjs}只")
    print(f"    打板成功率: {dbcgl:.2f}%")
    print(f"    大面情绪: {dmqx:.2f}")
    print(f"    大肉情绪: {drqx:.2f}")
    print(f"    最新高度: {zxgd}板")
    
    # 情绪评分（满分100分）
    emotion_score = 0
    
    # 1. 上涨比例得分（30分）
    if szbl >= 80:
        emotion_score += 30
    elif szbl >= 60:
        emotion_score += 25
    elif szbl >= 40:
        emotion_score += 15
    elif szbl >= 20:
        emotion_score += 5
    else:
        emotion_score += 0
    
    # 2. 打板成功率得分（25分）
    if dbcgl >= 80:
        emotion_score += 25
    elif dbcgl >= 60:
        emotion_score += 20
    elif dbcgl >= 40:
        emotion_score += 10
    else:
        emotion_score += 0
    
    # 3. 连板家数得分（15分）
    if lbjs >= 50:
        emotion_score += 15
    elif lbjs >= 30:
        emotion_score += 10
    elif lbjs >= 10:
        emotion_score += 5
    else:
        emotion_score += 0
    
    # 4. 大肉情绪得分（15分）
    if drqx >= 100:
        emotion_score += 15
    elif drqx >= 50:
        emotion_score += 10
    elif drqx >= 20:
        emotion_score += 5
    else:
        emotion_score += 0
    
    # 5. 大面情绪扣分（最多扣15分）
    if dmqx >= 100:
        emotion_score -= 15
    elif dmqx >= 50:
        emotion_score -= 10
    elif dmqx >= 20:
        emotion_score -= 5
    
    # 6. 涨跌停比得分（15分）
    if ztjs > 0 and dtjs == 0:
        emotion_score += 15
    elif ztjs > dtjs * 3:
        emotion_score += 10
    elif ztjs > dtjs:
        emotion_score += 5
    else:
        emotion_score += 0
    
    emotion_score = max(0, min(100, emotion_score))
    
    # 判断情绪周期
    if emotion_score >= 80:
        cycle_stage = "高潮期"
        risk_level = "低"
        position_advice = "可满仓操作"
    elif emotion_score >= 60:
        cycle_stage = "上升期"
        risk_level = "中低"
        position_advice = "可7-8成仓位"
    elif emotion_score >= 40:
        cycle_stage = "震荡期"
        risk_level = "中"
        position_advice = "建议5成仓位"
    elif emotion_score >= 20:
        cycle_stage = "退潮期"
        risk_level = "中高"
        position_advice = "建议3成仓位"
    else:
        cycle_stage = "冰点期"
        risk_level = "高"
        position_advice = "建议空仓观望"
    
    result = {
        'emotion_score': emotion_score,
        'cycle_stage': cycle_stage,
        'risk_level': risk_level,
        'position_advice': position_advice,
        'szbl': szbl,
        'lbjs': lbjs,
        'dmqx': dmqx,
        'drqx': drqx,
        'ztjs': ztjs,
        'dtjs': dtjs,
        'dbcgl': dbcgl,
        'zxgd': zxgd
    }
    
    print(f"\n  情绪分析结果:")
    print(f"    情绪评分: {emotion_score}分")
    print(f"    周期阶段: {cycle_stage}")
    print(f"    风险等级: {risk_level}")
    print(f"    仓位建议: {position_advice}")
    
    return result


def calculate_hot_sectors(client, date, top_n=5):
    """
    获取当日热点板块
    
    使用热点板块API获取数据，按板块强度排序
    
    API返回字段：
    - bkName: 板块名称
    - qjzf: 涨幅
    - qjje: 净额（资金净流入）
    - qiangdu: 板块强度
    - jlrts: 资金净流入天数
    
    Args:
        client: API客户端
        date: 日期
        top_n: 选出前N个热点板块
    
    Returns:
        list: 热点板块列表
    """
    print("\n正在获取热点板块数据...")
    
    # 调用热点板块API
    hot_sectors_data = client.get_hot_sectors(date)
    
    if not hot_sectors_data:
        print("  未获取到热点板块数据")
        return []
    
    # 按板块强度排序
    hot_sectors_data.sort(key=lambda x: float(x.get('qiangdu', 0)), reverse=True)
    
    # 取前N名
    top_sectors = hot_sectors_data[:top_n]
    
    # 格式化输出
    hot_sectors = []
    for sector in top_sectors:
        hot_sectors.append({
            'name': sector.get('bkName', ''),
            'code': sector.get('bkCode', ''),
            'change': float(sector.get('qjzf', 0)),  # 涨幅
            'net_flow': float(sector.get('qjje', 0)),  # 资金净流入
            'strength': float(sector.get('qiangdu', 0)),  # 板块强度
            'flow_days': int(sector.get('jlrts', 0))  # 资金净流入天数
        })
    
    print(f"\n  热点板块TOP{top_n}:")
    for i, sector in enumerate(hot_sectors, 1):
        print(f"    {i}. {sector['name']} - 涨幅: {sector['change']:.2f}%, "
              f"板块强度: {sector['strength']:.0f}, 资金净流入: {sector['net_flow']/100000000:.2f}亿")
    
    return hot_sectors

def main():
    """主函数"""
    print("=" * 60)
    print("T01龙头战法 - 测试发送飞书消息")
    print("=" * 60)

    # 使用指定日期
    test_date = '2026-02-13'
    print(f"\n使用日期: {test_date}")

    # 初始化API客户端
    client = StockAPIClient()

    # 获取涨停股票
    print(f"\n正在获取 {test_date} 的涨停股票...")
    stocks = client.get_limit_up_stocks(test_date)

    if not stocks:
        print("未获取到涨停股票数据。")
        return

    print(f"获取到 {len(stocks)} 只涨停股票。")

    # 获取热点板块
    hot_sectors = calculate_hot_sectors(client, test_date)

    # 获取情绪周期分析
    emotion_analysis = analyze_emotional_cycle(client)

    # 计算评分
    print("\n正在计算评分...")
    scored_stocks = []

    for i, stock in enumerate(stocks, 1):
        code, score, details = calculate_score(stock, client, test_date, hot_sectors)
        if score > 0:
            scored_stocks.append({
                'code': code,
                'name': stock.get('name', ''),
                'score': score,
                'details': details,
                'raw_data': stock
            })
        if i <= 3:
            print(f"  {i}. {stock.get('name')}({code}) - 评分: {score:.0f}")

    # 按评分降序排序
    scored_stocks.sort(key=lambda x: x['score'], reverse=True)

    # 返回前5名
    top5 = scored_stocks[:5]

    print(f"\n选出的前5名：")
    for i, stock in enumerate(top5, 1):
        print(f"  {i}. {stock['name']}({stock['code']}) - 评分: {stock['score']:.0f}")

    # 保存结果
    os.makedirs(DATA_DIR, exist_ok=True)
    result_data = {
        'date': test_date,
        'selected_count': len(top5),
        'stocks': top5
    }

    with open(RESULT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {RESULT_FILE}")

    # 构建飞书消息
    print("\n正在构建飞书消息...")

    message = f"📊 T01龙头战法 - {test_date} 晚间分析\n\n"
    
    # 添加情绪周期分析
    if emotion_analysis:
        emotion_score = emotion_analysis['emotion_score']
        cycle_stage = emotion_analysis['cycle_stage']
        risk_level = emotion_analysis['risk_level']
        position_advice = emotion_analysis['position_advice']
        
        message += "📈 情绪周期分析\n"
        message += "━" * 30 + "\n"
        message += f"情绪评分: {emotion_score}分 | 周期阶段: {cycle_stage}\n"
        message += f"风险等级: {risk_level} | 仓位建议: {position_advice}\n\n"
        message += f"上涨比例: {emotion_analysis['szbl']:.2f}% | "
        message += f"打板成功率: {emotion_analysis['dbcgl']:.2f}%\n"
        message += f"涨停: {emotion_analysis['ztjs']}只 | 跌停: {emotion_analysis['dtjs']}只 | "
        message += f"连板: {emotion_analysis['lbjs']}只\n"
        message += f"大肉情绪: {emotion_analysis['drqx']:.2f} | 大面情绪: {emotion_analysis['dmqx']:.2f}\n"
        message += "\n" + "━" * 30 + "\n\n"
    
    # 添加热点板块信息
    message += "🔥 当日热点板块TOP5\n"
    message += "━" * 30 + "\n"
    message += "数据来源：热点板块API（按板块强度排序）\n\n"
    
    for i, sector in enumerate(hot_sectors, 1):
        net_flow_yi = sector['net_flow'] / 100000000  # 转换为亿
        message += f"{i}. {sector['name']}\n"
        message += f"   涨幅: {sector['change']:.2f}% | 板块强度: {sector['strength']:.0f}\n"
        message += f"   资金净流入: {net_flow_yi:.2f}亿 | 连续流入: {sector['flow_days']}天\n"
    
    message += "\n" + "━" * 30 + "\n"
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
    message += "   ≥5倍=10分, ≥3倍=8分\n"
    message += "   ≥2倍=5分, ≥1.5倍=3分\n\n"
    message += "9️⃣ 热点板块（10分）\n"
    message += "   属于热点板块=10分\n\n"
    message += "━" * 30 + "\n"
    message += f"今日选出 {len(top5)} 只观察标的\n"
    message += "━" * 30 + "\n\n"

    for i, stock in enumerate(top5, 1):
        details = stock['details']
        raw_data = stock.get('raw_data', {})

        industry = raw_data.get('industry', 'N/A')
        plate_name = raw_data.get('plateName', 'N/A')
        gl = raw_data.get('gl', '')

        message += f"【{i}. {stock['name']}({stock['code']})】\n"
        message += f"📊 总评分: {stock['score']:.2f}分\n\n"
        message += "📈 详细指标:\n"

        # 1. 首次涨停时间
        first_time = details.get('first_ceiling_time', 'N/A')
        time_score = details.get('first_ceiling_time_score', 0)
        message += f"  ⏰ 首次涨停: {first_time} ({time_score:.2f}分)\n"

        # 2. 封成比
        seal_ratio = details.get('seal_ratio', 0)
        seal_score = details.get('seal_ratio_score', 0)
        message += f"  📊 封成比: {seal_ratio}倍 ({seal_score:.2f}分)\n"

        # 3. 封单金额/流通市值
        seal_cap = details.get('seal_to_market_cap', 0)
        seal_cap_score = details.get('seal_to_market_cap_score', 0)
        message += f"  💰 封单/流通市值: {seal_cap*100:.2f}% ({seal_cap_score:.2f}分)\n"

        # 4. 龙虎榜
        top_list_score = details.get('top_list_score', 0)
        message += f"  🐯 龙虎榜: {'有' if top_list_score > 0 else '无'} ({top_list_score:.2f}分)\n"

        # 5. 主力资金净占比
        main_ratio = details.get('main_net_ratio', 0)
        main_score = details.get('main_net_ratio_score', 0)
        message += f"  💵 主力资金净比: {main_ratio}% ({main_score:.2f}分)\n"

        # 6. 成交金额
        amount = details.get('amount', 0)
        amount_score = details.get('amount_score', 0)
        message += f"  💵 成交金额: {amount:.0f}万 ({amount_score:.2f}分)\n"

        # 7. 换手率
        turnover = details.get('turnover_rate', 0)
        turnover_score = details.get('turnover_rate_score', 0)
        message += f"  🔄 换手率: {turnover}% ({turnover_score:.2f}分)\n"

        # 8. 量比
        volume_ratio = details.get('volume_ratio', 0)
        volume_ratio_score = details.get('volume_ratio_score', 0)
        message += f"  📊 量比: {volume_ratio}倍 ({volume_ratio_score:.2f}分)\n"

        # 9. 热点板块
        hot_score = details.get('hot_sector_score', 0)
        is_hot = details.get('is_hot_sector', False)
        hot_status = "✅ 是" if is_hot else "❌ 否"
        message += f"  🔥 热点板块: {hot_status} ({hot_score:.2f}分)\n"

        # 所属板块
        message += f"\n🏢 所属板块:\n"
        message += f"  行业: {industry}\n"
        if plate_name and plate_name != 'N/A':
            message += f"  涨停主题: {plate_name}\n"
        if gl:
            concepts = gl.split(',')[:5]
            message += f"  概念: {', '.join(concepts)}\n"

        message += "\n" + "─" * 30 + "\n\n"

    message += "⏰ 明日早盘9:25将进行竞价分析，请关注推送消息。\n\n"
    
    # 添加风控建议
    if emotion_analysis:
        message += "📌 风控建议\n"
        message += "━" * 30 + "\n"
        message += f"根据情绪周期分析，当前处于【{emotion_analysis['cycle_stage']}】，\n"
        message += f"风险等级为【{emotion_analysis['risk_level']}】，\n"
        message += f"建议仓位：{emotion_analysis['position_advice']}\n\n"
    
    message += "⚠️ 风险提示: 以上分析仅供参考，投资有风险，请谨慎决策。"

    print("\n消息内容预览:")
    print(message[:500] + "...")

    # 发送到飞书
    print("\n正在发送消息到飞书...")
    success = send_feishu_message(FEISHU_CHAT_ID, message)

    if success:
        print("✅ 消息发送成功！")
    else:
        print("❌ 消息发送失败")

    print("\n" + "=" * 60)
    print("T01龙头战法 - 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
