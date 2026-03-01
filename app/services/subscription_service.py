from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models import Subscription, User
from app.services.outline_service import OutlineService
from config import settings
from datetime import datetime, timedelta
from typing import Optional, List
import pytz

class SubscriptionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.outline_service = OutlineService()

    async def create_subscription(self, user_id: int, tariff_type: str) -> Subscription:
        """Создание новой подписки"""
        
        # Если это платная подписка, проверяем и деактивируем активную триал подписку
        if tariff_type != "trial":
            existing_subscription = await self.get_active_subscription(user_id)
            if existing_subscription and existing_subscription.tariff_type == "trial":
                await self.deactivate_subscription(existing_subscription)
        
        # Получаем наименее загруженный сервер
        server_url = await self.outline_service.get_least_loaded_server()
        
        # Создаем ключ в Outline
        key_data = await self.outline_service.create_key(
            server_url, 
            name=f"user_{user_id}_{tariff_type}"
        )
        
        # Вычисляем даты начала и окончания подписки
        start_date = datetime.now(pytz.UTC)
        end_date = self._calculate_end_date(start_date, tariff_type)
        
        # Устанавливаем лимит трафика для пробного периода
        traffic_limit_gb = None
        if tariff_type == "trial":
            traffic_limit_gb = settings.trial_traffic_gb
            # Устанавливаем лимит в Outline (конвертируем ГБ в байты)
            limit_bytes = traffic_limit_gb * 1024 * 1024 * 1024
            await self.outline_service.set_data_limit(
                server_url, 
                key_data["id"], 
                limit_bytes
            )
        
        # Создаем запись подписки в БД
        subscription = Subscription(
            user_id=user_id,
            outline_key_id=key_data["id"],
            outline_server_url=server_url,
            access_url=key_data["accessUrl"],
            tariff_type=tariff_type,
            start_date=start_date,
            end_date=end_date,
            traffic_limit_gb=traffic_limit_gb
        )
        
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        
        return subscription

    def _calculate_end_date(self, start_date: datetime, tariff_type: str) -> datetime:
        """Вычисление даты окончания подписки"""
        if tariff_type == "trial":
            return start_date + timedelta(days=settings.trial_days)
        elif tariff_type == "monthly":
            return start_date + timedelta(days=30)
        elif tariff_type == "quarterly":
            return start_date + timedelta(days=90)
        elif tariff_type == "half_yearly":
            return start_date + timedelta(days=180)
        elif tariff_type == "yearly":
            return start_date + timedelta(days=365)
        elif tariff_type == "unlimited":
            return start_date + timedelta(days=36500)  # ~100 лет
        else:
            return start_date + timedelta(days=30)

    async def get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """Получение самой свежей активной подписки пользователя"""
        result = await self.session.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.user_id == user_id,
                    Subscription.is_active == True,
                    Subscription.end_date > datetime.now(pytz.UTC)
                )
            )
            .order_by(Subscription.end_date.desc())
        )
        return result.scalars().first()

    async def get_expiring_subscriptions(self, days_before: int = 3) -> List[Subscription]:
        """Получение подписок, истекающих через указанное количество дней"""
        target_date = datetime.now(pytz.UTC) + timedelta(days=days_before)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        result = await self.session.execute(
            select(Subscription).where(
                and_(
                    Subscription.is_active == True,
                    Subscription.end_date >= start_of_day,
                    Subscription.end_date <= end_of_day
                )
            )
        )
        return result.scalars().all()

    async def get_expired_subscriptions(self) -> List[Subscription]:
        """Получение истекших подписок"""
        now = datetime.now(pytz.UTC)
        result = await self.session.execute(
            select(Subscription).where(
                and_(
                    Subscription.is_active == True,
                    Subscription.end_date <= now
                )
            )
        )
        return result.scalars().all()

    async def deactivate_subscription(self, subscription: Subscription):
        """Деактивация подписки и удаление ключа"""
        try:
            # Удаляем ключ из Outline
            await self.outline_service.delete_key(
                subscription.outline_server_url,
                subscription.outline_key_id
            )
        except Exception as e:
            print(f"Ошибка при удалении ключа: {e}")
        
        # Деактивируем подписку в БД
        subscription.is_active = False
        await self.session.commit()

    async def get_subscription_info(self, subscription: Subscription) -> dict:
        """Получение информации о подписке с данными о трафике"""
        try:
            # Получаем данные о трафике из Outline
            transfer_data = await self.outline_service.get_transfer_data(
                subscription.outline_server_url
            )
            
            # Ищем данные по нашему ключу
            used_bytes = 0
            if "bytesTransferredByUserId" in transfer_data:
                used_bytes = transfer_data["bytesTransferredByUserId"].get(
                    subscription.outline_key_id, 0
                )
            
            used_gb = round(used_bytes / (1024 ** 3), 2)
            
            # Вычисляем оставшиеся дни
            now = datetime.now(pytz.UTC)
            remaining_days = (subscription.end_date - now).days
            
            return {
                "tariff_type": subscription.tariff_type,
                "end_date": subscription.end_date,
                "remaining_days": max(0, remaining_days),
                "traffic_used_gb": used_gb,
                "traffic_limit_gb": subscription.traffic_limit_gb,
                "is_active": subscription.is_active and subscription.end_date > now
            }
        except Exception as e:
            print(f"Ошибка при получении информации о подписке: {e}")
            return {
                "tariff_type": subscription.tariff_type,
                "end_date": subscription.end_date,
                "remaining_days": 0,
                "traffic_used_gb": 0,
                "traffic_limit_gb": subscription.traffic_limit_gb,
                "is_active": False
            } 