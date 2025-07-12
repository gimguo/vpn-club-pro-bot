#!/bin/bash

echo "=== ПРОВЕРКА БАЗЫ ДАННЫХ НА СЕРВЕРЕ ==="
echo "Время: $(date)"
echo ""

# Проверяем статус контейнеров
echo "1. СТАТУС DOCKER КОНТЕЙНЕРОВ:"
docker-compose ps
echo ""

# Проверяем логи бота
echo "2. ПОСЛЕДНИЕ ЛОГИ БОТА:"
docker-compose logs --tail=10 bot
echo ""

# Запускаем проверку базы данных через Docker
echo "3. ПРОВЕРКА БАЗЫ ДАННЫХ:"
docker-compose exec -T db python3 -c "
import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime

def check_database():
    try:
        connection = psycopg2.connect(
            host='localhost',
            database='vpn_club',
            user='postgres',
            password=os.environ.get('POSTGRES_PASSWORD', ''),
            port='5432'
        )
        
        cursor = connection.cursor(cursor_factory=DictCursor)
        
        print('=' * 60)
        print('ПРОВЕРКА БАЗЫ ДАННЫХ')
        print('=' * 60)
        print(f'Время проверки: {datetime.now()}')
        print()
        
        # Проверка таблиц
        print('1. СУЩЕСТВУЮЩИЕ ТАБЛИЦЫ:')
        cursor.execute('''
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        ''')
        tables = cursor.fetchall()
        for table in tables:
            print(f'   - {table[\"table_name\"]}')
        print()
        
        # Проверка таблицы telegram_payments
        print('2. СТРУКТУРА ТАБЛИЦЫ telegram_payments:')
        try:
            cursor.execute('''
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = 'telegram_payments'
                ORDER BY ordinal_position;
            ''')
            columns = cursor.fetchall()
            if columns:
                for col in columns:
                    print(f'   - {col[\"column_name\"]}: {col[\"data_type\"]} {\"NULL\" if col[\"is_nullable\"] == \"YES\" else \"NOT NULL\"} {col[\"column_default\"] or \"\"}')
            else:
                print('   ТАБЛИЦА НЕ НАЙДЕНА!')
        except Exception as e:
            print(f'   ОШИБКА: {e}')
        print()
        
        # Проверка количества записей
        print('3. КОЛИЧЕСТВО ЗАПИСЕЙ В ТАБЛИЦАХ:')
        for table in tables:
            table_name = table['table_name']
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table_name};')
                count = cursor.fetchone()[0]
                print(f'   - {table_name}: {count} записей')
            except Exception as e:
                print(f'   - {table_name}: ОШИБКА - {e}')
        print()
        
        # Проверка последних telegram_payments
        print('4. ПОСЛЕДНИЕ 5 ЗАПИСЕЙ telegram_payments:')
        try:
            cursor.execute('''
                SELECT id, user_id, tariff_id, amount_stars, status, created_at
                FROM telegram_payments
                ORDER BY created_at DESC
                LIMIT 5;
            ''')
            payments = cursor.fetchall()
            if payments:
                for payment in payments:
                    print(f'   - ID: {payment[\"id\"]}, User: {payment[\"user_id\"]}, Tariff: {payment[\"tariff_id\"]}, Stars: {payment[\"amount_stars\"]}, Status: {payment[\"status\"]}, Created: {payment[\"created_at\"]}')
            else:
                print('   НЕТ ЗАПИСЕЙ')
        except Exception as e:
            print(f'   ОШИБКА: {e}')
        print()
        
        cursor.close()
        connection.close()
        
        print('=' * 60)
        print('ПРОВЕРКА ЗАВЕРШЕНА')
        print('=' * 60)
        
    except Exception as e:
        print(f'ОШИБКА ПОДКЛЮЧЕНИЯ К БД: {e}')
        return False
    
    return True

check_database()
"

echo ""
echo "=== ПРОВЕРКА ЗАВЕРШЕНА ===" 