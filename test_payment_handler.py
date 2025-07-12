#!/usr/bin/env python3
"""
Тестовый скрипт для проверки обработчика successful_payment
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock
from app.services.telegram_payment_service import TelegramPaymentService
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.database import AsyncSessionLocal
from app.models import TelegramPayment, User
from sqlalchemy import select
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_successful_payment_handler():
    """Тестируем обработчик successful_payment"""
    
    # Создаем mock объекты
    bot_mock = AsyncMock()
    message_mock = MagicMock()
    
    # Создаем данные для тестирования
    import time
    test_payload = f"stars_payment_1_monthly_test_{int(time.time())}"
    
    # Создаем mock для successful_payment
    successful_payment_mock = MagicMock()
    successful_payment_mock.telegram_payment_charge_id = "test_charge_123"
    successful_payment_mock.provider_payment_charge_id = None
    successful_payment_mock.invoice_payload = test_payload
    successful_payment_mock.currency = "XTR"
    successful_payment_mock.total_amount = 50
    
    message_mock.successful_payment = successful_payment_mock
    message_mock.from_user.id = 7909062876  # Админский ID
    message_mock.bot = bot_mock
    message_mock.reply = AsyncMock()
    
    print("🧪 Тестируем обработчик successful_payment...")
    print(f"📦 Payload: {test_payload}")
    print(f"👤 User ID: {message_mock.from_user.id}")
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        telegram_payment_service = TelegramPaymentService(session, bot_mock)
        subscription_service = SubscriptionService(session)
        
        # Создаем или получаем пользователя
        user = await user_service.get_or_create_user(
            telegram_id=7909062876,
            username="admin",
            first_name="Admin",
            last_name="Test"
        )
        
        print(f"👤 Пользователь найден: ID {user.id}")
        
        # Создаем тестовый платеж
        test_payment = TelegramPayment(
            user_id=user.id,
            telegram_payment_charge_id=test_payload,
            amount=50.00,
            currency="XTR",
            tariff_type="monthly",
            payment_type="stars",
            telegram_user_id=str(user.id),
            invoice_payload=test_payload,
            status="pending"
        )
        
        session.add(test_payment)
        await session.commit()
        await session.refresh(test_payment)
        
        print(f"💰 Тестовый платеж создан: ID {test_payment.id}, статус: {test_payment.status}")
        
        # Обрабатываем успешный платеж
        successful_payment_data = {
            "telegram_payment_charge_id": successful_payment_mock.telegram_payment_charge_id,
            "provider_payment_charge_id": successful_payment_mock.provider_payment_charge_id,
            "invoice_payload": successful_payment_mock.invoice_payload,
            "currency": successful_payment_mock.currency,
            "total_amount": successful_payment_mock.total_amount
        }
        
        print("🔍 Тестируем process_successful_payment...")
        payment = await telegram_payment_service.process_successful_payment(successful_payment_data)
        
        if payment:
            print(f"✅ Платеж обработан успешно: ID {payment.id}, статус: {payment.status}")
            
            # Создаем подписку
            subscription = await subscription_service.create_subscription(
                user.id, 
                payment.tariff_type
            )
            
            print(f"📋 Подписка создана: ID {subscription.id}, активна до: {subscription.end_date}")
            
            print("🎉 Тест успешен!")
            
        else:
            print("❌ Не удалось обработать платеж")
            
        # Проверяем статус платежа в базе
        updated_payment = await session.get(TelegramPayment, test_payment.id)
        print(f"🔍 Финальный статус платежа: {updated_payment.status}")
        
        # Удаляем тестовый платеж
        await session.delete(test_payment)
        await session.commit()
        print("🧹 Тестовый платеж удален")

async def check_existing_payments():
    """Проверяем существующие платежи в базе данных"""
    print("\n🔍 Проверяем существующие платежи...")
    
    async with AsyncSessionLocal() as session:
        # Получаем все платежи
        result = await session.execute(select(TelegramPayment))
        payments = result.scalars().all()
        
        print(f"📊 Найдено платежей: {len(payments)}")
        
        for payment in payments:
            print(f"💰 Платеж {payment.id}: payload={payment.invoice_payload}, статус={payment.status}")
            
            # Попробуем обработать pending платежи
            if payment.status == "pending":
                print(f"🔄 Пытаемся обработать pending платеж {payment.id}...")
                
                # Создаем fake successful_payment_data
                successful_payment_data = {
                    "telegram_payment_charge_id": f"fake_charge_{payment.id}",
                    "provider_payment_charge_id": None,
                    "invoice_payload": payment.invoice_payload,
                    "currency": payment.currency,
                    "total_amount": int(payment.amount)
                }
                
                telegram_payment_service = TelegramPaymentService(session, AsyncMock())
                processed_payment = await telegram_payment_service.process_successful_payment(successful_payment_data)
                
                if processed_payment:
                    print(f"✅ Платеж {payment.id} обработан, новый статус: {processed_payment.status}")
                else:
                    print(f"❌ Не удалось обработать платеж {payment.id}")

if __name__ == "__main__":
    print("🧪 Запуск тестирования обработчика платежей...")
    asyncio.run(test_successful_payment_handler())
    asyncio.run(check_existing_payments()) 