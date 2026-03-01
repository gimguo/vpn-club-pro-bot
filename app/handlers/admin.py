from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from app.services.user_service import UserService
from app.services.subscription_service import SubscriptionService
from app.database import AsyncSessionLocal
from config import settings
import asyncio
from datetime import datetime

router = Router()

class SupportReplyStates(StatesGroup):
    waiting_for_reply = State()

async def is_admin(message: Message) -> bool:
    """Проверка является ли пользователь администратором"""
    # Главный админ из настроек всегда имеет права
    if hasattr(settings, 'admin_id') and message.from_user.id == settings.admin_id:
        return True
    
    # Проверяем админов в БД
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from app.models import User
        
        result = await session.execute(
            select(User).where(
                User.telegram_id == message.from_user.id,
                User.is_admin == True,
                User.is_active == True
            )
        )
        user = result.scalar_one_or_none()
        return user is not None

@router.message(Command("admin"))
async def admin_panel(message: Message):
    """Административная панель"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    text = f"""🔧 <b>Админ панель</b>

👤 <b>Администратор:</b> {message.from_user.first_name or 'Не указано'}

📊 <b>Основные команды:</b>
• /stats - общая статистика
• /users - список всех пользователей
• /servers - информация о серверах
• /user_info &lt;telegram_id&gt; - информация о пользователе

👥 <b>Управление пользователями:</b>
• /find_user &lt;query&gt; - поиск пользователя
• /make_admin &lt;telegram_id&gt; - назначить администратором
• /remove_admin &lt;telegram_id&gt; - снять администратора
• /block_user &lt;telegram_id&gt; - заблокировать пользователя
• /unblock_user &lt;telegram_id&gt; - разблокировать пользователя

🎫 <b>Система поддержки:</b>
• /support_tickets - просмотр всех тикетов
• /support_view &lt;номер_тикета&gt; - детали тикета
• /support_reply &lt;номер_тикета&gt; &lt;ответ&gt; - ответить на тикет
• /support_close &lt;номер_тикета&gt; - закрыть тикет

🎁 <b>Подписки:</b>
• /give_unlimited &lt;telegram_id&gt; - безлимитная подписка
• /give_key &lt;telegram_id&gt; &lt;тариф&gt; - выдать ключ по тарифу

🛠 <b>Сервисные команды:</b>
• /maintenance - режим обслуживания
• /broadcast &lt;сообщение&gt; - рассылка всем пользователям"""

    await message.answer(text, parse_mode="HTML")

@router.message(Command("users"))
async def show_users(message: Message):
    """Список пользователей с пагинацией"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return

    # Парсим номер страницы из команды: /users или /users 2
    args = message.text.split()
    page = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    await _show_users_page(message, page, edit=False)


async def _show_users_page(target, page: int, edit: bool = False):
    """Формирование страницы списка пользователей."""
    PAGE_SIZE = 10

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func, desc, case
        from app.models import User, Subscription

        # Общее число пользователей
        total_result = await session.execute(select(func.count(User.id)))
        total = total_result.scalar() or 0
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * PAGE_SIZE

        # Подзапрос: есть ли активная подписка
        sub_active = (
            select(func.count(Subscription.id))
            .where(
                Subscription.user_id == User.id,
                Subscription.is_active == True,
            )
            .correlate(User)
            .scalar_subquery()
        )

        result = await session.execute(
            select(User, sub_active.label("active_subs"))
            .order_by(desc(User.created_at))
            .offset(offset)
            .limit(PAGE_SIZE)
        )
        rows = result.all()

        # Сводка
        active_subs_total = await session.execute(
            select(func.count(Subscription.id)).where(Subscription.is_active == True)
        )
        total_active_subs = active_subs_total.scalar() or 0

    text = f"👥 <b>Пользователи</b> ({total} всего, {total_active_subs} с подпиской)\n"
    text += f"📄 Страница {page}/{total_pages}\n\n"

    for user, active_subs in rows:
        # Иконки статуса
        status = ""
        if user.is_admin:
            status += "👑"
        if not user.is_active:
            status += "🚫"
        if active_subs and active_subs > 0:
            status += "🔑"
        elif user.is_trial_used:
            status += "⏱️"

        name = user.first_name or "—"
        uname = f"@{user.username}" if user.username else ""
        reg = user.created_at.strftime("%d.%m.%y") if user.created_at else "?"

        text += (
            f"{status} <b>{name}</b> {uname}\n"
            f"    ID: <code>{user.telegram_id}</code> | {reg}"
        )
        if user.referral_code:
            text += f" | ref: {user.referral_code}"
        text += "\n"

    text += f"\n👑 админ  🔑 подписка  ⏱️ триал  🚫 заблокирован"

    # Кнопки пагинации
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️", callback_data=f"users_page_{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="users_noop"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton(text="▶️", callback_data=f"users_page_{page + 1}"))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        nav_buttons,
        [
            InlineKeyboardButton(text="🔑 Только с подпиской", callback_data="users_filter_active"),
            InlineKeyboardButton(text="🔄 Все", callback_data="users_page_1"),
        ],
    ])

    if edit and hasattr(target, "message"):
        await target.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await target.answer()
    elif edit and hasattr(target, "edit_text"):
        await target.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("users_page_"))
