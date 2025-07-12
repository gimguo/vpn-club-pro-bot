#!/usr/bin/env python3
"""
Автоматическое обновление постов в канале @vpn_club_pro_blog
"""

import asyncio
import sys
import os

# Добавляем корневую папку проекта в Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blog.channel_manager import TelegramChannelManager, BlogContentManager
from config import Settings

async def update_all_posts():
    """Автоматически обновляет все посты в канале"""
    settings = Settings()
    manager = TelegramChannelManager(settings.telegram_bot_token, 'vpn_club_pro_blog')
    content = BlogContentManager()
    
    print("🚀 Автоматическое обновление канала @vpn_club_pro_blog")
    print("=" * 60)
    
    # Сначала проверим права
    print("🔍 Проверка прав бота...")
    test_result = await manager.send_message("🧪 Тест прав бота - это сообщение будет удалено")
    
    if not test_result:
        print("❌ Ошибка: Бот не имеет прав в канале!")
        print("\n📋 Что нужно сделать:")
        print("1. Добавьте @vpn_club_pro_bot как администратора канала")
        print("2. Дайте права: 'Отправка сообщений' + 'Редактирование сообщений'")
        print("3. Запустите скрипт заново")
        return False
    
    print(f"✅ Права бота работают! Удаляем тестовое сообщение...")
    
    # Удаляем тестовое сообщение
    delete_url = f"{manager.api_url}/deleteMessage"
    delete_data = {
        "chat_id": f"@{manager.channel_username}",
        "message_id": test_result["message_id"]
    }
    
    import aiohttp
    async with aiohttp.ClientSession() as session:
        await session.post(delete_url, json=delete_data)
    
    print("\n📝 Начинаем обновление постов...")
    
    # Список постов для отправки/обновления
    posts_to_send = [
        ("welcome", content.get_welcome_post(), "Приветственный пост"),
        ("mobile_instruction", content.get_mobile_instruction(), "Инструкция для мобильных"),
        ("desktop_instruction", content.get_desktop_instruction(), "Инструкция для компьютеров"),
        ("updates", content.get_updates_post(), "Пост об обновлениях"),
        ("pricing", content.get_pricing_post(), "Пост о тарифах"),
        ("security", content.get_security_post(), "Пост о безопасности")
    ]
    
    sent_posts = []
    
    for post_type, post_content, description in posts_to_send:
        print(f"\n📤 Отправляем: {description}")
        try:
            result = await manager.send_message(post_content.format_text())
            if result:
                message_id = result["message_id"]
                sent_posts.append((post_type, message_id, description))
                print(f"   ✅ Успешно! ID: {message_id}")
                
                # Небольшая пауза между отправками
                await asyncio.sleep(1)
            else:
                print(f"   ❌ Ошибка отправки")
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    # Сохраняем ID постов в базу данных
    if sent_posts:
        print(f"\n💾 Сохраняем ID постов в базу данных...")
        
        posts_db_content = {
            "_info": "Database of blog posts with their message IDs",
            "_channel": "@vpn_club_pro_blog",
            "_updated": "2025-06-28",
            "_auto_updated": True
        }
        
        for post_type, message_id, description in sent_posts:
            posts_db_content[post_type] = message_id
        
        import json
        with open("blog/posts_db.json", "w", encoding="utf-8") as f:
            json.dump(posts_db_content, f, ensure_ascii=False, indent=2)
        
        print("✅ ID постов сохранены!")
        
        print(f"\n📋 Отправлено постов: {len(sent_posts)}")
        for post_type, message_id, description in sent_posts:
            print(f"   • {description}: ID {message_id}")
    
    print("\n🎉 Автоматическое обновление канала завершено!")
    print("\n💡 Теперь вы можете редактировать любой пост командой:")
    print("   python blog/post_editor.py")
    
    return True

async def main():
    """Главная функция"""
    try:
        success = await update_all_posts()
        if success:
            print("\n🚀 Канал @vpn_club_pro_blog успешно обновлен!")
        else:
            print("\n❌ Не удалось обновить канал. Проверьте права бота.")
    except KeyboardInterrupt:
        print("\n👋 Операция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 