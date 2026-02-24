"""
VPN Forge — Самолечение серверов (Self-Healer).

Автоматическое восстановление серверов по типу проблемы:
- Docker/Outline упал → restart
- Сервер не отвечает по SSH → reboot через провайдера
- Disk заполнен → очистка логов и docker prune
- RAM перегружена → restart тяжёлых процессов
"""
import asyncio
import logging
from typing import Optional, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.vpn_forge.models import VPNServer, HealthCheck, ServerEvent
from app.vpn_forge.ssh_client import SSHClient
from config import settings

logger = logging.getLogger(__name__)

MAX_HEAL_ATTEMPTS = 3


class SelfHealer:
    """Автоматическое восстановление VPN-серверов."""

    async def heal(self, server: VPNServer, check: HealthCheck,
                   session: AsyncSession) -> bool:
        """
        Попытка автолечения сервера на основе результатов проверки.

        Возвращает True если удалось починить.
        """
        if not server.auto_heal:
            logger.info(f"[{server.name}] Auto-heal disabled, skipping")
            return False

        # Определяем тип проблемы и выбираем стратегию
        strategies = self._determine_strategies(check)

        if not strategies:
            logger.info(f"[{server.name}] No applicable healing strategy")
            return False

        logger.info(f"[{server.name}] Healing strategies: {[s['name'] for s in strategies]}")

        for strategy in strategies:
            try:
                event = ServerEvent(
                    server_id=server.id,
                    event_type="heal_attempt",
                    severity="info",
                    message=f"Attempting: {strategy['name']}",
                    details={"strategy": strategy["name"]},
                    initiated_by="healer",
                )
                session.add(event)
                await session.commit()

                success = await strategy["fn"](server)

                if success:
                    # Логируем успех
                    event = ServerEvent(
                        server_id=server.id,
                        event_type="healed",
                        severity="info",
                        message=f"Successfully healed: {strategy['name']}",
                        details={"strategy": strategy["name"]},
                        initiated_by="healer",
                    )
                    session.add(event)
                    server.status = "active"
                    server.consecutive_failures = 0
                    await session.commit()
                    logger.info(f"[{server.name}] ✅ Healed with: {strategy['name']}")
                    return True
                else:
                    logger.warning(f"[{server.name}] Strategy failed: {strategy['name']}")

            except Exception as e:
                logger.error(f"[{server.name}] Heal error ({strategy['name']}): {e}")
                event = ServerEvent(
                    server_id=server.id,
                    event_type="heal_failed",
                    severity="error",
                    message=f"Failed: {strategy['name']} — {str(e)[:200]}",
                    details={"strategy": strategy["name"], "error": str(e)[:500]},
                    initiated_by="healer",
                )
                session.add(event)
                await session.commit()

        # Все стратегии не помогли
        logger.warning(f"[{server.name}] All healing strategies exhausted")
        server.status = "maintenance"
        event = ServerEvent(
            server_id=server.id,
            event_type="heal_exhausted",
            severity="critical",
            message="All healing strategies failed. Server needs manual attention or AI agent.",
            initiated_by="healer",
        )
        session.add(event)
        await session.commit()
        return False

    # ── Определение стратегий ─────────────────────────────

    def _determine_strategies(self, check: HealthCheck) -> List[Dict]:
        """Определить список стратегий лечения по результатам проверки."""
        strategies = []

        # Docker / Outline упал
        if check.ssh_ok and not check.docker_ok:
            strategies.append({"name": "restart_docker_outline", "fn": self._restart_outline})

        # Outline API не отвечает, но Docker работает
        if check.ssh_ok and check.docker_ok and not check.outline_api_ok:
            strategies.append({"name": "restart_shadowbox", "fn": self._restart_shadowbox})

        # Disk переполнен
        if check.disk_percent and check.disk_percent >= 85:
            strategies.append({"name": "cleanup_disk", "fn": self._cleanup_disk})

        # RAM перегружена
        if check.memory_percent and check.memory_percent >= 90:
            strategies.append({"name": "free_memory", "fn": self._free_memory})

        # SSH недоступен — пробуем ребут через провайдера (если есть)
        if not check.ssh_ok:
            strategies.append({"name": "provider_reboot", "fn": self._provider_reboot})

        return strategies

    # ── Стратегии лечения ─────────────────────────────────

    async def _restart_outline(self, server: VPNServer) -> bool:
        """Перезапустить Docker + Outline."""
        async with SSHClient(
            host=server.ip_address,
            username=server.ssh_user,
            port=server.ssh_port,
            key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
        ) as ssh:
            # Рестарт Docker
            await ssh.run("systemctl restart docker", timeout=60)
            await asyncio.sleep(10)

            # Запуск контейнеров
            await ssh.run("docker start shadowbox watchtower 2>/dev/null || true", timeout=30)
            await asyncio.sleep(10)

            # Проверка
            return await ssh.check_docker_container("shadowbox")

    async def _restart_shadowbox(self, server: VPNServer) -> bool:
        """Перезапустить только shadowbox контейнер."""
        async with SSHClient(
            host=server.ip_address,
            username=server.ssh_user,
            port=server.ssh_port,
            key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
        ) as ssh:
            await ssh.run("docker restart shadowbox", timeout=60)
            await asyncio.sleep(15)
            return await ssh.check_docker_container("shadowbox")

    async def _cleanup_disk(self, server: VPNServer) -> bool:
        """Очистка диска: docker prune, журналы, логи."""
        async with SSHClient(
            host=server.ip_address,
            username=server.ssh_user,
            port=server.ssh_port,
            key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
        ) as ssh:
            cleanup_commands = [
                # Docker cleanup
                "docker system prune -af --volumes 2>/dev/null || true",
                # Журналы systemd
                "journalctl --vacuum-time=2d 2>/dev/null || true",
                # Старые логи
                "find /var/log -name '*.gz' -delete 2>/dev/null || true",
                "find /var/log -name '*.old' -delete 2>/dev/null || true",
                "find /var/log -name '*.1' -delete 2>/dev/null || true",
                # tmp
                "find /tmp -type f -mtime +7 -delete 2>/dev/null || true",
                # apt cache
                "apt-get clean 2>/dev/null || true",
            ]
            for cmd in cleanup_commands:
                await ssh.run(cmd, timeout=60)

            # Проверяем что стало лучше
            metrics = await ssh.get_metrics()
            disk = metrics.get("disk_percent", 100)
            logger.info(f"[{server.name}] Disk after cleanup: {disk}%")
            return disk < 90

    async def _free_memory(self, server: VPNServer) -> bool:
        """Освободить оперативную память."""
        async with SSHClient(
            host=server.ip_address,
            username=server.ssh_user,
            port=server.ssh_port,
            key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
        ) as ssh:
            commands = [
                # Сброс кэша (безопасная операция)
                "sync && echo 3 > /proc/sys/vm/drop_caches",
                # Рестарт Outline (основной потребитель RAM)
                "docker restart shadowbox",
            ]
            for cmd in commands:
                await ssh.run(cmd, timeout=60)

            await asyncio.sleep(10)
            metrics = await ssh.get_metrics()
            mem = metrics.get("memory_percent", 100)
            logger.info(f"[{server.name}] Memory after cleanup: {mem}%")
            return mem < 90

    async def _provider_reboot(self, server: VPNServer) -> bool:
        """Ребут сервера через API провайдера."""
        if not server.provider_server_id:
            logger.warning(f"[{server.name}] No provider_server_id, cannot reboot via provider")
            return False

        try:
            if server.provider == "hetzner":
                from app.vpn_forge.providers.hetzner import HetznerProvider
                provider = HetznerProvider()
                await provider.reboot_server(server.provider_server_id)
            else:
                logger.warning(f"[{server.name}] Provider '{server.provider}' reboot not implemented")
                return False

            # Ждём перезагрузки
            logger.info(f"[{server.name}] Rebooting via provider, waiting 60s...")
            await asyncio.sleep(60)

            # Проверяем SSH
            ssh = SSHClient(
                host=server.ip_address,
                username=server.ssh_user,
                port=server.ssh_port,
                key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
            )
            connected = await ssh.connect(timeout=30)
            if connected:
                await ssh.disconnect()
            return connected

        except Exception as e:
            logger.error(f"[{server.name}] Provider reboot failed: {e}")
            return False
