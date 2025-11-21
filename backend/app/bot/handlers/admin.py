"""Admin handlers - user and service management"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.repositories.service import ServiceRepository
from app.bot.states.booking import AddServiceStates, UserManagementStates

router = Router(name="admin")


@router.callback_query(F.data == "admin:manage_users")
async def manage_users_menu(callback: CallbackQuery, _: callable):
    """Show user management menu"""
    # Implementation for user management
    await callback.message.edit_text(
        _("user_management.add_user") + "\n" +
        _("user_management.remove_user")
    )
    await callback.answer()


@router.callback_query(F.data == "admin:manage_services")
async def manage_services_menu(
    callback: CallbackQuery,
    session: AsyncSession,
    _: callable
):
    """Show services management menu"""
    service_repo = ServiceRepository(session)
    services = await service_repo.get_all_active()
    
    text = _("service_management.title") + "\n\n"
    
    if services:
        for service in services:
            text += f"• {service.name_pl} / {service.name_ru} ({service.duration_minutes} min)\n"
    else:
        text += _("service_management.no_services")
    
    await callback.message.edit_text(text)
    await callback.answer()


# Placeholder for other admin functions
# In a full implementation, add:
# - Add/remove users
# - Add/edit/remove services
# - Update system settings
# - View statistics

