"""FSM States for booking flow"""

from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    """States for creating a new booking"""
    
    # Service selection
    selecting_service = State()
    
    # Date and time selection
    selecting_date = State()
    selecting_time = State()
    
    # Car information
    entering_car_brand = State()
    entering_car_model = State()
    entering_car_number = State()
    
    # Client information
    entering_client_name = State()
    entering_client_phone = State()
    
    # Description
    entering_description = State()
    
    # Confirmation
    confirming = State()


class AddServiceStates(StatesGroup):
    """States for adding a new service"""
    
    entering_name_pl = State()
    entering_name_ru = State()
    entering_duration = State()
    entering_price = State()


class SettingsStates(StatesGroup):
    """States for updating settings"""
    
    updating_work_start = State()
    updating_work_end = State()
    updating_time_step = State()
    updating_buffer_time = State()


class UserManagementStates(StatesGroup):
    """States for user management"""
    
    adding_user = State()
    adding_mechanic = State()
    removing_user = State()
    removing_mechanic = State()

