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
Редакция от 26 февраля 2026 г.

<b>1. Описание сервиса</b>
Индивидуальный предприниматель (далее — «Оператор») предоставляет услугу организации защищённого шифрованного канала связи для обеспечения конфиденциальности данных пользователя, защиты соединения в публичных сетях Wi-Fi и безопасного удалённого доступа к ресурсам сети Интернет.

Сервис <b>не предназначен</b> для доступа к информационным ресурсам, доступ к которым ограничен на территории Российской Федерации в соответствии с действующим законодательством.

<b>2. Обязанности пользователя</b>
Пользователь обязуется:
• Использовать сервис исключительно в законных целях и в соответствии с законодательством РФ и страны пребывания
• <b>Не использовать сервис для обхода блокировок, установленных Роскомнадзором или иными уполномоченными органами РФ, и не предпринимать действий, направленных на доступ к запрещённым ресурсам</b>
• Не использовать сервис для распространения вредоносного ПО, спама, фишинга или иной противоправной деятельности
• Не передавать учётные данные (ключ доступа) третьим лицам
• Не создавать чрезмерную нагрузку на инфраструктуру сервиса
• Не использовать сервис для нарушения прав третьих лиц
• <b>Незамедлительно сообщить Оператору</b> об обнаружении сбоев или уязвимостей, которые могут привести к нарушению законодательства или утечке данных"""

TERMS_PART2 = """<b>3. Соответствие законодательству и взаимодействие с РКН</b>
Сервис функционирует в соответствии с:
• ФЗ № 149-ФЗ «Об информации, информационных технологиях и о защите информации»
• ФЗ № 152-ФЗ «О персональных данных»
• Требованиями Роскомнадзора к операторам, предоставляющим услуги шифрованного доступа к сети Интернет
• Иными применимыми нормативно-правовыми актами РФ

Оператор взаимодействует с Роскомнадзором в установленном законом порядке. Оператор вправе ограничивать функциональность сервиса в целях выполнения требований регулирующих органов, в том числе в части фильтрации доступа к ресурсам, включённым в Единый реестр запрещённой информации.

Оператор обеспечивает защиту персональных данных, включая их обезличение при обработке в аналитических целях, и локализацию хранения учётных данных пользователей на территории Российской Федерации (п. 5 ст. 18 ФЗ-152).

<b>4. Реферальная программа</b>
• Приглашающий получает бонусные дни за каждого нового зарегистрированного пользователя
• Запрещена массовая рассылка реферальных ссылок без согласия получателей (ФЗ № 38-ФЗ «О рекламе»)
• Реферальные материалы <b>не должны</b> содержать упоминаний об обходе блокировок, доступе к запрещённым ресурсам или анонимизации противоправной деятельности (ФЗ № 281-ФЗ)
• Оператор вправе аннулировать бонусы и заблокировать аккаунт при нарушении правил"""

TERMS_PART3 = """<b>5. Оплата и возвраты</b>
• Пробный период — бесплатно, однократно
• Платные подписки активируются после подтверждения оплаты
• Возврат средств возможен в течение 24 часов, если услуга не использовалась (объём данных = 0)
• Для возврата обратитесь через «💬 Поддержка»

<b>6. Ограничение ответственности</b>
• Сервис предоставляется «как есть» (as is) без каких-либо гарантий
• Оператор не несёт ответственности за действия пользователя
• Оператор не гарантирует бесперебойную работу и вправе проводить технические работы
• Пользователь несёт полную ответственность за соблюдение законодательства при использовании сервиса

<b>7. Обработка персональных данных</b>
Согласие на обработку ПД оформляется <b>отдельно</b> при регистрации в соответствии со ст. 9 ФЗ-152.
Подробности — /privacy

<b>8. Изменение условий</b>
• Оператор вправе изменять условия с уведомлением через бот
• Продолжение использования означает согласие с новыми условиями
• Актуальная версия: /terms

По вопросам: «💬 Поддержка»"""


# ── Политика конфиденциальности ───────────────────────────────

PRIVACY_PART1 = """🔒 <b>Политика конфиденциальности</b>
<b>Сервис VPN Club Pro</b>
Редакция от 26 февраля 2026 г.

<b>1. Общие положения</b>
Настоящая Политика разработана в соответствии с ФЗ № 152-ФЗ «О персональных данных» и определяет порядок обработки и защиты персональных данных пользователей.

