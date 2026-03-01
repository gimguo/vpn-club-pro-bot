"""
VPN Forge — модели данных для управления VPN-серверами.
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import BaseModel


class VPNServer(BaseModel):
    """Управляемый VPN-сервер"""
    __tablename__ = "vpn_servers"

    name = Column(String(255), nullable=False, unique=True)
    provider = Column(String(50), nullable=False)  # hetzner, digitalocean, vultr, manual
    provider_server_id = Column(String(100), nullable=True)  # ID сервера у провайдера
    region = Column(String(50), nullable=False)  # fsn1, nbg1, hel1, ...
    country = Column(String(10), nullable=True)   # DE, NL, US, FI, ...

    ip_address = Column(String(50), nullable=False, unique=True)
    ssh_port = Column(Integer, default=22)
    ssh_user = Column(String(50), default="root")
    ssh_key_path = Column(String(500), nullable=True)  # Путь к SSH-ключу

    outline_api_url = Column(String(500), nullable=True)
    outline_cert_sha256 = Column(String(255), nullable=True)

    # provisioning → deploying → active → degraded → maintenance → offline → deleting
    status = Column(String(50), default="provisioning", index=True)
    is_active = Column(Boolean, default=False)  # Участвует ли в балансировке
    priority = Column(Integer, default=0)  # Приоритет для балансировки (0 = обычный)

    # Метрики
    cpu_percent = Column(Float, nullable=True)
    memory_percent = Column(Float, nullable=True)
    disk_percent = Column(Float, nullable=True)
    active_keys = Column(Integer, default=0)
    max_keys = Column(Integer, default=100)
    total_traffic_gb = Column(Float, default=0.0)

    # Стоимость
    monthly_cost_cents = Column(Integer, nullable=True)  # В центах
    provider_plan = Column(String(50), nullable=True)     # cx22, cx32, ...

    # Health
    last_health_check_at = Column(DateTime(timezone=True), nullable=True)
    last_health_status = Column(String(20), nullable=True)  # ok, warning, critical
    consecutive_failures = Column(Integer, default=0)

    # Auto-management
    auto_managed = Column(Boolean, default=True)   # Управляется VPN Forge
    auto_heal = Column(Boolean, default=True)       # Разрешено автолечение

    events = relationship("ServerEvent", back_populates="server", cascade="all, delete-orphan",
                          order_by="ServerEvent.created_at.desc()")
    health_checks = relationship("HealthCheck", back_populates="server", cascade="all, delete-orphan",
                                 order_by="HealthCheck.created_at.desc()")

    @property
    def load_percent(self) -> float:
        """Процент загрузки по ключам"""
        if not self.max_keys or self.max_keys <= 0:
            return 100.0
        return round(((self.active_keys or 0) / self.max_keys) * 100, 1)

    def __repr__(self):
        return f"<VPNServer(name='{self.name}', ip='{self.ip_address}', status='{self.status}')>"


class ServerEvent(BaseModel):
    """Лог событий сервера (аудит)"""
    __tablename__ = "server_events"

    server_id = Column(Integer, ForeignKey("vpn_servers.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(100), nullable=False, index=True)
    # provisioned, deployed, deploy_failed, health_ok, health_warning, health_critical,
    # healed, heal_failed, ai_diagnosed, ai_fixed, rebooted, scaled_up, scaled_down,
    # decommissioned, config_changed, manual_action
    severity = Column(String(20), default="info")  # info, warning, error, critical
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    initiated_by = Column(String(50), default="system")  # system, admin, ai_agent, healer

    server = relationship("VPNServer", back_populates="events")

    def __repr__(self):
        return f"<ServerEvent(server={self.server_id}, type='{self.event_type}')>"


class HealthCheck(BaseModel):
    """Результат проверки здоровья сервера"""
    __tablename__ = "health_checks"

    server_id = Column(Integer, ForeignKey("vpn_servers.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False)  # ok, warning, critical
    response_time_ms = Column(Integer, nullable=True)

    # Метрики на момент проверки
    ssh_ok = Column(Boolean, nullable=True)
    outline_api_ok = Column(Boolean, nullable=True)
    docker_ok = Column(Boolean, nullable=True)
    cpu_percent = Column(Float, nullable=True)
    memory_percent = Column(Float, nullable=True)
    disk_percent = Column(Float, nullable=True)

    details = Column(JSON, nullable=True)

    server = relationship("VPNServer", back_populates="health_checks")

    def __repr__(self):
        return f"<HealthCheck(server={self.server_id}, status='{self.status}')>"
