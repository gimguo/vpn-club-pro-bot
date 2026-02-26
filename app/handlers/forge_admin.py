"""
VPN Forge — Админ-панель в Telegram-боте.

Команды:
  /forge       — Панель управления флотом серверов
  Callbacks:
    forge_*    — Навигация по панели
"""
import logging
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from config import settings

logger = logging.getLogger(__name__)
router = Router()

STATUS_EMOJI = {
    "active": "🟢",
    "degraded": "🟡",
    "maintenance": "🔧",
    "deploying": "🔵",
    "provisioning": "🔵",
    "offline": "⚫",
    "error": "🔴",
}


def is_admin(user_id: int) -> bool:
    return user_id == settings.admin_id


# ── /forge — Главная панель ───────────────────────────────

@router.message(Command("forge"))
async def forge_panel(message: Message):
    """Главная панель VPN Forge."""
    if not is_admin(message.from_user.id):
        return

    if not settings.vpn_forge_enabled:
        await message.answer("❌ VPN Forge отключён. Установите VPN_FORGE_ENABLED=true в .env")
        return

    from app.vpn_forge.manager import ForgeManager
    manager = ForgeManager()
    stats = await manager.get_fleet_stats()

    text = f"""🏗️ <b>VPN Forge — Панель управления</b>

🖥️ <b>Флот серверов:</b> {stats['total']}
   🟢 Active: {stats['active']}
   🟡 Degraded: {stats['degraded']}
   🔧 Maintenance: {stats['maintenance']}
   🔵 Deploying: {stats['deploying']}
   ⚫ Offline: {stats['offline']}

📊 <b>Загрузка:</b> {stats['avg_load']}% ({stats['total_keys']}/{stats['total_capacity']} ключей)
💰 <b>Расходы:</b> ~€{stats['monthly_cost_eur']}/мес

⚙️ <b>Настройки:</b>
   Scale UP: &gt;{settings.vpn_forge_scale_up_threshold}% → новый сервер
   Scale DOWN: &lt;{settings.vpn_forge_scale_down_threshold}% → убрать лишний
   Max серверов: {settings.vpn_forge_max_servers}
   Monitor: каждые {settings.vpn_forge_monitor_interval}с"""

    # Список серверов
    if stats["servers"]:
        text += "\n\n<b>Серверы:</b>"
        for s in stats["servers"]:
            emoji = STATUS_EMOJI.get(s["status"], "❓")
            check = s.get("last_check", "—")
            check_emoji = {"ok": "✅", "warning": "⚠️", "critical": "❌"}.get(check, "—")
            text += (
                f"\n{emoji} <b>{s['name']}</b> ({s['ip']})"
                f"\n   {s['country']} {s['region']} | {s['keys']}/{s['max_keys']} ключей | {check_emoji}"
            )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="forge_refresh")],
        [
            InlineKeyboardButton(text="➕ Добавить сервер", callback_data="forge_add"),
            InlineKeyboardButton(text="🚀 Scale UP", callback_data="forge_scale_up"),
        ],
        [
            InlineKeyboardButton(text="🤖 AI Status", callback_data="forge_ai_status"),
            InlineKeyboardButton(text="📋 Лог событий", callback_data="forge_events"),
        ],
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# ── Обновление панели ─────────────────────────────────────

