from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from app.keyboards.main_keyboard import MainKeyboard
from app.services.user_service import UserService
from app.database import AsyncSessionLocal

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Создаем или получаем пользователя
        await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code
        )
    
    # Приветственное сообщение с лого
    welcome_text_1 = """🚀 <b>Быстрый и безопасный VPN на базе Outline</b>

<b>Наш сервис обеспечивает:</b>
✅ Полную конфиденциальность  
✅ Высокую скорость
✅ Отсутствие рекламы
✅ Стабильную работу"""

    await message.answer(
        welcome_text_1,
        parse_mode="HTML"
    )

    # Второе сообщение с главным меню
    welcome_text_2 = """👋 <b>Добро пожаловать в VPN Club Pro!</b>

Здесь вы можете подключиться к VPN серверам Outline. Настройте за пару шагов и начните пользоваться уже сейчас."""

    await message.answer(
        welcome_text_2,
        reply_markup=MainKeyboard.get_main_menu(),
        parse_mode="HTML"
    )

def register_start_handlers(dp):
    """Регистрация обработчиков команд start"""
    dp.include_router(router) 