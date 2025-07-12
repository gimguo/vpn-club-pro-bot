#!/usr/bin/env python3
"""
Скрипт для проверки базы данных на сервере
"""

import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
import urllib.parse

def check_database():
    """Проверка состояния базы данных"""
    
    # Подключение к базе данных с переменными окружения из контейнера
    try:
        # Сначала пробуем DATABASE_URL
        database_url = os.getenv('DATABASE_URL')
        
        if database_url:
            # Парсим DATABASE_URL
            parsed = urllib.parse.urlparse(database_url)
            host = parsed.hostname
            port = parsed.port or 5432
            database = parsed.path[1:]  # убираем первый /
            user = parsed.username
            password = parsed.password
            
            print(f"Используем DATABASE_URL: {database_url}")
        else:
            # Резервный вариант с отдельными переменными
            host = os.getenv('DB_HOST', 'db')
            port = os.getenv('DB_PORT', '5432')
            database = os.getenv('DB_NAME', 'vpn_club')
            user = os.getenv('DB_USER', 'postgres')
            password = os.getenv('DB_PASSWORD', 'postgres_password')
            
            print(f"Используем отдельные переменные: host={host}, db={database}")
        
        # Подключение к PostgreSQL
        connection = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            port=port
        )
        
        cursor = connection.cursor(cursor_factory=DictCursor)
        
        print("=" * 60)
        print("ПРОВЕРКА БАЗЫ ДАННЫХ")
        print("=" * 60)
        print(f"Время проверки: {datetime.now()}")
        print(f"Подключение: {host}:{port}")
        print(f"База данных: {database}")
        print(f"Пользователь: {user}")
        print()
        
        # Проверка таблиц
        print("1. СУЩЕСТВУЮЩИЕ ТАБЛИЦЫ:")
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        for table in tables:
            print(f"   - {table['table_name']}")
        print()
        
        # Проверка таблицы telegram_payments
        print("2. СТРУКТУРА ТАБЛИЦЫ telegram_payments:")
        try:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'telegram_payments'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            if columns:
                for col in columns:
                    print(f"   - {col['column_name']}: {col['data_type']} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'} {col['column_default'] or ''}")
            else:
                print("   ТАБЛИЦА НЕ НАЙДЕНА!")
        except Exception as e:
            print(f"   ОШИБКА: {e}")
        print()
        
        # Проверка количества записей
        print("3. КОЛИЧЕСТВО ЗАПИСЕЙ В ТАБЛИЦАХ:")
        for table in tables:
            table_name = table['table_name']
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"   - {table_name}: {count} записей")
            except Exception as e:
                print(f"   - {table_name}: ОШИБКА - {e}")
        print()
        
        # Проверка последних telegram_payments с правильными полями
        print("4. ПОСЛЕДНИЕ 5 ЗАПИСЕЙ telegram_payments:")
        try:
            cursor.execute("""
                SELECT id, user_id, tariff_type, amount, currency, status, created_at, 
                       telegram_payment_charge_id, payment_type
                FROM telegram_payments
                ORDER BY created_at DESC
                LIMIT 5;
            """)
            payments = cursor.fetchall()
            if payments:
                for payment in payments:
                    print(f"   - ID: {payment['id']}, User: {payment['user_id']}, Tariff: {payment['tariff_type']}, Amount: {payment['amount']}, Currency: {payment['currency']}, Status: {payment['status']}, Charge ID: {payment['telegram_payment_charge_id']}, Payment Type: {payment['payment_type']}, Created: {payment['created_at']}")
            else:
                print("   НЕТ ЗАПИСЕЙ")
        except Exception as e:
            print(f"   ОШИБКА: {e}")
        print()
        
        # Проверка последних пользователей
        print("5. ПОСЛЕДНИЕ 5 ПОЛЬЗОВАТЕЛЕЙ:")
        try:
            cursor.execute("""
                SELECT id, telegram_id, username, first_name, subscription_active, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT 5;
            """)
            users = cursor.fetchall()
            if users:
                for user in users:
                    print(f"   - ID: {user['id']}, TG_ID: {user['telegram_id']}, Username: {user['username']}, Name: {user['first_name']}, Active: {user['subscription_active']}, Created: {user['created_at']}")
            else:
                print("   НЕТ ЗАПИСЕЙ")
        except Exception as e:
            print(f"   ОШИБКА: {e}")
        print()
        
        # Проверка последних подписок
        print("6. ПОСЛЕДНИЕ 5 ПОДПИСОК:")
        try:
            cursor.execute("""
                SELECT id, user_id, status, expires_at, created_at
                FROM subscriptions
                ORDER BY created_at DESC
                LIMIT 5;
            """)
            subscriptions = cursor.fetchall()
            if subscriptions:
                for sub in subscriptions:
                    print(f"   - ID: {sub['id']}, User: {sub['user_id']}, Status: {sub['status']}, Expires: {sub['expires_at']}, Created: {sub['created_at']}")
            else:
                print("   НЕТ ЗАПИСЕЙ")
        except Exception as e:
            print(f"   ОШИБКА: {e}")
        print()
        
        # Проверка переменных окружения
        print("7. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ:")
        print(f"   - TELEGRAM_BOT_TOKEN: {'УСТАНОВЛЕН' if os.getenv('TELEGRAM_BOT_TOKEN') else 'НЕ УСТАНОВЛЕН'}")
        print(f"   - TELEGRAM_PAYMENT_PROVIDER_TOKEN: {'УСТАНОВЛЕН (' + str(os.getenv('TELEGRAM_PAYMENT_PROVIDER_TOKEN')) + ')' if os.getenv('TELEGRAM_PAYMENT_PROVIDER_TOKEN') is not None else 'НЕ УСТАНОВЛЕН'}")
        print(f"   - DATABASE_URL: {'УСТАНОВЛЕН' if os.getenv('DATABASE_URL') else 'НЕ УСТАНОВЛЕН'}")
        print(f"   - ADMIN_ID: {os.getenv('ADMIN_ID', 'НЕ УСТАНОВЛЕН')}")
        print(f"   - DEBUG: {os.getenv('DEBUG', 'НЕ УСТАНОВЛЕН')}")
        print()
        
        # Проверка Stars платежей
        print("8. ПРОВЕРКА STARS ПЛАТЕЖЕЙ:")
        try:
            cursor.execute("""
                SELECT id, user_id, tariff_type, amount, currency, status, payment_type, created_at
                FROM telegram_payments
                WHERE payment_type = 'stars'
                ORDER BY created_at DESC
                LIMIT 10;
            """)
            stars_payments = cursor.fetchall()
            if stars_payments:
                print(f"   Найдено {len(stars_payments)} Stars платежей:")
                for payment in stars_payments:
                    print(f"   - ID: {payment['id']}, User: {payment['user_id']}, Tariff: {payment['tariff_type']}, Amount: {payment['amount']}, Status: {payment['status']}, Created: {payment['created_at']}")
            else:
                print("   НЕТ STARS ПЛАТЕЖЕЙ")
        except Exception as e:
            print(f"   ОШИБКА: {e}")
        print()
        
        cursor.close()
        connection.close()
        
        print("=" * 60)
        print("ПРОВЕРКА ЗАВЕРШЕНА")
        print("=" * 60)
        
    except Exception as e:
        print(f"ОШИБКА ПОДКЛЮЧЕНИЯ К БД: {e}")
        print(f"Переменные окружения:")
        print(f"   - DATABASE_URL: {'УСТАНОВЛЕН' if os.getenv('DATABASE_URL') else 'НЕ УСТАНОВЛЕН'}")
        print(f"   - DB_HOST: {os.getenv('DB_HOST', 'НЕ УСТАНОВЛЕН')}")
        print(f"   - DB_NAME: {os.getenv('DB_NAME', 'НЕ УСТАНОВЛЕН')}")
        print(f"   - DB_USER: {os.getenv('DB_USER', 'НЕ УСТАНОВЛЕН')}")
        print(f"   - DB_PASSWORD: {'УСТАНОВЛЕН' if os.getenv('DB_PASSWORD') else 'НЕ УСТАНОВЛЕН'}")
        return False
    
    return True

if __name__ == "__main__":
    check_database() 