@router.callback_query(F.data == "forge_refresh")
async def forge_refresh(callback: CallbackQuery):
    """Обновить панель."""
    if not is_admin(callback.from_user.id):
        return

    from app.vpn_forge.manager import ForgeManager
    manager = ForgeManager()
    stats = await manager.get_fleet_stats()

    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    text = f"""🏗️ <b>VPN Forge — Панель управления</b>

🖥️ <b>Флот:</b> {stats['active']}🟢 {stats['degraded']}🟡 {stats['maintenance']}🔧 {stats['deploying']}🔵 {stats['offline']}⚫
📊 <b>Загрузка:</b> {stats['avg_load']}% ({stats['total_keys']}/{stats['total_capacity']})
💰 <b>Расходы:</b> ~€{stats['monthly_cost_eur']}/мес
🕐 Обновлено: {now} UTC"""

    if stats["servers"]:
        text += "\n"
        for s in stats["servers"]:
            emoji = STATUS_EMOJI.get(s["status"], "❓")
            text += f"\n{emoji} <b>{s['name']}</b> {s['ip']} | {s['keys']}/{s['max_keys']}"

    # Кнопки серверов + управление
    buttons = []
    for s in stats["servers"]:
        emoji = STATUS_EMOJI.get(s["status"], "❓")
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {s['name']} — детали",
            callback_data=f"forge_server_{s['id']}",
        )])

    buttons.extend([
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="forge_refresh")],
        [
            InlineKeyboardButton(text="➕ Добавить", callback_data="forge_add"),
            InlineKeyboardButton(text="🚀 Scale UP", callback_data="forge_scale_up"),
        ],
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("Данные актуальны ✅")
            return
        raise
    await callback.answer("✅ Обновлено")


# ── Детали сервера ────────────────────────────────────────

