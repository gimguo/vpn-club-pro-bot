"""
VPN Forge — Базовый провайдер облачных серверов.

Абстрактный интерфейс: создание, удаление, ребут, статус серверов.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ProvisionedServer:
    """Результат создания сервера."""
    provider_server_id: str
    ip_address: str
    region: str
    country: str
    plan: str
    monthly_cost_cents: int


class BaseProvider(ABC):
    """Абстрактный провайдер облачных серверов."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Имя провайдера (hetzner, digitalocean, vultr)."""
        ...

    @abstractmethod
    async def create_server(self, name: str, region: str,
                            plan: str = None, ssh_key_name: str = None,
                            image: str = None) -> ProvisionedServer:
        """
        Создать новый сервер.

        Args:
            name: Имя сервера
            region: Регион (fsn1, nbg1, hel1, ...)
            plan: Тарифный план (cx22, cx32, ...) — по умолчанию самый дешёвый
            ssh_key_name: Имя SSH-ключа у провайдера
            image: Образ ОС или snapshot

        Returns:
            ProvisionedServer с ip_address и provider_server_id
        """
        ...

    @abstractmethod
    async def delete_server(self, server_id: str) -> bool:
        """Удалить сервер."""
        ...

    @abstractmethod
    async def reboot_server(self, server_id: str) -> bool:
        """Перезагрузить сервер."""
        ...

    @abstractmethod
    async def get_server_status(self, server_id: str) -> Optional[str]:
        """Получить статус сервера (running, stopped, ...)."""
        ...

    @abstractmethod
    async def list_servers(self) -> List[Dict]:
        """Получить список всех серверов."""
        ...

    @abstractmethod
    async def get_available_regions(self) -> List[Dict]:
        """Получить список доступных регионов."""
        ...

    @abstractmethod
    async def get_available_plans(self) -> List[Dict]:
        """Получить список доступных планов/тарифов."""
        ...
