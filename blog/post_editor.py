"""
Редактор постов для канала @vpn_club_pro_blog
"""

import asyncio
import json
import os
from channel_manager import TelegramChannelManager, BlogContentManager
from config import Settings

settings = Settings()

class PostEditor:
    """Класс для редактирования постов"""
    
    def __init__(self):
        self.channel_manager = TelegramChannelManager(
            bot_token=settings.telegram_bot_token,
            channel_username="vpn_club_pro_blog"
        )
        self.content_manager = BlogContentManager()
        self.posts_file = "blog/posts_db.json"
        self.posts_db = self.load_posts_db()
    
    def load_posts_db(self) -> dict:
        """Загружает базу данных постов"""
        if os.path.exists(self.posts_file):
            with open(self.posts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_posts_db(self):
        """Сохраняет базу данных постов"""
        with open(self.posts_file, 'w', encoding='utf-8') as f:
            json.dump(self.posts_db, f, ensure_ascii=False, indent=2)
    
    def save_post_id(self, post_type: str, message_id: int):
        """Сохраняет ID поста"""
        self.posts_db[post_type] = message_id
        self.save_posts_db()
    
    async def edit_post(self, post_type: str, new_content: str) -> bool:
        """Редактирует существующий пост"""
        if post_type not in self.posts_db:
            print(f"❌ Пост типа '{post_type}' не найден в базе данных")
            return False
        
        message_id = self.posts_db[post_type]
        success = await self.channel_manager.edit_message(message_id, new_content)
        
        if success:
            print(f"✅ Пост '{post_type}' успешно отредактирован!")
        else:
            print(f"❌ Ошибка редактирования поста '{post_type}'")
        
        return success
    
    async def update_welcome_post(self):
        """Обновляет приветственный пост"""
        post = self.content_manager.get_welcome_post()
        await self.edit_post("welcome", post.format_text())
    
    async def update_mobile_instruction(self):
        """Обновляет инструкцию для мобильных"""
        post = self.content_manager.get_mobile_instruction()
        await self.edit_post("mobile_instruction", post.format_text())
    
    async def update_desktop_instruction(self):
        """Обновляет инструкцию для компьютеров"""
        post = self.content_manager.get_desktop_instruction()
        await self.edit_post("desktop_instruction", post.format_text())
    
    async def update_pricing_post(self):
        """Обновляет пост о тарифах"""
        post = self.content_manager.get_pricing_post()
        await self.edit_post("pricing", post.format_text())
    
    def show_posts_db(self):
        """Показывает сохраненные ID постов"""
        if not self.posts_db:
            print("📭 База данных постов пуста")
            return
        
        print("\n📋 Сохраненные посты:")
        print("-" * 40)
        for post_type, message_id in self.posts_db.items():
            print(f"{post_type}: ID {message_id}")

async def main():
    """Основная функция редактора постов"""
    editor = PostEditor()
    
    print("📝 VPN Club Pro Blog Editor")
    print("=" * 40)
    print("1. Показать сохраненные посты")
    print("2. Редактировать приветственный пост")
    print("3. Редактировать инструкцию для мобильных")
    print("4. Редактировать инструкцию для компьютеров")
    print("5. Редактировать пост о тарифах")
    print("6. Добавить ID поста в базу данных")
    print("7. Редактировать произвольный пост")
    print("8. Выйти")
    
    while True:
        try:
            choice = input("\nВыберите действие (1-8): ").strip()
            
            if choice == "1":
                editor.show_posts_db()
                
            elif choice == "2":
                await editor.update_welcome_post()
                
            elif choice == "3":
                await editor.update_mobile_instruction()
                
            elif choice == "4":
                await editor.update_desktop_instruction()
                
            elif choice == "5":
                await editor.update_pricing_post()
                
            elif choice == "6":
                post_type = input("Введите тип поста: ").strip()
                try:
                    message_id = int(input("Введите ID сообщения: ").strip())
                    editor.save_post_id(post_type, message_id)
                    print(f"✅ ID поста сохранен: {post_type} -> {message_id}")
                except ValueError:
                    print("❌ Неверный формат ID")
                    
            elif choice == "7":
                post_type = input("Введите тип поста для редактирования: ").strip()
                new_content = input("Введите новый текст поста: ").strip()
                await editor.edit_post(post_type, new_content)
                
            elif choice == "8":
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