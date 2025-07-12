#!/usr/bin/env python3
"""
Тест прав бота в канале @vpn_club_pro_blog
"""

import asyncio
import sys
import os

# Добавляем корневую папку проекта в Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blog.channel_manager import TelegramChannelManager
from config import Settings

async def test_permissions():
    """Тестирует права бота в канале"""
    print("🔍 Тестирование прав бота @vpn_club_pro_bot в канале @vpn_club_pro_blog")
    print("=" * 70)
    
    settings = Settings()
    manager = TelegramChannelManager(settings.telegram_bot_token, 'vpn_club_pro_blog')
    
    # Тест 1: Отправка сообщения
    print("\n1️⃣ Тест отправки сообщения...")
    test_message = "🧪 Тест прав бота\n\n✅ Если вы видите это сообщение, права на отправку работают!"
    
    result = await manager.send_message(test_message)
    
    if result:
        message_id = result["message_id"]
        print(f"   ✅ Успешно! ID сообщения: {message_id}")
        
        # Тест 2: Редактирование сообщения
        print("\n2️⃣ Тест редактирования сообщения...")
        
        edited_message = "🧪 Тест прав бота (ОТРЕДАКТИРОВАНО)\n\n✅ Отправка работает!\n✅ Редактирование работает!\n\n🎉 Все права настроены корректно!"
        
        edit_result = await manager.edit_message(message_id, edited_message)
        
        if edit_result:
            print(f"   ✅ Редактирование работает!")
            print(f"\n🎉 ВСЕ ПРАВА РАБОТАЮТ КОРРЕКТНО!")
            print(f"\n💡 Теперь вы можете запустить автоматическое обновление канала:")
            print(f"   python blog/auto_update_channel.py")
            return True
        else:
            print(f"   ❌ Ошибка редактирования")
            print(f"\n📋 Настройте права бота:")
            print(f"   • Отправка сообщений: ✅ работает")
            print(f"   • Редактирование сообщений: ❌ не работает")
            return False
    else:
        print(f"   ❌ Ошибка отправки")
        print(f"\n📋 Бот не добавлен как администратор или нет прав на отправку сообщений")
        print(f"\n🔧 Что нужно сделать:")
        print(f"   1. Зайдите в канал @vpn_club_pro_blog")
        print(f"   2. Нажмите на название канала → 'Управление каналом'")
        print(f"   3. Выберите 'Администраторы' → 'Добавить администратора'")
        print(f"   4. Найдите и добавьте: @vpn_club_pro_bot")
        print(f"   5. Дайте права: 'Отправка сообщений' + 'Редактирование сообщений'")
        print(f"   6. Запустите этот тест заново")
        return False

async def main():
    """Главная функция"""
    try:
        success = await test_permissions()
        if success:
            print(f"\n🚀 Готово к работе! Канал можно обновлять.")
        else:
            print(f"\n❌ Настройте права бота и повторите тест.")
    except KeyboardInterrupt:
        print("\n👋 Тест прерван пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 