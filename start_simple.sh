#!/bin/bash
# TradingAgents-CN 后端启动脚本（直接部署，非 Docker）
# 配置唯一来源：项目根目录的 .env 文件

cd "$(dirname "$0")"

# 加载 .env 配置并导出为环境变量
if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "❌ 未找到 .env 配置文件"
    exit 1
fi

# 创建日志与数据目录（路径取自 .env）
mkdir -p "${TRADINGAGENTS_LOG_DIR:-/tmp/tradingagents_logs}" \
         "${TRADINGAGENTS_DATA_DIR:-/tmp/tradingagents_data}"/{cache,sessions,logs,config,temp,analysis_results,backups,exports,pulse} \
         uploads

# 启动 FastAPI 服务（仅监听源码目录，避免数据写入触发误重载）
python -m uvicorn app.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8001}" \
    --reload \
    --reload-dir app \
    --reload-dir tradingagents \
    --reload-exclude "*.log" \
    --reload-exclude "*.tmp" \
    --log-level info
