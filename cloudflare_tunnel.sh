#!/bin/bash

# Cloudflare Tunnel для VPN Club Pro Bot
echo "☁️ Настройка Cloudflare Tunnel..."

# Скачивание cloudflared
echo "📦 Установка cloudflared..."
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Аутентификация (откроется браузер)
echo "🔐 Авторизация в Cloudflare..."
cloudflared tunnel login

# Создание туннеля
echo "🚇 Создание туннеля..."
cloudflared tunnel create vpn-club-pro-bot

# Получение tunnel ID и обновление конфигурации
TUNNEL_ID=$(cloudflared tunnel list | grep vpn-club-pro-bot | awk '{print $1}')

# Создание конфигурации туннеля
cat > ~/.cloudflared/config.yml << EOF
tunnel: $TUNNEL_ID
credentials-file: ~/.cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: your-tunnel-domain.trycloudflare.com
    service: http://localhost:8000
  - service: http_status:404
EOF

# Запуск туннеля
echo "🚀 Запуск туннеля..."
cloudflared tunnel run vpn-club-pro-bot

echo "✅ Туннель настроен! Используйте полученный URL для webhook в ЮKassa" 