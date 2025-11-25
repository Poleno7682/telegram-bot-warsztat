"""Admin router aggregator."""

from aiogram import Router

from . import mechanics, services, settings, users

router = Router(name="admin")
router.include_router(users.router)
router.include_router(mechanics.router)
router.include_router(services.router)
router.include_router(settings.router)

__all__ = ["router", "users", "mechanics", "services", "settings"]

