#!/bin/bash

# Быстрая настройка DuckDNS + SSL для VPN Club Pro Bot
echo "🦆 Настройка DuckDNS + SSL..."

# Параметры (получите на https://www.duckdns.org/)
DUCK_DOMAIN="your-name"  # Замените на ваше имя (без .duckdns.org)
DUCK_TOKEN="your-token"  # Получите токен на duckdns.org
EMAIL="your-email@example.com"

FULL_DOMAIN="$DUCK_DOMAIN.duckdns.org"

# Обновление DuckDNS
echo "🔄 Обновление DuckDNS записи..."
curl "https://www.duckdns.org/update?domains=$DUCK_DOMAIN&token=$DUCK_TOKEN&ip="

# Установка certbot
echo "📦 Установка certbot..."
sudo apt update
sudo apt install -y certbot

# Остановка nginx
echo "⏹️ Остановка nginx..."
sudo docker-compose stop nginx

# Получение сертификата
echo "🔑 Получение SSL сертификата..."
sudo certbot certonly --standalone \
  --email $EMAIL \
  --agree-tos \
  --no-eff-email \
  -d $FULL_DOMAIN

# Копирование сертификатов
echo "📋 Копирование сертификатов..."
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/$FULL_DOMAIN/fullchain.pem nginx/ssl/server.crt
sudo cp /etc/letsencrypt/live/$FULL_DOMAIN/privkey.pem nginx/ssl/server.key
sudo chown -R $USER:$USER nginx/ssl

# Обновление nginx config
echo "⚙️ Обновление nginx конфигурации..."
sed -i "s/server_name 5.129.196.245;/server_name $FULL_DOMAIN;/g" nginx/nginx.conf

# Перезапуск
echo "🔄 Перезапуск сервисов..."
sudo docker-compose up -d

echo "✅ SSL настроен!"
echo "🔗 Новый webhook URL: https://$FULL_DOMAIN/webhook/yookassa"
echo "📝 Обновите URL в ЮKassa на: https://$FULL_DOMAIN/webhook/yookassa" 