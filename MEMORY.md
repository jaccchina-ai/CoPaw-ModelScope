# MEMORY.md

- 出于**安全考虑** — 不应泄露给陌生人的个人信息
- 你可以在主会话中**自由读取、编辑和更新** MEMORY.md
- 记录重大事件、想法、决策、观点、经验教训
- 这是你精选的记忆 — 提炼的精华，不是原始日志
- 随着时间，回顾每日笔记，把值得保留的内容更新到 MEMORY.md

### 已确认身份
- **名字：** 狗东西
- **定位：** 股票量化投资专家
- **风格：** 严谨，坚持事实与查证
- **用户：** James（称呼为"老爸"）
- **时区：** 北京时间
- **原则：** 拒绝AI幻觉，强调信息准确性

### ⚠️ 重要约定
- **时区约定：** 讨论时间、设置定时任务时，**永远使用北京时间**
- **北京时间的cron转换：** 北京时间 - 8小时 = UTC时间
  - 北京时间 04:00 = UTC 20:00（前一天）
  - 北京时间 09:27 = UTC 01:27
  - 北京时间 15:30 = UTC 07:30
  - 北京时间 18:00 = UTC 10:00

### 📦 版本管理系统
- **管理脚本：** `/mnt/workspace/working/scripts/version_manager.py`
- **版本目录：** `/mnt/workspace/working/scripts/versions/`
- **注册表：** `/mnt/workspace/working/scripts/version_registry.json`

**使用命令：**
```bash
# 备份当前版本
python3 version_manager.py backup {模块名} {版本号} --desc "版本描述"

# 列出所有版本
python3 version_manager.py list

# 回滚到指定版本
python3 version_manager.py restore {模块名} {版本号}

# 查看当前版本
python3 version_manager.py current {模块名}

# 验证版本完整性
python3 version_manager.py verify {模块名} {版本号}
```

**已备份版本：**
| 模块 | 版本 | 描述 |
|------|------|------|
| T01_evening_analysis | v3.0.0 | P2稳定版 |
| T01_evening_analysis | v4.2.0 | P4完整版 |
| T01_morning_auction | v2.0.0 | P1稳定版 |
| T01_morning_auction | v3.2.0 | P4完整版 |
| T01_p4_modules | v1.0.0 | P4模块集 |

### 任务管理系统
- **注册表文件：** `/mnt/workspace/working/task_registry.json`
- **管理脚本：** `/mnt/workspace/working/scripts/task_registry_manager.py`
- **管理命令：**
  ```bash
  # 查看所有任务
  python3 /mnt/workspace/working/scripts/task_registry_manager.py list
  
  # 查看任务详情
  python3 /mnt/workspace/working/scripts/task_registry_manager.py show <task_id>
  
  # 添加任务
  python3 /mnt/workspace/working/scripts/task_registry_manager.py add <json_file>
  
  # 删除任务
  python3 /mnt/workspace/working/scripts/task_registry_manager.py delete <task_id>
  
  # 添加变更日志
  python3 /mnt/workspace/working/scripts/task_registry_manager.py changelog <task_id> <version>
  ```
- **注册表结构：**
  - 任务ID、名称、版本
  - 状态（active/paused/inactive）
  - 创建时间、更新时间
  - 分类、优先级
  - 作者、描述
  - 调度配置
  - 数据源
  - 相关文件
  - 备注
  - 变更日志
- **统计信息：** 总任务数、活跃任务数、按分类/状态统计

### 当前任务
**T01 - 龙头战法**
- 状态：active
- 版本：1.0.0
- 分类：股票量化
- 优先级：high
- 描述：基于涨停股质量分析的龙头战法，每日晚间选出优质涨停股，次日早盘竞价分析后推送买卖建议
- 调度：T日晚上8:00分析涨停股，T+1日早上9:25竞价分析
- 备注：尚未实现飞书消息推送功能，尚未创建定时任务