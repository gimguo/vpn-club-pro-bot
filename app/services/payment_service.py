from yookassa import Configuration, Payment as YooKassaPayment
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Payment, User
from config import settings
import uuid
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        Configuration.account_id = settings.yookassa_shop_id
        Configuration.secret_key = settings.yookassa_secret_key

    async def create_payment(self, user_id: int, amount: Decimal, tariff_type: str, 
                           return_url: str = None) -> Payment:
        """Создание платежа в YooKassa"""
        # Получаем email пользователя из БД
        from app.models import User
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        customer_email = user.email if user and user.email else "noreply@vpnclubpro.com"
        logger.info(f"Using email for payment: {customer_email}")
        idempotency_key = str(uuid.uuid4())
        tariff_names = {
            "monthly": "Подписка на сервис (1 месяц)",
            "quarterly": "Подписка на сервис (3 месяца)", 
            "half_yearly": "Подписка на сервис (6 месяцев)",
            "yearly": "Подписка на сервис (12 месяцев)"
        }
        payment_data = {
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": return_url or f"https://t.me/{settings.bot_username}"
            },
            "capture": True,
            "description": f"Оплата подписки VPN Club Pro - {tariff_names.get(tariff_type, tariff_type)}",
            "receipt": {
                "customer": {
                    "email": customer_email
                },
                "items": [
                    {
                        "description": tariff_names.get(tariff_type, "Подписка на сервис"),
                        "quantity": "1",
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": "1",
                        "payment_subject": "service",
                        "payment_mode": "full_payment"
                    }
                ]
            },
            "metadata": {
                "user_id": str(user_id),
                "tariff_type": tariff_type
            }
        }
        logger.info(f"Creating YooKassa payment with data: {payment_data}")
        try:
            # Создаем платеж в YooKassa
            yookassa_payment = YooKassaPayment.create(payment_data, idempotency_key)
        except Exception as e:
            logger.error(f"YooKassa payment creation failed: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"YooKassa response: {e.response.text}")
            raise
        payment = Payment(
            user_id=user_id,
            yookassa_payment_id=yookassa_payment.id,
            amount=amount,
            tariff_type=tariff_type,
            status=yookassa_payment.status,
            payment_url=yookassa_payment.confirmation.confirmation_url
        )
        self.session.add(payment)
        await self.session.commit()
        await self.session.refresh(payment)
        return payment

    async def get_payment_by_yookassa_id(self, yookassa_payment_id: str) -> Optional[Payment]:
        """Получение платежа по ID YooKassa"""
        result = await self.session.execute(
            select(Payment).where(Payment.yookassa_payment_id == yookassa_payment_id)
        )
        return result.scalar_one_or_none()

    async def update_payment_status(self, yookassa_payment_id: str, status: str) -> Optional[Payment]:
        """Обновление статуса платежа"""
        payment = await self.get_payment_by_yookassa_id(yookassa_payment_id)
        if payment:
            payment.status = status
            await self.session.commit()
            await self.session.refresh(payment)
        return payment

    def get_tariff_price(self, tariff_type: str) -> Decimal:
        """Получение цены тарифа"""
        prices = {
            "trial": Decimal(settings.trial_price),
            "monthly": Decimal(settings.monthly_price),
            "quarterly": Decimal(settings.quarterly_price),
            "half_yearly": Decimal(settings.half_yearly_price),
            "yearly": Decimal(settings.yearly_price)
        }
        return prices.get(tariff_type, Decimal("0"))

    async def verify_payment(self, payment_id: str) -> bool:
        """Проверка статуса платежа в YooKassa"""
        try:
            yookassa_payment = YooKassaPayment.find_one(payment_id)
            return yookassa_payment.status == "succeeded"
        except Exception as e:
            logger.error(f"Error verifying payment {payment_id}: {e}")
            return False

    async def get_latest_payment(self, user_id: int) -> Optional[Payment]:
        """Получение последнего платежа пользователя"""
        result = await self.session.execute(
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
        )
        return result.scalar_one_or_none() 