from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from app.keyboards.tariff_keyboard import TariffKeyboard
from app.keyboards.payment_keyboard import PaymentKeyboard
from app.services.user_service import UserService
from app.services.payment_service import PaymentService
from app.services.telegram_payment_service import TelegramPaymentService
from app.services.subscription_service import SubscriptionService
from app.database import AsyncSessionLocal
from config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()


async def _send_stars_invoice_flow(callback: CallbackQuery, tariff_type: str):
    """Создать и сразу отправить Stars invoice без промежуточного шага подтверждения."""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        telegram_payment_service = TelegramPaymentService(session, callback.bot)

        user = await user_service.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )

        try:
            payment = await telegram_payment_service.create_stars_payment(
                user_id=user.id,
                tariff_type=tariff_type
            )
            success = await telegram_payment_service.send_stars_invoice(
                chat_id=callback.message.chat.id,
                payment=payment
            )

            if success:
                await callback.message.edit_text(
                    f"⭐ <b>Счёт отправлен</b>\n\n"
                    f"📋 Тариф: {TariffKeyboard.get_tariff_names().get(tariff_type, 'VPN')}\n"
                    f"💡 Откройте окно оплаты выше и подтвердите покупку.",
                    reply_markup=PaymentKeyboard.get_payment_pending(),
                    parse_mode="HTML"
                )
            else:
                await callback.answer("❌ Ошибка при отправке invoice", show_alert=True)
        except Exception as e:
            logger.error(f"Error creating Stars payment: {e}", exc_info=True)
            await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)


async def _send_card_invoice_flow(callback: CallbackQuery, tariff_type: str):
    """Создать и сразу отправить Telegram invoice для оплаты картой."""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        telegram_payment_service = TelegramPaymentService(session, callback.bot)

        user = await user_service.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )

        try:
            amount = telegram_payment_service.get_tariff_price(tariff_type)
            payment = await telegram_payment_service.create_card_payment(
                user_id=user.id,
                amount=amount,
                tariff_type=tariff_type
            )
            success = await telegram_payment_service.send_card_invoice(
                chat_id=callback.message.chat.id,
                payment=payment
            )

            if success:
                await callback.message.edit_text(
                    f"💳 <b>Счёт отправлен</b>\n\n"
                    f"📋 Тариф: {TariffKeyboard.get_tariff_names().get(tariff_type, 'VPN')}\n"
                    f"💡 Откройте окно оплаты выше и завершите покупку.",
                    reply_markup=PaymentKeyboard.get_payment_pending(),
                    parse_mode="HTML"
                )
            else:
                await callback.answer("❌ Ошибка при создании платежа", show_alert=True)
        except Exception as e:
            logger.error(f"Error creating card payment: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при создании платежа", show_alert=True)


async def _send_yookassa_payment_flow(callback: CallbackQuery, tariff_type: str):
    """Создать YooKassa payment и показать пользователю прямую ссылку на оплату."""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        payment_service = PaymentService(session)

        user = await user_service.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )

        amount = payment_service.get_tariff_price(tariff_type)

        try:
            payment = await payment_service.create_payment(
                user_id=user.id,
                amount=amount,
                tariff_type=tariff_type,
                return_url=f"https://t.me/{settings.bot_username}"
            )

            tariff_name = TariffKeyboard.get_tariff_names().get(tariff_type, "Неизвестный тариф")
            text = f"""💳 <b>Оплата подписки</b>

📋 <b>Тариф:</b> {tariff_name}
💰 <b>Сумма:</b> {amount} ₽

Нажмите кнопку ниже и завершите оплату в YooKassa."""

            await callback.message.edit_text(
                text,
                reply_markup=TariffKeyboard.get_payment_url_button(payment.payment_url),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"YooKassa payment creation failed: {e}", exc_info=True)
            await callback.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    """Legacy callback: сразу открываем оплату YooKassa без лишнего шага."""
    tariff_type = callback.data.removeprefix("pay_")
    await _send_yookassa_payment_flow(callback, tariff_type)

@router.callback_query(F.data.startswith("payment_yookassa_"))
async def process_yookassa_payment(callback: CallbackQuery):
    """Обработка создания платежа через YooKassa"""
    tariff_type = callback.data.removeprefix("payment_yookassa_")
    await _send_yookassa_payment_flow(callback, tariff_type)

@router.callback_query(F.data.startswith("payment_stars_"))
async def process_stars_payment(callback: CallbackQuery):
    """Быстрая оплата через Telegram Stars"""
    tariff_type = callback.data.removeprefix("payment_stars_")
    await _send_stars_invoice_flow(callback, tariff_type)

