from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from decimal import Decimal

class PaymentKeyboard:
    @staticmethod
    def get_payment_methods(tariff_type: str):
        """Клавиатура для выбора способа оплаты"""
        # Цены в Stars (рублевые цены / 3)
        stars_prices = {
            "trial": 50,
            "monthly": 50,
            "quarterly": 117,
            "half_yearly": 217,
            "yearly": 400
        }
        
        # Рублевые цены
        rub_prices = {
            "trial": 150,
            "monthly": 150,
            "quarterly": 350,
            "half_yearly": 650,
            "yearly": 1200
        }
        
        stars_price = stars_prices.get(tariff_type, 0)
        rub_price = rub_prices.get(tariff_type, 0)
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"⭐ Telegram Stars ({stars_price}⭐)", callback_data=f"payment_stars_{tariff_type}")],
                # [InlineKeyboardButton(text="💳 Банковская карта", callback_data=f"payment_card_{tariff_type}")],
                [InlineKeyboardButton(text=f"🥇 YooKassa ({rub_price}₽)", callback_data=f"payment_yookassa_{tariff_type}")],
                # [InlineKeyboardButton(text="🐕 DOGE (скоро)", callback_data=f"payment_doge_{tariff_type}")],
                # [InlineKeyboardButton(text="🔴 TRX (скоро)", callback_data=f"payment_trx_{tariff_type}")],
                [InlineKeyboardButton(text="⬅️ Назад к тарифам", callback_data="back_to_tariffs")]
            ]
        )
        return keyboard

    @staticmethod
    def get_stars_payment_confirm(tariff_type: str, amount: Decimal = None):
        """Подтверждение оплаты Stars"""
        # Цены в Stars (рублевые цены / 3)
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
                [InlineKeyboardButton(text=f"⭐ Оплатить {stars_amount} Stars", callback_data=f"confirm_stars_{tariff_type}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"payment_methods_{tariff_type}")]
            ]
        )
        return keyboard

    @staticmethod
    def get_card_payment_confirm(tariff_type: str, amount: Decimal):
        """Подтверждение оплаты картой"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Оплатить ${amount:.2f}", callback_data=f"confirm_card_{tariff_type}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"payment_methods_{tariff_type}")]
            ]
        )
        return keyboard

    @staticmethod
    def get_crypto_payment_confirm(tariff_type: str, crypto_type: str, amount: Decimal):
        """Подтверждение криптоплатежа"""
        crypto_names = {
            "doge": "🐕 DOGE",
            "trx": "🔴 TRX"
        }
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"Оплатить {crypto_names.get(crypto_type, crypto_type)}", callback_data=f"confirm_{crypto_type}_{tariff_type}")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"payment_methods_{tariff_type}")]
            ]
        )
        return keyboard

    @staticmethod
    def get_payment_success():
        """Клавиатура после успешной оплаты"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📱 Получить ключ VPN", callback_data="get_vpn_key")],
                [InlineKeyboardButton(text="📊 Мои подписки", callback_data="my_subscriptions")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
        return keyboard

    @staticmethod
    def get_payment_pending():
        """Клавиатура для ожидания оплаты"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_payment")],
                [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment")]
            ]
        )
        return keyboard

    @staticmethod
    def get_payment_prices():
        """Цены для разных способов оплаты"""
        return {
            "stars": {
                "trial": Decimal("1.50"),
                "monthly": Decimal("4.99"),
                "quarterly": Decimal("12.99"),
                "half_yearly": Decimal("24.99"),
                "yearly": Decimal("49.99")
            },
            "card": {
                "trial": Decimal("1.50"),
                "monthly": Decimal("4.99"),
                "quarterly": Decimal("12.99"),
                "half_yearly": Decimal("24.99"),
                "yearly": Decimal("49.99")
            },
            "crypto": {
                "trial": Decimal("1.50"),
                "monthly": Decimal("4.99"),
                "quarterly": Decimal("12.99"),
                "half_yearly": Decimal("24.99"),
                "yearly": Decimal("49.99")
            }
        }

    @staticmethod
    def get_payment_method_info():
        """Информация о способах оплаты"""
        return {
            "stars": {
                "name": "⭐ Telegram Stars",
                "description": "Мгновенная оплата через Telegram Stars",
                "benefits": ["Оплата прямо в боте", "Мгновенное зачисление", "Защита от Telegram"]
            },
            "card": {
                "name": "💳 Банковская карта",
                "description": "Оплата банковской картой через Telegram",
                "benefits": ["Безопасные платежи", "Поддержка всех карт", "Быстрое зачисление"]
            },
            "yookassa": {
                "name": "🥇 YooKassa",
                "description": "Классическая оплата в рублях",
                "benefits": ["Привычные рубли", "Все способы оплаты", "Российский сервис"]
            },
            "doge": {
                "name": "🐕 Dogecoin",
                "description": "Оплата криптовалютой DOGE",
                "benefits": ["Низкие комиссии", "Быстрые переводы", "Анонимность"]
            },
            "trx": {
                "name": "🔴 Tron",
                "description": "Оплата криптовалютой TRX",
                "benefits": ["Минимальные комиссии", "Мгновенные переводы", "Блокчейн Tron"]
            }
        } 