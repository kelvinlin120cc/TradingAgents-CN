# Debug Session: pulse-no-data

Status: [OPEN]

## Symptom
访问 `http://localhost/pulse` 页面无法获取数据。

## Initial hypotheses
1. 后端或 Nginx 未运行，导致 `/pulse` 页面 API 请求失败。
2. `/api/pulse/overview` 路由返回非 200，例如 404/500/502。
3. Pulse 接口能返回，但返回结构为空或前端解析失败。
4. Polymarket/Kalshi 外部请求超时，且快照缓存不可用。
5. 数据目录/快照文件路径变化导致后端找不到 `pulse_snapshot.json`。

## Evidence log
- `status_all.sh`: Docker、MongoDB、Redis、后端、Nginx 均 active，端口 27017/6379/8001/80 均监听。
- `curl http://localhost/api/pulse/overview`: HTTP 200，但最初返回 `sources: []`, `modules: []`。
- 后端日志：`pulse snapshot save failed: [Errno 13] Permission denied: '/app'`。
- Grep 发现 `market_pulse.py`、`polymarket_signals.py`、`kalshi_signals.py` 均硬编码 `Path("/app/data/pulse")`。
- `.env` 当前配置：`TRADINGAGENTS_DATA_DIR=/tmp/tradingagents_data`。
- 修复后，`/tmp/tradingagents_data/pulse/pulse_snapshot.json` 已生成，大小 38289 bytes。
- 修复后接口返回：`sources=['polymarket','kalshi']`, `modules_len=10`。

## Root cause
Pulse 快照目录仍使用 Docker 时代的硬编码路径 `/app/data/pulse`。直接部署模式下服务用户无法写 `/app`，导致快照保存失败；初始冷启动时又遇到数据源超时/空结果，最终页面得到空模块。

## Fix
将三个 Pulse 模块的快照目录改为：
`Path(os.getenv("TRADINGAGENTS_DATA_DIR", "data")) / "pulse"`

Affected files:
- `tradingagents/pulse/market_pulse.py`
- `tradingagents/pulse/polymarket_signals.py`
- `tradingagents/pulse/kalshi_signals.py`

## Verification
- `curl http://localhost/api/pulse/overview`: HTTP 200。
- 返回包含 `sources=['polymarket','kalshi']`。
- 返回 `modules_len=10`。
- `/tmp/tradingagents_data/pulse/pulse_snapshot.json` 已写入。
