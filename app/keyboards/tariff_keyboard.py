from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import settings

class TariffKeyboard:
    @staticmethod
    def get_tariffs():
        """Клавиатура с тарифами — психологическое ценообразование"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="🆓 Пробный период (бесплатно)", 
                    callback_data="tariff_trial"
                )],
                [InlineKeyboardButton(
                    text=f"1️⃣ 1 месяц — {settings.monthly_price} ₽", 
                    callback_data="tariff_monthly"
                )],
                [InlineKeyboardButton(
                    text=f"3️⃣ 3 месяца — {settings.quarterly_price} ₽  -22%", 
                    callback_data="tariff_quarterly"
                )],
                [InlineKeyboardButton(
                    text=f"⭐ 6 месяцев — {settings.half_yearly_price} ₽  ПОПУЛЯРНЫЙ", 
                    callback_data="tariff_half_yearly"
                )],
                [InlineKeyboardButton(
                    text=f"👑 12 месяцев — {settings.yearly_price} ₽  -44%", 
                    callback_data="tariff_yearly"
                )]
            ]
        )
        return keyboard

    @staticmethod
    def get_payment_button(amount: int, tariff_type: str):
        """Кнопка для перехода к выбору способа оплаты"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"💳 Оплатить {amount} ₽", 
                    callback_data=f"pay_{tariff_type}"
                )],
                [InlineKeyboardButton(
                    text="⬅️ Назад к тарифам", 
                    callback_data="back_to_tariffs"
                )]
            ]
        )
        return keyboard

    @staticmethod
    def get_payment_url_button(payment_url: str):
        """Кнопка с ссылкой на оплату"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
                [InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_payment")],
                [InlineKeyboardButton(text="⬅️ Назад к тарифам", callback_data="back_to_tariffs")]
            ]
        )
        return keyboard

    @staticmethod
    def get_tariff_names():
        """Словарь с названиями тарифов"""
        return {
            "trial": "🆓 Пробный период",
            "monthly": "1️⃣ 1 месяц",
            "quarterly": "3️⃣ 3 месяца", 
            "half_yearly": "⭐ 6 месяцев",
            "yearly": "👑 12 месяцев",
            "unlimited": "♾ Безлимит",
        }
    
    @staticmethod
    def get_tariff_details():
        """Подробности тарифов для экрана оплаты"""
        monthly = settings.monthly_price
        return {
            "trial": {
                "name": "Пробный период",
                "price": 0,
                "days": settings.trial_days,
                "traffic": f"{settings.trial_traffic_gb} ГБ",
                "badge": "🆓 БЕСПЛАТНО"
            },
            "monthly": {
                "name": "1 месяц",
                "price": settings.monthly_price,
                "days": 30,
                "traffic": "Безлимитный",
                "badge": ""
            },
            "quarterly": {
                "name": "3 месяца",
                "price": settings.quarterly_price,
                "days": 90,
                "traffic": "Безлимитный",
                "badge": "💰 -22%",
                "savings": monthly * 3 - settings.quarterly_price
            },
            "half_yearly": {
                "name": "6 месяцев",
                "price": settings.half_yearly_price,
                "days": 180,
                "traffic": "Безлимитный",
                "badge": "⭐ ПОПУЛЯРНЫЙ",
                "savings": monthly * 6 - settings.half_yearly_price
            },
            "yearly": {
                "name": "12 месяцев",
                "price": settings.yearly_price,
                "days": 365,
                "traffic": "Безлимитный",
                "badge": "👑 ЛУЧШАЯ ЦЕНА",
                "savings": monthly * 12 - settings.yearly_price
            }
        }
