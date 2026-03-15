# API 探索发现

根据对以下URL的探索，已找到关键API接口：

## 探索的URL
1. https://www.stockapi.com.cn/menu/38 - 涨停股池
2. https://www.stockapi.com.cn/menu/45 - 获取游资名称
3. https://www.stockapi.com.cn/menu/48 - 个股游资上榜交割单
4. https://www.stockapi.com.cn/menu/58 - 个股资金流向

## 发现的API接口

### 1. 涨停股池 API ✓
- **接口地址**: `https://www.stockapi.com.cn/v1/base/ZTPool`
- **请求方式**: GET
- **必需参数**: `date` (格式：2022-09-16)
- **更新时间**: 交易日15点30
- **请求频率**: 40次/秒
- **响应字段**:
  - code: 股票代码
  - name: 股票名称
  - changeRatio: 涨跌幅%
  - lastPrice: 最新价
  - amount: 成交额
  - flowCapital: 流通市值
  - totalCapital: 总市值
  - turnoverRatio: 换手率%
  - ceilingAmount: 封板资金
  - firstCeilingTime: 首次封板时间
  - lastCeilingTime: 最后封板时间
  - bombNum: 炸板次数
  - lbNum: 连扳数量
  - industry: 所属行业
  - time: 时间
  - gl: 概念
  - stock_reason: 股票涨停原因
  - plate_reason: 主题上涨原因
  - plate_name: 涨停主题

**示例URL**: `https://www.stockapi.com.cn/v1/base/ZTPool?date=2022-09-16`

### 2. 获取游资名称 API
- **接口地址**: `https://www.stockapi.com.cn/v1/youzi/name`
- **请求方式**: GET
- **更新时间**: 交易日下午5点40
- **请求频率**: 40次/秒
- **参数**: 未明确显示，需要进一步测试

### 3. 个股游资上榜交割单 API
- **接口地址**: `https://www.stockapi.com.cn/v1/youzi/gegu`
- **请求方式**: GET
- **更新时间**: 交易日下午5点40
- **请求频率**: 40次/秒
- **参数**: 未明确显示，需要进一步测试（可能需要股票代码等参数）

### 4. 个股资金流向 API
- **接口地址**: `https://www.stockapi.com.cn/v1/base/codeFlow`
- **请求方式**: GET
- **更新时间**: 交易日15:30
- **请求频率**: 40次/秒
- **参数**: 未明确显示，需要进一步测试（可能需要股票代码、日期等参数）

## 待确认事项
1. 游资名称API的请求参数
2. 个股游资上榜交割单API的请求参数
3. 个股资金流向API的请求参数
4. 是否需要token验证
5. 竞价数据的API接口（尚未找到）

## 下一步
1. 测试已找到的API接口，验证其可用性
2. 探索竞价数据相关的API接口
3. 完善参数配置
4. 更新代码中的API调用
