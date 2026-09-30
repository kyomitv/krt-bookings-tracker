"""
Secure encrypted credential storage for KRT Agent.
Uses Fernet symmetric encryption with a machine-derived key.
"""
import os
import sys
import json
import base64
import hashlib
import platform
import uuid
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from agent.config import CONFIG_FILE_PATH

def _get_machine_identifier(legacy: bool = False) -> bytes:
    """
    Derives a stable machine-specific seed for key derivation.
    Uses Windows MachineGuid when available to avoid Wi-Fi/MAC instability.
    """
    system = platform.system()
    if legacy:
        # Legacy derivation for backward compatibility
        seed_parts = [
            platform.node(),
            platform.machine(),
            system,
            str(uuid.getnode()),
        ]
        return ":".join(seed_parts).encode("utf-8")

    guid = ""
    if sys.platform == "win32":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            guid = winreg.QueryValueEx(k, "MachineGuid")[0]
        except Exception:
            pass

    seed_parts = [
        guid or "krt_guid_stable",
        platform.node(),
        platform.machine(),
        system,
        os.environ.get("COMPUTERNAME", ""),
        os.environ.get("USERNAME", ""),
    ]
    return ":".join(seed_parts).encode("utf-8")

def _get_fernet(legacy: bool = False) -> Fernet:
    """Generates a Fernet instance using machine-specific PBKDF2 derivation."""
    machine_seed = _get_machine_identifier(legacy=legacy)
    salt = b"krt_bookings_agent_salt_v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(machine_seed))
    return Fernet(key)

class SecureStorage:
    """Encrypted storage manager for session tokens and user state."""

    @staticmethod
    def save_credentials(data: Dict[str, Any]) -> bool:
        """Encrypt and write user credentials/tokens to local disk."""
        try:
            fernet = _get_fernet(legacy=False)
            json_data = json.dumps(data).encode("utf-8")
            encrypted = fernet.encrypt(json_data)
            CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE_PATH, "wb") as f:
                f.write(encrypted)
            return True
        except Exception as e:
            print(f"[CryptoStorage] Error saving credentials: {e}")
            return False

    @staticmethod
    def load_credentials() -> Optional[Dict[str, Any]]:
        """
        Read and decrypt stored credentials from local disk.
        Attempts stable key first, then falls back to legacy key if needed.
        """
        if not CONFIG_FILE_PATH.exists():
            return None
        try:
            with open(CONFIG_FILE_PATH, "rb") as f:
                encrypted = f.read()
            
            # 1. Try modern stable key
            try:
                fernet = _get_fernet(legacy=False)
                decrypted = fernet.decrypt(encrypted)
                return json.loads(decrypted.decode("utf-8"))
            except Exception:
                # 2. Try legacy fallback
                fernet_legacy = _get_fernet(legacy=True)
                decrypted = fernet_legacy.decrypt(encrypted)
                data = json.loads(decrypted.decode("utf-8"))
                # Migrate to modern key format automatically
                SecureStorage.save_credentials(data)
                return data
        except Exception as e:
            print(f"[CryptoStorage] Error loading credentials: {e}")
            return None

    @staticmethod
    def clear_credentials() -> bool:
        """Remove stored credentials on logout."""
        try:
            if CONFIG_FILE_PATH.exists():
                os.remove(CONFIG_FILE_PATH)
            return True
        except Exception as e:
            print(f"[CryptoStorage] Error removing credentials: {e}")
            return False

