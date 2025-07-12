from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
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

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    """Обработка выбора способа оплаты"""
    tariff_type = callback.data.split("_")[1]
    
    # Показываем способы оплаты
    text = f"""💳 <b>Выберите способ оплаты</b>

📋 <b>Тариф:</b> {TariffKeyboard.get_tariff_names().get(tariff_type, 'Неизвестный')}

💡 <b>Рекомендуем:</b>
⭐ <b>Telegram Stars</b> - мгновенная оплата прямо в боте
💳 <b>Банковская карта</b> - быстро и безопасно
🥇 <b>YooKassa</b> - привычные рубли
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=PaymentKeyboard.get_payment_methods(tariff_type),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("payment_yookassa_"))
async def process_yookassa_payment(callback: CallbackQuery):
    """Обработка создания платежа через YooKassa"""
    tariff_type = callback.data.split("_")[2]
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        payment_service = PaymentService(session)
        
        user = await user_service.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )
        
        # Получаем цену тарифа
        amount = payment_service.get_tariff_price(tariff_type)
        
        try:
            print(f"🔍 DEBUG: About to create payment for user {user.id}, amount {amount}, tariff {tariff_type}")
            # Создаем платеж
            payment = await payment_service.create_payment(
                user_id=user.id,
                amount=amount,
                tariff_type=tariff_type,
                return_url=f"https://t.me/{settings.bot_username}"
            )
            print(f"🔍 DEBUG: Payment created successfully: {payment.yookassa_payment_id}")
            
            print(f"🔍 DEBUG: About to get tariff names")
            tariff_names = TariffKeyboard.get_tariff_names()
            print(f"🔍 DEBUG: Got tariff names: {tariff_names}")
            
            tariff_name = tariff_names.get(tariff_type, "Неизвестный тариф")
            print(f"🔍 DEBUG: Tariff name for {tariff_type}: {tariff_name}")
            
            text = f"""💳 <b>Оплата подписки</b>

📋 <b>Тариф:</b> {tariff_name}
💰 <b>Сумма:</b> {amount} ₽

Нажмите кнопку "Оплатить" и после успешной оплаты вернитесь в бот для получения VPN-ключа."""
            
            print(f"🔍 DEBUG: Text formatted successfully")
            
            print(f"🔍 DEBUG: About to edit message with payment URL: {payment.payment_url}")
            
            try:
                keyboard = TariffKeyboard.get_payment_url_button(payment.payment_url)
                print(f"🔍 DEBUG: Keyboard created successfully")
                
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                print(f"🔍 DEBUG: Message edited successfully")
            except Exception as edit_error:
                print(f"🔍 DEBUG: Error editing message: {edit_error}")
                print(f"🔍 DEBUG: Error type: {type(edit_error)}")
                raise edit_error
            
        except Exception as e:
            print(f"🔍 DEBUG: Exception caught: {e}")
            print(f"🔍 DEBUG: Exception type: {type(e)}")
            import traceback
            print(f"🔍 DEBUG: Traceback: {traceback.format_exc()}")
            await callback.answer("Ошибка при создании платежа. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data.startswith("payment_stars_"))
async def process_stars_payment(callback: CallbackQuery):
    """Обработка оплаты через Telegram Stars"""
    tariff_type = callback.data.split("_")[2]
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        telegram_payment_service = TelegramPaymentService(session, callback.bot)
        
        user = await user_service.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )
        
        # Получаем цену тарифа в Stars
        stars_amount = telegram_payment_service.get_tariff_price_stars(tariff_type)
        
        text = f"""⭐ <b>Оплата через Telegram Stars</b>

📋 <b>Тариф:</b> {TariffKeyboard.get_tariff_names().get(tariff_type, 'Неизвестный')}
💰 <b>Стоимость:</b> {stars_amount} ⭐ Stars

✨ <b>Преимущества:</b>
• Мгновенная оплата
• Безопасность от Telegram
• Не покидаете бот"""
        
        await callback.message.edit_text(
            text,
            reply_markup=PaymentKeyboard.get_stars_payment_confirm(tariff_type),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("confirm_stars_"))
async def confirm_stars_payment(callback: CallbackQuery):
    """Подтверждение оплаты через Stars"""
    tariff_type = callback.data.split("_")[2]
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        telegram_payment_service = TelegramPaymentService(session, callback.bot)
        
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        try:
            logger.info(f"Creating Stars payment for user {user.id}, tariff {tariff_type}")
            
            # Создаем платеж
            payment = await telegram_payment_service.create_stars_payment(
                user_id=user.id,
                tariff_type=tariff_type
            )
            
            logger.info(f"Stars payment created: {payment.id}, amount: {payment.amount} {payment.currency}")
            
            # Отправляем invoice
            success = await telegram_payment_service.send_stars_invoice(
                chat_id=callback.message.chat.id,
                payment=payment
            )
            
            if success:
                logger.info(f"Stars invoice sent successfully to chat {callback.message.chat.id}")
                await callback.message.edit_text(
                    "⭐ Invoice отправлен! Нажмите кнопку оплаты выше ⬆️",
                    reply_markup=PaymentKeyboard.get_payment_pending()
                )
            else:
                logger.error("Failed to send Stars invoice")
                await callback.answer("❌ Ошибка при отправке invoice", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error creating Stars payment: {e}", exc_info=True)
            await callback.answer(f"❌ Ошибка: {str(e)[:100]}", show_alert=True)

@router.callback_query(F.data.startswith("payment_card_"))
async def process_card_payment(callback: CallbackQuery):
    """Обработка оплаты банковской картой"""
    tariff_type = callback.data.split("_")[2]
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        telegram_payment_service = TelegramPaymentService(session, callback.bot)
        
        user = await user_service.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )
        
        # Получаем цену тарифа в USD
        amount = telegram_payment_service.get_tariff_price(tariff_type)
        
        text = f"""💳 <b>Оплата банковской картой</b>

