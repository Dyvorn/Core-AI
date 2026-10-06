import os
import sys
import time
import platform
import subprocess
import logging
import urllib.request
from typing import Optional, Dict, Any, Tuple, List

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


def get_host_vitals(pid: Optional[int] = None) -> Dict[str, Any]:
    """
    Introspects host hardware, system RAM, CPU cores, and process memory
    using pure standard library (ctypes on Windows, /proc on Linux).
    Zero external dependencies.
    """
    vitals: Dict[str, Any] = {
        "platform": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "cpu_count": os.cpu_count() or 1,
        "total_ram_gb": 0.0,
        "avail_ram_gb": 0.0,
        "ram_used_percent": 0.0,
        "process_rss_mb": None,
        "gpu_hardware": "CPU / Integrated Silicon"
    }

    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', wintypes.DWORD),
                    ('dwMemoryLoad', wintypes.DWORD),
                    ('ullTotalPhys', ctypes.c_uint64),
                    ('ullAvailPhys', ctypes.c_uint64),
                    ('ullTotalPageFile', ctypes.c_uint64),
                    ('ullAvailPageFile', ctypes.c_uint64),
                    ('ullTotalVirtual', ctypes.c_uint64),
                    ('ullAvailVirtual', ctypes.c_uint64),
                    ('sullAvailExtendedVirtual', ctypes.c_uint64),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total = stat.ullTotalPhys / (1024 ** 3)
                avail = stat.ullAvailPhys / (1024 ** 3)
                vitals["total_ram_gb"] = round(total, 2)
                vitals["avail_ram_gb"] = round(avail, 2)
                vitals["ram_used_percent"] = round(((total - avail) / total) * 100, 1) if total > 0 else 0.0
        except Exception:
            pass

        if pid and pid > 0:
            try:
                import ctypes
                from ctypes import wintypes
                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ('cb', wintypes.DWORD),
                        ('PageFaultCount', wintypes.DWORD),
                        ('PeakWorkingSetSize', ctypes.c_size_t),
                        ('WorkingSetSize', ctypes.c_size_t),
                        ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                        ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                        ('PagefileUsage', ctypes.c_size_t),
                        ('PeakPagefileUsage', ctypes.c_size_t),
                    ]
                handle = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
                if handle:
                    pmc = PROCESS_MEMORY_COUNTERS()
                    pmc.cb = ctypes.sizeof(pmc)
                    if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                        vitals["process_rss_mb"] = round(pmc.WorkingSetSize / (1024 * 1024), 2)
                    ctypes.windll.kernel32.CloseHandle(handle)
            except Exception:
                pass
    else:
        # Linux / Unix
        try:
            if os.path.exists("/proc/meminfo"):
                mem: Dict[str, str] = {}
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            mem[parts[0].strip()] = parts[1].strip().split()[0]
                if "MemTotal" in mem and "MemAvailable" in mem:
                    total = int(mem["MemTotal"]) / (1024 * 1024)
                    avail = int(mem["MemAvailable"]) / (1024 * 1024)
                    vitals["total_ram_gb"] = round(total, 2)
                    vitals["avail_ram_gb"] = round(avail, 2)
                    vitals["ram_used_percent"] = round(((total - avail) / total) * 100, 1) if total > 0 else 0.0
        except Exception:
            pass

        if pid and pid > 0:
            try:
                status_path = f"/proc/{pid}/status"
                if os.path.exists(status_path):
                    with open(status_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                rss_kb = int(line.split(":")[1].strip().split()[0])
                                vitals["process_rss_mb"] = round(rss_kb / 1024, 2)
                                break
            except Exception:
                pass

    return vitals


class ServiceManager:
    """
    Core AI Process & Service Lifecycle Manager:
    - Zero external dependencies: pure Python standard library & OS native commands.
    - Starts the microkernel in background or terminal window.
    - Gracefully stops processes to free GPU, VRAM, and RAM (for video editing/gaming).
    - Status checking via PID inspection and Gateway health probes.
    - Real-time Hardware Metrics & Terminal Vitals Cards.
    - OS Autostart configuration (Windows Startup, Linux systemd, and desktop autostart).
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

    @staticmethod
    def get_lan_ip() -> str:
        """Returns the primary outbound LAN IPv4 address."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

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
        lan_ip = self.get_lan_ip()
        lan_suffix = f" | LAN: http://{lan_ip}:{port}" if lan_ip and lan_ip != "127.0.0.1" else ""
        gateway_str = f"{G}ONLINE (http://localhost:{port}{lan_suffix}){RST}" if gw_ok else f"{Y}OFFLINE{RST}"
        print(f"{C}|{RST}   Daemon Process:       {daemon_str}")
        print(f"{C}|{RST}   Watchdog Supervisor:  {watchdog_str}")
        print(f"{C}|{RST}   Universal Gateway:    {gateway_str}")
        if gw_ok and isinstance(details, dict):
            print(f"{C}|{RST}   Active Operator:      {G}{details.get('active_user', 'N/A')}{RST}")
            print(f"{C}|{RST}   Active Model:         {C}{details.get('active_model', 'N/A')}{RST}")
            print(f"{C}|{RST}   Connected Nodes:      {Y}{len(details.get('connected_edge_nodes', []))}{RST}")
        print(f"{C}+=====================================================================+{RST}\n")

    @classmethod
    def get_system_metrics(
        cls,
        state_manager=None,
        planner=None,
        connection_manager=None,
        registry=None,
        root_dir: Optional[str] = None,
        port: int = 8000
    ) -> Dict[str, Any]:
        """
        Gathers comprehensive telemetry covering host vitals, memory footprint,
        storage usage, and mesh nodes.
        """
        root = root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        sm = cls(root_dir=root)
        running_pid = sm.get_running_pid()
        vitals = get_host_vitals(pid=running_pid)

        # Database metrics
        db_path = os.path.join(root, "core_ai.db")
        db_size_kb = round(os.path.getsize(db_path) / 1024, 2) if os.path.exists(db_path) else 0.0

        zones_count = 0
        devices_count = 0
        routes_count = 0
        if state_manager:
            try:
                zones_count = len(state_manager.list_zones())
                devices_count = len(state_manager.list_all_devices())
                routes_count = len(state_manager.list_all_audio_routes())
            except Exception:
                pass

        edge_nodes = []
        broadcast_count = 0
        if connection_manager:
            edge_nodes = list(connection_manager.edge_nodes.keys())
            broadcast_count = len(connection_manager.broadcast_clients)

        active_user = "Operator"
        if state_manager:
            try:
                active_user = state_manager.get_user_profile().preferred_name
            except Exception:
                pass

        active_model = "heuristic"
        if planner and hasattr(planner, "get_active_model"):
            active_model = planner.get_active_model() or "heuristic"

        tools_count = len(registry.tools) if registry else 0

        lan_ip = cls.get_lan_ip()

        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "process": {
                "pid": running_pid,
                "watchdog_pid": sm.get_watchdog_pid(),
                "memory_rss_mb": vitals["process_rss_mb"]
            },
            "host": {
                "platform": vitals["platform"],
                "architecture": vitals["architecture"],
                "cpu_cores": vitals["cpu_count"],
                "total_ram_gb": vitals["total_ram_gb"],
                "avail_ram_gb": vitals["avail_ram_gb"],
                "ram_used_percent": vitals["ram_used_percent"],
                "gpu": vitals["gpu_hardware"]
            },
            "storage": {
                "db_path": db_path,
                "db_size_kb": db_size_kb,
                "zones_count": zones_count,
                "devices_count": devices_count,
                "audio_routes_count": routes_count
            },
            "network": {
                "port": port,
                "lan_ip": lan_ip,
                "local_url": f"http://localhost:{port}",
                "lan_url": f"http://{lan_ip}:{port}",
                "active_edge_nodes": edge_nodes,
                "edge_nodes_count": len(edge_nodes),
                "broadcast_clients_count": broadcast_count
            },
            "system": {
                "active_user": active_user,
                "active_model": active_model,
                "registered_tools_count": tools_count
            }
        }

    def print_metrics_card(self, port: int = 8000):
        """Prints a high-contrast terminal telemetry card."""
        info = self.status(port=port)
        running = info["is_running"]
        gw_ok = info["gateway_healthy"]
        pid = info["pid"]

        vitals = get_host_vitals(pid=pid)
        lan_ip = self.get_lan_ip()
        db_path = os.path.join(self.root_dir, "core_ai.db")
        db_size_kb = round(os.path.getsize(db_path) / 1024, 2) if os.path.exists(db_path) else 0.0

        details = info.get("details", {})

        try:
            from colorama import init, Fore, Style
            init(autoreset=True)
            G, C, Y, R, B, RST = Fore.GREEN, Fore.CYAN, Fore.YELLOW, Fore.RED, Style.BRIGHT, Style.RESET_ALL
        except ImportError:
            G = C = Y = R = B = RST = ""

        print(f"\n{C}+=====================================================================+{RST}")
        print(f"{C}|{B}   CORE AI :: SOVEREIGN SERVER TELEMETRY & HARDWARE VITALS           {RST}{C}|{RST}")
        print(f"{C}+=====================================================================+{RST}")
        daemon_str = f"{G}ONLINE (PID {pid}){RST}" if running else f"{Y}OFFLINE{RST}"
        watchdog_str = f"{G}ONLINE (PID {info['watchdog_pid']}, Self-Healing){RST}" if info.get("watchdog_running") else f"{Y}STANDALONE (No Watchdog){RST}"
        print(f"{C}|{RST}   Daemon Process:       {daemon_str}")
        print(f"{C}|{RST}   Supervisor:           {watchdog_str}")

        rss_str = f"{vitals['process_rss_mb']} MB RSS" if vitals["process_rss_mb"] is not None else "N/A"
        print(f"{C}|{RST}   Memory Footprint:     {G}{rss_str}{RST}")
        print(f"{C}+---------------------------------------------------------------------+{RST}")
        print(f"{C}|{RST}   Host Platform:        {C}{vitals['platform']} ({vitals['architecture']}, {vitals['cpu_count']} Cores){RST}")
        used_ram = round(vitals['total_ram_gb'] - vitals['avail_ram_gb'], 2)
        print(f"{C}|{RST}   System RAM:           {Y}{used_ram} GB Used / {vitals['total_ram_gb']} GB Total ({vitals['ram_used_percent']}%){RST}")
        print(f"{C}|{RST}   GPU Hardware:         {vitals['gpu_hardware']}")
        print(f"{C}+---------------------------------------------------------------------+{RST}")
        print(f"{C}|{RST}   Local Endpoint:       http://localhost:{port}")
        lan_url = f"http://{lan_ip}:{port}" if lan_ip != "127.0.0.1" else "http://localhost:8000"
        print(f"{C}|{RST}   LAN Mesh Ingress:     {G}{lan_url}{RST}")
        print(f"{C}|{RST}   WebSocket Stream:     ws://{lan_ip}:{port}/ws/events")
        print(f"{C}|{RST}   Edge Node RPC:        ws://{lan_ip}:{port}/ws/nodes/<id>")
        print(f"{C}|{RST}   LAN Discovery Beacon: {G}UDP Port 8008 (Broadcasting on LAN){RST}")
        print(f"{C}+---------------------------------------------------------------------+{RST}")
        active_user = details.get("active_user", "Operator") if gw_ok else "Dyvorn"
        active_model = details.get("active_model", "heuristic") if gw_ok else "N/A"
        nodes_count = len(details.get("connected_edge_nodes", [])) if gw_ok else 0
        print(f"{C}|{RST}   Active Operator:      {G}{active_user} (SOVEREIGN OWNER){RST}")
        print(f"{C}|{RST}   Cognitive Engine:     {C}{active_model}{RST}")
        print(f"{C}|{RST}   Connected Edge Nodes: {Y}{nodes_count} active connected{RST}")
        print(f"{C}|{RST}   SQLite Database:      {db_size_kb} KB ({db_path})")
        print(f"{C}+=====================================================================+{RST}\n")

    def generate_systemd_service(self, user: Optional[str] = None, port: int = 8000) -> str:
        """
        Generates production-grade systemd service unit file content for dedicated Linux/Fedora servers.
        """
        run_user = user or os.environ.get("USER", "root")
        python_bin = os.path.join(self.root_dir, ".venv", "bin", "python")
        if not os.path.exists(python_bin):
            python_bin = sys.executable

        service_unit = (
            "[Unit]\n"
            "Description=Core AI Sovereign Microkernel & Universal Gateway (24/7 Always-On)\n"
            "After=network.target network-online.target\n"
            "Wants=network-online.target\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"User={run_user}\n"
            f"WorkingDirectory={self.root_dir}\n"
            f"ExecStart={python_bin} -m core.watchdog --port {port}\n"
            "Restart=always\n"
            "RestartSec=5\n"
            "KillMode=process\n"
            "TimeoutStopSec=15\n"
            "Environment=PYTHONUNBUFFERED=1\n"
            f"Environment=CORE_PORT={port}\n"
            "Environment=CORE_HOST=0.0.0.0\n\n"
            "# Production Security Sandboxing\n"
            "ProtectSystem=full\n"
            "NoNewPrivileges=true\n\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )
        return service_unit

    def install_systemd_service(self, user: Optional[str] = None, port: int = 8000) -> Tuple[bool, str]:
        """
        Installs systemd service on Linux servers.
        """
        if os.name == "nt":
            return False, "systemd is only available on Linux operating systems."

        content = self.generate_systemd_service(user=user, port=port)
        systemd_path = "/etc/systemd/system/core-ai.service"
        try:
            with open(systemd_path, "w", encoding="utf-8") as f:
                f.write(content)
            # Try reloading systemd
            subprocess.run(["systemctl", "daemon-reload"], check=False)
            return True, f"Installed systemd unit to '{systemd_path}'. Enable with: sudo systemctl enable --now core-ai"
        except PermissionError:
            # Fallback to local user unit
            user_unit_dir = os.path.expanduser("~/.config/systemd/user")
            os.makedirs(user_unit_dir, exist_ok=True)
            user_path = os.path.join(user_unit_dir, "core-ai.service")
            with open(user_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, f"Installed user systemd unit to '{user_path}'. Enable with: systemctl --user enable --now core-ai"
        except Exception as e:
            return False, f"Failed to install systemd service: {e}"

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
        print(f"    core autostart systemd  (Generate/Install Linux systemd production service)")
        print(f"    core autostart status   (Check autostart configuration)\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Core AI Service Manager CLI")
    parser.add_argument("action", choices=["start", "stop", "restart", "status", "metrics", "vitals", "autostart"], help="Action to execute")
    parser.add_argument("subaction", nargs="?", default=None, help="Subaction (for autostart: on, off, status, visible, systemd)")
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
    elif args.action in ["metrics", "vitals"]:
        sm.print_metrics_card()
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
        elif sub in ["systemd", "linux"]:
            if os.name == "nt":
                print("\nGenerated Linux systemd unit file specimen:\n")
                print(sm.generate_systemd_service())
            else:
                ok, msg = sm.install_systemd_service()
                print(msg)
        else:
            print(f"Unknown autostart subaction: '{args.subaction}'. Valid options: on, off, status, visible, systemd")
            sm.print_autostart_card()
