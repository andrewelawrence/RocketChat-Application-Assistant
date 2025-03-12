# config.py

import os, logging
from logging.handlers import TimedRotatingFileHandler

# Log directory setup
_LOG_DIR = os.environ.get("logDir")  # Directory where logs are stored
_DEFAULT_PATH = os.path.join(_LOG_DIR, "app.log")  # Default log file path
_KOYEB = os.environ.get("koyebAppId") not in (None, "None")  # Detects if running in Koyeb environment

# Configure the root logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-10s | %(name)-10s -- %(message)s",
    handlers=[
        # If running in Koyeb, log to stdout; otherwise, log to rotating files
        logging.StreamHandler() if _KOYEB else TimedRotatingFileHandler(_DEFAULT_PATH, when="midnight", interval=1, backupCount=7)
    ]
)

def get_logger(name: str, uid: str = None, stdout: bool = False) -> logging.Logger:
    """
    Creates and returns a logger instance.

    This function configures loggers based on the execution environment:
    - If running in **Koyeb** (`koyebAppId` is set), logs are sent to stdout.
    - If **not** in Koyeb, logs are written to a rotating log file (`app.log`).
    - If a **user ID (`uid`)** is provided and not running in Koyeb, it logs to a per-user log file (`user_{uid}.log`).

    Args:
        name (str): The name of the logger (typically `__name__` of the calling module).
        uid (str, optional): User ID for logging per-user logs (default: `None`).
        stdout (bool, optional): If `True`, logs to stdout even if not in Koyeb (default: `False`).

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)

    if uid and not _KOYEB:
        user_log_path = os.path.join(_LOG_DIR, f"user_{uid}.log")
        user_handler = TimedRotatingFileHandler(user_log_path, when="midnight", interval=1, backupCount=7)
        user_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
        logger.addHandler(user_handler)
        
    return logger