async def users_page_callback(callback: CallbackQuery):
    """Пагинация списка юзеров."""
    if not (callback.from_user.id == settings.admin_id):
        return
    page = int(callback.data.removeprefix("users_page_"))
    await _show_users_page(callback, page, edit=True)


@router.callback_query(F.data == "users_filter_active")
async def users_filter_active(callback: CallbackQuery):
    """Показать только юзеров с активной подпиской."""
    if not (callback.from_user.id == settings.admin_id):
        return

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, desc
        from app.models import User, Subscription

        result = await session.execute(
            select(User, Subscription.tariff_type, Subscription.end_date)
            .join(Subscription, Subscription.user_id == User.id)
            .where(Subscription.is_active == True)
            .order_by(desc(Subscription.end_date))
            .limit(30)
        )
        rows = result.all()

    if not rows:
        await callback.answer("Нет пользователей с активной подпиской", show_alert=True)
        return

    text = f"🔑 <b>Пользователи с активной подпиской</b> ({len(rows)})\n\n"
    for user, tariff, end_date in rows:
        name = user.first_name or "—"
        uname = f"@{user.username}" if user.username else ""
        end = end_date.strftime("%d.%m.%y") if end_date else "?"
        text += (
            f"🔑 <b>{name}</b> {uname}\n"
            f"    ID: <code>{user.telegram_id}</code> | {tariff} до {end}\n"
        )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Все пользователи", callback_data="users_page_1")],
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "users_noop")
async def users_noop(callback: CallbackQuery):
    await callback.answer()


@router.message(Command("stats"))
async def show_stats(message: Message):
    """Показать статистику бота"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func
        from app.models import User, Subscription, Payment
        
        # Общее количество пользователей
        total_users_result = await session.execute(
            select(func.count(User.id))
        )
        total_users = total_users_result.scalar()
        
        # Активные пользователи
        active_users_result = await session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = active_users_result.scalar()
        
        # Активные подписки
        active_subscriptions_result = await session.execute(
            select(func.count(Subscription.id)).where(Subscription.is_active == True)
        )
        active_subscriptions = active_subscriptions_result.scalar()
        
        # Успешные платежи
        successful_payments_result = await session.execute(
            select(func.count(Payment.id), func.sum(Payment.amount)).where(
                Payment.status == "succeeded"
            )
        )
        payments_data = successful_payments_result.first()
        successful_payments = payments_data[0] or 0
        total_revenue = payments_data[1] or 0
        
        text = f"""📊 <b>Статистика бота</b>

👥 <b>Пользователи:</b>
   • Всего: {total_users}
   • Активных: {active_users}

🔑 <b>Подписки:</b>
   • Активных: {active_subscriptions}

💰 <b>Платежи:</b>
   • Успешных: {successful_payments}
   • Общая выручка: {total_revenue:.2f} ₽"""

        await message.answer(text, parse_mode="HTML")

@router.message(Command("servers"))
async def show_servers_stats(message: Message):
    """Показать статистику серверов"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    from app.services.outline_service import OutlineService
    
    await message.answer("🔄 Получаю статистику серверов...")
    
    outline_service = OutlineService()
    servers_stats = await outline_service.get_all_servers_stats()
    
    if not servers_stats:
        await message.answer("❌ Не удалось получить статистику серверов")
        return
    
    text = "🖥️ <b>Статистика серверов Outline</b>\n\n"
    
    total_keys = 0
    total_traffic = 0
    online_servers = 0
    
    for i, server in enumerate(servers_stats, 1):
        status_icon = "🟢" if server["status"] == "online" else "🔴"
        
        text += f"{status_icon} <b>Сервер {i}</b>\n"
        text += f"   📊 Активных ключей: {server['active_keys']}\n"
        text += f"   📈 Трафик: {server['total_traffic_gb']} ГБ\n"
        text += f"   ⚡ Нагрузка: {server['load_percentage']}%\n"
        
        if server["status"] == "offline":
            text += f"   ⚠️ Ошибка: {server.get('error', 'Unknown')[:50]}...\n"
        else:
            online_servers += 1
            total_keys += server['active_keys']
            total_traffic += server['total_traffic_gb']
        
        text += "\n"
    
    # Общая статистика
    text += f"📈 <b>Общая статистика:</b>\n"
    text += f"🖥️ Серверов онлайн: {online_servers}/{len(servers_stats)}\n"
    text += f"🔑 Всего ключей: {total_keys}\n"
    text += f"📊 Общий трафик: {total_traffic:.2f} ГБ"

    await message.answer(text, parse_mode="HTML")