@router.callback_query(F.data.startswith("forge_server_"))
async def forge_server_details(callback: CallbackQuery):
    """Показать детали сервера."""
    if not is_admin(callback.from_user.id):
        return

    server_id = int(callback.data.removeprefix("forge_server_"))

    from app.vpn_forge.manager import ForgeManager
    manager = ForgeManager()
    details = await manager.get_server_details(server_id)

    if not details:
        await callback.answer("Сервер не найден", show_alert=True)
        return

    s = details["server"]
    emoji = STATUS_EMOJI.get(s["status"], "❓")

    text = f"""{emoji} <b>{s['name']}</b>

🌍 {s['country']} {s['region']} | {s['provider']} | {s.get('plan', '—')}
🌐 IP: <code>{s['ip']}</code>
📊 Ключи: {s['keys']}/{s['max_keys']} ({s['load']}%)
💰 Стоимость: €{s['cost_eur']}/мес

<b>Метрики:</b>
   CPU: {s['cpu'] or '—'}%
   RAM: {s['mem'] or '—'}%
   Disk: {s['disk'] or '—'}%

🔧 Auto-heal: {'✅' if s['auto_heal'] else '❌'}
❌ Ошибок подряд: {s['consecutive_failures']}
📅 Создан: {s.get('created_at', '—')[:10] if s.get('created_at') else '—'}
🩺 Проверка: {s.get('last_health_check', '—')[:16] if s.get('last_health_check') else '—'}"""

    # Последние события
    if details["events"]:
        text += "\n\n<b>📋 Последние события:</b>"
        for e in details["events"][:5]:
            sev = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🔴"}.get(e["severity"], "•")
            time_str = e["at"][:16] if e["at"] else "—"
            text += f"\n{sev} [{time_str}] {e['type']}"
            if e["message"]:
                text += f"\n   {e['message'][:80]}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🤖 AI Диагностика", callback_data=f"forge_ai_diag_{server_id}"),
            InlineKeyboardButton(text="🔄 Перезапуск Outline", callback_data=f"forge_restart_{server_id}"),
        ],
        [
            InlineKeyboardButton(text="🩺 Проверить сейчас", callback_data=f"forge_check_{server_id}"),
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"forge_delete_{server_id}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="forge_refresh")],
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ── AI Диагностика ────────────────────────────────────────

@router.callback_query(F.data.startswith("forge_ai_diag_"))
async def forge_ai_diagnose(callback: CallbackQuery):
    """Запустить ИИ-диагностику сервера."""
    if not is_admin(callback.from_user.id):
        return

    server_id = int(callback.data.removeprefix("forge_ai_diag_"))
    await callback.answer("🤖 Запускаю AI-диагностику... Это может занять до 60 сек.", show_alert=True)

    await callback.message.edit_text(
        "🤖 <b>AI-диагностика запущена...</b>\n\n"
        "⏳ Собираю данные с сервера и отправляю в DeepSeek...",
        parse_mode="HTML",
    )

    from app.vpn_forge.manager import ForgeManager
    manager = ForgeManager()
    result = await manager.trigger_ai_diagnosis(server_id, auto_execute=False)

    if result.get("error"):
        text = f"❌ <b>Ошибка AI-диагностики:</b>\n{result['error']}"
    else:
        text = f"""🤖 <b>AI-диагностика завершена</b>

📋 <b>Диагноз:</b>
{result.get('diagnosis', 'Нет данных')}

💊 <b>Предложенные команды:</b> {len(result.get('commands', []))}"""

        for i, cmd in enumerate(result.get("commands", [])[:5], 1):
            text += f"\n{i}. <code>{cmd}</code>"

        if result.get("commands"):
            text += "\n\n⚠️ Нажмите «Выполнить» чтобы применить команды."

    buttons = [[InlineKeyboardButton(text="⬅️ К серверу", callback_data=f"forge_server_{server_id}")]]
    if result.get("commands") and not result.get("error"):
        buttons.insert(0, [InlineKeyboardButton(
            text="⚡ Выполнить команды AI",
            callback_data=f"forge_ai_exec_{server_id}",
        )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("forge_ai_exec_"))
async def forge_ai_execute(callback: CallbackQuery):
    """Выполнить команды ИИ-агента."""
    if not is_admin(callback.from_user.id):
        return

    server_id = int(callback.data.removeprefix("forge_ai_exec_"))
    await callback.answer("⚡ Выполняю команды AI...", show_alert=True)

    await callback.message.edit_text(
        "⚡ <b>Выполняю команды AI...</b>\n\nПодождите...",
        parse_mode="HTML",
    )

    from app.vpn_forge.manager import ForgeManager
    manager = ForgeManager()
    result = await manager.trigger_ai_diagnosis(server_id, auto_execute=True)

    if result.get("fixed"):
        text = "✅ <b>Сервер починен AI-агентом!</b>\n\n"
    else:
        text = "⚠️ <b>AI-агент выполнил команды, но сервер всё ещё нездоров</b>\n\n"

    text += f"📋 <b>Диагноз:</b> {result.get('diagnosis', 'N/A')[:200]}\n"

    if result.get("executed"):
        text += "\n<b>Выполнено:</b>"
        for cmd_r in result["executed"][:5]:
            status = "✅" if cmd_r.get("exit_code", 1) == 0 else "❌"
            text += f"\n{status} <code>{cmd_r['command'][:60]}</code>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К серверу", callback_data=f"forge_server_{server_id}")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


# ── Перезапуск Outline ────────────────────────────────────

@router.callback_query(F.data.startswith("forge_restart_"))
async def forge_restart(callback: CallbackQuery):
    """Перезапустить Outline на сервере."""
    if not is_admin(callback.from_user.id):
        return

    server_id = int(callback.data.removeprefix("forge_restart_"))
    await callback.answer("🔄 Перезапускаю Outline...", show_alert=True)

    from app.vpn_forge.manager import ForgeManager
    from app.vpn_forge.models import VPNServer
    from app.vpn_forge.ssh_client import SSHClient
    from app.database import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(VPNServer).where(VPNServer.id == server_id))
        server = result.scalar_one_or_none()

        if not server:
            await callback.message.edit_text("❌ Сервер не найден")
            return

        try:
            async with SSHClient(
                host=server.ip_address,
                username=server.ssh_user,
                port=server.ssh_port,
                key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
            ) as ssh:
                await ssh.run("docker restart shadowbox", timeout=60)

            text = f"✅ Outline перезапущен на <b>{server.name}</b>"
        except Exception as e:
            text = f"❌ Ошибка перезапуска: {str(e)[:200]}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К серверу", callback_data=f"forge_server_{server_id}")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


# ── Ручная проверка ───────────────────────────────────────

