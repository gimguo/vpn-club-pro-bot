from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.keyboards.main_keyboard import MainKeyboard
from app.keyboards.tariff_keyboard import TariffKeyboard
from app.database import AsyncSessionLocal
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from config import settings
import logging
import pytz
from datetime import datetime

logger = logging.getLogger(__name__)
router = Router()


# ─── Главное меню ──────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "🏠 <b>Главное меню</b>\n\nВыберите нужное действие:",
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()


# ─── Мой VPN (Status Dashboard) ──────────────────────────────

@router.message(F.text == "🛡️ Мой VPN")
async def my_vpn_status(message: Message):
    """Показать статус VPN — главный экран для подписчиков"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("❌ Нажмите /start для регистрации.")
            return
        
        active_sub = await subscription_service.get_active_subscription(user.id)
        
        if not active_sub:
            await message.answer(
                "❌ <b>Нет активной подписки</b>\n\n"
                "Оформите подписку, чтобы пользоваться VPN.",
                reply_markup=TariffKeyboard.get_tariffs(),
                parse_mode="HTML"
            )
            return
        
        # Получаем инфо с трафиком
        info = await subscription_service.get_subscription_info(active_sub)
        tariff_names = TariffKeyboard.get_tariff_names()
        
        remaining = info['remaining_days']
        
        # Визуальный статус-бар
        if remaining > 7:
            status = "🟢 <b>Защита активна</b>"
            bar = "▓▓▓▓▓▓▓▓▓▓"
        elif remaining > 3:
            status = "🟡 <b>Скоро истекает</b>"
            bar = "▓▓▓▓▓▓░░░░"
        elif remaining > 0:
            status = "🔴 <b>Заканчивается!</b>"
            bar = "▓▓░░░░░░░░"
        else:
            status = "⚫ <b>Истекла</b>"
            bar = "░░░░░░░░░░"
        
        text = f"""{status}
[{bar}]

📦 <b>Тариф:</b> {tariff_names.get(info['tariff_type'], 'VPN')}
📅 <b>До:</b> {info['end_date'].strftime('%d.%m.%Y')}
⏰ <b>Осталось:</b> {remaining} дн."""

        if info.get('traffic_limit_gb'):
            used = info['traffic_used_gb']
            limit = info['traffic_limit_gb']
            pct = min(100, int(used / limit * 100)) if limit > 0 else 0
            text += f"\n📊 <b>Трафик:</b> {used:.1f} / {limit} ГБ ({pct}%)"
        else:
            text += f"\n🚀 <b>Трафик:</b> безлимитный"
            if info['traffic_used_gb'] > 0:
                text += f" ({info['traffic_used_gb']:.1f} ГБ)"
        
        await message.answer(
            text,
            reply_markup=MainKeyboard.get_vpn_status_keyboard(),
            parse_mode="HTML"
        )


# ─── Бесплатный триал в одно касание ───────────────────────────

@router.message(F.text == "🆓 Попробовать бесплатно")
async def one_tap_trial(message: Message):
    """Создание пробного ключа в одно касание"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Проверка
        if user.is_trial_used:
            await message.answer(
                "⚠️ <b>Пробный период уже использован</b>\n\n"
                "Выберите подписку в «🔥 Тарифы» или пригласите друга через «👥 Друзьям» для бонусных дней!",
                parse_mode="HTML"
            )
            return
        
        active_sub = await subscription_service.get_active_subscription(user.id)
        if active_sub:
            await message.answer("✅ У вас уже есть активная подписка!")
            return
        
        try:
            # Определяем срок триала (расширенный для рефералов)
            subscription = await subscription_service.create_subscription(user.id, "trial")
            await user_service.mark_trial_used(user.id)
            
            from app.main import scheduler
            if scheduler:
                scheduler.schedule_subscription_notification(user.id, subscription.end_date)
            
            trial_days = settings.trial_days
            if user.referred_by:
                trial_days = settings.referral_trial_days
            
            await message.answer(
                f"🎉 <b>Ваш VPN готов!</b>\n\n"
                f"⏰ Активен: <b>{trial_days} дней</b>\n"
                f"📊 Трафик: {settings.trial_traffic_gb} ГБ\n\n"
                f"🔑 <b>Скопируйте ключ ниже и вставьте в приложение Outline:</b>",
                parse_mode="HTML"
            )
            
            await message.answer(
                f"<code>{subscription.access_url}</code>",
                parse_mode="HTML"
            )
            
            await message.answer(
                "👆 <b>Нажмите на ключ чтобы скопировать</b>\n\n"
                "Теперь скачайте приложение и вставьте ключ:",
                reply_markup=MainKeyboard.get_trial_success_keyboard(),
                parse_mode="HTML"
            )
            
        except Exception as e:
            logger.error(f"Error creating trial: {e}", exc_info=True)
            await message.answer("❌ Ошибка. Попробуйте позже или обратитесь в поддержку.")


