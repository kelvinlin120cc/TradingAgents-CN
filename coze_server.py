"""
TradingAgents-CN 扣子平台适配入口
- 优先启动完整 FastAPI 后端
- 若 MongoDB/Redis 不可用，自动降级为轻量状态服务器
- 强制监听 DEPLOY_RUN_PORT (默认 5000)
"""

import os
import sys
import time
import logging
from pathlib import Path

# ============================================================================
# 0. 全局设置
# ============================================================================
# 强制端口映射（必须在 import app 之前）
os.environ.setdefault("PORT", os.environ.get("DEPLOY_RUN_PORT", "5000"))
os.environ.setdefault("HOST", "0.0.0.0")

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 显式加载 .env 文件中的所有环境变量到 os.environ
# Pydantic Settings 的 env_file 只加载 model 中定义的字段，
# 但 tradingagents 核心模块通过 os.getenv() 读取 CUSTOM_OPENAI_* 等变量
# 所以必须在这里显式加载，确保所有 .env 变量都可用
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)  # 不覆盖已有的系统环境变量（如扣子 Secret 注入的）
        logger_tmp = logging.getLogger("coze_server")
        logger_tmp.info(f".env loaded from {env_path}")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("coze_server")


def get_version() -> str:
    """读取版本号"""
    try:
        version_file = PROJECT_ROOT / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return "1.0.0"


def check_mongodb_available() -> bool:
    """检测 MongoDB 是否可用（快速 socket 检测）"""
    import socket
    host = os.environ.get("MONGODB_HOST", "localhost")
    port = int(os.environ.get("MONGODB_PORT", "27017"))
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (OSError, socket.timeout):
        logger.warning(f"MongoDB not available: {host}:{port}")
        return False


def check_redis_available() -> bool:
    """检测 Redis 是否可用（快速 socket 检测）"""
    import socket
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (OSError, socket.timeout):
        logger.warning(f"Redis not available: {host}:{port}")
        return False


def ensure_admin_user():
    """确保管理员用户存在（首次启动时自动创建）"""
    try:
        import hashlib
        from pymongo import MongoClient

        mongo_host = os.environ.get("MONGODB_HOST", "localhost")
        mongo_port = int(os.environ.get("MONGODB_PORT", "27017"))
        mongo_db = os.environ.get("MONGODB_DATABASE", "tradingagentscn")

        client = MongoClient(mongo_host, mongo_port, serverSelectionTimeoutMS=3000)
        db = client[mongo_db]

        # 检查是否已有管理员
        admin = db.users.find_one({"username": "admin"})
        if admin:
            logger.info("Admin user already exists.")
            return

        # 创建管理员
        password = os.environ.get("ADMIN_PASSWORD", "Admin123456")
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        admin_user = {
            "username": "admin",
            "email": "admin@tradingagents.cn",
            "hashed_password": hashed_password,
            "role": "admin",
            "is_active": True,
        }

        db.users.insert_one(admin_user)
        logger.info(f"Admin user created. Username: admin, Password: {password}")
    except Exception as e:
        logger.warning(f"Failed to create admin user: {e}")


def start_full_backend():
    """启动完整后端（需要 MongoDB + Redis）"""
    import uvicorn
    from app.core.config import settings
    from app.core.dev_config import DEV_CONFIG

    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(f"Starting FULL backend on {host}:{port}")
    logger.info(f"MongoDB: {settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
    logger.info(f"Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")

    # 自动初始化管理员用户
    ensure_admin_user()

    uvicorn_config = DEV_CONFIG.get_uvicorn_config(settings.DEBUG)
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        **uvicorn_config,
    )


