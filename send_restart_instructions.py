#!/usr/bin/env python3
import asyncio
import sys
import os

# Добавляем корневую папку в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot
from config import settings

async def send_restart_instructions():
    print('🚨 ОТПРАВЛЯЮ СРОЧНЫЕ ИНСТРУКЦИИ АДМИНУ')
    
    bot = Bot(token=settings.telegram_bot_token)
    
    try:
        # Отправляем подробные инструкции
        message1 = "🚨 КРИТИЧНО: Stars payments НЕ РАБОТАЮТ\n\n❌ Проблема: successful_payment события не обрабатываются\n✅ Решение: Код исправлен, нужен перезапуск Docker\n\n🔧 СРОЧНО выполните на сервере:"
        
        message2 = "📋 КОМАНДЫ ДЛЯ СЕРВЕРА:\n\nssh deployer@5.129.196.245\ncd /home/deployer/vpn-club-pro-telegram-bot\ndocker compose down\ngit pull origin master\ndocker compose up --build -d\n\nПосле этого Stars payments заработают!"
        
        await bot.send_message(chat_id=settings.admin_id, text=message1)
        await bot.send_message(chat_id=settings.admin_id, text=message2)
        
        # Отправляем текущий статус
        webhook_info = await bot.get_webhook_info()
        has_successful_payment = 'successful_payment' in (webhook_info.allowed_updates or [])
        
        status_msg = f"📊 ТЕКУЩИЙ СТАТУС (ПРОБЛЕМА):\n🏷️ Allowed updates: {webhook_info.allowed_updates}\n❌ successful_payment: {has_successful_payment}\n\nПосле перезапуска должно быть:\n✅ ['message', 'callback_query', 'successful_payment']"
        
        await bot.send_message(chat_id=settings.admin_id, text=status_msg)
        
        print('✅ Срочные инструкции отправлены')
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(send_restart_instructions()) 