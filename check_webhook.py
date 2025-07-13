#!/usr/bin/env python3
import asyncio
import os
import sys
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

load_dotenv()

async def main():
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не найден!")
        sys.exit(1)
    
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    try:
        # Проверяем webhook
        webhook_info = await bot.get_webhook_info()
        print(f"📡 Webhook URL: {webhook_info.url or 'NOT SET'}")
        print(f"🏷️ Allowed updates: {webhook_info.allowed_updates or []}")
        print(f"🔢 Pending updates: {webhook_info.pending_update_count}")
        
        if webhook_info.url:
            print("⚠️ WEBHOOK АКТИВЕН! Это может конфликтовать с polling!")
            
            # Удаляем webhook
            result = await bot.delete_webhook(drop_pending_updates=True)
            print(f"🗑️ Webhook удален: {result}")
            
            # Проверяем еще раз
            webhook_info = await bot.get_webhook_info()
            print(f"✅ Webhook после удаления: {webhook_info.url or 'NOT SET'}")
        else:
            print("✅ Webhook не установлен")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 