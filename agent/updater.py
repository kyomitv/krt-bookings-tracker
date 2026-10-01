"""
Automatic Update Manager for KRT Bookings Tracker Agent.
Interacts with GitHub Releases API, checks for newer versions, downloads assets,
and performs safe self-replacement on Windows, Linux, and macOS.
"""
import os
import sys
import re
import time
import json
import tempfile
import subprocess
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import requests

from agent.config import APP_VERSION, GITHUB_REPO, get_executable_path, UPDATER_LOG_PATH
from agent.logger import logger


def parse_version(v_str: str) -> tuple:
    """
    Parses semantic version string (e.g., 'v1.2.3', '1.2.3', 'v2.0.1-beta')
    into a comparable integer tuple.
    """
    if not v_str:
        return (0, 0, 0)
    cleaned = re.sub(r"^[vV]", "", v_str.strip())
    # Extract numbers
    parts = re.split(r"[-+.]", cleaned)
    numeric_parts = []
    for part in parts:
        try:
            numeric_parts.append(int(part))
        except ValueError:
            break
    while len(numeric_parts) < 3:
        numeric_parts.append(0)
    return tuple(numeric_parts[:3])


def is_newer_version(latest_tag: str, current_version: str) -> bool:
    """Returns True if latest_tag represents a strictly higher version than current_version."""
    v_latest = parse_version(latest_tag)
    v_curr = parse_version(current_version)
    return v_latest > v_curr


class ReleaseInfo:
    """Structured container for GitHub Release information."""

    def __init__(self, tag_name: str, name: str, body: str, html_url: str,
                 asset_name: str, download_url: str, asset_size: int, published_at: str):
        self.tag_name = tag_name
        self.version = tag_name.lstrip("vV")
        self.name = name or tag_name
        self.body = body or "Aucune note de version fournie."
        self.html_url = html_url
        self.asset_name = asset_name
        self.download_url = download_url
        self.asset_size = asset_size
        self.published_at = published_at

    def __repr__(self) -> str:
        return f"<ReleaseInfo {self.tag_name} ({self.asset_name})>"


