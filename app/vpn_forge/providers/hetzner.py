"""
VPN Forge — Провайдер Hetzner Cloud.

Создание, удаление, ребут серверов через Hetzner Cloud API.
Документация: https://docs.hetzner.cloud/
"""
import logging
from typing import Dict, List, Optional

import aiohttp

from app.vpn_forge.providers.base import BaseProvider, ProvisionedServer
from config import settings

logger = logging.getLogger(__name__)

HETZNER_API_BASE = "https://api.hetzner.cloud/v1"

# Дефолтные настройки
DEFAULT_PLAN = "cx22"          # 2 vCPU, 4 GB RAM, 40 GB SSD — €3.79/мес
DEFAULT_IMAGE = "ubuntu-22.04"
DEFAULT_REGION = "fsn1"        # Falkenstein, Germany

# Маппинг регионов к странам
REGION_COUNTRY = {
    "fsn1": "DE", "nbg1": "DE", "hel1": "FI",
    "ash": "US", "hil": "US", "sin": "SG",
}


class HetznerProvider(BaseProvider):
    """Провайдер Hetzner Cloud."""

    def __init__(self):
        self.api_token = settings.hetzner_api_token
        if not self.api_token:
            logger.warning("Hetzner API token not configured!")

    @property
    def name(self) -> str:
        return "hetzner"

    def _headers(self) -> Dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, endpoint: str,
                       data: dict = None) -> Dict:
        """Базовый HTTP-запрос к Hetzner API."""
        url = f"{HETZNER_API_BASE}/{endpoint}"
        async with aiohttp.ClientSession() as http:
            kwargs = {"headers": self._headers(), "timeout": aiohttp.ClientTimeout(total=30)}
            if data:
                kwargs["json"] = data

            async with http.request(method, url, **kwargs) as resp:
                body = await resp.json()
                if resp.status >= 400:
                    error_msg = body.get("error", {}).get("message", str(body))
                    raise RuntimeError(f"Hetzner API error ({resp.status}): {error_msg}")
                return body

    # ── Создание сервера ──────────────────────────────────

    async def create_server(self, name: str, region: str = DEFAULT_REGION,
                            plan: str = DEFAULT_PLAN, ssh_key_name: str = None,
                            image: str = DEFAULT_IMAGE) -> ProvisionedServer:
        """Создать сервер в Hetzner Cloud."""
        payload = {
            "name": name,
            "server_type": plan,
            "image": image,
            "location": region,
            "start_after_create": True,
        }

        # Добавляем SSH-ключ если указан
        if ssh_key_name:
            ssh_keys = await self._get_ssh_keys()
            key_id = next((k["id"] for k in ssh_keys if k["name"] == ssh_key_name), None)
            if key_id:
                payload["ssh_keys"] = [key_id]

        logger.info(f"Creating Hetzner server: {name} ({plan} in {region})")
        result = await self._request("POST", "servers", payload)

        server_data = result["server"]
        ip_address = server_data["public_net"]["ipv4"]["ip"]

        # Получаем стоимость
        prices = await self._get_server_type_price(plan, region)
        monthly_cost = int(float(prices.get("monthly", "0")) * 100)  # В центы

        logger.info(f"Hetzner server created: {name} → {ip_address} (id={server_data['id']})")

        return ProvisionedServer(
            provider_server_id=str(server_data["id"]),
            ip_address=ip_address,
            region=region,
            country=REGION_COUNTRY.get(region, "??"),
            plan=plan,
            monthly_cost_cents=monthly_cost,
        )

    # ── Удаление ──────────────────────────────────────────

    async def delete_server(self, server_id: str) -> bool:
        """Удалить сервер."""
        try:
            await self._request("DELETE", f"servers/{server_id}")
            logger.info(f"Hetzner server {server_id} deleted")
            return True
        except Exception as e:
            logger.error(f"Failed to delete Hetzner server {server_id}: {e}")
            return False

    # ── Ребут ─────────────────────────────────────────────

    async def reboot_server(self, server_id: str) -> bool:
        """Перезагрузить сервер (soft reboot)."""
        try:
            await self._request("POST", f"servers/{server_id}/actions/reboot")
            logger.info(f"Hetzner server {server_id} rebooting")
            return True
        except Exception as e:
            logger.error(f"Failed to reboot Hetzner server {server_id}: {e}")
            return False

    # ── Статус ────────────────────────────────────────────

    async def get_server_status(self, server_id: str) -> Optional[str]:
        """Получить статус сервера."""
        try:
            result = await self._request("GET", f"servers/{server_id}")
            return result["server"]["status"]
        except Exception as e:
            logger.error(f"Failed to get status of Hetzner server {server_id}: {e}")
            return None

    # ── Список серверов ───────────────────────────────────

    async def list_servers(self) -> List[Dict]:
        """Получить все серверы."""
        result = await self._request("GET", "servers?per_page=50")
        servers = []
        for s in result.get("servers", []):
            servers.append({
                "id": str(s["id"]),
                "name": s["name"],
                "status": s["status"],
                "ip": s["public_net"]["ipv4"]["ip"],
                "type": s["server_type"]["name"],
                "location": s["datacenter"]["location"]["name"],
                "created": s["created"],
            })
        return servers

    # ── Регионы ───────────────────────────────────────────

    async def get_available_regions(self) -> List[Dict]:
        """Получить доступные дата-центры."""
        result = await self._request("GET", "locations")
        return [
            {
                "id": loc["name"],
                "name": loc["description"],
                "country": loc["country"],
                "city": loc["city"],
            }
            for loc in result.get("locations", [])
        ]

    # ── Планы/тарифы ─────────────────────────────────────

    async def get_available_plans(self) -> List[Dict]:
        """Получить доступные типы серверов."""
        result = await self._request("GET", "server_types?per_page=50")
        plans = []
        for st in result.get("server_types", []):
            plans.append({
                "id": st["name"],
                "description": st["description"],
                "cores": st["cores"],
                "memory_gb": st["memory"],
                "disk_gb": st["disk"],
                "deprecated": st.get("deprecated", False),
            })
        return plans

    # ── Вспомогательные ───────────────────────────────────

    async def _get_ssh_keys(self) -> List[Dict]:
        """Получить SSH-ключи из аккаунта."""
        result = await self._request("GET", "ssh_keys")
        return result.get("ssh_keys", [])

    async def _get_server_type_price(self, plan: str, location: str) -> Dict:
        """Получить цену для конкретного плана в регионе."""
        try:
            result = await self._request("GET", f"server_types?name={plan}")
            server_types = result.get("server_types", [])
            if server_types:
                for price in server_types[0].get("prices", []):
                    if price["location"] == location:
                        return {
                            "monthly": price["price_monthly"]["gross"],
                            "hourly": price["price_hourly"]["gross"],
                        }
        except Exception:
            pass
        return {"monthly": "0", "hourly": "0"}

    async def create_ssh_key(self, name: str, public_key: str) -> Optional[int]:
        """Загрузить SSH-ключ в Hetzner."""
        try:
            result = await self._request("POST", "ssh_keys", {
                "name": name,
                "public_key": public_key,
            })
            return result["ssh_key"]["id"]
        except Exception as e:
            logger.error(f"Failed to create SSH key in Hetzner: {e}")
            return None