<b>2. Оператор персональных данных</b>
Оператором является индивидуальный предприниматель — владелец сервиса VPN Club Pro.
Оператор уведомил Роскомнадзор о начале обработки персональных данных в соответствии со ст. 22 ФЗ-152 и включён в Реестр операторов персональных данных.
Контакт: меню «💬 Поддержка» в боте.

<b>3. Собираемые данные</b>
Мы собираем и обрабатываем:
• Telegram ID (числовой идентификатор)
• Имя пользователя (username) и имя в Telegram
• Дата и время регистрации
• Тип подписки и срок действия
• Реферальный код (при наличии)
• Данные об оплате (ID транзакции — без данных карты)
• Дата и время дачи согласия на обработку ПД

<b>4. Данные, которые мы НЕ собираем</b>
• Логи сетевой активности (посещённые сайты, DNS-запросы)
• IP-адреса пользователей
• Содержимое передаваемого трафика
• Геолокация пользователя
• Данные банковских карт (обрабатываются ЮKassa)

Техническая архитектура сервиса (протокол Shadowsocks / Outline) конструктивно не предусматривает сбор и хранение логов сетевой активности. Данный факт может быть подтверждён техническим аудитом исходного кода."""

PRIVACY_PART2 = """<b>5. Цели обработки данных</b>
• Предоставление доступа к сервису
• Управление подписками и ключами доступа
• Обработка платежей
• Функционирование реферальной программы
• Техническая поддержка
• Уведомления о статусе подписки

<b>6. Правовые основания</b>
• Согласие субъекта ПД (ст. 9 ФЗ-152) — оформляется <b>отдельно</b> от иных документов при регистрации
• Исполнение договора (ст. 6 ч. 1 п. 5 ФЗ-152) — предоставление оплаченной услуги

<b>7. Локализация и хранение данных</b>
• Учётные данные пользователей (Telegram ID, подписки, платежи) хранятся в базе данных, расположенной на территории Российской Федерации, в соответствии с п. 5 ст. 18 ФЗ-152
• VPN-серверы (инфраструктура передачи данных) расположены за пределами РФ, однако <b>не хранят</b> персональные данные пользователей
• При обработке данных в аналитических целях применяется обезличение

<b>8. Сроки хранения</b>
• Данные активных пользователей — в течение срока подписки
• После окончания подписки — 12 месяцев (восстановление)
• Данные об оплатах — 5 лет (бухгалтерский учёт)
• По запросу пользователя данные удаляются в течение 30 дней"""

PRIVACY_PART3 = """<b>9. Права пользователя</b>
Вы имеете право (ст. 14 ФЗ-152):
• Запросить информацию о хранимых данных
• Потребовать исправления неточных данных
• Потребовать удаления данных (отзыв согласия — ст. 9 ч. 2 ФЗ-152)
• Получить данные в машиночитаемом формате
• Обжаловать действия Оператора в Роскомнадзор

Для реализации прав: «💬 Поддержка». Срок ответа — 10 рабочих дней.

<b>10. Защита данных</b>
• Шифрование при передаче (TLS/SSL)
• Разграничение доступа к БД
• Регулярное обновление ПО
• Серверы в защищённых дата-центрах

<b>11. Реагирование на инциденты</b>
В случае обнаружения утечки персональных данных Оператор обязуется:
• Уведомить Роскомнадзор в течение 24 часов с момента обнаружения
• Уведомить затронутых пользователей через бот
• Провести расследование и принять меры по устранению последствий
• Предоставить Роскомнадзору результаты расследования в течение 72 часов

<b>12. Передача третьим лицам</b>
Данные не передаются третьим лицам, за исключением:
• ЮKassa — обработка платежей (ID транзакции)
• Роскомнадзор — по требованию в случаях, предусмотренных законом
• Иные уполномоченные органы — на основании судебного решения

Актуальная версия: /privacy"""


@router.message(Command("terms"))
async def show_terms(message: Message):
    """Условия использования — полная версия (3 сообщения)"""
    await message.answer(TERMS_PART1, parse_mode="HTML")
    await message.answer(TERMS_PART2, parse_mode="HTML")
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Политика конфиденциальности", callback_data="show_privacy")],
    ])
    await message.answer(TERMS_PART3, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("privacy"))
async def show_privacy(message: Message):
    """Политика конфиденциальности — полная версия (3 сообщения)"""
    await message.answer(PRIVACY_PART1, parse_mode="HTML")
    await message.answer(PRIVACY_PART2, parse_mode="HTML")
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Условия использования", callback_data="show_terms")],
    ])
    await message.answer(PRIVACY_PART3, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data == "show_terms")
async def show_terms_callback(callback: CallbackQuery):
    """Краткие условия через inline"""
    text = """📜 <b>Условия использования (кратко)</b>

