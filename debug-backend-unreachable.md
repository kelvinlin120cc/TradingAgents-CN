# Debug Session: backend-unreachable

Status: [OPEN]

## Symptom
前端提示：后端服务连接失败，无法连接到后端服务，请检查服务是否正常运行。

## Initial hypotheses
1. tradingagents systemd 服务启动失败并反复重启。
2. /tmp/tradingagents_logs 或相关数据目录缺失，导致 systemd/应用启动失败。
3. .env 被 shell source 时仍有未加引号的特殊字符，导致环境变量加载失败。
4. MongoDB/Redis 容器健康但认证或连接配置导致后端启动卡住/退出。
5. Nginx 代理配置正常，但后端 8001 未监听导致前端报连接失败。

## Evidence log
- `systemctl status tradingagents`: `inactive (dead)`，不是运行中也不是启动失败循环。
- `/tmp/tradingagents_logs/systemd.log`: 文件不存在，但当前后端服务没有启动，因此不是正在报 209/STDOUT。
- `status_all.sh`: MongoDB/Redis 容器均为 `Exited`，后端 `inactive`，Nginx `inactive`。
- 端口 27017/6379/8001/80 均未监听。
- HTTP 健康检查全部无响应。

## Current conclusion
根因是所有相关服务当前都处于停止状态；前端提示后端连接失败是预期结果。当前无需修改业务代码，先按既定一键启动脚本恢复服务。
