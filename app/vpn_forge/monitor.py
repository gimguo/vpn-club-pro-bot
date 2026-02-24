"""
VPN Forge — Монитор здоровья серверов.

Каждую минуту проверяет SSH, Outline API, Docker,
CPU/RAM/Disk и записывает результат в HealthCheck.
"""
import asyncio
import logging
import time
import aiohttp
from datetime import datetime, timezone
from typing import Optional, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.vpn_forge.models import VPNServer, HealthCheck, ServerEvent
from app.vpn_forge.ssh_client import SSHClient
from config import settings

logger = logging.getLogger(__name__)

# Пороги
CPU_WARNING = 80
CPU_CRITICAL = 95
MEM_WARNING = 85
MEM_CRITICAL = 95
DISK_WARNING = 85
DISK_CRITICAL = 95
CONSECUTIVE_FAILURES_DEGRADED = 3


class ServerMonitor:
    """Мониторинг здоровья VPN-серверов."""

    async def check_server(self, server: VPNServer, session: AsyncSession) -> HealthCheck:
        """
        Полная проверка одного сервера.

        Проверки:
        1. SSH-подключение
        2. Docker (shadowbox контейнер)
        3. Outline API (GET /server)
        4. CPU / RAM / Disk
        """
        start_time = time.monotonic()
        check = HealthCheck(
            server_id=server.id,
            ssh_ok=False,
            outline_api_ok=False,
            docker_ok=False,
        )
        details = {}

        ssh: Optional[SSHClient] = None
        try:
            # ── 1. SSH ────────────────────────────────────
            ssh = SSHClient(
                host=server.ip_address,
                username=server.ssh_user,
                port=server.ssh_port,
                key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
            )
            connected = await ssh.connect(timeout=10)
            check.ssh_ok = connected

            if not connected:
                details["ssh_error"] = "Connection failed"
                check.status = "critical"
                check.response_time_ms = int((time.monotonic() - start_time) * 1000)
                check.details = details
                await self._save_check(session, server, check)
                return check

            # ── 2. Docker ─────────────────────────────────
            check.docker_ok = await ssh.check_docker_container("shadowbox")
            if not check.docker_ok:
                details["docker_error"] = "shadowbox container not running"

            # ── 3. Outline API ────────────────────────────
            if server.outline_api_url:
                check.outline_api_ok = await self._check_outline_api(server.outline_api_url)
                if not check.outline_api_ok:
                    details["outline_error"] = "API not responding"

                # Получаем кол-во активных ключей
                keys_count = await self._get_active_keys_count(server.outline_api_url)
                if keys_count is not None:
                    details["active_keys"] = keys_count

            # ── 4. Метрики ────────────────────────────────
            metrics = await ssh.get_metrics()
            check.cpu_percent = metrics.get("cpu_percent")
            check.memory_percent = metrics.get("memory_percent")
            check.disk_percent = metrics.get("disk_percent")

        except Exception as e:
            details["error"] = str(e)
            logger.error(f"[{server.name}] Monitor error: {e}")
        finally:
            if ssh:
                await ssh.disconnect()

        # ── Определяем статус ─────────────────────────────
        check.status = self._evaluate_status(check)
        check.response_time_ms = int((time.monotonic() - start_time) * 1000)
        check.details = details

        # Сохраняем результат и обновляем сервер
        await self._save_check(session, server, check)
        return check

    async def check_all_servers(self, session: AsyncSession) -> List[HealthCheck]:
        """Проверить все активные/managed серверы параллельно."""
        result = await session.execute(
            select(VPNServer).where(
                VPNServer.status.in_(["active", "degraded", "deploying"]),
                VPNServer.auto_managed == True,
            )
        )
        servers = result.scalars().all()

        if not servers:
            logger.debug("No servers to monitor")
            return []

        logger.info(f"Monitoring {len(servers)} servers...")

        # Параллельная проверка
        tasks = [self.check_server(server, session) for server in servers]
        checks = await asyncio.gather(*tasks, return_exceptions=True)

        # Фильтруем ошибки
        valid_checks = []
        for i, check in enumerate(checks):
            if isinstance(check, Exception):
                logger.error(f"Monitor task failed for {servers[i].name}: {check}")
            else:
                valid_checks.append(check)

        return valid_checks

    # ── Проверка Outline API ──────────────────────────────

    async def _check_outline_api(self, api_url: str) -> bool:
        """GET запрос к Outline Management API."""
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as http:
                async with http.get(f"{api_url}/server", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def _get_active_keys_count(self, api_url: str) -> Optional[int]:
        """Получить количество ключей через Outline API."""
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as http:
                async with http.get(f"{api_url}/access-keys", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return len(data.get("accessKeys", []))
        except Exception:
            pass
        return None

    # ── Оценка статуса ────────────────────────────────────

    @staticmethod
    def _evaluate_status(check: HealthCheck) -> str:
        """Определить общий статус проверки: ok / warning / critical."""
        # Critical: SSH или Outline API недоступны
        if not check.ssh_ok:
            return "critical"
        if not check.outline_api_ok:
            return "critical"
        if not check.docker_ok:
            return "critical"

        # Warning: высокая нагрузка
        warnings = 0
        if check.cpu_percent and check.cpu_percent >= CPU_CRITICAL:
            return "critical"
        if check.memory_percent and check.memory_percent >= MEM_CRITICAL:
            return "critical"
        if check.disk_percent and check.disk_percent >= DISK_CRITICAL:
            return "critical"

        if check.cpu_percent and check.cpu_percent >= CPU_WARNING:
            warnings += 1
        if check.memory_percent and check.memory_percent >= MEM_WARNING:
            warnings += 1
        if check.disk_percent and check.disk_percent >= DISK_WARNING:
            warnings += 1

        if warnings > 0:
            return "warning"

        return "ok"

    # ── Сохранение результатов ─────────────────────────────

    async def _save_check(self, session: AsyncSession, server: VPNServer, check: HealthCheck):
        """Сохранить результат проверки и обновить сервер."""
        session.add(check)

        now = datetime.now(timezone.utc)
        server.last_health_check_at = now
        server.last_health_status = check.status

        # Обновляем метрики на сервере
        if check.cpu_percent is not None:
            server.cpu_percent = check.cpu_percent
        if check.memory_percent is not None:
            server.memory_percent = check.memory_percent
        if check.disk_percent is not None:
            server.disk_percent = check.disk_percent

        # Обновляем active_keys если есть данные
        if check.details and "active_keys" in check.details:
            server.active_keys = check.details["active_keys"]

        # Считаем consecutive failures
        if check.status == "critical":
            server.consecutive_failures += 1
            # Если 3+ подряд critical → degraded
            if server.consecutive_failures >= CONSECUTIVE_FAILURES_DEGRADED and server.status == "active":
                server.status = "degraded"
                event = ServerEvent(
                    server_id=server.id,
                    event_type="health_degraded",
                    severity="warning",
                    message=f"Server degraded after {server.consecutive_failures} consecutive failures",
                    initiated_by="monitor",
                )
                session.add(event)
                logger.warning(f"[{server.name}] Status → degraded ({server.consecutive_failures} failures)")
        else:
            # Сброс при успешной проверке
            if server.consecutive_failures > 0:
                server.consecutive_failures = 0
            # Возвращаем из degraded в active
            if server.status == "degraded" and check.status == "ok":
                server.status = "active"
                event = ServerEvent(
                    server_id=server.id,
                    event_type="health_recovered",
                    severity="info",
                    message="Server recovered, status back to active",
                    initiated_by="monitor",
                )
                session.add(event)
                logger.info(f"[{server.name}] Status → active (recovered)")

        await session.commit()
