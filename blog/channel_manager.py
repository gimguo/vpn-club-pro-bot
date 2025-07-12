"""
Менеджер для управления постами в Telegram канале @vpn_club_pro_blog
"""

import asyncio
import aiohttp
from typing import Optional, List, Dict
from dataclasses import dataclass
from config import Settings

settings = Settings()

@dataclass
class BlogPost:
    """Структура поста в блоге"""
    title: str
    content: str
    hashtags: List[str] = None
    
    def format_text(self) -> str:
        """Форматирует текст поста"""
        text = f"{self.title}\n\n{self.content}"
        if self.hashtags:
            text += f"\n\n{' '.join(self.hashtags)}"
        return text

class TelegramChannelManager:
    """Менеджер для работы с Telegram каналом"""
    
    def __init__(self, bot_token: str, channel_username: str):
        self.bot_token = bot_token
        self.channel_username = channel_username.replace('@', '')
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(self, text: str, parse_mode: str = "HTML") -> Optional[Dict]:
        """Отправляет сообщение в канал"""
        url = f"{self.api_url}/sendMessage"
        data = {
            "chat_id": f"@{self.channel_username}",
            "text": text,
            "parse_mode": parse_mode
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result["ok"]:
                        return result["result"]
                    else:
                        print(f"Error: {result}")
                        return None
                else:
                    print(f"HTTP Error: {response.status}")
                    return None
    
    async def edit_message(self, message_id: int, text: str, parse_mode: str = "HTML") -> bool:
        """Редактирует сообщение в канале"""
        url = f"{self.api_url}/editMessageText"
        data = {
            "chat_id": f"@{self.channel_username}",
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["ok"]
                else:
                    print(f"HTTP Error: {response.status}")
                    return False
    
    async def get_channel_posts(self, limit: int = 10) -> List[Dict]:
        """Получает последние посты из канала"""
        # Примечание: для получения постов нужны дополнительные права
        # Пока используем базовый функционал
        return []

class BlogContentManager:
    """Менеджер контента для блога"""
    
    @staticmethod
    def get_welcome_post() -> BlogPost:
        """Приветственный пост"""
        return BlogPost(
            title="🎉 **Добро пожаловать в VPN Club Pro Blog!**",
            content="""Здесь вы найдете:
🆕 **Новости и обновления** сервиса
💰 **Эксклюзивные акции** и скидки  
🔧 **Статус серверов** и техническую информацию
📱 **Подробные инструкции** по настройке
🎁 **Специальные предложения** для подписчиков

🤖 **Наш бот:** @vpn_club_pro_bot
⚡ **Быстро. Надежно. Безопасно.**

Подписывайтесь и будьте в курсе всех новостей!"""
        )
    
    @staticmethod
    def get_mobile_instruction() -> BlogPost:
        """Инструкция для мобильных устройств"""
        return BlogPost(
            title="📱 **ИНСТРУКЦИЯ: Настройка VPN на iOS и Android**",
            content="""**Шаг 1:** Скачайте приложение Outline
        🍎 **iOS:** https://apps.apple.com/us/app/outline-app/id1356177741
        🤖 **Android:** https://play.google.com/store/apps/details?id=org.outline.android.client

**Шаг 2:** Добавьте сервер
• Откройте приложение Outline
• Нажмите ➕ в правом верхнем углу
• Вставьте ваш ключ доступа
• Нажмите **"ADD SERVER"**

**Шаг 3:** Подключитесь
• Выберите добавленный сервер
• Нажмите **"Connect"**
• ✅ Готово! VPN активен

🔑 **Получить ключ:** @vpn_club_pro_bot""",
            hashtags=["#инструкция_мобильные"]
        )
    
    @staticmethod
    def get_desktop_instruction() -> BlogPost:
        """Инструкция для компьютеров"""
        return BlogPost(
            title="💻 **ИНСТРУКЦИЯ: Настройка VPN на компьютере**",
            content="""**Шаг 1:** Скачайте приложение Outline
        🖥️ **Windows:** https://s3.amazonaws.com/outline-releases/client/windows/stable/Outline-Client.exe
        🍎 **macOS:** https://s3.amazonaws.com/outline-releases/client/macos/stable/Outline-Client.dmg

**Шаг 2:** Установите и настройте
• Запустите программу Outline
• Нажмите ➕ для добавления сервера
• Вставьте ваш ключ доступа
• Нажмите **"ADD SERVER"**

**Шаг 3:** Активируйте VPN
• Выберите сервер из списка
• Нажмите **"Connect"**
• 🚀 Наслаждайтесь быстрым интернетом!

💡 **Совет:** Держите приложение в автозагрузке для мгновенного подключения""",
            hashtags=["#инструкция_компьютер"]
        )
    
    @staticmethod
    def get_updates_post() -> BlogPost:
        """Пост об обновлениях"""
        return BlogPost(
            title="🚀 **Обновления VPN Club Pro**",
            content="""Команда усердно работает над улучшением сервиса! 

**✅ Готово:**
• Стабильные высокоскоростные серверы
• Круглосуточная техническая поддержка
• Простая система оплаты

**🔄 В разработке:**
• Расширение географии серверов
• Мобильное приложение VPN Club Pro
• Система бонусов для постоянных клиентов
• Групповые тарифы со скидками

📞 **Поддержка:** Обращайтесь в @vpn_club_pro_bot с любыми вопросами

Следите за обновлениями в канале! 📡""",
            hashtags=["#обновления", "#планы"]
        )
    
    @staticmethod
    def get_pricing_post() -> BlogPost:
        """Пост о тарифах"""
        return BlogPost(
            title="💎 **Тарифы VPN Club Pro**",
            content="""🆓 **ПРОБНЫЙ:** 3 дня бесплатно
• 10 ГБ трафика
• Все серверы доступны

💰 **ОСНОВНЫЕ ТАРИФЫ:**
📅 **1 месяц** - 150₽
📅 **3 месяца** - 350₽ (экономия 100₽)
📅 **6 месяцев** - 650₽ (экономия 250₽)  
📅 **12 месяцев** - 1200₽ (экономия 600₽)

🎁 **Все тарифы включают:**
• Безлимитный трафик
• Множество серверов
• Круглосуточную поддержку

🚀 **Заказать:** @vpn_club_pro_bot""",
            hashtags=["#тарифы", "#цены"]
        )
    
    @staticmethod
    def get_security_post() -> BlogPost:
        """Пост о безопасности"""
        return BlogPost(
            title="🔐 **Ваша безопасность - наш приоритет**",
            content="""**Что защищает VPN Club Pro:**
✅ Шифрование военного уровня
✅ Отсутствие логирования активности  
✅ Защита от утечек DNS
✅ Обход блокировок и цензуры

**Идеально для:**
📱 Безопасного Wi-Fi в кафе
🌍 Доступа к заблокированным сайтам
🎬 Стриминга без ограничений
💼 Удаленной работы

🛡️ **Попробуйте бесплатно:** @vpn_club_pro_bot""",
            hashtags=["#безопасность", "#защита"]
        )

async def main():
    """Основная функция для управления блогом"""
    # Инициализация менеджера канала
    channel_manager = TelegramChannelManager(
        bot_token=settings.telegram_bot_token,
        channel_username="vpn_club_pro_blog"
    )
    
    # Менеджер контента
    content_manager = BlogContentManager()
    
    print("VPN Club Pro Blog Manager")
    print("=" * 40)
    print("1. Отправить приветственный пост")
    print("2. Отправить инструкцию для мобильных")
    print("3. Отправить инструкцию для компьютеров")
    print("4. Отправить пост об обновлениях")
    print("5. Отправить пост о тарифах")
    print("6. Отправить пост о безопасности")
    print("7. Выйти")
    
    while True:
        try:
            choice = input("\nВыберите действие (1-7): ").strip()
            
            if choice == "1":
                post = content_manager.get_welcome_post()
                result = await channel_manager.send_message(post.format_text())
                if result:
                    print(f"✅ Приветственный пост отправлен! ID: {result['message_id']}")
                else:
                    print("❌ Ошибка отправки")
                    
            elif choice == "2":
                post = content_manager.get_mobile_instruction()
                result = await channel_manager.send_message(post.format_text())
                if result:
                    print(f"✅ Инструкция для мобильных отправлена! ID: {result['message_id']}")
                else:
                    print("❌ Ошибка отправки")
                    
            elif choice == "3":
                post = content_manager.get_desktop_instruction()
                result = await channel_manager.send_message(post.format_text())
                if result:
                    print(f"✅ Инструкция для компьютеров отправлена! ID: {result['message_id']}")
                else:
                    print("❌ Ошибка отправки")
                    
            elif choice == "4":
                post = content_manager.get_updates_post()
                result = await channel_manager.send_message(post.format_text())
                if result:
                    print(f"✅ Пост об обновлениях отправлен! ID: {result['message_id']}")
                else:
                    print("❌ Ошибка отправки")
                    
            elif choice == "5":
                post = content_manager.get_pricing_post()
                result = await channel_manager.send_message(post.format_text())
                if result:
                    print(f"✅ Пост о тарифах отправлен! ID: {result['message_id']}")
                else:
                    print("❌ Ошибка отправки")
                    
            elif choice == "6":
                post = content_manager.get_security_post()
                result = await channel_manager.send_message(post.format_text())
                if result:
                    print(f"✅ Пост о безопасности отправлен! ID: {result['message_id']}")
                else:
                    print("❌ Ошибка отправки")
                    
            elif choice == "7":
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