def start_fallback_server():
    """启动轻量降级服务器（无需 MongoDB/Redis）"""
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse, HTMLResponse

    app = FastAPI(
        title="TradingAgents-CN (Degraded Mode)",
        description="扣子平台降级模式 - MongoDB/Redis 未连接",
        version=get_version(),
    )

    # ===== API 路由（必须在 SPA catch-all 之前注册） =====
    @app.get("/health")
    async def health():
        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "status": "degraded",
                    "version": get_version(),
                    "timestamp": int(time.time()),
                    "service": "TradingAgents-CN API (Degraded)",
                    "mongodb": "unavailable",
                    "redis": "unavailable",
                },
                "message": "服务运行在降级模式，请配置 MongoDB 和 Redis",
            }
        )

    @app.get("/api/health")
    async def api_health():
        """前端调用的 /api/health 端点"""
        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "status": "degraded",
                    "version": get_version(),
                    "timestamp": int(time.time()),
                    "service": "TradingAgents-CN API (Degraded)",
                    "mongodb": "unavailable",
                    "redis": "unavailable",
                },
                "message": "服务运行在降级模式，请配置 MongoDB 和 Redis",
            }
        )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "mode": "degraded"}

    @app.get("/readyz")
    async def readyz():
        return {"status": "ok", "mode": "degraded"}

    @app.get("/api/status")
    async def api_status():
        return JSONResponse(
            content={
                "mode": "degraded",
                "version": get_version(),
                "services": {
                    "mongodb": "unavailable",
                    "redis": "unavailable",
                },
                "env": {
                    "COZE_PROJECT_ENV": os.environ.get("COZE_PROJECT_ENV", "DEV"),
                    "PORT": os.environ.get("PORT", "5000"),
                },
                "message": "请配置 .env 文件中的 MONGODB_HOST、REDIS_HOST 等连接信息",
            }
        )

    @app.get("/api/system/config/validate")
    async def config_validate():
        """前端启动时调用的配置验证端点"""
        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "status": "degraded",
                    "version": get_version(),
                    "mongodb": "unavailable",
                    "redis": "unavailable",
                    "openai_configured": bool(os.environ.get("CUSTOM_OPENAI_API_KEY", "")),
                    "tushare_configured": bool(os.environ.get("TUSHARE_TOKEN", "")),
                },
            }
        )

    # ===== 前端路由 =====
    # 尝试提供 Vue.js 前端（如果已构建）
    _frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")

    if os.path.exists(os.path.join(_frontend_dist, "index.html")):
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse

        @app.get("/", response_class=HTMLResponse)
        async def index():
            with open(os.path.join(_frontend_dist, "index.html"), "r") as f:
                return HTMLResponse(content=f.read())

        app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

        # SPA catch-all 必须放在所有 API 路由之后
        @app.get("/{path:path}", response_class=HTMLResponse)
        async def spa_fallback(path: str):
            """SPA catch-all: 前端路由回退到 index.html（排除 API 路径）"""
            # 排除 API 和后端路由（双重保护）
            _excluded_prefixes = ("api/", "docs", "openapi", "redoc", "health", "healthz", "readyz", "ws")
            if any(path.startswith(p) for p in _excluded_prefixes):
                return JSONResponse(content={"detail": "Not Found"}, status_code=404)
            # 先检查是否是静态文件
            file_path = os.path.join(_frontend_dist, path)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            # SPA fallback
            with open(os.path.join(_frontend_dist, "index.html"), "r") as f:
                return HTMLResponse(content=f.read())
    else:
        @app.get("/", response_class=HTMLResponse)
        async def index():
            return HTMLResponse(content=_build_status_page())

    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(f"Starting FALLBACK server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


def _build_status_page() -> str:
    """生成状态页面 HTML"""
    version = get_version()
    project_env = os.environ.get("COZE_PROJECT_ENV", "DEV")
    port = os.environ.get("PORT", "5000")
    domain = os.environ.get("COZE_PROJECT_DOMAIN_DEFAULT", f"localhost:{port}")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TradingAgents-CN</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            max-width: 720px;
            width: 90%;
            padding: 48px;
            background: rgba(30, 41, 59, 0.8);
            border-radius: 16px;
            border: 1px solid rgba(99, 102, 241, 0.3);
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.4);
        }}
        h1 {{
            font-size: 28px;
            margin-bottom: 8px;
            background: linear-gradient(90deg, #818cf8, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .version {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 24px;
        }}
        .status-degraded {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}
        .dot {{
            width: 8px; height: 8px;
            border-radius: 50%;
            background: #fbbf24;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 24px;
        }}
        .info-card {{
            background: rgba(15, 23, 42, 0.6);
            border-radius: 8px;
            padding: 14px;
            border: 1px solid rgba(99, 102, 241, 0.15);
        }}
        .info-card .label {{ font-size: 12px; color: #64748b; margin-bottom: 4px; }}
        .info-card .value {{ font-size: 14px; color: #e2e8f0; font-family: monospace; }}
        .service-list {{ margin-bottom: 24px; }}
        .service-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            border-radius: 8px;
            margin-bottom: 6px;
            background: rgba(15, 23, 42, 0.4);
            border: 1px solid rgba(99, 102, 241, 0.1);
        }}
        .service-name {{ font-size: 14px; }}
        .service-status {{
            font-size: 12px;
            padding: 3px 10px;
            border-radius: 999px;
        }}
        .status-off {{ background: rgba(239, 68, 68, 0.15); color: #f87171; }}
        .help-section {{
            background: rgba(99, 102, 241, 0.1);
            border-radius: 8px;
            padding: 16px;
            border: 1px solid rgba(99, 102, 241, 0.2);
        }}
        .help-section h3 {{ font-size: 14px; color: #818cf8; margin-bottom: 10px; }}
        .help-section code {{
            display: block;
            background: rgba(15, 23, 42, 0.8);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            margin-bottom: 6px;
            color: #a5b4fc;
            overflow-x: auto;
        }}
        .help-section p {{ font-size: 13px; color: #94a3b8; line-height: 1.6; }}
        .api-link {{
            display: inline-block;
            margin-top: 16px;
            color: #818cf8;
            text-decoration: none;
            font-size: 14px;
        }}
        .api-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>TradingAgents-CN</h1>
        <div class="version">v{version} - Coze Platform</div>
        <div class="status-badge status-degraded">
            <span class="dot"></span>
            Degraded Mode
        </div>
        <div class="info-grid">
            <div class="info-card">
                <div class="label">Environment</div>
                <div class="value">{project_env}</div>
            </div>
            <div class="info-card">
                <div class="label">Port</div>
                <div class="value">{port}</div>
            </div>
            <div class="info-card">
                <div class="label">Domain</div>
                <div class="value">{domain}</div>
            </div>
            <div class="info-card">
                <div class="label">Branch</div>
                <div class="value">feature/coze</div>
            </div>
        </div>
        <div class="service-list">
            <div class="service-item">
                <span class="service-name">MongoDB</span>
                <span class="service-status status-off">Disconnected</span>
            </div>
            <div class="service-item">
                <span class="service-name">Redis</span>
                <span class="service-status status-off">Disconnected</span>
            </div>
            <div class="service-item">
                <span class="service-name">FastAPI Backend</span>
                <span class="service-status status-off">Waiting</span>
            </div>
        </div>
        <div class="help-section">
            <h3>How to enable full mode</h3>
            <p>Configure the following in your .env file:</p>
            <code>MONGODB_HOST=your-mongodb-host</code>
            <code>MONGODB_PORT=27017</code>
            <code>REDIS_HOST=your-redis-host</code>
            <code>REDIS_PORT=6379</code>
            <p>After configuration, restart the service. The system will automatically switch to full mode.</p>
        </div>
        <a class="api-link" href="/health">/health</a> &middot;
        <a class="api-link" href="/api/status">/api/status</a>
    </div>
</body>
</html>"""


def main():
    """主启动逻辑：先检测依赖，再决定启动模式"""
    logger.info("=" * 60)
    logger.info("TradingAgents-CN Coze Platform Adapter")
    logger.info(f"Version: {get_version()}")
    logger.info(f"Port: {os.environ.get('PORT', '5000')}")
    logger.info("=" * 60)

    # 先检测 MongoDB/Redis 是否可用（不依赖 app.core.config）
    logger.info("Checking backend dependencies...")
    mongo_ok = check_mongodb_available()
    redis_ok = check_redis_available()

    if mongo_ok and redis_ok:
        # 依赖可用，尝试启动完整后端
        try:
            from app.core.config import settings  # noqa: F401

            logger.info("All dependencies available. Starting FULL backend.")
            start_full_backend()
        except ImportError as e:
            logger.error(f"Failed to import backend modules: {e}")
            logger.info("Starting FALLBACK server (degraded mode).")
            start_fallback_server()
        except Exception as e:
            logger.error(f"Unexpected error starting full backend: {e}")
            logger.info("Starting FALLBACK server (degraded mode).")
            start_fallback_server()
    else:
        if not mongo_ok:
            logger.warning("MongoDB is not available.")
        if not redis_ok:
            logger.warning("Redis is not available.")
        logger.info("Starting FALLBACK server (degraded mode).")
        start_fallback_server()


if __name__ == "__main__":
    main()
