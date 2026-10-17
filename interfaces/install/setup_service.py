"""
Core AI :: System Installation & Deployment Wizard
Supports:
  1. Normal PC Setup: Installs Nothing OS Desktop App & CLI, connects to mesh server,
     zero background voice daemons, zero battery/CPU overhead, 1-click Desktop App launcher.
  2. Central Server Setup: Configures full 24/7 Sovereign Microkernel, DAG engine,
     voice pipeline, autostart on system boot, and watchdog.
"""

import os
import sys
import json
import urllib.request
from typing import Optional, Tuple, List, Dict, Any

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.service import ServiceManager
from core.state import StateManager
from interfaces.cli.setup_wizard import run_setup as run_identity_setup


def prompt_yn(question: str, default: bool = True) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        resp = input(question + suffix).strip().lower()
        if not resp:
            return default
        if resp in ["y", "yes"]:
            return True
        if resp in ["n", "no"]:
            return False
        print("Please answer with 'y' or 'n'.")


def prompt_choice(question: str, choices: List[str], default: str = "1") -> str:
    prompt_str = f"{question} (Default: {default}): "
    while True:
        resp = input(prompt_str).strip()
        if not resp:
            return default
        if resp in choices:
            return resp
        print(f"Please enter one of: {', '.join(choices)}")


