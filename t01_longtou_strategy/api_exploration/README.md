# API 探索记录

## 目标URL分析
通过分析提供的URL，成功提取了以下关键API接口信息：

### 1. 涨停股池 (menu/38)
- **接口地址**: `https://www.stockapi.com.cn/v1/base/ZTPool`
- **请求参数**: `date` (交易日期，格式: YYYY-MM-DD)
- **关键返回字段**:
  - `code`: 股票代码
  - `name`: 股票名称
  - `changeRatio`: 涨跌幅%
  - `lastPrice`: 最新价
  - `amount`: 成交额
  - `flowCapital`: 流通市值
  - `totalCapital`: 总市值
  - `turnoverRatio`: 换手率%
  - `ceilingAmount`: 封板资金
  - `firstCeilingTime`: 首次封板时间
  - `lastCeilingTime`: 最后封板时间
  - `bombNum`: 炸板次数
  - `lbNum`: 连扳数量
  - `industry`: 所属行业
  - `gl`: 概念

### 2. 个股游资上榜交割单 (menu/48)
- **接口地址**: `https://www.stockapi.com.cn/v1/youzi/gegu`
- **请求参数**: 未知（需进一步探索）
- **说明**: 用于获取个股的龙虎榜数据。

### 3. 获取游资名称 (menu/45)
- **接口地址**: `https://www.stockapi.com.cn/v1/youzi/name`
- **说明**: 用于获取所有游资席位的名称列表。

### 4. 个股资金流向 (menu/58)
- **接口地址**: `https://www.stockapi.com.cn/v1/base/codeFlow`
- **请求参数**: 未知（需进一步探索）
- **说明**: 用于获取个股的历史资金流数据。

### 5. 查询上证指数 (menu/30)
- **接口地址**: `https://www.stockapi.com.cn/v1/index/sh`
- **说明**: 用于获取上证指数数据。

### 6. 情绪周期 (menu/73)
- **接口地址**: `https://www.stockapi.com.cn/v1/base/emotionalCycle`
- **说明**: 包含最近40日的涨跌停家数、大面情绪、大肉情绪等数据。

### 7. 交易日历 (menu/15)
- **接口地址**: `https://www.stockapi.com.cn/v1/base/tradeDate`
- **说明**: 用于判断某日是否为交易日。

### 8. 早盘抢筹成交金额排序 (menu/78) & 开盘金额排序 (menu/79)
- **接口地址**: `https://www.stockapi.com.cn/v1/base/jjqc`
- **更新时间**: 交易日9:26
- **说明**: 这两个菜单项指向同一个API，提供竞价结束后的抢筹数据。这是获取竞价数据的关键接口。

## 关键发现
1. **竞价数据来源**: `menu/78` 和 `menu/79` 都指向 `https://www.stockapi.com.cn/v1/base/jjqc`，该接口在交易日9:26更新，是获取竞价数据（如成交金额、开盘金额）的直接来源。
2. **手动计算指标**: 对于“竞价换手率”和“竞价量比”，API可能不直接提供。但我们可以利用 `jjqc` 接口返回的竞价成交额，结合 `ZTPool` 或 `QSPool` 中的日级别成交额和换手率数据，进行手动计算。
3. **龙虎榜数据**: `menu/48` 提供了龙虎榜（游资交割单）的接口，但需要确定其具体请求参数。

## 下一步行动
1. **验证 `jjqc` 接口**: 立即调用此接口，确认其返回的数据结构，特别是是否包含我们所需的竞价成交额、开盘价等信息。
2. **完善 `StockAPI` 类**: 将新发现的API端点集成到 `stock_api.py` 中。
3. **设计计算逻辑**: 为“竞价换手率”和“竞价量比”设计具体的计算公式。