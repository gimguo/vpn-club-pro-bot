"""
VPN Forge — ИИ-агент для диагностики серверов.

Подключается по SSH, собирает диагностику,
отправляет в DeepSeek через OpenRouter,
получает рекомендации и (опционально) выполняет fix-команды.
"""
import asyncio
import logging
import json
from typing import Optional, Dict, List

import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession

from app.vpn_forge.models import VPNServer, ServerEvent
from app.vpn_forge.ssh_client import SSHClient
from config import settings

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Whitelist разрешённых команд (безопасность)
ALLOWED_COMMAND_PREFIXES = [
    "docker ", "systemctl ", "journalctl ", "cat ", "ls ", "df ", "free ",
    "top ", "ps ", "netstat ", "ss ", "iptables ", "ufw ", "curl ",
    "apt-get ", "apt ", "find ", "rm /var/log", "rm /tmp", "echo ",
    "sync", "sysctl ", "chmod ", "chown ", "mkdir ", "cp ", "mv ",
    "tail ", "head ", "grep ", "wc ", "du ", "ip ", "ping ",
    "service ", "nginx ", "certbot ",
]

# Запрещённые паттерны (строгий запрет)
FORBIDDEN_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "> /dev/sd",
    "chmod 777 /",
    "wget -O- | bash",
    "curl | bash",
    "shutdown",
    "poweroff",
    "halt",
    "init 0",
    "reboot",  # Ребут только через провайдера
]

MAX_COMMANDS_PER_SESSION = 5
MAX_DIAGNOSTIC_LENGTH = 8000


