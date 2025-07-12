#!/usr/bin/env python3
"""
Скрипт для создания таблицы telegram_payments в SQLite
"""

import asyncio
from app.database import engine
from app.models.telegram_payment import TelegramPayment
from app.models.base import Base

async def create_telegram_payments_table():
    """Создание таблицы telegram_payments"""
    
    print("🔧 Создание таблицы telegram_payments...")
    
    try:
        # Создаем таблицу
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        print("✅ Таблица telegram_payments создана успешно!")
        
        # Проверяем, что таблица создана
        from app.database import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='telegram_payments'"))
            table_exists = result.fetchone()
            
            if table_exists:
                print("✅ Таблица telegram_payments найдена в базе данных")
            else:
                print("❌ Таблица telegram_payments НЕ найдена в базе данных")
            
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при создании таблицы: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(create_telegram_payments_table()) 