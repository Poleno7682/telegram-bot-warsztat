"""Logging configuration using structlog with JSON format and contextvars"""

import sys
import logging
from typing import Any
import structlog
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
    merge_contextvars
)


def configure_logging(log_level: str = "INFO", json_format: bool = True) -> None:
    """
    Configure structlog with JSON format and contextvars
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Whether to use JSON format (True) or human-readable (False)
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    
    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,  # Merge contextvars
        structlog.stdlib.add_log_level,  # Add log level
        structlog.stdlib.add_logger_name,  # Add logger name
        structlog.processors.TimeStamper(fmt="iso"),  # ISO timestamp
        structlog.processors.StackInfoRenderer(),  # Stack info
        structlog.processors.format_exc_info,  # Exception formatting
    ]
    
    if json_format:
        # JSON format for production
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable format for development
        processors.append(
            structlog.dev.ConsoleRenderer(colors=True)
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a structlog logger instance
    
    Args:
        name: Logger name (default: calling module name)
        
    Returns:
        Configured structlog logger
    """
    if name is None:
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "app")
    
    return structlog.get_logger(name)


# Context management helpers
def set_log_context(**kwargs: Any) -> None:
    """
    Set context variables for logging
    
    Args:
        **kwargs: Context variables to set
    """
    bind_contextvars(**kwargs)


def clear_log_context() -> None:
    """Clear all context variables"""
    clear_contextvars()


def get_log_context() -> dict[str, Any]:
    """
    Get current context variables
    
    Returns:
        Dictionary of context variables
    """
    return dict(get_contextvars())

