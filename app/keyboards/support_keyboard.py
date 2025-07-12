from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class SupportKeyboard:
    @staticmethod
    def get_support_menu():
        """Главное меню поддержки"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать обращение", callback_data="support_new_ticket")],
                [InlineKeyboardButton(text="📋 Мои обращения", callback_data="support_my_tickets")],
                [InlineKeyboardButton(text="❓ Часто задаваемые вопросы", callback_data="support_faq")],
                [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_main")]
            ]
        )
        return keyboard

    @staticmethod
    def get_category_menu():
        """Меню выбора категории обращения"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔌 Проблемы с подключением", callback_data="category_connection")],
                [InlineKeyboardButton(text="💳 Вопросы по оплате", callback_data="category_payment")],
                [InlineKeyboardButton(text="⚙️ Технические проблемы", callback_data="category_technical")],
                [InlineKeyboardButton(text="📱 Настройка приложения", callback_data="category_setup")],
                [InlineKeyboardButton(text="❓ Другое", callback_data="category_other")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="support_back")]
            ]
        )
        return keyboard

    @staticmethod
    def get_ticket_actions(ticket_id: int, is_closed: bool = False):
        """Действия с тикетом"""
        buttons = []
        
        if not is_closed:
            buttons.append([InlineKeyboardButton(text="💬 Добавить сообщение", callback_data=f"ticket_reply_{ticket_id}")])
            buttons.append([InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"ticket_close_{ticket_id}")])
        
        buttons.append([InlineKeyboardButton(text="⬅️ К списку тикетов", callback_data="support_my_tickets")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        return keyboard

    @staticmethod
    def get_admin_ticket_actions(ticket_id: int):
        """Админские действия с тикетом"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"admin_reply_{ticket_id}")],
                [InlineKeyboardButton(text="🔒 Закрыть", callback_data=f"admin_close_{ticket_id}")],
                [InlineKeyboardButton(text="📋 История", callback_data=f"admin_history_{ticket_id}")],
                [InlineKeyboardButton(text="⬅️ К списку", callback_data="admin_tickets")]
            ]
        )
        return keyboard

    @staticmethod
    def get_cancel_keyboard():
        """Кнопка отмены"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить", callback_data="support_cancel")]
            ]
        )
        return keyboard

    @staticmethod
    def get_faq_keyboard():
        """FAQ клавиатура"""
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Как настроить VPN?", callback_data="faq_setup")],
                [InlineKeyboardButton(text="🐌 Медленная скорость", callback_data="faq_speed")],
                [InlineKeyboardButton(text="💰 Как оплатить?", callback_data="faq_payment")],
                [InlineKeyboardButton(text="📱 Проблемы с приложением", callback_data="faq_app")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="support_back")]
            ]
        )
        return keyboard 