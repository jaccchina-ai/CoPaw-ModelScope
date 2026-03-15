#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票API客户端
封装股票API的各种接口调用
"""

import requests
from datetime import datetime
import time

# API配置
API_BASE_URL = "https://www.stockapi.com.cn"
API_TOKEN = "516f4946db85f3f172e8ed29c6ad32f26148c58a38b33c74"


class StockAPIClient:
    """股票API客户端"""

    def __init__(self, token=None):
        self.token = token or API_TOKEN
        self.headers = {
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint, params=None, timeout=10):
        """
        发送HTTP请求的通用方法

        Args:
            endpoint: API端点（如 /v1/base/ZTPool）
            params: 请求参数
            timeout: 超时时间（秒）

        Returns:
            dict: 返回的数据，失败返回None
        """
        try:
            # 构建完整URL，token作为URL参数
            url = f"{API_BASE_URL}{endpoint}"

            # 添加token到参数
            if params is None:
                params = {}
            params['token'] = self.token

            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()

            data = response.json()

            # 检查返回码
            if data.get('code') == 20000:
                return data.get('data', {})
            else:
                print(f"API返回错误: {data.get('msg', '未知错误')}")
                return None

        except requests.exceptions.Timeout:
            print(f"API请求超时: {endpoint}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"API请求失败: {e}")
            return None
        except Exception as e:
            print(f"API请求发生错误: {e}")
            return None

    def get_trading_day(self, date):
        """
        查询指定日期是否为交易日

        Args:
            date: 日期字符串（格式：YYYY-MM-DD）

        Returns:
            bool: True表示是交易日，False表示不是交易日
        """
        params = {"tradeDate": date}

        result = self._make_request("/v1/base/tradeDate", params)

        if result is not None:
            is_trade = result.get('isTradeDate', 0)
            return is_trade == 1

        return False

    def get_limit_up_stocks(self, date):
        """
        获取当日涨停股票列表

        Args:
            date: 日期字符串（格式：YYYY-MM-DD）

        Returns:
            list: 涨停股票列表
        """
        params = {"date": date}

        result = self._make_request("/v1/base/ZTPool", params)

        if result is not None:
            return result

        return []

    def get_dragon_tiger(self, date):
        """
        获取龙虎榜数据

        Args:
            date: 日期字符串（格式：YYYY-MM-DD）

        Returns:
            list: 龙虎榜数据列表
        """
        params = {"date": date}

        result = self._make_request("/v1/base/dragonTiger", params)

        if result is not None:
            # 确保返回列表格式
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                # 如果是字典，尝试提取数据
                data = result.get('data', result)
                if isinstance(data, list):
                    return data
                return [data] if data else []

        return []

    def check_stock_in_dragon_tiger(self, stock_code, date):
        """
        检查指定股票是否在龙虎榜中

        Args:
            stock_code: 股票代码
            date: 日期字符串（格式：YYYY-MM-DD）

        Returns:
            bool: True表示在龙虎榜中
        """
        dragon_data = self.get_dragon_tiger_detail(stock_code, date)
        return dragon_data is not None
    
    def get_dragon_tiger_detail(self, stock_code, date):
        """
        获取股票在龙虎榜中的详细信息（优化版）
        
        Args:
            stock_code: 股票代码
            date: 日期字符串（格式：YYYY-MM-DD）
        
        Returns:
            dict: 龙虎榜详情，包含买入额、卖出额、游资等，如果不在龙虎榜返回None
        """
        dragon_data = self.get_dragon_tiger(date)

        if dragon_data and isinstance(dragon_data, list):
            for item in dragon_data:
                ths_code = item.get('thsCode', '')
                # 去掉后缀（如 300449.SZ -> 300449）
                code = ths_code.split('.')[0] if '.' in ths_code else ths_code
                if code == stock_code:
                    return item

        return None
    
    def get_hot_sectors_enhanced(self, date=None):
        """
        获取热点板块数据（增强版，包含更多字段）
        
        Args:
            date: 日期，默认当天
        
        Returns:
            list: 热点板块列表，包含强度、净额、流入天数等
        """
        if date is None:
            date = self.get_today_date()
        
        result = self._make_request("/v1/hotBkJlrDr", {"date": date})
        
        if result is not None:
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                data = result.get('data', result)
                if isinstance(data, list):
                    return data
        
        return []

    def get_stock_capital_flow(self, stock_code, date):
        """
        获取个股资金流向数据

        Args:
            stock_code: 股票代码
            date: 日期字符串（格式：YYYY-MM-DD）

        Returns:
            dict: 资金流向数据
        """
        params = {
            "code": stock_code,
            "startDate": date,
            "endDate": date,
            "pageNo": "1",
            "pageSize": "1"
        }

        result = self._make_request("/v1/base/codeFlow", params)

        if result and isinstance(result, list) and len(result) > 0:
            return result[0]

        return {}

    def get_hot_sector_auction(self):
        """
        获取早盘热点板块竞价数据

        Returns:
            list: 热点板块竞价数据
        """
        result = self._make_request("/v1/base/bkjj")

        if result is not None:
            return result

        return []

    def get_hot_sector_stocks(self):
        """
        获取早盘热点板块竞价所属个股

        Returns:
            list: 个股竞价数据
        """
        result = self._make_request("/v1/base/bkCodeList")

        if result is not None:
            return result

        return []
    
    def get_enhanced_auction_sectors(self, trade_date=None):
        """
        获取增强版热点板块竞价数据
        
        更新时间：交易日上午9:26分
        
        Args:
            trade_date: 交易日期（格式：YYYY-MM-DD），默认今天
        
        Returns:
            list: 热点板块竞价数据，包含：
                - bkCode: 板块代码
                - bkName: 板块名称
                - jjzf: 竞价涨幅
                - szjs: 上涨家数
                - xdjs: 下跌家数
        """
        if not trade_date:
            trade_date = self.get_today_date()
        
        params = {"tradeDate": trade_date}
        result = self._make_request("/v1/base/bkjjzq", params)

        if result is not None:
            return result

        return []
    
    def get_enhanced_auction_stocks(self, trade_date=None, bk_code=None):
        """
        获取增强版热点板块竞价所属个股
        
        更新时间：交易日上午9:26分
        
        Args:
            trade_date: 交易日期（格式：YYYY-MM-DD），默认今天
            bk_code: 板块代码（可选，不传则获取所有热点板块的个股）
        
        Returns:
            list: 竞价热点个股数据，包含：
                - code: 股票代码
                - name: 股票名称
                - jjzf: 竞价涨幅
                - bkCode: 所属板块代码
                - bkName: 所属板块名称
        """
        if not trade_date:
            trade_date = self.get_today_date()
        
        if bk_code:
            # 获取指定板块的竞价个股
            params = {"tradeDate": trade_date, "bkCode": bk_code}
            result = self._make_request("/v1/base/zqbkCodeList", params)
            if result:
                return result
            return []
        
        # 获取所有热点板块的竞价个股（遍历前10个板块）
        all_stocks = []
        sectors = self.get_enhanced_auction_sectors(trade_date)
        
        if not sectors:
            return []
        
        seen_codes = set()  # 去重
        
        for sector in sectors[:10]:  # 只取前10个热门板块
            sector_bk_code = sector.get('bkCode')
            if not sector_bk_code:
                continue
            
            params = {"tradeDate": trade_date, "bkCode": sector_bk_code}
            stocks = self._make_request("/v1/base/zqbkCodeList", params)
            
            if stocks:
                for stock in stocks:
                    code = stock.get('code', '')
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        all_stocks.append(stock)
        
        return all_stocks

    def get_stock_kline(self, stock_code, start_date, end_date, cycle=100):
        """
        获取股票K线数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）
            cycle: 周期（100=日线，101=周线，102=月线）

        Returns:
            dict: K线数据
        """
        params = {
            "code": stock_code,
            "startDate": start_date,
            "endDate": end_date,
            "calculationCycle": str(cycle)
        }

        result = self._make_request("/v1/base/day", params)

        if result is not None:
            return result

        return {}

    def get_volume_ratio(self, stock_code, date):
        """
        获取股票的量比（当日换手率 / 过去5日平均换手率）

        Args:
            stock_code: 股票代码
            date: 日期（格式：YYYY-MM-DD）

        Returns:
            float: 量比，如果无法计算返回0
        """
        try:
            # 获取当日涨停股数据
            limit_up_data = self.get_limit_up_stocks(date)

            current_turnover = 0
            for stock in limit_up_data:
                if stock.get('code') == stock_code:
                    current_turnover = float(stock.get('turnoverRatio', 0))
                    break

            if current_turnover == 0:
                return 0

            # 获取过去几天的K线数据来计算平均换手率
            from datetime import timedelta

            end_date = datetime.strptime(date, "%Y-%m-%d")
            start_date = end_date - timedelta(days=15)

            kline_data = self.get_stock_kline(
                stock_code,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                cycle=100
            )

            # K线数据是列表格式
            if not kline_data or not isinstance(kline_data, list):
                # 如果没有历史数据，使用默认值
                # 假设正常换手率为5%
                return round(current_turnover / 5, 2)

            # 提取换手率数据（排除当天）
            past_turnovers = []
            for item in kline_data:
                item_date = item.get('time', '')
                # 只取当日之前的数据
                if item_date < date:
                    turnover = item.get('turnoverRatio', '0')
                    try:
                        past_turnovers.append(float(turnover))
                    except:
                        pass

            if len(past_turnovers) < 3:
                return round(current_turnover / 5, 2)

            # 取最近5个交易日的换手率
            recent_turnovers = past_turnovers[-5:] if len(past_turnovers) >= 5 else past_turnovers

            # 计算5日平均换手率
            avg_turnover = sum(recent_turnovers) / len(recent_turnovers)

            if avg_turnover > 0:
                volume_ratio = current_turnover / avg_turnover
                return round(volume_ratio, 2)

            return 0

        except Exception as e:
            print(f"获取量比时发生错误: {e}")
            return 0

    def get_hot_sectors(self, date):
        """
        获取热点板块数据

        Args:
            date: 日期（格式：YYYY-MM-DD）

        Returns:
            list: 热点板块列表，每个元素包含：
                - bkCode: 板块代码
                - bkName: 板块名称
                - qjzf: 涨幅
                - qjje: 净额（资金净流入）
                - qiangdu: 板块强度
                - jlrts: 资金净流入天数
        """
        params = {"date": date}

        result = self._make_request("/v1/hotBkJlrDr", params)

        if result is not None:
            return result

        return []

    def get_emotional_cycle(self):
        """
        获取情绪周期数据

        Returns:
            dict: 情绪周期数据，包含最近40日的：
                - date1: 时间
                - szbl: 上涨比例
                - lbjs: 连板家数
                - ylgd: 压力高度
                - zxgd: 最新高度
                - dmqx: 大面情绪
                - drqx: 大肉情绪
                - ztjs: 涨停家数
                - dbcgl: 打板成功率
                - dtjs: 跌停家数
        """
        result = self._make_request("/v1/base/emotionalCycle")

        if result is not None:
            return result

        return {}

    def parse_emotional_cycle(self, data):
        """
        解析情绪周期数据

        Args:
            data: API返回的原始数据

        Returns:
            list: 解析后的数据列表，每个元素是一个字典
        """
        if not data or 'colNameList' not in data or 'contentList' not in data:
            return []

        col_names = data['colNameList']
        content_list = data['contentList']

        parsed_data = []
        for row in content_list:
            item = {}
            for i, col in enumerate(col_names):
                if i < len(row):
                    item[col] = row[i]
            parsed_data.append(item)

        return parsed_data

    def get_latest_emotion(self):
        """
        获取最新一日情绪数据

        Returns:
            dict: 最新情绪数据
        """
        data = self.get_emotional_cycle()
        parsed = self.parse_emotional_cycle(data)

        if parsed:
            return parsed[-1]  # 返回最后一条（最新）

        return {}

    def get_stock_kline(self, stock_code, start_date, end_date, cycle=100):
        """
        获取股票K线数据

        Args:
            stock_code: 股票代码
            start_date: 开始日期（格式：YYYY-MM-DD）
            end_date: 结束日期（格式：YYYY-MM-DD）
            cycle: 周期（100=日线，101=周线，102=月线）

        Returns:
            dict: K线数据
        """
        params = {
            "code": stock_code,
            "startDate": start_date,
            "endDate": end_date,
            "calculationCycle": str(cycle)
        }

        result = self._make_request("/v1/base/day", params)

        if result is not None:
            return result

        return {}

    def calculate_volume_ratio(self, stock_code, date):
        """
        计算量比（当日成交量 / 过去5日平均成交量）

        Args:
            stock_code: 股票代码
            date: 当日日期（格式：YYYY-MM-DD）

        Returns:
            float: 量比，如果无法计算返回0
        """
        try:
            from datetime import datetime, timedelta

            # 获取当日涨停股池数据中的成交量
            limit_up_data = self.get_limit_up_stocks(date)

            current_volume = 0
            for stock in limit_up_data:
                if stock.get('code') == stock_code:
                    # 成交量单位是股，需要转换
                    current_volume = float(stock.get('amount', 0))  # 成交额，单位元
                    break

            if current_volume == 0:
                return 0

            # 获取过去5个交易日的K线数据
            # 需要获取足够多的天数来找到5个交易日
            end_date = datetime.strptime(date, "%Y-%m-%d")
            start_date = end_date - timedelta(days=15)  # 往前推15天，确保有5个交易日

            kline_data = self.get_stock_kline(
                stock_code,
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                cycle=100
            )

            if not kline_data or 'volume' not in kline_data:
                return 0

            # K线数据中volume是数组
            volumes = kline_data.get('volume', [])

            if not volumes or len(volumes) < 2:  # 至少需要当日和前几日数据
                return 0

            # volumes数组的最后一个元素是当日，去掉它
            past_volumes = volumes[:-1]

            if len(past_volumes) == 0:
                return 0

            # 取最近5个交易日的成交量（如果有）
            past_5_volumes = past_volumes[-5:] if len(past_volumes) >= 5 else past_volumes

            # 计算平均成交量
            avg_volume = sum(past_5_volumes) / len(past_5_volumes)

            if avg_volume == 0:
                return 0

            # 计算量比
            volume_ratio = current_volume / avg_volume

            return volume_ratio

        except Exception as e:
            print(f"计算量比时出错: {e}")
            return 0

    def parse_ceiling_time(self, time_str):
        """
        解析封板时间字符串

        Args:
            time_str: 时间字符串，如 "134027" 表示 13:40:27

        Returns:
            int: 分钟数（从0:00开始）
        """
        try:
            if len(time_str) == 6:
                hour = int(time_str[0:2])
                minute = int(time_str[2:4])
                second = int(time_str[4:6])
                return hour * 60 + minute + second / 60
        except:
            pass

        return 0

    def calculate_seal_ratio(self, stock_data):
        """
        计算封成比（封单金额/成交金额）

        Args:
            stock_data: 股票数据字典

        Returns:
            float: 封成比
        """
        try:
            ceiling_amount = float(stock_data.get('ceilingAmount', 0))
            amount = float(stock_data.get('amount', 0))

            if amount > 0:
                return ceiling_amount / amount
        except:
            pass

        return 0

    def calculate_seal_to_market_cap(self, stock_data):
        """
        计算封单金额/流通市值

        Args:
            stock_data: 股票数据字典

        Returns:
            float: 封单金额/流通市值
        """
        try:
            ceiling_amount = float(stock_data.get('ceilingAmount', 0))
            flow_capital = float(stock_data.get('flowCapital', 0))

            if flow_capital > 0:
                return ceiling_amount / flow_capital
        except:
            pass

        return 0

    def get_today_date(self):
        """获取今天的日期字符串"""
        return datetime.now().strftime("%Y-%m-%d")

    def get_yesterday_date(self):
        """获取昨天的日期字符串"""
        yesterday = datetime.now() - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")
    
    # ==================== 大盘指数接口 ====================
    
    def get_index_sh(self, start_date, end_date):
        """
        获取上证指数数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        
        Returns:
            list: 上证指数K线数据
        """
        result = self._make_request('/v1/index/sh', {
            'startDate': start_date,
            'endDate': end_date
        })
        
        if result is not None:
            return result
        return []
    
    def get_index_sz(self, start_date, end_date):
        """
        获取深证成指数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        
        Returns:
            list: 深证成指K线数据
        """
        result = self._make_request('/v1/index/sz', {
            'startDate': start_date,
            'endDate': end_date
        })
        
        if result is not None:
            return result
        return []
    
    def get_index_data(self, index_type='sh', days=30):
        """
        获取指数数据（统一接口）
        
        Args:
            index_type: 指数类型 ('sh'=上证, 'sz'=深证)
            days: 获取最近多少天的数据
        
        Returns:
            list: 指数K线数据
        """
        from datetime import timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        if index_type == 'sh':
            return self.get_index_sh(start_date, end_date)
        elif index_type == 'sz':
            return self.get_index_sz(start_date, end_date)
        else:
            return []

    # ==================== 竞价抢筹接口 ====================
    
    def get_auction_robbing(self, trade_date, period=0, type=1):
        """
        获取竞价抢筹数据
        
        更新时间：交易日9:26（早盘）/ 15:10（尾盘）
        
        Args:
            trade_date: 交易日期（格式：YYYY-MM-DD）
            period: 抢筹类型
                - 0: 早盘竞价抢筹
                - 1: 尾盘抢筹
            type: 排序类型
                - 1: 按抢筹委托金额排序
                - 2: 按抢筹成交金额排序
                - 3: 按开盘金额排序
                - 4: 按抢筹涨幅排序
        
        Returns:
            list: 抢筹数据列表，包含：
                - code: 代码
                - name: 名称
                - openAmt: 开盘金额
                - qczf: 抢筹涨幅
                - qccje: 抢筹成交额
                - qcwtje: 抢筹委托金额
        """
        params = {
            "tradeDate": trade_date,
            "period": str(period),
            "type": str(type)
        }
        
        result = self._make_request("/v1/base/jjqc", params)
        
        if result is not None:
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                data = result.get('data', result)
                if isinstance(data, list):
                    return data
        
        return []
    
    def get_stock_in_auction_robbing(self, stock_code, trade_date, period=0):
        """
        检查股票是否在竞价抢筹榜中
        
        Args:
            stock_code: 股票代码
            trade_date: 交易日期
            period: 0-早盘，1-尾盘
        
        Returns:
            dict: 抢筹数据，如果不在榜单返回None
        """
        for type_id in [1, 2, 3, 4]:
            robbing_data = self.get_auction_robbing(trade_date, period, type_id)
            
            for item in robbing_data:
                code = item.get('code', '')
                if '.' in code:
                    code = code.split('.')[0]
                
                if code == stock_code:
                    return item
        
        return None


# 测试函数
def main():
    """测试API客户端"""
    print("测试股票API客户端...")

    client = StockAPIClient()

    # 测试交易日查询
    today = client.get_today_date()
    print(f"\n今天 ({today}) 是否为交易日: {client.get_trading_day(today)}")

    # 测试涨停股池（使用测试日期）
    test_date = "2024-02-02"
    print(f"\n获取 {test_date} 的涨停股...")
    limit_up_stocks = client.get_limit_up_stocks(test_date)

    if limit_up_stocks:
        print(f"获取到 {len(limit_up_stocks)} 只涨停股票")

        # 显示前3只
        for i, stock in enumerate(limit_up_stocks[:3], 1):
            print(f"  {i}. {stock.get('name')}({stock.get('code')}) - "
                  f"涨跌幅: {stock.get('changeRatio')}% - "
                  f"首次封板: {stock.get('firstCeilingTime')}")
    else:
        print("未获取到涨停股数据")


if __name__ == "__main__":
    main()

