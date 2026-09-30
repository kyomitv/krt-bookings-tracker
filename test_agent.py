"""
Unit test and sanity check script for KRT Bookings Tracker Agent modules.
"""
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from agent.config import APP_NAME, SUPABASE_URL, SUPABASE_ANON_KEY
from agent.crypto_storage import SecureStorage
from agent.autostart import AutostartManager
from agent.supabase_client import SupabaseClient
from agent.systray_manager import SystrayManager

from agent.updater import parse_version, is_newer_version, AutoUpdater

class TestKRTAgent(unittest.TestCase):

    def test_config(self):
        self.assertEqual(APP_NAME, "KRT Bookings Tracker")
        self.assertTrue(len(SUPABASE_URL) > 0)
        self.assertTrue(len(SUPABASE_ANON_KEY) > 0)

    def test_versioning_and_updater(self):
        # Version parsing
        self.assertEqual(parse_version("1.0.0"), (1, 0, 0))
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("V2.10.5-beta"), (2, 10, 5))
        self.assertEqual(parse_version("1.0"), (1, 0, 0))

        # Newer version comparison
        self.assertTrue(is_newer_version("v1.0.1", "1.0.0"))
        self.assertTrue(is_newer_version("2.0.0", "1.9.9"))
        self.assertTrue(is_newer_version("v1.1.0", "1.0.9"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.0"))
        self.assertFalse(is_newer_version("0.9.9", "1.0.0"))
        self.assertFalse(is_newer_version("v1.0.0", "1.0.1"))

        # Updater asset selection
        updater = AutoUpdater(repo="test/repo", current_version="1.0.0")
        assets = [
            {"name": "source.tar.gz", "browser_download_url": "https://.../source.tar.gz", "size": 1000},
            {"name": "KRT-Bookings-Tracker.exe", "browser_download_url": "https://.../KRT-Bookings-Tracker.exe", "size": 25000000},
        ]
        selected = updater._select_asset(assets)
        self.assertIsNotNone(selected)
        if sys.platform == "win32":
            self.assertEqual(selected["name"], "KRT-Bookings-Tracker.exe")

    def test_crypto_storage(self):
        # Backup existing credentials if any
        original_creds = SecureStorage.load_credentials()

        sample_data = {"test_key": "test_value_123", "user_id": "test-uuid-456"}
        save_res = SecureStorage.save_credentials(sample_data)
        self.assertTrue(save_res)

        loaded_data = SecureStorage.load_credentials()
        self.assertIsNotNone(loaded_data)
        self.assertEqual(loaded_data.get("test_key"), "test_value_123")
        self.assertEqual(loaded_data.get("user_id"), "test-uuid-456")

        # Cleanup / Restore original
        if original_creds:
            SecureStorage.save_credentials(original_creds)
        else:
            SecureStorage.clear_credentials()

    def test_autostart_check(self):
        # Should not raise exception
        status = AutostartManager.is_enabled()
        self.assertIsInstance(status, bool)

    def test_supabase_client_init(self):
        client = SupabaseClient()
        self.assertIsNotNone(client.base_url)
        headers = client._get_headers(authenticated=False)
        self.assertIn("apikey", headers)
        self.assertTrue(hasattr(client, "cleanup_stale_sessions"))
        self.assertTrue(callable(client.cleanup_stale_sessions))
        self.assertTrue(hasattr(client, "get_work_session"))

    def test_remote_session_sync_logic(self):
        from agent.agent import KRTTrackerAgent
        import datetime
        agent = KRTTrackerAgent()
        agent.status = "active"
        agent.start_time_str = "09:00"
        agent.estimated_end_time_str = "17:30"

        # Simulate web app updating started_at to 08:30 UTC
        utc_time = "2026-09-30T06:30:00Z"
        agent._sync_session_from_remote({"started_at": utc_time})

        expected_local_dt = datetime.datetime.fromisoformat("2026-09-30T06:30:00+00:00").astimezone()
        expected_start_str = expected_local_dt.strftime("%H:%M")
        expected_end_str = (expected_local_dt + datetime.timedelta(hours=8, minutes=30)).strftime("%H:%M")

        self.assertEqual(agent.start_time_str, expected_start_str)
        self.assertEqual(agent.estimated_end_time_str, expected_end_str)
        self.assertEqual(agent.session_start_time, expected_local_dt.timestamp())
        agent.root.destroy()

    def test_resume_existing_work_session(self):
        from agent.agent import KRTTrackerAgent
        import datetime
        agent = KRTTrackerAgent()
        sample_session = {
            "id": "test-session-uuid-123",
            "started_at": "2026-09-30T08:00:00Z",
            "status": "paused",
            "duration_seconds": 1800,
        }
        agent.resume_existing_work_session(sample_session)
        self.assertEqual(agent.current_session_id, "test-session-uuid-123")
        self.assertEqual(agent.status, "active")
        expected_dt = datetime.datetime.fromisoformat("2026-09-30T08:00:00+00:00").astimezone()
        self.assertEqual(agent.start_time_str, expected_dt.strftime("%H:%M"))
        agent.root.destroy()

    def test_single_instance_lock(self):
        from agent.single_instance import SingleInstanceManager
        lock1 = SingleInstanceManager(mutex_name="Local\\Test_SingleInstance_Mutex_1")
        lock2 = SingleInstanceManager(mutex_name="Local\\Test_SingleInstance_Mutex_1")
        try:
            self.assertTrue(lock1.acquire())
            # Second acquire on same mutex should fail
            self.assertFalse(lock2.acquire())
        finally:
            lock1.release()
            lock2.release()

    def test_version_display_format(self):
        from agent.config import APP_VERSION, APP_VERSION_DISPLAY
        self.assertFalse(APP_VERSION.startswith("v"))
        self.assertTrue(APP_VERSION_DISPLAY.startswith("v"))
        self.assertEqual(APP_VERSION_DISPLAY, f"v{APP_VERSION}")

if __name__ == "__main__":
    unittest.main()