📋 <b>Тариф:</b> {TariffKeyboard.get_tariff_names().get(tariff_type, 'Неизвестный')}
💰 <b>Стоимость:</b> ${amount:.2f}

🔒 <b>Преимущества:</b>
• Безопасные платежи
• Поддержка всех карт
• Быстрое зачисление"""
        
        await callback.message.edit_text(
            text,
            reply_markup=PaymentKeyboard.get_card_payment_confirm(tariff_type, amount),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("confirm_card_"))
async def confirm_card_payment(callback: CallbackQuery):
    """Подтверждение оплаты картой"""
    tariff_type = callback.data.split("_")[2]
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        telegram_payment_service = TelegramPaymentService(session, callback.bot)
        
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден")
            return
        
        try:
            # Получаем цену тарифа
            amount = telegram_payment_service.get_tariff_price(tariff_type)
            
            # Создаем платеж
            payment = await telegram_payment_service.create_card_payment(
                user_id=user.id,
                amount=amount,
                tariff_type=tariff_type
            )
            
            # Отправляем invoice
            success = await telegram_payment_service.send_card_invoice(
                chat_id=callback.message.chat.id,
                payment=payment
            )
            
            if success:
                await callback.message.edit_text(
                    "💳 Invoice отправлен! Нажмите кнопку оплаты выше ⬆️",
                    reply_markup=PaymentKeyboard.get_payment_pending()
                )
            else:
                await callback.answer("❌ Ошибка при создании платежа", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error creating card payment: {e}")
            await callback.answer("❌ Ошибка при создании платежа", show_alert=True)

@router.callback_query(F.data == "check_payment")
async def check_payment_status(callback: CallbackQuery):
    """Проверка статуса платежа"""
    try:
        # Получаем пользователя
        async with AsyncSessionLocal() as session:
            user_service = UserService(session)
            payment_service = PaymentService(session)
            subscription_service = SubscriptionService(session)
            
            user = await user_service.get_user_by_telegram_id(callback.from_user.id)
            if not user:
                await callback.answer("❌ Пользователь не найден")
                return
            
            # Получаем последний платеж
            latest_payment = await payment_service.get_latest_payment(user.id)
            
            if not latest_payment:
                await callback.message.edit_text(
                    "❌ Платеж не найден. Попробуйте создать новый платеж.",
                    reply_markup=TariffKeyboard.get_tariff_keyboard()
                )
                return
                
            # Проверяем статус в YooKassa
            is_paid = await payment_service.verify_payment(latest_payment.yookassa_payment_id)
            
            if is_paid:
                # Обновляем статус платежа
                await payment_service.update_payment_status(
                    latest_payment.yookassa_payment_id,
                    "succeeded"
                )
                
                # Создаем подписку
                subscription = await subscription_service.create_subscription(
                    user.id, 
                    latest_payment.tariff_type
                )
                
                # Планируем уведомление об истечении
                from app.main import scheduler
                if scheduler:
                    scheduler.schedule_subscription_notification(user.id, subscription.end_date)
                
                success_text = """🎉 <b>Оплата прошла успешно!</b>

🔑 <b>Ваш ключ доступа:</b>"""
                
                await callback.message.edit_text(success_text, parse_mode="HTML")
                await callback.message.answer(f"<code>{subscription.access_url}</code>", parse_mode="HTML")
                
                tariff_names = TariffKeyboard.get_tariff_names()
                info_text = f"""📋 <b>Информация о подписке:</b>
📦 Тариф: {tariff_names[latest_payment.tariff_type]}
🚀 Безлимитный трафик
⏰ Активна до: {subscription.end_date.strftime('%d.%m.%Y')}

📱 Не забудьте скачать приложение и настроить VPN!"""
                
                await callback.message.answer(info_text, parse_mode="HTML")
                
            else:
                # Если платеж еще не прошел, показываем кнопку оплаты
                await callback.message.edit_text(
                    "⏳ Платеж еще не поступил. Нажмите кнопку ниже для оплаты.",
                    reply_markup=TariffKeyboard.get_payment_url_button(latest_payment.payment_url)
                )
                
    except Exception as e:
        logger.error(f"Error checking payment: {e}")
        await callback.message.edit_text(
            "❌ Произошла ошибка при проверке платежа. Попробуйте позже.",
            reply_markup=TariffKeyboard.get_tariff_keyboard()
        )

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
            
            logger.info(f"🎯 [SUCCESS_PAYMENT] Subscription created: ID {subscription.id}, expires: {subscription.expires_at}")
            
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
    tariff_type = callback.data.split("_")[2]
    
    text = f"""💳 <b>Выберите способ оплаты</b>

📋 <b>Тариф:</b> {TariffKeyboard.get_tariff_names().get(tariff_type, 'Неизвестный')}

💡 <b>Рекомендуем:</b>
⭐ <b>Telegram Stars</b> - мгновенная оплата прямо в боте
💳 <b>Банковская карта</b> - быстро и безопасно
🥇 <b>YooKassa</b> - привычные рубли
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=PaymentKeyboard.get_payment_methods(tariff_type),
        parse_mode="HTML"
    )

def register_payment_handlers(dp):
    """Регистрация обработчиков платежей"""
    dp.include_router(router) 