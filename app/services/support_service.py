from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, func
from app.models import SupportTicket, SupportMessage, User
from typing import Optional, List
from datetime import datetime
import secrets
import string

class SupportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _generate_ticket_number(self) -> str:
        """Генерация уникального номера тикета"""
        # Формат: SUP-YYYYMMDD-XXXXX
        date_part = datetime.now().strftime("%Y%m%d")
        random_part = ''.join(secrets.choice(string.digits) for _ in range(5))
        return f"SUP-{date_part}-{random_part}"

    async def create_ticket(self, user_id: int, message: str, 
                          category: str = "other", subject: str = None) -> SupportTicket:
        """Создание нового тикета поддержки"""
        ticket_number = self._generate_ticket_number()
        
        # Проверяем уникальность номера
        while await self._ticket_exists(ticket_number):
            ticket_number = self._generate_ticket_number()
        
        ticket = SupportTicket(
            user_id=user_id,
            ticket_number=ticket_number,
            subject=subject,
            message=message,
            category=category,
            status="new"
        )
        
        self.session.add(ticket)
        await self.session.commit()
        await self.session.refresh(ticket)
        
        # Создаем первое сообщение в тикете
        first_message = SupportMessage(
            ticket_id=ticket.id,
            user_id=user_id,
            message=message,
            is_from_admin=False
        )
        
        self.session.add(first_message)
        await self.session.commit()
        
        return ticket

    async def _ticket_exists(self, ticket_number: str) -> bool:
        """Проверка существования тикета с данным номером"""
        result = await self.session.execute(
            select(SupportTicket).where(SupportTicket.ticket_number == ticket_number)
        )
        return result.scalar_one_or_none() is not None

    async def get_user_tickets(self, user_id: int, limit: int = 10) -> List[SupportTicket]:
        """Получение тикетов пользователя"""
        result = await self.session.execute(
            select(SupportTicket)
            .where(SupportTicket.user_id == user_id)
            .order_by(desc(SupportTicket.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_ticket_by_number(self, ticket_number: str) -> Optional[SupportTicket]:
        """Получение тикета по номеру"""
        result = await self.session.execute(
            select(SupportTicket).where(SupportTicket.ticket_number == ticket_number)
        )
        return result.scalar_one_or_none()

    async def add_message_to_ticket(self, ticket_id: int, message: str = "", 
                                  user_id: int = None, admin_id: int = None,
                                  is_from_admin: bool = False) -> SupportMessage:
        """Добавление сообщения в тикет"""
        support_message = SupportMessage(
            ticket_id=ticket_id,
            user_id=user_id,
            admin_id=admin_id,
            message=message,
            is_from_admin=is_from_admin or (admin_id is not None)
        )
        
        self.session.add(support_message)
        
        # Обновляем статус тикета
        if admin_id:
            # Если отвечает админ - ставим "в работе"
            await self._update_ticket_status(ticket_id, "in_progress", admin_id)
        
        await self.session.commit()
        await self.session.refresh(support_message)
        
        return support_message

    async def _update_ticket_status(self, ticket_id: int, status: str, admin_id: int = None):
        """Обновление статуса тикета"""
        result = await self.session.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        
        if ticket:
            ticket.status = status
            if admin_id:
                ticket.admin_id = admin_id
            if status == "closed":
                ticket.closed_at = datetime.now()
            elif status == "in_progress" and not ticket.responded_at:
                ticket.responded_at = datetime.now()

    async def close_ticket(self, ticket_id: int, admin_id: int = None):
        """Закрытие тикета"""
        await self._update_ticket_status(ticket_id, "closed", admin_id)
        await self.session.commit()

    async def get_ticket_messages(self, ticket_id: int) -> List[SupportMessage]:
        """Получение всех сообщений тикета"""
        result = await self.session.execute(
            select(SupportMessage)
            .where(SupportMessage.ticket_id == ticket_id)
            .order_by(SupportMessage.created_at)
        )
        return result.scalars().all()

    async def get_new_tickets(self, limit: int = 50) -> List[SupportTicket]:
        """Получение новых тикетов для админов"""
        result = await self.session.execute(
            select(SupportTicket)
            .where(SupportTicket.status == "new")
            .order_by(desc(SupportTicket.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_ticket_stats(self) -> dict:
        """Статистика по тикетам"""
        # Всего тикетов
        total_result = await self.session.execute(select(SupportTicket))
        total = len(total_result.scalars().all())
        
        # Новые
        new_result = await self.session.execute(
            select(SupportTicket).where(SupportTicket.status == "new")
        )
        new_count = len(new_result.scalars().all())
        
        # В работе
        in_progress_result = await self.session.execute(
            select(SupportTicket).where(SupportTicket.status == "in_progress")
        )
        in_progress_count = len(in_progress_result.scalars().all())
        
        # Закрытые
        closed_result = await self.session.execute(
            select(SupportTicket).where(SupportTicket.status == "closed")
        )
        closed_count = len(closed_result.scalars().all())
        
        return {
            "total": total,
            "new": new_count,
            "in_progress": in_progress_count,
            "closed": closed_count
        }

    async def get_ticket_info(self, ticket_id: int):
        """Получение информации о тикете"""
        result = await self.session.execute(
            select(SupportTicket).where(SupportTicket.id == ticket_id)
        )
        return result.scalar_one_or_none()
    
    # Методы для админки
    async def get_admin_stats(self):
        """Получение статистики для админ панели"""
        # Статистика по статусам
        result = await self.session.execute(
            select(SupportTicket.status, func.count(SupportTicket.id))
            .group_by(SupportTicket.status)
        )
        status_counts = dict(result.all())
        
        # Общее количество
        total_result = await self.session.execute(
            select(func.count(SupportTicket.id))
        )
        total = total_result.scalar()
        
        return {
            "new": status_counts.get("new", 0),
            "in_progress": status_counts.get("in_progress", 0), 
            "closed": status_counts.get("closed", 0),
            "total": total
        }
    
    async def get_all_tickets(self, limit: int = 10):
        """Получение всех тикетов для админки"""
        result = await self.session.execute(
            select(SupportTicket)
            .order_by(SupportTicket.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all() 