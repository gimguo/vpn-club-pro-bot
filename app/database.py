from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from config import settings
from app.models.base import Base
import logging

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=settings.debug)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    """Создание таблиц в базе данных"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Миграция: добавляем новые колонки если их нет
        await _run_migrations(conn)

async def _run_migrations(conn):
    """Добавляем новые колонки для реферальной системы"""
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(20) UNIQUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS referred_by INTEGER REFERENCES users(id)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_bonus_days INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try:
            await conn.execute(text(sql))
            logger.info(f"Migration OK: {sql[:60]}...")
        except Exception as e:
            logger.debug(f"Migration skip: {e}")

async def get_db() -> AsyncSession:
    """Получение сессии базы данных"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() 