@router.message(Command("user_info"))
async def user_info(message: Message):
    """Информация о пользователе"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Укажите telegram_id пользователя\nПример: /user_info 123456789")
        return
    
    try:
        telegram_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный формат telegram_id")
        return
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        # Получаем активную подписку
        subscription = await subscription_service.get_active_subscription(user.id)
        
        text = f"""👤 <b>Информация о пользователе</b>

🆔 ID: {user.id}
📱 Telegram ID: {user.telegram_id}
👤 Имя: {user.first_name or 'Не указано'}
📝 Username: @{user.username or 'Не указан'}
📧 Email: {user.email or 'Не указан'}
👑 Админ: {'Да' if user.is_admin else 'Нет'}
🔓 Активен: {'Да' if user.is_active else 'Нет'}
🎁 Триал использован: {'Да' if user.is_trial_used else 'Нет'}

🔑 <b>Подписка:</b>"""

        if subscription:
            text += f"""
📦 Тариф: {subscription.tariff_type}
⏰ Активна до: {subscription.end_date.strftime('%d.%m.%Y')}
🌐 Сервер: {subscription.outline_server_url or 'Не указан'}"""
        else:
            text += "\n❌ Нет активной подписки"

        await message.answer(text, parse_mode="HTML")

@router.message(Command("maintenance"))
async def toggle_maintenance(message: Message):
    """Включить/выключить режим обслуживания"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Проверяем текущий статус из файла или переменной
    import os
    maintenance_file = "maintenance.flag"
    
    if os.path.exists(maintenance_file):
        # Выключаем режим обслуживания
        os.remove(maintenance_file)
        await message.answer("✅ Режим обслуживания выключен\nБот снова доступен для всех пользователей")
    else:
        # Включаем режим обслуживания
        with open(maintenance_file, "w") as f:
            f.write("maintenance")
        await message.answer("🔧 Режим обслуживания включен\nБот недоступен для обычных пользователей")

@router.message(Command("broadcast"))
async def broadcast_message(message: Message):
    """Массовая рассылка сообщений"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    # Извлекаем текст сообщения
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("❌ Укажите текст для рассылки\nПример: /broadcast Привет всем!")
        return
    
    await message.answer("🔄 Начинаю рассылку...")
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        from sqlalchemy import select
        from app.models import User
        
        result = await session.execute(
            select(User).where(User.is_active == True)
        )
        active_users = result.scalars().all()
        
        sent_count = 0
        failed_count = 0
        
        for user in active_users:
            try:
                await message.bot.send_message(
                    user.telegram_id,
                    text,
                    parse_mode="HTML"
                )
                sent_count += 1
                await asyncio.sleep(0.1)  # Задержка для избежания лимитов
                
            except Exception as e:
                failed_count += 1
        
        result_text = f"""✅ Рассылка завершена
        
📤 Отправлено: {sent_count}
❌ Ошибок: {failed_count}"""
        
        await message.answer(result_text)

@router.message(Command("give_key"))
async def give_key(message: Message):
    """Выдать ключ пользователю"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    try:
        parts = message.text.split()
        telegram_id = int(parts[1])
        tariff_type = parts[2].lower()
    except (IndexError, ValueError):
        await message.answer("""❌ Неверный формат команды

Использование: /give_key &lt;telegram_id&gt; &lt;тариф&gt;

Доступные тарифы:
• trial - Пробный (3 дня, 10 ГБ)
• monthly - Месячный (30 дней)
• quarterly - Квартальный (90 дней)
• half_yearly - Полугодовой (180 дней)
• yearly - Годовой (365 дней)
• unlimited - ♾ Безлимит (бессрочно)

Пример: /give_key 123456789 monthly""", parse_mode="HTML")
        return
    
    # Проверяем правильность тарифа
    valid_tariffs = ["trial", "monthly", "quarterly", "half_yearly", "yearly", "unlimited"]
    if tariff_type not in valid_tariffs:
        await message.answer(f"❌ Неверный тариф. Доступные: {', '.join(valid_tariffs)}")
        return
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        # Проверяем существование пользователя
        user = await user_service.get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        # Проверяем активную подписку
        active_subscription = await subscription_service.get_active_subscription(user.id)
        if active_subscription:
            await message.answer("❌ У пользователя уже есть активная подписка")
            return
        
        try:
            # Создаем подписку
            await message.answer("🔄 Создаю ключ...")
            subscription = await subscription_service.create_subscription(user.id, tariff_type)
            
            # Планируем уведомление об истечении
            from app.main import scheduler
            if scheduler:
                scheduler.schedule_subscription_notification(user.id, subscription.end_date)
            
            # Отправляем уведомление пользователю
            tariff_names = {
                "trial": "Пробный (3 дня, 10 ГБ)",
                "monthly": "Месячный (30 дней)",
                "quarterly": "Квартальный (90 дней)",
                "half_yearly": "Полугодовой (180 дней)",
                "yearly": "Годовой (365 дней)",
                "unlimited": "♾ Безлимит (бессрочно)",
            }
            
            user_text = f"""🎉 <b>Вам выдан VPN ключ!</b>

📦 Тариф: {tariff_names[tariff_type]}
⏰ Активна до: {subscription.end_date.strftime('%d.%m.%Y')}

🔑 <b>Ваш ключ:</b>
<code>{subscription.access_url}</code>

📱 Для подключения используйте приложение Outline"""
            
            try:
                await message.bot.send_message(
                    telegram_id,
                    user_text,
                    parse_mode="HTML"
                )
                
                await message.answer(f"✅ Ключ выдан пользователю {telegram_id}\nТариф: {tariff_names[tariff_type]}")
                
            except Exception as e:
                await message.answer(f"✅ Ключ создан, но не удалось отправить пользователю: {e}")
                
        except Exception as e:
            await message.answer(f"❌ Ошибка при создании ключа: {e}")

