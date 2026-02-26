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

## Структура проекта

```
main.py                    — Точка входа: бот + FastAPI webhook + VPN Forge
config.py                  — Settings из .env (все настройки)
app/
  database.py              — engine, AsyncSessionLocal, init_db() + миграции
  scheduler.py             — APScheduler: уведомления, обработка webhook-файлов
  webhook.py               — aiohttp webhook сервер для Telegram
  handlers/
    __init__.py            — register_all_handlers(dp)
    start.py               — /start + реферальные deeplinks (ref_CODE)
    common.py              — Главное меню, "Мой VPN", "Друзьям", скачать, инструкции
    tariffs.py             — Выбор тарифов, пробный период, "Попробовать бесплатно"
    payments.py            — Оплата: YooKassa, Telegram Stars, карта, pre_checkout
    support.py             — Поддержка: тикеты
    admin.py               — Админка бота: статистика, рассылки
    forge_admin.py         — Админка VPN Forge: /forge, управление серверами
  keyboards/
    main_keyboard.py       — Контекстное главное меню (зависит от подписки/триала)
    tariff_keyboard.py     — Тарифы с психологическим ценообразованием
    payment_keyboard.py    — Выбор способа оплаты + подтверждение
  models/
    base.py                — BaseModel (id, created_at, updated_at)
    user.py                — User + referral_code, referred_by, referral_bonus_days
    subscription.py        — Subscription (tariff_type, access_url, end_date)
    payment.py             — Payment (YooKassa)
    telegram_payment.py    — TelegramPayment (Stars, Card)
    support.py             — SupportTicket, SupportMessage
  services/
    user_service.py        — CRUD пользователей + реферальная система
    subscription_service.py — Подписки: создание, проверка, деактивация
    payment_service.py     — YooKassa платежи
    telegram_payment_service.py — Stars/Card платежи через Telegram Payments API
    outline_service.py     — Outline VPN API: создание/удаление ключей, балансировка
    support_service.py     — Тикеты поддержки
  middleware/
    maintenance.py         — Middleware режима обслуживания
  vpn_forge/               — СИСТЕМА АВТОУПРАВЛЕНИЯ СЕРВЕРАМИ (см. ниже)
```

## VPN Forge — автономная система управления VPN-серверами

```
app/vpn_forge/
  __init__.py
  models.py          — VPNServer, ServerEvent, HealthCheck (SQLAlchemy)
  ssh_client.py      — Async SSH клиент (asyncssh): команды, метрики, файлы
  deployer.py        — Автоустановка Outline через SSH (Docker + install script)
  monitor.py         — Мониторинг: SSH, Docker, Outline API, CPU/RAM/Disk
  healer.py          — Самолечение: restart, cleanup disk/RAM, provider reboot
  ai_agent.py        — ИИ-диагностика: DeepSeek через OpenRouter
  orchestrator.py    — Автомасштабирование: scale up/down по загрузке
  manager.py         — Центральный менеджер: фоновые циклы, публичное API
  prompts/
    system_prompt.md — Системный промпт для DeepSeek (загружается из файла)
  providers/
    base.py          — Абстрактный интерфейс провайдера
    hetzner.py       — Hetzner Cloud API: create/delete/reboot серверов
```

### Как работает VPN Forge

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

### Админ-панель: `/forge`
- Статус флота (active/degraded/maintenance)
- Детали каждого сервера (CPU/RAM/Disk, ключи, события)
- AI-диагностика (dry-run или с выполнением)
- Ручной scale up / удаление / перезапуск Outline
- Добавление сервера: `/forge_add name ip [user] [port] [api_url]`
- Лог событий

## Docker Compose

Сервисы с уникальными именами чтобы не конфликтовать с другими проектами:
- `vpn_bot_db` (postgres:15-alpine) — порт **5435**:5432
- `vpn_bot_redis` (redis:7-alpine) — порт **6380**:6379
- `vpn_bot_app` — порт 8000 (FastAPI webhook)
- `vpn_bot_nginx` — порты **8080**:80, **8443**:443, **9000**:9000
- Сеть: `vpn_bot_network` (изолированная)
- Source code монтируется через volume (`.:/ app`) для hot-reload

## Ключевые .env переменные

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_ID=...
TELEGRAM_BOT_USERNAME=vpn_club_pro_bot
DATABASE_URL=postgresql+asyncpg://...
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
TELEGRAM_PAYMENT_PROVIDER_TOKEN=...
OUTLINE_API_URL=...   (или OUTLINE_SERVERS=url1,url2)

