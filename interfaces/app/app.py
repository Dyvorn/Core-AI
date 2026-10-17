"""
Core AI :: Sovereign Desktop Companion Launcher
Delivers a 100% native PyQt6 desktop application with Nothing OS Dot-Matrix Glyph aesthetic.
Zero HTML, Zero JavaScript, Zero WebView on PC desktop.

Usage:
  core app
  core.bat app
  core.sh app
  python interfaces/app/app.py
"""

import os
import sys
import time
import urllib.request
import urllib.error

# Ensure project root is on sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.terminal import render_box, CYAN, GREEN, YELLOW, RED, BOLD, RESET


def resolve_gateway_url() -> str:
    """Resolves target gateway URL from env var, mesh profile, or default."""
    url = os.getenv("CORE_GATEWAY_URL")
    if not url:
        try:
            from core.state import StateManager
            profile = StateManager().get_user_profile()
            url = profile.preferences.get("mesh", {}).get("main_server_url")
        except Exception:
            url = None
    return (url or "http://127.0.0.1:8000").rstrip("/")


def check_gateway_online(target_url: str) -> bool:
    """Verifies whether the central Core AI Universal Gateway is actively running."""
    url = f"{target_url}/api/v1/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CoreAI-AppLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def launch_native_qt_app() -> int:
    """Launches the pure Python PyQt6 Nothing OS Glyph Matrix desktop application."""
    from interfaces.app.qt_app import run_qt_app
    return run_qt_app()


def launch_app(start_local_daemon: bool = False) -> int:
    """
    Launches the official Core AI Sovereign Desktop Chat Companion (100% Native PyQt6).
    """
    target_gateway = resolve_gateway_url()
    is_online = check_gateway_online(target_gateway)

    if not is_online and start_local_daemon and ("127.0.0.1" in target_gateway or "localhost" in target_gateway):
        print(f"{YELLOW}[*] Local microkernel offline. Starting Core AI Universal Gateway in background...{RESET}")
        try:
            from core.service import ServiceManager
            mgr = ServiceManager()
            ok, msg = mgr.start(in_new_terminal=False, extra_args=["--headless"])
            print(f"  {msg}")
            for _ in range(6):
                if check_gateway_online(target_gateway):
                    is_online = True
                    break
                time.sleep(0.5)
        except Exception as e:
            print(f"{YELLOW}[!] Notice starting service: {e}{RESET}")

    box = render_box(
        title="CORE AI :: SOVEREIGN PC DESKTOP CHAT APP",
        rows=[
            ("Application:", f"{CYAN}c.o.r.e. Native Desktop Chat Companion{RESET}"),
            ("Desktop Engine:", f"{GREEN}100% Native Python PyQt6 (Zero Web / Zero Slop){RESET}"),
            ("Gateway Target:", f"{GREEN}{target_gateway}{RESET}"),
            ("Gateway State:", f"{GREEN}ONLINE{RESET}" if is_online else f"{YELLOW}STANDALONE (OFFLINE){RESET}"),
            ("Aesthetic:", f"{CYAN}Nothing OS Dot-Matrix & Obsidian Void (#0B0B0B){RESET}"),
            ("Shortcuts:", f"Enter: Send · Shift+Enter: Newline · Ctrl+N: New Chat · Ctrl+,: Settings"),
        ],
        width=75
    )
    print(f"\n{box}\n", flush=True)
    return launch_native_qt_app()


if __name__ == "__main__":
    start_daemon = "--start-daemon" in sys.argv
    sys.exit(launch_app(start_local_daemon=start_daemon))