# ─── Реферальная программа ──────────────────────────────────────

@router.message(F.text == "👥 Друзьям")
async def referral_menu(message: Message):
    """Экран реферальной программы"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        user = await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        ref_code = await user_service.ensure_referral_code(user)
        stats = await user_service.get_referral_stats(user.id)
    
    referral_link = f"https://t.me/{settings.bot_username}?start=ref_{ref_code}"
    
    # Формируем красивый текст
    invited = stats['referral_count']
    bonus = stats['bonus_days']
    
    # Визуальный прогресс
    level_thresholds = [
        (0, "🌱 Новичок"),
        (3, "⭐ Активист"),
        (10, "🔥 Амбассадор"),
        (25, "👑 VPN-мастер"),
        (50, "💎 Легенда")
    ]
    
    level = "🌱 Новичок"
    next_level = "⭐ Активист (3 друга)"
    for threshold, name in reversed(level_thresholds):
        if invited >= threshold:
            level = name
            idx = level_thresholds.index((threshold, name))
            if idx < len(level_thresholds) - 1:
                next_t, next_n = level_thresholds[idx + 1]
                next_level = f"{next_n} ({next_t} друзей)"
            else:
                next_level = "Максимальный уровень! 🎉"
            break
    
    text = f"""👥 <b>Приведи друга — получи VPN бесплатно!</b>

📊 <b>Ваша статистика:</b>
{level}
├ Приглашено: <b>{invited}</b> друзей
├ Бонус: <b>{bonus}</b> дней
└ До след. уровня: {next_level}

🎁 <b>Как это работает:</b>
1️⃣ Поделитесь ссылкой с другом
2️⃣ Друг получает <b>{settings.referral_trial_days} дней</b> бесплатно
3️⃣ Вы получаете <b>+{settings.referral_bonus_days} дней</b> к подписке

🔗 <b>Ваша ссылка:</b>
<code>{referral_link}</code>"""

    await message.answer(
        text,
        reply_markup=MainKeyboard.get_referral_keyboard(referral_link, ref_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "referral_info")
async def referral_info_callback(callback: CallbackQuery):
    """Реферальная программа через inline кнопку"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("Нажмите /start")
            return
        
        ref_code = await user_service.ensure_referral_code(user)
        stats = await user_service.get_referral_stats(user.id)
    
    referral_link = f"https://t.me/{settings.bot_username}?start=ref_{ref_code}"
    
    text = f"""👥 <b>Приведи друга — получи VPN бесплатно!</b>

Приглашено: <b>{stats['referral_count']}</b> | Бонус: <b>{stats['bonus_days']}</b> дней

🎁 За каждого друга: <b>+{settings.referral_bonus_days} дней</b> VPN

🔗 <b>Ваша ссылка:</b>
<code>{referral_link}</code>"""
    
    await callback.message.edit_text(
        text,
        reply_markup=MainKeyboard.get_referral_keyboard(referral_link, ref_code),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("copy_ref_"))
async def copy_referral_code(callback: CallbackQuery):
    """Показать реферальный код для копирования"""
    ref_code = callback.data.removeprefix("copy_ref_")
    referral_link = f"https://t.me/{settings.bot_username}?start=ref_{ref_code}"
    await callback.answer(f"Ссылка: {referral_link}", show_alert=True)


# ─── Скачать / Инструкция ──────────────────────────────────────