@router.message(Command("give_unlimited"))
async def give_unlimited(message: Message):
    """Выдать безлимитную подписку пользователю"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "❌ Укажите telegram_id пользователя\n\n"
            "Использование: /give_unlimited &lt;telegram_id&gt;\n"
            "Пример: /give_unlimited 123456789\n\n"
            "💡 Telegram ID можно узнать через /users или /find_user",
            parse_mode="HTML",
        )
        return

    try:
        telegram_id = int(args[1])
    except ValueError:
        await message.answer("❌ Неверный формат telegram_id")
        return

    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)

        user = await user_service.get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return

        # Деактивируем текущую подписку, если есть
        active_sub = await subscription_service.get_active_subscription(user.id)
        if active_sub:
            await subscription_service.deactivate_subscription(active_sub)

        try:
            await message.answer("🔄 Создаю безлимитный ключ...")
            subscription = await subscription_service.create_subscription(user.id, "unlimited")

            name = user.first_name or user.username or str(telegram_id)

            await message.answer(
                f"✅ <b>Безлимитная подписка выдана!</b>\n\n"
                f"👤 Пользователь: {name} (<code>{telegram_id}</code>)\n"
                f"📦 Тариф: ♾ Безлимит\n"
                f"⏰ Действует до: бессрочно\n"
                f"🌐 Трафик: без ограничений",
                parse_mode="HTML",
            )

            # Уведомляем пользователя
            try:
                user_text = (
                    "🎉 <b>Вам выдан VPN-ключ!</b>\n\n"
                    "📦 Тариф: ♾ <b>Безлимит</b>\n"
                    "⏰ Срок: <b>бессрочно</b>\n"
                    "🌐 Трафик: <b>без ограничений</b>\n\n"
                    f"🔑 <b>Ваш ключ:</b>\n<code>{subscription.access_url}</code>\n\n"
                    "👆 Нажмите чтобы скопировать, затем вставьте в Outline"
                )
                await message.bot.send_message(telegram_id, user_text, parse_mode="HTML")
            except Exception as e:
                await message.answer(f"⚠️ Ключ создан, но не удалось уведомить пользователя: {e}")

        except Exception as e:
            await message.answer(f"❌ Ошибка при создании ключа: {e}")


@router.message(Command("find_user"))
async def find_user(message: Message):
    """Поиск пользователя по username"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    try:
        username = message.text.split()[1].replace("@", "").lower()
    except IndexError:
        await message.answer("❌ Укажите username\nПример: /find_user @username")
        return
    
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        from app.models import User
        
        # Ищем пользователя по username
        result = await session.execute(
            select(User).where(User.username.ilike(f"%{username}%"))
        )
        users = result.scalars().all()
        
        if not users:
            await message.answer(f"❌ Пользователь с ником @{username} не найден в базе")
            return
        
        if len(users) == 1:
            user = users[0]
            text = f"""🔍 <b>Найден пользователь:</b>

🆔 ID: <code>{user.telegram_id}</code>
👤 Имя: {user.first_name or 'Не указано'}
📛 Username: @{user.username or 'Не указан'}
📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M')}
✅ Активен: {'Да' if user.is_active else 'Нет'}"""
        else:
            text = f"🔍 <b>Найдено {len(users)} пользователей:</b>\n\n"
            for user in users[:10]:  # Максимум 10 результатов
                text += f"🆔 {user.telegram_id} - @{user.username} ({user.first_name})\n"

        await message.answer(text, parse_mode="HTML")

@router.message(Command("make_admin"))
async def make_admin(message: Message):
    """Назначить администратора (только для главного админа)"""
    # Только главный админ из настроек может назначать других админов
    if not hasattr(settings, 'admin_id') or message.from_user.id != settings.admin_id:
        await message.answer("❌ Только главный администратор может назначать админов")
        return
    
    try:
        telegram_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Укажите корректный Telegram ID\nПример: /make_admin 123456789")
        return
    
    if telegram_id == settings.admin_id:
        await message.answer("❌ Главный админ не может изменить свои права")
        return
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        user = await user_service.get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if user.is_admin:
            await message.answer("❌ Пользователь уже является администратором")
            return
        
        user.is_admin = True
        await session.commit()
        
        await message.answer(f"✅ Пользователь {telegram_id} назначен администратором")
        
        # Уведомляем нового админа
        try:
            await message.bot.send_message(
                telegram_id,
                "👑 <b>Вы назначены администратором!</b>\n\nТеперь у вас есть доступ к административным функциям бота.",
                parse_mode="HTML"
            )
        except Exception:
            pass

