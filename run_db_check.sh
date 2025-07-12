#!/bin/bash

echo "=== ПРОВЕРКА БАЗЫ ДАННЫХ НА СЕРВЕРЕ ==="
echo "Время: $(date)"
echo ""

# Переходим в папку с проектом
cd /home/deployer/vpn-club-pro-telegram-bot

# Проверяем статус контейнеров
echo "1. СТАТУС DOCKER КОНТЕЙНЕРОВ:"
docker compose ps
echo ""

# Проверяем логи бота (последние 20 строк)
echo "2. ПОСЛЕДНИЕ ЛОГИ БОТА:"
docker compose logs --tail=20 bot
echo ""

# Запускаем проверку базы данных через Python скрипт
echo "3. ПРОВЕРКА БАЗЫ ДАННЫХ:"
docker compose exec -T bot python3 /app/check_database.py
echo ""

echo "=== ПРОВЕРКА ЗАВЕРШЕНА ===" 