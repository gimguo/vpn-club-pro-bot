"""
VPN Forge — Центральный менеджер.

Точка входа для всей системы:
- Инициализация и запуск мониторинга/оркестрации
- Интеграция с ботом (замена статических серверов из .env)
- Публичное API для хэндлеров бота
"""
import asyncio
import logging
from typing import List, Optional, Dict
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.vpn_forge.models import VPNServer, ServerEvent, HealthCheck
from app.vpn_forge.monitor import ServerMonitor
from app.vpn_forge.orchestrator import Orchestrator
from app.vpn_forge.ai_agent import AIAgent
from app.database import AsyncSessionLocal
from config import settings

logger = logging.getLogger(__name__)


class ForgeManager:
    """Центральный менеджер VPN Forge."""

    def __init__(self, bot=None):
        self.bot = bot
        self.monitor = ServerMonitor()
        self.orchestrator = Orchestrator()
        self.ai_agent = AIAgent()
        self._monitor_task: Optional[asyncio.Task] = None
        self._orchestrator_task: Optional[asyncio.Task] = None

    # ── Запуск / остановка ────────────────────────────────

    def start(self):
        """Запустить фоновые задачи мониторинга и оркестрации."""
        if not settings.vpn_forge_enabled:
            logger.info("VPN Forge disabled (VPN_FORGE_ENABLED=false)")
            return

        logger.info("🚀 Starting VPN Forge...")
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        self._orchestrator_task = asyncio.create_task(self._orchestrator_loop())
        logger.info("✅ VPN Forge started")

    def stop(self):
        """Остановить фоновые задачи."""
        if self._monitor_task:
            self._monitor_task.cancel()
        if self._orchestrator_task:
            self._orchestrator_task.cancel()
        logger.info("VPN Forge stopped")

    # ── Фоновые циклы ────────────────────────────────────

    async def _monitor_loop(self):
        """Цикл мониторинга (каждые N секунд)."""
        interval = settings.vpn_forge_monitor_interval
        logger.info(f"Monitor loop started (interval={interval}s)")

        while True:
            try:
                async with AsyncSessionLocal() as session:
                    await self.monitor.check_all_servers(session)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}", exc_info=True)

            await asyncio.sleep(interval)

    async def _orchestrator_loop(self):
        """Цикл оркестрации (каждые 5 минут)."""
        logger.info("Orchestrator loop started (interval=300s)")

        # Первый запуск через 30 секунд после старта
        await asyncio.sleep(30)

        while True:
            try:
                async with AsyncSessionLocal() as session:
                    await self.orchestrator.evaluate(session)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Orchestrator loop error: {e}", exc_info=True)

            await asyncio.sleep(300)

    # ── Публичное API для бота ────────────────────────────

    async def get_active_servers(self) -> List[str]:
        """
        Получить список API URL активных серверов.
        Используется вместо settings.outline_servers.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(VPNServer.outline_api_url).where(
                    VPNServer.status == "active",
                    VPNServer.is_active == True,
                    VPNServer.outline_api_url.isnot(None),
                ).order_by(VPNServer.priority.desc())
            )
            urls = [row[0] for row in result.fetchall()]

        # Fallback на .env если нет серверов в Forge
        if not urls:
            return settings.outline_servers

        return urls

    async def get_fleet_stats(self) -> Dict:
        """Получить сводную статистику флота для админ-панели."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(VPNServer).where(VPNServer.auto_managed == True)
            )
            servers = result.scalars().all()

        if not servers:
            return {
                "total": 0,
                "active": 0,
                "degraded": 0,
                "maintenance": 0,
                "deploying": 0,
                "offline": 0,
                "total_keys": 0,
                "total_capacity": 0,
                "avg_load": 0,
                "monthly_cost_eur": 0,
                "servers": [],
            }

        active = [s for s in servers if s.status == "active"]
        stats = {
            "total": len(servers),
            "active": len(active),
            "degraded": len([s for s in servers if s.status == "degraded"]),
            "maintenance": len([s for s in servers if s.status == "maintenance"]),
            "deploying": len([s for s in servers if s.status in ("provisioning", "deploying")]),
            "offline": len([s for s in servers if s.status == "offline"]),
            "total_keys": sum(s.active_keys for s in servers),
            "total_capacity": sum(s.max_keys for s in servers),
            "avg_load": round(
                sum(s.load_percent for s in active) / len(active), 1
            ) if active else 0,
            "monthly_cost_eur": round(
                sum((s.monthly_cost_cents or 0) for s in servers) / 100, 2
            ),
            "servers": [
                {
                    "id": s.id,
                    "name": s.name,
                    "ip": s.ip_address,
                    "region": s.region,
                    "country": s.country,
                    "status": s.status,
                    "keys": s.active_keys,
                    "max_keys": s.max_keys,
                    "load": s.load_percent,
                    "cpu": s.cpu_percent,
                    "mem": s.memory_percent,
                    "disk": s.disk_percent,
                    "last_check": s.last_health_status,
                    "provider": s.provider,
                }
                for s in servers
            ],
        }
        return stats

    async def get_server_details(self, server_id: int) -> Optional[Dict]:
        """Получить детальную информацию о сервере."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(VPNServer).where(VPNServer.id == server_id)
            )
            server = result.scalar_one_or_none()
            if not server:
                return None

            # Последние 10 событий
            events_result = await session.execute(
                select(ServerEvent)
                .where(ServerEvent.server_id == server_id)
                .order_by(desc(ServerEvent.created_at))
                .limit(10)
            )
            events = events_result.scalars().all()

            # Последние 5 health checks
            checks_result = await session.execute(
                select(HealthCheck)
                .where(HealthCheck.server_id == server_id)
                .order_by(desc(HealthCheck.created_at))
                .limit(5)
            )
            checks = checks_result.scalars().all()

            return {
                "server": {
                    "id": server.id,
                    "name": server.name,
                    "ip": server.ip_address,
                    "provider": server.provider,
                    "region": server.region,
                    "country": server.country,
                    "status": server.status,
                    "is_active": server.is_active,
                    "keys": server.active_keys,
                    "max_keys": server.max_keys,
                    "load": server.load_percent,
                    "cpu": server.cpu_percent,
                    "mem": server.memory_percent,
                    "disk": server.disk_percent,
                    "traffic_gb": server.total_traffic_gb,
                    "cost_eur": round((server.monthly_cost_cents or 0) / 100, 2),
                    "plan": server.provider_plan,
                    "auto_heal": server.auto_heal,
                    "consecutive_failures": server.consecutive_failures,
                    "outline_api_url": server.outline_api_url,
                    "last_health_check": server.last_health_check_at.isoformat() if server.last_health_check_at else None,
                    "created_at": server.created_at.isoformat() if server.created_at else None,
                },
                "events": [
                    {
                        "type": e.event_type,
                        "severity": e.severity,
                        "message": e.message,
                        "initiated_by": e.initiated_by,
                        "at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in events
                ],
                "health_checks": [
                    {
                        "status": c.status,
                        "ssh": c.ssh_ok,
                        "outline": c.outline_api_ok,
                        "docker": c.docker_ok,
                        "cpu": c.cpu_percent,
                        "mem": c.memory_percent,
                        "disk": c.disk_percent,
                        "response_ms": c.response_time_ms,
                        "at": c.created_at.isoformat() if c.created_at else None,
                    }
                    for c in checks
                ],
            }

    async def trigger_ai_diagnosis(self, server_id: int,
                                    auto_execute: bool = False) -> Dict:
        """Запустить ИИ-диагностику конкретного сервера."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(VPNServer).where(VPNServer.id == server_id)
            )
            server = result.scalar_one_or_none()
            if not server:
                return {"error": "Server not found"}

            return await self.ai_agent.diagnose_and_fix(
                server, session, auto_execute=auto_execute
            )

    async def add_server(self, name: str, ip_address: str,
                         ssh_user: str = "root", ssh_port: int = 22,
                         ssh_key_path: str = None,
                         outline_api_url: str = None,
                         outline_cert: str = None) -> Dict:
        """Добавить сервер вручную."""
        async with AsyncSessionLocal() as session:
            server = await self.orchestrator.add_manual_server(
                session=session,
                name=name,
                ip_address=ip_address,
                ssh_user=ssh_user,
                ssh_port=ssh_port,
                ssh_key_path=ssh_key_path,
                outline_api_url=outline_api_url,
                outline_cert_sha256=outline_cert,
            )
            return {"id": server.id, "name": server.name, "status": server.status}

    async def notify_admin(self, message: str):
        """Отправить уведомление админу через бот."""
        if self.bot and settings.admin_id:
            try:
                await self.bot.send_message(
                    settings.admin_id,
                    f"🔧 <b>VPN Forge</b>\n\n{message}",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")
