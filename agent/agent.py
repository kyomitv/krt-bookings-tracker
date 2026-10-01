"""
Core Agent Lifecycle and Orchestration for KRT Bookings Tracker.
"""
import sys
import time
import datetime
import threading
import tkinter as tk
from typing import Optional, Dict, Any

from agent.config import (
    APP_NAME, APP_VERSION, APP_VERSION_DISPLAY, HEARTBEAT_INTERVAL_SECONDS,
    UPDATE_CHECK_ON_STARTUP, UPDATE_CHECK_INTERVAL_SECONDS, UPDATER_LOG_PATH,
    get_executable_path
)
from agent.crypto_storage import SecureStorage
from agent.supabase_client import SupabaseClient
from agent.autostart import AutostartManager
from agent.systray_manager import SystrayManager
from agent.updater import AutoUpdater, ReleaseInfo
from agent.ui.login_view import LoginWindow
from agent.ui.startup_modal import StartupModal
from agent.ui.dashboard_view import DashboardWindow
from agent.ui.confirm_modal import ConfirmEndWorkModal
from agent.ui.connection_alert_modal import ConnectionAlertModal
from agent.ui.update_modal import UpdateModal
from agent.ui.theme import apply_window_theme
from agent.logger import logger

class KRTTrackerAgent:
    """Main Agent controller orchestrating UI, Supabase sync, systray, and time tracking."""

    def __init__(self, single_instance_lock=None):
        logger.info("Initializing KRTTrackerAgent instance...")
        self.single_instance_lock = single_instance_lock
        self.client = SupabaseClient(
            on_tokens_updated=lambda data: SecureStorage.save_credentials(data)
        )
        self.updater = AutoUpdater()
        self.systray = SystrayManager(self)
        self.dashboard: Optional[DashboardWindow] = None
        self._update_modal: Optional[UpdateModal] = None
        self._connection_alert_modal: Optional[ConnectionAlertModal] = None
        self._active_modal = None
        self._has_shutdown = False
        self._consecutive_heartbeat_failures = 0

        # Hook single-instance activation callback
        if self.single_instance_lock:
            self.single_instance_lock.set_activate_callback(lambda: self.root.after(0, self.bring_to_front))

        # State variables
        self.status = "idle" # "active", "paused", "personal", "completed", "idle"
        self.current_session_id: Optional[str] = None
        self.session_start_time: Optional[float] = None
        self.start_time_str: Optional[str] = None
        self.estimated_end_time_str: Optional[str] = None
        self.accumulated_seconds: int = 0
        self.last_pause_time: Optional[float] = None
        self.last_heartbeat_time: Optional[float] = None
        self.is_connected = True
        self.today_prior_seconds = 0

        # Background thread control
        self._running = True
        self._heartbeat_thread: Optional[threading.Thread] = None

        # Register shutdown & signal handlers (for automatic session close on PC power off)
        self._setup_shutdown_handlers()

        # Tkinter Root
        self.root = tk.Tk()
        self.root.title("_KRT_INTERNAL_ROOT_")
        self.root.withdraw() # Main root is hidden, child dialogs/dashboard are Toplevels

    def bring_to_front(self):
        """Brings the primary active window to the front cleanly without Win32 hacks."""
        try:
            logger.info("bring_to_front triggered - restoring UI.")
            if self._connection_alert_modal and self._connection_alert_modal.top.winfo_exists():
                self._connection_alert_modal.show()
                return

            if self._update_modal and self._update_modal.top.winfo_exists():
                self._update_modal.top.deiconify()
                self._update_modal.top.lift()
                self._update_modal.top.focus_force()
                return

            if self.dashboard and self.dashboard.top.winfo_exists():
                self.dashboard.show()
                return

            if self._active_modal and hasattr(self._active_modal, "top") and self._active_modal.top.winfo_exists():
                self._active_modal.top.deiconify()
                self._active_modal.top.lift()
                self._active_modal.top.focus_force()
                return

            if self.client.is_authenticated():
                self.show_dashboard()
        except Exception as e:
            logger.warning(f"Error in bring_to_front: {e}")

    def _keepalive(self):
        """Periodic keepalive to ensure Tkinter message loop stays responsive."""
        if self._running and self.root.winfo_exists():
            self.root.after(1000, self._keepalive)

    # ==================== USER & PROFILE ====================

    def get_profile_info(self) -> Dict[str, Any]:
        if self.client.user_profile:
            return self.client.user_profile
        return {"email": "technicien@krt.fr", "role": "technicien"}

    def get_user_display_name(self) -> str:
        prof = self.get_profile_info()
        name = f"{prof.get('first_name', '')} {prof.get('last_name', '')}".strip()
        return name if name else prof.get("email", "Technicien")

    def get_status_display_text(self) -> str:
        if self.status == "active":
            return "🟢 En cours"
        elif self.status == "paused":
            return "🟡 En pause"
        elif self.status == "personal":
            return "☕ Mode Perso"
        return "⚪ Inactif"

    # ==================== TIME CALCULATION ====================

    def get_current_session_seconds(self) -> int:
        if self.status == "active" and self.session_start_time:
            current_run = int(time.time() - self.session_start_time)
            return self.accumulated_seconds + current_run
        return self.accumulated_seconds

    def get_today_total_seconds(self) -> int:
        return self.today_prior_seconds + self.get_current_session_seconds()

    def get_last_heartbeat_ago(self) -> str:
        if not self.last_heartbeat_time:
            return "En attente"
        diff = int(time.time() - self.last_heartbeat_time)
        if diff < 60:
            return f"{diff}s"
        return f"{diff // 60}m"

    # ==================== REMOTE SYNC ====================

    def _sync_session_from_remote(self, session_data: Dict[str, Any]):
        """Synchronizes remote session properties (e.g. started_at modified from web app)."""
        if not session_data:
            return

        remote_started_at = session_data.get("started_at")
        if remote_started_at:
            try:
                clean_str = remote_started_at.replace("Z", "+00:00")
                dt = datetime.datetime.fromisoformat(clean_str).astimezone()
                new_start_str = dt.strftime("%H:%M")
                new_estimated_end = (dt + datetime.timedelta(hours=8, minutes=30)).strftime("%H:%M")

                if new_start_str != self.start_time_str or new_estimated_end != self.estimated_end_time_str:
                    logger.info(f"Detected remote start_at update: {self.start_time_str} -> {new_start_str}")
                    self.start_time_str = new_start_str
                    self.estimated_end_time_str = new_estimated_end

                    # If session is active and user altered start time from web, realign live timer origin
                    if self.status == "active":
                        self.session_start_time = dt.timestamp()
                        self.accumulated_seconds = 0
            except Exception as e:
                logger.warning(f"Error syncing remote started_at: {e}")

    # ==================== WORKFLOW ACTIONS ====================

    def resume_existing_work_session(self, session_data: Dict[str, Any]):
        """Resumes an existing unclosed work session from today."""
        self.current_session_id = session_data.get("id")
        logger.info(f"Resuming existing work session ID: {self.current_session_id}...")
        self.status = "active"
        self.is_connected = True

        remote_started_at = session_data.get("started_at")
        if remote_started_at:
            try:
                clean_str = remote_started_at.replace("Z", "+00:00")
                dt = datetime.datetime.fromisoformat(clean_str).astimezone()
                self.start_time_str = dt.strftime("%H:%M")
                self.estimated_end_time_str = (dt + datetime.timedelta(hours=8, minutes=30)).strftime("%H:%M")
                self.session_start_time = dt.timestamp()
                self.accumulated_seconds = 0
            except Exception as e:
                logger.warning(f"Error parsing started_at in resume: {e}")
                now_dt = datetime.datetime.now()
                self.start_time_str = now_dt.strftime("%H:%M")
                self.estimated_end_time_str = (now_dt + datetime.timedelta(hours=8, minutes=30)).strftime("%H:%M")
                self.session_start_time = time.time()
                self.accumulated_seconds = session_data.get("duration_seconds", 0)
        else:
            now_dt = datetime.datetime.now()
            self.start_time_str = now_dt.strftime("%H:%M")
            self.estimated_end_time_str = (now_dt + datetime.timedelta(hours=8, minutes=30)).strftime("%H:%M")
            self.session_start_time = time.time()
            self.accumulated_seconds = session_data.get("duration_seconds", 0)

        # Notify Supabase of resume
        self.client.resume_session(self.current_session_id)
        self.last_heartbeat_time = time.time()
        self.systray.update_icon()

    def start_work(self):
        """Starts a pro work session with Supabase sync."""
        if self.status == "active":
            return

        logger.info("Starting work session (START_WORK)...")
        self.status = "active"
        self.session_start_time = time.time()
        if not self.start_time_str:
            now_dt = datetime.datetime.now()
            self.start_time_str = now_dt.strftime("%H:%M")
            self.estimated_end_time_str = (now_dt + datetime.timedelta(hours=8, minutes=30)).strftime("%H:%M")

        # Call Supabase
        success, err, session = self.client.start_work_session("work")
        if success and session:
            self.current_session_id = session.get("id")
            self.is_connected = True
            logger.info(f"Active session ID: {self.current_session_id}")
            self._sync_session_from_remote(session)
        else:
            logger.warning(f"Failed to create session on Supabase: {err}")
            self.is_connected = False

        self.last_heartbeat_time = time.time()
        self.systray.update_icon()

    def pause_work(self):
        """Pauses the current pro work session."""
        if self.status != "active":
            return

        logger.info("Pausing work session (PAUSE)...")
        now = time.time()
        if self.session_start_time:
            self.accumulated_seconds += int(now - self.session_start_time)
            self.session_start_time = None

        self.status = "paused"
        self.last_pause_time = now

        if self.current_session_id:
            self.client.pause_session(self.current_session_id, self.accumulated_seconds)

        self.systray.update_icon()

    def resume_work(self):
        """Resumes the pro work session."""
        if self.status != "paused":
            return

        logger.info("Resuming work session (RESUME)...")
        self.status = "active"
        self.session_start_time = time.time()
        self.last_pause_time = None

        if self.current_session_id:
            self.client.resume_session(self.current_session_id)

        self.systray.update_icon()

    def start_personal_mode(self):
        """Switches to personal/leisure mode (pauses any work session)."""
        if self.status == "active":
            self.pause_work()

        logger.info("Switching to Personal / Leisure mode...")
        self.status = "personal"
        self.client.log_activity(self.current_session_id, "PERSONAL_MODE", {})
        self.systray.update_icon()

    def prompt_end_work(self):
        """Displays confirmation modal to record work completion and exit."""
        total_sec = self.get_current_session_seconds()
        hours, remainder = divmod(total_sec, 3600)
        minutes, seconds = divmod(remainder, 60)
        formatted = f"{hours:02d}h {minutes:02d}m {seconds:02d}s"

        modal = ConfirmEndWorkModal(
            parent=self.root,
            formatted_duration=formatted,
        )
        confirmed = modal.show_modal()

        if confirmed:
            self._execute_end_work_and_quit()

    def _setup_shutdown_handlers(self):
        """Registers OS and process handlers for system shutdown, logoff, and termination."""
        import atexit
        import signal

        atexit.register(self.shutdown_cleanup)

        try:
            signal.signal(signal.SIGINT, lambda s, f: self._signal_handler("SIGINT"))
            signal.signal(signal.SIGTERM, lambda s, f: self._signal_handler("SIGTERM"))
            if hasattr(signal, "SIGBREAK"):
                signal.signal(signal.SIGBREAK, lambda s, f: self._signal_handler("SIGBREAK"))
        except Exception as e:
            logger.debug(f"Signal registration note: {e}")

        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

                def win_console_handler(ctrl_type):
                    # 0: CTRL_C_EVENT, 1: CTRL_BREAK_EVENT, 2: CTRL_CLOSE_EVENT
                    # 5: CTRL_LOGOFF_EVENT, 6: CTRL_SHUTDOWN_EVENT
                    if ctrl_type in (2, 5, 6):
                        logger.info(f"Windows shutdown/logoff signal received (type={ctrl_type}). Finalizing session...")
                        self.shutdown_cleanup()
                        return True
                    return False

                self._win_handler_ref = HandlerRoutine(win_console_handler)
                ctypes.windll.kernel32.SetConsoleCtrlHandler(self._win_handler_ref, True)
                logger.info("Windows shutdown and logoff control handler registered.")
            except Exception as e:
                logger.warning(f"Could not register Win32 console handler: {e}")

    def _signal_handler(self, sig_name: str):
        logger.info(f"Process termination signal received: {sig_name}")
        self.shutdown_cleanup()
        sys.exit(0)

    def shutdown_cleanup(self):
        """Synchronously finalizes active work session on Supabase and releases resources upon PC shutdown."""
        if self._has_shutdown:
            return
        self._has_shutdown = True

        logger.info("Performing shutdown cleanup: closing active work session if present...")
        self._running = False

        if self.status in ("active", "paused") and self.current_session_id:
            try:
                elapsed = self.get_current_session_seconds()
                logger.info(f"Closing active work session {self.current_session_id} on system shutdown (elapsed={elapsed}s)...")
                self.client.end_work_session(
                    self.current_session_id,
                    elapsed,
                    notes="Clôturée automatiquement à l'extinction du PC"
                )
                self.status = "completed"
            except Exception as e:
                logger.error(f"Error closing session on shutdown: {e}")

        try:
            self.systray.stop()
        except Exception:
            pass

        if self.single_instance_lock:
            try:
                self.single_instance_lock.release()
            except Exception:
                pass

    def _execute_end_work_and_quit(self):
        """Finalizes session on Supabase and exits application cleanly."""
        logger.info("User requested work termination. Finalizing session and exiting...")
        self.shutdown_cleanup()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def restart_app(self):
        """Restarts the application executable or script cleanly without raising uncaught exceptions."""
        logger.info("Restarting application requested...")
        import subprocess
        import os
        import tempfile
        from pathlib import Path
        from agent.config import get_executable_path

        self.shutdown_cleanup()

        try:
            pid = os.getpid()
            exe_path = Path(get_executable_path()).resolve()

            if sys.platform == "win32":
                is_frozen = getattr(sys, "frozen", False)
                bat_path = Path(tempfile.gettempdir()) / f"krt_restart_{pid}.bat"

                work_dir = str(exe_path.parent)
                updater_log_str = str(UPDATER_LOG_PATH.resolve())

                # Clear Win32 OS-level environment variables
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetEnvironmentVariableW("_MEIPASS2", None)
                    ctypes.windll.kernel32.SetEnvironmentVariableW("_MEIPASS", None)
                except Exception:
                    pass

                if is_frozen:
                    bat_script = f"""@echo off
setlocal
set "LOGFILE={updater_log_str}"
echo [%date% %time%] [Restart] Starting application restart >> "%LOGFILE%"
echo [%date% %time%] [Restart] Target PID: {pid} >> "%LOGFILE%"
echo [%date% %time%] [Restart] Executable: {str(exe_path)} >> "%LOGFILE%"

:: Wait 2 seconds for parent process to exit and release all temporary directory handles
echo [%date% %time%] [Restart] Waiting for parent process {pid} to terminate... >> "%LOGFILE%"
ping 127.0.0.1 -n 3 >nul

set "_MEIPASS2="
set "_MEIPASS="
set "PYTHONHOME="
set "PYTHONPATH="

cd /d "{work_dir}"
echo [%date% %time%] [Restart] Launching: {str(exe_path)} >> "%LOGFILE%"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "(New-Object -ComObject Shell.Application).ShellExecute('{str(exe_path)}', '', '{work_dir}', 'open', 1)" >> "%LOGFILE%" 2>&1
echo [%date% %time%] [Restart] App restarted >> "%LOGFILE%"
(goto) 2>nul & del /F /Q "%~f0"
"""
                else:
                    bat_script = f"""@echo off
setlocal
set "LOGFILE={updater_log_str}"
echo [%date% %time%] [Restart] Starting dev mode restart >> "%LOGFILE%"
ping 127.0.0.1 -n 3 >nul
set "_MEIPASS2="
set "_MEIPASS="
cd /d "{work_dir}"
start "" "{sys.executable}" "{str(exe_path)}"
(goto) 2>nul & del /F /Q "%~f0"
"""

                bat_path.write_text(bat_script, encoding="cp1252", errors="ignore")
                env = os.environ.copy()
                env.pop("_MEIPASS2", None)
                env.pop("_MEIPASS", None)
                subprocess.Popen(
                    ["cmd.exe", "/c", str(bat_path)],
                    cwd=tempfile.gettempdir(),
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    close_fds=True
                )
            else:
                if getattr(sys, "frozen", False):
                    subprocess.Popen([str(exe_path)], start_new_session=True)
                else:
                    subprocess.Popen([sys.executable, str(exe_path)], start_new_session=True)
        except Exception as e:
            logger.error(f"Failed to spawn new process on restart: {e}")

        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _show_connection_alert(self):
        """Displays or focuses the connection lost alert modal."""
        if not self._connection_alert_modal or not self._connection_alert_modal.top.winfo_exists():
            self._connection_alert_modal = ConnectionAlertModal(
                parent=self.root,
                on_restart=self.restart_app,
                on_retry=self.retry_connection,
                on_dismiss=self._dismiss_connection_alert,
            )
        self._connection_alert_modal.show()

    def _dismiss_connection_alert(self):
        if self._connection_alert_modal:
            self._connection_alert_modal.close()
        self._connection_alert_modal = None

    def retry_connection(self):
        """Attempts an immediate manual reconnection and updates modal/UI."""
        def _worker():
            logger.info("Attempting manual reconnection to Supabase...")
            ok = self.client.test_connection()
            if ok:
                self.is_connected = True
                self._consecutive_heartbeat_failures = 0
                if self.status in ("active", "paused") and self.current_session_id:
                    elapsed = self.get_current_session_seconds()
                    self.client.send_heartbeat(self.current_session_id, elapsed)

                def _on_success():
                    if self._connection_alert_modal:
                        self._connection_alert_modal.set_status_message("Connexion rétablie avec succès !", "#10B981")
                        self.root.after(800, self._dismiss_connection_alert)
                    if self.dashboard:
                        self.dashboard.update_timer_display(self.get_current_session_seconds(), self.get_today_total_seconds(), self.status)

                self.root.after(0, _on_success)
            else:
                def _on_fail():
                    if self._connection_alert_modal:
                        self._connection_alert_modal.set_status_message("Impossible de joindre le serveur. Veuillez vérifier votre réseau.", "#EF4444")
                self.root.after(0, _on_fail)

        threading.Thread(target=_worker, daemon=True, name="ManualReconnectionWorker").start()

    # ==================== BACKGROUND HEARTBEAT ====================

    def _heartbeat_worker(self):
        """Background thread sending heartbeats and syncing session changes from web app."""
        logger.info(f"Heartbeat thread started (interval={HEARTBEAT_INTERVAL_SECONDS}s).")
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
            if not self._running:
                break

            if self.status in ("active", "paused") and self.current_session_id:
                elapsed = self.get_current_session_seconds()
                success, session_data = self.client.send_heartbeat(self.current_session_id, elapsed)
                self.is_connected = success
                if success:
                    self.last_heartbeat_time = time.time()
                    if self._consecutive_heartbeat_failures > 0:
                        logger.info(f"Connection restored successfully after {self._consecutive_heartbeat_failures} failed heartbeat(s).")
                        self._consecutive_heartbeat_failures = 0
                        if self._connection_alert_modal:
                            self.root.after(0, self._dismiss_connection_alert)
                    if session_data:
                        self._sync_session_from_remote(session_data)
                else:
                    self._consecutive_heartbeat_failures += 1
                    logger.warning(f"Heartbeat failed ({self._consecutive_heartbeat_failures} consecutive failure(s)).")
                    # Trigger alert after 4 consecutive failures (~2 minutes of sustained disconnection)
                    if self._consecutive_heartbeat_failures == 4:
                        self.root.after(0, self._show_connection_alert)


    # ==================== AUTO-UPDATE ====================

    def check_updates(self, manual: bool = False):
        """Checks for updates on GitHub in a background thread."""
        logger.info(f"Checking for updates on GitHub (manual={manual})...")

        def worker():
            release_info = self.updater.check_for_update()
            if release_info:
                logger.info(f"Update available: {release_info.tag_name}")
                def open_modal():
                    parent_win = self.dashboard.top if (self.dashboard and self.dashboard.top.winfo_exists() and self.dashboard._is_visible) else self.root
                    if not self._update_modal or not self._update_modal.top.winfo_exists():
                        self._update_modal = UpdateModal(
                            parent=parent_win,
                            release_info=release_info,
                            updater=self.updater,
                            on_before_restart=self._prepare_restart
                        )
                    else:
                        self._update_modal.show()
                self.root.after(0, open_modal)
            elif manual:
                logger.info("Application is up to date.")
                def show_up_to_date():
                    self._show_info_popup(
                        "KRT Bookings Tracker",
                        f"Vous utilisez déjà la dernière version disponible ({APP_VERSION_DISPLAY})."
                    )
                self.root.after(0, show_up_to_date)

        t = threading.Thread(target=worker, daemon=True, name="UpdateCheckThread")
        t.start()

    def _show_info_popup(self, title: str, message: str):
        """Displays a lightweight themed popup for informative messages."""
        parent_win = self.dashboard.top if (self.dashboard and self.dashboard.top.winfo_exists() and self.dashboard._is_visible) else self.root
        top = tk.Toplevel(parent_win)
        from agent.ui.theme import (
            apply_window_theme, center_window, BG_MAIN, BG_CARD, BG_CARD_HOVER,
            TEXT_PRIMARY, TEXT_SECONDARY, ACCENT_GREEN,
            FONT_TITLE, FONT_BODY, FONT_SMALL
        )
        apply_window_theme(top, title=title, resizable=False)
        top.attributes("-topmost", True)
        if parent_win != self.root:
            top.transient(parent_win)

        frame = tk.Frame(top, bg=BG_MAIN, padx=24, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="✅ À jour", font=FONT_TITLE, fg=ACCENT_GREEN, bg=BG_MAIN).pack(anchor="w")
        tk.Label(frame, text=message, font=FONT_BODY, fg=TEXT_SECONDARY, bg=BG_MAIN, wraplength=420, justify="left").pack(anchor="w", pady=(8, 16))

        tk.Button(
            frame, text="Fermer", font=FONT_SMALL,
            bg=BG_CARD, fg=TEXT_PRIMARY, activebackground=BG_CARD_HOVER, activeforeground=TEXT_PRIMARY,
            relief=tk.FLAT, cursor="hand2", padx=18, pady=6, command=top.destroy
        ).pack(side=tk.RIGHT)

        center_window(top, width=480, height=220)
        top.deiconify()
        top.lift()
        top.focus_force()

    def _prepare_restart(self):
        """Prepares the agent for update restart by closing active sessions/threads cleanly."""
        logger.info("Preparing for application restart post-update...")
        self.shutdown_cleanup()

    # ==================== UI OPENERS ====================

    def show_dashboard(self):
        """Opens or brings to focus the live tracking dashboard."""
        if not self.dashboard:
            self.dashboard = DashboardWindow(self, parent=self.root)
        self.dashboard.show()

    # ==================== STARTUP SEQUENCE ====================

    def start(self):
        """Main startup sequence."""
        logger.info(f"[{APP_NAME}] Starting agent initialization...")
        self._keepalive()

        # 1. Check local credentials
        creds = SecureStorage.load_credentials()
        authenticated = False

        if creds:
            logger.info("Found stored credentials, verifying session...")
            self.client.access_token = creds.get("access_token")
            self.client.refresh_token = creds.get("refresh_token")
            self.client.user_id = creds.get("user_id")
            if creds.get("profile"):
                self.client.user_profile = creds.get("profile")
            if self.client.verify_token():
                authenticated = True
                logger.info(f"Authenticated as {self.get_user_display_name()}")

        # 2. If not authenticated, open Login Window modal
        if not authenticated:
            logger.info("Opening login window modal...")
            login_win = LoginWindow(
                parent=self.root,
                client=self.client,
                on_success=lambda data: SecureStorage.save_credentials(data),
            )
            self._active_modal = login_win
            auth_data = login_win.show_modal()
            self._active_modal = None

            # Verify if login was successful
            if not self.client.user_id:
                logger.warning("Authentication cancelled or failed. Exiting.")
                self.root.destroy()
                sys.exit(0)

        # 3. Ensure Autostart is registered
        if not AutostartManager.is_enabled():
            AutostartManager.enable()

        # 4. Clean up any unclosed sessions from previous days (older than today)
        self.client.cleanup_stale_sessions(exclude_today=True)

        # 5. Check if an unclosed session from today exists to propose resuming
        pending_session = self.client.get_today_unclosed_session()

        # 6. Fetch today's summary
        summary = self.client.get_today_summary()
        self.today_prior_seconds = summary.get("total_seconds", 0)

        # 7. Startup Session Qualification Modal
        user_name = self.get_user_display_name().split()[0]
        logger.info(f"Opening startup qualification modal for {user_name} (pending_session={'yes' if pending_session else 'no'})...")
        startup_modal = StartupModal(
            parent=self.root,
            user_name=user_name,
            resumable_session=pending_session,
        )
        self._active_modal = startup_modal
        choice = startup_modal.show_modal()
        self._active_modal = None

        if choice == "resume" and pending_session:
            self.resume_existing_work_session(pending_session)
        elif choice in ("work", "new_work"):
            self.start_work()
        else:
            self.start_personal_mode()

        # 6. Initialize Dashboard Window (hidden by default)
        self.dashboard = DashboardWindow(self, parent=self.root)
        self.dashboard.hide()

        # 7. Start Systray and Heartbeat Thread
        self.systray.start()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_worker,
            daemon=True,
            name="HeartbeatThread",
        )
        self._heartbeat_thread.start()

        # 8. Check for updates on startup & periodically
        if UPDATE_CHECK_ON_STARTUP:
            self.root.after(4000, lambda: self.check_updates(manual=False))

        def periodic_update_checker():
            while self._running:
                time.sleep(UPDATE_CHECK_INTERVAL_SECONDS)
                if not self._running:
                    break
                self.check_updates(manual=False)

        threading.Thread(target=periodic_update_checker, daemon=True, name="PeriodicUpdaterThread").start()

        logger.info("Agent is fully initialized, running mainloop...")

        # 9. Start Tkinter Main Event Loop
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._execute_end_work_and_quit()
