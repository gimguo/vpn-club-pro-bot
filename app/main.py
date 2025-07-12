import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import json
import threading

from config import settings
from app.database import init_db
from app.handlers import start, tariffs, payments, admin, support, common
from app.scheduler import NotificationScheduler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальная переменная для бота (для доступа из других модулей)
bot = None

# Создаем FastAPI приложение для webhook
fastapi_app = FastAPI()

@fastapi_app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    """Обработка webhook уведомлений от YooKassa"""
    try:
        body = await request.body()
        data = json.loads(body)
        
        logger.info(f"🔔 Webhook received: {data}")
        
        # Проверяем тип события
        if data.get("event") == "payment.succeeded":
            payment_data = data.get("object", {})
            payment_id = payment_data.get("id")
            
            if payment_id:
                # Обновляем статус платежа в базе данных
                from app.database import AsyncSessionLocal
                from app.services.payment_service import PaymentService
                from app.services.subscription_service import SubscriptionService
                from app.services.user_service import UserService
                
                async with AsyncSessionLocal() as session:
                    payment_service = PaymentService(session)
                    subscription_service = SubscriptionService(session)
                    user_service = UserService(session)
                    
                    # Обновляем статус платежа
                    payment = await payment_service.update_payment_status(payment_id, "succeeded")
                    
                    if payment:
                        logger.info(f"✅ Payment {payment_id} marked as succeeded")
                        
                        # Создаем подписку автоматически
                        try:
                            subscription = await subscription_service.create_subscription(
                                payment.user_id, 
                                payment.tariff_type
                            )
                            
                            # Отправляем уведомление пользователю
                            user = await user_service.get_user_by_id(payment.user_id)
                            if user:
                                from app.keyboards.tariff_keyboard import TariffKeyboard
                                tariff_names = TariffKeyboard.get_tariff_names()
                                
                                success_text = f"""🎉 <b>Оплата прошла успешно!</b>

🔑 Ваш ключ доступа:
<code>{subscription.access_url}</code>

📋 <b>Информация о подписке:</b>
📦 Тариф: {tariff_names[payment.tariff_type]}
🚀 Безлимитный трафик
⏰ Активна до: {subscription.end_date.strftime('%d.%m.%Y')}

📱 Не забудьте скачать приложение и настроить VPN!"""
                                
                                bot = Bot(token=settings.telegram_bot_token)
                                await bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=success_text,
                                    parse_mode="HTML"
                                )
                                await bot.session.close()
                                
                                logger.info(f"📱 Notification sent to user {user.telegram_id}")
                            
                        except Exception as e:
                            logger.error(f"❌ Error creating subscription: {e}")
                    
        return JSONResponse(content={"status": "ok"})
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@fastapi_app.get("/")
async def root():
    """Корневой endpoint для проверки работы сервера"""
    return {"message": "VPN Club Pro Bot Webhook Server"}

async def run_bot():
    """Запуск Telegram бота"""
    global bot
    
    # Инициализация базы данных
    await init_db()
    
    # Создание бота и диспетчера
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрация обработчиков
    dp.include_router(support.router)
    dp.include_router(start.router)
    dp.include_router(common.router)
    dp.include_router(tariffs.router)
    dp.include_router(payments.router)
    dp.include_router(admin.router)
    
    # Запуск планировщика уведомлений
    scheduler = NotificationScheduler(bot)
    scheduler.start()
    
    try:
        logger.info("Запуск в режиме polling...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        scheduler.stop()

def run_fastapi():
    """Запуск FastAPI сервера"""
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

async def main():
    """Основная функция запуска"""
    # Запускаем FastAPI в отдельном потоке
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    
    logger.info("FastAPI сервер запущен на порту 8000")
    
    # Запускаем бота в основном потоке
    await run_bot()

if __name__ == "__main__":
    asyncio.run(main()) 