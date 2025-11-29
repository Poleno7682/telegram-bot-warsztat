"""Utility for updating .env file with new settings values"""

import re
from pathlib import Path
from typing import Optional
from datetime import time

from app.config.settings import get_settings


def update_env_file(
    default_time_step: Optional[int] = None,
    default_buffer_time: Optional[int] = None,
    default_work_start: Optional[str] = None,
    default_work_end: Optional[str] = None,
    timezone: Optional[str] = None
) -> bool:
    """
    Update .env file with new settings values
    
    Args:
        default_time_step: New DEFAULT_TIME_STEP value
        default_buffer_time: New DEFAULT_BUFFER_TIME value
        default_work_start: New DEFAULT_WORK_START value (format: "HH:MM")
        default_work_end: New DEFAULT_WORK_END value (format: "HH:MM")
        timezone: New TIMEZONE value
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        # Get .env file path - it's in project root (parent of backend directory)
        # The path in Settings.model_config is: backend/.env relative to backend
        # So we need to go to project root
        backend_dir = Path(__file__).resolve().parent.parent.parent
        project_root = backend_dir.parent
        env_file_path = project_root / ".env"
        
        # Read current .env file
        if not env_file_path.exists():
            # If .env doesn't exist, create it with default values
            env_content = ""
        else:
            env_content = env_file_path.read_text(encoding="utf-8")
        
        # Update values
        updates = {}
        if default_time_step is not None:
            updates["DEFAULT_TIME_STEP"] = str(default_time_step)
        if default_buffer_time is not None:
            updates["DEFAULT_BUFFER_TIME"] = str(default_buffer_time)
        if default_work_start is not None:
            updates["DEFAULT_WORK_START"] = default_work_start
        if default_work_end is not None:
            updates["DEFAULT_WORK_END"] = default_work_end
        if timezone is not None:
            updates["TIMEZONE"] = timezone
        
        # Update or add each variable
        # Split into lines preserving line endings
        if not env_content:
            lines = []
        else:
            # Split by newlines but preserve them
            lines = env_content.splitlines(True)  # keepends=True
            # If file doesn't end with newline, last line won't have it
            if lines and not env_content.endswith("\n"):
                lines[-1] = lines[-1].rstrip("\n")
        
        updated_keys = set()
        
        # Process existing lines
        for i, line in enumerate(lines):
            # Skip comments and empty lines
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            
            # Check if this line contains a variable we want to update
            for key, value in updates.items():
                # Match pattern: KEY = value or KEY=value (with optional spaces)
                pattern = rf"^{re.escape(key)}\s*=\s*.*"
                if re.match(pattern, stripped):
                    # Replace the line, preserve original line ending style
                    line_ending = "\n" if line.endswith("\n") else ""
                    lines[i] = f"{key}={value}{line_ending}"
                    updated_keys.add(key)
                    break
        
        # Add missing variables at the end
        for key, value in updates.items():
            if key not in updated_keys:
                # Add new variable at the end
                if lines and not (lines[-1].endswith("\n") or lines[-1].endswith("\r\n")):
                    lines.append("\n")
                lines.append(f"{key}={value}\n")
        
        # Reconstruct content
        env_content = "".join(lines)
        
        # Write back to file
        env_file_path.write_text(env_content, encoding="utf-8")
        return True
        
    except Exception as e:
        # Log error but don't fail
        import structlog
        logger = structlog.get_logger()
        logger.error("Failed to update .env file", error=str(e), exc_info=True)
        return False


def update_env_from_settings(settings) -> bool:
    """
    Update .env file from SystemSettings instance
    
    Args:
        settings: SystemSettings instance
        
    Returns:
        True if update was successful, False otherwise
    """
    return update_env_file(
        default_time_step=settings.time_step_minutes,
        default_buffer_time=settings.buffer_time_minutes,
        default_work_start=settings.work_start_time.strftime("%H:%M"),
        default_work_end=settings.work_end_time.strftime("%H:%M"),
        timezone=settings.timezone
    )

