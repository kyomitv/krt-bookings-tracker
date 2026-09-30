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
        sample_data = {"test_key": "test_value_123", "user_id": "test-uuid-456"}
        save_res = SecureStorage.save_credentials(sample_data)
        self.assertTrue(save_res)

        loaded_data = SecureStorage.load_credentials()
        self.assertIsNotNone(loaded_data)
        self.assertEqual(loaded_data.get("test_key"), "test_value_123")
        self.assertEqual(loaded_data.get("user_id"), "test-uuid-456")

        # Cleanup
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

if __name__ == "__main__":
    unittest.main()