# VPN Forge
VPN_FORGE_ENABLED=true
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=deepseek/deepseek-chat
HETZNER_API_TOKEN=...
VPN_FORGE_MONITOR_INTERVAL=60
VPN_FORGE_MAX_SERVERS=10
VPN_FORGE_SCALE_UP_THRESHOLD=70
VPN_FORGE_SCALE_DOWN_THRESHOLD=30
```

## Оплата

3 способа оплаты:
1. **YooKassa** (рубли) — через payment_service.py, webhook на /webhook/yookassa
2. **Telegram Stars** — через telegram_payment_service.py, pre_checkout_query
3. **Банковская карта** (USD) — через Telegram Payments provider token

Поток: Тариф → Способ оплаты → Подтверждение → Invoice → pre_checkout → successful_payment → Создание подписки + Outline ключ

## Тарифы

| Тариф | Цена | Период |
|-------|------|--------|
| trial | 0₽ | 7 дней, 10 ГБ |
| monthly | 150₽ | 1 мес |
| quarterly | 350₽ | 3 мес |
| half_yearly | 650₽ | 6 мес |
| yearly | 1200₽ | 12 мес |

## Реферальная система

- Каждый пользователь получает уникальный `referral_code` при регистрации
- Ссылка: `https://t.me/{bot}?start=ref_{CODE}`
- Друг получает +7 дней, реферер получает +7 дней к подписке
- Уровни: Новичок → Активист → Амбассадор → Мастер → Легенда
- ⚠️ Реферальные тексты НЕ содержат упоминаний обхода блокировок (ФЗ «О рекламе»)

## Юридическое соответствие (ФЗ-149, ФЗ-152, ФЗ-38, ФЗ-281)

### Документы в боте
- `/terms` — Пользовательское соглашение (3 сообщения):
  - Запрет обхода блокировок РКН, обязанность сообщать о сбоях
  - Взаимодействие с Роскомнадзором, фильтрация, локализация ПД в РФ
  - Реферальная программа (запрет рекламы обхода — ФЗ-281), оплата, ответственность
- `/privacy` — Политика конфиденциальности (3 сообщения):
  - Оператор в Реестре РКН (ст. 22 ФЗ-152), перечень собираемых/несобираемых данных
  - Цели, правовые основания, локализация учётных данных в РФ (ст. 18 ФЗ-152)
  - Права пользователя (ст. 14), инцидент-менеджмент (уведомление РКН 24ч), передача 3-м лицам

### Двухэтапная регистрация (/start)
1. **Шаг 1:** Принятие условий использования → `terms_accepted`, `terms_accepted_at`
2. **Шаг 2:** Отдельное согласие на обработку ПД (ст. 9 ФЗ-152) → `pd_consent`, `pd_consent_at`
   - Содержит: оператор, цель, перечень данных, действия, срок, порядок отзыва

### Позиционирование
- Сервис = **защита данных и шифрование**, НЕ обход блокировок
- ОКВЭД: 62.09 (основной), 63.11 (дополнительный)
- Оплата: ЮKassa (ИП)

## Частые грабли (уже исправлено)

- `half_yearly` ломался при `split("_")` → используем `removeprefix("tariff_")`
- `scalar_one_or_none()` бросал MultipleResultsFound → заменён на `scalars().first()` + `limit(1)`
- `subscription.expires_at` не существует → правильно `subscription.end_date`
- `datetime.now()` без таймзоны → `datetime.now(pytz.UTC)` или `datetime.now(timezone.utc)`
- Обязателен `pre_checkout_query` handler для Telegram Payments
- `allowed_updates` должен содержать `pre_checkout_query`, НЕ `successful_payment`
- `declarative_base` импорт из `sqlalchemy.orm`, не `sqlalchemy.ext.declarative`

## Юридический статус: ✅ ГОТОВО К ЗАПУСКУ

Документы прошли итоговую юридическую экспертизу — **полное соответствие** всем нормативным актам:

| НПА | Статус |
|-----|--------|
| ФЗ-152-ФЗ (Персональные данные) | ✅ Полное |
| ФЗ-149-ФЗ (Информация и защита) | ✅ Полное |
| ФЗ-38-ФЗ (О рекламе) | ✅ Полное |
| ФЗ-281-ФЗ (Запрет популяризации обхода) | ✅ Полное |
| ФЗ-161-ФЗ (Платёжная система / ЮKassa) | ✅ Полное |
| КоАП РФ ст. 13.11 (Утечки) | ✅ Полное |

### Организационные задачи (вне кода):
1. Подготовить **шаблон акта уничтожения ПД** (дата, перечень данных, способ, ФИО ответственных)
2. Хранить акты уничтожения **3 года** (ст. 21 ФЗ-152)
3. Провести **технический аудит Outline/Shadowsocks** — подтвердить отсутствие логирования
4. **Периодически актуализировать** `/terms` и `/privacy` при изменении законодательства
5. Рекомендуется **консультация юриста по IT-праву** перед запуском

## Что ещё НЕ реализовано (TODO)

- Миграция ключей при scale down (сейчас удаляет только пустые серверы)
- DigitalOcean / Vultr провайдеры (только Hetzner)
- Уведомление рефереру когда друг активирует VPN
- Dashboard с графиками нагрузки серверов
- Автоматическое гео-распределение на основе локации пользователей
