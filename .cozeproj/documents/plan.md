# TradingAgents-CN 前端部署计划

## 概述

将项目已有的 Vue.js 前端（Vue 3 + Element Plus + ECharts）集成到扣子平台 5000 端口，实现用户通过浏览器直接登录使用股票分析功能。方案：构建 Vue.js 前端产物，由 FastAPI 提供静态文件服务 + API 服务，单端口统一访问。

## 技术方案

| 维度 | 选择 | 理由 |
|------|------|------|
| 前端框架 | Vue 3 + Element Plus + ECharts（项目已有） | 14个页面，功能完整 |
| 构建工具 | Vite（项目已有） | 开发热更新 + 生产构建 |
| 包管理器 | yarn（项目使用 yarn.lock） | 前端项目原有配置 |
| 部署方式 | FastAPI StaticFiles 挂载 | 单端口 5000，前后端统一 |
| API 通信 | 前端相对路径请求 `/api/*` | 无跨域问题，无需代理 |
| SPA 路由 | FastAPI catch-all fallback 到 index.html | Vue Router history 模式 |

## 功能模块

### 前端页面（14个视图）

| 模块 | 页面 | 核心功能 |
|------|------|---------|
| 认证 | LoginView, RegisterView | 登录/注册 |
| 仪表板 | DashboardView | 概览统计 |
| 股票分析 | SingleAnalysisView, BatchAnalysisView, QuickAnalysisView | 单股/批量/快速分析 |
| 股票列表 | StockListView | 股票数据浏览 |
| 股票筛选 | ScreeningView | 条件筛选 |
| 分析报告 | ReportsView | 历史报告 |
| 收藏 | FavoritesView | 自选股 |
| 模拟交易 | PaperTradingView | 虚拟交易 |
| 学习中心 | LearningView | 知识文章 |
| 任务队列 | QueueView | 异步任务状态 |
| 定时任务 | TasksView | 调度管理 |
| 系统设置 | SettingsView | 参数配置 |
| 系统管理 | SystemView | 运维管理 |

### 后端适配

- FastAPI 挂载静态文件目录（`frontend/dist`）
- SPA 路由 fallback：非 API/非静态文件请求返回 `index.html`
- CORS 配置更新：允许同域请求

## 是否有原型设计

否 — 项目已有完整的 Vue.js 前端，直接构建部署即可，无需重新设计原型。

## 实施步骤

1. **构建 Vue.js 前端** — 安装 yarn 依赖，配置 API 基础路径为相对路径，执行 `vite build` 生成 dist 产物。涉及文件：`frontend/.env.production`、`frontend/vite.config.ts`

2. **修改 FastAPI 挂载静态文件** — 在 `app/main.py` 中添加 StaticFiles 挂载和 SPA catch-all fallback，使 `/` 访问前端页面，`/api/*` 访问后端接口。涉及文件：`app/main.py`

3. **修改 .coze 构建流程** — 在 build 步骤中增加前端构建命令（yarn install + vite build），确保部署时自动构建前端。涉及文件：`.coze`

4. **修改 start_coze.sh 启动脚本** — 确保启动流程兼容前端静态文件路径，CORS 配置自动适配当前域名。涉及文件：`start_coze.sh`

5. **测试完整流程** — 构建前端 → 启动服务 → 浏览器访问 → 登录 → 股票分析，验证端到端功能。涉及文件：无（验证步骤）

## 页面规格

##### @nav(web-topbar)
> type: topbar
> platform: web

- @page(/) 仪表板
- @page(/analysis) 股票分析
- @page(/stocks) 股票列表
- @page(/screening) 股票筛选
- @page(/reports) 分析报告
- @page(/favorites) 收藏
- @page(/paper-trading) 模拟交易
- @page(/settings) 系统设置

##### @page(/) 仪表板

**核心职责**：展示投资组合概览和关键指标
**访问路径**：登录后默认跳转
**布局**：顶部导航栏 + 统计卡片行 + 图表区域 + 最近分析列表

##### @page(/analysis) 股票分析

**核心职责**：启动 AI 股票分析（单个/批量/快速）
**访问路径**：顶部导航直达
**布局**：Tab 切换（单个分析/批量分析/快速分析）+ 分析表单 + 结果展示区

##### @page(/stocks) 股票列表

**核心职责**：浏览和搜索股票数据
**访问路径**：顶部导航直达
**布局**：搜索栏 + 筛选器 + 数据表格（分页）
**列表项字段**：股票代码 / 股票名称 / 最新价 / 涨跌幅 / 成交量 / 操作

##### @page(/screening) 股票筛选

**核心职责**：按条件筛选股票
**访问路径**：顶部导航直达
**布局**：筛选条件面板 + 结果列表

##### @page(/reports) 分析报告

**核心职责**：查看历史分析报告
**访问路径**：顶部导航直达
**布局**：报告列表 + 详情展开

##### @page(/favorites) 收藏

**核心职责**：管理自选股
**访问路径**：顶部导航直达
**布局**：自选股列表 + 快速分析入口

##### @page(/paper-trading) 模拟交易

**核心职责**：虚拟交易练习
**访问路径**：顶部导航直达
**布局**：持仓概览 + 交易面板 + 交易记录

##### @page(/settings) 系统设置

**核心职责**：配置 API Key 和系统参数
**访问路径**：顶部导航直达
**布局**：设置表单分组（数据源配置/AI 模型配置/系统参数）

##### @page(/login) 登录

**核心职责**：用户身份认证
**访问路径**：未登录时自动跳转
**布局**：居中登录表单（用户名 + 密码 + 登录按钮）
**交互说明**

| 元素 | 动作 | 响应 | 传参 | 备注 |
|------|------|------|------|------|
| 登录按钮 | 点击 | 调用 API 登录，成功跳转 @page(/) | — | — |
| 注册链接 | 点击 | 跳转 @page(/register) | — | — |