class AutoUpdater:
    """Manages update discovery, background downloads, and binary installation."""

    def __init__(self, repo: str = GITHUB_REPO, current_version: str = APP_VERSION):
        self.repo = repo
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{self.repo}/releases/latest"

    def check_for_update(self) -> Optional[ReleaseInfo]:
        """
        Queries GitHub API for latest published release.
        Returns ReleaseInfo if a newer version is available, else None.
        """
        logger.info(f"[Updater] Checking latest release on GitHub repo: {self.repo}...")
        try:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": f"KRT-Bookings-Tracker/{self.current_version}"
            }
            # Add GitHub token if available in environment for higher rate limit
            token = os.environ.get("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"token {token}"

            resp = requests.get(self.api_url, headers=headers, timeout=10)

            if resp.status_code == 404:
                logger.info(f"[Updater] No releases found in {self.repo} (404).")
                return None
            elif resp.status_code != 200:
                logger.warning(f"[Updater] GitHub API returned status {resp.status_code}: {resp.text}")
                return None

            data = resp.json()
            latest_tag = data.get("tag_name", "")
            if not latest_tag:
                return None

            if not is_newer_version(latest_tag, self.current_version):
                logger.info(f"[Updater] Up to date (current={self.current_version}, latest={latest_tag}).")
                return None

            # Look for the appropriate binary in release assets
            assets = data.get("assets", [])
            target_asset = self._select_asset(assets)

            if not target_asset:
                logger.warning(f"[Updater] Release {latest_tag} found but no matching binary asset.")
                return None

            info = ReleaseInfo(
                tag_name=latest_tag,
                name=data.get("name", latest_tag),
                body=data.get("body", ""),
                html_url=data.get("html_url", ""),
                asset_name=target_asset.get("name", ""),
                download_url=target_asset.get("browser_download_url", ""),
                asset_size=target_asset.get("size", 0),
                published_at=data.get("published_at", ""),
            )
            logger.info(f"[Updater] New update available: {info.tag_name} (Asset: {info.asset_name})")
            return info

        except Exception as e:
            logger.error(f"[Updater] Failed to check for update: {e}")
            return None

    def _select_asset(self, assets: list) -> Optional[Dict[str, Any]]:
        """Selects the asset matching the current OS and binary type."""
        if not assets:
            return None

        # Filter by platform
        is_windows = sys.platform == "win32"
        is_linux = sys.platform.startswith("linux")
        is_darwin = sys.platform == "darwin"

        for asset in assets:
            name = asset.get("name", "").lower()
            if is_windows and name.endswith(".exe"):
                return asset
            if is_linux and ("linux" in name or name.endswith(".bin") or name == "krt-bookings-tracker"):
                return asset
            if is_darwin and ("mac" in name or name.endswith(".dmg") or name.endswith(".app.zip")):
                return asset

        # Default fallback to first asset if only one exists
        if len(assets) == 1:
            return assets[0]

        return None

    def download_update(
        self,
        release_info: ReleaseInfo,
        progress_callback: Optional[Callable[[int, int, float], None]] = None
    ) -> Optional[Path]:
        """
        Downloads the release binary to a temporary file.
        Invokes progress_callback(bytes_downloaded, total_bytes, percent) if provided.
        Returns the Path to the downloaded file.
        """
        try:
            logger.info(f"[Updater] Downloading {release_info.download_url}...")
            temp_dir = Path(tempfile.gettempdir()) / "krt_tracker_updates"
            temp_dir.mkdir(parents=True, exist_ok=True)
            dest_file = temp_dir / release_info.asset_name

            headers = {
                "Accept": "application/octet-stream",
                "User-Agent": f"KRT-Bookings-Tracker/{self.current_version}"
            }
            token = os.environ.get("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"token {token}"

            response = requests.get(release_info.download_url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", release_info.asset_size or 0))
            downloaded = 0
            chunk_size = 64 * 1024 # 64 KB chunks

            with open(dest_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        percent = min(100.0, (downloaded / total_size) * 100.0)
                        progress_callback(downloaded, total_size, percent)

            logger.info(f"[Updater] Download complete: {dest_file} ({downloaded} bytes)")
            return dest_file

        except Exception as e:
            logger.error(f"[Updater] Download failed: {e}")
            return None

    def apply_update_and_restart(self, new_binary_path: Path) -> bool:
        """
        Safely replaces the current executable with the new binary and restarts it.
        Works seamlessly on Windows using an asynchronous detachment script.
        """
        current_exe = Path(get_executable_path()).resolve()
        logger.info(f"[Updater] Applying update to target: {current_exe}")

        if not new_binary_path.exists():
            logger.error(f"[Updater] New binary does not exist: {new_binary_path}")
            return False

        try:
            if sys.platform == "win32":
                pid = os.getpid()
                bat_path = Path(tempfile.gettempdir()) / f"krt_update_swap_{pid}.bat"
                is_frozen = getattr(sys, "frozen", False)

                src_str = str(new_binary_path.resolve())
                dst_str = str(current_exe)
                dst_dir = str(current_exe.parent)
                updater_log_str = str(UPDATER_LOG_PATH.resolve())

                if is_frozen:
                    bat_script = f"""@echo off
setlocal
set "LOGFILE={updater_log_str}"
echo [%date% %time%] [Updater] Starting atomic update swap >> "%LOGFILE%"
echo [%date% %time%] [Updater] Target PID: {pid} >> "%LOGFILE%"
echo [%date% %time%] [Updater] Source binary: {src_str} >> "%LOGFILE%"
echo [%date% %time%] [Updater] Destination: {dst_str} >> "%LOGFILE%"

:: 1. Force kill the running application process tree
echo [%date% %time%] [Updater] Terminating process {pid}... >> "%LOGFILE%"
taskkill /F /T /PID {pid} >> "%LOGFILE%" 2>&1
ping 127.0.0.1 -n 2 >nul

:: 2. Instant atomic rename of existing binary
if exist "{dst_str}.old" del /F /Q "{dst_str}.old" >> "%LOGFILE%" 2>&1
move /Y "{dst_str}" "{dst_str}.old" >> "%LOGFILE%" 2>&1

:: 3. Move new binary into place
move /Y "{src_str}" "{dst_str}" >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo [%date% %time%] [Updater] Move failed, attempting copy fallback... >> "%LOGFILE%"
    copy /Y "{src_str}" "{dst_str}" >> "%LOGFILE%" 2>&1
) else (
    echo [%date% %time%] [Updater] Binary swapped successfully >> "%LOGFILE%"
)

:: 4. Completely clear PyInstaller and Python environment variables
set _MEIPASS2=
set _MEIPASS=
set PYTHONHOME=
set PYTHONPATH=

:: 5. Launch updated application in a clean independent process
cd /d "{dst_dir}"
echo [%date% %time%] [Updater] Launching updated application: {dst_str} >> "%LOGFILE%"
start "" "{dst_str}"
echo [%date% %time%] [Updater] Update process finished successfully >> "%LOGFILE%"

:: 6. Cleanup
ping 127.0.0.1 -n 3 >nul
del /F /Q "{dst_str}.old" >> "%LOGFILE%" 2>&1
(goto) 2>nul & del /F /Q "%~f0"
"""
                else:
                    bat_script = f"""@echo off
setlocal
set "LOGFILE={updater_log_str}"
echo [%date% %time%] [Updater] Starting dev mode launch >> "%LOGFILE%"
taskkill /F /T /PID {pid} >> "%LOGFILE%" 2>&1
ping 127.0.0.1 -n 2 >nul
set _MEIPASS2=
set _MEIPASS=
cd /d "{dst_dir}"
start "" "{src_str}"
(goto) 2>nul & del /F /Q "%~f0"
"""

                bat_path.write_text(bat_script, encoding="cp1252", errors="ignore")
                logger.info(f"[Updater] Spawned updater script: {bat_path}")

                env = os.environ.copy()
                env.pop("_MEIPASS2", None)
                env.pop("_MEIPASS", None)
                subprocess.Popen(
                    ["cmd.exe", "/c", str(bat_path)],
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    close_fds=True
                )
                return True

            else:
                # Linux / macOS: Replace binary and make executable
                import stat
                import shutil

                # Backup or directly overwrite
                shutil.copy2(new_binary_path, current_exe)
                current_exe.chmod(current_exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

                subprocess.Popen([str(current_exe)], start_new_session=True)
                return True

        except Exception as e:
            logger.error(f"[Updater] Failed to apply update and restart: {e}")
            return False
