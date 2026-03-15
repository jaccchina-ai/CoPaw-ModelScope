#!/bin/bash
# 狗东西完整备份脚本
# 使用方法: bash backup_all.sh

set -e

BACKUP_DIR="/mnt/workspace"
WORKING_DIR="/mnt/workspace/working"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="dogdong_backup_${TIMESTAMP}.tar.gz"

echo "=========================================="
echo "   狗东西完整备份脚本"
echo "=========================================="
echo ""

# 检查工作目录是否存在
if [ ! -d "$WORKING_DIR" ]; then
    echo "❌ 错误: 工作目录不存在: $WORKING_DIR"
    exit 1
fi

echo "📦 正在备份..."
echo "   源目录: $WORKING_DIR"
echo "   备份文件: $BACKUP_DIR/$BACKUP_FILE"
echo ""

# 创建备份
cd "$BACKUP_DIR"
tar -czvf "$BACKUP_FILE" working/

# 显示备份信息
echo ""
echo "=========================================="
echo "   ✅ 备份完成!"
echo "=========================================="
echo ""
echo "📁 备份文件: $BACKUP_DIR/$BACKUP_FILE"
echo "📊 文件大小: $(ls -lh $BACKUP_FILE | awk '{print $5}')"
echo ""

# 显示备份内容清单
echo "📋 备份内容清单:"
echo "   - 核心身份: AGENTS.md, MEMORY.md, PROFILE.md, SOUL.md"
echo "   - 每日记忆: memory/ 目录"
echo "   - 技能系统: active_skills/ 目录"
echo "   - 脚本程序: scripts/ 目录"
echo "   - 定时任务: jobs.json, task_registry.json"
echo "   - 数据文件: data/ 目录"
echo "   - 其他配置: config.json, HEARTBEAT.md, BOOTSTRAP.md"
echo ""

# 显示环境变量提醒
echo "⚠️  请手动记录以下环境变量到新服务器:"
echo "   export TAVILY_API_KEY=\"$TAVILY_API_KEY\""
echo "   export TOGETHER_API_KEY=\"$TOGETHER_API_KEY\""
echo ""

# 可选：计算校验和
echo "🔐 文件校验和 (MD5):"
md5sum "$BACKUP_FILE" 2>/dev/null || echo "   (无法计算MD5)"
echo ""

echo "=========================================="
echo "   下一步操作:"
echo "=========================================="
echo "1. 下载备份文件到本地"
echo "2. 上传到新服务器 /mnt/workspace/"
echo "3. 解压: tar -xzvf $BACKUP_FILE"
echo "4. 设置环境变量"
echo "5. 安装 Python 依赖: pip3 install together tavily-python requests"
echo ""