@router.message(Command("remove_admin"))
async def remove_admin(message: Message):
    """Снять права администратора (только для главного админа)"""
    # Только главный админ из настроек может снимать права
    if not hasattr(settings, 'admin_id') or message.from_user.id != settings.admin_id:
        await message.answer("❌ Только главный администратор может снимать права админов")
        return
    
    try:
        telegram_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Укажите корректный Telegram ID\nПример: /remove_admin 123456789")
        return
    
    if telegram_id == settings.admin_id:
        await message.answer("❌ Нельзя снять права у главного админа")
        return
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        user = await user_service.get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if not user.is_admin:
            await message.answer("❌ Пользователь не является администратором")
            return
        
        user.is_admin = False
        await session.commit()
        
        await message.answer(f"✅ Права администратора у пользователя {telegram_id} сняты")
        
        # Уведомляем бывшего админа
        try:
            await message.bot.send_message(
                telegram_id,
                "📉 <b>Ваши права администратора сняты</b>\n\nВы больше не имеете доступа к административным функциям.",
                parse_mode="HTML"
            )
        except Exception:
            pass

@router.message(Command("block_user"))
async def block_user(message: Message):
    """Заблокировать пользователя"""
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    try:
        telegram_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        await message.answer("❌ Укажите корректный Telegram ID\nПример: /block_user 123456789")
        return
    
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        subscription_service = SubscriptionService(session)
        
        user = await user_service.get_user_by_telegram_id(telegram_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if not user.is_active:
            await message.answer("❌ Пользователь уже заблокирован")
            return
        
        # Деактивируем пользователя
        user.is_active = False
        
        # Деактивируем все активные подписки
        active_subscription = await subscription_service.get_active_subscription(user.id)
        if active_subscription:
            active_subscription.is_active = False
            await message.answer(f"✅ Пользователь {telegram_id} заблокирован\n🔑 Активные ключи деактивированы")
        else:
            await message.answer(f"✅ Пользователь {telegram_id} заблокирован")
        
        await session.commit()
        
        # Уведомляем пользователя
        try:
            await message.bot.send_message(
                telegram_id,
                "🚫 <b>Ваш аккаунт заблокирован</b>\n\nОбратитесь к администратору для получения дополнительной информации.",
                parse_mode="HTML"
            )
        except Exception:
            pass  # Пользователь может заблокировать бота

@router.message(Command("unblock_user"))
async def unblock_user_command(message: Message):
    """Разблокировка пользователя"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await message.answer("❌ У вас нет прав администратора")
            return
        
        args = message.text.split()[1:]
        if len(args) != 1:
            await message.answer("Использование: /unblock_user &lt;telegram_id&gt;")
            return
        
        try:
            target_telegram_id = int(args[0])
        except ValueError:
            await message.answer("❌ Неверный формат Telegram ID")
            return
        
        # Ищем пользователя
        target_user = await user_service.get_user_by_telegram_id(target_telegram_id)
        if not target_user:
            await message.answer("❌ Пользователь не найден")
            return
        
        # Разблокируем пользователя (активируем)
        target_user.is_active = True
        await session.commit()
        
        text = f"""✅ <b>Пользователь разблокирован</b>

👤 <b>Пользователь:</b> {target_user.first_name}
📧 <b>Telegram ID:</b> <code>{target_user.telegram_id}</code>
✅ <b>Статус:</b> Активен"""

        await message.answer(text, parse_mode="HTML")

# Команды поддержки для админа
@router.message(Command("support_tickets"))
async def admin_support_tickets(message: Message):
    """Просмотр всех тикетов поддержки"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await message.answer("❌ У вас нет прав администратора")
            return
        
        from app.services.support_service import SupportService
        support_service = SupportService(session)
        
        # Получаем статистику
        stats = await support_service.get_admin_stats()
        
        # Получаем последние тикеты
        tickets = await support_service.get_all_tickets(limit=10)
        
        text = f"""🎫 <b>Система поддержки - Админ панель</b>

📊 <b>Статистика:</b>
🆕 Новые: {stats.get('new', 0)}
⏳ В работе: {stats.get('in_progress', 0)}
✅ Закрытые: {stats.get('closed', 0)}
📋 Всего: {stats.get('total', 0)}

📝 <b>Последние тикеты:</b>"""

        if not tickets:
            text += "\n\nТикетов пока нет."
        else:
            for ticket in tickets:
                status_emoji = {"new": "🆕", "in_progress": "⏳", "closed": "✅"}.get(ticket.status, "❓")
                category_name = {"connection": "🔌 Подключение", "payment": "💳 Оплата", "technical": "⚙️ Техника", "setup": "📱 Настройка", "other": "❓ Другое"}.get(ticket.category, "❓ Другое")
                
                text += f"""

{status_emoji} <b>{ticket.ticket_number}</b>
📂 {category_name}
📅 {ticket.created_at.strftime('%d.%m.%Y %H:%M')}
📝 {ticket.message[:50]}{'...' if len(ticket.message) > 50 else ''}"""

        # Создаем inline-кнопки для быстрых действий с тикетами
        if tickets:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            for ticket in tickets[:5]:  # Показываем кнопки только для первых 5 тикетов
                row = [
                    InlineKeyboardButton(text=f"👁 {ticket.ticket_number}", callback_data=f"view_ticket_{ticket.ticket_number}"),
                    InlineKeyboardButton(text=f"💬", callback_data=f"reply_ticket_{ticket.ticket_number}"),
                    InlineKeyboardButton(text=f"✅", callback_data=f"close_ticket_{ticket.ticket_number}")
                ]
                keyboard.inline_keyboard.append(row)
            
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await message.answer(text, parse_mode="HTML")

@router.message(Command("support_reply"))
async def admin_support_reply(message: Message):
    """Ответ на тикет поддержки"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await message.answer("❌ У вас нет прав администратора")
            return
        
        # Парсим команду
        parts = message.text.split(' ', 2)
        if len(parts) < 3:
            await message.answer("Использование: /support_reply &lt;номер_тикета&gt; &lt;ваш_ответ&gt;")
            return
        
        ticket_number = parts[1]
        reply_text = parts[2]
        
        from app.services.support_service import SupportService
        support_service = SupportService(session)
        
        # Находим тикет
        ticket = await support_service.get_ticket_by_number(ticket_number)
        if not ticket:
            await message.answer("❌ Тикет не найден")
            return
        
        # Обновляем тикет
        ticket.admin_response = reply_text
        ticket.admin_id = admin_user.id
        ticket.status = "in_progress"
        ticket.responded_at = datetime.utcnow()
        
        # Добавляем сообщение в историю
        await support_service.add_message_to_ticket(
            ticket.id,
            admin_id=admin_user.id,
            message=reply_text,
            is_from_admin=True
        )
        
        await session.commit()
        
        # Отправляем ответ пользователю
        user = await user_service.get_user_by_id(ticket.user_id)
        if user:
            user_text = f"""📬 <b>Ответ службы поддержки</b>

🎫 <b>Тикет:</b> {ticket.ticket_number}
📅 <b>Время ответа:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

💬 <b>Ответ:</b>
{reply_text}

Если у вас есть дополнительные вопросы по этому тикету, просто ответьте на это сообщение."""
            
            from app.main import bot
            if bot:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=user_text,
                    parse_mode="HTML"
                )
        
        await message.answer(f"✅ Ответ отправлен пользователю по тикету {ticket_number}", parse_mode="HTML")

@router.message(Command("support_close"))
async def admin_support_close(message: Message):
    """Закрытие тикета поддержки"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await message.answer("❌ У вас нет прав администратора")
            return
        
        args = message.text.split()[1:]
        if len(args) != 1:
            await message.answer("Использование: /support_close &lt;номер_тикета&gt;")
            return
        
        ticket_number = args[0]
        
        from app.services.support_service import SupportService
        support_service = SupportService(session)
        
        # Находим тикет
        ticket = await support_service.get_ticket_by_number(ticket_number)
        if not ticket:
            await message.answer("❌ Тикет не найден")
            return
        
        # Закрываем тикет
        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        if not ticket.admin_id:
            ticket.admin_id = admin_user.id
        
        await session.commit()
        
        # Уведомляем пользователя
        user = await user_service.get_user_by_id(ticket.user_id)
        if user:
            user_text = f"""✅ <b>Тикет закрыт</b>

🎫 <b>Тикет:</b> {ticket.ticket_number}
📅 <b>Дата закрытия:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

Ваше обращение было рассмотрено и закрыто. Если у вас возникнут новые вопросы, создайте новое обращение через меню "💬 Поддержка".

Спасибо за обращение! 🙏"""
            
            from app.main import bot
            if bot:
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=user_text,
                    parse_mode="HTML"
                )
        
        await message.answer(f"✅ Тикет {ticket_number} закрыт", parse_mode="HTML")