@router.message(F.text.in_({"📱 Скачать VPN", "📱 Скачать"}))
async def download_vpn(message: Message):
    """Показать ссылки для скачивания"""
    text = """📱 <b>Скачайте Outline VPN:</b>

Выберите вашу платформу:"""

    await message.answer(
        text,
        reply_markup=MainKeyboard.get_download_links(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "download_app")
async def download_app_callback(callback: CallbackQuery):
    """Скачать приложение через inline кнопку"""
    text = """📱 <b>Скачайте Outline VPN:</b>

Выберите вашу платформу:"""

    await callback.message.edit_text(
        text,
        reply_markup=MainKeyboard.get_download_links(),
        parse_mode="HTML"
    )


@router.message(F.text == "📖 Инструкция")
async def show_instructions(message: Message):
    """Показать инструкции"""
    await _show_instructions(message)


@router.callback_query(F.data == "instructions")
async def show_instructions_callback(callback: CallbackQuery):
    """Показать инструкции через callback"""
    text = """📖 <b>Как подключить VPN</b>

<b>3 простых шага:</b>
1️⃣ Скачайте Outline (кнопка выше)
2️⃣ Скопируйте VPN-ключ из бота
3️⃣ Откройте Outline → нажмите ➕ → вставьте ключ

<b>Подробные инструкции:</b>"""
    
    await callback.message.edit_text(
        text,
        reply_markup=MainKeyboard.get_instructions(),
        parse_mode="HTML"
    )


async def _show_instructions(message: Message):
    """Отправить инструкции"""
    text = """📖 <b>Как подключить VPN</b>

<b>3 простых шага:</b>
1️⃣ Скачайте Outline
2️⃣ Скопируйте VPN-ключ из бота
3️⃣ Откройте Outline → нажмите ➕ → вставьте ключ

<b>Подробные инструкции:</b>"""

    await message.answer(
        text,
        reply_markup=MainKeyboard.get_instructions(),
        parse_mode="HTML"
    )


# ─── Проверить ключ ──────────────────────────────────────────

@router.message(F.text == "🔍 Проверить ключ")
async def check_key(message: Message):
    """Проверить активный ключ пользователя"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not user:
            await message.answer("❌ Нажмите /start для регистрации.")
            return
        
        active_sub = await subscription_service.get_active_subscription(user.id)
        
        if not active_sub:
            await message.answer(
                "❌ <b>Нет активного ключа</b>\n\n"
                "Оформите подписку в «🔥 Тарифы».",
                parse_mode="HTML"
            )
            return
        
        info = await subscription_service.get_subscription_info(active_sub)
        tariff_names = TariffKeyboard.get_tariff_names()
        
        text = f"""✅ <b>Ваша подписка активна</b>

📦 Тариф: {tariff_names.get(info['tariff_type'], 'VPN')}
📅 До: {info['end_date'].strftime('%d.%m.%Y')}
⏰ Осталось: {info['remaining_days']} дн."""

        if info.get('traffic_limit_gb'):
            text += f"\n📊 Трафик: {info['traffic_used_gb']:.1f} / {info['traffic_limit_gb']} ГБ"
        else:
            text += "\n🚀 Трафик: безлимитный"

        text += "\n\n🔑 <b>Ваш ключ:</b>"

        await message.answer(text, parse_mode="HTML")
        await message.answer(
            f"<code>{active_sub.access_url}</code>",
            parse_mode="HTML"
        )


# ─── Продлить подписку ──────────────────────────────────────────

@router.message(F.text == "🔥 Продлить")
async def renew_subscription(message: Message):
    """Продление подписки — перенаправление на тарифы"""
    text = """🔄 <b>Продление подписки</b>

Выберите тариф для продления. Новый ключ будет создан автоматически:"""

    await message.answer(
        text,
        reply_markup=TariffKeyboard.get_tariffs(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "renew_subscription")
async def renew_subscription_callback(callback: CallbackQuery):
    """Продление через inline кнопку"""
    text = """🔄 <b>Продление подписки</b>

Выберите тариф:"""

    await callback.message.edit_text(
        text,
        reply_markup=TariffKeyboard.get_tariffs(),
        parse_mode="HTML"
    )


def register_common_handlers(dp):
    """Регистрация общих обработчиков"""
    dp.include_router(router)
