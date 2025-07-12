from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .base import BaseModel

class Payment(BaseModel):
    __tablename__ = "payments"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    yookassa_payment_id = Column(String(255), unique=True, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="RUB")
    tariff_type = Column(String(50), nullable=False)
    
    status = Column(String(50), default="pending")  # pending, succeeded, canceled
    payment_url = Column(String(1000), nullable=True)
    
    # Relationship
    user = relationship("User", backref="payments")
    
    def __repr__(self):
        return f"<Payment(user_id={self.user_id}, amount={self.amount}, status={self.status})>" 