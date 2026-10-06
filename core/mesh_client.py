import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple, List, Callable
from datetime import datetime, timezone

from core.state import StateManager
from core.schemas import UserProfile, ZoneRecord, DeviceTopologyRecord, AudioRouteRecord

logger = logging.getLogger(__name__)

class MeshClient:
    """
    Intercontinental Mesh & Sovereign Client:
    - Supports two operational roles: 'main_server' (the central 24/7 host) and 'edge_node' (roaming phone/laptop).
    - In 'edge_node' mode, dispatches goals to the central server across LAN, Tailscale, or WAN.
    - Autonomous Local Fallback: If the central server is down, disconnected, or unreachable,
      the node executes the goal locally on its own silicon with local tools/models.
    - Zero lock-out: User is informed transparently with a diagnostic fallback notice.
    - Machine Migration: Exports and imports full system state bundles for switching the main server.
    """

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        role: str = "main_server",
        main_server_url: str = "http://localhost:8000",
        node_id: str = "roaming_client",
        auth_secret: str = "core_sovereign_secret"
    ):
        self.state_manager = state_manager or StateManager()
        self.role = role
        self.main_server_url = main_server_url.rstrip("/")
        self.node_id = node_id
        self.auth_secret = auth_secret
        self.offline_buffer: List[Dict[str, Any]] = []
        self._load_configuration()

    def _load_configuration(self):
        """Loads node role and server URL from operator profile preferences."""
        try:
            profile = self.state_manager.get_user_profile()
            mesh_prefs = profile.preferences.get("mesh", {})
            if "role" in mesh_prefs:
                self.role = mesh_prefs["role"]
            if "main_server_url" in mesh_prefs:
                self.main_server_url = mesh_prefs["main_server_url"].rstrip("/")
            if "node_id" in mesh_prefs:
                self.node_id = mesh_prefs["node_id"]
        except Exception as e:
            logger.debug(f"Could not load mesh preferences: {e}")

    def save_configuration(self, role: str, main_server_url: Optional[str] = None):
        """Persists mesh configuration to SQLite."""
        profile = self.state_manager.get_user_profile()
        if "mesh" not in profile.preferences:
            profile.preferences["mesh"] = {}
        profile.preferences["mesh"]["role"] = role
        self.role = role
        if main_server_url:
            self.main_server_url = main_server_url.rstrip("/")
            profile.preferences["mesh"]["main_server_url"] = self.main_server_url
        self.state_manager.save_user_profile(profile)
        logger.info(f"Updated mesh configuration: role='{self.role}', main_server='{self.main_server_url}'")

    def ping_main_server(self, timeout: float = 1.5) -> Tuple[bool, Dict[str, Any]]:
        """
        Checks if the central main server is reachable.
        Returns: (is_online, response_dict_or_error)
        """
        url = f"{self.main_server_url}/api/v1/health"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"CoreAI-Mesh/{self.node_id}"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return True, data
                return False, {"error": f"HTTP {resp.status}"}
        except Exception as e:
            return False, {"error": str(e)}

    def execute_over_mesh(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        local_executor: Optional[Callable[[str, Optional[Dict[str, Any]]], Any]] = None,
        on_fallback_notice: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes an operational goal:
        - If main_server: runs directly via local executor.
        - If edge_node: attempts remote execution via main server REST API.
        - If main server is unreachable: falls back gracefully to local autonomous execution.
        """
        if self.role == "main_server" or not self.main_server_url:
            if local_executor:
                return local_executor(goal, context)
            return {"status": "error", "message": "No local executor configured on main_server node."}

        # Edge node: Check if main server is online
        is_online, info = self.ping_main_server()
        if is_online:
            try:
                endpoint = f"{self.main_server_url}/api/v1/pipeline/solve_sync"
                payload = json.dumps({
                    "goal": goal,
                    "context": {**(context or {}), "source_node": self.node_id}
                }).encode("utf-8")

                req = urllib.request.Request(
                    endpoint,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Trust-Tier": "owner",
                        "X-Node-Id": self.node_id
                    },
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    if resp.status == 200:
                        result = json.loads(resp.read().decode("utf-8"))
                        return {
                            "execution_mode": "remote_main_server",
                            "server_url": self.main_server_url,
                            "result": result
                        }
            except Exception as e:
                logger.warning(f"Remote execution on main server failed: {e}. Transitioning to local autonomous fallback.")

        # Fallback to local autonomous execution
        notice = f"Notice: Main Core Server at '{self.main_server_url}' is unreachable ({info.get('error', 'offline')}). Operating in Local Autonomous Mode."
        logger.warning(notice)
        if on_fallback_notice:
            on_fallback_notice(notice)

        if local_executor:
            local_result = local_executor(goal, context)
            # Buffer executed task into offline log
            self.offline_buffer.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "goal": goal,
                "context": context,
                "status": "completed_locally"
            })
            return {
                "execution_mode": "local_autonomous_fallback",
                "notice": notice,
                "result": local_result
            }

        return {
            "execution_mode": "local_autonomous_fallback",
            "notice": notice,
            "error": "Main server unreachable and no local executor provided."
        }

    def export_state_bundle(self, export_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Exports the system state bundle (profile, zones, devices, audio routes, dynamic tools)
        to facilitate migrating the main server to another machine.
        """
        bundle = {
            "version": "2.0.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "profile": self.state_manager.get_user_profile().model_dump(),
            "zones": [z.model_dump() for z in self.state_manager.list_zones()],
            "devices": [d.model_dump() for d in self.state_manager.list_all_devices()],
            "audio_routes": [r.model_dump() for r in self.state_manager.list_all_audio_routes()],
            "dynamic_tools": self.state_manager.get_dynamic_tool_records()
        }

        if export_path:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(bundle, f, indent=2, default=str)
            logger.info(f"Exported system state bundle to '{export_path}'")

        return bundle

    def import_state_bundle(self, bundle_or_path: Any) -> Dict[str, int]:
        """
        Imports a system state bundle onto this machine to promote it as the new Main Server.
        """
        if isinstance(bundle_or_path, str):
            with open(bundle_or_path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
        else:
            bundle = bundle_or_path

        counts = {"zones": 0, "devices": 0, "audio_routes": 0, "dynamic_tools": 0}

        # 1. Profile
        if "profile" in bundle:
            prof_data = bundle["profile"]
            if isinstance(prof_data.get("updated_at"), str):
                prof_data["updated_at"] = datetime.fromisoformat(prof_data["updated_at"])
            self.state_manager.save_user_profile(UserProfile(**prof_data))

        # 2. Zones
        for z in bundle.get("zones", []):
            self.state_manager.ensure_zone_exists(
                zone_id=z["zone_id"],
                display_name=z.get("display_name"),
                metadata=z.get("metadata")
            )
            counts["zones"] += 1

        # 3. Devices
        for d in bundle.get("devices", []):
            if isinstance(d.get("last_seen"), str):
                d["last_seen"] = datetime.fromisoformat(d["last_seen"])
            self.state_manager.register_or_update_device(DeviceTopologyRecord(**d))
            counts["devices"] += 1

        # 4. Audio Routes
        for r in bundle.get("audio_routes", []):
            if isinstance(r.get("updated_at"), str):
                r["updated_at"] = datetime.fromisoformat(r["updated_at"])
            self.state_manager.set_audio_route(AudioRouteRecord(**r))
            counts["audio_routes"] += 1

        logger.info(f"Imported state bundle: {counts}")
        return counts

    def scan_for_servers(self, timeout: float = 2.0) -> List[Dict[str, Any]]:
        """Scans local subnet for active Core AI Sovereign Main Servers via UDP broadcast."""
        try:
            from core.discovery import discover_core_servers
            return discover_core_servers(timeout=timeout)
        except Exception as e:
            logger.warning(f"Error scanning LAN for Core AI servers: {e}")
            return []

def main():
    import sys
    client = MeshClient()
    args = sys.argv[1:]

    try:
        from colorama import init, Fore, Style
        init(autoreset=True)
        G, C, Y, R, B, RST = Fore.GREEN, Fore.CYAN, Fore.YELLOW, Fore.RED, Style.BRIGHT, Style.RESET_ALL
    except ImportError:
        G = C = Y = R = B = RST = ""

    if not args or args[0] in ["status", "info"]:
        is_online, ping_info = client.ping_main_server()
        status_str = f"{G}REACHABLE (Online){RST}" if is_online else f"{Y}UNREACHABLE ({ping_info.get('error', 'offline')}){RST}"
        print(f"\n{C}+=====================================================================+{RST}")
        print(f"{C}|{B}   CORE AI :: INTERCONTINENTAL SOVEREIGN MESH STATUS                 {RST}{C}|{RST}")
        print(f"{C}+=====================================================================+{RST}")
        print(f"{C}|{RST}   Node Role:        {C}{client.role.upper()}{RST}")
        print(f"{C}|{RST}   Main Server URL:  {client.main_server_url}")
        print(f"{C}|{RST}   Server Status:    {status_str}")
        print(f"{C}|{RST}   Offline Buffer:   {len(client.offline_buffer)} items queued")
        if client.role == "edge_node" and not is_online:
            print(f"{C}|{RST}   {Y}↳ Autonomous Local Fallback is ACTIVE (never locked out).{RST}")
        print(f"{C}+=====================================================================+{RST}\n")
        print("  Commands:")
        print("    core mesh scan                         (Scan LAN subnet for running Main Servers)")
        print("    core mesh connect auto                 (Auto-discover and pair to first LAN Server)")
        print("    core mesh connect <http://host:port>   (Bind this machine as edge node to server)")
        print("    core mesh role <main_server|edge_node> (Set operational node role)")
        print("    core mesh disconnect                   (Revert to standalone main server)\n")

    elif args[0] in ["scan", "discover"]:
        print(f"\n{C}[*] Scanning local network for active Core AI Sovereign Main Servers...{RST}")
        servers = client.scan_for_servers(timeout=2.0)
        if not servers:
            print(f"{Y}[!] No active Core AI servers discovered on local subnet broadcast.{RST}")
            print(f"    Ensure the Main Server is running (`core start`) on the same LAN or Wi-Fi.\n")
        else:
            print(f"{G}[+] Discovered {len(servers)} active Sovereign Server(s) on LAN:{RST}\n")
            for idx, s in enumerate(servers, 1):
                print(f"  [{idx}] {B}{s.get('hostname', 'Server')}{RST} - {C}{s.get('url')}{RST}")
                print(f"      Operator: {G}{s.get('active_user', 'Operator')}{RST} | Cognitive Model: {s.get('active_model', 'N/A')}")
                print(f"      LAN IPv4: {s.get('lan_ip')} | Port: {s.get('port')}\n")
            print(f"  To pair: core mesh connect {servers[0].get('url')}\n")

    elif args[0] == "connect":
        if len(args) > 1 and args[1].lower() == "auto":
            print(f"{C}[*] Scanning LAN for active Core AI Sovereign Server...{RST}")
            servers = client.scan_for_servers(timeout=2.0)
            if not servers:
                print(f"{R}[-] No server discovered on LAN. Specify URL manually:{RST} core mesh connect <http://IP:8000>")
                return
            target_url = servers[0].get("url")
            print(f"{G}[+] Found server at {target_url}! Pairing...{RST}")
            client.save_configuration(role="edge_node", main_server_url=target_url)
            is_online, ping = client.ping_main_server()
            if is_online:
                print(f"{G}[OK] Paired as EDGE_NODE to {target_url} ({servers[0].get('active_user')})!{RST}")
            else:
                print(f"{Y}[!] Saved server URL '{target_url}', but could not establish HTTP connection.{RST}")
        elif len(args) > 1:
            url = args[1].rstrip("/")
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "http://" + url
            client.save_configuration(role="edge_node", main_server_url=url)
            is_online, ping = client.ping_main_server()
            if is_online:
                print(f"{G}[OK] Paired as EDGE_NODE to Main Server at {url}!{RST}")
                print(f"All goals executed on this PC will now run on the server.")
            else:
                print(f"{Y}[!] Saved server URL '{url}', but server is currently unreachable ({ping.get('error', 'offline')}).{RST}")
                print("Local autonomous fallback is active until server is reached.")
        else:
            print("Usage: core mesh connect <http://<SERVER-IP>:8000> or core mesh connect auto")

    elif args[0] == "role":
        if len(args) > 1:
            new_role = "main_server" if "main" in args[1].lower() else "edge_node"
            client.save_configuration(role=new_role)
            print(f"{G}[OK] Node role set to: {new_role}{RST}")
        else:
            print("Usage: core mesh role <main_server|edge_node>")

    elif args[0] in ["disconnect", "reset"]:
        client.save_configuration(role="main_server", main_server_url="http://localhost:8000")
        print(f"{G}[OK] Reset to standalone MAIN_SERVER mode.{RST}")

    else:
        print(f"Unknown mesh command: {args[0]}")
        print("Valid commands: status, scan, connect, role, disconnect")

if __name__ == "__main__":
    main()
