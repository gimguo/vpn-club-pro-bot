#!/bin/bash

# Скрипт для быстрого запуска VPN Club Pro Bot

echo "🚀 Запуск VPN Club Pro Bot..."

# Проверка существования .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    echo "📝 Создайте файл .env на основе .env.example"
    echo "💡 Команда: cp .env.example .env"
    exit 1
fi

# Проверка Docker и Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен!"
    echo "📦 Установите Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose не установлен!"
    echo "📦 Установите Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Функция для выбора режима запуска
echo "🔧 Выберите режим запуска:"
echo "1) Production (Docker Compose)"
echo "2) Development (локально)"
echo "3) Остановить сервисы"
echo "4) Просмотр логов"
echo "5) Пересборка контейнеров"

read -p "Введите номер (1-5): " choice

case $choice in
    1)
        echo "🐳 Запуск в режиме Production с Docker Compose..."
        docker compose up -d
        echo "✅ Сервисы запущены!"
        echo "📋 Просмотр логов: docker compose logs -f bot"
        echo "🛑 Остановка: docker compose down"
        ;;
    2)
        echo "💻 Запуск в режиме Development..."
        if ! command -v python3 &> /dev/null; then
            echo "❌ Python 3 не установлен!"
            exit 1
        fi
        
        # Создание виртуального окружения если его нет
        if [ ! -d "venv" ]; then
            echo "📦 Создание виртуального окружения..."
            python3 -m venv venv
        fi
        
        # Активация виртуального окружения
        source venv/bin/activate
        
        # Установка зависимостей
        echo "📥 Установка зависимостей..."
        pip install -r requirements.txt
        
        # Запуск бота
        echo "🤖 Запуск бота..."
        python main.py
        ;;
    3)
        echo "🛑 Остановка сервисов..."
        docker compose down
        echo "✅ Сервисы остановлены!"
        ;;
    4)
        echo "📋 Просмотр логов..."
        docker compose logs -f bot
        ;;
    5)
        echo "🔨 Пересборка контейнеров..."
        docker compose down
        docker compose build --no-cache
        docker compose up -d
        echo "✅ Контейнеры пересобраны и запущены!"
        ;;
    *)
        echo "❌ Неверный выбор!"
        exit 1
        ;;
esac 