"""Password validation utilities."""

import re


def validate_password(password: str) -> tuple[bool, str | None]:
    """
    Validate password against MVP security policy.
    
    Requirements:
    - Minimum 10 characters
    - Maximum 128 characters
    - At least one letter (a-z, A-Z)
    - At least one number (0-9)
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"
    
    if len(password) < 10:
        return False, "Password must be at least 10 characters long"
    
    if len(password) > 128:
        return False, "Password must be at most 128 characters long"
    
    if not re.search(r"[a-zA-Z]", password):
        return False, "Password must contain at least one letter"
    
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number"
    
    return True, None
