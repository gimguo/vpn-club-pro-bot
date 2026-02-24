from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import User
from typing import Optional
import secrets
import string

class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    @staticmethod
    def _generate_referral_code() -> str:
        """Генерация уникального реферального кода"""
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(8))

    async def get_or_create_user(self, telegram_id: int, username: str = None, 
                                first_name: str = None, last_name: str = None,
                                language_code: str = None) -> User:
        """Получить существующего пользователя или создать нового"""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Генерируем уникальный реферальный код
            ref_code = self._generate_referral_code()
            while await self.get_user_by_referral_code(ref_code):
                ref_code = self._generate_referral_code()
            
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                referral_code=ref_code
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
        else:
            # Обновляем данные при изменении профиля Telegram
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if language_code and user.language_code != language_code:
                user.language_code = language_code
                updated = True
            if updated:
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

    async def get_user_by_referral_code(self, code: str) -> Optional[User]:
        """Найти пользователя по реферальному коду"""
        result = await self.session.execute(
            select(User).where(User.referral_code == code)
        )
        return result.scalar_one_or_none()

    async def process_referral(self, new_user: User, referrer_code: str) -> bool:
        """Обработать реферал: привязать нового юзера к пригласившему"""
        referrer = await self.get_user_by_referral_code(referrer_code)
        if not referrer or referrer.id == new_user.id:
            return False
        
        # Привязываем нового юзера к пригласившему
        new_user.referred_by = referrer.id
        
        # Начисляем бонусные дни пригласившему
        from config import settings
        referrer.referral_bonus_days = (referrer.referral_bonus_days or 0) + settings.referral_bonus_days
        
        await self.session.commit()
        return True

    async def get_referral_stats(self, user_id: int) -> dict:
        """Статистика рефералов пользователя"""
        # Количество приглашённых
        result = await self.session.execute(
            select(func.count(User.id)).where(User.referred_by == user_id)
        )
        referral_count = result.scalar() or 0
        
        # Получаем пользователя для бонусных дней
        user = await self.get_user_by_id(user_id)
        bonus_days = user.referral_bonus_days if user else 0
        
        return {
            "referral_count": referral_count,
            "bonus_days": bonus_days,
            "referral_code": user.referral_code if user else ""
        }
    
    async def ensure_referral_code(self, user: User) -> str:
        """Убедиться что у пользователя есть реферальный код"""
        if not user.referral_code:
            ref_code = self._generate_referral_code()
            while await self.get_user_by_referral_code(ref_code):
                ref_code = self._generate_referral_code()
            user.referral_code = ref_code
            await self.session.commit()
            await self.session.refresh(user)
        return user.referral_code 