@router.message(Command("support_view"))
async def admin_support_view(message: Message):
    """Просмотр детальной информации о тикете"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await message.answer("❌ У вас нет прав администратора")
            return
        
        args = message.text.split()[1:]
        if len(args) != 1:
            await message.answer("Использование: /support_view &lt;номер_тикета&gt;")
            return
        
        ticket_number = args[0]
        
        from app.services.support_service import SupportService
        support_service = SupportService(session)
        
        # Находим тикет
        ticket = await support_service.get_ticket_by_number(ticket_number)
        if not ticket:
            await message.answer("❌ Тикет не найден")
            return
        
        # Получаем пользователя
        user = await user_service.get_user_by_id(ticket.user_id)
        
        # Получаем историю сообщений
        messages = await support_service.get_ticket_messages(ticket.id)
        
        status_emoji = {"new": "🆕", "in_progress": "⏳", "closed": "✅"}.get(ticket.status, "❓")
        category_name = {"connection": "🔌 Подключение", "payment": "💳 Оплата", "technical": "⚙️ Техника", "setup": "📱 Настройка", "other": "❓ Другое"}.get(ticket.category, "❓ Другое")
        
        text = f"""🎫 <b>Тикет: {ticket.ticket_number}</b>

{status_emoji} <b>Статус:</b> {ticket.status.title()}
📂 <b>Категория:</b> {category_name}
👤 <b>Пользователь:</b> {user.first_name} (@{user.username or 'без username'})
📧 <b>Telegram ID:</b> <code>{user.telegram_id}</code>
📅 <b>Создан:</b> {ticket.created_at.strftime('%d.%m.%Y %H:%M')}"""

        if ticket.responded_at:
            text += f"\n📬 <b>Ответ дан:</b> {ticket.responded_at.strftime('%d.%m.%Y %H:%M')}"
        
        if ticket.closed_at:
            text += f"\n🔒 <b>Закрыт:</b> {ticket.closed_at.strftime('%d.%m.%Y %H:%M')}"
        
        text += f"""