@router.callback_query(F.data.startswith("forge_check_"))
async def forge_check_now(callback: CallbackQuery):
    """Запустить проверку сервера прямо сейчас."""
    if not is_admin(callback.from_user.id):
        return

    server_id = int(callback.data.removeprefix("forge_check_"))
    await callback.answer("🩺 Проверяю...", show_alert=True)

    from app.vpn_forge.monitor import ServerMonitor
    from app.vpn_forge.models import VPNServer
    from app.database import AsyncSessionLocal
    from sqlalchemy import select

    monitor = ServerMonitor()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(VPNServer).where(VPNServer.id == server_id))
        server = result.scalar_one_or_none()
        if not server:
            await callback.message.edit_text("❌ Сервер не найден")
            return

        check = await monitor.check_server(server, session)

    status_emoji = {"ok": "✅", "warning": "⚠️", "critical": "❌"}.get(check.status, "❓")

    text = f"""🩺 <b>Результат проверки: {server.name}</b>

{status_emoji} Статус: <b>{check.status}</b>
⏱️ Время ответа: {check.response_time_ms}ms

SSH: {'✅' if check.ssh_ok else '❌'}
Docker: {'✅' if check.docker_ok else '❌'}
Outline API: {'✅' if check.outline_api_ok else '❌'}

CPU: {check.cpu_percent or '—'}%
RAM: {check.memory_percent or '—'}%
Disk: {check.disk_percent or '—'}%"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К серверу", callback_data=f"forge_server_{server_id}")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


# ── Scale UP вручную ──────────────────────────────────────

@router.callback_query(F.data == "forge_scale_up")
async def forge_scale_up(callback: CallbackQuery):
    """Ручной Scale UP."""
    if not is_admin(callback.from_user.id):
        return

    if not settings.hetzner_api_token:
        await callback.answer("❌ Hetzner API token не настроен", show_alert=True)
        return

    await callback.answer("🚀 Создаю новый сервер...", show_alert=True)

    await callback.message.edit_text(
        "🚀 <b>Создаю новый сервер...</b>\n\n"
        "⏳ Аренда + установка Outline займут ~5 минут.\n"
        "Вы получите уведомление по завершению.",
        parse_mode="HTML",
    )

    from app.vpn_forge.manager import ForgeManager
    from app.database import AsyncSessionLocal

    manager = ForgeManager()
    async with AsyncSessionLocal() as session:
        await manager.orchestrator._scale_up(session)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К панели", callback_data="forge_refresh")],
    ])
    await callback.message.edit_text(
        "✅ <b>Сервер создаётся!</b>\n\n"
        "Outline будет установлен автоматически в фоне.\n"
        "Нажмите «К панели» чтобы увидеть статус.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ── Удаление сервера ─────────────────────────────────────

@router.callback_query(F.data.startswith("forge_delete_"))
async def forge_delete_confirm(callback: CallbackQuery):
    """Подтверждение удаления сервера."""
    if not is_admin(callback.from_user.id):
        return

    server_id = int(callback.data.removeprefix("forge_delete_"))

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Да, удалить!", callback_data=f"forge_delete_yes_{server_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"forge_server_{server_id}")],
    ])

    await callback.message.edit_text(
        "⚠️ <b>Вы уверены?</b>\n\n"
        "Сервер будет удалён у провайдера и из базы.\n"
        "Все ключи на этом сервере перестанут работать!",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("forge_delete_yes_"))
async def forge_delete_execute(callback: CallbackQuery):
    """Выполнить удаление сервера."""
    if not is_admin(callback.from_user.id):
        return

    server_id = int(callback.data.removeprefix("forge_delete_yes_"))

    from app.vpn_forge.models import VPNServer, ServerEvent
    from app.vpn_forge.providers.hetzner import HetznerProvider
    from app.database import AsyncSessionLocal
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(VPNServer).where(VPNServer.id == server_id))
        server = result.scalar_one_or_none()

        if not server:
            await callback.answer("Сервер не найден", show_alert=True)
            return

        # Удаляем у провайдера
        if server.provider == "hetzner" and server.provider_server_id:
            try:
                provider = HetznerProvider()
                await provider.delete_server(server.provider_server_id)
            except Exception as e:
                logger.error(f"Provider delete error: {e}")

        server.status = "offline"
        server.is_active = False

        event = ServerEvent(
            server_id=server.id,
            event_type="decommissioned",
            severity="info",
            message="Server manually deleted by admin",
            initiated_by="admin",
        )
        session.add(event)
        await session.commit()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К панели", callback_data="forge_refresh")],
    ])
    await callback.message.edit_text(
        f"🗑️ Сервер <b>{server.name}</b> удалён.",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


# ── Добавление сервера ───────────────────────────────────

@router.callback_query(F.data == "forge_add")
async def forge_add_server(callback: CallbackQuery):
    """Инструкция по добавлению сервера."""
    if not is_admin(callback.from_user.id):
        return

    text = """➕ <b>Добавление сервера</b>

