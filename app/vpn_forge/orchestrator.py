"""
VPN Forge — Оркестратор (автомасштабирование).

Анализирует загрузку флота серверов и принимает решения:
- Scale Up:   средняя загрузка > threshold → арендовать новый сервер
- Scale Down: средняя загрузка < threshold и серверов > min → удалить лишний
- Heal:       degraded серверы → передать в Healer
- AI:         maintenance серверы → передать в AI Agent (с cooldown)
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.vpn_forge.models import VPNServer, ServerEvent
from app.vpn_forge.deployer import OutlineDeployer
from app.vpn_forge.healer import SelfHealer
from app.vpn_forge.ai_agent import AIAgent
from app.vpn_forge.ssh_client import SSHClient
from app.vpn_forge.providers.hetzner import HetznerProvider
from config import settings

logger = logging.getLogger(__name__)


class Orchestrator:
    """Центральный оркестратор VPN-инфраструктуры."""

    # AI Agent cooldown: не чаще 1 раза в час на сервер, макс 3 попытки в сутки
    AI_COOLDOWN_SECONDS = 3600       # 1 час между попытками
    AI_MAX_ATTEMPTS_PER_DAY = 3      # Макс 3 попытки в сутки на сервер

    def __init__(self):
        self.healer = SelfHealer()
        self.ai_agent = AIAgent()
        self._scaling_lock = asyncio.Lock()
        self._server_counter = 0  # Для генерации уникальных имён
        # Трекинг AI-попыток: {server_id: [datetime, datetime, ...]}
        self._ai_attempts: Dict[int, List[datetime]] = {}

    # ── Главный цикл ─────────────────────────────────────

    async def evaluate(self, session: AsyncSession):
        """
        Один цикл оркестрации: оценить состояние флота и принять решения.
        Вызывается периодически планировщиком (каждые 5 мин).
        """
        logger.info("🔄 Orchestrator: evaluating fleet...")

        # Получаем все управляемые серверы
        result = await session.execute(
            select(VPNServer).where(VPNServer.auto_managed == True)
        )
        servers = result.scalars().all()

        if not servers:
            logger.info("No managed servers found")
            return

        # Классифицируем серверы
        active_servers = [s for s in servers if s.status == "active"]
        degraded_servers = [s for s in servers if s.status == "degraded"]
        maintenance_servers = [s for s in servers if s.status == "maintenance"]
        deploying_servers = [s for s in servers if s.status in ("provisioning", "deploying")]

        logger.info(
            f"Fleet: {len(active_servers)} active, {len(degraded_servers)} degraded, "
            f"{len(maintenance_servers)} maintenance, {len(deploying_servers)} deploying"
        )

        # ── 1. Лечение degraded серверов ──────────────────
        for server in degraded_servers:
            if server.auto_heal:
                logger.info(f"[{server.name}] Attempting to heal degraded server...")
                # Получаем последний health check
                from sqlalchemy import desc
                from app.vpn_forge.models import HealthCheck
                hc_result = await session.execute(
                    select(HealthCheck)
                    .where(HealthCheck.server_id == server.id)
                    .order_by(desc(HealthCheck.created_at))
                    .limit(1)
                )
                last_check = hc_result.scalar_one_or_none()
                if last_check:
                    await self.healer.heal(server, last_check, session)

        # ── 2. AI-диагностика maintenance серверов (с cooldown) ──
        for server in maintenance_servers:
            if not settings.openrouter_api_key:
                logger.warning(f"[{server.name}] No OpenRouter API key, skipping AI diagnosis")
                continue

            # Проверяем cooldown
            if not self._can_run_ai(server.id):
                logger.info(
                    f"[{server.name}] AI Agent cooldown active, skipping "
                    f"(attempts today: {self._get_today_attempts(server.id)}/"
                    f"{self.AI_MAX_ATTEMPTS_PER_DAY})"
                )
                continue

            logger.info(f"[{server.name}] Sending to AI Agent for diagnostics...")
            self._record_ai_attempt(server.id)

            ai_result = await self.ai_agent.diagnose_and_fix(server, session, auto_execute=True)
            if ai_result.get("fixed"):
                logger.info(f"[{server.name}] AI Agent fixed the server!")
                # Сбрасываем счётчик при успехе
                self._ai_attempts.pop(server.id, None)
            else:
                attempts_left = self.AI_MAX_ATTEMPTS_PER_DAY - self._get_today_attempts(server.id)
                logger.warning(
                    f"[{server.name}] AI Agent could not fix. "
                    f"Attempts left today: {attempts_left}. "
                    f"Diagnosis: {ai_result.get('diagnosis', 'N/A')[:100]}"
                )

        # ── 3. Автомасштабирование ────────────────────────
        # Учитываем только active серверы
        if active_servers:
            avg_load = sum(s.load_percent for s in active_servers) / len(active_servers)
            total_keys = sum(s.active_keys for s in active_servers)
            total_capacity = sum(s.max_keys for s in active_servers)

            logger.info(
                f"Fleet load: {avg_load:.1f}% "
                f"({total_keys}/{total_capacity} keys, "
                f"{len(active_servers)} active servers)"
            )

            # Scale UP
            if (avg_load >= settings.vpn_forge_scale_up_threshold
                    and len(active_servers) + len(deploying_servers) < settings.vpn_forge_max_servers):
                logger.info(f"📈 Scale UP triggered (load {avg_load:.1f}% >= {settings.vpn_forge_scale_up_threshold}%)")
                await self._scale_up(session)

            # Scale DOWN
            elif (avg_load <= settings.vpn_forge_scale_down_threshold
                  and len(active_servers) > settings.vpn_forge_min_servers
                  and not deploying_servers):
                logger.info(f"📉 Scale DOWN triggered (load {avg_load:.1f}% <= {settings.vpn_forge_scale_down_threshold}%)")
                await self._scale_down(active_servers, session)

    # ── AI Agent cooldown helpers ───────────────────────────

    def _can_run_ai(self, server_id: int) -> bool:
        """Проверить, можно ли запустить AI Agent для сервера."""
        now = datetime.now(timezone.utc)
        attempts = self._ai_attempts.get(server_id, [])

        # Очищаем старые записи (старше 24ч)
        attempts = [t for t in attempts if now - t < timedelta(hours=24)]
        self._ai_attempts[server_id] = attempts

        # Проверяем лимит за сутки
        if len(attempts) >= self.AI_MAX_ATTEMPTS_PER_DAY:
            return False

        # Проверяем cooldown (последняя попытка)
        if attempts and (now - attempts[-1]).total_seconds() < self.AI_COOLDOWN_SECONDS:
            return False

        return True

    def _record_ai_attempt(self, server_id: int):
        """Записать попытку AI-диагностики."""
        now = datetime.now(timezone.utc)
        if server_id not in self._ai_attempts:
            self._ai_attempts[server_id] = []
        self._ai_attempts[server_id].append(now)

    def _get_today_attempts(self, server_id: int) -> int:
        """Количество AI-попыток за последние 24 часа."""
        now = datetime.now(timezone.utc)
        attempts = self._ai_attempts.get(server_id, [])
        return len([t for t in attempts if now - t < timedelta(hours=24)])

    # ── Scale UP ──────────────────────────────────────────

    async def _scale_up(self, session: AsyncSession):
        """Арендовать и развернуть новый сервер."""
        async with self._scaling_lock:
            if not settings.hetzner_api_token:
                logger.warning("Cannot scale up: Hetzner API token not configured")
                return

            provider = HetznerProvider()

            # Генерируем уникальное имя
            self._server_counter += 1
            timestamp = datetime.now(timezone.utc).strftime("%m%d%H%M")
            server_name = f"vpn-{timestamp}-{self._server_counter}"

            # Выбираем регион (чередуем для гео-распределения)
            regions = ["fsn1", "nbg1", "hel1"]
            result = await session.execute(
                select(func.count(VPNServer.id)).where(VPNServer.auto_managed == True)
            )
            total_count = result.scalar_one()
            region = regions[total_count % len(regions)]

            try:
                # 1. Создаём сервер у провайдера
                logger.info(f"Provisioning new server: {server_name} in {region}...")
                provisioned = await provider.create_server(
                    name=server_name,
                    region=region,
                )

                # 2. Регистрируем в БД
                from app.vpn_forge.providers.hetzner import REGION_COUNTRY
                vpn_server = VPNServer(
                    name=server_name,
                    provider="hetzner",
                    provider_server_id=provisioned.provider_server_id,
                    region=region,
                    country=provisioned.country,
                    ip_address=provisioned.ip_address,
                    status="provisioning",
                    monthly_cost_cents=provisioned.monthly_cost_cents,
                    provider_plan=provisioned.plan,
                    auto_managed=True,
                    auto_heal=True,
                    max_keys=settings.vpn_forge_max_keys_per_server,
                )
                session.add(vpn_server)

                event = ServerEvent(
                    server_id=vpn_server.id,
                    event_type="provisioned",
                    severity="info",
                    message=f"Server provisioned at Hetzner ({region}): {provisioned.ip_address}",
                    details={
                        "provider_server_id": provisioned.provider_server_id,
                        "plan": provisioned.plan,
                        "monthly_cost": provisioned.monthly_cost_cents,
                    },
                    initiated_by="orchestrator",
                )
                session.add(event)
                await session.commit()
                await session.refresh(vpn_server)

                # 3. Deploy Outline в фоне
                asyncio.create_task(self._deploy_outline(vpn_server.id))

                logger.info(f"✅ Server {server_name} provisioned, deploying Outline in background...")

            except Exception as e:
                logger.error(f"Scale UP failed: {e}", exc_info=True)
                event = ServerEvent(
                    server_id=0,  # No server yet
                    event_type="scale_up_failed",
                    severity="error",
                    message=f"Failed to provision server: {str(e)[:300]}",
                    initiated_by="orchestrator",
                )
                # Не можем привязать к server_id=0, логируем в лог
                logger.error(f"Scale up event not saved (no server): {event.message}")

    async def _deploy_outline(self, server_id: int):
        """Фоновая задача: развернуть Outline на новом сервере."""
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(VPNServer).where(VPNServer.id == server_id)
                )
                server = result.scalar_one_or_none()
                if not server:
                    return

                server.status = "deploying"
                await session.commit()

                # Подключаемся и деплоим
                ssh = SSHClient(
                    host=server.ip_address,
                    username=server.ssh_user,
                    port=server.ssh_port,
                    key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
                )

                deployer = OutlineDeployer(ssh)
                deploy_result = await deployer.deploy()

                if deploy_result["success"]:
                    server.outline_api_url = deploy_result["api_url"]
                    server.outline_cert_sha256 = deploy_result["cert_sha256"]
                    server.status = "active"
                    server.is_active = True
                    server.last_successful_deploy_at = datetime.now(timezone.utc)

                    event = ServerEvent(
                        server_id=server.id,
                        event_type="deployed",
                        severity="info",
                        message=f"Outline deployed successfully: {deploy_result['api_url']}",
                        initiated_by="orchestrator",
                    )
                    logger.info(f"[{server.name}] ✅ Outline deployed!")
                else:
                    server.status = "error"
                    event = ServerEvent(
                        server_id=server.id,
                        event_type="deploy_failed",
                        severity="error",
                        message=f"Deploy failed: {deploy_result.get('error', 'unknown')}",
                        initiated_by="orchestrator",
                    )
                    logger.error(f"[{server.name}] ❌ Deploy failed: {deploy_result.get('error')}")

                session.add(event)
                await session.commit()

            except Exception as e:
                logger.error(f"Deploy task error for server_id={server_id}: {e}", exc_info=True)

    # ── Scale DOWN ────────────────────────────────────────

    async def _scale_down(self, active_servers: List[VPNServer], session: AsyncSession):
        """Удалить наименее загруженный сервер."""
        async with self._scaling_lock:
            if len(active_servers) <= settings.vpn_forge_min_servers:
                return

            # Выбираем сервер с минимальным количеством ключей
            target = min(active_servers, key=lambda s: s.active_keys)

            if target.active_keys > 0:
                logger.warning(
                    f"[{target.name}] Has {target.active_keys} active keys, "
                    f"migration needed before decommission. Skipping for now."
                )
                # TODO: Реализовать миграцию ключей
                return

            logger.info(f"Decommissioning server: {target.name} (0 keys, load {target.load_percent}%)")

            try:
                # Удаляем сервер у провайдера
                if target.provider == "hetzner" and target.provider_server_id:
                    provider = HetznerProvider()
                    await provider.delete_server(target.provider_server_id)

                # Помечаем в БД
                target.status = "offline"
                target.is_active = False

                event = ServerEvent(
                    server_id=target.id,
                    event_type="decommissioned",
                    severity="info",
                    message=f"Server decommissioned (scale down). Was: {target.active_keys} keys.",
                    initiated_by="orchestrator",
                )
                session.add(event)
                await session.commit()

                logger.info(f"[{target.name}] ✅ Server decommissioned")

            except Exception as e:
                logger.error(f"Scale DOWN failed for {target.name}: {e}")

    # ── Ручное добавление сервера ─────────────────────────

    async def add_manual_server(self, session: AsyncSession,
                                name: str, ip_address: str,
                                ssh_user: str = "root", ssh_port: int = 22,
                                ssh_key_path: str = None,
                                outline_api_url: str = None,
                                outline_cert_sha256: str = None) -> VPNServer:
        """
        Добавить существующий сервер вручную (без аренды через провайдера).
        """
        server = VPNServer(
            name=name,
            provider="manual",
            region="custom",
            country="??",
            ip_address=ip_address,
            ssh_user=ssh_user,
            ssh_port=ssh_port,
            ssh_key_path=ssh_key_path,
            outline_api_url=outline_api_url,
            outline_cert_sha256=outline_cert_sha256,
            status="active" if outline_api_url else "provisioning",
            is_active=bool(outline_api_url),
            auto_managed=True,
            auto_heal=True,
            max_keys=settings.vpn_forge_max_keys_per_server,
        )
        session.add(server)

        event = ServerEvent(
            server_id=server.id,
            event_type="manual_added",
            severity="info",
            message=f"Server added manually: {ip_address}",
            initiated_by="admin",
        )
        session.add(event)
        await session.commit()
        await session.refresh(server)

        # Если нет Outline API — запускаем деплой
        if not outline_api_url:
            asyncio.create_task(self._deploy_outline(server.id))

        logger.info(f"Manual server added: {name} ({ip_address})")
        return server
