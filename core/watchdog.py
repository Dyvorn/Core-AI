import os
import sys
import time
import signal
import logging
import subprocess
from typing import Optional, List

logger = logging.getLogger("CoreAI.Watchdog")

WATCHDOG_PID_FILE = ".core_watchdog.pid"

class WatchdogDaemon:
    """
    Self-Healing 24/7 Process Supervisor for Core AI Sovereign Main Server:
    - Continuously monitors the Core AI microkernel process.
    - If Core AI terminates unexpectedly (exit code != 0 or unhandled crash),
      automatically revives it with exponential backoff defense.
    - Gracefully handles SIGINT/SIGTERM by stopping the server cleanly.
    - Zero external dependencies: pure standard library.
    """

    def __init__(
        self,
        root_dir: Optional[str] = None,
        port: int = 8000,
        extra_args: Optional[List[str]] = None,
        max_consecutive_crashes: int = 5
    ):
        self.root_dir = root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.port = port
        self.extra_args = list(extra_args or ["--headless"])
        self.max_consecutive_crashes = max_consecutive_crashes
        self.stop_requested = False
        self.current_process: Optional[subprocess.Popen] = None
        self.log_file = os.path.join(self.root_dir, "logs", "watchdog.log")

    def _log(self, message: str):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [WATCHDOG] {message}\n"
        if sys.stdout:
            try:
                sys.stdout.write(entry)
                sys.stdout.flush()
            except Exception:
                pass
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass

    def _save_pid(self):
        pid_path = os.path.join(self.root_dir, WATCHDOG_PID_FILE)
        try:
            with open(pid_path, "w", encoding="utf-8") as f:
                f.write(str(os.getpid()))
        except Exception:
            pass

    def _clear_pid(self):
        pid_path = os.path.join(self.root_dir, WATCHDOG_PID_FILE)
        if os.path.exists(pid_path):
            try:
                os.remove(pid_path)
            except Exception:
                pass

    def _handle_signal(self, signum, frame):
        self._log(f"Received termination signal ({signum}). Gracefully stopping Core AI...")
        self.stop_requested = True
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self.current_process.kill()

    def run(self):
        self._save_pid()
        self._log(f"Starting Core AI 24/7 Always-On Watchdog on port {self.port} (Root: {self.root_dir})...")

        # Register signal handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        executable = sys.executable
        if os.name == "nt":
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.exists(pythonw):
                executable = pythonw

        cmd = [executable, "main.py", "--port", str(self.port)] + self.extra_args
        consecutive_crashes = 0
        server_log_path = os.path.join(self.root_dir, "logs", "server_stdout.log")
        os.makedirs(os.path.dirname(server_log_path), exist_ok=True)

        try:
            while not self.stop_requested:
                self._log(f"Spawning Core AI instance (command: {' '.join(cmd)})...")
                start_time = time.time()

                try:
                    try:
                        log_out = open(server_log_path, "a", encoding="utf-8")
                    except Exception:
                        log_out = subprocess.DEVNULL

                    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if (os.name == "nt" and "--headless" in self.extra_args) else 0

                    self.current_process = subprocess.Popen(
                        cmd,
                        cwd=self.root_dir,
                        stdin=subprocess.DEVNULL,
                        stdout=log_out,
                        stderr=subprocess.STDOUT,
                        creationflags=flags
                    )
                except Exception as e:
                    self._log(f"Failed to spawn Core AI process: {e}")
                    time.sleep(5.0)
                    continue

                self._log(f"Core AI running with PID {self.current_process.pid}.")

                # Monitor process lifecycle
                while not self.stop_requested:
                    ret_code = self.current_process.poll()
                    if ret_code is not None:
                        # Process terminated
                        run_duration = time.time() - start_time
                        if ret_code == 0:
                            self._log(f"Core AI process exited normally (code 0) after {run_duration:.1f}s.")
                            self.stop_requested = True
                            break
                        else:
                            self._log(f"CRASH DETECTED: Core AI process terminated unexpectedly with code {ret_code} after {run_duration:.1f}s.")
                            if run_duration < 10.0:
                                consecutive_crashes += 1
                            else:
                                consecutive_crashes = 1  # Reset if ran stably for a while

                            if consecutive_crashes >= self.max_consecutive_crashes:
                                self._log(f"DEFENSE TRIGGERED: Reached {consecutive_crashes} consecutive rapid crashes. Pausing for 30s before retry.")
                                time.sleep(30.0)
                                consecutive_crashes = 0
                            else:
                                backoff = min(2 ** consecutive_crashes, 10)
                                self._log(f"Self-healing revival in {backoff}s...")
                                time.sleep(backoff)
                            break

                    time.sleep(2.0)

        finally:
            self._clear_pid()
            self._log("Core AI Watchdog stopped cleanly.")

def get_watchdog_pid(root_dir: Optional[str] = None) -> Optional[int]:
    """Returns the watchdog PID if running, else None."""
    root = root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    from core.service import ServiceManager
    return ServiceManager(root).get_watchdog_pid()

def is_watchdog_running(root_dir: Optional[str] = None) -> bool:
    """Returns True if watchdog supervisor is active."""
    return get_watchdog_pid(root_dir) is not None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Core AI Self-Healing 24/7 Watchdog Supervisor")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind Core AI Gateway")
    parser.add_argument("--visible", action="store_true", help="Run with visible server shell")
    parser.add_argument("--status", action="store_true", help="Check if watchdog is running")
    parser.add_argument("--stop", action="store_true", help="Stop running watchdog supervisor")
    args = parser.parse_args()

    if args.status:
        pid = get_watchdog_pid()
        if pid:
            print(f"[OK] Core AI Watchdog is running with PID {pid}.")
        else:
            print("[INFO] Core AI Watchdog is not running.")
        sys.exit(0)

    if args.stop:
        from core.service import ServiceManager
        sm = ServiceManager()
        ok, msg = sm.stop()
        print(msg)
        sys.exit(0)

    extra = [] if args.visible else ["--headless"]
    watchdog = WatchdogDaemon(port=args.port, extra_args=extra)
    watchdog.run()

if __name__ == "__main__":
    main()
