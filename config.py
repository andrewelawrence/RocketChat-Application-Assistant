import logging
import os
from logging.handlers import TimedRotatingFileHandler

# Log directory
_LOG_DIR = os.environ.get("logDir")
_DEFAULT_PATH = os.path.join(_LOG_DIR, "app.log")
_KOYEB = os.environ.get("koyebAppId") not in (None, "None")

# Configure the root logger
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s -- %(message)s",
    handlers=[
        logging.StreamHandler() if _KOYEB else TimedRotatingFileHandler(_DEFAULT_PATH, when="midnight", interval=1, backupCount=7)
    ]
)

def get_logger(name: str, uid: str = None, stdout: bool = False) -> logging.Logger:
    """
    Returns a logger with stdout logging if running in Koyeb, otherwise logs to files.
    - If `koyebAppId` is set and not "None", logs go to stdout.
    - Otherwise, logs are written to `app.log` or per-user logs if `user_id` is provided.
    """
    logger = logging.getLogger(name)

    if uid and not _KOYEB:
        user_log_path = os.path.join(_LOG_DIR, f"user_{uid}.log")
        user_handler = TimedRotatingFileHandler(user_log_path, when="midnight", interval=1, backupCount=7)
        user_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
        logger.addHandler(user_handler)
        
    return logger
