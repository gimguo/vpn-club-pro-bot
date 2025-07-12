# Инструкции по разработке VPN Club Bot

## Сервер и деплой

### ⚠️ ВАЖНО: GitHub Actions Runner на сервере
Сервер `178.236.243.99` имеет установленный GitHub Actions runner для автоматического деплоя.

**НЕ ПОДКЛЮЧАЙТЕСЬ К СЕРВЕРУ НАПРЯМУЮ ПО SSH ДЛЯ ИЗМЕНЕНИЙ!**

### Процесс деплоя
1. Внесите изменения в код локально
2. Закоммитьте изменения: `git commit -m "описание изменений"`
3. Запушьте в master: `git push origin master`
4. GitHub Actions автоматически задеплоит изменения на сервер

### Структура проекта на сервере
- Путь: `/home/deployer/vpn-club-pro-telegram-bot`
- Docker контейнеры: `bot`, `db`, `nginx`, `redis`
- Команды Docker: `docker compose` (не `docker-compose`)

### Проверка статуса на сервере
Для проверки базы данных и логов используйте:
```bash
# Только для чтения, без изменений!
ssh deployer@178.236.243.99 "cd /home/deployer/vpn-club-pro-telegram-bot && ./run_db_check.sh"
```

### Структура Docker контейнеров
```
vpn-club-pro-telegram-bot-bot-1    - Telegram бот
vpn-club-pro-telegram-bot-db-1     - PostgreSQL база данных
vpn-club-pro-telegram-bot-nginx-1  - Nginx веб-сервер
vpn-club-pro-telegram-bot-redis-1  - Redis кэш
```

### Логи и диагностика
- Логи бота: `docker compose logs bot`
- Статус контейнеров: `docker compose ps`
- Проверка базы: `./run_db_check.sh`

### Переменные окружения
- `BOT_TOKEN` - токен Telegram бота
- `TELEGRAM_PAYMENT_PROVIDER_TOKEN` - токен для Telegram Payments (пустой для Stars)
- `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - настройки БД

## Локальная разработка

### Запуск локально
```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка .env файла
cp env.example .env
# Отредактируйте .env с вашими данными

# Запуск бота
python main.py
```

### Тестирование платежей
- Локально: SQLite база данных
- Сервер: PostgreSQL база данных
- Для тестирования Stars используйте админский ID: 7909062876

### Структура проекта
```
app/
├── handlers/          # Обработчики команд
├── keyboards/         # Клавиатуры
├── models/           # Модели данных
├── services/         # Бизнес-логика
└── middleware/       # Middleware

migrations/           # Миграции БД
blog/                # Система блога
```

## Telegram Payments

### Конфигурация Stars
- Provider token: пустой (для Stars)
- Цены: в 3 раза дешевле рублевых тарифов
- Админ ID: 7909062876

### Тарифы Stars
- Trial: 50⭐
- Monthly: 50⭐  
- Quarterly: 117⭐
- Half-yearly: 217⭐
- Yearly: 400⭐

### Отладка платежей
Используйте `check_database.py` для проверки записей в таблице `telegram_payments`. 