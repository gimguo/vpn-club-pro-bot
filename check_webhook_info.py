#!/usr/bin/env python3
"""
Скрипт для проверки настроек webhook бота
"""

import asyncio
from aiogram import Bot
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_webhook_info():
    """Проверяем настройки webhook бота"""
    
    bot = Bot(token=settings.telegram_bot_token)
    
    try:
        # Получаем информацию о webhook
        webhook_info = await bot.get_webhook_info()
        
        print("🔍 ИНФОРМАЦИЯ О WEBHOOK:")
        print(f"📡 URL: {webhook_info.url}")
        print(f"✅ Has custom certificate: {webhook_info.has_custom_certificate}")
        print(f"📊 Pending update count: {webhook_info.pending_update_count}")
        print(f"🔢 Max connections: {webhook_info.max_connections}")
        print(f"🏷️ Allowed updates: {webhook_info.allowed_updates}")
        print(f"🌐 IP address: {webhook_info.ip_address}")
        print(f"📅 Last error date: {webhook_info.last_error_date}")
        print(f"❌ Last error message: {webhook_info.last_error_message}")
        print(f"🔄 Last synchronization error date: {webhook_info.last_synchronization_error_date}")
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        print(f"\n🤖 ИНФОРМАЦИЯ О БОТЕ:")
        print(f"📛 Username: @{bot_info.username}")
        print(f"🆔 ID: {bot_info.id}")
        print(f"👤 Name: {bot_info.first_name}")
        print(f"💳 Can join groups: {bot_info.can_join_groups}")
        print(f"🔒 Can read all group messages: {bot_info.can_read_all_group_messages}")
        print(f"🎯 Supports inline queries: {bot_info.supports_inline_queries}")
        
        # Проверяем настройки платежей
        try:
            # Пытаемся отправить тестовый invoice для проверки настроек
            print(f"\n💳 ПРОВЕРКА НАСТРОЕК ПЛАТЕЖЕЙ:")
            print(f"💰 Provider token: '{settings.telegram_payment_provider_token}'")
            print(f"🔑 Admin ID: {settings.admin_id}")
            
            # Если webhook не установлен, бот работает в polling режиме
            if not webhook_info.url:
                print("\n⚠️  ВНИМАНИЕ: Webhook не установлен - бот работает в polling режиме")
                print("📡 Для production рекомендуется использовать webhook")
            else:
                print(f"\n✅ Webhook настроен: {webhook_info.url}")
                
        except Exception as e:
            print(f"❌ Ошибка при проверке настроек платежей: {e}")
        
    except Exception as e:
        print(f"❌ Ошибка при получении информации о боте: {e}")
        logger.error(f"Error getting bot info: {e}", exc_info=True)
        
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_webhook_info()) 