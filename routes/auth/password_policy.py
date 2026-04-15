"""
Password policy module for EduQuest.
Shared validation used by signup and password reset.
"""

from typing import Tuple

# Minimum password length
MIN_PASSWORD_LENGTH = 10

# Common passwords to reject (short list for v1; expand as needed)
COMMON_PASSWORDS = {
    'password', 'password1', 'password123', '12345678', '123456789', '1234567890',
    'qwerty123', 'letmein', 'welcome', 'admin', 'iloveyou', 'sunshine',
    'princess', 'football', 'abc123', 'monkey', 'dragon', 'master',
    'eduquest', 'eduquest1', 'eduquest123', 'student', 'teacher',
}


def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate a password against the password policy.
    
    Returns:
        (is_valid, error_message)
        - is_valid: True if password meets all requirements
        - error_message: Human-friendly message if invalid, empty string if valid
    """
    if not password:
        return False, "Password is required."
    
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    
    # Check against common passwords (case-insensitive)
    if password.lower() in COMMON_PASSWORDS:
        return False, "This password is too common. Please choose a more unique password."
    
    # Optional: require at least one letter and one number
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    
    if not has_letter or not has_digit:
        return False, "Password must contain at least one letter and one number."
    
    return True, ""


def get_password_requirements() -> dict:
    """
    Return password requirements for frontend display.
    """
    return {
        "min_length": MIN_PASSWORD_LENGTH,
        "requirements": [
            f"At least {MIN_PASSWORD_LENGTH} characters",
            "At least one letter",
            "At least one number",
            "Not a commonly used password"
        ]
    }

