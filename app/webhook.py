from aiohttp import web, ClientSession
from app.services.payment_service import PaymentService
from app.services.subscription_service import SubscriptionService
from app.services.user_service import UserService
from app.database import AsyncSessionLocal
import json
import hmac
import hashlib
from config import settings
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.handlers import register_all_handlers

async def yookassa_webhook(request):
    """Обработчик webhook от YooKassa"""
    try:
        # Получаем данные из запроса
        body = await request.read()
        
        # Проверяем подпись (опционально, для безопасности)
        # signature = request.headers.get('Authorization', '')
        # if not verify_signature(body, signature):
        #     return web.Response(status=400, text="Invalid signature")
        
        data = json.loads(body.decode('utf-8'))
        
        # Проверяем тип события
        if data.get('event') != 'payment.succeeded':
            return web.Response(status=200, text="OK")
        
        payment_data = data.get('object', {})
        payment_id = payment_data.get('id')
        
        if not payment_id:
            return web.Response(status=400, text="No payment ID")
        
        # Обрабатываем успешный платеж
        async with AsyncSessionLocal() as session:
            payment_service = PaymentService(session)
            subscription_service = SubscriptionService(session)
            user_service = UserService(session)
            
            # Обновляем статус платежа
            payment = await payment_service.update_payment_status(payment_id, "succeeded")
            
            if payment:
                # Проверяем есть ли уже активная подписка у пользователя
                active_subscription = await subscription_service.get_active_subscription(payment.user_id)
                
                if not active_subscription:
                    try:
                        # Создаем подписку
                        subscription = await subscription_service.create_subscription(
                            payment.user_id,
                            payment.tariff_type
                        )
                        
                        # Отправляем уведомление пользователю
                        user = await user_service.get_user_by_telegram_id(payment.user.telegram_id)
                        if user:
                            # Здесь нужно получить экземпляр бота для отправки сообщения
                            # Это можно сделать через глобальную переменную или dependency injection
                            pass
                            
                    except Exception as e:
                        print(f"Ошибка при создании подписки: {e}")
        
        return web.Response(status=200, text="OK")
        
    except Exception as e:
        print(f"Ошибка в webhook: {e}")
        return web.Response(status=500, text="Internal Server Error")

def verify_signature(body: bytes, signature: str) -> bool:
    """Проверка подписи webhook от YooKassa"""
    try:
        # Извлекаем подпись из заголовка
        if not signature.startswith('Bearer '):
            return False
        
        received_signature = signature[7:]  # Убираем "Bearer "
        
        # Вычисляем ожидаемую подпись
        expected_signature = hmac.new(
            settings.yookassa_secret_key.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, received_signature)
        
    except Exception:
        return False

def create_webhook_app():
    """Создание веб-приложения для webhook"""
    # Создаем бота
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаем диспетчер
    dp = Dispatcher()
    
    # Регистрируем обработчики
    register_all_handlers(dp)
    
    # Создаем веб-приложение
    app = web.Application()
    
    # Добавляем обработчики
    app.router.add_post('/webhook/yookassa', yookassa_webhook)
    
    # Настраиваем webhook для Telegram
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        allowed_updates=['message', 'callback_query', 'successful_payment']
    ).register(app, path="/webhook/telegram")
    
    setup_application(app, dp, bot=bot)
    
    return app 