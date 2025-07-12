#!/usr/bin/env python3
"""
Тестовый скрипт для проверки Stars платежа на сервере
"""

import asyncio
import os
from aiogram import Bot
from aiogram.types import LabeledPrice
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_stars_payment():
    """Тестируем отправку Stars invoice на сервере"""
    
    # Получаем админский ID
    admin_id = settings.admin_id
    
    # Создаем бота
    bot = Bot(token=settings.telegram_bot_token)
    
    try:
        print(f"🤖 Тестируем Stars платеж для админа: {admin_id}")
        print(f"🔑 Bot token: {settings.telegram_bot_token[:10]}...")
        print(f"💳 Provider token: '{settings.telegram_payment_provider_token}'")
        print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'local')}")
        
        # Отправляем Stars invoice
        payload = "test_stars_server_payment_123"
        
        await bot.send_invoice(
            chat_id=admin_id,
            title="VPN Club Pro - Тестовый Stars платеж",
            description="Тестовый платеж для проверки Stars на сервере",
            payload=payload,
            provider_token="",  # Пустой для Stars
            currency="XTR",
            prices=[LabeledPrice(label="Тест", amount=1)],  # 1 Star
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            send_phone_number_to_provider=False,
            send_email_to_provider=False,
            is_flexible=False,
            disable_notification=False,
            protect_content=False,
            reply_to_message_id=None,
            allow_sending_without_reply=True
        )
        
        print("✅ Stars invoice отправлен успешно!")
        print(f"📦 Payload: {payload}")
        print("🎯 Теперь попробуйте оплатить в Telegram и проверьте логи")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        logger.error(f"Error sending Stars invoice: {e}", exc_info=True)
        
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_stars_payment()) 