# 版本管理系统使用指南

## 概述

版本管理系统(`version_manager.py`)是一个**通用的灾难冗余机制**，适用于所有任务（T01、T02、T03...），支持：
- ✅ 版本备份：更新前自动备份当前版本
- ✅ 版本注册：记录所有版本信息到JSON注册表
- ✅ 一键回滚：退回到任意历史版本
- ✅ MD5校验：确保备份文件完整性
- ✅ 回滚前自动备份：防止误操作

---

## 核心文件

- **版本管理器**: `scripts/version_manager.py`
- **版本注册表**: `scripts/version_registry.json`
- **备份目录**: `scripts/versions/{模块名}/{版本号}/`

---

## 命令行使用

### 1. 备份版本

```bash
cd /mnt/workspace/working/scripts
python3 version_manager.py backup <模块名> <版本号> --desc "描述"

# 示例：
python3 version_manager.py backup T01_evening_analysis v5.0.0 --desc "新增热点追踪功能"
python3 version_manager.py backup T02_momentum_strategy v1.0.0 --desc "首版动量策略"
```

**备份策略**：
- 自动备份模块前缀匹配的文件（如 T01_xxx.py）
- 自动备份模块名主体部分匹配的文件（如 evening_analysis）
- 自动备份通用核心文件（feishu_notifier.py, stockapi_client.py）

### 2. 列出版本

```bash
# 列出所有版本
python3 version_manager.py list

# 列出指定模块版本
python3 version_manager.py list --module T01_evening_analysis
```

### 3. 回滚版本

```bash
python3 version_manager.py restore <模块名> <版本号>

# 示例：
python3 version_manager.py restore T01_evening_analysis v3.0.0
```

**回滚机制**：
- 回滚前自动备份当前版本（防止误操作）
- 从备份目录恢复所有相关文件
- 更新注册表中的当前版本标记

### 4. 查看当前版本

```bash
python3 version_manager.py current <模块名>

# 示例：
python3 version_manager.py current T01_evening_analysis
```

### 5. 验证版本完整性

```bash
python3 version_manager.py verify <模块名> <版本号>

# 示例：
python3 version_manager.py verify T01_evening_analysis v4.2.0
```

---

## Python API 使用

```python
from version_manager import VersionManager

vm = VersionManager()

# 备份版本
result = vm.backup_version("T01_evening_analysis", "v5.0.0", "新增功能")
print(f"备份成功: {result['success']}")
print(f"备份文件: {result['files']}")

# 回滚版本
result = vm.restore_version("T01_evening_analysis", "v4.2.0")
print(f"回滚成功: {result['success']}")

# 列出版本
versions = vm.list_versions("T01_evening_analysis")
for v in versions:
    print(f"{v['version']}: {v['description']}")

# 获取当前版本
current = vm.get_current_version("T01_evening_analysis")
print(f"当前版本: {current['version']}")

# 验证版本
result = vm.verify_version("T01_evening_analysis", "v4.2.0")
print(f"验证通过: {result['valid']}")
```

---

## 工作流程建议

### 开发新版本前

```bash
# 1. 备份当前稳定版本
python3 version_manager.py backup T01_evening_analysis v4.2.0 --desc "P4完整版"

# 2. 开发新版本...
```

### 发现问题时

```bash
# 1. 查看版本历史
python3 version_manager.py list --module T01_evening_analysis

# 2. 回滚到稳定版本
python3 version_manager.py restore T01_evening_analysis v4.2.0

# 3. 验证回滚是否成功
python3 version_manager.py verify T01_evening_analysis v4.2.0
```

---

## 已备份版本

### T01 - 龙头战法

| 模块 | 版本 | 描述 |
|------|------|------|
| T01_evening_analysis | v3.0.0 | P2稳定版-资金流入天数+涨停原因分析 |
| T01_evening_analysis | v4.2.0 | P4完整版-新闻舆情+解禁+减持+游资+情绪+轮动+资金流+回测 |
| T01_morning_auction | v2.0.0 | P1稳定版-竞价抢筹 |
| T01_morning_auction | v3.2.0 | P4完整版-竞价换手率+竞价量比+资金流向+情绪周期 |
| T01_p4_modules | v1.0.0 | P4模块集-解禁+减持+游资+情绪+轮动+资金流+回测 |

---

## 注意事项

1. **备份时机**：每次重大修改前都应备份
2. **版本命名**：建议使用语义化版本号（v主版本.次版本.修订号）
3. **描述清晰**：备份时写清楚本次变更内容
4. **定期清理**：避免保留过多无用版本（可手动删除versions目录下的旧版本）
5. **回滚验证**：回滚后务必测试系统功能是否正常

---

## 扩展性

版本管理系统是**通用的**，可以用于：
- ✅ T01 龙头战法
- ✅ T02 动量策略
- ✅ T03 均值回归
- ✅ ... 任何未来任务

只需按命名规范创建模块名（如 T02_xxx），版本管理器会自动识别和管理。
