#!/bin/bash
# Скрипт для перезапуска VPN Club Pro Bot
echo "🔄 Начинаю перезапуск VPN Club Pro Bot..."

# Переходим в рабочую директорию
cd /home/deployer/vpn-club-pro-telegram-bot

# Останавливаем контейнеры
echo "🛑 Останавливаю Docker контейнеры..."
docker compose down

# Обновляем код
echo "📥 Обновляю код..."
git pull origin master

# Пересобираем и запускаем
echo "🔨 Пересобираю и запускаю контейнеры..."
docker compose up --build -d

# Проверяем статус
echo "📊 Проверяю статус..."
docker compose ps

