import os
import sys
import time
import subprocess
import logging
import urllib.request
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

PID_FILE = ".core_ai.pid"

def is_pid_alive(pid: int) -> bool:
    """Verifies if a process ID is running using OS built-in commands."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=2.0
            )
            return str(pid) in res.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

def kill_process_tree(pid: int) -> bool:
    """Gracefully terminates a process and its child tree using OS native tools."""
    if os.name == "nt":
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                text=True,
                timeout=5.0
            )
            return res.returncode == 0
        except Exception:
            return False
    else:
        try:
            import signal
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            if is_pid_alive(pid):
                os.kill(pid, signal.SIGKILL)
            return True
        except Exception:
            return False


class ServiceManager:
    """
    Core AI Process & Service Lifecycle Manager:
    - Zero external dependencies: pure Python standard library & OS native commands.
    - Starts the microkernel in background or terminal window.
    - Gracefully stops processes to free GPU, VRAM, and RAM (for video editing/gaming).
    - Status checking via PID inspection and Gateway health probes.
    - OS Autostart configuration (Windows Startup folder and Linux systemd).
    """

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.pid_path = os.path.join(self.root_dir, PID_FILE)

    def get_running_pid(self) -> Optional[int]:
        """Returns the active PID if Core AI is currently running."""
        if not os.path.exists(self.pid_path):
            return None
        try:
            with open(self.pid_path, "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            if is_pid_alive(pid):
                return pid
            # PID file stale
            self._clear_pid()
            return None
        except Exception:
            self._clear_pid()
            return None

    def _save_pid(self, pid: int):
        with open(self.pid_path, "w", encoding="utf-8") as f:
            f.write(str(pid))

    def _clear_pid(self):
        if os.path.exists(self.pid_path):
            try:
                os.remove(self.pid_path)
            except Exception:
                pass

    def check_health(self, port: int = 8000, timeout: float = 1.0) -> Tuple[bool, Dict[str, Any]]:
        """Checks if Gateway server answers on HTTP."""
        url = f"http://localhost:{port}/api/v1/health"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CoreAI-ServiceManager"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    import json
                    return True, json.loads(resp.read().decode("utf-8"))
                return False, {"error": f"HTTP {resp.status}"}
        except Exception as e:
            return False, {"error": str(e)}

    def start(
        self,
        in_new_terminal: bool = True,
        port: int = 8000,
        extra_args: Optional[list] = None
    ) -> Tuple[bool, str]:
        """
        Starts the Core AI Server Suite.
        - in_new_terminal: launches in a visible terminal window (interactive server shell).
        - Otherwise launches as detached background daemon.
        """
        pid = self.get_running_pid()
        if pid:
            return False, f"Core AI is already running (PID {pid})."

        cmd = [sys.executable, "main.py", "--port", str(port)] + (extra_args or [])

        try:
            if in_new_terminal:
                if os.name == "nt":
                    proc = subprocess.Popen(
                        ["cmd.exe", "/k", "title Core AI Server Suite &&"] + cmd,
                        cwd=self.root_dir,
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
                else:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=self.root_dir,
                        stdout=open(os.path.join(self.root_dir, "logs", "server_stdout.log"), "a"),
                        stderr=subprocess.STDOUT
                    )
            else:
                log_file = open(os.path.join(self.root_dir, "logs", "server_daemon.log"), "a")
                flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                proc = subprocess.Popen(
                    cmd,
                    cwd=self.root_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=flags
                )

            self._save_pid(proc.pid)
            logger.info(f"Core AI server started with PID {proc.pid}")
            return True, f"Core AI server started successfully (PID {proc.pid}) on port {port}."
        except Exception as e:
            return False, f"Failed to start Core AI server: {e}"

    def stop(self) -> Tuple[bool, str]:
        """
        Gracefully stops Core AI, freeing RAM, GPU, VRAM, and ports for video editing / gaming.
        """
        pid = self.get_running_pid()
        if not pid:
            return False, "Core AI is not currently running."

        try:
            kill_process_tree(pid)
            self._clear_pid()
            logger.info(f"Core AI (PID {pid}) stopped successfully.")
            return True, f"Core AI server (PID {pid}) stopped. GPU and RAM freed."
        except Exception as e:
            self._clear_pid()
            return False, f"Error while stopping Core AI: {e}"

    def status(self, port: int = 8000) -> Dict[str, Any]:
        """Returns detailed process and gateway health status."""
        pid = self.get_running_pid()
        is_healthy, health_data = self.check_health(port=port)

        info = {
            "is_running": pid is not None,
            "pid": pid,
            "gateway_healthy": is_healthy,
            "port": port,
            "details": health_data
        }

        return info

    def get_autostart_path(self) -> Optional[str]:
        """Returns the OS-specific autostart file path."""
        if os.name == "nt":
            appdata = os.getenv("APPDATA")
            if appdata:
                return os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup\CoreAI_Startup.bat")
        else:
            home = os.path.expanduser("~")
            return os.path.join(home, ".config", "autostart", "core-ai.desktop")
        return None

    def enable_autostart(self, in_terminal: bool = True) -> Tuple[bool, str]:
        """Configures OS autostart so Core AI boots with the system."""
        path = self.get_autostart_path()
        if not path:
            return False, "Unsupported platform for automated autostart configuration."

        os.makedirs(os.path.dirname(path), exist_ok=True)

        if os.name == "nt":
            python_exe = sys.executable
            main_script = os.path.join(self.root_dir, "main.py")
            content = f'@echo off\r\ntitle Core AI Server Suite\r\ncd /d "{self.root_dir}"\r\n"{python_exe}" "{main_script}"\r\n'
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True, f"Windows autostart enabled at '{path}'."
            except Exception as e:
                return False, f"Failed to write autostart file: {e}"
        else:
            python_exe = sys.executable
            main_script = os.path.join(self.root_dir, "main.py")
            content = f"[Desktop Entry]\nType=Application\nName=Core AI Server\nExec={python_exe} {main_script}\nPath={self.root_dir}\nTerminal={str(in_terminal).lower()}\n"
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True, f"Linux desktop autostart enabled at '{path}'."
            except Exception as e:
                return False, f"Failed to write desktop autostart file: {e}"

    def disable_autostart(self) -> Tuple[bool, str]:
        """Removes the OS autostart file."""
        path = self.get_autostart_path()
        if path and os.path.exists(path):
            try:
                os.remove(path)
                return True, f"Autostart disabled (removed '{path}')."
            except Exception as e:
                return False, f"Failed to remove autostart file: {e}"
        return True, "Autostart was not enabled."
