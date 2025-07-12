from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from .base import BaseModel

class Subscription(BaseModel):
    __tablename__ = "subscriptions"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    outline_key_id = Column(String(255), nullable=False)
    outline_server_url = Column(String(500), nullable=False)
    access_url = Column(Text, nullable=False)  # ss:// ключ
    
    tariff_type = Column(String(50), nullable=False)  # trial, monthly, quarterly, etc.
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    traffic_limit_gb = Column(Integer, nullable=True)  # Лимит трафика в ГБ (для пробного)
    traffic_used_gb = Column(Integer, default=0)
    
    is_active = Column(Boolean, default=True)
    
    # Relationship
    user = relationship("User", backref="subscriptions")
    
    def __repr__(self):
        return f"<Subscription(user_id={self.user_id}, tariff={self.tariff_type}, active={self.is_active})>" 