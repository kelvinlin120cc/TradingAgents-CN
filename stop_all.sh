#!/bin/bash
# TradingAgents-CN 一键停止脚本
# 默认停止后端 + Nginx，保留数据库容器（保证数据持续可用）
# 如需同时停止数据库容器，加参数：  bash stop_all.sh --with-db

set -u

echo "========================================"
echo " TradingAgents-CN 停止中..."
echo "========================================"

echo "① 停止后端服务 (tradingagents)..."
sudo systemctl stop tradingagents

echo "② 停止 Nginx..."
sudo systemctl stop nginx

if [ "${1:-}" = "--with-db" ]; then
    echo "③ 停止数据库容器 (MongoDB / Redis)..."
    docker stop tradingagents-mongodb tradingagents-redis
else
    echo "③ 保留数据库容器（如需停止请加 --with-db 参数）"
fi

echo "----------------------------------------"
echo "  后端服务: $(systemctl is-active tradingagents)"
echo "  Nginx:    $(systemctl is-active nginx)"
docker ps --filter "name=mongo" --filter "name=redis" --format "  容器 {{.Names}}: {{.Status}}"
echo "========================================"
echo " 已停止"
echo "========================================"
