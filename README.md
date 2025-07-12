# VPN Club Pro Bot

Автоматизированный сервис для продажи и управления доступом к VPN на базе технологии Outline через интерфейс Telegram-бота.

## 🚀 Возможности

- **Пробный период**: 3 дня бесплатно с лимитом 10 ГБ
- **Платные тарифы**: 1, 3, 6, 12 месяцев с безлимитным трафиком
- **Автоматические ключи**: Создание и управление ключами Outline
- **Платежи YooKassa**: Интеграция с российским платежным сервисом
- **Уведомления**: Автоматические напоминания об истечении подписки
- **Балансировка**: Распределение нагрузки между серверами
- **Админ-панель**: Статистика, рассылки, управление пользователями

## 🛠 Технологический стек

- **Python 3.10+** - Основной язык
- **aiogram 3.x** - Telegram Bot Framework
- **PostgreSQL** - База данных
- **SQLAlchemy** - ORM
- **YooKassa API** - Платежи
- **Docker** - Контейнеризация
- **APScheduler** - Планировщик задач

## 📦 Установка и настройка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd vpn-club-pro-telegram-bot
```

### 2. Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Заполните необходимые переменные:

```env
# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_ID=your_telegram_id

# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/vpn_club

# YooKassa Configuration
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# Outline Servers Configuration
OUTLINE_SERVER_1_URL=https://your-server-1/api-key
OUTLINE_SERVER_2_URL=https://your-server-2/api-key

# Webhook Configuration (оставьте пустым для polling)
WEBHOOK_URL=https://your-domain.com

# Debug Mode
DEBUG=False

# Database Initialization (для Docker)
SKIP_DB_INIT=false  # true чтобы пропустить автоинициализацию БД
```

### 3. Продакшн деплой (Рекомендуется)

```bash
# Автоматический деплой через GitHub Actions
git push origin master

# Деплой автоматически:
# 1. Проверит и инициализирует базу данных
# 2. Загрузит дамп с данными, если база новая
# 3. Соберет и запустит приложение
```

### 4. Локальная разработка

```bash
# Локальный деплой для разработки
./deploy.sh

# Или ручной запуск Docker Compose
docker-compose up -d

# Просмотр логов
docker-compose logs -f bot

# Остановка
docker-compose down
```

### 4. Ручная установка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Инициализация базы данных
python manage_db.py

# Запуск бота
python main.py
```

## 🔧 Настройка Outline серверов

1. Установите Outline Manager
2. Создайте новый сервер
3. Скопируйте API URL сервера
4. Добавьте URL в переменные окружения

## 💳 Настройка YooKassa

1. Зарегистрируйтесь в [YooKassa](https://yookassa.ru/)
2. Получите Shop ID и Secret Key
3. Настройте webhook на `https://your-domain.com/webhook/yookassa`
4. Добавьте данные в переменные окружения

## 📋 Административные команды

- `/admin` - Панель администратора
- `/stats` - Статистика бота
- `/broadcast <текст>` - Массовая рассылка
- `/maintenance` - Уведомление о технических работах
- `/user_info <telegram_id>` - Информация о пользователе

## 🗄️ Управление базой данных

### Инициализация базы данных

```bash
# Создание базы данных и выполнение миграций
python manage_db.py
```

### Миграции

Миграции находятся в папке `migrations/`:
- `001_initial_schema.sql` - Создание начальной схемы БД

Для добавления новых миграций:
1. Создайте файл `002_название_миграции.sql` в папке `migrations/`
2. Добавьте его в список миграций в `manage_db.py`

### Продакшн деплой через GitHub Actions

Автоматический деплой запускается при push в ветку `master`:

```bash
git push origin master
```

GitHub Actions workflow автоматически:

**Джоба 1: Инициализация базы данных**
- Синхронизирует файлы миграций на сервер
- Запускает PostgreSQL контейнер
- Проверяет состояние базы данных
- Если база новая - загружает полный дамп с данными
- Если база существует - проверяет схему

**Джоба 2: Деплой приложения**
- Синхронизирует все файлы проекта
- Собирает Docker образы
- Запускает все сервисы (бот, БД, Redis)
- Очищает старые Docker образы

### Локальный деплой

Для локальной разработки используйте:

```bash
./deploy.sh
```

Локальный скрипт:
- Проверит наличие .env файла
- Остановит существующие контейнеры
- Запустит PostgreSQL и Redis
- Дождется готовности базы данных
- Инициализирует БД через `manage_db.py`
- Соберет и запустит приложение

### Docker автоинициализация

При запуске через Docker Compose бот автоматически:
- Дождется доступности PostgreSQL
- Проверит, существует ли база данных
- Если БД новая - загрузит полный дамп с данными
- Если БД существует - проверит схему через SQLAlchemy

Управляющие переменные:
- `SKIP_DB_INIT=true` - пропустить автоинициализацию

## 🔄 Автоматические процессы

- **Уведомления за 3 дня** до истечения подписки (10:00 ежедневно)
- **Деактивация истекших** подписок (10:30 ежедневно)
- **Удаление ключей** из Outline при истечении

## 📊 Структура проекта

```
vpn-club-pro-telegram-bot/
├── app/
│   ├── handlers/          # Обработчики команд
│   ├── keyboards/         # Клавиатуры Telegram
│   ├── models/           # Модели базы данных
│   ├── services/         # Бизнес-логика
│   ├── database.py       # Подключение к БД
│   ├── scheduler.py      # Планировщик задач
│   └── webhook.py        # Webhook обработчики
├── migrations/           # Миграции базы данных
│   └── 001_initial_schema.sql
├── config.py             # Конфигурация
├── main.py              # Точка входа
├── manage_db.py         # Управление базой данных
├── requirements.txt     # Зависимости
├── Dockerfile          # Docker образ
└── docker-compose.yml  # Docker Compose
```

## 🐛 Отладка

### Логи

```bash
# Docker
docker-compose logs -f bot

# Прямой запуск
python main.py
```

### Проверка БД

```bash
# Подключение к PostgreSQL
docker-compose exec db psql -U postgres -d vpn_club

# Просмотр таблиц
\dt

# Просмотр пользователей
SELECT * FROM users LIMIT 10;
```

### Тестирование Outline API

```bash
# Проверка доступности сервера
curl -k https://your-server-url/server

# Получение списка ключей
curl -k https://your-server-url/access-keys
```

## 🔐 Безопасность

- Все чувствительные данные в переменных окружения
- SSL/TLS для всех API запросов
- Проверка подписи webhook от YooKassa
- Ограничение административных команд

## 📈 Масштабирование

- Добавление новых Outline серверов через переменные окружения
- Балансировка нагрузки между серверами
- Горизонтальное масштабирование через Docker

## 🤝 Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь в корректности переменных окружения
3. Проверьте доступность Outline серверов
4. Проверьте настройки YooKassa

## 📄 Лицензия

MIT License 