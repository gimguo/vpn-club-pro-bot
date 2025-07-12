import asyncio
import logging
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Payment
from app.services.payment_service import PaymentService
from app.services.subscription_service import SubscriptionService
from yookassa import Payment as YooKassaPayment

logger = logging.getLogger(__name__)

class PaymentChecker:
    """Сервис для автоматической проверки статуса платежей"""
    
    @staticmethod
    async def check_pending_payments():
        """Проверяет все pending платежи"""
        async with AsyncSessionLocal() as session:
            payment_service = PaymentService(session)
            subscription_service = SubscriptionService(session)
            
            # Получаем все pending платежи
            result = await session.execute(
                select(Payment).where(Payment.status == "pending")
            )
            pending_payments = result.scalars().all()
            
            logger.info(f"Checking {len(pending_payments)} pending payments")
            
            for payment in pending_payments:
                try:
                    # Проверяем статус в YooKassa
                    yookassa_payment = YooKassaPayment.find_one(payment.yookassa_payment_id)
                    
                    if yookassa_payment.status == "succeeded":
                        # Обновляем статус платежа
                        await payment_service.update_payment_status(
                            payment.yookassa_payment_id, 
                            "succeeded"
                        )
                        
                        # Создаем подписку
                        subscription = await subscription_service.create_subscription(
                            payment.user_id,
                            payment.tariff_type
                        )
                        
                        logger.info(f"Payment {payment.yookassa_payment_id} succeeded, subscription created")
                        
                        # TODO: Отправить уведомление пользователю в Telegram
                        
                    elif yookassa_payment.status in ["canceled", "failed"]:
                        # Обновляем статус на неуспешный
                        await payment_service.update_payment_status(
                            payment.yookassa_payment_id,
                            yookassa_payment.status
                        )
                        
                        logger.info(f"Payment {payment.yookassa_payment_id} failed/canceled")
                        
                except Exception as e:
                    logger.error(f"Error checking payment {payment.yookassa_payment_id}: {e}")
    
    @staticmethod
    async def start_periodic_check(interval_minutes: int = 5):
        """Запускает периодическую проверку платежей"""
        while True:
            try:
                await PaymentChecker.check_pending_payments()
            except Exception as e:
                logger.error(f"Error in periodic payment check: {e}")
            
            await asyncio.sleep(interval_minutes * 60) 