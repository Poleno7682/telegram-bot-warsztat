"""Regression tests for AdminAuthMiddleware.

Covers 0.3 from docs/REFACTORING_PLAN_2026-07.md: AuthMiddleware only
checked "has some role" (admin/mechanic/user), not specifically ADMIN, so
any authorized user could trigger admin:* callback_data directly since
nothing but the keyboard's button visibility stood in the way.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.middlewares.admin_auth import AdminAuthMiddleware
from app.models.user import User, UserRole


def make_user(role: UserRole) -> User:
    return User(id=1, telegram_id=999, first_name="Test", role=role, is_active=True)


@pytest.fixture
def middleware() -> AdminAuthMiddleware:
    return AdminAuthMiddleware()


@pytest.fixture
def handler() -> AsyncMock:
    return AsyncMock(return_value="handled")


class TestAdminAuthMiddleware:
    async def test_admin_passes_through(self, middleware, handler):
        event = MagicMock()
        data = {"user": make_user(UserRole.ADMIN)}

        result = await middleware(handler, event, data)

        assert result == "handled"
        handler.assert_awaited_once_with(event, data)

    @pytest.mark.parametrize("role", [UserRole.MECHANIC, UserRole.USER])
    async def test_non_admin_message_is_blocked(self, middleware, handler, role):
        from aiogram.types import Message

        event = MagicMock(spec=Message)
        event.answer = AsyncMock()
        data = {"user": make_user(role)}

        result = await middleware(handler, event, data)

        assert result is None
        handler.assert_not_awaited()
        event.answer.assert_awaited_once()

    async def test_non_admin_callback_is_blocked_and_answered(self, middleware, handler):
        from aiogram.types import CallbackQuery, Message

        inner_message = MagicMock(spec=Message)
        inner_message.answer = AsyncMock()

        event = MagicMock(spec=CallbackQuery)
        event.message = inner_message
        event.answer = AsyncMock()
        data = {"user": make_user(UserRole.USER)}

        result = await middleware(handler, event, data)

        assert result is None
        handler.assert_not_awaited()
        inner_message.answer.assert_awaited_once()
        event.answer.assert_awaited_once()

    async def test_missing_user_is_blocked(self, middleware, handler):
        from aiogram.types import Message

        event = MagicMock(spec=Message)
        event.answer = AsyncMock()
        data = {}

        result = await middleware(handler, event, data)

        assert result is None
        handler.assert_not_awaited()
