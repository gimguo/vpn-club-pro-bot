# 🔧 Настройка Blog Manager для @vpn_club_pro_blog

## ⚠️ Важно: Настройка прав бота

Чтобы Blog Manager мог управлять постами в канале, нужно настроить права бота.

### 📋 Пошаговая инструкция:

#### 1. Добавить бота в канал как администратора

1. Зайдите в канал @vpn_club_pro_blog
2. Нажмите на название канала → **"Управление каналом"**
3. Выберите **"Администраторы"**
4. Нажмите **"Добавить администратора"**
5. Найдите бота: **@vpn_club_pro_bot**
6. Добавьте бота в администраторы

#### 2. Настроить права бота

Дайте боту следующие права:
- ✅ **Отправка сообщений**
- ✅ **Редактирование сообщений**
- ✅ **Удаление сообщений** (опционально)
- ❌ Остальные права можно оставить выключенными

#### 3. Проверить работу

После настройки прав запустите тест:

```bash
# Из корня проекта
python -c "
import asyncio
from blog.channel_manager import TelegramChannelManager
from config import Settings

async def test():
    settings = Settings()
    manager = TelegramChannelManager(settings.telegram_bot_token, 'vpn_club_pro_blog')
    result = await manager.send_message('🧪 Тест системы управления блогом\n\nЭто тестовое сообщение от VPN Club Pro Bot Manager')
    if result:
        print(f'✅ Тест успешен! ID сообщения: {result[\"message_id\"]}')
    else:
        print('❌ Ошибка отправки. Проверьте права бота в канале')

asyncio.run(test())
"
```

## 🚀 Использование после настройки

### Запуск главного меню:
```bash
python blog/run_blog_manager.py
```

### Быстрая отправка постов:
```bash
python blog/channel_manager.py
```

### Редактирование постов:
```bash
python blog/post_editor.py
```

## 🔄 Рабочий процесс

1. **Отправляете пост** → получаете ID сообщения
2. **Сохраняете ID** в базу данных через редактор
3. **Редактируете пост** при необходимости

## 📝 Пример полного цикла

```bash
# 1. Отправить новый пост
python blog/channel_manager.py
# Выбираете пост → получаете ID (например, 123)

# 2. Сохранить ID для редактирования
python blog/post_editor.py
# Опция 6 → вводите тип поста и ID 123

# 3. Редактировать пост
python blog/post_editor.py  
# Выбираете нужный пост для редактирования
```

## ⚡ Быстрые команды

```bash
# Отправить приветственный пост
python -c "
import asyncio
from blog.channel_manager import TelegramChannelManager, BlogContentManager
from config import Settings

async def send_welcome():
    settings = Settings()
    manager = TelegramChannelManager(settings.telegram_bot_token, 'vpn_club_pro_blog')
    content = BlogContentManager()
    post = content.get_welcome_post()
    result = await manager.send_message(post.format_text())
    print(f'Пост отправлен! ID: {result[\"message_id\"]}')

asyncio.run(send_welcome())
"
```

## 🛠 Troubleshooting

### Ошибка 403
- Проверьте что бот добавлен как администратор
- Убедитесь что у бота есть права на отправку сообщений

### Ошибка 400
- Проверьте правильность @username канала
- Убедитесь что канал существует

### ModuleNotFoundError
- Запускайте скрипты из корня проекта
- Проверьте что файл config.py доступен 