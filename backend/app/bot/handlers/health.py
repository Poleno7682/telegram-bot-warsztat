"""Health check handler"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message as TelegramMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import get_metrics_collector
from app.core.logging_config import get_logger
from app.config.database import AsyncSessionLocal

router = Router(name="health")
logger = get_logger(__name__)


@router.message(Command("health"))
async def cmd_health(message: TelegramMessage, session: AsyncSession):
    """
    Health check command - returns system status and metrics
    
    Args:
        message: Message from user
        session: Database session
    """
    try:
        # Check database connection
        async with AsyncSessionLocal() as test_session:
            await test_session.execute("SELECT 1")
        db_status = "OK"
    except Exception as e:
        db_status = f"ERROR: {e}"
        logger.error("Database health check failed", error=str(e), exc_info=True)
    
    # Get metrics
    metrics = get_metrics_collector()
    metrics_data = await metrics.get_metrics()
    
    # Format response
    response = f"""🏥 <b>System Health Check</b>

📊 <b>Database:</b> {db_status}

📈 <b>Metrics:</b>
"""
    
    if metrics_data["counters"]:
        response += "\n<b>Counters:</b>\n"
        for name, value in sorted(metrics_data["counters"].items()):
            response += f"  • {name}: {value}\n"
    
    if metrics_data["gauges"]:
        response += "\n<b>Gauges:</b>\n"
        for name, value in sorted(metrics_data["gauges"].items()):
            response += f"  • {name}: {value}\n"
    
    if not metrics_data["counters"] and not metrics_data["gauges"]:
        response += "  No metrics collected yet\n"
    
    await message.answer(response, parse_mode="HTML")
    
    # Record health check metric
    await metrics.increment("health.checks")

