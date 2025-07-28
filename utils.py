"""Utility functions for the Mercy Tracker Bot"""

from config import (
    MAX_AMOUNT_PER_COMMAND, 
    MIN_AMOUNT_PER_COMMAND,
    PROGRESS_BAR_LENGTH,
    PROGRESS_EMPTY_CHAR,
    PROGRESS_FILLED_CHAR
)

def validate_amount(amount):
    """Validate if the amount is within acceptable range"""
    return isinstance(amount, int) and MIN_AMOUNT_PER_COMMAND <= amount <= MAX_AMOUNT_PER_COMMAND

def format_progress_bar(progress, length=None):
    """Create a visual progress bar"""
    if length is None:
        length = PROGRESS_BAR_LENGTH
    
    # Ensure progress is between 0 and 1
    progress = max(0, min(1, progress))
    
    filled_length = int(length * progress)
    empty_length = length - filled_length
    
    bar = PROGRESS_FILLED_CHAR * filled_length + PROGRESS_EMPTY_CHAR * empty_length
    percentage = int(progress * 100)
    
    return f"{bar} {percentage}%"

def format_number_with_commas(number):
    """Format large numbers with commas for readability"""
    return f"{number:,}"

def calculate_percentage(current, total):
    """Calculate percentage with safety check for division by zero"""
    if total == 0:
        return 0
    return (current / total) * 100

def truncate_text(text, max_length=100):
    """Truncate text if it exceeds max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

def sanitize_input(text):
    """Basic input sanitization"""
    if not isinstance(text, str):
        return str(text)
    
    # Remove any potentially harmful characters
    sanitized = text.strip()
    # Remove any markdown that could break formatting
    sanitized = sanitized.replace('`', '').replace('*', '').replace('_', '')
    
    return sanitized

def format_time_ago(timestamp):
    """Format timestamp to human readable 'time ago' format"""
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc)
    diff = now - timestamp
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

def get_rarity_emoji(rarity):
    """Get emoji for different rarities"""
    rarity_emojis = {
        "legendary": "🟡",
        "mythical": "🔴",
        "epic": "🟣",
        "rare": "🔵",
        "uncommon": "🟢",
        "common": "⚪"
    }
    return rarity_emojis.get(rarity.lower(), "⚫")

def get_shard_emoji(shard_type):
    """Get emoji for different shard types"""
    shard_emojis = {
        "ancient": "🔵",
        "void": "🟣",
        "sacred": "🟡",
        "primal": "🔴",
        "remnant": "⚫"
    }
    return shard_emojis.get(shard_type.lower(), "🔘")

def format_shard_type(shard_type):
    """Format shard type with proper capitalization"""
    return shard_type.title()

def validate_user_id(user_id):
    """Validate Discord user ID format"""
    if not isinstance(user_id, (str, int)):
        return False
    
    try:
        user_id_int = int(user_id)
        # Discord user IDs are 17-19 digits long
        return 10**16 <= user_id_int <= 10**19
    except (ValueError, TypeError):
        return False

def safe_divide(numerator, denominator, default=0):
    """Safe division that handles division by zero"""
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ValueError):
        return default
