<b>A股市场量化选股 -- 龙头战法</b>

scripts/
├── 核心脚本
│   ├── T01_evening_analysis_v4.py       # 晚间选股主程序（最新版）
│   ├── T01_morning_auction_v3.py        # 早盘竞价主程序（最新版）
│   ├── T01_ai_evolution_v2.py           # AI进化模块
│   ├── T01_complete_system.py           # 完整系统入口
│   ├── T01_data_storage.py              # 数据存储模块
│   └── ...（共37个核心脚本）
│
├── 辅助工具
│   ├── version_manager.py               # 版本管理器
│   ├── task_registry_manager.py         # 任务注册表
│   ├── stockapi_client.py               # StockAPI客户端
│   └── feishu_notifier.py               # 飞书消息生成器
│
├── 测试脚本
│   ├── T01_full_flow_test.py            # 端到端测试
│   ├── test_scoring.py                  # 评分逻辑测试
│   └── T01_system_test.py               # 系统测试
│
└── 版本仓库 (versions/)
    ├── T01_evening_analysis/
    │   ├── v3.0.0/                      # 旧版本（2026-02-23）
    │   └── v4.2.0/                      # 当前版本（2026-03-20）
    │       ├── T01_evening_analysis_v4.py
    │       ├── stockapi_client.py
    │       └── feishu_notifier.py
    │
    ├── T01_morning_auction/
    │   ├── v2.0.0/                      # 旧版本
    │   └── v3.2.0/                      # 当前版本
    │
    └── T01_p4_modules/                  # P4深度分析模块
        └── v1.0.0/
