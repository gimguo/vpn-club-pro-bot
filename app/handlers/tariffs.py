from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from app.keyboards.tariff_keyboard import TariffKeyboard
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.database import AsyncSessionLocal
from config import settings

router = Router()

@router.message(F.text == "🔥 Тарифы")
async def show_tariffs(message: Message):
    """Показать тарифы"""
    text = """💰 <b>Выберите подходящий тариф:</b>

🆓 <b>Пробный период</b> - 3 дня бесплатно
   • Лимит: 10 ГБ трафика
   • Один раз на пользователя

💵 <b>Платные тарифы</b> - безлимитный трафик
   • Полная скорость без ограничений
   • Стабильная работа 24/7"""

    await message.answer(
        text,
        reply_markup=TariffKeyboard.get_tariffs(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("tariff_"))
async def process_tariff_selection(callback: CallbackQuery):
    """Обработка выбора тарифа"""
    tariff_type = callback.data.split("_")[1]
    tariff_names = TariffKeyboard.get_tariff_names()
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_or_create_user(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            last_name=callback.from_user.last_name
        )
        
        # Проверяем есть ли уже активная подписка
        active_subscription = await subscription_service.get_active_subscription(user.id)
        
        # Для триал подписки разрешаем переход на платные тарифы
        if active_subscription:
            if tariff_type == "trial":
                await callback.answer("У вас уже есть активная подписка!", show_alert=True)
                return
            elif active_subscription.tariff_type != "trial":
                await callback.answer("У вас уже есть активная платная подписка!", show_alert=True)
                return
        
        if tariff_type == "trial":
            # Проверяем использован ли пробный период
            if user.is_trial_used:
                await callback.answer("Вы уже использовали пробный период!", show_alert=True)
                return
            
            try:
                # Создаем пробную подписку
                subscription = await subscription_service.create_subscription(user.id, "trial")
                await user_service.mark_trial_used(user.id)
                
                # Планируем уведомление об истечении (импортируем планировщик глобально)
                from app.main import scheduler
                if scheduler:
                    scheduler.schedule_subscription_notification(user.id, subscription.end_date)
                
                success_text = """✅ <b>Пробный ключ успешно создан!</b>

🔑 Ваш ключ доступа:"""
                
                await callback.message.edit_text(success_text, parse_mode="HTML")
                await callback.message.answer(f"<code>{subscription.access_url}</code>", parse_mode="HTML")
                
                info_text = f"""📋 <b>Информация о пробном периоде:</b>
📊 Лимит трафика: {settings.trial_traffic_gb} ГБ
⏰ Активна до: {subscription.end_date.strftime('%d.%m.%Y')}

📱 Не забудьте скачать приложение и настроить VPN!"""
                
                await callback.message.answer(info_text, parse_mode="HTML")
                
            except Exception as e:
                await callback.answer("Ошибка при создании ключа. Попробуйте позже.", show_alert=True)
        else:
            # Для платных тарифов показываем кнопку оплаты
            from app.services.payment_service import PaymentService
            payment_service = PaymentService(session)
            amount = payment_service.get_tariff_price(tariff_type)
            
            # Рассчитываем экономию
            monthly_price = 150  # Базовая цена за месяц
            savings_info = ""
            
            if tariff_type == "quarterly":
                regular_price = monthly_price * 3
                savings = regular_price - int(amount)
                savings_info = f"\n💰 <b>Экономия:</b> {savings}₽ по сравнению с ежемесячной оплатой"
            elif tariff_type == "half_yearly":
                regular_price = monthly_price * 6
                savings = regular_price - int(amount)
                savings_info = f"\n💰 <b>Экономия:</b> {savings}₽ по сравнению с ежемесячной оплатой"
            elif tariff_type == "yearly":
                regular_price = monthly_price * 12
                savings = regular_price - int(amount)
                savings_info = f"\n💰 <b>Экономия:</b> {savings}₽ по сравнению с ежемесячной оплатой"
            
            text = f"""📋 <b>Вы выбрали тариф:</b> {tariff_names[tariff_type]}

💰 <b>Стоимость:</b> {amount} ₽{savings_info}
🚀 <b>Преимущества:</b>
   • Безлимитный трафик
   • Максимальная скорость
   • Стабильная работа 24/7
   • Отсутствие рекламы"""
            
            await callback.message.edit_text(
                text,
                reply_markup=TariffKeyboard.get_payment_button(int(amount), tariff_type),
                parse_mode="HTML"
            )

@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback: CallbackQuery):
    """Возврат к тарифам"""
    text = """💰 <b>Выберите подходящий тариф:</b>

🆓 <b>Пробный период</b> - 3 дня бесплатно
   • Лимит: 10 ГБ трафика
   • Один раз на пользователя

💵 <b>Платные тарифы</b> - безлимитный трафик
   • Полная скорость без ограничений
   • Стабильная работа 24/7"""

    await callback.message.edit_text(
        text,
        reply_markup=TariffKeyboard.get_tariffs(),
        parse_mode="HTML"
    )

def register_tariff_handlers(dp):
    """Регистрация обработчиков тарифов"""
    dp.include_router(router) 