import os
import sys
import time
import subprocess
import logging
import urllib.request
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

PID_FILE = ".core_ai.pid"
WATCHDOG_PID_FILE = ".core_watchdog.pid"

def is_pid_alive(pid: int) -> bool:
    """Verifies if a process ID is running using OS built-in commands."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x00100000, False, pid)
            if handle != 0:
                kernel32.CloseHandle(handle)
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

def kill_process_tree(pid: int) -> bool:
    """Gracefully terminates a process and its child tree using OS native tools."""
    if os.name == "nt":
        try:
            taskkill_bin = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
            if not os.path.exists(taskkill_bin):
                taskkill_bin = "taskkill"
            res = subprocess.run(
                [taskkill_bin, "/F", "/T", "/PID", str(pid)],
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

    def get_watchdog_pid(self) -> Optional[int]:
        """Returns the active PID if Watchdog Supervisor is currently running."""
        w_path = os.path.join(self.root_dir, WATCHDOG_PID_FILE)
        if not os.path.exists(w_path):
            return None
        try:
            with open(w_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return None
                pid = int(content)
            if is_pid_alive(pid):
                return pid
            self._clear_watchdog_pid()
            return None
        except Exception:
            self._clear_watchdog_pid()
            return None

    def _clear_watchdog_pid(self):
        w_path = os.path.join(self.root_dir, WATCHDOG_PID_FILE)
        if os.path.exists(w_path):
            try:
                os.remove(w_path)
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

        os.makedirs(os.path.join(self.root_dir, "logs"), exist_ok=True)
        args_to_use = list(extra_args or [])
        if not in_new_terminal and "--headless" not in args_to_use:
            args_to_use.append("--headless")

        executable = sys.executable
        if not in_new_terminal and os.name == "nt":
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.exists(pythonw):
                executable = pythonw

        cmd = [executable, "main.py", "--port", str(port)] + args_to_use

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
                flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
                proc = subprocess.Popen(
                    cmd,
                    cwd=self.root_dir,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
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
        Also terminates any active Watchdog supervisor to prevent unwanted revival.
        """
        watchdog_pid = self.get_watchdog_pid()
        watchdog_msg = ""
        if watchdog_pid:
            kill_process_tree(watchdog_pid)
            self._clear_watchdog_pid()
            watchdog_msg = f" (Watchdog PID {watchdog_pid} stopped)"

        pid = self.get_running_pid()
        if not pid:
            if watchdog_msg:
                return True, f"Core AI Watchdog supervisor stopped.{watchdog_msg}"
            return False, "Core AI is not currently running."

        try:
            kill_process_tree(pid)
            self._clear_pid()
            logger.info(f"Core AI (PID {pid}) stopped successfully.")
            return True, f"Core AI server (PID {pid}) stopped. GPU and RAM freed.{watchdog_msg}"
        except Exception as e:
            self._clear_pid()
            return False, f"Error while stopping Core AI: {e}"

    def status(self, port: int = 8000) -> Dict[str, Any]:
        """Returns detailed process, supervisor, and gateway health status."""
        pid = self.get_running_pid()
        watchdog_pid = self.get_watchdog_pid()
        is_healthy, health_data = self.check_health(port=port)

        info = {
            "is_running": pid is not None,
            "pid": pid,
            "watchdog_running": watchdog_pid is not None,
            "watchdog_pid": watchdog_pid,
            "gateway_healthy": is_healthy,
            "port": port,
            "details": health_data
        }

        return info

    def print_status_card(self, port: int = 8000):
        """Prints a high-contrast terminal status card."""
        info = self.status(port=port)
        running = info["is_running"]
        gw_ok = info["gateway_healthy"]
        details = info.get("details", {})

        try:
            from colorama import init, Fore, Style
            init(autoreset=True)
            G, C, Y, R, B, RST = Fore.GREEN, Fore.CYAN, Fore.YELLOW, Fore.RED, Style.BRIGHT, Style.RESET_ALL
        except ImportError:
            G = C = Y = R = B = RST = ""

        print(f"\n{C}+=====================================================================+{RST}")
        print(f"{C}|{B}   CORE AI :: DAEMON & GATEWAY STATUS CARD                           {RST}{C}|{RST}")
        print(f"{C}+=====================================================================+{RST}")
        daemon_str = f"{G}ONLINE (PID {info['pid']}){RST}" if running else f"{Y}OFFLINE{RST}"
        watchdog_str = f"{G}ONLINE (PID {info['watchdog_pid']}, Self-Healing){RST}" if info.get("watchdog_running") else f"{Y}STANDALONE (No Watchdog){RST}"
        gateway_str = f"{G}ONLINE (http://localhost:{port}){RST}" if gw_ok else f"{Y}OFFLINE{RST}"
        print(f"{C}|{RST}   Daemon Process:       {daemon_str}")
        print(f"{C}|{RST}   Watchdog Supervisor:  {watchdog_str}")
        print(f"{C}|{RST}   Universal Gateway:    {gateway_str}")
        if gw_ok and isinstance(details, dict):
            print(f"{C}|{RST}   Active Operator:      {G}{details.get('active_user', 'N/A')}{RST}")
            print(f"{C}|{RST}   Active Model:         {C}{details.get('active_model', 'N/A')}{RST}")
            print(f"{C}|{RST}   Connected Nodes:      {Y}{len(details.get('connected_edge_nodes', []))}{RST}")
        print(f"{C}+=====================================================================+{RST}\n")

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

    def is_autostart_enabled(self) -> bool:
        """Returns True if OS autostart is currently configured."""
        path = self.get_autostart_path()
        return bool(path and os.path.exists(path))

    def enable_autostart(self, in_terminal: bool = False, use_watchdog: bool = True) -> Tuple[bool, str]:
        """Configures OS autostart so Core AI boots with the system as a 24/7 background service."""
        path = self.get_autostart_path()
        if not path:
            return False, "Unsupported platform for automated autostart configuration."

        os.makedirs(os.path.dirname(path), exist_ok=True)

        if os.name == "nt":
            if in_terminal:
                content = (
                    "@echo off\r\n"
                    f'cd /d "{self.root_dir}"\r\n'
                    "call core.bat run\r\n"
                )
            else:
                if use_watchdog:
                    content = (
                        "@echo off\r\n"
                        f'cd /d "{self.root_dir}"\r\n'
                        'if exist ".venv\\Scripts\\pythonw.exe" (\r\n'
                        '    start "" /b ".venv\\Scripts\\pythonw.exe" -m core.watchdog\r\n'
                        ") else (\r\n"
                        "    call core.bat watchdog\r\n"
                        ")\r\n"
                    )
                else:
                    content = (
                        "@echo off\r\n"
                        f'cd /d "{self.root_dir}"\r\n'
                        "call core.bat start\r\n"
                    )
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                mode_desc = "Interactive Terminal" if in_terminal else ("24/7 Self-Healing Watchdog" if use_watchdog else "24/7 Silent Daemon")
                return True, f"Windows autostart enabled ({mode_desc}) at '{path}'."
            except Exception as e:
                return False, f"Failed to write autostart file: {e}"
        else:
            python_exe = os.path.join(self.root_dir, ".venv", "bin", "python")
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            main_target = f"{python_exe} -m core.watchdog" if use_watchdog else f"{python_exe} main.py --headless"
            if in_terminal:
                main_target = f"bash -c 'cd \"{self.root_dir}\" && ./core.sh run'"
            content = f"[Desktop Entry]\nType=Application\nName=Core AI Server\nExec={main_target}\nPath={self.root_dir}\nTerminal={str(in_terminal).lower()}\n"
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

    def print_autostart_card(self):
        """Prints a high-contrast autostart status overview."""
        try:
            from colorama import init, Fore, Style
            init(autoreset=True)
            G, C, Y, R, B, RST = Fore.GREEN, Fore.CYAN, Fore.YELLOW, Fore.RED, Style.BRIGHT, Style.RESET_ALL
        except ImportError:
            G = C = Y = R = B = RST = ""

        enabled = self.is_autostart_enabled()
        path = self.get_autostart_path()
        status_lbl = f"{G}ENABLED (Active on Boot){RST}" if enabled else f"{Y}DISABLED{RST}"

        print(f"\n{C}+=====================================================================+{RST}")
        print(f"{C}|{B}   CORE AI :: 24/7 ALWAYS-ON AUTOSTART STATUS                        {RST}{C}|{RST}")
        print(f"{C}+=====================================================================+{RST}")
        print(f"{C}|{RST}   Autostart on Boot:  {status_lbl}")
        print(f"{C}|{RST}   Supervisor Mode:    {G}Self-Healing 24/7 Watchdog{RST}")
        print(f"{C}|{RST}   Startup Path:       {path}")
        print(f"{C}|{RST}   Service Mode:       {G}24/7 Sovereign Main Server{RST}")
        print(f"{C}+=====================================================================+{RST}\n")
        print(f"  To manage autostart:")
        print(f"    core autostart on       (Enable silent 24/7 background boot with Watchdog)")
        print(f"    core autostart off      (Disable automatic boot)")
        print(f"    core autostart visible  (Enable interactive terminal console on boot)")
        print(f"    core autostart status   (Check autostart configuration)\n")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Core AI Service Manager CLI")
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "autostart"], help="Action to execute")
    parser.add_argument("subaction", nargs="?", default=None, help="Subaction (for autostart: on, off, status, visible)")
    args = parser.parse_args()

    sm = ServiceManager()
    if args.action == "start":
        ok, msg = sm.start(in_new_terminal=False, extra_args=["--headless"])
        print(msg)
    elif args.action == "stop":
        ok, msg = sm.stop()
        print(msg)
    elif args.action == "restart":
        sm.stop()
        ok, msg = sm.start(in_new_terminal=False, extra_args=["--headless"])
        print(msg)
    elif args.action == "status":
        sm.print_status_card()
    elif args.action == "autostart":
        sub = (args.subaction or "status").lower()
        if sub in ["status", "card", "info"]:
            sm.print_autostart_card()
        elif sub in ["on", "enable", "yes"]:
            ok, msg = sm.enable_autostart(in_terminal=False, use_watchdog=True)
            print(msg)
        elif sub in ["off", "disable", "no"]:
            ok, msg = sm.disable_autostart()
            print(msg)
        elif sub in ["visible", "console", "terminal"]:
            ok, msg = sm.enable_autostart(in_terminal=True, use_watchdog=False)
            print(msg)
        else:
            print(f"Unknown autostart subaction: '{args.subaction}'. Valid options: on, off, status, visible")
            sm.print_autostart_card()
