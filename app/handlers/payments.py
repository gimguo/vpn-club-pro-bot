from aiogram import Router, F
from aiogram.types import CallbackQuery
from app.keyboards.tariff_keyboard import TariffKeyboard
from app.services.user_service import UserService
from app.services.payment_service import PaymentService
from app.services.subscription_service import SubscriptionService
from app.database import AsyncSessionLocal
from config import settings
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery):
    """Обработка создания платежа"""
    tariff_type = callback.data.split("_")[1]
    
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

def register_payment_handlers(dp):
    """Регистрация обработчиков платежей"""
    dp.include_router(router) 