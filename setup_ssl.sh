#!/bin/bash

# Скрипт установки Let's Encrypt SSL для VPN Club Pro Bot
echo "🔐 Установка Let's Encrypt SSL..."

# Параметры (замените на ваши)
DOMAIN="your-domain.com"  # Замените на ваш домен
EMAIL="your-email@example.com"  # Замените на ваш email

# Установка certbot
echo "📦 Установка certbot..."
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Остановка nginx для получения сертификата
echo "⏹️ Остановка nginx..."
sudo docker-compose stop nginx

# Получение сертификата
echo "🔑 Получение SSL сертификата..."
sudo certbot certonly --standalone \
  --email $EMAIL \
  --agree-tos \
  --no-eff-email \
  -d $DOMAIN

# Копирование сертификатов в nginx директорию
echo "📋 Копирование сертификатов..."
sudo mkdir -p nginx/ssl
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/server.crt
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/server.key
sudo chown -R $USER:$USER nginx/ssl

# Обновление nginx конфигурации
echo "⚙️ Обновление nginx config..."
sed -i "s/server_name 5.129.196.245;/server_name $DOMAIN;/g" nginx/nginx.conf

# Перезапуск контейнеров
echo "🔄 Перезапуск сервисов..."
sudo docker-compose up -d

echo "✅ SSL настроен! Новый webhook URL: https://$DOMAIN/webhook/yookassa" 