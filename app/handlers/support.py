import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.keyboards.support_keyboard import SupportKeyboard
from app.keyboards.main_keyboard import MainKeyboard
from app.services.support_service import SupportService
from app.services.user_service import UserService
from app.states.support_states import SupportStates
from app.database import AsyncSessionLocal
from config import settings

logger = logging.getLogger(__name__)
router = Router()

# Обработчики сообщений
@router.message(F.text == "💬 Поддержка")
async def support_menu(message: Message):
    """Главное меню поддержки"""
    text = """💬 <b>Служба поддержки</b>

Выберите действие:"""
    
    await message.answer(
        text,
        reply_markup=SupportKeyboard.get_support_menu(),
        parse_mode="HTML"
    )

# Категории для удобства
CATEGORIES = {
    "connection": "🔌 Проблемы с подключением",
    "payment": "💳 Вопросы по оплате", 
    "technical": "⚙️ Технические проблемы",
    "setup": "📱 Настройка приложения",
    "other": "❓ Другое"
}

STATUS_EMOJI = {
    "new": "🆕",
    "in_progress": "⏳", 
    "closed": "✅"
}

@router.callback_query(F.data == "support_new_ticket")
async def start_new_ticket(callback: CallbackQuery, state: FSMContext):
    """Начать создание нового тикета"""
    text = """📝 <b>Создание обращения</b>

Выберите категорию вашего вопроса:"""

    await callback.message.edit_text(
        text,
        reply_markup=SupportKeyboard.get_category_menu(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("category_"))
async def select_category(callback: CallbackQuery, state: FSMContext):
    """Выбор категории обращения"""
    category = callback.data.split("_")[1]
    category_name = CATEGORIES.get(category, "Другое")
    
    await state.update_data(category=category, category_name=category_name)
    
    text = f"""📝 <b>Создание обращения</b>
    
Категория: {category_name}

Напишите ваш вопрос или опишите проблему подробно:

💡 <b>Советы для быстрого решения:</b>
• Укажите модель устройства и версию ОС
• Опишите, что именно не работает
• Приложите скриншоты, если возможно"""

    await callback.message.edit_text(
        text,
        reply_markup=SupportKeyboard.get_cancel_keyboard(),
        parse_mode="HTML"
    )
    
    await state.set_state(SupportStates.waiting_for_message)

@router.message(SupportStates.waiting_for_message)
async def process_support_message(message: Message, state: FSMContext):
    """Обработка сообщения пользователя"""
    data = await state.get_data()
    category = data.get("category", "other")
    category_name = data.get("category_name", "Другое")
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        support_service = SupportService(session)
        
        # Получаем или создаем пользователя
        user = await user_service.get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Создаем тикет
        ticket = await support_service.create_ticket(
            user_id=user.id,
            message=message.text,
            category=category
        )
        
        # Уведомляем пользователя
        success_text = f"""✅ <b>Обращение создано успешно!</b>

🎫 <b>Номер тикета:</b> <code>{ticket.ticket_number}</code>
📂 <b>Категория:</b> {category_name}
📅 <b>Дата создания:</b> {ticket.created_at.strftime('%d.%m.%Y %H:%M')}

Ваше обращение передано в службу поддержки. Мы ответим в ближайшее время.

Вы можете отслеживать статус в разделе "📋 Мои обращения"."""

        await message.answer(
            success_text,
            reply_markup=SupportKeyboard.get_support_menu(),
            parse_mode="HTML"
        )
        
        # Уведомляем админа
        await notify_admin_new_ticket(ticket, user, message.text)
        
    await state.clear()

@router.callback_query(F.data == "support_my_tickets")
async def show_user_tickets(callback: CallbackQuery):
    """Показать тикеты пользователя"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        support_service = SupportService(session)
        
        user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
            
        tickets = await support_service.get_user_tickets(user.id)
        
        if not tickets:
            text = """📋 <b>Мои обращения</b>

У вас пока нет обращений в службу поддержки.

Создайте новое обращение, если у вас есть вопросы!"""
        else:
            text = "📋 <b>Мои обращения</b>\n\n"
            
            for ticket in tickets:
                status_emoji = STATUS_EMOJI.get(ticket.status, "❓")
                category_name = CATEGORIES.get(ticket.category, "Другое")
                
                text += f"""{status_emoji} <b>{ticket.ticket_number}</b>
📂 {category_name}
📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}
📝 {ticket.message[:50]}{'...' if len(ticket.message) > 50 else ''}

