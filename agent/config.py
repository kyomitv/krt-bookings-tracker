"""
Configuration and constants for KRT Bookings Tracker Agent.
Supports local .env loading for development, GitHub Actions secrets for compilation,
and compiled build config injection.
"""
import os
import sys
from pathlib import Path

# Try to load local .env file if in development mode
def _load_env():
    # Check current directory and project root
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent / ".env",
    ]
    for p in candidates:
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ:
                                os.environ[k] = v
            except Exception:
                pass
            break

_load_env()

# Try to load built-in baked config if generated during PyInstaller build
_BAKED_CONFIG = {}
try:
    from agent._build_config import BAKED_CONFIG as _BAKED_CONFIG
except ImportError:
    pass

# Application metadata
APP_NAME = "KRT Bookings Tracker"
APP_ID = "fr.krt.bookings.tracker"
_RAW_VERSION = os.environ.get("APP_VERSION", _BAKED_CONFIG.get("APP_VERSION", "1.0.6"))
APP_VERSION = _RAW_VERSION.lstrip("vV").strip()
APP_VERSION_DISPLAY = f"v{APP_VERSION}"

# GitHub Repository for Releases & Auto-Update
GITHUB_REPO = os.environ.get(
    "GITHUB_REPO",
    _BAKED_CONFIG.get("GITHUB_REPO", "kyomitv/krt-bookings-tracker")
)
UPDATE_CHECK_ON_STARTUP = True
UPDATE_CHECK_INTERVAL_SECONDS = 14400 # 4 hours

# Web Dashboard / Schedules URL
WEB_SCHEDULES_URL = os.environ.get(
    "WEB_SCHEDULES_URL",
    _BAKED_CONFIG.get("WEB_SCHEDULES_URL", "https://krt-bookings-two.vercel.app/dashboard/team")
)

# Supabase config
SUPABASE_URL = os.environ.get(
    "SUPABASE_URL",
    _BAKED_CONFIG.get("SUPABASE_URL", "")
)
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    _BAKED_CONFIG.get("SUPABASE_ANON_KEY", "")
)

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL_SECONDS = 30

# Local storage path
USER_HOME = Path.home()
APP_DATA_DIR = USER_HOME / ".krt_bookings_tracker"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE_PATH = APP_DATA_DIR / "auth_config.enc"
LOGS_FILE_PATH = APP_DATA_DIR / "agent.log"
UPDATER_LOG_PATH = APP_DATA_DIR / "updater.log"


def get_executable_path() -> str:
    """Returns the path of the current executable or python script."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])
