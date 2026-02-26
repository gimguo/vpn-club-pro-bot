# VPN Club Pro Bot — Контекст проекта

## Что это

Telegram-бот для продажи VPN-подписок на базе **Outline VPN (Shadowbox)**. Бот + система автоматического управления серверами **VPN Forge**.

- **Язык:** Python 3.11+
- **Фреймворк бота:** aiogram 3.13
- **ORM:** SQLAlchemy 2.0 (async, asyncpg)
- **БД:** PostgreSQL 15
- **Кэш:** Redis 7
- **Контейнеризация:** Docker Compose
- **Путь:** `/home/andrey/projects/vpn-bot`
- **Админ:** @gimguo (telegram_id: 7909062876)

## Текущий флот серверов

| Сервер | IP | Страна | Статус | Outline |
|--------|-----|--------|--------|---------|
| de-germany-1 | 46.203.233.50 | 🇩🇪 DE | 🟢 active | ✅ port 31468 |
| ir-server-2 | 151.241.100.129 | 🇮🇷 IR | 🟢 active | ✅ port 9225 |

## Структура проекта

```
main.py                    — Точка входа: бот + FastAPI webhook + VPN Forge
config.py                  — Settings из .env (все настройки)
CONTEXT.md                 — Этот файл (контекст для ИИ-ассистента)
app/
  database.py              — engine, AsyncSessionLocal, init_db() + миграции
  scheduler.py             — APScheduler: уведомления, обработка webhook-файлов
  webhook.py               — aiohttp webhook сервер для Telegram
  handlers/
    __init__.py            — register_all_handlers(dp)
    start.py               — /start + реферальные deeplinks + двухэтапное согласие
    common.py              — /terms, /privacy, меню, "Мой VPN", "Друзьям", скачать
    tariffs.py             — Выбор тарифов, пробный период
    payments.py            — Оплата: YooKassa, Telegram Stars, карта
    support.py             — Поддержка: тикеты
    admin.py               — Админка: /admin, /users, статистика, рассылки
    forge_admin.py         — VPN Forge: /forge, /forge_add, управление серверами
  keyboards/
    main_keyboard.py       — Контекстное главное меню (зависит от подписки/триала)
    tariff_keyboard.py     — Тарифы с психологическим ценообразованием
    payment_keyboard.py    — Выбор способа оплаты + подтверждение
  models/
    base.py                — BaseModel (id, created_at, updated_at)
    user.py                — User + referral + terms_accepted + pd_consent
    subscription.py        — Subscription (tariff_type, access_url, end_date)
    payment.py             — Payment (YooKassa)
    telegram_payment.py    — TelegramPayment (Stars, Card)
    support.py             — SupportTicket, SupportMessage
  services/
    user_service.py        — CRUD пользователей + реферальная система
    subscription_service.py — Подписки: создание, проверка, деактивация
    payment_service.py     — YooKassa платежи
    telegram_payment_service.py — Stars/Card платежи
    outline_service.py     — Outline VPN API: ключи, балансировка
    support_service.py     — Тикеты поддержки
  middleware/
    maintenance.py         — Middleware режима обслуживания
  vpn_forge/               — СИСТЕМА АВТОУПРАВЛЕНИЯ СЕРВЕРАМИ
    models.py              — VPNServer, ServerEvent, HealthCheck
    ssh_client.py          — Async SSH клиент (asyncssh)
    deployer.py            — Автоустановка Outline (Docker + install script)
    monitor.py             — Мониторинг: SSH, Docker, Outline API, CPU/RAM/Disk
    healer.py              — Самолечение: restart, cleanup, reboot
    ai_agent.py            — ИИ-диагностика: DeepSeek через OpenRouter
    orchestrator.py        — Автомасштабирование: scale up/down
    manager.py             — Центральный менеджер: фоновые циклы
    prompts/system_prompt.md — Системный промпт для DeepSeek
    providers/base.py      — Абстрактный интерфейс провайдера
    providers/hetzner.py   — Hetzner Cloud API
```

## VPN Forge — как работает