"""
        
        await callback.message.edit_text(
            text,
            reply_markup=SupportKeyboard.get_support_menu(),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "support_faq")
async def show_faq(callback: CallbackQuery):
    """Показать FAQ"""
    text = """❓ <b>Часто задаваемые вопросы</b>

Выберите интересующую вас тему:"""

    await callback.message.edit_text(
        text,
        reply_markup=SupportKeyboard.get_faq_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("faq_"))
async def show_faq_answer(callback: CallbackQuery):
    """Показать ответ из FAQ"""
    faq_type = callback.data.split("_")[1]
    
    faq_answers = {
        "setup": """🔧 <b>Как настроить VPN?</b>

1️⃣ Скачайте приложение Outline:
   • iOS: App Store
   • Android: Google Play
   • Windows/Mac: с нашего сайта

2️⃣ Получите ключ доступа в боте

3️⃣ Добавьте ключ в приложение:
   • Нажмите "+" в приложении
   • Вставьте ключ доступа
   • Нажмите "Подключить"

📱 Подробная инструкция: /start → "📖 Инструкция" """,
        
        "speed": """🐌 <b>Что делать при медленной скорости?</b>

🔍 <b>Возможные причины:</b>
• Слабый интернет-провайдер
• Удаленный сервер
• Много подключенных устройств

✅ <b>Решения:</b>
• Перезапустите VPN
• Поменяйте сервер (если доступно)
• Закройте лишние приложения
• Проверьте скорость без VPN

Если проблема не решилась - создайте обращение.""",
        
        "payment": """💰 <b>Как оплатить подписку?</b>

💳 <b>Способы оплаты:</b>
• Банковские карты (Visa, MasterCard, МИР)
• Электронные кошельки
• Мобильные платежи

📝 <b>Процесс оплаты:</b>
1. Выберите тариф в боте
2. Нажмите "Оплатить"
3. Следуйте инструкциям
4. Ключ придет автоматически

❓ Проблемы с оплатой? Создайте обращение с указанием суммы и времени платежа.""",
        
        "app": """📱 <b>Проблемы с приложением</b>

🔧 <b>Общие решения:</b>
• Перезапустите приложение
• Обновите до последней версии
• Перезагрузите устройство
• Переустановите приложение

⚠️ <b>Если ключ не работает:</b>
• Проверьте интернет-соединение
• Убедитесь что ключ скопирован полностью
• Попробуйте создать новый ключ

Не помогает? Опишите проблему в обращении."""
    }
    
    answer = faq_answers.get(faq_type, "Информация не найдена")
    
    await callback.message.edit_text(
        answer,
        reply_markup=SupportKeyboard.get_faq_keyboard(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "support_back")
async def back_to_support(callback: CallbackQuery):
    """Возврат в меню поддержки"""
    text = """💬 <b>Служба поддержки</b>

Выберите действие:"""
    
    await callback.message.edit_text(
        text,
        reply_markup=SupportKeyboard.get_support_menu(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "support_cancel")
async def cancel_support(callback: CallbackQuery, state: FSMContext):
    """Отмена создания тикета"""
    await state.clear()
    
    text = """💬 <b>Служба поддержки</b>

Выберите действие:"""
    
    await callback.message.edit_text(
        text,
        reply_markup=SupportKeyboard.get_support_menu(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    # edit_text не поддерживает ReplyKeyboardMarkup, поэтому убираем inline-клавиатуру
    # и отправляем новое сообщение с Reply-клавиатурой
    await callback.message.edit_text(
        "👋 <b>Главное меню</b>",
        parse_mode="HTML",
        reply_markup=None,
    )
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=MainKeyboard.get_main_menu(),
        parse_mode="HTML",
    )

async def notify_admin_new_ticket(ticket, user, message_text):
    """Уведомление админа о новом тикете"""
    try:
        from app.main import bot  # Импортируем бот
        
        admin_text = f"""🆘 <b>Новое обращение в поддержку</b>

🎫 <b>Тикет:</b> {ticket.ticket_number}
👤 <b>Пользователь:</b> {user.first_name} (@{user.username or 'без username'})
📧 <b>Telegram ID:</b> <code>{user.telegram_id}</code>
📂 <b>Категория:</b> {CATEGORIES.get(ticket.category, 'Другое')}
📅 <b>Время:</b> {ticket.created_at.strftime('%d.%m.%Y %H:%M')}

💬 <b>Сообщение:</b>
{message_text}"""

        await bot.send_message(
            chat_id=settings.admin_id,
            text=admin_text,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления админу: {e}")

def register_support_handlers(dp):
    """Регистрация обработчиков поддержки"""
    dp.include_router(router) 