Используя VPN Club Pro, вы подтверждаете:
• Сервис используется для защиты данных в сети
• Сервис <b>не предназначен</b> для обхода блокировок РКН
• Вы обязуетесь соблюдать законодательство РФ
• Оператор взаимодействует с Роскомнадзором
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

<b>Собираем:</b> Telegram ID, имя, тип подписки, дата согласия
<b>НЕ собираем:</b> логи трафика, IP, посещённые сайты

• Оператор включён в Реестр операторов ПД (ст. 22 ФЗ-152)
• Учётные данные хранятся в РФ (ст. 18 ФЗ-152)
• Вы можете запросить удаление данных
• При утечке — уведомление РКН в течение 24ч

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
    """Шаг 1 пройден — условия приняты. Переходим к Шагу 2: согласие на ПД."""
    from datetime import datetime as dt

    # Извлекаем реферальный код
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

    # Шаг 2: Отдельное согласие на обработку ПД (ст. 9 ФЗ-152)
    ref_suffix = f":{referral_code}" if referral_code else ""

    text = """✅ Условия приняты!

<b>Шаг 2 из 2:</b> 🔒 <b>Согласие на обработку персональных данных</b>

В соответствии со ст. 9 ФЗ-152 «О персональных данных», нажимая «✅ Даю согласие», вы подтверждаете:

• <b>Оператор:</b> ИП — владелец VPN Club Pro
• <b>Цель:</b> предоставление услуг сервиса, управление подписками, обработка платежей
• <b>Перечень данных:</b> Telegram ID, имя, username, тип подписки, данные оплаты (ID транзакции)
• <b>Действия:</b> сбор, хранение, обработка, удаление
• <b>Срок:</b> до отзыва согласия или 12 мес после окончания подписки
• <b>Порядок отзыва:</b> через «💬 Поддержка» (данные удаляются в течение 30 дней)

Подробнее: /privacy"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Даю согласие", callback_data=f"accept_pd{ref_suffix}")],
        [InlineKeyboardButton(text="🔒 Прочитать политику", callback_data="show_privacy")],
        [InlineKeyboardButton(text="❌ Отказываюсь", callback_data="decline_terms")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("accept_pd"))
async def accept_pd_consent(callback: CallbackQuery):
    """Шаг 2 пройден — согласие на обработку ПД дано. Регистрация завершена."""
    from datetime import datetime as dt

    referral_code = None
    if ":" in callback.data:
        referral_code = callback.data.split(":", 1)[1]

    async with AsyncSessionLocal() as session:
        us = UserService(session)
        user = await us.get_user_by_telegram_id(callback.from_user.id)
        if user:
            user.pd_consent = True
            user.pd_consent_at = dt.now(pytz.UTC)
            await session.commit()
            logger.info(f"PD consent given by user {user.telegram_id}")

            # Обрабатываем реферал
            if referral_code and not user.referred_by:
                success = await us.process_referral(user, referral_code)
                if success:
                    logger.info(f"Referral processed: user {user.telegram_id} via code {referral_code}")

    await callback.message.edit_text(
        "✅ <b>Регистрация завершена!</b>\n\n"
        "📜 Условия приняты\n"
        "🔒 Согласие на обработку ПД получено\n\n"
        "Добро пожаловать в VPN Club Pro!\n"
        "Нажмите /start для начала работы.",
        parse_mode="HTML",
    )
    await callback.answer("✅ Добро пожаловать!")


@router.callback_query(F.data == "decline_terms")
async def decline_terms(callback: CallbackQuery):
    """Пользователь отклонил условия или согласие на ПД"""
    await callback.message.edit_text(
        "❌ <b>Регистрация не завершена</b>\n\n"
        "Для использования сервиса необходимо:\n"
        "1. Принять условия использования\n"
        "2. Дать согласие на обработку ПД\n\n"
        "Нажмите /start чтобы попробовать снова.",
        parse_mode="HTML",
    )
    await callback.answer()


def register_common_handlers(dp):
    """Регистрация общих обработчиков"""
    dp.include_router(router)
