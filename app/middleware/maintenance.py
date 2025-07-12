import os
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from config import settings


class MaintenanceMiddleware(BaseMiddleware):
    """Middleware для проверки режима обслуживания"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем только сообщения
        if not isinstance(event, Message):
            return await handler(event, data)
        
        # Проверяем существование файла режима обслуживания
        maintenance_file = "maintenance.flag"
        if not os.path.exists(maintenance_file):
            return await handler(event, data)
        
        # Разрешаем админам пользоваться ботом в режиме обслуживания
        user_id = event.from_user.id
        
        # Главный админ
        if hasattr(settings, 'admin_id') and user_id == settings.admin_id:
            return await handler(event, data)
        
        # Проверяем админов в БД
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            from app.models import User
            
            result = await session.execute(
                select(User).where(
                    User.telegram_id == user_id,
                    User.is_admin == True,
                    User.is_active == True
                )
            )
            user = result.scalar_one_or_none()
            
            if user:
                return await handler(event, data)
        
        # Для обычных пользователей показываем сообщение о техобслуживании
        await event.answer(
            "🔧 <b>Техническое обслуживание</b>\n\n"
            "Бот временно недоступен для обслуживания.\n"
            "Попробуйте позже.",
            parse_mode="HTML"
        )
        return 