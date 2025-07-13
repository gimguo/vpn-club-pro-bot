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
import os
from datetime import datetime

from config import settings
from app.database import init_db
from app.handlers import start, tariffs, payments, admin, support, common
from app.scheduler import NotificationScheduler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальная переменная для бота (для доступа из других модулей)
bot = None
scheduler = None

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
                logger.info(f"💳 Processing payment: {payment_id}")
                
                # Записываем webhook в файл для обработки планировщиком
                webhook_data = {
                    "payment_id": payment_id,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Создаем папку для webhooks если её нет
                os.makedirs("/tmp/webhooks", exist_ok=True)
                
                # Записываем webhook в файл
                with open(f"/tmp/webhooks/payment_{payment_id}.json", "w") as f:
                    json.dump(webhook_data, f)
                
                logger.info(f"📝 Webhook saved to file for processing by scheduler")
                    
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
    global bot, scheduler
    
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
        # Форсируем деплой через GitHub Actions
        logger.info("🔄 НОВЫЙ КОД: Запуск в режиме polling с successful_payment!")
        allowed_updates = ['message', 'callback_query', 'successful_payment']
        logger.info(f"🏷️ НОВЫЙ КОД: allowed_updates = {allowed_updates}")
        await dp.start_polling(bot, allowed_updates=allowed_updates)
    finally:
        await bot.session.close()
        if scheduler:
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