@router.callback_query(F.data.startswith("confirm_stars_"))
async def confirm_stars_payment(callback: CallbackQuery):
    """Legacy fallback: подтверждение оплаты через Stars"""
    tariff_type = callback.data.removeprefix("confirm_stars_")
    await _send_stars_invoice_flow(callback, tariff_type)

@router.callback_query(F.data.startswith("payment_card_"))
async def process_card_payment(callback: CallbackQuery):
    """Быстрая оплата банковской картой"""
    tariff_type = callback.data.removeprefix("payment_card_")
    await _send_card_invoice_flow(callback, tariff_type)

@router.callback_query(F.data.startswith("confirm_card_"))
async def confirm_card_payment(callback: CallbackQuery):
    """Legacy fallback: подтверждение оплаты картой"""
    tariff_type = callback.data.removeprefix("confirm_card_")
    await _send_card_invoice_flow(callback, tariff_type)

@router.callback_query(F.data == "check_payment")
async def check_payment_status(callback: CallbackQuery):
    """Проверка статуса платежа"""
    try:
        async with AsyncSessionLocal() as session:
            user_service = UserService(session)
            payment_service = PaymentService(session)
            subscription_service = SubscriptionService(session)
            
            user = await user_service.get_user_by_telegram_id(callback.from_user.id)
            if not user:
                await callback.answer("❌ Пользователь не найден")
                return
            
            # Проверяем: может подписка уже создана (webhook обработал раньше)
            active_sub = await subscription_service.get_active_subscription(user.id)
            if active_sub:
                tariff_names = TariffKeyboard.get_tariff_names()
                await callback.message.edit_text(
                    f"✅ <b>Подписка уже активна!</b>\n\n"
                    f"📦 Тариф: {tariff_names.get(active_sub.tariff_type, 'VPN')}\n"
                    f"⏰ До: {active_sub.end_date.strftime('%d.%m.%Y')}",
                    parse_mode="HTML"
                )
                await callback.message.answer(
                    f"🔑 <b>Ваш ключ:</b>\n<code>{active_sub.access_url}</code>",
                    parse_mode="HTML"
                )
                return
            
            # Получаем последний платеж
            latest_payment = await payment_service.get_latest_payment(user.id)
            
            if not latest_payment:
                await callback.message.edit_text(
                    "❌ Платеж не найден. Попробуйте создать новый.",
                    reply_markup=TariffKeyboard.get_tariffs()
                )
                return
                
            # Проверяем статус в YooKassa
            is_paid = await payment_service.verify_payment(latest_payment.yookassa_payment_id)
            
            if is_paid:
                await payment_service.update_payment_status(
                    latest_payment.yookassa_payment_id, "succeeded"
                )
                
                subscription = await subscription_service.create_subscription(
                    user.id, latest_payment.tariff_type
                )
                
                from app.main import scheduler
                if scheduler:
                    scheduler.schedule_subscription_notification(user.id, subscription.end_date)
                
                await callback.message.edit_text(
                    "🎉 <b>Оплата прошла успешно!</b>\n\n🔑 <b>Ваш ключ доступа:</b>",
                    parse_mode="HTML"
                )
                await callback.message.answer(f"<code>{subscription.access_url}</code>", parse_mode="HTML")
                
                tariff_names = TariffKeyboard.get_tariff_names()
                await callback.message.answer(
                    f"📦 Тариф: {tariff_names.get(latest_payment.tariff_type, 'VPN')}\n"
                    f"🚀 Безлимитный трафик\n"
                    f"⏰ Активна до: {subscription.end_date.strftime('%d.%m.%Y')}",
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    "⏳ Платеж ещё не поступил. Нажмите кнопку для оплаты.",
                    reply_markup=TariffKeyboard.get_payment_url_button(latest_payment.payment_url)
                )
                
    except Exception as e:
        logger.error(f"Error checking payment: {e}")
        await callback.message.edit_text(
            "❌ Ошибка при проверке платежа. Попробуйте позже.",
            reply_markup=TariffKeyboard.get_tariffs()
        )

