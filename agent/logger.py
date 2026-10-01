"""
Logging configuration for KRT Bookings Tracker Agent.
Writes logs to ~/.krt_bookings_tracker/agent.log and stderr.
"""
import sys
import logging
import traceback
from agent.config import LOGS_FILE_PATH

class NullStream:
    """Null stream fallback when sys.stderr/sys.stdout are None in windowed apps."""
    def write(self, *args, **kwargs):
        pass
    def flush(self, *args, **kwargs):
        pass

if sys.stderr is None:
    sys.stderr = NullStream()
if sys.stdout is None:
    sys.stdout = NullStream()

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
if hasattr(sys, "stderr") and sys.stderr and not isinstance(sys.stderr, NullStream):
    try:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    except Exception:
        pass

def handle_exception(exc_type, exc_value, exc_traceback):
    """Logs any uncaught exception globally."""
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        return
    logger.critical("Uncaught exception in sys.excepthook:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

# Handle thread exceptions (Python 3.8+)
import threading
def handle_thread_exception(args):
    if issubclass(args.exc_type, (KeyboardInterrupt, SystemExit)):
        return
    logger.critical(f"Uncaught exception in thread {args.thread.name}:", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

if hasattr(threading, "excepthook"):
    threading.excepthook = handle_thread_exception

# Handle unraisable exceptions
def handle_unraisable(unraisable):
    if issubclass(unraisable.exc_type, (KeyboardInterrupt, SystemExit)):
        return
    logger.warning(f"Unraisable exception: {unraisable.err_msg}", exc_info=(unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback))

if hasattr(sys, "unraisablehook"):
    sys.unraisablehook = handle_unraisable

