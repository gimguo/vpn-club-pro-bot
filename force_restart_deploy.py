#!/usr/bin/env python3
"""
Принудительный перезапуск бота на сервере
"""
import asyncio
import sys
import os
import time

# Добавляем корневую папку в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot
from aiogram.types import LabeledPrice
from config import settings

async def force_restart_check():
    """Проверка и принудительный перезапуск"""
    
    bot = Bot(token=settings.telegram_bot_token)
    
    try:
        print('🔄 ПРИНУДИТЕЛЬНАЯ ПРОВЕРКА БОТА')
        
        # Получаем информацию о боте
        me = await bot.get_me()
        print(f'🤖 Бот: {me.username} (ID: {me.id})')
        
        # Получаем информацию о webhook
        webhook_info = await bot.get_webhook_info()
        print(f'📡 Webhook URL: {webhook_info.url}')
        print(f'🏷️ Allowed updates: {webhook_info.allowed_updates}')
        
        # Принудительно удаляем webhook
        print('🗑️ Удаляю webhook...')
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Ждем немного
        await asyncio.sleep(2)
        
        # Проверяем еще раз
        webhook_info = await bot.get_webhook_info()
        print(f'📡 Webhook URL после удаления: {webhook_info.url}')
        print(f'🏷️ Allowed updates после удаления: {webhook_info.allowed_updates}')
        
        # Отправляем тестовое сообщение админу
        await bot.send_message(
            chat_id=settings.admin_id,
            text='🔄 Бот перезапущен! Проверяю работу Stars payments...'
        )
        
        # Отправляем новый Stars invoice
        print('📤 Отправляю новый Stars invoice...')
        await bot.send_invoice(
            chat_id=settings.admin_id,
            title='🔄 ПОСЛЕ ПЕРЕЗАПУСКА',
            description='Тест Stars payment после принудительного перезапуска',
            payload='after_restart_test',
            provider_token='',
            currency='XTR',
            prices=[LabeledPrice(label='Restart Test', amount=50)],
            start_parameter='restart_test'
        )
        
        print('✅ Новый invoice отправлен!')
        print('💡 Попробуйте оплатить его сейчас')
        
    except Exception as e:
        print(f'❌ Ошибка: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(force_restart_check()) 