<b>Автоматически (Hetzner):</b>
Нажмите "🚀 Scale UP" — сервер арендуется и настроится автоматически.

<b>Вручную (любой VPS):</b>
Отправьте команду в формате:

<code>/forge_add name ip [user] [port] [api_url]</code>

Примеры:
<code>/forge_add de-manual-1 5.161.100.50</code>
<code>/forge_add nl-custom-1 65.108.1.2 root 22 https://65.108.1.2:1234/abc</code>

Если api_url не указан — Outline будет установлен автоматически."""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="forge_refresh")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("forge_add"))
async def forge_add_server_cmd(message: Message):
    """Добавить сервер вручную через команду."""
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()[1:]  # Убираем /forge_add

    if len(args) < 2:
        await message.answer(
            "❌ Формат: <code>/forge_add name ip [user] [port] [api_url]</code>",
            parse_mode="HTML",
        )
        return

    name = args[0]
    ip = args[1]
    user = args[2] if len(args) > 2 else "root"
    port = int(args[3]) if len(args) > 3 else 22
    api_url = args[4] if len(args) > 4 else None

    from app.vpn_forge.manager import ForgeManager
    manager = ForgeManager()

    result = await manager.add_server(
        name=name,
        ip_address=ip,
        ssh_user=user,
        ssh_port=port,
        outline_api_url=api_url,
    )

    deploy_msg = ""
    if not api_url:
        deploy_msg = "\n\n⏳ Outline устанавливается автоматически в фоне..."

    await message.answer(
        f"✅ Сервер <b>{result['name']}</b> добавлен!\n"
        f"Статус: {result['status']}{deploy_msg}",
        parse_mode="HTML",
    )


# ── Лог событий ──────────────────────────────────────────

@router.callback_query(F.data == "forge_events")
async def forge_events(callback: CallbackQuery):
    """Показать последние события VPN Forge."""
    if not is_admin(callback.from_user.id):
        return

    from app.vpn_forge.models import ServerEvent, VPNServer
    from app.database import AsyncSessionLocal
    from sqlalchemy import select, desc

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ServerEvent)
            .order_by(desc(ServerEvent.created_at))
            .limit(15)
        )
        events = result.scalars().all()

    if not events:
        text = "📋 <b>Нет событий</b>"
    else:
        text = "📋 <b>Последние события VPN Forge:</b>\n"
        for e in events:
            sev = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🔴"}.get(e.severity, "•")
            time_str = e.created_at.strftime("%d.%m %H:%M") if e.created_at else "—"
            msg = (e.message or "")[:60]
            text += f"\n{sev} [{time_str}] <b>{e.event_type}</b>\n   {msg}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К панели", callback_data="forge_refresh")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


# ── AI Status ─────────────────────────────────────────────

@router.callback_query(F.data == "forge_ai_status")
async def forge_ai_status(callback: CallbackQuery):
    """Показать статус AI-агента."""
    if not is_admin(callback.from_user.id):
        return

    has_key = bool(settings.openrouter_api_key)
    model = settings.openrouter_model

    text = f"""🤖 <b>AI Agent Status</b>

API ключ: {'✅ Настроен' if has_key else '❌ Не настроен'}
Модель: <code>{model}</code>
Провайдер: OpenRouter

<b>Возможности AI-агента:</b>
• Автоматическая диагностика проблем
• Анализ логов через LLM (DeepSeek)
• Генерация fix-команд
• Whitelist безопасных команд
• Dry-run режим (диагностика без выполнения)

<b>Безопасность:</b>
• Max {5} команд за сессию
• Запрещены деструктивные команды
• Все действия логируются"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К панели", callback_data="forge_refresh")],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


# ── Регистрация ──────────────────────────────────────────

def register_forge_handlers(dp):
    """Регистрация обработчиков VPN Forge."""
    dp.include_router(router)
