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
    APP_NAME, APP_VERSION, HEARTBEAT_INTERVAL_SECONDS,
    UPDATE_CHECK_ON_STARTUP, UPDATE_CHECK_INTERVAL_SECONDS
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
from agent.ui.update_modal import UpdateModal
from agent.logger import logger

class KRTTrackerAgent:
    """Main Agent controller orchestrating UI, Supabase sync, systray, and time tracking."""

    def __init__(self):
        logger.info("Initializing KRTTrackerAgent instance...")
        self.client = SupabaseClient()
        self.updater = AutoUpdater()
        self.systray = SystrayManager(self)
        self.dashboard: Optional[DashboardWindow] = None
        self._update_modal: Optional[UpdateModal] = None

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

        # Tkinter Root
        self.root = tk.Tk()
        self.root.withdraw() # Main root is hidden, child dialogs/dashboard are Toplevels

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

    # ==================== WORKFLOW ACTIONS ====================

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

    def _execute_end_work_and_quit(self):
        """Finalizes session on Supabase and exits application."""
        logger.info("Finalizing work session and terminating agent...")
        total_sec = self.get_current_session_seconds()
        if self.current_session_id:
            self.client.end_work_session(self.current_session_id, total_sec)

        self.status = "completed"
        self._running = False
        self.systray.stop()
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    # ==================== BACKGROUND HEARTBEAT ====================

    def _heartbeat_worker(self):
        """Background thread sending heartbeats every HEARTBEAT_INTERVAL_SECONDS."""
        logger.info(f"Heartbeat thread started (interval={HEARTBEAT_INTERVAL_SECONDS}s).")
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
            if not self._running:
                break

            if self.status == "active" and self.current_session_id:
                elapsed = self.get_current_session_seconds()
                success = self.client.send_heartbeat(self.current_session_id, elapsed)
                self.is_connected = success
                if success:
                    self.last_heartbeat_time = time.time()
                else:
                    logger.warning("Heartbeat failed, will retry next cycle.")

    # ==================== AUTO-UPDATE ====================

    def check_updates(self, manual: bool = False):
        """Checks for updates on GitHub in a background thread."""
        logger.info(f"Checking for updates on GitHub (manual={manual})...")

        def worker():
            release_info = self.updater.check_for_update()
            if release_info:
                logger.info(f"Update available: {release_info.tag_name}")
                def open_modal():
                    if not self._update_modal or not self._update_modal.top.winfo_exists():
                        self._update_modal = UpdateModal(
                            parent=self.root,
                            release_info=release_info,
                            updater=self.updater,
                            on_before_restart=self._prepare_restart
                        )
                    else:
                        self._update_modal.top.lift()
                self.root.after(0, open_modal)
            elif manual:
                logger.info("Application is up to date.")
                def show_up_to_date():
                    self._show_info_popup(
                        "KRT Bookings Tracker",
                        f"Vous utilisez déjà la dernière version disponible (v{APP_VERSION})."
                    )
                self.root.after(0, show_up_to_date)

        t = threading.Thread(target=worker, daemon=True, name="UpdateCheckThread")
        t.start()

    def _show_info_popup(self, title: str, message: str):
        """Displays a lightweight themed popup for informative messages."""
        top = tk.Toplevel(self.root)
        top.title(title)
        top.configure(bg="#0F172A")
        top.resizable(False, False)
        top.attributes("-topmost", True)
        from agent.ui.theme import center_window
        center_window(top, 380, 160)
        top.transient(self.root)

        frame = tk.Frame(top, bg="#0F172A", padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="✅ À jour", font=("Segoe UI", 12, "bold"), fg="#10B981", bg="#0F172A").pack(anchor="w")
        tk.Label(frame, text=message, font=("Segoe UI", 9), fg="#94A3B8", bg="#0F172A", wraplength=340, justify="left").pack(anchor="w", pady=(8, 14))

        tk.Button(
            frame, text="Fermer", font=("Segoe UI", 9, "bold"),
            bg="#1E293B", fg="#F8FAFC", relief=tk.FLAT, cursor="hand2",
            padx=16, pady=4, command=top.destroy
        ).pack(side=tk.RIGHT)

    def _prepare_restart(self):
        """Prepares the agent for update restart by closing active sessions/threads cleanly."""
        logger.info("Preparing for application restart post-update...")
        if self.status == "active" and self.current_session_id:
            elapsed = self.get_current_session_seconds()
            self.client.pause_session(self.current_session_id, elapsed)
        self._running = False
        self.systray.stop()

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
            auth_data = login_win.show_modal()

            # Verify if login was successful
            if not self.client.user_id:
                logger.warning("Authentication cancelled or failed. Exiting.")
                self.root.destroy()
                sys.exit(0)

        # 3. Ensure Autostart is registered
        if not AutostartManager.is_enabled():
            AutostartManager.enable()

        # 4. Fetch today's summary
        summary = self.client.get_today_summary()
        self.today_prior_seconds = summary.get("total_seconds", 0)

        # 5. Startup Session Qualification Modal
        user_name = self.get_user_display_name().split()[0]
        logger.info(f"Opening startup qualification modal for {user_name}...")
        startup_modal = StartupModal(
            parent=self.root,
            user_name=user_name,
        )
        choice = startup_modal.show_modal()

        if choice == "work":
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
