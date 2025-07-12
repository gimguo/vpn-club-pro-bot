#!/usr/bin/env python3
import asyncio
import sys
import os

# Добавляем корневую папку в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import LabeledPrice, Message
from config import settings

async def test_local_stars():
    print('🧪 ЛОКАЛЬНЫЙ ТЕСТ SUCCESSFUL_PAYMENT')
    
    # Создаем бота
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаем диспетчер
    dp = Dispatcher()
    
    # Обработчик successful_payment
    @dp.message()
    async def handle_message(message: Message):
        if message.successful_payment:
            print(f'🎉 [LOCAL] Получен successful_payment!')
            print(f'💰 Amount: {message.successful_payment.total_amount}')
            print(f'💱 Currency: {message.successful_payment.currency}')
            print(f'📦 Payload: {message.successful_payment.invoice_payload}')
            print(f'🏷️ Telegram charge ID: {message.successful_payment.telegram_payment_charge_id}')
            await message.reply('✅ Локальный тест - оплата получена!')
        elif message.text:
            print(f'📨 Текст: {message.text}')
    
    try:
        # Отправляем invoice
        print(f'📤 Отправляю invoice админу {settings.admin_id}...')
        await bot.send_invoice(
            chat_id=settings.admin_id,
            title='🧪 ЛОКАЛЬНЫЙ ТЕСТ - Stars Payment',
            description='Тест для проверки successful_payment обработчика',
            payload='local_test_stars_payment',
            provider_token='',
            currency='XTR',
            prices=[LabeledPrice(label='Local Test', amount=50)],
            start_parameter='local_test_stars'
        )
        print('✅ Invoice отправлен!')
        print('💡 Оплатите его в боте, затем Ctrl+C для завершения')
        
        # Запускаем polling с правильными allowed_updates
        print('🔄 Запускаю polling с allowed_updates: message, callback_query, successful_payment')
        await dp.start_polling(bot, allowed_updates=['message', 'callback_query', 'successful_payment'])
        
    except KeyboardInterrupt:
        print('\n⏹️ Локальный тест остановлен')
    except Exception as e:
        print(f'❌ Ошибка: {e}')
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(test_local_stars()) 