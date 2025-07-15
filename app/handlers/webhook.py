from aiogram import Router
from fastapi import Request, HTTPException
from app.services.payment_service import PaymentService
from app.services.subscription_service import SubscriptionService
from app.database import AsyncSessionLocal
import json
import logging

router = Router()
logger = logging.getLogger(__name__)

async def process_yookassa_webhook(request: Request):
    """Обработка webhook уведомлений от YooKassa"""
    try:
        # Получаем данные от YooKassa
        body = await request.body()
        data = json.loads(body)
        
        logger.info(f"Webhook received: {data}")
        
        # Проверяем тип события
        if data.get("event") == "payment.succeeded":
            payment_data = data.get("object", {})
            payment_id = payment_data.get("id")
            
            if not payment_id:
                raise HTTPException(status_code=400, detail="Payment ID not found")
            
            async with AsyncSessionLocal() as session:
                payment_service = PaymentService(session)
                subscription_service = SubscriptionService(session)
                
                # Проверяем статус платежа через API YooKassa
                is_paid = await payment_service.verify_payment(payment_id)
                if not is_paid:
                    logger.warning(f"Webhook: Payment {payment_id} not succeeded on YooKassa, skipping subscription creation.")
                    return {"status": "skipped"}
                
                # Обновляем статус платежа
                payment = await payment_service.update_payment_status(payment_id, "succeeded")
                
                if payment:
                    # Создаем подписку
                    subscription = await subscription_service.create_subscription(
                        payment.user_id, 
                        payment.tariff_type
                    )
                    
                    logger.info(f"Subscription created for payment {payment_id}")
                    
                    # TODO: Отправить уведомление пользователю в Telegram
                    
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 