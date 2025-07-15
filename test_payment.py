#!/usr/bin/env python3
"""
💳 Тест оплаты для YooKassa
"""

import asyncio
import sys
import os

# Добавляем корневую папку в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.payment_service import PaymentService
from app.services.user_service import UserService
from app.database import AsyncSessionLocal
from config import settings
from decimal import Decimal

async def test_payment():
    """Тестируем создание платежа"""
    
    print('💳 ТЕСТ СОЗДАНИЯ ПЛАТЕЖА')
    print('=' * 50)
    
    async with AsyncSessionLocal() as session:
        try:
            # Создаем сервисы
            payment_service = PaymentService(session)
            user_service = UserService(session)
            
            # Получаем или создаем пользователя
            user = await user_service.get_or_create_user(
                telegram_id=settings.admin_id,
                username="admin",
                first_name="Admin",
                last_name="User"
            )
            
            print(f'👤 Пользователь: {user.first_name} (ID: {user.id})')
            
            # Создаем тестовый платеж
            print('\n💰 Создаю тестовый платеж...')
            payment = await payment_service.create_payment(
                user_id=user.id,
                amount=Decimal("150.00"),
                tariff_type="monthly",
                return_url=f"https://t.me/{settings.bot_username}"
            )
            
            print(f'✅ Платеж создан успешно!')
            print(f'🆔 Payment ID: {payment.yookassa_payment_id}')
            print(f'💵 Сумма: {payment.amount} {payment.currency}')
            print(f'📋 Тариф: {payment.tariff_type}')
            print(f'🔗 URL оплаты: {payment.payment_url}')
            
            # Инструкции
            print('\n📝 ИНСТРУКЦИИ ДЛЯ ТЕСТИРОВАНИЯ:')
            print('1. Перейдите по URL оплаты выше')
            print('2. Выполните тестовую оплату')
            print('3. Проверьте логи webhook на сервере')
            print('4. Проверьте создание подписки')
            
            # Проверка webhook URL
            print(f'\n🔗 Webhook URL: https://vm16784.hosted-by.it-garage.pro/webhook/yookassa')
            print(f'📋 События: payment.succeeded, payment.canceled')
            
        except Exception as e:
            print(f'❌ Ошибка: {e}')
            import traceback
            print(f'📋 Детали: {traceback.format_exc()}')

if __name__ == '__main__':
    asyncio.run(test_payment()) 