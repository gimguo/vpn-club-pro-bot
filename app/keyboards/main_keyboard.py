from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

class MainKeyboard:
    @staticmethod
    def get_main_menu(has_subscription: bool = False, is_trial_available: bool = True):
        """Главное меню бота — адаптивное в зависимости от статуса пользователя"""
        
        if has_subscription:
            # Пользователь с активной подпиской
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🛡️ Мой VPN")],
                    [KeyboardButton(text="🔥 Продлить"), KeyboardButton(text="👥 Друзьям")],
                    [KeyboardButton(text="📱 Скачать"), KeyboardButton(text="📖 Инструкция")],
                    [KeyboardButton(text="💬 Поддержка")]
                ],
                resize_keyboard=True,
                persistent=True
            )
        elif is_trial_available:
            # Новый пользователь — акцент на бесплатный триал
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🆓 Попробовать бесплатно")],
                    [KeyboardButton(text="🔥 Тарифы"), KeyboardButton(text="👥 Друзьям")],
                    [KeyboardButton(text="📱 Скачать"), KeyboardButton(text="📖 Инструкция")],
                    [KeyboardButton(text="💬 Поддержка")]
                ],
                resize_keyboard=True,
                persistent=True
            )
        else:
            # Триал использован, подписки нет
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="🔥 Тарифы")],
                    [KeyboardButton(text="🔍 Проверить ключ"), KeyboardButton(text="👥 Друзьям")],
                    [KeyboardButton(text="📱 Скачать"), KeyboardButton(text="📖 Инструкция")],
                    [KeyboardButton(text="💬 Поддержка")]
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
                [
                    InlineKeyboardButton(text="📱 iOS", url="https://apps.apple.com/app/outline-app/id1356177741"),
                    InlineKeyboardButton(text="🤖 Android", url="https://play.google.com/store/apps/details?id=org.outline.android.client")
                ],
                [
                    InlineKeyboardButton(text="💻 Windows", url="https://s3.amazonaws.com/outline-releases/client/windows/stable/Outline-Client.exe"),
                    InlineKeyboardButton(text="🍎 MacOS", url="https://s3.amazonaws.com/outline-releases/client/macos/stable/Outline-Client.dmg")
                ],
                [InlineKeyboardButton(text="📱 Huawei", url="https://appgallery.huawei.com/#/app/C102980387")],
                [InlineKeyboardButton(text="📖 Инструкция по настройке", callback_data="instructions")]
            ]
        )
        return keyboard

    @staticmethod
    def get_instructions():
        """Инлайн клавиатура для инструкций"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📱 iOS / Android", url="https://t.me/vpn_club_pro_blog/24"),
                ],
                [
                    InlineKeyboardButton(text="💻 Windows / Mac / Linux", url="https://t.me/vpn_club_pro_blog/25")
                ],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
        return keyboard
    
    @staticmethod
    def get_referral_keyboard(referral_link: str, referral_code: str):
        """Клавиатура для реферальной программы"""
        share_text = f"🔒 Защити свои данные в сети! Попробуй бесплатно: {referral_link}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="📤 Поделиться ссылкой", 
                    url=f"https://t.me/share/url?url={referral_link}&text=🔒 Защити свои данные в сети! Попробуй бесплатно"
                )],
                [InlineKeyboardButton(text="📋 Скопировать код", callback_data=f"copy_ref_{referral_code}")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
        return keyboard
    
    @staticmethod
    def get_trial_success_keyboard():
        """Клавиатура после успешного создания триала"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 Скачать приложение", callback_data="download_app")],
                [InlineKeyboardButton(text="📖 Как подключить?", callback_data="instructions")],
                [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral_info")],
                [InlineKeyboardButton(text="🏠 Меню", callback_data="main_menu")]
            ]
        )
        return keyboard
    
    @staticmethod
    def get_vpn_status_keyboard():
        """Клавиатура для экрана статуса VPN"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔑 Показать ключ", callback_data="get_vpn_key")],
                [InlineKeyboardButton(text="📱 Скачать приложение", callback_data="download_app")],
                [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="renew_subscription")],
                [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral_info")]
            ]
        )
        return keyboard
