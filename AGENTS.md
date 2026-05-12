# AGENTS.md - TradingAgents-CN 项目指南

## 项目概览

TradingAgents-CN 是一个基于多智能体的股票分析框架，包含 FastAPI 后端、Streamlit Web 前端和 Vue.js 前端。

- **upstream**: https://github.com/hsliuping/TradingAgents-CN.git
- **origin (Fork)**: https://github.com/kelvinlin120cc/TradingAgents-CN.git
- **部署分支**: `feature/coze`（扣子平台适配分支）
- **同步分支**: `main`（与 upstream 保持同步，不做自定义修改）

## 目录结构

```
├── app/                  # FastAPI 后端（端口 8000，扣子适配为 5000）
│   ├── main.py           # FastAPI 主应用
│   ├── __main__.py       # python -m app 启动入口
│   ├── core/             # 配置、数据库、日志
│   ├── routers/          # API 路由（analysis, auth, health, stocks 等）
│   ├── services/         # 业务服务层
│   ├── models/           # 数据模型
│   ├── schemas/          # Pydantic Schema
│   └── worker/           # 数据同步 Worker
├── web/                  # Streamlit 前端（端口 8501）
│   ├── app.py            # Streamlit 主应用
│   └── run_web.py        # Streamlit 启动脚本
├── frontend/             # Vue.js 前端（yarn + Vite）
├── tradingagents/        # 核心分析引擎
│   ├── graph/            # Trading Graph
│   ├── agents/           # 多智能体定义
│   └── dataflows/        # 数据流处理
├── coze_server.py        # 扣子平台适配入口（降级模式支持）
├── start_coze.sh         # 扣子平台启动脚本
├── .coze                 # 扣子平台构建/运行配置
├── pyproject.toml        # Python 项目配置
└── .env.example          # 环境变量模板
```

## 扣子平台适配说明

### 关键文件

| 文件 | 说明 |
|------|------|
| `.coze` | 扣子构建/运行配置，指定 Python 3.10 + 启动脚本 |
| `coze_server.py` | 适配入口，自动检测 MongoDB/Redis 可用性，降级模式 |
| `start_coze.sh` | 启动脚本，处理端口映射和环境变量 |

### 双分支策略

- **`main`**: 与 upstream/hsliuping 保持同步，不做自定义修改
- **`feature/coze`**: 扣子平台适配分支，包含 `.coze`、`coze_server.py`、`start_coze.sh` 等平台特定文件

### 启动模式

1. **完整模式**: MongoDB + Redis 均可用时，启动完整 FastAPI 后端
2. **降级模式**: MongoDB/Redis 不可用时，启动轻量状态服务器，提供健康检查和配置引导

### 端口映射

扣子平台要求端口 5000，通过环境变量 `DEPLOY_RUN_PORT` 自动映射到 `PORT`。

### 环境变量与密钥管理

关键环境变量通过 `.env` 文件和扣子平台 Secret 双重管理。

#### 密钥管理策略

| 变量 | 管理方式 | 说明 |
|------|---------|------|
| `CUSTOM_OPENAI_API_KEY` | **扣子 Secret** | 大模型 API 密钥（阿里百炼），敏感 |
| `CUSTOM_OPENAI_BASE_URL` | 扣子 Secret | 大模型 API 地址，与密钥配套 |
| `CUSTOM_OPENAI_MODEL` | .env | 模型名称，非敏感配置 |
| `TUSHARE_TOKEN` | **扣子 Secret** | A股数据 API Token，敏感 |
| `JWT_SECRET` | **扣子 Secret** | JWT 签名密钥，敏感 |
| `CSRF_SECRET` | **扣子 Secret** | CSRF 防护密钥，敏感 |
| `MONGODB_HOST/PORT` | .env | 本地数据库地址，非敏感 |
| `REDIS_HOST/PORT` | .env | 本地缓存地址，非敏感 |

#### 密钥注入优先级

```
扣子平台环境变量（运行时注入） > .env 文件（本地开发）
```

> ⚠️ `.env` 文件已在 `.gitignore` 中排除，不会被提交到 Git。
> 生产环境务必通过扣子平台「项目设置 → 环境变量」注入敏感密钥。

#### 当前大模型配置

- **提供商**: 阿里百炼（通义千问）- OpenAI 兼容接口
- **模型**: qwen3.5-plus
- **API 地址**: https://coding.dashscope.aliyuncs.com/v1

#### 数据源配置

- **Tushare**: A股数据（已配置）
- **AKShare**: 免费开源，无需 Token（默认可用）
- **Finnhub**: 美股数据（可选，需单独配置 FINNHUB_API_KEY）

## Git 远程源管理

```bash
# 同步上游更新
git fetch upstream
git checkout main
git merge upstream/main
git push origin main

# 同步到 feature/coze
git checkout feature/coze
git merge main
git push origin feature/coze
```

## 依赖

- Python 3.10+
- MongoDB + Redis（完整模式必需）
- 详见 `pyproject.toml` 和 `requirements.txt`

## 代码风格

- Python: 遵循 PEP 8，使用中文注释
- API: RESTful 风格，FastAPI 自动生成 /docs 文档
- 数据模型: Pydantic v2
