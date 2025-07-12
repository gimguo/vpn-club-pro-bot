from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from .base import BaseModel

class TelegramPayment(BaseModel):
    __tablename__ = "telegram_payments"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_payment_charge_id = Column(String(255), unique=True, nullable=False)
    
    # Детали платежа
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="XTR")  # XTR для Telegram Stars, USD для карт
    tariff_type = Column(String(50), nullable=False)
    
    # Тип платежа
    payment_type = Column(String(20), nullable=False)  # "stars" или "card"
    
    # Статус
    status = Column(String(50), default="pending")  # pending, succeeded, canceled
    
    # Данные от Telegram
    provider_payment_charge_id = Column(String(255), nullable=True)  # ID от платежного провайдера
    telegram_user_id = Column(String(50), nullable=False)
    
    # Дополнительные данные
    invoice_payload = Column(Text, nullable=True)  # Payload для идентификации платежа
    order_info = Column(Text, nullable=True)  # Дополнительная информация о заказе
    
    # Relationship
    user = relationship("User", backref="telegram_payments")
    
    def __repr__(self):
        return f"<TelegramPayment(user_id={self.user_id}, amount={self.amount}, type={self.payment_type}, status={self.status})>" 