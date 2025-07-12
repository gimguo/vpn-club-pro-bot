from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import User
from typing import Optional

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, telegram_id: int, username: str = None, 
                                first_name: str = None, last_name: str = None,
                                language_code: str = None) -> User:
        """Получить существующего пользователя или создать нового"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        
        return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Получить пользователя по ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def mark_trial_used(self, user_id: int):
        """Отметить что пробный период использован"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.is_trial_used = True
            await self.session.commit()

    async def get_all_active_users(self):
        """Получить всех активных пользователей"""
        result = await self.session.execute(
            select(User).where(User.is_active == True)
        )
        return result.scalars().all() 