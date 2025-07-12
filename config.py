import os
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

class Settings:
    # Telegram Bot
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_id: int = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
    bot_username: str = os.getenv("TELEGRAM_BOT_USERNAME", "vpn_club_pro_bot")
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres_password@localhost:5432/vpn_club")
    
    # YooKassa
    yookassa_shop_id: str = os.getenv("YOOKASSA_SHOP_ID", "")
    yookassa_secret_key: str = os.getenv("YOOKASSA_SECRET_KEY", "")
    
    # Outline VPN
    outline_api_url: str = os.getenv("OUTLINE_API_URL", "")
    outline_cert_sha256: str = os.getenv("OUTLINE_CERT_SHA256", "")
    
    # Multiple Outline Servers for Load Balancing
    @property
    def outline_servers(self) -> list:
        """Получаем список серверов из разных источников для обратной совместимости"""
        servers = []
        
        # Новый способ - через OUTLINE_SERVERS (приоритет)
        if os.getenv("OUTLINE_SERVERS"):
            servers = [url.strip() for url in os.getenv("OUTLINE_SERVERS").split(",") if url.strip()]
        
        # Старый способ - через OUTLINE_SERVER_1_URL, OUTLINE_SERVER_2_URL и т.д.
        elif os.getenv("OUTLINE_SERVER_1_URL") or os.getenv("OUTLINE_SERVER_2_URL"):
            for i in range(1, 10):  # Поддерживаем до 9 серверов
                server_url = os.getenv(f"OUTLINE_SERVER_{i}_URL")
                if server_url:
                    servers.append(server_url.strip())
        
        # Fallback на OUTLINE_API_URL
        elif self.outline_api_url:
            servers = [self.outline_api_url]
        
        return servers if servers else [""]
    
    # Pricing
    trial_price: int = int(os.getenv("TRIAL_PRICE", "99"))
    monthly_price: int = int(os.getenv("MONTHLY_PRICE", "150"))
    quarterly_price: int = int(os.getenv("QUARTERLY_PRICE", "350"))
    half_yearly_price: int = int(os.getenv("HALF_YEARLY_PRICE", "650"))
    yearly_price: int = int(os.getenv("YEARLY_PRICE", "1200"))
    
    # Trial settings
    trial_days: int = int(os.getenv("TRIAL_DAYS", "3"))
    trial_traffic_gb: int = int(os.getenv("TRIAL_TRAFFIC_GB", "10"))
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Webhook
    webhook_url: str = os.getenv("WEBHOOK_URL", "")
    
    # Debug
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"

settings = Settings() 