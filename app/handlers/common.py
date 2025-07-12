from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from app.keyboards.main_keyboard import MainKeyboard
from app.keyboards.support_keyboard import SupportKeyboard
from app.database import AsyncSessionLocal
from app.services import UserService
from app.services.subscription_service import SubscriptionService

import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("start"))
async def start_command(message: Message):
    """Обработчик команды /start"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        user = await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        welcome_text = f"""👋 Добро пожаловать в VPN Club Pro!

🚀 Быстрый и безопасный VPN для любых задач
🌍 Серверы по всему миру
🔒 Полная анонимность
⚡ Безлимитный трафик

Выберите действие:"""

        await message.answer(
            welcome_text,
            reply_markup=MainKeyboard.get_main_keyboard(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    welcome_text = """🏠 <b>Главное меню</b>

Выберите нужное действие:"""
    
    await callback.message.edit_text(
        welcome_text,
        reply_markup=MainKeyboard.get_main_keyboard(),
        parse_mode="HTML"
    )



@router.message(F.text == "📱 Скачать VPN")
async def download_vpn(message: Message):
    """Показать ссылки для скачивания"""
    text = """📱 <b>Скачайте приложение Outline VPN:</b>

Выберите подходящую версию для вашего устройства:"""

    await message.answer(
        text,
        reply_markup=MainKeyboard.get_download_links(),
        parse_mode="HTML"
    )

@router.message(F.text == "📖 Инструкция")
async def show_instructions(message: Message):
    """Показать инструкции"""
    await show_instructions_menu(message)

@router.callback_query(F.data == "instructions")
async def show_instructions_callback(callback: CallbackQuery):
    """Показать инструкции через callback"""
    await show_instructions_menu(callback.message)

async def show_instructions_menu(message):
    """Показать меню инструкций"""
    text = """📖 <b>Инструкции по настройке VPN</b>

Выберите подходящую инструкцию для вашего устройства:"""

    await message.answer(
        text,
        reply_markup=MainKeyboard.get_instructions(),
        parse_mode="HTML"
    )

@router.message(F.text == "🔍 Проверить ключ")
async def check_key(message: Message):
    """Проверить активный ключ пользователя"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("❌ Пользователь не найден. Нажмите /start для регистрации.")
            return
        
        active_subscription = await subscription_service.get_active_subscription(user.id)
        
        if not active_subscription:
            text = """❌ <b>У вас нет активного ключа</b>

Перейдите в раздел "Тарифы", чтобы получить доступ к VPN."""
            
            await message.answer(text, parse_mode="HTML")
            return
        
        # Получаем информацию о подписке
        subscription_info = await subscription_service.get_subscription_info(active_subscription)
        
        tariff_names = {
            "trial": "Пробный период",
            "monthly": "1 месяц",
            "quarterly": "3 месяца", 
            "half_yearly": "6 месяцев",
            "yearly": "12 месяцев"
        }
        
        # Формируем сообщение
        text = f"""✅ <b>Информация о вашей подписке</b>

📦 <b>Тариф:</b> {tariff_names.get(subscription_info['tariff_type'], 'Неизвестный')}
📅 <b>Активна до:</b> {subscription_info['end_date'].strftime('%d.%m.%Y')}
⏰ <b>Осталось дней:</b> {subscription_info['remaining_days']}"""

        # Добавляем информацию о трафике для пробного периода
        if subscription_info.get('traffic_limit_gb'):
            text += f"\n📊 <b>Использовано трафика:</b> {subscription_info['traffic_used_gb']:.2f} из {subscription_info['traffic_limit_gb']} ГБ"
        else:
            text += f"\n🚀 <b>Трафик:</b> Безлимитный"
            if subscription_info['traffic_used_gb'] > 0:
                text += f" (использовано: {subscription_info['traffic_used_gb']:.2f} ГБ)"

        text += "\n\n🔑 <b>Ваш ключ доступа:</b>"

        await message.answer(text, parse_mode="HTML")
        
        # Отдельно отправляем только ключ для удобства копирования
        await message.answer(
            f"<code>{active_subscription.access_url}</code>",
            parse_mode="HTML"
        )

def register_common_handlers(dp):
    """Регистрация общих обработчиков"""
    dp.include_router(router) 