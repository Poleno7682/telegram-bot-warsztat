"""Validation utilities - Helper functions for data validation"""

from typing import Optional, Tuple


def validate_phone(phone: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format.
    
    Currently accepts only digits. Returns cleaned phone number if valid.
    
    Args:
        phone: Phone number string to validate
        
    Returns:
        Tuple of (is_valid: bool, cleaned_phone: Optional[str])
        - If valid: (True, cleaned_phone_number)
        - If invalid: (False, None)
        
    Example:
        >>> is_valid, phone = validate_phone("123456789")
        >>> if is_valid:
        ...     use_phone(phone)
    """
    if not phone:
        return False, None
    
    phone = phone.strip()
    
    # Currently only digits are allowed
    if not phone or not phone.isdigit():
        return False, None
    
    return True, phone


def validate_telegram_id(telegram_id: str) -> Tuple[bool, Optional[int]]:
    """
    Validate and parse Telegram ID from string.
    
    Args:
        telegram_id: Telegram ID as string
        
    Returns:
        Tuple of (is_valid: bool, parsed_id: Optional[int])
        - If valid: (True, telegram_id_as_int)
        - If invalid: (False, None)
        
    Example:
        >>> is_valid, tid = validate_telegram_id("12345")
        >>> if is_valid:
        ...     user = await get_user(tid)
    """
    if not telegram_id:
        return False, None
    
    telegram_id = telegram_id.strip()
    
    try:
        parsed_id = int(telegram_id)
        # Telegram IDs are positive integers
        if parsed_id > 0:
            return True, parsed_id
    except ValueError:
        pass
    
    return False, None

