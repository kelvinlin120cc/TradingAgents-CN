#!/bin/bash
# Nginx启动脚本 - 使用本地Nginx

cd /home/kelvin/TradingAgents-CN

# 停止旧的Docker Nginx容器（如果存在）
docker stop tradingagents-nginx-direct 2>/dev/null || true
docker rm tradingagents-nginx-direct 2>/dev/null || true

# 停止本地Nginx服务（如果正在运行）
sudo systemctl stop nginx 2>/dev/null || true

# 备份原有Nginx配置
if [ -f /etc/nginx/nginx.conf ]; then
    sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
fi

# 复制Nginx配置文件
sudo cp /home/kelvin/TradingAgents-CN/nginx_direct.conf /etc/nginx/nginx.conf

# 部署前端静态文件到标准web目录（避免home目录权限问题）
sudo rm -rf /var/www/tradingagents
sudo mkdir -p /var/www/tradingagents
sudo cp -r /home/kelvin/TradingAgents-CN/frontend/dist/* /var/www/tradingagents/
sudo chown -R www-data:www-data /var/www/tradingagents

# 测试Nginx配置
sudo nginx -t

# 启动本地Nginx服务
sudo systemctl start nginx
sudo systemctl enable nginx

echo "本地Nginx已启动，访问 http://localhost/"