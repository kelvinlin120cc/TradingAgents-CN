#!/bin/bash
# TradingAgents-CN 服务状态查询脚本
# 只读检查，不改变任何服务状态，无需 sudo

echo "========================================"
echo " TradingAgents-CN 服务状态"
echo "========================================"

echo "【1】Docker 引擎"
if systemctl is-active --quiet docker; then
    echo "  ✅ docker: active"
else
    echo "  ❌ docker: 未运行"
fi

echo "【2】数据库容器"
docker ps -a --filter "name=tradingagents-mongodb" --filter "name=tradingagents-redis" \
    --format "  {{.Names}}: {{.Status}}" 2>/dev/null || echo "  ⚠️ 无法查询 Docker"

echo "【3】后端服务 (tradingagents)"
echo "  状态: $(systemctl is-active tradingagents) / 自启: $(systemctl is-enabled tradingagents 2>/dev/null)"

echo "【4】Nginx (前端 + 反向代理)"
echo "  状态: $(systemctl is-active nginx) / 自启: $(systemctl is-enabled nginx 2>/dev/null)"

echo "【5】端口监听"
for p in 27017 6379 8001 80; do
    if ss -tlnp 2>/dev/null | grep -q ":$p "; then
        echo "  ✅ 端口 $p: 监听中"
    else
        echo "  ❌ 端口 $p: 未监听"
    fi
done

echo "【6】HTTP 健康检查"
curl -s -o /dev/null -w "  后端API (8001直连):  %{http_code}\n" http://localhost:8001/api/health 2>/dev/null || echo "  后端API: 无响应"
curl -s -o /dev/null -w "  后端API (经Nginx):   %{http_code}\n" http://localhost/api/health 2>/dev/null || echo "  经Nginx: 无响应"
curl -s -o /dev/null -w "  前端页面:            %{http_code}\n" http://localhost/ 2>/dev/null || echo "  前端: 无响应"

echo "========================================"