class AIAgent:
    """ИИ-агент для диагностики и автоматического лечения VPN-серверов."""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model

    # ── Главная точка входа ───────────────────────────────

    async def diagnose_and_fix(self, server: VPNServer, session: AsyncSession,
                                auto_execute: bool = True) -> Dict:
        """
        Полный цикл ИИ-диагностики сервера.

        1. SSH → сбор диагностики
        2. Отправка в DeepSeek → получение анализа + команд
        3. (опционально) Выполнение fix-команд
        4. Проверка результата

        Возвращает dict:
          - diagnosis: str  — текстовый диагноз
          - commands: list   — предложенные команды
          - executed: list   — выполненные команды с результатами
          - fixed: bool      — удалось ли починить
        """
        result = {
            "diagnosis": None,
            "commands": [],
            "executed": [],
            "fixed": False,
            "error": None,
        }

        if not self.api_key:
            result["error"] = "OpenRouter API key not configured"
            return result

        ssh: Optional[SSHClient] = None
        try:
            # 1. Подключаемся по SSH
            ssh = SSHClient(
                host=server.ip_address,
                username=server.ssh_user,
                port=server.ssh_port,
                key_path=server.ssh_key_path or settings.vpn_forge_ssh_key_path or None,
            )
            connected = await ssh.connect(timeout=15)
            if not connected:
                result["error"] = "Cannot connect via SSH for diagnostics"
                return result

            # 2. Собираем диагностику
            logger.info(f"[{server.name}] AI Agent: collecting diagnostics...")
            diagnostics = await self._collect_diagnostics(ssh)

            # Логируем событие
            event = ServerEvent(
                server_id=server.id,
                event_type="ai_diagnosis_started",
                severity="info",
                message="AI Agent started diagnostics",
                details={"diagnostics_length": len(diagnostics)},
                initiated_by="ai_agent",
            )
            session.add(event)
            await session.commit()

            # 3. Отправляем в DeepSeek
            logger.info(f"[{server.name}] AI Agent: consulting DeepSeek...")
            ai_response = await self._consult_llm(server, diagnostics)

            if not ai_response:
                result["error"] = "Failed to get response from AI"
                return result

            result["diagnosis"] = ai_response.get("diagnosis", "No diagnosis")
            result["commands"] = ai_response.get("commands", [])

            logger.info(f"[{server.name}] AI diagnosis: {result['diagnosis'][:200]}...")
            logger.info(f"[{server.name}] AI suggested {len(result['commands'])} commands")

            # Логируем диагноз
            event = ServerEvent(
                server_id=server.id,
                event_type="ai_diagnosed",
                severity="info",
                message=result["diagnosis"][:500],
                details={
                    "commands_count": len(result["commands"]),
                    "commands": result["commands"][:MAX_COMMANDS_PER_SESSION],
                },
                initiated_by="ai_agent",
            )
            session.add(event)
            await session.commit()

            # 4. Выполняем команды (если разрешено)
            if auto_execute and result["commands"]:
                safe_commands = self._filter_safe_commands(result["commands"])
                logger.info(f"[{server.name}] Executing {len(safe_commands)} safe commands...")

                for cmd in safe_commands[:MAX_COMMANDS_PER_SESSION]:
                    try:
                        code, stdout, stderr = await ssh.run(cmd, timeout=120)
                        cmd_result = {
                            "command": cmd,
                            "exit_code": code,
                            "stdout": stdout[:500],
                            "stderr": stderr[:500],
                        }
                        result["executed"].append(cmd_result)
                        logger.info(f"[{server.name}] Executed: {cmd} → exit {code}")
                    except Exception as e:
                        result["executed"].append({
                            "command": cmd,
                            "error": str(e)[:200],
                        })

                # 5. Проверяем — помогло ли
                await asyncio.sleep(10)
                docker_ok = await ssh.check_docker_container("shadowbox")

                if docker_ok:
                    result["fixed"] = True
                    server.status = "active"
                    server.consecutive_failures = 0

                    event = ServerEvent(
                        server_id=server.id,
                        event_type="ai_fixed",
                        severity="info",
                        message=f"AI Agent fixed the server. Executed {len(result['executed'])} commands.",
                        details={"executed": result["executed"]},
                        initiated_by="ai_agent",
                    )
                    session.add(event)
                    logger.info(f"[{server.name}] ✅ AI Agent fixed the server!")
                else:
                    event = ServerEvent(
                        server_id=server.id,
                        event_type="ai_fix_failed",
                        severity="warning",
                        message="AI Agent commands executed but server still not healthy",
                        details={"executed": result["executed"]},
                        initiated_by="ai_agent",
                    )
                    session.add(event)

                await session.commit()

        except Exception as e:
            logger.error(f"[{server.name}] AI Agent error: {e}", exc_info=True)
            result["error"] = str(e)

            event = ServerEvent(
                server_id=server.id,
                event_type="ai_error",
                severity="error",
                message=f"AI Agent error: {str(e)[:300]}",
                initiated_by="ai_agent",
            )
            session.add(event)
            await session.commit()
        finally:
            if ssh:
                await ssh.disconnect()

        return result

    # ── Сбор диагностики ──────────────────────────────────

    async def _collect_diagnostics(self, ssh: SSHClient) -> str:
        """Собрать диагностическую информацию с сервера."""
        commands = {
            "system_info": "uname -a",
            "uptime": "uptime",
            "disk": "df -h",
            "memory": "free -h",
            "cpu_top": "top -bn1 | head -20",
            "docker_ps": "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'Docker not available'",
            "docker_logs_shadowbox": "docker logs shadowbox --tail 100 2>&1 | tail -80",
            "docker_logs_watchtower": "docker logs watchtower --tail 30 2>&1 | tail -20",
            "systemd_journal": "journalctl -n 50 --no-pager 2>/dev/null | tail -40",
            "dmesg": "dmesg | tail -30",
            "network_listeners": "ss -tlnp",
            "network_connections": "ss -tun | wc -l",
            "iptables": "iptables -L -n --line-numbers 2>/dev/null | head -40",
            "outline_config": "cat /opt/outline/access.txt 2>/dev/null || echo 'not found'",
            "processes": "ps aux --sort=-%mem | head -15",
        }

        sections = []
        for name, cmd in commands.items():
            try:
                code, stdout, stderr = await ssh.run(cmd, timeout=15)
                output = stdout if stdout else stderr
                sections.append(f"=== {name} ===\n{output}")
            except Exception as e:
                sections.append(f"=== {name} ===\nERROR: {e}")

        full_diagnostics = "\n\n".join(sections)

        # Ограничиваем длину
        if len(full_diagnostics) > MAX_DIAGNOSTIC_LENGTH:
            full_diagnostics = full_diagnostics[:MAX_DIAGNOSTIC_LENGTH] + "\n... (truncated)"

        return full_diagnostics

    # ── Взаимодействие с LLM ──────────────────────────────

    async def _consult_llm(self, server: VPNServer, diagnostics: str) -> Optional[Dict]:
        """Отправить диагностику в DeepSeek через OpenRouter."""
        system_prompt = """Ты — опытный DevOps-инженер, специализирующийся на VPN-серверах. 
Ты анализируешь диагностику сервера с Outline VPN (Shadowbox).

Твоя задача:
1. Определить корневую причину проблемы
2. Предложить конкретные bash-команды для исправления

ВАЖНО:
- Давай ТОЛЬКО безопасные команды
- НИКОГДА не предлагай rm -rf /, shutdown, reboot, mkfs, dd
- Максимум 5 команд
- Команды должны быть идемпотентными (безопасны при повторном выполнении)
- Фокус на: Docker-контейнеры (shadowbox, watchtower), сеть, диск, память

Ответ СТРОГО в JSON формате:
{
  "diagnosis": "Краткое описание проблемы на русском",
  "root_cause": "Корневая причина",
  "severity": "low|medium|high|critical",
  "commands": ["команда1", "команда2", ...],
  "explanation": "Объяснение каждой команды"
}"""

        user_prompt = f"""Сервер: {server.name} ({server.ip_address})
Провайдер: {server.provider}, регион: {server.region}
Статус: {server.status}
Последний статус проверки: {server.last_health_status}
Подряд ошибок: {server.consecutive_failures}

ДИАГНОСТИКА:
{diagnostics}

Проанализируй и предложи исправление."""

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://vpn-forge.local",
                "X-Title": "VPN Forge AI Agent",
            }

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
                "response_format": {"type": "json_object"},
            }

            async with aiohttp.ClientSession() as http:
                async with http.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"OpenRouter API error {resp.status}: {error_text[:300]}")
                        return None

                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]

                    # Парсим JSON из ответа
                    return self._parse_llm_response(content)

        except Exception as e:
            logger.error(f"LLM consultation failed: {e}")
            return None

    @staticmethod
    def _parse_llm_response(content: str) -> Optional[Dict]:
        """Парсинг JSON ответа от LLM."""
        try:
            # Пробуем напрямую
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Пробуем извлечь JSON из markdown блока
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Пробуем найти { ... }
        brace_match = re.search(r'\{.*\}', content, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"Could not parse LLM response as JSON: {content[:200]}")
        return {"diagnosis": content[:500], "commands": []}

    # ── Фильтрация команд ─────────────────────────────────

    def _filter_safe_commands(self, commands: List[str]) -> List[str]:
        """Фильтрация команд: только безопасные из whitelist."""
        safe = []
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue

            # Проверяем запрещённые паттерны
            is_forbidden = False
            for pattern in FORBIDDEN_PATTERNS:
                if pattern in cmd:
                    logger.warning(f"BLOCKED forbidden command: {cmd}")
                    is_forbidden = True
                    break

            if is_forbidden:
                continue

            # Проверяем whitelist
            is_allowed = False
            for prefix in ALLOWED_COMMAND_PREFIXES:
                if cmd.startswith(prefix):
                    is_allowed = True
                    break

            if is_allowed:
                safe.append(cmd)
            else:
                logger.warning(f"BLOCKED non-whitelisted command: {cmd}")

        return safe

    # ── Dry-run режим ─────────────────────────────────────

    async def diagnose_only(self, server: VPNServer, session: AsyncSession) -> Dict:
        """Только диагностика без выполнения команд."""
        return await self.diagnose_and_fix(server, session, auto_execute=False)
