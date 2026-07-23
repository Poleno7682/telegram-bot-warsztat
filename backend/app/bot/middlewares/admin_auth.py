"""Admin-only authorization middleware"""

from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from app.models.user import User, UserRole
from app.core.i18n import get_text


class AdminAuthMiddleware(BaseMiddleware):
    """Restricts access to the admin router to users with UserRole.ADMIN.

    Attach this only to the admin router (not the dispatcher-wide chain),
    so it runs after AuthMiddleware has already populated data["user"] for
    any authorized user (admin/mechanic/user). Without this, any
    authorized user could trigger admin callback_data directly - the
    admin keyboard hiding those buttons was the only protection.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: Optional[User] = data.get("user")

        if user is None or user.role != UserRole.ADMIN:
            # Same message/UX as AuthMiddleware's "unauthorized" case, so a
            # non-admin can't distinguish "not authorized at all" from
            # "authorized but not an admin".
            message_text = get_text("start.unauthorized_both", "pl")

            if isinstance(event, Message):
                await event.answer(message_text)
            elif isinstance(event, CallbackQuery):
                if isinstance(event.message, Message):
                    await event.message.answer(message_text)
                await event.answer()

            return None

        return await handler(event, data)
