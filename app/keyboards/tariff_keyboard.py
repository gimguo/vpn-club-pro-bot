from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import settings

class TariffKeyboard:
    @staticmethod
    def get_tariffs():
        """Клавиатура с тарифами"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🆓 Пробный период (3 дня)", callback_data="tariff_trial")],
                [InlineKeyboardButton(text=f"1️⃣ 1 месяц - {settings.monthly_price} ₽", callback_data="tariff_monthly")],
                [InlineKeyboardButton(text=f"3️⃣ 3 месяца - {settings.quarterly_price} ₽ (экономия 100₽)", callback_data="tariff_quarterly")],
                [InlineKeyboardButton(text=f"6️⃣ 6 месяцев - {settings.half_yearly_price} ₽ (экономия 250₽)", callback_data="tariff_half_yearly")],
                [InlineKeyboardButton(text=f"🔥 12 месяцев - {settings.yearly_price} ₽ (экономия 600₽)", callback_data="tariff_yearly")]
            ]
        )
        return keyboard

    @staticmethod
    def get_payment_button(amount: int, tariff_type: str):
        """Кнопка для оплаты"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Оплатить {amount} ₽", callback_data=f"payment_yookassa_{tariff_type}")],
                [InlineKeyboardButton(text="⬅️ Назад к тарифам", callback_data="back_to_tariffs")]
            ]
        )
        return keyboard

    @staticmethod
    def get_payment_url_button(payment_url: str):
        """Кнопка с ссылкой на оплату"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
                [InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_payment")]
            ]
        )
        return keyboard

    @staticmethod
    def get_tariff_names():
        """Словарь с названиями тарифов"""
        return {
            "trial": "Пробный период",
            "monthly": "1 месяц",
            "quarterly": "3 месяца", 
            "half_yearly": "6 месяцев",
            "yearly": "12 месяцев"
        } 