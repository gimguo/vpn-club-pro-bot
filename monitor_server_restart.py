#!/usr/bin/env python3
import asyncio
import sys
import os
import time

# Добавляем корневую папку в sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot
from aiogram.types import LabeledPrice
from config import settings

async def monitor_server_restart():
    print('👁️ МОНИТОРИНГ ПЕРЕЗАПУСКА СЕРВЕРА')
    
    bot = Bot(token=settings.telegram_bot_token)
    
    try:
        # Начальное состояние
        initial_webhook_info = await bot.get_webhook_info()
        initial_allowed_updates = initial_webhook_info.allowed_updates or []
        
        print(f'📊 Начальное состояние: {initial_allowed_updates}')
        
        # Ожидаем изменений
        max_checks = 30  # 30 проверок по 10 секунд = 5 минут
        check_interval = 10  # секунд
        
        for i in range(max_checks):
            await asyncio.sleep(check_interval)
            
            try:
                webhook_info = await bot.get_webhook_info()
                current_allowed_updates = webhook_info.allowed_updates or []
                
                print(f'🔍 Проверка {i+1}/{max_checks}: {current_allowed_updates}')
                
                # Проверяем изменения
                if 'successful_payment' in current_allowed_updates:
                    print('🎉 УСПЕХ! successful_payment найден!')
                    
                    # Отправляем уведомление
                    await bot.send_message(
                        chat_id=settings.admin_id,
                        text='🎉 СЕРВЕР ПЕРЕЗАПУЩЕН УСПЕШНО!\n\n'
                             f'✅ Allowed updates: {current_allowed_updates}\n'
                             f'✅ successful_payment: True\n\n'
                             'Stars payments теперь должны работать!'
                    )
                    
                    # Отправляем тестовый Stars invoice
                    print('📤 Отправляю тестовый Stars invoice...')
                    await bot.send_invoice(
                        chat_id=settings.admin_id,
                        title='🎉 ТЕСТ ПОСЛЕ ИСПРАВЛЕНИЯ',
                        description='Тест Stars payment после успешного перезапуска',
                        payload='success_restart_test',
                        provider_token='',
                        currency='XTR',
                        prices=[LabeledPrice(label='Success Test', amount=50)],
                        start_parameter='success_test'
                    )
                    
                    print('✅ Тестовый invoice отправлен!')
                    print('💡 ПОПРОБУЙТЕ ОПЛАТИТЬ - ДОЛЖНО РАБОТАТЬ!')
                    break
                    
                elif current_allowed_updates != initial_allowed_updates:
                    print(f'🔄 Изменения обнаружены: {current_allowed_updates}')
                    
                    await bot.send_message(
                        chat_id=settings.admin_id,
                        text=f'🔄 ИЗМЕНЕНИЯ ОБНАРУЖЕНЫ:\n\n'
                             f'Было: {initial_allowed_updates}\n'
                             f'Стало: {current_allowed_updates}\n\n'
                             f'❌ successful_payment: {"successful_payment" in current_allowed_updates}\n'
                             'Продолжаю мониторинг...'
                    )
                    
                    initial_allowed_updates = current_allowed_updates
                    
            except Exception as e:
                print(f'❌ Ошибка проверки: {e}')
                
        else:
            # Если цикл завершился без break
            print('⏰ Время мониторинга истекло')
            await bot.send_message(
                chat_id=settings.admin_id,
                text='⏰ МОНИТОРИНГ ЗАВЕРШЕН\n\n'
                     'Изменения не обнаружены за 5 минут.\n'
                     'Возможно, перезапуск не произошел.\n\n'
                     'Проверьте выполнение команд на сервере.'
            )
        
    except Exception as e:
        print(f'❌ Критическая ошибка: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(monitor_server_restart()) 