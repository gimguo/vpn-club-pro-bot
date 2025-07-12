from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel
from datetime import datetime

class SupportTicket(BaseModel):
    __tablename__ = "support_tickets"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ticket_number = Column(String(20), unique=True, nullable=False, index=True)
    subject = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="new")  # new, in_progress, closed
    priority = Column(String(10), default="normal")  # low, normal, high, urgent
    category = Column(String(50), nullable=True)  # connection, payment, technical, other
    admin_response = Column(Text, nullable=True)
    admin_id = Column(Integer, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Связь с пользователем
    user = relationship("User", backref="support_tickets")
    
    def __repr__(self):
        return f"<SupportTicket(ticket_number={self.ticket_number}, status={self.status})>"

class SupportMessage(BaseModel):
    __tablename__ = "support_messages"
    
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null если от админа
    admin_id = Column(Integer, nullable=True)  # ID админа если сообщение от админа
    message = Column(Text, nullable=False)
    is_from_admin = Column(Boolean, default=False)
    
    # Связи
    ticket = relationship("SupportTicket", backref="messages")
    user = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self):
        sender = "Admin" if self.is_from_admin else "User"
        return f"<SupportMessage(ticket_id={self.ticket_id}, from={sender})>" 