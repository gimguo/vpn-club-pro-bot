from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from decimal import Decimal
from config import settings


class PaymentKeyboard:
    @staticmethod
    def get_payment_methods(tariff_type: str):
        """Клавиатура для выбора способа оплаты — все методы на одном экране"""
        # Рублевые цены из настроек
        rub_prices = {
            "trial": settings.trial_price,
            "monthly": settings.monthly_price,
            "quarterly": settings.quarterly_price,
            "half_yearly": settings.half_yearly_price,
            "yearly": settings.yearly_price
        }
        
        # Stars цены
        stars_prices = {
            "trial": 50,
            "monthly": 50,
            "quarterly": 117,
            "half_yearly": 217,
            "yearly": 400
        }
        
        rub_price = rub_prices.get(tariff_type, 0)
        stars_price = stars_prices.get(tariff_type, 0)
        
        buttons = [
            [InlineKeyboardButton(
                text=f"💳 Банковская карта — {rub_price} ₽", 
                callback_data=f"payment_yookassa_{tariff_type}"
            )],
            [InlineKeyboardButton(
                text=f"⭐ Telegram Stars — {stars_price} Stars", 
                callback_data=f"payment_stars_{tariff_type}"
            )],
            [InlineKeyboardButton(
                text="⬅️ Назад к тарифам", 
                callback_data="back_to_tariffs"
            )]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        return keyboard

    @staticmethod
    def get_stars_payment_confirm(tariff_type: str, amount: Decimal = None):
        """Подтверждение оплаты Stars"""
        stars_prices = {
            "trial": 50,
            "monthly": 50,
            "quarterly": 117,
            "half_yearly": 217,
            "yearly": 400
        }
        
        stars_amount = stars_prices.get(tariff_type, 0)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"⭐ Оплатить {stars_amount} Stars", 
                    callback_data=f"confirm_stars_{tariff_type}"
                )],
                [InlineKeyboardButton(
                    text="⬅️ Другой способ", 
                    callback_data=f"pay_{tariff_type}"
                )]
            ]
        )
        return keyboard

    @staticmethod
    def get_card_payment_confirm(tariff_type: str, amount: Decimal):
        """Подтверждение оплаты картой"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💳 Оплатить ${amount:.2f}", 
                    callback_data=f"confirm_card_{tariff_type}"
                )],
                [InlineKeyboardButton(
                    text="⬅️ Другой способ", 
                    callback_data=f"pay_{tariff_type}"
                )]
            ]
        )
        return keyboard

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
