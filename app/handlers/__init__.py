from .start import register_start_handlers
from .tariffs import register_tariff_handlers
from .common import register_common_handlers
from .payments import register_payment_handlers
from .admin import register_admin_handlers
from .support import register_support_handlers

def register_all_handlers(dp):
    """Регистрация всех обработчиков"""
    register_start_handlers(dp)
    register_tariff_handlers(dp)
    register_payment_handlers(dp)
    register_common_handlers(dp)
    register_admin_handlers(dp)
    register_support_handlers(dp) 