from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import TelegramPayment, User
from config import settings
import uuid
import logging
from decimal import Decimal
from typing import Optional, Dict, Any
from aiogram.types import LabeledPrice, Message
from aiogram import Bot

logger = logging.getLogger(__name__)

class TelegramPaymentService:
    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot

    async def create_stars_payment(self, user_id: int, tariff_type: str) -> TelegramPayment:
        """Создание платежа через Telegram Stars"""
        # Получаем цену в Stars для тарифа
        stars_amount = self.get_tariff_price_stars(tariff_type)
        
        # Создаем payload для идентификации платежа
        payload = f"stars_payment_{user_id}_{tariff_type}_{uuid.uuid4().hex[:8]}"
        
        # Создаем запись в БД
        payment = TelegramPayment(
            user_id=user_id,
            telegram_payment_charge_id=payload,  # Временно, обновится после оплаты
            amount=Decimal(str(stars_amount)),  # Сохраняем количество Stars
            currency="XTR",  # Telegram Stars
            tariff_type=tariff_type,
            payment_type="stars",
            telegram_user_id=str(user_id),
            invoice_payload=payload,
            status="pending"
        )
        
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        
        return payment

    async def create_card_payment(self, user_id: int, amount: Decimal, tariff_type: str) -> TelegramPayment:
        """Создание платежа через банковскую карту"""
        # Создаем payload для идентификации платежа
        payload = f"card_payment_{user_id}_{tariff_type}_{uuid.uuid4().hex[:8]}"
        
        # Создаем запись в БД
        payment = TelegramPayment(
            user_id=user_id,
            telegram_payment_charge_id=payload,  # Временно, обновится после оплаты
            amount=amount,
            currency="USD",  # Банковские карты в USD
            tariff_type=tariff_type,
            payment_type="card",
            telegram_user_id=str(user_id),
            invoice_payload=payload,
            status="pending"
        )
        
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        
        return payment

    async def send_stars_invoice(self, chat_id: int, payment: TelegramPayment) -> bool:
        """Отправка invoice для оплаты Stars"""
        try:
            tariff_names = {
                "trial": "Пробная подписка (3 дня)",
                "monthly": "Подписка на месяц",
                "quarterly": "Подписка на 3 месяца",
                "half_yearly": "Подписка на 6 месяцев",
                "yearly": "Подписка на год"
            }
            
            title = f"VPN Club Pro - {tariff_names.get(payment.tariff_type, 'Подписка')}"
            description = f"Оплата подписки через Telegram Stars"
            
            # Используем сохраненную цену в Stars из payment.amount
            stars_amount = int(payment.amount)
            
            # Отправляем invoice
            await self.bot.send_invoice(
                chat_id=chat_id,
                title=title,
                description=description,
                payload=payment.invoice_payload,
                provider_token="",  # Пустой для Telegram Stars
                currency="XTR",
                prices=[LabeledPrice(label="Подписка", amount=stars_amount)],
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                send_phone_number_to_provider=False,
                send_email_to_provider=False,
                is_flexible=False,
                disable_notification=False,
                protect_content=False,
                reply_to_message_id=None,
                allow_sending_without_reply=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending Stars invoice: {e}")
            return False

    async def send_card_invoice(self, chat_id: int, payment: TelegramPayment) -> bool:
        """Отправка invoice для оплаты банковской картой"""
        try:
            tariff_names = {
                "trial": "Пробная подписка (3 дня)",
                "monthly": "Подписка на месяц",
                "quarterly": "Подписка на 3 месяца",
                "half_yearly": "Подписка на 6 месяцев",
                "yearly": "Подписка на год"
            }
            
            title = f"VPN Club Pro - {tariff_names.get(payment.tariff_type, 'Подписка')}"
            description = f"Оплата подписки банковской картой"
            
            # Конвертируем в центы
            amount_cents = int(payment.amount * 100)
            
            # Отправляем invoice
            await self.bot.send_invoice(
                chat_id=chat_id,
                title=title,
                description=description,
                payload=payment.invoice_payload,
                provider_token=settings.telegram_payment_provider_token,
                currency="USD",
                prices=[LabeledPrice(label="Подписка", amount=amount_cents)],
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
                send_phone_number_to_provider=False,
                send_email_to_provider=False,
                is_flexible=False,
                disable_notification=False,
                protect_content=False,
                reply_to_message_id=None,
                allow_sending_without_reply=True
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending card invoice: {e}")
            return False

    async def get_payment_by_payload(self, payload: str) -> Optional[TelegramPayment]:
        """Получение платежа по payload"""
        result = await self.session.execute(
            select(TelegramPayment).where(TelegramPayment.invoice_payload == payload)
        )
        return result.scalar_one_or_none()

    async def process_successful_payment(self, successful_payment: Dict[str, Any]) -> Optional[TelegramPayment]:
        """Обработка успешного платежа"""
        payload = successful_payment.get("invoice_payload")
        logger.info(f"🔍 [PROCESS_PAYMENT] Starting to process payment with payload: {payload}")
        
        if not payload:
            logger.error("❌ [PROCESS_PAYMENT] No payload in successful payment")
            return None
            
        logger.info(f"🔍 [PROCESS_PAYMENT] Searching for payment with payload: {payload}")
        payment = await self.get_payment_by_payload(payload)
        
        if not payment:
            logger.error(f"❌ [PROCESS_PAYMENT] Payment not found for payload: {payload}")
            
            # Дополнительная диагностика - выводим все платежи
            logger.info("🔍 [PROCESS_PAYMENT] Checking all payments in database...")
            result = await self.session.execute(select(TelegramPayment))
            all_payments = result.scalars().all()
            
            for p in all_payments:
                logger.info(f"🔍 [PROCESS_PAYMENT] Found payment: ID {p.id}, payload: {p.invoice_payload}, status: {p.status}")
            
            return None
            
        logger.info(f"✅ [PROCESS_PAYMENT] Found payment: ID {payment.id}, current status: {payment.status}")
        
        # Обновляем статус и данные платежа
        old_status = payment.status
        payment.status = "succeeded"
        payment.telegram_payment_charge_id = successful_payment.get("telegram_payment_charge_id")
        payment.provider_payment_charge_id = successful_payment.get("provider_payment_charge_id")
        
        logger.info(f"📝 [PROCESS_PAYMENT] Updating payment {payment.id}: {old_status} -> succeeded")
        logger.info(f"📝 [PROCESS_PAYMENT] Telegram charge ID: {payment.telegram_payment_charge_id}")
        logger.info(f"📝 [PROCESS_PAYMENT] Provider charge ID: {payment.provider_payment_charge_id}")
        
        await self.session.commit()
        await self.session.refresh(payment)
        
        logger.info(f"✅ [PROCESS_PAYMENT] Payment {payment.id} processed successfully, new status: {payment.status}")
        return payment

    async def get_latest_payment(self, user_id: int) -> Optional[TelegramPayment]:
        """Получение последнего платежа пользователя"""
        result = await self.session.execute(
            select(TelegramPayment)
            .where(TelegramPayment.user_id == user_id)
            .order_by(TelegramPayment.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    def get_tariff_price(self, tariff_type: str) -> Decimal:
        """Получение цены тарифа в USD"""
        # Цены в USD для Telegram Payments
        prices = {
            "trial": Decimal("1.50"),
            "monthly": Decimal("4.99"),
            "quarterly": Decimal("12.99"),
            "half_yearly": Decimal("24.99"),
            "yearly": Decimal("49.99")
        }
        return prices.get(tariff_type, Decimal("0"))

    async def create_rub_payment(self, user_id: int, tariff_type: str) -> TelegramPayment:
        """Создание платежа для нативной оплаты картой в рублях через Telegram Payments + YooKassa."""
        rub_prices = {
            "monthly": settings.monthly_price,
            "quarterly": settings.quarterly_price,
            "half_yearly": settings.half_yearly_price,
            "yearly": settings.yearly_price,
        }
        amount = Decimal(str(rub_prices.get(tariff_type, 0)))
        payload = f"rub_payment_{user_id}_{tariff_type}_{uuid.uuid4().hex[:8]}"

        payment = TelegramPayment(
            user_id=user_id,
            telegram_payment_charge_id=payload,
            amount=amount,
            currency="RUB",
            tariff_type=tariff_type,
            payment_type="card_rub",
            telegram_user_id=str(user_id),
            invoice_payload=payload,
            status="pending",
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def send_rub_invoice(self, chat_id: int, payment: TelegramPayment) -> bool:
        """Отправить нативный Telegram invoice в рублях (YooKassa provider)."""
        try:
            tariff_names = {
                "monthly": "Подписка на 1 месяц",
                "quarterly": "Подписка на 3 месяца",
                "half_yearly": "Подписка на 6 месяцев",
                "yearly": "Подписка на 12 месяцев",
            }
            description = tariff_names.get(payment.tariff_type, "Подписка")
            amount_kopecks = int(payment.amount * 100)

            await self.bot.send_invoice(
                chat_id=chat_id,
                title="VPN Club Pro",
                description=description,
                payload=payment.invoice_payload,
                provider_token=settings.telegram_payment_provider_token,
                currency="RUB",
                prices=[LabeledPrice(label=description, amount=amount_kopecks)],
                need_name=False,
                need_phone_number=False,
                need_email=False,
                need_shipping_address=False,
            )
            return True
        except Exception as e:
            logger.error(f"Error sending RUB invoice: {e}", exc_info=True)
            return False

    def get_tariff_price_stars(self, tariff_type: str) -> int:
        """Получение цены тарифа в Telegram Stars"""
        from app.keyboards.tariff_keyboard import TariffKeyboard
        return TariffKeyboard.get_stars_prices().get(tariff_type, 0)

    async def update_payment_status(self, payment_id: int, status: str) -> Optional[TelegramPayment]:
        """Обновление статуса платежа"""
        result = await self.session.execute(
            select(TelegramPayment).where(TelegramPayment.id == payment_id)
        )
        payment = result.scalar_one_or_none()
        
        if payment:
            payment.status = status
            await self.session.commit()
            await self.session.refresh(payment)
            
        return payment 