#!/bin/bash
# T01 自动备份到 GitHub 脚本
# 工作目录
WORK_DIR="/mnt/workspace/working"
# 日志文件
LOG_FILE="$WORK_DIR/logs/git_backup.log"

# 创建日志目录
mkdir -p "$WORK_DIR/logs"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

cd "$WORK_DIR" || exit 1

# 检查是否有变化
CHANGES=$(git status --porcelain 2>/dev/null)

if [ -z "$CHANGES" ]; then
    log "无变化，跳过备份"
    exit 0
fi

log "检测到变化，开始备份..."
log "变化文件: $CHANGES"

# 添加所有变化
git add -A

# 生成提交信息
COMMIT_MSG="自动备份: $(date '+%Y-%m-%d %H:%M:%S')"
CHANGED_FILES=$(echo "$CHANGES" | wc -l)
COMMIT_MSG="$COMMIT_MSG - $CHANGED_FILES 个文件变更"

# 提交
git commit -m "$COMMIT_MSG" >> "$LOG_FILE" 2>&1

# 推送
git push origin main >> "$LOG_FILE" 2>&1

if [ $? -eq 0 ]; then
    log "✅ 备份成功!"
else
    log "❌ 备份失败!"
    exit 1
fi
