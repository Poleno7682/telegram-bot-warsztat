"""Admin router aggregator."""

from aiogram import Router

from app.bot.middlewares.admin_auth import AdminAuthMiddleware

from . import mechanics, services, settings, users

router = Router(name="admin")

# Gate every admin sub-router behind an explicit ADMIN role check. Without
# this, AuthMiddleware only verifies the user has *some* role - any
# authorized user could invoke admin:* callback_data directly.
router.message.middleware(AdminAuthMiddleware())
router.callback_query.middleware(AdminAuthMiddleware())

router.include_router(users.router)
router.include_router(mechanics.router)
router.include_router(services.router)
router.include_router(settings.router)

__all__ = ["router", "users", "mechanics", "services", "settings"]