@router.callback_query(F.data == "get_vpn_key")
async def get_vpn_key(callback: CallbackQuery):
    """Показать текущий VPN ключ"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        active_sub = await subscription_service.get_active_subscription(user.id)
        if not active_sub:
            await callback.answer("❌ Нет активной подписки", show_alert=True)
            return
        
        await callback.message.answer(
            f"🔑 <b>Ваш VPN-ключ:</b>\n\n<code>{active_sub.access_url}</code>\n\n"
            f"⏰ Активен до: {active_sub.end_date.strftime('%d.%m.%Y')}",
            parse_mode="HTML"
        )
        await callback.answer()

@router.callback_query(F.data == "my_subscriptions")
async def my_subscriptions(callback: CallbackQuery):
    """Показать подписки пользователя"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        active_sub = await subscription_service.get_active_subscription(user.id)
        if not active_sub:
            await callback.message.edit_text(
                "❌ <b>Нет активной подписки</b>\n\nОформите подписку в разделе «Тарифы».",
                reply_markup=TariffKeyboard.get_tariffs(),
                parse_mode="HTML"
            )
            return
        
        info = await subscription_service.get_subscription_info(active_sub)
        tariff_names = TariffKeyboard.get_tariff_names()
        
        text = f"📊 <b>Ваша подписка</b>\n\n"
        text += f"📦 Тариф: {tariff_names.get(info['tariff_type'], 'VPN')}\n"
        text += f"📅 До: {info['end_date'].strftime('%d.%m.%Y')}\n"
        text += f"⏰ Осталось: {info['remaining_days']} дн.\n"
        
        if info.get('traffic_limit_gb'):
            text += f"📊 Трафик: {info['traffic_used_gb']:.1f} / {info['traffic_limit_gb']} ГБ"
        else:
            text += f"🚀 Трафик: безлимитный ({info['traffic_used_gb']:.1f} ГБ использовано)"
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Показать ключ", callback_data="get_vpn_key")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery):
    """Отмена платежа"""
    await callback.message.edit_text(
        "❌ Платёж отменён.\n\nВыберите другой тариф:",
        reply_markup=TariffKeyboard.get_tariffs(),
        parse_mode="HTML"
    )

