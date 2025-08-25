import re
import random
import datetime



# --- Helper Functions from the original code ---
def is_valid_email(email):
    """Check if email format is valid"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def check_password_strength(password):
    """Check password strength and return validation result"""
    if len(password) < 8:
        return False, " Password must be at least 8 characters long"
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    if not has_upper:
        return False, " Password must contain at least one uppercase letter"
    if not has_lower:
        return False, " Password must contain at least one lowercase letter"
    if not has_digit:
        return False, " Password must contain at least one number"
    if not has_special:
        return False, " Password must contain at least one special character (!@#$%^&*)"
    
    return True, " Password strength is good!"


def get_password_strength_score(password):
    """Get password strength score from 0-5"""
    if not password:
        return 0
    
    score = 0
    if len(password) >= 8:
        score += 1
    if any(c.islower() for c in password):
        score += 1
    if any(c.isupper() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(c in '!@#$%^&*()-_=+[{]}\\|;:",<.>/?' for c in password):
        score += 1
    
    return score