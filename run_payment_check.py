#!/usr/bin/env python3
"""
Скрипт для проверки и обновления статусов pending платежей
"""
import asyncio
import logging
from app.services.payment_checker import PaymentChecker

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Запуск проверки платежей"""
    print("🔄 Запуск проверки pending платежей...")
    print("=" * 50)
    
    try:
        await PaymentChecker.check_pending_payments()
        print("✅ Проверка платежей завершена!")
    except Exception as e:
        print(f"❌ Ошибка при проверке платежей: {e}")
        logging.error(f"Error in payment check: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 