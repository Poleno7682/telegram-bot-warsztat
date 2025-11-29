"""Callback utilities - Helper functions for parsing callback data"""

from typing import Optional


def parse_callback_data(
    callback_data: Optional[str],
    expected_prefix: str,
    index: int = 2
) -> Optional[int]:
    """
    Parse callback data and extract ID from specified index.
    
    This utility eliminates repetitive callback parsing logic across handlers.
    
    Args:
        callback_data: Callback data string (e.g., "booking:accept:123")
        expected_prefix: Expected prefix (e.g., "booking:accept")
        index: Index in split array to extract ID from (default: 2)
               For "booking:accept:123", index 2 would be "123"
        
    Returns:
        Extracted ID as integer, or None if parsing failed
        
    Example:
        >>> callback_data = "booking:accept:123"
        >>> booking_id = parse_callback_data(callback_data, "booking:accept")
        >>> # Returns: 123
        >>> 
        >>> callback_data = "service:edit:456"
        >>> service_id = parse_callback_data(callback_data, "service:edit", index=2)
        >>> # Returns: 456
    """
    if not callback_data:
        return None
    
    if not callback_data.startswith(expected_prefix):
        return None
    
    try:
        parts = callback_data.split(":")
        if len(parts) > index:
            return int(parts[index])
    except (ValueError, IndexError):
        pass
    
    return None


def validate_callback_data(
    callback_data: Optional[str],
    expected_prefix: str
) -> bool:
    """
    Validate that callback data has the expected prefix.
    
    Args:
        callback_data: Callback data string
        expected_prefix: Expected prefix to check
        
    Returns:
        True if callback_data starts with expected_prefix, False otherwise
        
    Example:
        >>> if validate_callback_data(callback.data, "booking:"):
        ...     # Handle booking callback
    """
    if not callback_data:
        return False
    
    return callback_data.startswith(expected_prefix)

