from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

class MainKeyboard:
    @staticmethod
    def get_main_menu():
        """Главное меню бота"""
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔥 Тарифы")],
                [KeyboardButton(text="📱 Скачать VPN"), KeyboardButton(text="📖 Инструкция")],
                [KeyboardButton(text="🔍 Проверить ключ"), KeyboardButton(text="💬 Поддержка")]
            ],
            resize_keyboard=True,
            persistent=True
        )
        return keyboard

    @staticmethod
    def get_download_links():
        """Инлайн клавиатура для скачивания приложений"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 iOS", url="https://apps.apple.com/app/outline-app/id1356177741")],
                [InlineKeyboardButton(text="🤖 Android", url="https://play.google.com/store/apps/details?id=org.outline.android.client")],
                [InlineKeyboardButton(text="💻 Windows", url="https://s3.amazonaws.com/outline-releases/client/windows/stable/Outline-Client.exe")],
                [InlineKeyboardButton(text="🍎 MacOS", url="https://s3.amazonaws.com/outline-releases/client/macos/stable/Outline-Client.dmg")],
                [InlineKeyboardButton(text="📱 Huawei", url="https://appgallery.huawei.com/#/app/C102980387")],
                [InlineKeyboardButton(text="📖 Инструкция", callback_data="instructions")]
            ]
        )
        return keyboard

    @staticmethod
    def get_instructions():
        """Инлайн клавиатура для инструкций"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 iOS", url="https://t.me/vpn_club_pro_blog/24")],
                [InlineKeyboardButton(text="🤖 Android", url="https://t.me/vpn_club_pro_blog/24")],
                [InlineKeyboardButton(text="💻 Windows", url="https://t.me/vpn_club_pro_blog/25")],
                [InlineKeyboardButton(text="🍎 MacOS", url="https://t.me/vpn_club_pro_blog/25")],
                [InlineKeyboardButton(text="🐧 Linux", url="https://t.me/vpn_club_pro_blog/25")]
            ]
        )
        return keyboard 