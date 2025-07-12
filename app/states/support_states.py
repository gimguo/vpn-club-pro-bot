from aiogram.fsm.state import State, StatesGroup

class SupportStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_message = State()
    waiting_for_admin_response = State() 