📝 <b>Первоначальное сообщение:</b>
{ticket.message}"""

        if ticket.admin_response:
            text += f"""

💬 <b>Ответ администратора:</b>
{ticket.admin_response}"""

        if messages and len(messages) > 1:
            text += "\n\n📜 <b>История переписки:</b>"
            for msg in messages[-5:]:  # Последние 5 сообщений
                sender = "👤 Пользователь" if not msg.is_from_admin else "👨‍💼 Админ"
                text += f"\n\n{sender} ({msg.created_at.strftime('%d.%m %H:%M')}):\n{msg.message}"

        await message.answer(text, parse_mode="HTML")

# Обработчики callback-запросов для быстрых действий с тикетами
@router.callback_query(F.data.startswith("view_ticket_"))
async def handle_view_ticket(callback: CallbackQuery):
    """Быстрый просмотр тикета"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await callback.answer("❌ У вас нет прав администратора", show_alert=True)
            return
        
        ticket_number = callback.data.split("_")[-1]
        
        from app.services.support_service import SupportService
        support_service = SupportService(session)
        
        ticket = await support_service.get_ticket_by_number(ticket_number)
        if not ticket:
            await callback.answer("❌ Тикет не найден", show_alert=True)
            return
        
        user = await user_service.get_user_by_id(ticket.user_id)
        
        status_emoji = {"new": "🆕", "in_progress": "⏳", "closed": "✅"}.get(ticket.status, "❓")
        category_name = {"connection": "🔌 Подключение", "payment": "💳 Оплата", "technical": "⚙️ Техника", "setup": "📱 Настройка", "other": "❓ Другое"}.get(ticket.category, "❓ Другое")
        
        text = f"""🎫 <b>Тикет: {ticket.ticket_number}</b>

{status_emoji} <b>Статус:</b> {ticket.status.title()}
📂 <b>Категория:</b> {category_name}
👤 <b>Пользователь:</b> {user.first_name} (@{user.username or 'без username'})
📧 <b>Telegram ID:</b> <code>{user.telegram_id}</code>
📅 <b>Создан:</b> {ticket.created_at.strftime('%d.%m.%Y %H:%M')}

📝 <b>Сообщение:</b>
{ticket.message}"""

        if ticket.admin_response:
            text += f"""

💬 <b>Ответ администратора:</b>
{ticket.admin_response}"""

        # Создаем кнопки для дальнейших действий
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Ответить", callback_data=f"reply_ticket_{ticket_number}"),
                InlineKeyboardButton(text="✅ Закрыть", callback_data=f"close_ticket_{ticket_number}")
            ]
        ])

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
        await callback.answer()

