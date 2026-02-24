from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, CommandObject
from app.keyboards.main_keyboard import MainKeyboard
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.database import AsyncSessionLocal
from config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart(deep_link=True))
async def cmd_start_deeplink(message: Message, command: CommandObject):
    """Обработчик /start с deep link (реферальная ссылка)"""
    args = command.args or ""
    referral_code = None
    
    # Парсим реферальный код: /start ref_XXXXXXXX
    if args.startswith("ref_"):
        referral_code = args[4:]
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code
        )
        
        # Обрабатываем реферал (только для новых юзеров без referred_by)
        referral_msg = ""
        if referral_code and not user.referred_by:
            success = await user_service.process_referral(user, referral_code)
            if success:
                referral_msg = f"\n\n🎁 <b>Бонус по приглашению!</b> Ваш пробный период — {settings.referral_trial_days} дней вместо {settings.trial_days}!"
                logger.info(f"Referral processed: user {user.telegram_id} via code {referral_code}")
        
        # Проверяем есть ли активная подписка
        active_sub = await subscription_service.get_active_subscription(user.id)
    
    if active_sub:
        await _send_dashboard(message, active_sub)
    else:
        await _send_welcome(message, user, referral_msg)


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code
        )
        
        active_sub = await subscription_service.get_active_subscription(user.id)
    
    if active_sub:
        await _send_dashboard(message, active_sub)
    else:
        await _send_welcome(message, user)


async def _send_welcome(message: Message, user, referral_msg: str = ""):
    """Отправка приветственного сообщения для новых/неактивных пользователей"""
    name = message.from_user.first_name or "друг"
    
    # Определяем срок триала
    trial_days = settings.trial_days
    if user.referred_by:
        trial_days = settings.referral_trial_days
    
    trial_label = f"{trial_days} дней" if trial_days != 1 else "1 день"
    
    welcome_text = f"""👋 <b>{name}, добро пожаловать!</b>

🛡️ <b>VPN Club Pro</b> — быстрый и простой VPN

Забудьте о блокировках, слежке и ограничениях.
Подключение за <b>2 клика</b> — без регистрации и настроек.

✅ Скорость без ограничений
✅ Ноль рекламы
✅ Работает на всех устройствах
✅ Серверы по всему миру{referral_msg}"""

    await message.answer(welcome_text, parse_mode="HTML")
    
    # Второе сообщение — действие
    if user.is_trial_used:
        action_text = """💡 Выберите действие в меню ниже:"""
    else:
        action_text = f"""🚀 <b>Начните прямо сейчас!</b>

Нажмите «🆓 Попробовать бесплатно» — получите VPN-ключ на <b>{trial_label}</b> за одно касание.

Или выберите подписку в «🔥 Тарифы»."""
    
    await message.answer(
        action_text,
        reply_markup=MainKeyboard.get_main_menu(is_trial_available=not user.is_trial_used),
        parse_mode="HTML"
    )


async def _send_dashboard(message: Message, subscription):
    """Отправка дашборда для пользователей с активной подпиской"""
    from app.keyboards.tariff_keyboard import TariffKeyboard
    tariff_names = TariffKeyboard.get_tariff_names()
    
    remaining = (subscription.end_date - __import__('datetime').datetime.now(__import__('pytz').UTC)).days
    
    # Визуальный статус
    if remaining > 7:
        status_icon = "🟢"
        status_text = "Защита активна"
    elif remaining > 1:
        status_icon = "🟡"
        status_text = f"Истекает через {remaining} дн."
    else:
        status_icon = "🔴"
        status_text = "Истекает сегодня!"
    
    dashboard = f"""{status_icon} <b>{status_text}</b>

📦 Тариф: {tariff_names.get(subscription.tariff_type, 'VPN')}
📅 До: {subscription.end_date.strftime('%d.%m.%Y')}
⏰ Осталось: {max(0, remaining)} дн."""

    if subscription.traffic_limit_gb:
        used = subscription.traffic_used_gb or 0
        dashboard += f"\n📊 Трафик: {used} / {subscription.traffic_limit_gb} ГБ"
    else:
        dashboard += "\n🚀 Трафик: безлимитный"
    
    await message.answer(dashboard, parse_mode="HTML")
    
    await message.answer(
        "📋 Выберите действие:",
        reply_markup=MainKeyboard.get_main_menu(has_subscription=True),
        parse_mode="HTML"
    )


def register_start_handlers(dp):
    """Регистрация обработчиков команд start"""
    dp.include_router(router)
