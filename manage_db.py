#!/usr/bin/env python3
"""
Скрипт для управления базой данных PostgreSQL
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path

from config import settings
from app.database import init_db


async def create_database():
    """Создание базы данных, если её нет"""
    # Извлекаем параметры подключения из URL
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        # Подключаемся к базе postgres для создания нашей базы
        system_db_url = db_url.rsplit('/', 1)[0] + '/postgres'
        conn = await asyncpg.connect(system_db_url)
        
        # Извлекаем имя базы данных
        db_name = db_url.split('/')[-1]
        
        # Проверяем, существует ли база данных
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"✅ База данных '{db_name}' создана")
            await conn.close()
            return True  # Новая база данных
        else:
            print(f"ℹ️  База данных '{db_name}' уже существует")
            await conn.close()
            return False  # Существующая база данных
            
    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")
        return None


async def is_database_empty():
    """Проверка, пустая ли база данных"""
    try:
        db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(db_url)
        
        # Проверяем наличие таблиц
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        
        await conn.close()
        return len(tables) == 0
        
    except Exception as e:
        print(f"❌ Ошибка при проверке базы данных: {e}")
        return True


async def run_migration(migration_file: str):
    """Выполнение SQL миграции"""
    try:
        # Подключаемся к нашей базе данных
        db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(db_url)
        
        # Читаем файл миграции
        migration_path = Path("migrations") / migration_file
        if not migration_path.exists():
            print(f"❌ Файл миграции {migration_file} не найден")
            return False
            
        with open(migration_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Выполняем SQL
        await conn.execute(sql_content)
        print(f"✅ Миграция {migration_file} выполнена успешно")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при выполнении миграции {migration_file}: {e}")
        return False


async def load_full_dump():
    """Загрузка полного дампа данных"""
    try:
        db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(db_url)
        
        # Читаем полный дамп
        dump_path = Path("migrations") / "postgres_full_dump.sql"
        if not dump_path.exists():
            print(f"❌ Файл дампа postgres_full_dump.sql не найден")
            return False
            
        with open(dump_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Выполняем SQL дампа
        await conn.execute(sql_content)
        print(f"✅ Полный дамп загружен успешно")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при загрузке дампа: {e}")
        return False


async def init_database():
    """Инициализация базы данных через SQLAlchemy"""
    try:
        await init_db()
        print("✅ Таблицы созданы через SQLAlchemy")
        return True
    except Exception as e:
        print(f"❌ Ошибка при инициализации через SQLAlchemy: {e}")
        return False


async def setup_fresh_database():
    """Настройка новой базы данных с данными"""
    print("🆕 Настройка новой базы данных...")
    
    # Проверяем, есть ли полный дамп для загрузки
    dump_path = Path("migrations") / "postgres_full_dump.sql"
    if dump_path.exists():
        print("📦 Найден полный дамп, загружаем данные...")
        if await load_full_dump():
            print("✅ База данных инициализирована с данными из дампа")
            return True
    
    # Если дампа нет, создаем схему через миграции
    print("🔧 Создаем схему через миграции...")
    migrations = [
        "001_initial_schema.sql",
        "002_support_system.sql",
        "003_telegram_payments.sql"
    ]
    
    for migration in migrations:
        if not await run_migration(migration):
            print(f"❌ Остановка на миграции {migration}")
            return False
    
    print("✅ Схема создана, база данных пуста")
    return True


async def main():
    """Основная функция"""
    print("🚀 Управление базой данных VPN Club Pro Bot")
    print("=" * 50)
    
    # Проверяем аргументы командной строки
    force_fresh = "--force-fresh" in sys.argv
    skip_data = "--skip-data" in sys.argv
    
    if force_fresh:
        print("⚠️  Принудительная инициализация как новой БД")
    
    # 1. Создаем базу данных
    print("\n1. Создание базы данных...")
    db_creation_result = await create_database()
    if db_creation_result is None:
        return
    
    is_new_db = db_creation_result or force_fresh
    
    # 2. Проверяем, пустая ли база данных
    if not is_new_db and not force_fresh:
        print("\n2. Проверка базы данных...")
        is_empty = await is_database_empty()
        if is_empty:
            print("📭 База данных пустая, инициализируем как новую")
            is_new_db = True
    
    # 3. Инициализация в зависимости от состояния БД
    if is_new_db and not skip_data:
        print("\n3. Инициализация новой базы данных...")
        if not await setup_fresh_database():
            return
    else:
        if skip_data:
            print("\n3. Пропускаем загрузку данных (флаг --skip-data)")
        else:
            print("\n3. База данных уже инициализирована")
        
        # Проверяем схему через SQLAlchemy (опционально)
        print("\n4. Проверка схемы через SQLAlchemy...")
        await init_database()
    
    print("\n✅ Все готово! База данных инициализирована.")
    print("\nТеперь можно запускать бота:")
    print("  python main.py")
    print("  или")
    print("  docker-compose up -d")
    
    print("\n💡 Дополнительные опции:")
    print("  --force-fresh   : Принудительно инициализировать как новую БД")
    print("  --skip-data     : Не загружать данные, только схему")


if __name__ == "__main__":
    asyncio.run(main()) 