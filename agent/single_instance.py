"""
Single instance enforcement and IPC orchestration for KRT Bookings Tracker.
Prevents multiple instances from running concurrently using a Windows Named Mutex.
When a duplicate instance starts, it securely signals the primary instance via local IPC
to bring its dashboard or active view to the foreground, then exits cleanly.
"""
import sys
import os
import json
import socket
import threading
import ctypes
from typing import Optional, Callable
from pathlib import Path
from agent.config import APP_DATA_DIR
from agent.logger import logger

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Local\\KRT_Bookings_Tracker_SingleInstance_Mutex"
LOCK_FILE = APP_DATA_DIR / "app_instance.lock"
DEFAULT_IPC_PORT = 49285


class SingleInstanceManager:
    """Manages single-instance lock and IPC activation across the operating system."""

    def __init__(self, mutex_name: str = MUTEX_NAME):
        self.mutex_name = mutex_name
        self._mutex_handle = None
        self._server_sock: Optional[socket.socket] = None
        self._server_thread: Optional[threading.Thread] = None
        self._running = False
        self._activate_callback: Optional[Callable[[], None]] = None

    def set_activate_callback(self, callback: Callable[[], None]):
        """Registers callback to be triggered when a secondary instance attempts to start."""
        self._activate_callback = callback

    def acquire(self) -> bool:
        """
        Attempts to acquire the single-instance lock.
        Returns True if primary instance, False if another instance is already running.
        """
        if sys.platform == "win32":
            try:
                self._mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, self.mutex_name)
                last_error = ctypes.windll.kernel32.GetLastError()
                if last_error == ERROR_ALREADY_EXISTS:
                    logger.info("[SingleInstance] Existing instance detected via Mutex. Signaling activation...")
                    self._notify_existing_instance()
                    return False
            except Exception as e:
                logger.error(f"[SingleInstance] Win32 Mutex exception: {e}")

        # Fallback PID check if non-windows
        if sys.platform != "win32" and LOCK_FILE.exists():
            try:
                data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if pid and self._is_pid_running(pid) and pid != os.getpid():
                    logger.info(f"[SingleInstance] PID {pid} is running. Signaling activation...")
                    self._notify_existing_instance(data.get("port", DEFAULT_IPC_PORT))
                    return False
            except Exception:
                pass

        # Primary instance acquired! Start the IPC server
        self._start_ipc_server()
        return True

    def _notify_existing_instance(self, fallback_port: int = DEFAULT_IPC_PORT):
        """Sends an ACTIVATE signal to the running primary instance via localhost socket."""
        target_port = fallback_port
        try:
            if LOCK_FILE.exists():
                data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
                target_port = int(data.get("port", fallback_port))
        except Exception:
            pass

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.5)
                s.connect(("127.0.0.1", target_port))
                s.sendall(b"ACTIVATE\n")
                logger.info(f"[SingleInstance] Sent ACTIVATE signal to primary instance on port {target_port}.")
        except Exception as e:
            logger.debug(f"[SingleInstance] Could not send ACTIVATE signal: {e}")

    def _start_ipc_server(self):
        """Starts a lightweight localhost TCP socket listener for activation requests."""
        self._running = True
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self._server_sock.bind(("127.0.0.1", DEFAULT_IPC_PORT))
            except Exception:
                # Bind to random OS available port if default is occupied
                self._server_sock.bind(("127.0.0.1", 0))

            bound_port = self._server_sock.getsockname()[1]
            self._server_sock.listen(5)
            self._server_sock.settimeout(1.0)

            # Write lock file with PID and Port
            LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "port": bound_port}), encoding="utf-8")

            def listen_loop():
                while self._running:
                    try:
                        client, _ = self._server_sock.accept()
                        with client:
                            data = client.recv(1024)
                            if b"ACTIVATE" in data:
                                logger.info("[SingleInstance] Received ACTIVATE signal from secondary instance.")
                                if self._activate_callback:
                                    self._activate_callback()
                    except socket.timeout:
                        continue
                    except Exception:
                        break

            self._server_thread = threading.Thread(target=listen_loop, daemon=True, name="SingleInstanceIPCListener")
            self._server_thread.start()
        except Exception as e:
            logger.warning(f"[SingleInstance] Failed to start IPC socket listener: {e}")

    def _is_pid_running(self, pid: int) -> bool:
        """Checks whether a process with the given PID is currently running."""
        if sys.platform == "win32":
            try:
                h_proc = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                if h_proc:
                    ctypes.windll.kernel32.CloseHandle(h_proc)
                    return True
                return False
            except Exception:
                return False
        else:
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

    def release(self):
        """Releases the lock, stops IPC server, and removes lockfile on exit."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if sys.platform == "win32" and self._mutex_handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self._mutex_handle)
                self._mutex_handle = None
            except Exception:
                pass

        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
        except Exception:
            pass
