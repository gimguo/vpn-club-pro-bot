import aiohttp
import asyncio
from typing import Dict, Optional, List
from config import settings
import json
from datetime import datetime

class OutlineService:
    def __init__(self):
        self.servers = settings.outline_servers
        print(f"🖥️ OutlineService initialized with {len(self.servers)} servers: {self.servers}")
        
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

    async def get_least_loaded_server(self) -> str:
        """Получение наименее загруженного сервера на основе количества активных ключей"""
        server_loads = []
        
        for server in self.servers:
            try:
                # Получаем список ключей на сервере
                keys_data = await self._make_request(server, "GET", "access-keys")
                active_keys_count = len(keys_data.get("accessKeys", []))
                
                server_loads.append({
                    "server": server,
                    "load": active_keys_count,
                    "available": True
                })
                
            except Exception as e:
                print(f"Server {server} unavailable: {e}")
                server_loads.append({
                    "server": server,
                    "load": float('inf'),  # Недоступный сервер имеет бесконечную нагрузку
                    "available": False
                })
        
        # Сортируем по нагрузке (меньше ключей = меньше нагрузка)
        server_loads.sort(key=lambda x: x["load"])
        
        # Возвращаем наименее загруженный доступный сервер
        for server_info in server_loads:
            if server_info["available"]:
                print(f"Selected server {server_info['server']} with {server_info['load']} active keys")
                return server_info["server"]
        
        # Если все серверы недоступны, возвращаем первый
        print("All servers unavailable, using first server as fallback")
        return self.servers[0]

    async def get_transfer_data(self, server_url: str) -> Dict:
        """Получение данных о трафике"""
        try:
            return await self._make_request(server_url, "GET", "metrics/transfer")
        except:
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