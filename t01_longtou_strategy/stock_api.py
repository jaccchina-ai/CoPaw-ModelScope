"""
股票 API 客户端
封装所有与 stockapi.com.cn 的交互
"""
import requests
import json
from datetime import datetime, timedelta

class StockAPI:
    def __init__(self, config_path='config.json'):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        self.base_url = self.config['api_base_url']
        self.token = self.config['token']

    def _make_request(self, endpoint, params=None):
        """通用API请求方法"""
        if params is None:
            params = {}
        params['token'] = self.token

        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 20000:
                return data.get('data', [])
            else:
                print(f"API Error: {data.get('msg', 'Unknown error')}")
                return []
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return []

    def get_stock_day_data(self, code, start_date, end_date):
        """
        获取个股日线数据 (已验证)
        API文档: https://www.stockapi.com.cn/menu/11
        端点: /v1/base/day
        """
        endpoint = "/v1/base/day"
        params = {
            "code": code,
            "startDate": start_date,
            "endDate": end_date
        }
        return self._make_request(endpoint, params)

    def get_stock_fund_flow(self, code, start_date, end_date, page_no=1, page_size=50):
        """
        获取个股资金流向 (已实现)
        API文档: https://www.stockapi.com.cn/menu/58
        端点: /v1/base/codeFlow
        更新时间: 交易日15:30
        请求限制: 40次/秒

        返回字段:
        - mainAmount: 主力净流入净额
        - mainAmountPercentage: 主力净流入占比
        - supperBigAmount: 超大单净流入净额
        - bigAmount: 大单净流入净额
        - middleAmount: 中单净流入净额
        - minAmount: 小单净流入净额
        - changeRatio: 涨跌幅
        - lastPrice: 最新价
        """
        endpoint = "/v1/base/codeFlow"
        params = {
            "code": code,
            "startDate": start_date,
            "endDate": end_date,
            "pageNo": page_no,
            "pageSize": page_size
        }
        return self._make_request(endpoint, params)

    def get_hot_sectors(self, date_str):
        """
        获取热点板块排行 (已实现)
        API文档: https://www.stockapi.com.cn/menu/111
        端点: /v1/hotBkJlrDr
        更新时间: 交易日下午16点
        请求频率: 10次/秒

        返回字段:
        - bkCode: 板块代码
        - bkName: 板块名称
        - qjzf: 涨幅
        - qjje: 净额
        - jlrts: 资金净流入天数
        - qiangdu: 板块强度
        """
        endpoint = "/v1/hotBkJlrDr"
        params = {"date": date_str}
        return self._make_request(endpoint, params)

    def get_daily_limit_up_stocks(self, date_str):
        """
        获取指定日期的涨停股池 (待实现)
        需要找到正确的API端点
        预计端点可能在: /menu/38 (涨停股池)
        """
        # TODO: 需要逆向工程确定此接口
        endpoint = "/v1/xxx/limitUpPool" # Placeholder
        params = {"date": date_str}
        return self._make_request(endpoint, params)

    def get_lhb_data(self, date_str):
        """
        获取龙虎榜数据 (待实现)
        需要找到正确的API端点
        预计端点可能在: /menu/13 (龙虎榜单)
        """
        # TODO: 需要逆向工程确定此接口
        endpoint = "/v1/xxx/lhb" # Placeholder
        params = {"date": date_str}
        return self._make_request(endpoint, params)

    def get_auction_data(self, code, date_str):
        """
        获取集合竞价数据 (待实现)
        需要找到正确的API端点
        预计端点可能在: /menu/55 或 /menu/56 (竞价相关)
        """
        # TODO: 需要逆向工程确定此接口
        endpoint = "/v1/xxx/auction" # Placeholder
        params = {"code": code, "date": date_str}
        return self._make_request(endpoint, params)


# 测试已验证的接口
if __name__ == "__main__":
    api = StockAPI()
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    print("=" * 60)
    print("测试1: 日线数据接口 (600004 白云机场)")
    print("=" * 60)
    data = api.get_stock_day_data("600004", yesterday, today)
    print(json.dumps(data, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("测试2: 个股资金流向 (600004 白云机场)")
    print("=" * 60)
    flow_data = api.get_stock_fund_flow("600004", yesterday, today)
    print(json.dumps(flow_data, indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("测试3: 热点板块排行")
    print("=" * 60)
    hot_data = api.get_hot_sectors(today)
    print(json.dumps(hot_data, indent=2, ensure_ascii=False))
