# VPN Club Pro Blog Manager

Модуль для автоматического управления постами в Telegram канале @vpn_club_pro_blog.

## 🚀 Возможности

- ✅ Создание и отправка новых постов
- ✅ Редактирование существующих постов  
- ✅ Готовые шаблоны постов (приветствие, инструкции, тарифы, безопасность)
- ✅ База данных ID постов для редактирования
- ✅ Интерактивное меню

## 📁 Структура

```
blog/
├── __init__.py              # Инициализация модуля
├── channel_manager.py       # Основной менеджер канала
├── post_editor.py          # Редактор существующих постов
├── run_blog_manager.py     # Главный запускаемый скрипт
├── posts_db.json          # База данных ID постов
└── README.md              # Документация
```

## 🔧 Использование

### Быстрый запуск
```bash
# Из корня проекта
python blog/run_blog_manager.py
```

### Создание новых постов
```bash
python blog/channel_manager.py
```

### Редактирование постов
```bash
python blog/post_editor.py
```

## 📝 Готовые шаблоны постов

1. **Приветственный пост** - Добро пожаловать в блог
2. **Инструкция для мобильных** - iOS/Android настройка
3. **Инструкция для компьютеров** - Windows/macOS настройка
4. **Обновления сервиса** - Новости и планы развития
5. **Тарифы** - Цены и подписки
6. **Безопасность** - О защите и приватности

## 🔑 Требования

- Бот должен быть администратором канала @vpn_club_pro_blog
- В .env файле должен быть указан TELEGRAM_BOT_TOKEN
- Установленная зависимость: `aiohttp`

## 💡 Как работает

1. **TelegramChannelManager** - отправляет новые посты через Bot API
2. **BlogContentManager** - содержит готовые шаблоны постов
3. **PostEditor** - редактирует существующие посты по ID
4. **posts_db.json** - хранит ID отправленных постов

## 📋 Пример использования

```python
from blog.channel_manager import TelegramChannelManager, BlogContentManager
from config import Settings

settings = Settings()

# Инициализация
manager = TelegramChannelManager(
    bot_token=settings.telegram_bot_token,
    channel_username="vpn_club_pro_blog"
)

content = BlogContentManager()

# Отправка поста
post = content.get_welcome_post()
result = await manager.send_message(post.format_text())
print(f"Пост отправлен! ID: {result['message_id']}")
```

## 🔄 Рабочий процесс

1. **Отправляем новый пост** через `channel_manager.py`
2. **Сохраняем ID поста** в `posts_db.json`
3. **Редактируем при необходимости** через `post_editor.py`

## ⚠️ Важно

- Сохраняйте ID отправленных постов для последующего редактирования
- Проверьте права бота в канале перед использованием
- Используйте HTML разметку в постах 