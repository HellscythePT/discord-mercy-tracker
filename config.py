"""Configuration settings for the Mercy Tracker Bot"""

# Valid shard types supported by the bot
VALID_SHARD_TYPES = ["ancient", "void", "sacred", "primal", "primal_legendary", "primal_mythical", "remnant"]

# Maximum amount that can be added in a single command
MAX_AMOUNT_PER_COMMAND = 500

# Minimum amount that can be added in a single command
MIN_AMOUNT_PER_COMMAND = 1

# Data file settings
DATA_FILE = "user_data.json"
BACKUP_FOLDER = "backups"
MAX_BACKUPS = 10

# Logging settings
LOG_FILE = "bot.log"
LOG_LEVEL = "INFO"

# Discord settings
COMMAND_PREFIX = "!"

# Progress bar settings
PROGRESS_BAR_LENGTH = 10
PROGRESS_EMPTY_CHAR = "▱"
PROGRESS_FILLED_CHAR = "▰"

# Embed colors (hex values)
COLORS = {
    "success": 0x00ff00,
    "error": 0xff0000,
    "warning": 0xffa500,
    "info": 0x0099ff,
    "mercy_active": 0xff6600,
    "mercy_close": 0xffff00,
    "help": 0x00ff99
}

# Rate limiting settings
COMMANDS_PER_MINUTE = 10
COOLDOWN_SECONDS = 3
