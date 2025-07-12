#!/usr/bin/env python3
"""
Простой скрипт для запуска менеджера блога VPN Club Pro
"""

import sys
import os
import asyncio

# Добавляем корневую папку проекта в Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blog.channel_manager import main as channel_main
from blog.post_editor import main as editor_main

async def main():
    """Главное меню для управления блогом"""
    print("🎯 VPN Club Pro Blog Management System")
    print("=" * 50)
    print("1. 📝 Создать и отправить новые посты")
    print("2. ✏️  Редактировать существующие посты")
    print("3. 🚪 Выйти")
    
    while True:
        try:
            choice = input("\nВыберите режим работы (1-3): ").strip()
            
            if choice == "1":
                print("\n🚀 Запуск менеджера создания постов...")
                await channel_main()
                
            elif choice == "2":
                print("\n📝 Запуск редактора постов...")
                await editor_main()
                
            elif choice == "3":
                print("👋 До свидания!")
                break
                
            else:
                print("❌ Неверный выбор. Попробуйте еще раз.")
                
        except KeyboardInterrupt:
            print("\n👋 До свидания!")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 