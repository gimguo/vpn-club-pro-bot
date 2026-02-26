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
        (25, "👑 Мастер"),
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
    
    text = f"""👥 <b>Приведи друга — получи бонус!</b>

📊 <b>Ваша статистика:</b>
{level}
├ Приглашено: <b>{invited}</b> друзей
├ Бонус: <b>{bonus}</b> дней
└ До след. уровня: {next_level}

🎁 <b>Как это работает:</b>
1️⃣ Поделитесь ссылкой с другом
2️⃣ Друг получает <b>{settings.referral_trial_days} дней</b> бесплатно
3️⃣ Вы получаете <b>+{settings.referral_bonus_days} дней</b> к подписке

⚠️ <i>Рассылка ссылок без согласия получателей запрещена</i>

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
    
    text = f"""👥 <b>Приведи друга — получи бонус!</b>

Приглашено: <b>{stats['referral_count']}</b> | Бонус: <b>{stats['bonus_days']}</b> дней

🎁 За каждого друга: <b>+{settings.referral_bonus_days} дней</b> к подписке

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


# ─── Условия использования ──────────────────────────────────────

from aiogram.filters import Command

# ── Условия использования (полная версия — 2 сообщения) ───────

TERMS_PART1 = """📜 <b>Пользовательское соглашение</b>
<b>Сервис VPN Club Pro</b>
Дата вступления в силу: 26 февраля 2026 г.

<b>1. Описание сервиса</b>
ИП предоставляет услугу организации защищённого шифрованного канала связи (прокси-сервер) для обеспечения конфиденциальности данных пользователя, защиты соединения в публичных сетях Wi-Fi и безопасного удалённого доступа к ресурсам сети Интернет.

Сервис <b>не предназначен</b> для доступа к информационным ресурсам, доступ к которым ограничен на территории Российской Федерации в соответствии с действующим законодательством.

<b>2. Обязанности пользователя</b>
Пользователь обязуется:
• Использовать сервис исключительно в законных целях и в соответствии с законодательством Российской Федерации и своей страны пребывания
• <b>Не использовать сервис для доступа к ресурсам, заблокированным по решению Роскомнадзора или иных уполномоченных органов РФ</b>
• Не использовать сервис для распространения вредоносного ПО, спама, фишинга или иной противоправной деятельности
• Не передавать учётные данные (ключ доступа) третьим лицам
• Не создавать чрезмерную нагрузку на инфраструктуру сервиса
• Не использовать сервис для совершения действий, нарушающих права третьих лиц

<b>3. Соответствие законодательству</b>
Сервис функционирует в соответствии с требованиями:
• Федерального закона № 149-ФЗ «Об информации, информационных технологиях и о защите информации»
• Федерального закона № 152-ФЗ «О персональных данных»
• Иных применимых нормативно-правовых актов РФ

Администрация оставляет за собой право ограничивать функциональность сервиса в целях соблюдения требований регулирующих органов."""

TERMS_PART2 = """<b>4. Реферальная программа</b>
• Приглашающий получает бонусные дни за каждого нового зарегистрированного пользователя
• Запрещена массовая рассылка реферальных ссылок без согласия получателей (ФЗ «О рекламе» № 38-ФЗ)
• Реферальные материалы не должны содержать упоминаний об обходе блокировок, доступе к запрещённым ресурсам или анонимизации противоправной деятельности
• Администрация вправе аннулировать бонусы и заблокировать аккаунт при нарушении правил

<b>5. Оплата и возвраты</b>
• Пробный период предоставляется бесплатно, однократно
• Платные подписки активируются после подтверждения оплаты
• Возврат средств возможен в течение 24 часов после оплаты при условии, что услуга фактически не использовалась (объём переданных данных = 0)
• Для возврата обратитесь через меню «💬 Поддержка»

<b>6. Ограничение ответственности</b>
• Сервис предоставляется «как есть» (as is) без каких-либо гарантий
• Администрация не несёт ответственности за действия пользователя при использовании сервиса
• Администрация не гарантирует бесперебойную работу и оставляет за собой право на проведение технических работ
• Пользователь несёт полную ответственность за соблюдение законодательства при использовании сервиса

<b>7. Обработка персональных данных</b>
Подробная информация — /privacy
Нажимая «Принимаю», вы даёте согласие на обработку персональных данных в соответствии с Политикой конфиденциальности.

<b>8. Изменение условий</b>
• Администрация вправе изменять условия с уведомлением через бот
• Продолжение использования сервиса после уведомления означает согласие с новыми условиями
• Актуальная версия всегда доступна по команде /terms

По вопросам: меню «💬 Поддержка»"""


# ── Политика конфиденциальности ───────────────────────────────

PRIVACY_PART1 = """🔒 <b>Политика конфиденциальности</b>
<b>Сервис VPN Club Pro</b>
Дата вступления в силу: 26 февраля 2026 г.

<b>1. Общие положения</b>
Настоящая Политика разработана в соответствии с Федеральным законом № 152-ФЗ «О персональных данных» и определяет порядок обработки и защиты персональных данных пользователей.

<b>2. Оператор персональных данных</b>
Оператором является индивидуальный предприниматель — владелец сервиса VPN Club Pro. Контакт: через меню «💬 Поддержка» в боте.

<b>3. Собираемые данные</b>
Мы собираем и обрабатываем:
• Telegram ID (числовой идентификатор)
• Имя пользователя (username) и имя в Telegram
• Дата и время регистрации
• Тип оформленной подписки и срок её действия
• Реферальный код (при наличии)
• Данные об оплате (ID транзакции — без данных карты)

<b>4. Данные, которые мы НЕ собираем</b>
• Логи сетевой активности (посещённые сайты, DNS-запросы)
• IP-адреса пользователей
• Содержимое передаваемого трафика
• Геолокация пользователя
• Данные банковских карт (обрабатываются ЮKassa)

Серверы инфраструктуры расположены в юрисдикциях, не требующих обязательного логирования пользовательского трафика. Техническая архитектура сервиса (Outline/Shadowbox) не предусматривает хранение логов активности."""