@router.callback_query(F.data.startswith("reply_ticket_"))
async def handle_reply_ticket(callback: CallbackQuery, state: FSMContext):
    """Запуск процесса ответа на тикет"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await callback.answer("❌ У вас нет прав администратора", show_alert=True)
            return
        
        ticket_number = callback.data.split("_")[-1]
        
        from app.services.support_service import SupportService
        support_service = SupportService(session)
        
        ticket = await support_service.get_ticket_by_number(ticket_number)
        if not ticket:
            await callback.answer("❌ Тикет не найден", show_alert=True)
            return
        
        # Сохраняем номер тикета в состоянии FSM
        await state.set_state(SupportReplyStates.waiting_for_reply)
        await state.update_data(ticket_number=ticket_number, callback_message_id=callback.message.message_id)
        
        # Создаем кнопку отмены
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_reply")]
        ])
        
        await callback.message.edit_text(
            f"✍️ <b>Ответ на тикет {ticket_number}</b>\n\nНапишите ваш ответ пользователю:", 
            parse_mode="HTML", 
            reply_markup=keyboard
        )
        await callback.answer()

@router.callback_query(F.data.startswith("close_ticket_"))
async def handle_close_ticket(callback: CallbackQuery):
    """Быстрое закрытие тикета"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(callback.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await callback.answer("❌ У вас нет прав администратора", show_alert=True)
            return
        
        ticket_number = callback.data.split("_")[-1]
        
        from app.services.support_service import SupportService
        support_service = SupportService(session)
        
        ticket = await support_service.get_ticket_by_number(ticket_number)
        if not ticket:
            await callback.answer("❌ Тикет не найден", show_alert=True)
            return
        
        if ticket.status == "closed":
            await callback.answer("ℹ️ Тикет уже закрыт", show_alert=True)
            return
        
        # Закрываем тикет
        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        if not ticket.admin_id:
            ticket.admin_id = admin_user.id
        
        await session.commit()
        
        # Уведомляем пользователя
        user = await user_service.get_user_by_id(ticket.user_id)
        if user:
            user_text = f"""✅ <b>Тикет закрыт</b>

🎫 <b>Тикет:</b> {ticket.ticket_number}
📅 <b>Дата закрытия:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

Ваше обращение было рассмотрено и закрыто. Если у вас возникнут новые вопросы, создайте новое обращение через меню "💬 Поддержка".

Спасибо за обращение! 🙏"""
            
            try:
                await callback.bot.send_message(
                    chat_id=user.telegram_id,
                    text=user_text,
                    parse_mode="HTML"
                )
            except Exception:
                pass
        
        await callback.message.edit_text(
            f"✅ <b>Тикет {ticket_number} закрыт</b>\n\nПользователь получил уведомление о закрытии тикета.",
            parse_mode="HTML"
        )
        await callback.answer("✅ Тикет закрыт успешно!")

@router.callback_query(F.data == "cancel_reply")
async def handle_cancel_reply(callback: CallbackQuery, state: FSMContext):
    """Отмена процесса ответа на тикет"""
    await state.clear()
    await callback.message.edit_text("❌ Ответ на тикет отменен")
    await callback.answer()

@router.message(SupportReplyStates.waiting_for_reply)
async def process_reply_text(message: Message, state: FSMContext):
    """Обработка текста ответа на тикет"""
    async with AsyncSessionLocal() as session:
        user_service = UserService(session)
        
        # Проверяем что пользователь админ
        admin_user = await user_service.get_user_by_telegram_id(message.from_user.id)
        if not admin_user or not admin_user.is_admin:
            await message.answer("❌ У вас нет прав администратора")
            await state.clear()
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        ticket_number = data.get("ticket_number")
        callback_message_id = data.get("callback_message_id")
        
        reply_text = message.text
        
        from app.services.support_service import SupportService
        support_service = SupportService(session)
        
        # Находим тикет
        ticket = await support_service.get_ticket_by_number(ticket_number)
        if not ticket:
            await message.answer("❌ Тикет не найден")
            await state.clear()
            return
        
        # Обновляем тикет
        ticket.admin_response = reply_text
        ticket.admin_id = admin_user.id
        ticket.status = "in_progress"
        ticket.responded_at = datetime.utcnow()
        
        # Добавляем сообщение в историю
        await support_service.add_message_to_ticket(
            ticket.id,
            admin_id=admin_user.id,
            message=reply_text,
            is_from_admin=True
        )
        
        await session.commit()
        
        # Отправляем ответ пользователю
        user = await user_service.get_user_by_id(ticket.user_id)
        if user:
            user_text = f"""📬 <b>Ответ службы поддержки</b>

🎫 <b>Тикет:</b> {ticket.ticket_number}
📅 <b>Время ответа:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

💬 <b>Ответ:</b>
{reply_text}

Если у вас есть дополнительные вопросы по этому тикету, просто ответьте на это сообщение."""
            
            try:
                await message.bot.send_message(
                    chat_id=user.telegram_id,
                    text=user_text,
                    parse_mode="HTML"
                )
                success_msg = "✅ Ответ отправлен пользователю успешно!"
            except Exception:
                success_msg = "✅ Ответ сохранен, но не удалось отправить пользователю"
        else:
            success_msg = "✅ Ответ сохранен"
        
        # Удаляем исходное сообщение с вопросом (если возможно)
        try:
            await message.bot.delete_message(message.chat.id, callback_message_id)
        except Exception:
            pass
        
        await message.answer(f"✅ <b>Ответ на тикет {ticket_number} отправлен</b>\n\n{success_msg}", parse_mode="HTML")
        await state.clear()

def register_admin_handlers(dp):
    """Регистрация обработчиков администратора"""
    dp.include_router(router) 