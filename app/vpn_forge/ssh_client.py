"""
VPN Forge — Асинхронный SSH-клиент.

Обёртка над asyncssh: выполнение команд, сбор метрик,
загрузка/скачивание файлов, проверка портов.
"""
import asyncssh
import asyncio
import logging
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)


class SSHClient:
    """Асинхронный SSH-клиент для управления VPN-серверами."""

    def __init__(self, host: str, username: str = "root", port: int = 22,
                 key_path: Optional[str] = None):
        self.host = host
        self.username = username
        self.port = port
        self.key_path = key_path
        self._conn: Optional[asyncssh.SSHClientConnection] = None

    # ── Подключение / отключение ──────────────────────────

    async def connect(self, timeout: int = 15) -> bool:
        """Установить SSH-соединение."""
        try:
            client_keys = [self.key_path] if self.key_path else None
            self._conn = await asyncio.wait_for(
                asyncssh.connect(
                    self.host,
                    port=self.port,
                    username=self.username,
                    client_keys=client_keys,
                    known_hosts=None,
                ),
                timeout=timeout,
            )
            logger.info(f"SSH connected: {self.username}@{self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"SSH connect failed ({self.host}): {e}")
            self._conn = None
            return False

    async def disconnect(self):
        """Закрыть SSH-соединение."""
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None
            logger.debug(f"SSH disconnected: {self.host}")

    async def _ensure_connected(self):
        """Убедиться, что соединение активно."""
        if self._conn is None:
            if not await self.connect():
                raise ConnectionError(f"Cannot connect to {self.host}")

    # ── Выполнение команд ─────────────────────────────────

    async def run(self, command: str, check: bool = False,
                  timeout: int = 300) -> Tuple[int, str, str]:
        """
        Выполнить команду.

        Возвращает: (exit_code, stdout, stderr)
        """
        await self._ensure_connected()
        logger.debug(f"[{self.host}] $ {command}")
        try:
            result = await asyncio.wait_for(
                self._conn.run(command, check=check),
                timeout=timeout,
            )
            code = result.exit_status or 0
            stdout = (result.stdout or "").strip()
            stderr = (result.stderr or "").strip()
            return code, stdout, stderr
        except asyncssh.ProcessError as e:
            return e.exit_status or 1, (e.stdout or "").strip(), (e.stderr or "").strip()
        except asyncio.TimeoutError:
            raise TimeoutError(f"Command timed out ({timeout}s): {command}")

    async def run_ok(self, command: str, timeout: int = 300) -> str:
        """Выполнить команду и вернуть stdout. Бросает исключение при ошибке."""
        code, stdout, stderr = await self.run(command, timeout=timeout)
        if code != 0:
            raise RuntimeError(f"Command failed (exit {code}): {command}\n{stderr}")
        return stdout

    # ── Сбор метрик ───────────────────────────────────────

    async def get_metrics(self) -> Dict:
        """Собрать CPU / RAM / Disk с сервера."""
        metrics = {}
        try:
            # CPU (средняя за 1 секунду)
            code, out, _ = await self.run(
                "top -bn2 -d1 | grep 'Cpu(s)' | tail -1 | awk '{print $2+$4}'",
                timeout=15,
            )
            if code == 0 and out:
                metrics["cpu_percent"] = round(float(out), 1)

            # Memory
            code, out, _ = await self.run(
                "free | awk '/Mem:/{printf \"%.1f\", $3/$2*100}'",
                timeout=10,
            )
            if code == 0 and out:
                metrics["memory_percent"] = round(float(out), 1)

            # Disk
            code, out, _ = await self.run(
                "df / | awk 'NR==2{gsub(/%/,\"\",$5); print $5}'",
                timeout=10,
            )
            if code == 0 and out:
                metrics["disk_percent"] = round(float(out), 1)

        except Exception as e:
            logger.warning(f"[{self.host}] metrics collection error: {e}")

        return metrics

    async def check_port(self, port: int) -> bool:
        """Проверить, слушает ли порт на localhost."""
        code, _, _ = await self.run(f"ss -tlnp | grep -q ':{port} '", timeout=10)
        return code == 0

    async def check_docker_container(self, name: str) -> bool:
        """Проверить, работает ли Docker-контейнер."""
        code, out, _ = await self.run(
            f"docker inspect -f '{{{{.State.Running}}}}' {name} 2>/dev/null",
            timeout=10,
        )
        return code == 0 and out.strip().lower() == "true"

    # ── Файлы ─────────────────────────────────────────────

    async def upload(self, local_path: str, remote_path: str):
        """Загрузить файл на сервер."""
        await self._ensure_connected()
        await asyncssh.scp(local_path, (self._conn, remote_path))
        logger.info(f"[{self.host}] uploaded {local_path} → {remote_path}")

    async def download(self, remote_path: str, local_path: str):
        """Скачать файл с сервера."""
        await self._ensure_connected()
        await asyncssh.scp((self._conn, remote_path), local_path)
        logger.info(f"[{self.host}] downloaded {remote_path} → {local_path}")

    # ── Context manager ───────────────────────────────────

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.disconnect()