def probe_gateway(url: str, timeout: float = 1.5) -> Tuple[bool, Dict[str, Any]]:
    try:
        endpoint = f"{url.rstrip('/')}/api/v1/health"
        req = urllib.request.Request(endpoint, headers={"User-Agent": "CoreAI-Setup/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return True, json.loads(resp.read().decode())
    except Exception:
        pass
    return False, {}


def update_env_gateway(root_dir: str, server_url: str):
    env_path = os.path.join(root_dir, "config", ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("CORE_GATEWAY_URL="):
                    lines.append(f"CORE_GATEWAY_URL={server_url}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"CORE_GATEWAY_URL={server_url}\n")
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def create_desktop_launcher(root_dir: str, for_app: bool = True) -> Optional[str]:
    try:
        if os.name == "nt":
            desktop_dir = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
            if os.path.isdir(desktop_dir):
                bat_name = "Core AI.bat" if for_app else "CoreAI.bat"
                bat_path = os.path.join(desktop_dir, bat_name)
                cmd = "call core.bat app\r\n" if for_app else "call core.bat\r\n"
                content = (
                    "@echo off\r\n"
                    f'cd /d "{root_dir}"\r\n'
                    f"{cmd}"
                )
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[OK] Created Desktop launcher: {bat_path}")
                return bat_path
        else:
            desktop_dir = os.path.expanduser("~/Desktop")
            if os.path.isdir(desktop_dir):
                sh_name = "CoreAI-App.desktop" if for_app else "CoreAI.desktop"
                sh_path = os.path.join(desktop_dir, sh_name)
                cmd = "./core.sh app" if for_app else "./core.sh"
                content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    f"Name=Core AI {'Desktop App' if for_app else 'Sovereign Terminal'}\n"
                    f"Exec=bash -c 'cd \"{root_dir}\" && {cmd}'\n"
                    "Terminal=true\n"
                )
                with open(sh_path, "w", encoding="utf-8") as f:
                    f.write(content)
                os.chmod(sh_path, 0o755)
                print(f"[OK] Created Desktop launcher: {sh_path}")
                return sh_path
    except Exception as e:
        print(f"[WARNING] Could not create Desktop launcher: {e}")
    return None


def run_service_setup(preselected_mode: Optional[str] = None):
    print("\n" + "=" * 68)
    print("  C.O.R.E. AI :: SYSTEM INSTALLATION & DEPLOYMENT WIZARD")
    print("  Zero corporate telemetry. 100% self-hosted sovereign intelligence.")
    print("=" * 68)

    svc = ServiceManager()
    state = StateManager()
    root_dir = svc.root_dir
    profile = state.get_user_profile()

    # Determine Setup Mode
    if preselected_mode in ("1", "normal", "pc", "client"):
        choice = "1"
    elif preselected_mode in ("2", "server", "host"):
        choice = "2"
    else:
        print("\nSelect your installation architecture:\n")
        print("  [1] Normal PC Setup (Desktop Companion App & CLI)  [RECOMMENDED FOR PC]")
        print("      - Installs the Nothing OS Desktop Chat Companion and CLI tools.")
        print("      - Connects directly to your Central Core AI Server across LAN / Tailscale.")
        print("      - Zero background microphone listening, zero daemons on this PC.")
        print("      - Creates a 1-click Desktop App launcher.")
        print("")
        print("  [2] Central Server Setup (24/7 Sovereign Microkernel & Mesh Host)")
        print("      - For dedicated homelab servers, always-on headless hosts, or standalone PCs.")
        print("      - Runs the 24/7 Universal Gateway, DAG engine, voice loop, and spatial audio mesh.")
        print("      - Configures automated system boot service & self-healing watchdog.")
        print("")

        choice = prompt_choice("[?] Select setup mode [1 = Normal PC, 2 = Central Server]", choices=["1", "2"], default="1")

    # -------------------------------------------------------------
    # Option 1: Normal PC Setup
    # -------------------------------------------------------------
    if choice == "1":
        print("\n" + "-" * 68)
        print("  [*] Configuring NORMAL PC SETUP (Desktop Companion Client)")
        print("-" * 68)

        # 1. Mesh server connection
        existing_url = profile.preferences.get("mesh", {}).get("main_server_url") or "http://192.168.2.153:8000"
        connect_remote = prompt_yn("[?] Connect to an existing Central Core AI Server on your network?", default=True)
        server_url = "http://127.0.0.1:8000"
        if connect_remote:
            server_input = input(f"    [>] Enter Central Server URL [{existing_url}]: ").strip()
            server_url = server_input if server_input else existing_url
            ok, s_info = probe_gateway(server_url)
            if ok:
                ver = s_info.get("version", "v0.3.1")
                plat = s_info.get("platform", "Server")
                print(f"    [OK] Successfully connected to Central Server at '{server_url}' ({ver} on {plat})!")
            else:
                print(f"    [!] Notice: Server at '{server_url}' was not immediately reachable.")
                print(f"        Saved target URL; companion will connect automatically once online.")

        # Persist mesh client configuration
        if "mesh" not in profile.preferences:
            profile.preferences["mesh"] = {}
        profile.preferences["mesh"]["role"] = "edge_node"
        profile.preferences["mesh"]["main_server_url"] = server_url
        state.save_user_profile(profile)
        update_env_gateway(root_dir, server_url)

        # Ensure no background voice daemons are registered on PC autostart
        svc.disable_autostart()

        # 2. Operator Identity Setup
        if profile.preferred_name == "User":
            print("\nOperator profile is currently using default 'User'.")
            if prompt_yn("[?] Configure your operator handle and primary space now?", default=True):
                run_identity_setup()

        # 3. Desktop Launcher for Desktop App
        enable_desktop = prompt_yn("\n[?] Place a 1-click launcher on your Desktop for the Core AI App?", default=True)
        if enable_desktop:
            create_desktop_launcher(root_dir, for_app=True)

        print("\n" + "=" * 68)
        print("  [OK] Normal PC Setup complete! Software installed and ready.")
        print(f"  Target Gateway:    {server_url}")
        print(f"  Operational Role:  Edge Client / Desktop Companion")
        print(f"  Desktop Launcher:  {'Created on Desktop' if enable_desktop else 'None'}")
        print(f"  Background Daemon: OFF (Zero background mic or file clutter)")
        print("=" * 68)

        # 4. Launch Desktop Companion App
        start_now = prompt_yn("\n[?] Launch Core AI Desktop Companion now?", default=True)
        if start_now:
            print("\nLaunching Core AI Desktop Companion...\n")
            from interfaces.app.app import launch_app
            launch_app()

    # -------------------------------------------------------------
    # Option 2: Central Server Setup
    # -------------------------------------------------------------
    else:
        print("\n" + "-" * 68)
        print("  [*] Configuring CENTRAL SERVER SETUP (24/7 Sovereign Microkernel)")
        print("-" * 68)

        if "mesh" not in profile.preferences:
            profile.preferences["mesh"] = {}
        profile.preferences["mesh"]["role"] = "main_server"
        profile.preferences["mesh"]["main_server_url"] = "http://localhost:8000"
        state.save_user_profile(profile)

        # 1. Identity & Space
        if profile.preferred_name == "User":
            print("\nOperator profile is currently using default 'User'.")
            if prompt_yn("[?] Configure your operator handle and primary space now?", default=True):
                run_identity_setup()

        # 2. Desktop Launcher for Terminal
        enable_desktop = prompt_yn("\n[?] Place a 1-click terminal launcher on your Desktop?", default=True)
        if enable_desktop:
            create_desktop_launcher(root_dir, for_app=False)

        # 3. Autostart & 24/7 Watchdog
        enable_auto = prompt_yn("\n[?] Start Core AI automatically on system boot?", default=True)
        silent_watchdog = True
        if enable_auto:
            silent_watchdog = prompt_yn("    [?] Run silently in background with 24/7 self-healing Watchdog?", default=True)
            ok, msg = svc.enable_autostart(in_terminal=not silent_watchdog, use_watchdog=silent_watchdog)
            if ok:
                print(f"    [OK] {msg}")
            else:
                print(f"    [WARNING] {msg}")
        else:
            svc.disable_autostart()

        print("\n" + "=" * 68)
        print("  [OK] Central Server Setup complete!")
        print(f"  Operational Role:  Central Server (Port 8000)")
        print(f"  Desktop Launcher:  {'Created' if enable_desktop else 'None'}")
        print(f"  Autostart on Boot: {'YES' if enable_auto else 'NO'}")
        print("=" * 68)

        start_now = prompt_yn("\n[?] Launch Core AI Sovereign Terminal now?", default=True)
        if start_now:
            print("\nStarting Core AI...\n")
            from main import main as launch_main
            launch_main()


if __name__ == "__main__":
    mode_arg = None
    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            mode_arg = arg.split("=", 1)[1].lower()
        elif arg in ("--normal", "--client", "--pc"):
            mode_arg = "normal"
        elif arg in ("--server", "--host"):
            mode_arg = "server"
    run_service_setup(preselected_mode=mode_arg)
