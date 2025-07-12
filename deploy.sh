#!/bin/bash

# Локальный скрипт деплоя VPN Club Pro Bot
# Для локальной разработки и тестирования
# Основной деплой теперь происходит через GitHub Actions

set -e  # Останавливаться при ошибках

echo "🚀 Локальный деплой VPN Club Pro Bot"
echo "==========================================="
echo "ℹ️  Для продакшн деплоя используйте GitHub Actions"
echo ""

# Проверяем наличие .env файла
if [ ! -f .env ]; then
    echo "⚠️  Файл .env не найден. Создайте его на основе .env.example"
    echo "   cp .env.example .env"
    echo "   # Затем отредактируйте .env файл"
    exit 1
fi

# Проверяем наличие Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker и попробуйте снова."
    exit 1
fi

# 1. Останавливаем существующие контейнеры
echo "🛑 Остановка существующих контейнеров..."
docker compose down

# 2. Сборка и запуск базы данных
echo "🗄️  Запуск базы данных..."
docker compose up -d db redis

# Ждем запуска PostgreSQL
echo "⏳ Ожидание запуска PostgreSQL..."
sleep 10

# Проверяем доступность базы данных
echo "🔍 Проверка доступности базы данных..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose exec db pg_isready -U postgres -d vpn_club; then
        echo "✅ База данных доступна"
        break
    else
        echo "⏳ Ожидание базы данных... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
        sleep 2
        RETRY_COUNT=$((RETRY_COUNT + 1))
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ Не удалось подключиться к базе данных"
    exit 1
fi

# 3. Инициализация базы данных
echo "🔧 Инициализация базы данных..."

# Проверяем, есть ли Python в системе
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Python не найден в системе"
    exit 1
fi

# Проверяем, есть ли виртуальное окружение
if [ -d "venv" ]; then
    echo "🐍 Активация виртуального окружения..."
    source venv/bin/activate
fi

# Запускаем инициализацию базы данных
echo "🏗️  Инициализация базы данных..."
$PYTHON_CMD manage_db.py

# 4. Сборка и запуск приложения
echo "🔨 Сборка приложения..."
docker compose build bot

echo "🚀 Запуск приложения..."
docker compose up -d

# 5. Проверка статуса
echo "📊 Проверка статуса контейнеров..."
docker compose ps

# Показываем логи бота
echo "📋 Логи бота (последние 20 строк):"
docker compose logs --tail=20 bot

echo ""
echo "✅ Локальный деплой завершен успешно!"
echo ""
echo "🔗 Полезные команды:"
echo "   docker compose logs -f bot     # Просмотр логов"
echo "   docker compose restart bot     # Перезапуск бота"
echo "   docker compose down            # Остановка всех сервисов"
echo "   docker compose up -d           # Перезапуск всех сервисов"
echo ""
echo "🗄️  Управление базой данных:"
echo "   python manage_db.py            # Обычная инициализация"
echo "   python manage_db.py --force-fresh  # Принудительная пересборка БД"
echo "   python manage_db.py --skip-data    # Только схема, без данных"
echo ""
echo "🎯 Для продакшн деплоя:"
echo "   git push origin master         # Автоматический деплой через GitHub Actions" 