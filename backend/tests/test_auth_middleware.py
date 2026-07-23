"""Regression tests for AuthMiddleware.

Covers 1.4 from docs/REFACTORING_PLAN_2026-07.md: the unauthorized-user
branch called `event.message.answer(...)` unconditionally for CallbackQuery
events. CallbackQuery.message is Optional[Message | InaccessibleMessage] -
it can be None (e.g. a callback from an inline-mode result with no
underlying chat message), which has no .answer() and would raise
AttributeError. InaccessibleMessage *does* support .answer() (it only needs
.chat.id), so that case should still get a reply - only the None case
should be skipped.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.middlewares.auth import AuthMiddleware


@pytest.fixture
def middleware() -> AuthMiddleware:
    return AuthMiddleware()


@pytest.fixture
def handler() -> AsyncMock:
    return AsyncMock(return_value="handled")


def patch_unauthorized(monkeypatch):
    mock_auth_service = MagicMock()
    mock_auth_service.is_authorized = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "app.bot.middlewares.auth.AuthService",
        MagicMock(return_value=mock_auth_service),
    )


class TestAuthMiddlewareUnauthorizedCallback:
    async def test_inaccessible_message_still_gets_answered(self, middleware, handler, monkeypatch):
        from aiogram.types import CallbackQuery, InaccessibleMessage

        patch_unauthorized(monkeypatch)

        inaccessible = MagicMock(spec=InaccessibleMessage)
        inaccessible.answer = AsyncMock()

        event = MagicMock(spec=CallbackQuery)
        event.from_user = MagicMock(id=42)
        event.message = inaccessible
        event.answer = AsyncMock()
        data = {"session": MagicMock()}

        result = await middleware(handler, event, data)

        assert result is None
        handler.assert_not_awaited()
        inaccessible.answer.assert_awaited_once()
        event.answer.assert_awaited_once()

    async def test_none_message_does_not_raise(self, middleware, handler, monkeypatch):
        from aiogram.types import CallbackQuery

        patch_unauthorized(monkeypatch)

        event = MagicMock(spec=CallbackQuery)
        event.from_user = MagicMock(id=42)
        event.message = None
        event.answer = AsyncMock()
        data = {"session": MagicMock()}

        result = await middleware(handler, event, data)

        assert result is None
        handler.assert_not_awaited()
        event.answer.assert_awaited_once()

    async def test_real_message_gets_answered(self, middleware, handler, monkeypatch):
        from aiogram.types import CallbackQuery, Message

        patch_unauthorized(monkeypatch)

        inner_message = MagicMock(spec=Message)
        inner_message.answer = AsyncMock()

        event = MagicMock(spec=CallbackQuery)
        event.from_user = MagicMock(id=42)
        event.message = inner_message
        event.answer = AsyncMock()
        data = {"session": MagicMock()}

        result = await middleware(handler, event, data)

        assert result is None
        handler.assert_not_awaited()
        inner_message.answer.assert_awaited_once()
        event.answer.assert_awaited_once()
