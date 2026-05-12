#!/bin/bash
# TradingAgents-CN 扣子平台启动脚本
# 负责环境准备、端口映射和服务启动

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ============================================================================
# 1. 端口映射：扣子平台要求 5000 端口
# ============================================================================
export PORT="${DEPLOY_RUN_PORT:-5000}"
export HOST="0.0.0.0"

echo "============================================"
echo "  TradingAgents-CN - Coze Platform Startup"
echo "============================================"
echo "PORT: $PORT"
echo "HOST: $HOST"
echo "PROJECT_DIR: $PROJECT_DIR"
echo "COZE_PROJECT_ENV: ${COZE_PROJECT_ENV:-DEV}"
echo "============================================"

# ============================================================================
# 2. 环境变量文件准备
# ============================================================================
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "[INFO] .env not found, copying from .env.example ..."
        cp .env.example .env
        echo "[INFO] .env created. Please configure your API keys and service connections."
    else
        echo "[WARN] Neither .env nor .env.example found."
    fi
else
    echo "[INFO] .env file found."
fi

# ============================================================================
# 3. 启动后端服务
# ============================================================================
echo "[INFO] Starting TradingAgents-CN backend on port $PORT ..."

# 使用 python 启动，确保 PORT 环境变量被 FastAPI 读取
# 将 stderr 合并到 stdout，避免日志级别误标记
python coze_server.py 2>&1
