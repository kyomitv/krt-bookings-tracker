"""
Cross-platform autostart manager for KRT Agent.
Supports Windows (HKCU Run registry key), Linux (.desktop entry), and macOS (LaunchAgents plist).
"""
import os
import sys
import platform
from pathlib import Path
from agent.config import APP_NAME, APP_ID, get_executable_path

class AutostartManager:
    """Manages system autostart integration across Windows, Linux, and macOS."""

    @staticmethod
    def is_enabled() -> bool:
        """Checks if the agent is registered for automatic startup."""
        system = platform.system()
        try:
            if system == "Windows":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_READ,
                )
                try:
                    winreg.QueryValueEx(key, APP_NAME)
                    winreg.CloseKey(key)
                    return True
                except FileNotFoundError:
                    winreg.CloseKey(key)
                    return False

            elif system == "Linux":
                desktop_file = Path.home() / ".config" / "autostart" / f"{APP_ID}.desktop"
                return desktop_file.exists()

            elif system == "Darwin": # macOS
                plist_file = Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"
                return plist_file.exists()

            return False
        except Exception as e:
            print(f"[Autostart] Check failed: {e}")
            return False

    @staticmethod
    def enable() -> bool:
        """Registers the current executable or script to launch at system startup."""
        system = platform.system()
        exe_path = get_executable_path()
        try:
            if system == "Windows":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_SET_VALUE,
                )
                # If running as raw python script, launch with pythonw.exe if available or python.exe
                if not getattr(sys, "frozen", False):
                    python_exe = sys.executable
                    # replace python.exe with pythonw.exe if existing to avoid terminal window
                    pythonw = python_exe.replace("python.exe", "pythonw.exe")
                    if os.path.exists(pythonw):
                        cmd = f'"{pythonw}" "{exe_path}"'
                    else:
                        cmd = f'"{python_exe}" "{exe_path}"'
                else:
                    cmd = f'"{exe_path}"'

                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                winreg.CloseKey(key)
                print(f"[Autostart] Windows registry startup key registered: {cmd}")
                return True

            elif system == "Linux":
                autostart_dir = Path.home() / ".config" / "autostart"
                autostart_dir.mkdir(parents=True, exist_ok=True)
                desktop_file = autostart_dir / f"{APP_ID}.desktop"

                if getattr(sys, "frozen", False):
                    exec_cmd = f'"{exe_path}"'
                else:
                    exec_cmd = f'"{sys.executable}" "{exe_path}"'

                content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name={APP_NAME}
Comment=KRT Bookings Real-time HR Tracking Agent
Exec={exec_cmd}
Terminal=false
Hidden=false
X-GNOME-Autostart-enabled=true
"""
                with open(desktop_file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[Autostart] Linux desktop autostart entry created: {desktop_file}")
                return True

            elif system == "Darwin": # macOS
                agents_dir = Path.home() / "Library" / "LaunchAgents"
                agents_dir.mkdir(parents=True, exist_ok=True)
                plist_file = agents_dir / f"{APP_ID}.plist"

                if getattr(sys, "frozen", False):
                    program_args = f"<string>{exe_path}</string>"
                else:
                    program_args = f"<string>{sys.executable}</string><string>{exe_path}</string>"

                content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{APP_ID}</string>
    <key>ProgramArguments</key>
    <array>
        {program_args}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
                with open(plist_file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[Autostart] macOS LaunchAgent created: {plist_file}")
                return True

            return False
        except Exception as e:
            print(f"[Autostart] Enable failed: {e}")
            return False

    @staticmethod
    def disable() -> bool:
        """Removes the agent from system startup."""
        system = platform.system()
        try:
            if system == "Windows":
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run",
                    0,
                    winreg.KEY_SET_VALUE,
                )
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
                winreg.CloseKey(key)
                return True

            elif system == "Linux":
                desktop_file = Path.home() / ".config" / "autostart" / f"{APP_ID}.desktop"
                if desktop_file.exists():
                    desktop_file.unlink()
                return True

            elif system == "Darwin":
                plist_file = Path.home() / "Library" / "LaunchAgents" / f"{APP_ID}.plist"
                if plist_file.exists():
                    plist_file.unlink()
                return True

            return False
        except Exception as e:
            print(f"[Autostart] Disable failed: {e}")
            return False
