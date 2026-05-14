#!/bin/bash
# TradingAgents-CN 扣子平台启动脚本
# 负责环境准备、端口映射、数据库初始化和服务启动
# 支持全新容器环境自动安装 MongoDB/Redis

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
# 3. 自动安装和启动 MongoDB（如果未安装）
# ============================================================================
MONGO_HOST="${MONGODB_HOST:-localhost}"
MONGO_PORT="${MONGODB_PORT:-27017}"

if [ "$MONGO_HOST" = "localhost" ] || [ "$MONGO_HOST" = "127.0.0.1" ]; then
    # 检查 MongoDB 是否已安装
    if ! command -v mongod &> /dev/null; then
        echo "[INFO] MongoDB not installed. Installing..."
        # 添加 MongoDB 7.0 源
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg 2>/dev/null || true
        echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] http://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list > /dev/null
        apt-get update -qq 2>/dev/null
        apt-get install -y -qq mongodb-org 2>&1 | tail -3
        echo "[INFO] MongoDB installed."
    fi

    # 检查 MongoDB 是否已运行
    if ! pgrep -x mongod > /dev/null; then
        echo "[INFO] Starting MongoDB..."
        mkdir -p /data/db /data/log
        mongod --dbpath /data/db --logpath /data/log/mongod.log --bind_ip 127.0.0.1 --port 27017 --fork 2>&1 || {
            echo "[WARN] MongoDB start failed, will fall back to degraded mode."
        }
        sleep 2
        # 验证
        if pgrep -x mongod > /dev/null; then
            echo "[INFO] MongoDB started successfully on port 27017."
        else
            echo "[WARN] MongoDB not running after start attempt."
        fi
    else
        echo "[INFO] MongoDB already running."
    fi
else
    echo "[INFO] Using remote MongoDB: $MONGO_HOST:$MONGO_PORT"
fi

# ============================================================================
# 4. 自动安装和启动 Redis（如果未安装）
# ============================================================================
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

if [ "$REDIS_HOST" = "localhost" ] || [ "$REDIS_HOST" = "127.0.0.1" ]; then
    # 检查 Redis 是否已安装
    if ! command -v redis-server &> /dev/null; then
        echo "[INFO] Redis not installed. Installing..."
        apt-get update -qq 2>/dev/null
        apt-get install -y -qq redis-server 2>&1 | tail -3
        echo "[INFO] Redis installed."
    fi

    # 检查 Redis 是否已运行
    if ! pgrep -x redis-server > /dev/null; then
        echo "[INFO] Starting Redis..."
        redis-server --daemonize yes --bind 127.0.0.1 --port 6379 2>&1 || {
            echo "[WARN] Redis start failed, will fall back to degraded mode."
        }
        sleep 1
        # 验证
        if redis-cli ping 2>/dev/null | grep -q PONG; then
            echo "[INFO] Redis started successfully on port 6379."
        else
            echo "[WARN] Redis not running after start attempt."
        fi
    else
        echo "[INFO] Redis already running."
    fi
else
    echo "[INFO] Using remote Redis: $REDIS_HOST:$REDIS_PORT"
fi

# ============================================================================
# 5. 启动后端服务
# ============================================================================
echo "[INFO] Starting TradingAgents-CN backend on port $PORT ..."

# 使用 python 启动，确保 PORT 环境变量被 FastAPI 读取
# 将 stderr 合并到 stdout，避免日志级别误标记
python coze_server.py 2>&1
