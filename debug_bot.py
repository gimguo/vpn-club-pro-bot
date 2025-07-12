#!/usr/bin/env python3
"""
Скрипт для диагностики проблем с ботом
"""
import asyncio
from config import settings
from aiogram import Bot
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_bot_connection():
    """Тестирование подключения к боту"""
    try:
        print("🤖 Тестирование подключения к боту...")
        print(f"🔑 Токен: {settings.telegram_bot_token[:10]}...")
        
        bot = Bot(token=settings.telegram_bot_token)
        
        # Проверяем информацию о боте
        me = await bot.get_me()
        print(f"✅ Бот подключен: @{me.username}")
        print(f"👤 Имя: {me.first_name}")
        print(f"🆔 ID: {me.id}")
        
        # Проверяем webhook
        webhook_info = await bot.get_webhook_info()
        print(f"🔗 Webhook URL: {webhook_info.url or 'Не установлен'}")
        print(f"📊 Pending updates: {webhook_info.pending_update_count}")
        
        if webhook_info.last_error_date:
            print(f"❌ Последняя ошибка webhook: {webhook_info.last_error_message}")
        
        # Отправляем тестовое сообщение админу
        try:
            admin_id = settings.admin_id
            if admin_id:
                await bot.send_message(
                    chat_id=admin_id,
                    text="🔧 <b>Диагностика бота</b>\n\n✅ Бот запущен и работает корректно!",
                    parse_mode="HTML"
                )
                print(f"✅ Тестовое сообщение отправлено админу: {admin_id}")
            else:
                print("⚠️  ADMIN_ID не задан")
        except Exception as e:
            print(f"❌ Не удалось отправить сообщение админу: {e}")
        
        await bot.session.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к боту: {e}")
        return False

async def test_database():
    """Тестирование подключения к базе данных"""
    try:
        print("\n🗄️ Тестирование подключения к базе данных...")
        print(f"🔗 URL: {settings.database_url}")
        
        from app.database import AsyncSessionLocal
        from app.models import User
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as session:
            # Проверяем подключение
            result = await session.execute(text("SELECT 1"))
            print("✅ Подключение к БД работает")
            
            # Проверяем таблицы
            result = await session.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"📋 Таблицы в БД: {', '.join(tables)}")
            
            # Проверяем наличие telegram_payments
            if 'telegram_payments' in tables:
                print("✅ Таблица telegram_payments найдена")
            else:
                print("❌ Таблица telegram_payments НЕ найдена!")
            
            # Проверяем количество пользователей
            result = await session.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"👥 Пользователей в БД: {user_count}")
            
        return True
        
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return False

def check_environment():
    """Проверка переменных окружения"""
    print("\n🔧 Проверка переменных окружения...")
    
    required_vars = [
        ("TELEGRAM_BOT_TOKEN", settings.telegram_bot_token),
        ("DATABASE_URL", settings.database_url),
        ("ADMIN_ID", settings.admin_id),
    ]
    
    optional_vars = [
        ("YOOKASSA_SHOP_ID", settings.yookassa_shop_id),
        ("YOOKASSA_SECRET_KEY", settings.yookassa_secret_key),
        ("TELEGRAM_PAYMENT_PROVIDER_TOKEN", settings.telegram_payment_provider_token),
        ("OUTLINE_API_URL", settings.outline_api_url),
    ]
    
    print("📋 Обязательные переменные:")
    for name, value in required_vars:
        if value:
            print(f"  ✅ {name}: {'*' * min(len(str(value)), 10)}")
        else:
            print(f"  ❌ {name}: НЕ ЗАДАНА")
    
    print("\n📋 Опциональные переменные:")
    for name, value in optional_vars:
        if value:
            print(f"  ✅ {name}: {'*' * min(len(str(value)), 10)}")
        else:
            print(f"  ⚠️  {name}: не задана")

async def main():
    """Основная функция диагностики"""
    print("🔍 Диагностика VPN Club Pro Bot")
    print("=" * 40)
    
    # Проверка переменных окружения
    check_environment()
    
    # Тестирование бота
    bot_ok = await test_bot_connection()
    
    # Тестирование БД
    db_ok = await test_database()
    
    print("\n📊 Результаты диагностики:")
    print(f"🤖 Бот: {'✅ OK' if bot_ok else '❌ ERROR'}")
    print(f"🗄️ База данных: {'✅ OK' if db_ok else '❌ ERROR'}")
    
    if bot_ok and db_ok:
        print("\n🎉 Все компоненты работают корректно!")
    else:
        print("\n⚠️  Обнаружены проблемы, требуется исправление")
    
    return bot_ok and db_ok

if __name__ == "__main__":
    success = asyncio.run(main()) 