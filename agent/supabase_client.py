"""
Supabase API Client for KRT Bookings Tracker.
Handles authentication, profile fetching, work sessions, and heartbeats.
"""
import platform
import socket
import datetime
import requests
from typing import Optional, Dict, Any, Tuple
from agent.config import SUPABASE_URL, SUPABASE_ANON_KEY
from agent.logger import logger

class SupabaseClient:
    """Direct lightweight client for Supabase REST API & GoTrue Auth."""

    def __init__(self, access_token: Optional[str] = None, refresh_token: Optional[str] = None, user_id: Optional[str] = None):
        self.base_url = SUPABASE_URL.rstrip("/")
        self.anon_key = SUPABASE_ANON_KEY
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.user_id = user_id
        self.user_profile: Optional[Dict[str, Any]] = None

    def _get_headers(self, authenticated: bool = True) -> Dict[str, str]:
        headers = {
            "apikey": self.anon_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if authenticated and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        else:
            headers["Authorization"] = f"Bearer {self.anon_key}"
        return headers

    def _get_device_info(self) -> Dict[str, Any]:
        """Collects non-intrusive system device info for session context."""
        return {
            "hostname": socket.gethostname(),
            "os": platform.system(),
            "os_release": platform.release(),
            "python_version": platform.python_version(),
        }

    # ==================== AUTHENTICATION ====================

    def sign_in_with_password(self, email: str, password: str) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Sign in using email and password via Supabase Auth."""
        logger.info(f"Attempting login for email: {email}")
        url = f"{self.base_url}/auth/v1/token?grant_type=password"
        payload = {
            "email": email.strip(),
            "password": password,
        }
        try:
            resp = requests.post(url, headers=self._get_headers(authenticated=False), json=payload, timeout=12)
            logger.debug(f"Auth response code: {resp.status_code}")
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                user = data.get("user", {})
                self.user_id = user.get("id")

                logger.info(f"Login successful for user_id: {self.user_id}")
                # Fetch detailed profile
                self.fetch_profile()
                return True, None, {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "user_id": self.user_id,
                    "email": email,
                    "profile": self.user_profile,
                }
            else:
                try:
                    error_data = resp.json()
                    err_msg = error_data.get("error_description") or error_data.get("msg") or "Identifiants incorrects."
                except Exception:
                    err_msg = f"Erreur serveur ({resp.status_code})"
                logger.warning(f"Login failed: {err_msg}")
                return False, err_msg, None
        except Exception as e:
            logger.error(f"Network error during sign_in: {e}")
            return False, f"Erreur de connexion réseau : {e}", None

    def refresh_session(self) -> bool:
        """Refreshes the auth session using the refresh token."""
        if not self.refresh_token:
            return False
        logger.info("Refreshing auth session token...")
        url = f"{self.base_url}/auth/v1/token?grant_type=refresh_token"
        payload = {"refresh_token": self.refresh_token}
        try:
            resp = requests.post(url, headers=self._get_headers(authenticated=False), json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                user = data.get("user", {})
                self.user_id = user.get("id")
                logger.info("Session refreshed successfully.")
                return True
            logger.warning(f"Failed to refresh session: {resp.status_code} {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Error during refresh_session: {e}")
            return False

    def verify_token(self) -> bool:
        """Verifies if current access token is valid by querying user endpoint."""
        if not self.access_token:
            return False
        logger.info("Verifying access token...")
        url = f"{self.base_url}/auth/v1/user"
        try:
            resp = requests.get(url, headers=self._get_headers(authenticated=True), timeout=8)
            if resp.status_code == 200:
                user_data = resp.json()
                self.user_id = user_data.get("id")
                self.fetch_profile()
                logger.info(f"Token verified for user_id: {self.user_id}")
                return True
            logger.info("Token expired or invalid, trying refresh...")
            # Try to refresh token
            if self.refresh_session():
                self.fetch_profile()
                return True
            return False
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return False

    def fetch_profile(self) -> Optional[Dict[str, Any]]:
        """Fetch user profile from public.profiles table."""
        if not self.user_id:
            return None
        url = f"{self.base_url}/rest/v1/profiles?id=eq.{self.user_id}&select=*"
        try:
            resp = requests.get(url, headers=self._get_headers(authenticated=True), timeout=8)
            if resp.status_code == 200:
                rows = resp.json()
                if rows and len(rows) > 0:
                    self.user_profile = rows[0]
                    logger.info(f"Profile loaded: {self.user_profile.get('first_name')} {self.user_profile.get('last_name')}")
                    return self.user_profile
            return None
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            return None

    # ==================== WORK SESSIONS ====================

    def cleanup_stale_sessions(self) -> int:
        """
        Closes any unclosed/dangling sessions ('active' or 'paused') for the current user
        by marking them as 'cancelled' (failed/interrupted due to connection loss or abrupt shutdown).
        Returns the number of closed sessions.
        """
        if not self.user_id:
            return 0

        url = f"{self.base_url}/rest/v1/hr_work_sessions?user_id=eq.{self.user_id}&status=in.(active,paused)&select=id,last_heartbeat_at,updated_at,started_at,duration_seconds,notes"
        try:
            resp = requests.get(url, headers=self._get_headers(authenticated=True), timeout=8)
            if resp.status_code != 200:
                logger.warning(f"Could not fetch stale sessions ({resp.status_code}): {resp.text}")
                return 0

            stale_sessions = resp.json()
            if not stale_sessions:
                return 0

            logger.info(f"Found {len(stale_sessions)} stale/unclosed session(s). Closing them...")
            closed_count = 0
            now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            for s in stale_sessions:
                sid = s.get("id")
                if not sid:
                    continue
                ended_at = s.get("last_heartbeat_at") or s.get("updated_at") or now_iso
                existing_notes = s.get("notes") or ""
                note_suffix = "[Clôturée en échec - perte de connexion ou arrêt inopiné]"
                new_notes = f"{existing_notes} {note_suffix}".strip() if existing_notes else note_suffix

                patch_url = f"{self.base_url}/rest/v1/hr_work_sessions?id=eq.{sid}"
                patch_payload = {
                    "status": "cancelled",
                    "ended_at": ended_at,
                    "notes": new_notes,
                    "updated_at": now_iso,
                }
                patch_resp = requests.patch(patch_url, headers=self._get_headers(authenticated=True), json=patch_payload, timeout=8)
                if patch_resp.status_code in (200, 204):
                    closed_count += 1
                    self.log_activity(sid, "SESSION_CLOSED_ON_RECOVERY", {
                        "reason": "unclosed_session_cleanup",
                        "ended_at": ended_at
                    })
                    logger.info(f"Stale session {sid} closed as 'cancelled' (ended_at={ended_at})")
                else:
                    logger.warning(f"Failed to close stale session {sid}: {patch_resp.status_code} {patch_resp.text}")

            return closed_count
        except Exception as e:
            logger.error(f"Error during cleanup_stale_sessions: {e}")
            return 0

    def start_work_session(self, session_type: str = "work") -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Creates a new work session in Supabase after closing any dangling sessions,
        and records the START_WORK event.
        """
        if not self.user_id:
            return False, "Utilisateur non authentifié.", None

        # Automatically close any previous unclosed/blocking sessions
        self.cleanup_stale_sessions()

        logger.info(f"Starting work session on Supabase (type={session_type})...")
        url = f"{self.base_url}/rest/v1/hr_work_sessions"
        payload = {
            "user_id": self.user_id,
            "status": "active",
            "session_type": session_type,
            "duration_seconds": 0,
            "device_info": self._get_device_info(),
        }
        try:
            resp = requests.post(url, headers=self._get_headers(authenticated=True), json=payload, timeout=10)
            logger.debug(f"start_work_session status: {resp.status_code}, response: {resp.text}")
            if resp.status_code in (200, 201):
                rows = resp.json()
                session = rows[0] if isinstance(rows, list) and rows else payload
                session_id = session.get("id")

                # Log activity event
                if session_id:
                    self.log_activity(session_id, "START_WORK", {"session_type": session_type})

                logger.info(f"Work session created with id: {session_id}")
                return True, None, session
            else:
                err_msg = f"Supabase error ({resp.status_code}): {resp.text}"
                logger.error(err_msg)
                return False, err_msg, None
        except Exception as e:
            logger.error(f"Exception during start_work_session: {e}")
            return False, f"Erreur réseau: {e}", None

    def send_heartbeat(self, session_id: str, elapsed_seconds: int) -> bool:
        """
        Updates session's last_heartbeat_at timestamp and duration.
        """
        if not session_id or not self.user_id:
            return False

        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{self.base_url}/rest/v1/hr_work_sessions?id=eq.{session_id}"
        payload = {
            "last_heartbeat_at": now_iso,
            "duration_seconds": elapsed_seconds,
            "updated_at": now_iso,
        }
        try:
            resp = requests.patch(url, headers=self._get_headers(authenticated=True), json=payload, timeout=8)
            success = resp.status_code in (200, 204)
            if success:
                logger.debug(f"Heartbeat sent for session {session_id} (elapsed={elapsed_seconds}s)")
            else:
                logger.warning(f"Heartbeat failed with status {resp.status_code}: {resp.text}")
            return success
        except Exception as e:
            logger.error(f"Heartbeat exception: {e}")
            return False

    def pause_session(self, session_id: str, elapsed_seconds: int) -> bool:
        """Pauses the current active work session."""
        if not session_id:
            return False
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{self.base_url}/rest/v1/hr_work_sessions?id=eq.{session_id}"
        payload = {
            "status": "paused",
            "duration_seconds": elapsed_seconds,
            "updated_at": now_iso,
        }
        try:
            resp = requests.patch(url, headers=self._get_headers(authenticated=True), json=payload, timeout=8)
            if resp.status_code in (200, 204):
                self.log_activity(session_id, "PAUSE", {"duration_seconds": elapsed_seconds})
                logger.info(f"Session {session_id} paused at {elapsed_seconds}s")
                return True
            logger.warning(f"Pause failed: {resp.status_code} {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Pause exception: {e}")
            return False

    def resume_session(self, session_id: str) -> bool:
        """Resumes a paused work session."""
        if not session_id:
            return False
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{self.base_url}/rest/v1/hr_work_sessions?id=eq.{session_id}"
        payload = {
            "status": "active",
            "last_heartbeat_at": now_iso,
            "updated_at": now_iso,
        }
        try:
            resp = requests.patch(url, headers=self._get_headers(authenticated=True), json=payload, timeout=8)
            if resp.status_code in (200, 204):
                self.log_activity(session_id, "RESUME", {})
                logger.info(f"Session {session_id} resumed")
                return True
            logger.warning(f"Resume failed: {resp.status_code} {resp.text}")
            return False
        except Exception as e:
            logger.error(f"Resume exception: {e}")
            return False

    def end_work_session(self, session_id: str, total_duration_seconds: int, notes: str = "") -> bool:
        """
        Marks work session as completed and records END_WORK signal with retry logic.
        """
        if not session_id:
            return False
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{self.base_url}/rest/v1/hr_work_sessions?id=eq.{session_id}"
        payload = {
            "status": "completed",
            "ended_at": now_iso,
            "duration_seconds": total_duration_seconds,
            "notes": notes,
            "updated_at": now_iso,
        }
        for attempt in range(3):
            try:
                resp = requests.patch(url, headers=self._get_headers(authenticated=True), json=payload, timeout=8)
                if resp.status_code in (200, 204):
                    self.log_activity(session_id, "END_WORK", {
                        "total_duration_seconds": total_duration_seconds,
                        "notes": notes,
                    })
                    logger.info(f"Session {session_id} ended (total_duration={total_duration_seconds}s)")
                    return True
                logger.warning(f"End session attempt {attempt + 1} failed: {resp.status_code} {resp.text}")
            except Exception as e:
                logger.error(f"End session attempt {attempt + 1} exception: {e}")
            time.sleep(1)
        return False

    def log_activity(self, session_id: Optional[str], event_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Inserts an event into public.hr_activity_logs."""
        if not self.user_id:
            return False
        url = f"{self.base_url}/rest/v1/hr_activity_logs"
        payload = {
            "session_id": session_id,
            "user_id": self.user_id,
            "event_type": event_type,
            "metadata": metadata or {},
        }
        try:
            resp = requests.post(url, headers=self._get_headers(authenticated=True), json=payload, timeout=6)
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"Log activity exception: {e}")
            return False

    def get_today_summary(self) -> Dict[str, Any]:
        """Calculates total hours worked today across completed and active sessions."""
        if not self.user_id:
            return {"total_seconds": 0, "session_count": 0}

        # Format as UTC ISO with 'Z' suffix to avoid PostgREST '+' space encoding issue
        today_start = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

        url = f"{self.base_url}/rest/v1/hr_work_sessions?user_id=eq.{self.user_id}&started_at=gte.{today_start}&select=duration_seconds,status"
        try:
            resp = requests.get(url, headers=self._get_headers(authenticated=True), timeout=8)
            if resp.status_code == 200:
                rows = resp.json()
                total_sec = sum(r.get("duration_seconds", 0) for r in rows)
                logger.info(f"Today's summary: {len(rows)} sessions, {total_sec}s total")
                return {
                    "total_seconds": total_sec,
                    "session_count": len(rows),
                }
            logger.warning(f"Failed to fetch today summary ({resp.status_code}): {resp.text}")
            return {"total_seconds": 0, "session_count": 0}
        except Exception as e:
            logger.error(f"Error fetching today summary: {e}")
            return {"total_seconds": 0, "session_count": 0}
