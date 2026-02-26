from sqlalchemy import Column, Integer, String, Boolean, BigInteger, ForeignKey, DateTime
from .base import BaseModel

class User(BaseModel):
    __tablename__ = "users"
    
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), nullable=True)
    email = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    is_trial_used = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Legal consent (ФЗ-152)
    terms_accepted = Column(Boolean, default=False)
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)
    pd_consent = Column(Boolean, default=False)          # Отдельное согласие на обработку ПД (ст.9 ФЗ-152)
    pd_consent_at = Column(DateTime(timezone=True), nullable=True)

    # Referral system
    referral_code = Column(String(20), unique=True, nullable=True, index=True)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    referral_bonus_days = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>" 