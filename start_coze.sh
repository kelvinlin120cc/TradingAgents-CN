#!/bin/bash
# TradingAgents-CN 扣子平台启动脚本
# 负责环境准备、端口映射、数据库初始化和服务启动
# 支持全新容器环境自动安装 MongoDB/Redis
# 生产环境（PROD）只读文件系统下跳过本地服务安装，依赖远程服务或降级模式

# 不使用 set -e，避免只读文件系统等非致命错误导致退出

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
# 生产环境（PROD）文件系统可能只读，不尝试创建 .env
# 敏感配置通过扣子平台环境变量/Secret 注入，coze_server.py 的 load_dotenv(override=False) 会自动处理
if [ "${COZE_PROJECT_ENV}" = "PROD" ]; then
    echo "[INFO] Production environment detected, skipping .env file creation."
    echo "[INFO] Environment variables should be injected via Coze platform Secrets."
else
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            echo "[INFO] .env not found, copying from .env.example ..."
            cp .env.example .env 2>/dev/null || echo "[WARN] Cannot create .env (read-only filesystem). Using environment variables only."
        else
            echo "[WARN] Neither .env nor .env.example found."
        fi
    else
        echo "[INFO] .env file found."
    fi
fi

# ============================================================================
# 3. 数据库服务准备
# ============================================================================
# 生产环境（PROD）通常为只读文件系统，无法安装本地 MongoDB/Redis
# 开发环境（DEV）自动安装和启动本地服务

MONGO_HOST="${MONGODB_HOST:-localhost}"
MONGO_PORT="${MONGODB_PORT:-27017}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

if [ "${COZE_PROJECT_ENV}" = "PROD" ]; then
    echo "[INFO] Production environment - skipping local MongoDB/Redis installation."
    echo "[INFO] MongoDB: $MONGO_HOST:$MONGO_PORT"
    echo "[INFO] Redis: $REDIS_HOST:$REDIS_PORT"
else
    # ---- 开发环境：自动安装和启动 MongoDB ----
    if [ "$MONGO_HOST" = "localhost" ] || [ "$MONGO_HOST" = "127.0.0.1" ]; then
        if ! command -v mongod &> /dev/null; then
            echo "[INFO] MongoDB not installed. Installing..."
            curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg 2>/dev/null || true
            echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] http://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | tee /etc/apt/sources.list.d/mongodb-org-7.0.list > /dev/null
            apt-get update -qq 2>/dev/null
            apt-get install -y -qq mongodb-org 2>&1 | tail -3
            echo "[INFO] MongoDB installed."
        fi

        if ! pgrep -x mongod > /dev/null; then
            echo "[INFO] Starting MongoDB..."
            mkdir -p /data/db /data/log
            mongod --dbpath /data/db --logpath /data/log/mongod.log --bind_ip 127.0.0.1 --port 27017 --fork 2>&1 || {
                echo "[WARN] MongoDB start failed, will fall back to degraded mode."
            }
            sleep 2
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

    # ---- 开发环境：自动安装和启动 Redis ----
    if [ "$REDIS_HOST" = "localhost" ] || [ "$REDIS_HOST" = "127.0.0.1" ]; then
        if ! command -v redis-server &> /dev/null; then
            echo "[INFO] Redis not installed. Installing..."
            apt-get update -qq 2>/dev/null
            apt-get install -y -qq redis-server 2>&1 | tail -3
            echo "[INFO] Redis installed."
        fi

        if ! pgrep -x redis-server > /dev/null; then
            echo "[INFO] Starting Redis..."
            redis-server --daemonize yes --bind 127.0.0.1 --port 6379 2>&1 || {
                echo "[WARN] Redis start failed, will fall back to degraded mode."
            }
            sleep 1
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
fi

# ============================================================================
# 4. 启动后端服务
# ============================================================================
echo "[INFO] Starting TradingAgents-CN backend on port $PORT ..."

# 使用 python 启动，确保 PORT 环境变量被 FastAPI 读取
# 将 stderr 合并到 stdout，避免日志级别误标记
python coze_server.py 2>&1
