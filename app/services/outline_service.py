import aiohttp
import asyncio
import logging
from typing import Dict, Optional, List
from config import settings
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class OutlineService:
    def __init__(self):
        self.servers = settings.outline_servers
        logger.info(f"OutlineService initialized with {len(self.servers)} env servers")
        
    async def _make_request(self, server_url: str, method: str, endpoint: str, data: dict = None) -> dict:
        """Базовый метод для выполнения HTTP запросов к Outline API"""
        url = f"{server_url}/{endpoint}"
        
        # Отключаем проверку SSL для self-signed сертификатов
        connector = aiohttp.TCPConnector(ssl=False)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                if method.upper() == "GET":
                    async with session.get(url) as response:
                        return await response.json()
                elif method.upper() == "POST":
                    async with session.post(url, json=data) as response:
                        return await response.json()
                elif method.upper() == "PUT":
                    async with session.put(url, json=data) as response:
                        if response.status == 204:
                            return {"status": "ok"}
                        return await response.json()
                elif method.upper() == "DELETE":
                    async with session.delete(url) as response:
                        return {"status": "deleted"} if response.status == 204 else await response.json()
            except Exception as e:
                raise Exception(f"Ошибка запроса к Outline API: {str(e)}")

    async def create_key(self, server_url: str, name: str = None) -> Dict:
        """Создание нового ключа доступа"""
        data = {"name": name} if name else {}
        return await self._make_request(server_url, "POST", "access-keys", data)

    async def delete_key(self, server_url: str, key_id: str) -> Dict:
        """Удаление ключа доступа"""
        return await self._make_request(server_url, "DELETE", f"access-keys/{key_id}")

    async def get_key_info(self, server_url: str, key_id: str) -> Dict:
        """Получение информации о ключе"""
        keys = await self._make_request(server_url, "GET", "access-keys")
        for key in keys.get("accessKeys", []):
            if key["id"] == key_id:
                return key
        return None

    async def set_data_limit(self, server_url: str, key_id: str, limit_bytes: int) -> Dict:
        """Установка лимита трафика для ключа"""
        data = {"limit": {"bytes": limit_bytes}}
        return await self._make_request(server_url, "PUT", f"access-keys/{key_id}/data-limit", data)

    async def get_server_info(self, server_url: str) -> Dict:
        """Получение информации о сервере"""
        return await self._make_request(server_url, "GET", "server")

    async def _get_forge_servers(self) -> List[Dict]:
        """Получить список активных серверов из VPN Forge БД с приоритетом."""
        if not settings.vpn_forge_enabled:
            return []
        try:
            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            from app.vpn_forge.models import VPNServer

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(VPNServer.outline_api_url, VPNServer.priority, VPNServer.name).where(
                        VPNServer.status == "active",
                        VPNServer.is_active == True,
                        VPNServer.outline_api_url.isnot(None),
                    ).order_by(VPNServer.priority.asc())
                )
                servers = [
                    {"url": row[0], "priority": row[1] or 50, "name": row[2]}
                    for row in result.all() if row[0]
                ]
                if servers:
                    logger.info(f"VPN Forge: found {len(servers)} active servers: {[s['name'] for s in servers]}")
                return servers
        except Exception as e:
            logger.warning(f"VPN Forge DB query failed, falling back to .env: {e}")
            return []

    async def get_least_loaded_server(self) -> str:
        """Получение наименее загруженного сервера.
        
        Сортировка: приоритет (из БД) → количество ключей.
        Сервер с меньшим priority выбирается первым при равной нагрузке.
        """
        forge_servers = await self._get_forge_servers()
        
        server_loads = []
        
        if forge_servers:
            # VPN Forge режим: учитываем приоритет из БД
            for srv in forge_servers:
                try:
                    keys_data = await self._make_request(srv["url"], "GET", "access-keys")
                    active_keys_count = len(keys_data.get("accessKeys", []))
                    server_loads.append({
                        "server": srv["url"],
                        "name": srv["name"],
                        "priority": srv["priority"],
                        "load": active_keys_count,
                        "available": True
                    })
                except Exception as e:
                    logger.warning(f"Server {srv['name']} unavailable: {e}")
                    server_loads.append({
                        "server": srv["url"],
                        "name": srv["name"],
                        "priority": srv["priority"],
                        "load": float('inf'),
                        "available": False
                    })
            
            # Сортируем: сначала по приоритету, потом по нагрузке
            server_loads.sort(key=lambda x: (x["priority"], x["load"]))
        else:
            # Fallback на .env серверы
            for server in self.servers:
                if not server:
                    continue
                try:
                    keys_data = await self._make_request(server, "GET", "access-keys")
                    active_keys_count = len(keys_data.get("accessKeys", []))
                    server_loads.append({
                        "server": server,
                        "name": "env",
                        "priority": 50,
                        "load": active_keys_count,
                        "available": True
                    })
                except Exception as e:
                    logger.warning(f"Server {server[:40]}... unavailable: {e}")
                    server_loads.append({
                        "server": server,
                        "name": "env",
                        "priority": 50,
                        "load": float('inf'),
                        "available": False
                    })
            server_loads.sort(key=lambda x: x["load"])
        
        # Возвращаем лучший доступный сервер
        for server_info in server_loads:
            if server_info["available"]:
                logger.info(
                    f"Selected server {server_info['name']} "
                    f"(priority={server_info['priority']}, keys={server_info['load']})"
                )
                return server_info["server"]
        
        # Fallback
        if forge_servers:
            fallback = forge_servers[0]["url"]
        elif self.servers:
            fallback = self.servers[0]
        else:
            raise RuntimeError("No Outline servers configured")
        logger.warning(f"All servers unavailable, using fallback")
        return fallback

    async def get_transfer_data(self, server_url: str) -> Dict:
        """Получение данных о трафике"""
        try:
            return await self._make_request(server_url, "GET", "metrics/transfer")
        except Exception as e:
            logger.warning(f"Failed to get transfer data: {e}")
            return {} 

    async def get_all_servers_stats(self) -> List[Dict]:
        """Получение статистики по всем серверам для админки"""
        stats = []
        
        for server in self.servers:
            try:
                server_info = await self.get_server_info(server)
                keys_data = await self._make_request(server, "GET", "access-keys")
                transfer_data = await self.get_transfer_data(server)
                
                active_keys = len(keys_data.get("accessKeys", []))
                
                # Подсчитываем общий трафик
                total_bytes = 0
                if "bytesTransferredByUserId" in transfer_data:
                    total_bytes = sum(transfer_data["bytesTransferredByUserId"].values())
                
                stats.append({
                    "server_url": server,
                    "server_name": server_info.get("name", "Unknown"),
                    "active_keys": active_keys,
                    "total_traffic_gb": round(total_bytes / (1024**3), 2),
                    "status": "online",
                    "load_percentage": min(100, (active_keys / 100) * 100)  # Примерный расчет нагрузки
                })
                
            except Exception as e:
                stats.append({
                    "server_url": server,
                    "server_name": "Unknown",
                    "active_keys": 0,
                    "total_traffic_gb": 0,
                    "status": "offline",
                    "error": str(e),
                    "load_percentage": 0
                })
        
        return stats 