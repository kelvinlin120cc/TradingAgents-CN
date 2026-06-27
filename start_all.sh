#!/bin/bash
# TradingAgents-CN 一键启动脚本
# 幂等设计：任何服务状态下都可重复执行，不会产生副作用
# 启动顺序：数据库容器 → 后端服务 → Nginx
#
# 用法：
#   bash start_all.sh           启动全部，并设置为「电脑重启后不自动启动」
#   bash start_all.sh enabled   启动全部，并设置为「电脑重启后自动启动」

set -u

AUTOSTART="${1:-}"

echo "========================================"
echo " TradingAgents-CN 启动中..."
echo "========================================"

echo "① 启动数据库容器 (MongoDB / Redis)..."
docker start tradingagents-mongodb tradingagents-redis

echo "② 等待数据库就绪..."
sleep 3

echo "③ 准备日志目录并启动后端服务 (tradingagents)..."
mkdir -p /tmp/tradingagents_logs
sudo systemctl start tradingagents

echo "④ 启动 Nginx (前端 + 反向代理)..."
sudo systemctl start nginx

# 根据参数设置开机自启策略
if [ "$AUTOSTART" = "enabled" ]; then
    echo "⑤ 配置开机自启：✅ 启用"
    docker update --restart unless-stopped tradingagents-mongodb tradingagents-redis >/dev/null
    sudo systemctl enable tradingagents >/dev/null 2>&1
    sudo systemctl enable nginx >/dev/null 2>&1
    echo "   数据库容器 / 后端 / Nginx 均已设为开机自启"
else
    echo "⑤ 配置开机自启：❌ 禁用（电脑重启后不自动启动）"
    docker update --restart no tradingagents-mongodb tradingagents-redis >/dev/null
    sudo systemctl disable tradingagents >/dev/null 2>&1
    sudo systemctl disable nginx >/dev/null 2>&1
    echo "   数据库容器 / 后端 / Nginx 均已取消开机自启"
fi

echo "⑥ 验证服务状态..."
sleep 3
echo "----------------------------------------"
docker ps --filter "name=mongo" --filter "name=redis" --format "  容器 {{.Names}}: {{.Status}}"
echo "  后端服务: $(systemctl is-active tradingagents) / 自启: $(systemctl is-enabled tradingagents 2>/dev/null)"
echo "  Nginx:    $(systemctl is-active nginx) / 自启: $(systemctl is-enabled nginx 2>/dev/null)"
echo "----------------------------------------"
curl -s -o /dev/null -w "  后端API (经Nginx): %{http_code}\n" http://localhost/api/health
curl -s -o /dev/null -w "  前端页面:          %{http_code}\n" http://localhost/
echo "========================================"
echo " 完成，访问 http://localhost/"
echo "========================================"
