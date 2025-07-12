#!/usr/bin/env python3
"""
Скрипт для тестирования настроек платежного провайдера
"""

import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import LabeledPrice

# Загружаем переменные окружения
load_dotenv()

async def test_payment_provider():
    """Тестирование подключения к платежному провайдеру"""
    
    # Получаем токены из переменных окружения
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    payment_provider_token = os.getenv("TELEGRAM_PAYMENT_PROVIDER_TOKEN")
    admin_id = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN не найден в .env файле")
        return
    
    if not admin_id:
        print("❌ TELEGRAM_ADMIN_ID не найден в .env файле")
        return
    
    bot = Bot(token=bot_token)
    
    try:
        print("🔍 Проверка подключения к боту...")
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username}")
        
        print("\n🔍 Проверка настроек платежей...")
        
        # Проверяем Telegram Stars
        print("\n--- Telegram Stars ---")
        try:
            await bot.send_invoice(
                chat_id=admin_id,
                title="Test Stars Payment",
                description="Тестовый платеж через Telegram Stars",
                payload="test_stars_payment",
                provider_token="",  # Пустой для Stars
                currency="XTR",
                prices=[LabeledPrice(label="Тест", amount=1)]
            )
            print("✅ Telegram Stars: Настроены корректно")
        except Exception as e:
            print(f"❌ Telegram Stars: Ошибка - {e}")
        
        # Проверяем банковские карты (если есть токен)
        if payment_provider_token:
            print("\n--- Банковские карты ---")
            try:
                await bot.send_invoice(
                    chat_id=admin_id,
                    title="Test Card Payment",
                    description="Тестовый платеж банковской картой",
                    payload="test_card_payment",
                    provider_token=payment_provider_token,
                    currency="RUB",
                    prices=[LabeledPrice(label="Тест", amount=10000)]  # 100 рублей
                )
                print("✅ Банковские карты: Настроены корректно")
            except Exception as e:
                print(f"❌ Банковские карты: Ошибка - {e}")
        else:
            print("\n--- Банковские карты ---")
            print("⚠️  TELEGRAM_PAYMENT_PROVIDER_TOKEN не задан")
            print("   Банковские карты не будут работать")
        
    except Exception as e:
        print(f"❌ Ошибка подключения к боту: {e}")
    
    finally:
        await bot.session.close()

if __name__ == "__main__":
    print("🧪 Тестирование настроек платежного провайдера")
    print("=" * 50)
    asyncio.run(test_payment_provider()) 