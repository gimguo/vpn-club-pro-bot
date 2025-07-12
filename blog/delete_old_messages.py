#!/usr/bin/env python3
"""
Удаление старых сообщений из канала @vpn_club_pro_blog
"""

import asyncio
import sys
import os
import aiohttp

# Добавляем корневую папку проекта в Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blog.channel_manager import TelegramChannelManager
from config import Settings

async def delete_old_messages():
    """Удаляет старые сообщения из канала"""
    settings = Settings()
    manager = TelegramChannelManager(settings.telegram_bot_token, 'vpn_club_pro_blog')
    
    print("🗑️  Удаление старых сообщений из канала @vpn_club_pro_blog")
    print("=" * 60)
    
    # Удаляем старые посты ID 16-22, новые посты начинаются с ID 23
    old_message_ids = list(range(16, 23))  # ID 16, 17, 18, 19, 20, 21, 22
    
    deleted_count = 0
    errors_count = 0
    
    print(f"🔍 Попытка удалить сообщения с ID: {old_message_ids}")
    
    async with aiohttp.ClientSession() as session:
        for message_id in old_message_ids:
            print(f"\n🗑️  Удаляем сообщение ID {message_id}...")
            
            try:
                delete_url = f"{manager.api_url}/deleteMessage"
                delete_data = {
                    "chat_id": f"@{manager.channel_username}",
                    "message_id": message_id
                }
                
                async with session.post(delete_url, json=delete_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("ok"):
                            print(f"   ✅ Сообщение ID {message_id} удалено")
                            deleted_count += 1
                        else:
                            print(f"   ⚠️  Сообщение ID {message_id} не найдено или уже удалено")
                            errors_count += 1
                    else:
                        print(f"   ❌ Ошибка удаления сообщения ID {message_id}: HTTP {response.status}")
                        errors_count += 1
                
                # Небольшая пауза между удалениями
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ Ошибка при удалении сообщения ID {message_id}: {e}")
                errors_count += 1
    
    print(f"\n📊 Результаты удаления:")
    print(f"   ✅ Удалено сообщений: {deleted_count}")
    print(f"   ⚠️  Ошибок/не найдено: {errors_count}")
    
    if deleted_count > 0:
        print(f"\n🎉 Старые сообщения успешно удалены!")
        print(f"📱 Теперь в канале @vpn_club_pro_blog только новые посты с правильными ссылками:")
        
        # Показываем какие посты остались
        remaining_posts = [
            "ID 23: Приветственный пост (финальная версия)",
            "ID 24: Инструкция для мобильных (с прямыми ссылками)",
            "ID 25: Инструкция для компьютеров (с прямыми ссылками)", 
            "ID 26: Пост об обновлениях (финальная версия)",
            "ID 27: Пост о тарифах (финальная версия)",
            "ID 28: Пост о безопасности (финальная версия)"
        ]
        
        for post in remaining_posts:
            print(f"   • {post}")
    
    return deleted_count > 0

async def main():
    """Главная функция"""
    try:
        success = await delete_old_messages()
        if success:
            print(f"\n🚀 Канал очищен от старых сообщений!")
        else:
            print(f"\n💡 Нет старых сообщений для удаления.")
    except KeyboardInterrupt:
        print("\n👋 Операция прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 