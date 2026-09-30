"""
Logging configuration for KRT Bookings Tracker Agent.
Writes logs to ~/.krt_bookings_tracker/agent.log and stderr.
"""
import sys
import logging
import traceback
from agent.config import LOGS_FILE_PATH

# Create logger
logger = logging.getLogger("krt_agent")
logger.setLevel(logging.DEBUG)

# File handler
file_handler = logging.FileHandler(LOGS_FILE_PATH, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler (if running in terminal)
if sys.stderr:
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def handle_exception(exc_type, exc_value, exc_traceback):
    """Logs any uncaught exception globally."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception
