from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class PaymentKeyboard:

    @staticmethod
    def get_payment_success():
        """Клавиатура после успешной оплаты"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔑 Мой VPN-ключ", callback_data="get_vpn_key")],
                [InlineKeyboardButton(text="📱 Скачать приложение", callback_data="download_app")],
                [InlineKeyboardButton(text="👥 Пригласить друга", callback_data="referral_info")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
        return keyboard

    @staticmethod
    def get_payment_pending():
        """Клавиатура для ожидания оплаты"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_payment")],
                [InlineKeyboardButton(text="⬅️ К тарифам", callback_data="cancel_payment")]
            ]
        )
        return keyboard