```
Monitor (каждые 60с) → проверяет все серверы → пишет HealthCheck
         ↓ critical x3
     Healer → restart Docker, cleanup disk, reboot
         ↓ не помог
     AI Agent → SSH диагностика → DeepSeek → fix-команды
         ↓ не помог
     Admin notification

Orchestrator (каждые 5 мин) → оценивает загрузку флота
  load > 70% → Scale UP (Hetzner API → новый сервер → deploy Outline)
  load < 30% → Scale DOWN (удалить лишний сервер)
```

Deployer при установке: ждёт dpkg lock → останавливает unattended-upgrades → apt update/upgrade → Docker install (с retry) → Outline install script → парсит API URL + cert → верифицирует API.

## Docker Compose

- `vpn_bot_db` (postgres:15-alpine) — порт **5435**:5432
- `vpn_bot_redis` (redis:7-alpine) — порт **6380**:6379
- `vpn_bot_app` — порт 8000 (FastAPI webhook), user: root, pip install asyncssh httpx при старте
- `vpn_bot_nginx` — порты **8080**:80, **8443**:443, **9000**:9000
- Сеть: `vpn_bot_network` (изолированная)
- Volume: `~/.ssh:/root/.ssh:ro` для SSH-ключей VPN Forge

## Ключевые .env переменные

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_ID=7909062876
TELEGRAM_BOT_USERNAME=vpn_club_pro_bot
DATABASE_URL=postgresql+asyncpg://...
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
TELEGRAM_PAYMENT_PROVIDER_TOKEN=...
OUTLINE_API_URL=...

# VPN Forge
VPN_FORGE_ENABLED=true
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=deepseek/deepseek-chat
HETZNER_API_TOKEN=...
VPN_FORGE_SSH_KEY_PATH=/root/.ssh/vpn_forge
VPN_FORGE_MONITOR_INTERVAL=60
VPN_FORGE_MAX_SERVERS=10
VPN_FORGE_SCALE_UP_THRESHOLD=70
VPN_FORGE_SCALE_DOWN_THRESHOLD=30
```

## Оплата

3 способа: **YooKassa** (рубли, ИП), **Telegram Stars**, **Банковская карта** (USD).

Поток: Тариф → Способ оплаты → Подтверждение → Invoice → pre_checkout → successful_payment → Подписка + Outline ключ

## Тарифы

| Тариф | Цена | Период |
|-------|------|--------|
| trial | 0₽ | 7 дней, 10 ГБ |
| monthly | 150₽ | 1 мес |
| quarterly | 350₽ | 3 мес |
| half_yearly | 650₽ | 6 мес |
| yearly | 1200₽ | 12 мес |

## Реферальная система

- Уникальный `referral_code` при регистрации
- Ссылка: `https://t.me/vpn_club_pro_bot?start=ref_{CODE}`
- +7 дней другу, +7 дней рефереру
- Уровни: Новичок → Активист → Амбассадор → Мастер → Легенда
- ⚠️ Тексты НЕ содержат упоминаний обхода блокировок (ФЗ-38, ФЗ-281)

## Юридическое соответствие

**Статус: ✅ ГОТОВО К ЗАПУСКУ** — полное соответствие ФЗ-152, ФЗ-149, ФЗ-38, ФЗ-281, ФЗ-161, КоАП 13.11.

- `/terms` — Пользовательское соглашение (3 сообщения)
- `/privacy` — Политика конфиденциальности (3 сообщения)
- Двухэтапная регистрация: 1) принятие условий → 2) согласие на обработку ПД
- Позиционирование: **защита данных и шифрование**, НЕ обход блокировок
- ОКВЭД: 62.09 (основной), 63.11 (дополнительный)

## Частые грабли (уже исправлено)

- `half_yearly` → используем `removeprefix("tariff_")` вместо `split("_")`
- `scalar_one_or_none()` → `scalars().first()` + `limit(1)`
- `datetime.now()` → `datetime.now(timezone.utc)`
- Deployer: ожидание dpkg lock + retry Docker install
- `forge_refresh`: TelegramBadRequest → try/except + timestamp в сообщении

## Что ещё НЕ реализовано (TODO)

- Миграция ключей при scale down (сейчас удаляет только пустые серверы)
- DigitalOcean / Vultr провайдеры (только Hetzner для auto-scale)
- Уведомление рефереру когда друг активирует VPN
- Dashboard с графиками нагрузки серверов
