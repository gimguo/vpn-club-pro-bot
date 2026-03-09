import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.tariff_keyboard import TariffKeyboard
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.database import AsyncSessionLocal
from config import settings

logger = logging.getLogger(__name__)

router = Router()

# Защита от двойного клика при создании подписки (ограничено 500 записей)
_tariff_locks: dict[int, asyncio.Lock] = {}
_MAX_LOCKS = 500


@router.message(F.text.in_({"🔥 Тарифы", "🔥 Продлить"}))
async def show_tariffs(message: Message):
    """Показать тарифы"""
    text = f"""💰 <b>Выберите тариф</b>

🆓 <b>Пробный период</b> — бесплатно
   {settings.trial_days} дней · {settings.trial_traffic_gb} ГБ трафика

━━━━━━━━━━━━━━━━━━

💵 <b>Платные тарифы</b> — безлимит
   ✅ Высокая скорость
   ✅ Работает 24/7
   ✅ Все устройства"""

    await message.answer(
        text,
        reply_markup=TariffKeyboard.get_tariffs(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("tariff_"))
async def process_tariff_selection(callback: CallbackQuery):
    """Обработка выбора тарифа"""
    tariff_type = callback.data.removeprefix("tariff_")
    tariff_details = TariffKeyboard.get_tariff_details()
    detail = tariff_details.get(tariff_type)
    
    if not detail:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    
    # Защита от двойного клика
    user_tg_id = callback.from_user.id
    if user_tg_id not in _tariff_locks:
        if len(_tariff_locks) >= _MAX_LOCKS:
            _tariff_locks.clear()
        _tariff_locks[user_tg_id] = asyncio.Lock()
    
    if _tariff_locks[user_tg_id].locked():
        await callback.answer("⏳ Подождите, запрос обрабатывается...", show_alert=True)
        return

    async with _tariff_locks[user_tg_id]:
        async with AsyncSessionLocal() as session:
            user_service = UserService(session)
            subscription_service = SubscriptionService(session)

            user = await user_service.get_or_create_user(
                telegram_id=callback.from_user.id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name
            )

            # Проверяем активную подписку
            active_subscription = await subscription_service.get_active_subscription(user.id)

            if active_subscription:
                if tariff_type == "trial":
                    await callback.answer("У вас уже есть активная подписка!", show_alert=True)
                    return
                elif active_subscription.tariff_type != "trial":
                    await callback.answer("У вас уже есть платная подписка!", show_alert=True)
                    return

            if tariff_type == "trial":
                # Пробный период
                if user.is_trial_used:
                    await callback.answer("Пробный период уже использован!", show_alert=True)
                    return

                try:
                    subscription = await subscription_service.create_subscription(user.id, "trial")
                    await user_service.mark_trial_used(user.id)

                    from app.main import scheduler
                    if scheduler:
                        scheduler.schedule_subscription_notification(user.id, subscription.end_date)

                    await callback.message.edit_text(
                        f"🎉 <b>VPN-ключ готов!</b>\n\n"
                        f"⏰ Активен: {settings.trial_days} дней\n"
                        f"📊 Трафик: {settings.trial_traffic_gb} ГБ\n\n"
                        f"🔑 <b>Скопируйте ключ:</b>",
                        parse_mode="HTML"
                    )

                    await callback.message.answer(
                        f"<code>{subscription.access_url}</code>",
                        parse_mode="HTML"
                    )

                    from app.keyboards.main_keyboard import MainKeyboard
                    await callback.message.answer(
                        "👆 Нажмите чтобы скопировать, затем вставьте в Outline:",
                        reply_markup=MainKeyboard.get_trial_success_keyboard(),
                        parse_mode="HTML"
                    )

                except Exception as e:
                    logger.error(f"Trial creation failed: {e}", exc_info=True)
                    await callback.answer("Ошибка. Попробуйте позже.", show_alert=True)
            else:
                # ── Платные тарифы ──────────────────────────────
                from app.services.payment_service import PaymentService
                from app.services.telegram_payment_service import TelegramPaymentService
                payment_service = PaymentService(session)
                amount = payment_service.get_tariff_price(tariff_type)

                badge = f"\n{detail['badge']}" if detail.get('badge') else ""
                savings = ""
                if detail.get('savings'):
                    savings = f"\n💰 <b>Экономия:</b> {detail['savings']} ₽"
                per_month = int(int(amount) / (detail['days'] / 30))

                try:
                    if settings.telegram_payment_provider_token:
                        # ── Нативный Telegram Payment (3 клика) ──
                        tg_ps = TelegramPaymentService(session, callback.bot)
                        payment = await tg_ps.create_rub_payment(user.id, tariff_type)

                        text = (
                            f"📋 <b>{detail['name']}</b>{badge}\n\n"
                            f"💰 <b>Стоимость:</b> {int(amount)} ₽ ({per_month} ₽/мес){savings}\n\n"
                            f"✅ Безлимитный трафик · Макс. скорость · Все устройства\n\n"
                            f"⬇️ Нажмите <b>Оплатить</b> в сообщении ниже:"
                        )

                        stars_amount = TariffKeyboard.get_stars_prices().get(tariff_type, 0)
                        kb = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(
                                text=f"⭐ Или Stars — {stars_amount}",
                                callback_data=f"payment_stars_{tariff_type}"
                            )],
                            [InlineKeyboardButton(text="⬅️ К тарифам", callback_data="back_to_tariffs")],
                        ])
                        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
                        await tg_ps.send_rub_invoice(callback.message.chat.id, payment)
                    else:
                        # ── Fallback: YooKassa redirect ──
                        payment = await payment_service.create_payment(
                            user_id=user.id,
                            amount=amount,
                            tariff_type=tariff_type,
                            return_url=f"https://t.me/{settings.bot_username}"
                        )

                        text = (
                            f"📋 <b>{detail['name']}</b>{badge}\n\n"
                            f"💰 <b>Стоимость:</b> {int(amount)} ₽ ({per_month} ₽/мес){savings}\n\n"
                            f"✅ Безлимитный трафик · Макс. скорость · Все устройства"
                        )

                        await callback.message.edit_text(
                            text,
                            reply_markup=TariffKeyboard.get_checkout_buttons(
                                payment.payment_url, int(amount), tariff_type
                            ),
                            parse_mode="HTML"
                        )
                except Exception as e:
                    logger.error(f"Payment creation failed for {tariff_type}: {e}", exc_info=True)
                    await callback.answer("❌ Ошибка при создании платежа. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: CallbackQuery):
    """Возврат к тарифам"""
    text = f"""💰 <b>Выберите тариф</b>

🆓 <b>Пробный период</b> — бесплатно
   {settings.trial_days} дней · {settings.trial_traffic_gb} ГБ

━━━━━━━━━━━━━━━━━━

💵 <b>Платные тарифы</b> — безлимит
   ✅ Высокая скорость
   ✅ Работает 24/7"""

    await callback.message.edit_text(
        text,
        reply_markup=TariffKeyboard.get_tariffs(),
        parse_mode="HTML"
    )


def register_tariff_handlers(dp):
    """Регистрация обработчиков тарифов"""
    dp.include_router(router)
