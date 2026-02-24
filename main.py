import asyncio
import logging
import threading
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import json
import os

from config import settings
from app.database import init_db
from app.handlers import register_all_handlers
from app.scheduler import NotificationScheduler
from app.webhook import create_webhook_app
from app.middleware.maintenance import MaintenanceMiddleware
from app.vpn_forge.manager import ForgeManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные переменные
scheduler = None
forge_manager = None

# Создаем FastAPI приложение для YooKassa webhook
fastapi_app = FastAPI()

@fastapi_app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    """Обработка webhook уведомлений от YooKassa"""
    try:
        body = await request.body()
        data = json.loads(body)
        
        logger.info(f"🔔 Webhook received: {data}")
        
        # Проверяем тип события
        event_type = data.get("event")
        
        if event_type == "payment.succeeded":
            payment_data = data.get("object", {})
            payment_id = payment_data.get("id")
            
            if payment_id:
                logger.info(f"💳 Processing successful payment: {payment_id}")
                
                # Записываем webhook в файл для обработки планировщиком
                webhook_data = {
                    "payment_id": payment_id,
                    "event": "payment.succeeded",
                    "timestamp": datetime.now().isoformat()
                }
                
                # Создаем папку для webhooks если её нет
                os.makedirs("/tmp/webhooks", exist_ok=True)
                
                # Записываем webhook в файл
                with open(f"/tmp/webhooks/payment_{payment_id}.json", "w") as f:
                    json.dump(webhook_data, f)
                
                logger.info(f"📝 Successful payment webhook saved to file for processing")
                
        elif event_type == "payment.canceled":
            payment_data = data.get("object", {})
            payment_id = payment_data.get("id")
            
            if payment_id:
                logger.info(f"❌ Processing canceled payment: {payment_id}")
                
                # Записываем webhook об отмене
                webhook_data = {
                    "payment_id": payment_id,
                    "event": "payment.canceled",
                    "timestamp": datetime.now().isoformat()
                }
                
                # Создаем папку для webhooks если её нет
                os.makedirs("/tmp/webhooks", exist_ok=True)
                
                # Записываем webhook в файл
                with open(f"/tmp/webhooks/payment_canceled_{payment_id}.json", "w") as f:
                    json.dump(webhook_data, f)
                
                logger.info(f"📝 Canceled payment webhook saved to file")
                
        else:
            logger.info(f"ℹ️ Received unhandled event: {event_type}")
                    
        return JSONResponse(content={"status": "ok"})
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=400)

@fastapi_app.get("/")
async def root():
    """Корневой endpoint для проверки работы сервера"""
    return {"message": "VPN Club Pro Bot Webhook Server"}

def run_fastapi():
    """Запуск FastAPI сервера"""
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000)

async def main():
    """Основная функция запуска бота"""
    global scheduler
    
    # Создание экземпляра бота
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Устанавливаем глобальную переменную бота в app.main для доступа из хэндлеров
    import app.main as app_main
    app_main.bot = bot
    
    # Создание диспетчера
    dp = Dispatcher()
    
    # Подключение middleware
    dp.message.middleware(MaintenanceMiddleware())
    
    # Регистрация обработчиков
    register_all_handlers(dp)
    
    # Инициализация базы данных
    logger.info("Инициализация базы данных...")
    await init_db()
    
    # Запуск планировщика
    logger.info("Запуск планировщика...")
    scheduler = NotificationScheduler(bot)
    scheduler.start()
    
    # Устанавливаем глобальную переменную планировщика в app.main для доступа из хэндлеров
    app_main.scheduler = scheduler
    
    # Запуск VPN Forge
    logger.info("Инициализация VPN Forge...")
    forge_manager = ForgeManager(bot=bot)
    forge_manager.start()
    app_main.forge_manager = forge_manager
    
    # Запускаем FastAPI в отдельном потоке для YooKassa webhook
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    logger.info("FastAPI сервер запущен на порту 8000 для YooKassa webhook")
    
    try:
        # Удаление вебхука если он был установлен
        await bot.delete_webhook(drop_pending_updates=True)
        
        if settings.webhook_url:
            # Webhook режим для Telegram
            logger.info("Запуск в режиме webhook...")
            
            # Создание веб-приложения для Telegram webhook
            webhook_app = create_webhook_app()
            
            # Установка webhook
            await bot.set_webhook(
                url=f"{settings.webhook_url}/webhook/telegram",
                drop_pending_updates=True
            )
            
            # Запуск веб-сервера на другом порту (9000) для Telegram
            runner = web.AppRunner(webhook_app)
            await runner.setup()
            
            site = web.TCPSite(runner, '0.0.0.0', 9000)
            await site.start()
            
            logger.info("Telegram webhook сервер запущен на порту 9000")
            
            # Ожидание бесконечно
            await asyncio.Event().wait()
            
        else:
            # Polling режим для Telegram
            logger.info("🔄 Запуск в режиме polling...")
            await dp.start_polling(bot, allowed_updates=['message', 'callback_query', 'pre_checkout_query'])
            
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
    finally:
        # Остановка VPN Forge
        if forge_manager:
            forge_manager.stop()
        
        # Остановка планировщика
        if scheduler:
            scheduler.stop()
        
        # Закрытие сессии бота
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}") 