PRIVACY_PART2 = """<b>5. Цели обработки данных</b>
• Предоставление доступа к сервису
• Управление подписками и ключами доступа
• Обработка платежей
• Функционирование реферальной программы
• Техническая поддержка
• Уведомления о статусе подписки

<b>6. Правовые основания</b>
• Согласие пользователя (ст. 9 ФЗ-152) — предоставляется при нажатии «Принимаю» при регистрации
• Исполнение договора (ст. 6 ч. 1 п. 5 ФЗ-152) — предоставление оплаченной услуги

<b>7. Сроки хранения</b>
• Данные активных пользователей — в течение срока действия подписки
• После окончания подписки — 12 месяцев (для возможности восстановления)
• Данные об оплатах — 5 лет (требование бухгалтерского учёта)
• По запросу пользователя данные удаляются в течение 30 дней

<b>8. Права пользователя</b>
Вы имеете право:
• Запросить информацию о хранимых данных
• Потребовать исправления неточных данных
• Потребовать удаления своих данных (отзыв согласия)
• Получить данные в машиночитаемом формате

Для реализации прав обратитесь через «💬 Поддержка».

<b>9. Защита данных</b>
• Шифрование данных при передаче (TLS/SSL)
• Разграничение доступа к базе данных
• Регулярное обновление программного обеспечения
• Серверы в защищённых дата-центрах

<b>10. Передача третьим лицам</b>
Данные не передаются третьим лицам, за исключением:
• ЮKassa — обработка платежей (ID транзакции)
• По требованию уполномоченных органов в случаях, предусмотренных законом

Актуальная версия: /privacy"""


@router.message(Command("terms"))
async def show_terms(message: Message):
    """Условия использования — полная версия"""
    await message.answer(TERMS_PART1, parse_mode="HTML")
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Политика конфиденциальности", callback_data="show_privacy")],
    ])
    await message.answer(TERMS_PART2, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("privacy"))
async def show_privacy(message: Message):
    """Политика конфиденциальности — полная версия"""
    await message.answer(PRIVACY_PART1, parse_mode="HTML")
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Условия использования", callback_data="show_terms")],
    ])
    await message.answer(PRIVACY_PART2, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "show_terms")
async def show_terms_callback(callback: CallbackQuery):
    """Краткие условия через inline"""
    text = """📜 <b>Условия использования (кратко)</b>

Используя VPN Club Pro, вы подтверждаете:
• Сервис используется для защиты данных в сети
• Сервис <b>не предназначен</b> для доступа к ресурсам, заблокированным на территории РФ
• Вы обязуетесь соблюдать законодательство РФ
• Вы согласны с обработкой данных (/privacy)

Полная версия: /terms"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Политика конфиденц.", callback_data="show_privacy")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "show_privacy")
async def show_privacy_callback(callback: CallbackQuery):
    """Краткая политика через inline"""
    text = """🔒 <b>Политика конфиденциальности (кратко)</b>

<b>Собираем:</b> Telegram ID, имя, тип подписки, данные оплаты
<b>НЕ собираем:</b> логи трафика, IP-адреса, посещённые сайты

• Данные не передаются третьим лицам
• Вы можете запросить удаление данных
• Серверы не ведут логов сетевой активности

Полная версия: /privacy"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Условия использования", callback_data="show_terms")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ── Принятие условий при регистрации ──────────────────────────

@router.callback_query(F.data.startswith("accept_terms"))
async def accept_terms(callback: CallbackQuery):
    """Пользователь принял условия — записываем согласие и продолжаем"""
    from datetime import datetime as dt
    import pytz

    # Извлекаем реферальный код, если был
    referral_code = None
    if ":" in callback.data:
        referral_code = callback.data.split(":", 1)[1]

    async with AsyncSessionLocal() as session:
        us = UserService(session)
        user = await us.get_user_by_telegram_id(callback.from_user.id)
        if user:
            user.terms_accepted = True
            user.terms_accepted_at = dt.now(pytz.UTC)
            await session.commit()
            logger.info(f"Terms accepted by user {user.telegram_id}")

            # Обрабатываем реферал, если есть
            if referral_code and not user.referred_by:
                success = await us.process_referral(user, referral_code)
                if success:
                    logger.info(f"Referral processed: user {user.telegram_id} via code {referral_code}")

    await callback.message.edit_text(
        "✅ <b>Условия приняты!</b>\n\n"
        "Добро пожаловать в VPN Club Pro.\n"
        "Нажмите /start для начала работы.",
        parse_mode="HTML",
    )
    await callback.answer("✅ Добро пожаловать!")


@router.callback_query(F.data == "decline_terms")
async def decline_terms(callback: CallbackQuery):
    """Пользователь отклонил условия"""
    await callback.message.edit_text(
        "❌ <b>Условия не приняты</b>\n\n"
        "Для использования сервиса необходимо принять\n"
        "условия и дать согласие на обработку данных.\n\n"
        "Нажмите /start чтобы попробовать снова.",
        parse_mode="HTML",
    )
    await callback.answer()


def register_common_handlers(dp):
    """Регистрация общих обработчиков"""
    dp.include_router(router)