@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Обработка pre_checkout_query — обязательный шаг для Telegram Payments"""
    try:
        logger.info(f"📋 [PRE_CHECKOUT] Received pre_checkout_query from user {pre_checkout_query.from_user.id}")
        logger.info(f"📋 [PRE_CHECKOUT] Payload: {pre_checkout_query.invoice_payload}")
        logger.info(f"📋 [PRE_CHECKOUT] Currency: {pre_checkout_query.currency}, Amount: {pre_checkout_query.total_amount}")
        
        # Проверяем, что платеж существует в БД
        async with AsyncSessionLocal() as session:
            telegram_payment_service = TelegramPaymentService(session, pre_checkout_query.bot)
            payment = await telegram_payment_service.get_payment_by_payload(pre_checkout_query.invoice_payload)
            
            if payment and payment.status == "pending":
                await pre_checkout_query.answer(ok=True)
                logger.info(f"✅ [PRE_CHECKOUT] Approved for payload: {pre_checkout_query.invoice_payload}")
            else:
                await pre_checkout_query.answer(ok=False, error_message="Платёж не найден или уже обработан")
                logger.warning(f"❌ [PRE_CHECKOUT] Rejected: payment not found or already processed")
    except Exception as e:
        logger.error(f"❌ [PRE_CHECKOUT] Error: {e}", exc_info=True)
        await pre_checkout_query.answer(ok=False, error_message="Ошибка при проверке платежа")

@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Обработка успешного платежа через Telegram Payments"""
    try:
        payment_info = message.successful_payment
        logger.info(f"🎉 [SUCCESS_PAYMENT] Received successful payment from user {message.from_user.id}")
        logger.info(f"💰 [SUCCESS_PAYMENT] Payment details: {payment_info.total_amount} {payment_info.currency}")
        logger.info(f"📦 [SUCCESS_PAYMENT] Payload: {payment_info.invoice_payload}")
        logger.info(f"🏷️ [SUCCESS_PAYMENT] Telegram charge ID: {payment_info.telegram_payment_charge_id}")
        logger.info(f"🔑 [SUCCESS_PAYMENT] Provider charge ID: {payment_info.provider_payment_charge_id}")
        
        async with AsyncSessionLocal() as session:
            user_service = UserService(session)
            telegram_payment_service = TelegramPaymentService(session, message.bot)
            subscription_service = SubscriptionService(session)
            
            # Получаем пользователя
            user = await user_service.get_user_by_telegram_id(message.from_user.id)
            if not user:
                logger.error(f"❌ [SUCCESS_PAYMENT] User not found for telegram_id {message.from_user.id}")
                await message.reply("❌ Пользователь не найден")
                return
            
            logger.info(f"👤 [SUCCESS_PAYMENT] Found user: ID {user.id}, telegram_id {user.telegram_id}")
            
            # Обрабатываем успешный платеж
            successful_payment_data = {
                "telegram_payment_charge_id": message.successful_payment.telegram_payment_charge_id,
                "provider_payment_charge_id": message.successful_payment.provider_payment_charge_id,
                "invoice_payload": message.successful_payment.invoice_payload,
                "currency": message.successful_payment.currency,
                "total_amount": message.successful_payment.total_amount
            }
            
            logger.info(f"📊 [SUCCESS_PAYMENT] Processing payment data: {successful_payment_data}")
            
            payment = await telegram_payment_service.process_successful_payment(successful_payment_data)
            
            if not payment:
                logger.error("❌ [SUCCESS_PAYMENT] Failed to process successful payment - payment not found by payload")
                await message.reply("❌ Ошибка при обработке платежа - платеж не найден")
                return
            
            logger.info(f"✅ [SUCCESS_PAYMENT] Payment processed successfully: ID {payment.id}, type: {payment.payment_type}, status: {payment.status}")
            
            # Создаем подписку
            logger.info(f"📋 [SUCCESS_PAYMENT] Creating subscription for user {user.id}, tariff: {payment.tariff_type}")
            subscription = await subscription_service.create_subscription(
                user.id, 
                payment.tariff_type
            )
            
            logger.info(f"🎯 [SUCCESS_PAYMENT] Subscription created: ID {subscription.id}, expires: {subscription.end_date}")
            
            # Планируем уведомление об истечении
            try:
                from app.main import scheduler
                if scheduler:
                    scheduler.schedule_subscription_notification(user.id, subscription.end_date)
                    logger.info(f"⏰ [SUCCESS_PAYMENT] Scheduled notification for user {user.id}")
            except Exception as e:
                logger.error(f"❌ [SUCCESS_PAYMENT] Failed to schedule notification: {e}")
            
            # Отправляем уведомление об успешной оплате
            payment_type_names = {
                "stars": "⭐ Telegram Stars",
                "card": "💳 Банковская карта"
            }
            
            success_text = f"""🎉 <b>Оплата прошла успешно!</b>

💳 <b>Способ оплаты:</b> {payment_type_names.get(payment.payment_type, 'Неизвестный')}
💰 <b>Сумма:</b> {payment.amount} {payment.currency}
📋 <b>Тариф:</b> {TariffKeyboard.get_tariff_names().get(payment.tariff_type, 'Неизвестный')}

🔑 <b>Ваш ключ доступа:</b>"""
            
            logger.info(f"📨 [SUCCESS_PAYMENT] Sending success message to user {user.id}")
            await message.reply(success_text, parse_mode="HTML")
            await message.reply(f"<code>{subscription.access_url}</code>", parse_mode="HTML")
            
            info_text = f"""📋 <b>Информация о подписке:</b>
🚀 Безлимитный трафик
⏰ Активна до: {subscription.end_date.strftime('%d.%m.%Y')}

📱 Не забудьте скачать приложение и настроить VPN!"""
            
            await message.reply(
                info_text, 
                parse_mode="HTML",
                reply_markup=PaymentKeyboard.get_payment_success()
            )
            
            logger.info(f"✅ [SUCCESS_PAYMENT] Process completed successfully for user {user.id}")
            
    except Exception as e:
        logger.error(f"❌ [SUCCESS_PAYMENT] Error processing successful payment: {e}", exc_info=True)
        await message.reply(f"❌ Произошла ошибка при обработке платежа: {str(e)[:100]}")

@router.callback_query(F.data.startswith("payment_methods_"))
async def back_to_payment_methods(callback: CallbackQuery):
    """Возврат к выбору способа оплаты"""
    tariff_type = callback.data.removeprefix("payment_methods_")
    
    text = f"""💳 <b>Оплата подписки</b>

📋 <b>Тариф:</b> {TariffKeyboard.get_tariff_names().get(tariff_type, 'Неизвестный')}

Доступные способы оплаты через YooKassa:
• Банковские карты (Visa, MasterCard, МИР)
• СБП (Система быстрых платежей)
• ЮMoney
• SberPay
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=PaymentKeyboard.get_payment_methods(tariff_type),
        parse_mode="HTML"
    )

def register_payment_handlers(dp):
    """Регистрация обработчиков платежей"""
    dp.include_router(router) 