"""
VPN Forge — Автоустановщик Outline VPN.

Подключается по SSH к новому серверу,
устанавливает Docker + Outline, парсит API URL и cert.
"""
import asyncio
import logging
import re
from typing import Optional, Dict, Tuple

from app.vpn_forge.ssh_client import SSHClient

logger = logging.getLogger(__name__)

# Официальный скрипт установки Outline
OUTLINE_INSTALL_URL = "https://raw.githubusercontent.com/Jigsaw-Code/outline-server/master/src/server_manager/install_scripts/install_server.sh"


class OutlineDeployer:
    """Автоматическая установка Outline VPN на сервер через SSH."""

    def __init__(self, ssh: SSHClient):
        self.ssh = ssh

    # ── Главная точка входа ───────────────────────────────

    async def deploy(self) -> Dict:
        """
        Полный цикл развёртывания Outline на сервере.

        Возвращает dict с ключами:
          - api_url: str     — URL Outline Management API
          - cert_sha256: str — SHA-256 отпечаток сертификата
          - success: bool

        Этапы:
          1. Ожидание готовности SSH
          2. Базовая настройка ОС
          3. Установка Docker
          4. Запуск Outline install script
          5. Парсинг вывода → api_url + cert
          6. Проверка: GET /server → 200
        """
        result = {"success": False, "api_url": None, "cert_sha256": None, "error": None}

        try:
            # 1. Ждём готовности SSH
            logger.info(f"[{self.ssh.host}] Waiting for SSH...")
            if not await self._wait_for_ssh(max_attempts=30, delay=10):
                result["error"] = "SSH not reachable after 5 minutes"
                return result

            # 2. Базовая настройка ОС
            logger.info(f"[{self.ssh.host}] Preparing OS...")
            await self._prepare_os()

            # 3. Docker
            logger.info(f"[{self.ssh.host}] Installing Docker...")
            await self._install_docker()

            # 4. Outline
            logger.info(f"[{self.ssh.host}] Installing Outline VPN...")
            api_url, cert_sha256 = await self._install_outline()

            if not api_url:
                result["error"] = "Failed to parse Outline API URL from install output"
                return result

            # 5. Удаляем Watchtower (install_server.sh ставит его автоматически)
            logger.info(f"[{self.ssh.host}] Removing Watchtower (auto-installed by Outline)...")
            await self._remove_watchtower()

            # 6. Проверка
            logger.info(f"[{self.ssh.host}] Verifying Outline API...")
            if await self._verify_outline(api_url):
                result["success"] = True
                result["api_url"] = api_url
                result["cert_sha256"] = cert_sha256
                logger.info(f"[{self.ssh.host}] ✅ Outline deployed successfully!")
            else:
                result["error"] = "Outline API verification failed"

        except Exception as e:
            logger.error(f"[{self.ssh.host}] Deploy failed: {e}", exc_info=True)
            result["error"] = str(e)

        return result

    # ── Этап 1: Ожидание SSH ──────────────────────────────

    async def _wait_for_ssh(self, max_attempts: int = 30, delay: int = 10) -> bool:
        """Ожидание доступности SSH-сервера."""
        for attempt in range(1, max_attempts + 1):
            try:
                connected = await self.ssh.connect(timeout=10)
                if connected:
                    logger.info(f"[{self.ssh.host}] SSH ready (attempt {attempt})")
                    return True
            except Exception:
                pass
            logger.debug(f"[{self.ssh.host}] SSH not ready, attempt {attempt}/{max_attempts}")
            await asyncio.sleep(delay)
        return False

    # ── Этап 2: Подготовка ОС ─────────────────────────────

    async def _wait_for_dpkg_lock(self, max_wait: int = 300):
        """Ожидание снятия блокировки dpkg (unattended-upgrades и др.)."""
        logger.info(f"[{self.ssh.host}] Waiting for dpkg lock to be released...")
        for i in range(max_wait // 5):
            code, _, _ = await self.ssh.run(
                "fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1",
                timeout=10,
            )
            if code != 0:
                # Lock свободен (fuser не нашёл процесс)
                logger.info(f"[{self.ssh.host}] dpkg lock is free")
                return True
            logger.debug(f"[{self.ssh.host}] dpkg still locked, waiting... ({(i+1)*5}s)")
            await asyncio.sleep(5)

        # Принудительно останавливаем unattended-upgrades
        logger.warning(f"[{self.ssh.host}] dpkg still locked after {max_wait}s, killing unattended-upgrades...")
        await self.ssh.run("systemctl stop unattended-upgrades 2>/dev/null || true", timeout=30)
        await self.ssh.run("killall -9 unattended-upgr 2>/dev/null || true", timeout=10)
        await asyncio.sleep(5)
        await self.ssh.run("dpkg --configure -a 2>/dev/null || true", timeout=120)
        return True

    async def _prepare_os(self):
        """Базовая настройка: обновление, установка зависимостей, firewall."""
        # Сначала ждём снятия блокировки dpkg (unattended-upgrades на свежих VPS)
        await self._wait_for_dpkg_lock()

        commands = [
            "export DEBIAN_FRONTEND=noninteractive",
            # Останавливаем unattended-upgrades чтобы не мешало
            "systemctl stop unattended-upgrades 2>/dev/null || true",
            "systemctl disable unattended-upgrades 2>/dev/null || true",
            # Обновление пакетов
            "apt-get update -qq",
            "apt-get upgrade -y -qq",
            # Необходимые утилити
            "apt-get install -y -qq curl wget net-tools jq ca-certificates gnupg lsb-release",
            # Часовой пояс
            "timedatectl set-timezone UTC 2>/dev/null || true",
        ]
        for cmd in commands:
            code, _, stderr = await self.ssh.run(cmd, timeout=300)
            if code != 0:
                logger.warning(f"[{self.ssh.host}] OS prep warning: {stderr[:200]}")

    # ── Этап 3: Установка Docker ──────────────────────────

    async def _install_docker(self):
        """Установка Docker если ещё не установлен."""
        # Проверяем наличие Docker
        code, _, _ = await self.ssh.run("docker --version", timeout=10)
        if code == 0:
            logger.info(f"[{self.ssh.host}] Docker already installed")
            return

        # Ждём снятия блокировки dpkg перед установкой
        await self._wait_for_dpkg_lock()

        # Устанавливаем Docker с retry
        for attempt in range(1, 4):
            logger.info(f"[{self.ssh.host}] Docker install attempt {attempt}/3...")
            code, stdout, stderr = await self.ssh.run(
                "curl -fsSL https://get.docker.com | sh", timeout=600
            )
            if code == 0:
                break
            logger.warning(f"[{self.ssh.host}] Docker install attempt {attempt} failed: {stderr[:300]}")
            if attempt < 3:
                await self._wait_for_dpkg_lock(max_wait=120)
                await asyncio.sleep(10)

        # Включаем и запускаем
        await self.ssh.run("systemctl enable docker", timeout=30)
        await self.ssh.run("systemctl start docker", timeout=30)

        # Проверка
        code, out, _ = await self.ssh.run("docker --version", timeout=10)
        if code != 0:
            raise RuntimeError(f"Docker installation failed on {self.ssh.host}")
        logger.info(f"[{self.ssh.host}] Docker installed: {out}")

    # ── Этап 4: Установка Outline ─────────────────────────

    async def _install_outline(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Запуск официального скрипта установки Outline.

        Парсит вывод для получения:
        - apiUrl: https://IP:PORT/HASH
        - certSha256: HEXSTRING
        """
        # Скачиваем и запускаем скрипт
        install_cmd = (
            f"bash -c 'wget -qO- {OUTLINE_INSTALL_URL} | "
            f"SB_IMAGE=quay.io/nicholasgasior/shadowbox-multiarch:daily bash'"
        )

        # Альтернативный вариант с официальным образом
        install_cmd_official = (
            f"bash -c 'wget -qO- {OUTLINE_INSTALL_URL} | bash'"
        )

        # Пробуем официальный образ сначала
        code, stdout, stderr = await self.ssh.run(install_cmd_official, timeout=600)
        full_output = stdout + "\n" + stderr

        if code != 0:
            logger.warning(f"[{self.ssh.host}] Official image failed, trying alternative...")
            code, stdout, stderr = await self.ssh.run(install_cmd, timeout=600)
            full_output = stdout + "\n" + stderr

        if code != 0:
            logger.error(f"[{self.ssh.host}] Outline install failed:\n{full_output[-500:]}")
            raise RuntimeError(f"Outline installation failed on {self.ssh.host}")

        # Парсим вывод
        api_url = self._parse_api_url(full_output)
        cert_sha256 = self._parse_cert_sha256(full_output)

        logger.info(f"[{self.ssh.host}] Parsed API URL: {api_url}")
        logger.info(f"[{self.ssh.host}] Parsed cert SHA256: {cert_sha256}")

        return api_url, cert_sha256

    @staticmethod
    def _parse_api_url(output: str) -> Optional[str]:
        """Извлечь apiUrl из вывода install script."""
        # Формат: {"apiUrl":"https://IP:PORT/HASH","certSha256":"..."}
        # Или отдельной строкой
        patterns = [
            r'"apiUrl"\s*:\s*"(https?://[^"]+)"',
            r'apiUrl:\s*(https?://\S+)',
            r'(https?://\d+\.\d+\.\d+\.\d+:\d+/[a-zA-Z0-9_-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1).rstrip("/")
        return None

    @staticmethod
    def _parse_cert_sha256(output: str) -> Optional[str]:
        """Извлечь certSha256 из вывода install script."""
        patterns = [
            r'"certSha256"\s*:\s*"([A-Fa-f0-9]+)"',
            r'certSha256:\s*([A-Fa-f0-9]+)',
            r'SHA256[:\s]+([A-Fa-f0-9]{64})',
        ]
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)
        return None

    # ── Этап 5: Проверка ──────────────────────────────────

    async def _verify_outline(self, api_url: str, retries: int = 5) -> bool:
        """Проверить что Outline API отвечает."""
        for attempt in range(1, retries + 1):
            code, out, _ = await self.ssh.run(
                f"curl -sk {api_url}/server | jq -r '.name' 2>/dev/null",
                timeout=15,
            )
            if code == 0 and out:
                logger.info(f"[{self.ssh.host}] Outline API verified: name={out}")
                return True
            logger.debug(f"[{self.ssh.host}] Outline verify attempt {attempt}/{retries}")
            await asyncio.sleep(5)
        return False

    # ── Вспомогательные ───────────────────────────────────

    async def get_outline_access_config(self) -> Optional[Dict]:
        """
        Получить конфигурацию Outline с сервера
        (если уже установлен, но API URL неизвестен).
        """
        try:
            code, out, _ = await self.ssh.run(
                "cat /opt/outline/access.txt 2>/dev/null || "
                "cat /root/shadowbox/access.txt 2>/dev/null || "
                "docker logs shadowbox 2>&1 | grep -o '{.*apiUrl.*}' | tail -1",
                timeout=15,
            )
            if code == 0 and out:
                api_url = self._parse_api_url(out)
                cert_sha256 = self._parse_cert_sha256(out)
                if api_url:
                    return {"api_url": api_url, "cert_sha256": cert_sha256}
        except Exception as e:
            logger.warning(f"[{self.ssh.host}] Could not get Outline config: {e}")
        return None

    async def _remove_watchtower(self):
        """
        Удаляет Watchtower, который install_server.sh ставит автоматически.
        
        Watchtower проверяет Docker Hub на новые образы и при неудачном 
        обновлении УДАЛЯЕТ контейнеры (shadowbox, x-ui) без восстановления.
        """
        commands = [
            "docker stop watchtower 2>/dev/null || true",
            "docker rm -f watchtower 2>/dev/null || true",
            "docker rmi -f containrrr/watchtower 2>/dev/null || true",
            "docker rmi -f nickfedor/watchtower 2>/dev/null || true",
        ]
        for cmd in commands:
            await self.ssh.run(cmd, timeout=15)
        logger.info(f"[{self.ssh.host}] Watchtower removed (prevents container deletion)")

    async def uninstall_outline(self):
        """Удалить Outline с сервера."""
        commands = [
            "docker stop shadowbox watchtower 2>/dev/null || true",
            "docker rm shadowbox watchtower 2>/dev/null || true",
            "docker rmi -f $(docker images -q) 2>/dev/null || true",
            "rm -rf /opt/outline /root/shadowbox 2>/dev/null || true",
        ]
        for cmd in commands:
            await self.ssh.run(cmd, timeout=30)
        logger.info(f"[{self.ssh.host}] Outline uninstalled")
