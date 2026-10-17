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


def check_gateway_online(host: str = "127.0.0.1", port: int = 8000) -> bool:
    """Verifies whether the central Core AI Universal Gateway is actively running."""
    url = f"http://{host}:{port}/api/v1/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CoreAI-AppLauncher/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_daemon_if_needed(port: int = 8000):
    """Starts the Core AI background daemon if offline."""
    if not check_gateway_online(port=port):
        print(f"{YELLOW}[*] Microkernel daemon offline. Starting Core AI Universal Gateway in background...{RESET}")
        try:
            from core.service import ServiceManager
            mgr = ServiceManager()
            ok, msg = mgr.start(in_new_terminal=False, extra_args=["--headless", "--port", str(port)])
            print(f"  {msg}")
            # Wait up to 3 seconds for gateway to bind port
            for _ in range(6):
                if check_gateway_online(port=port):
                    break
                time.sleep(0.5)
        except Exception as e:
            print(f"{YELLOW}[!] Notice starting service: {e}{RESET}")


def launch_native_qt_app() -> int:
    """Launches the pure Python PyQt6 Nothing OS Glyph Matrix desktop application."""
    from interfaces.app.qt_app import run_qt_app
    return run_qt_app()


def launch_app(port: int = 8000) -> int:
    """
    Launches the official Core AI Sovereign Desktop Chat Companion (100% Native PyQt6).
    """
    start_daemon_if_needed(port=port)
    is_online = check_gateway_online(port=port)

    box = render_box(
        title="CORE AI :: SOVEREIGN PC DESKTOP CHAT APP",
        rows=[
            ("Application:", f"{CYAN}c.o.r.e. Native Desktop Chat Companion{RESET}"),
            ("Desktop Engine:", f"{GREEN}100% Native Python PyQt6 (Zero Web / Zero Slop){RESET}"),
            ("Gateway State:", f"{GREEN}ONLINE (Port {port}){RESET}" if is_online else f"{YELLOW}STANDALONE LOCAL{RESET}"),
            ("Aesthetic:", f"{CYAN}Nothing OS Dot-Matrix & Obsidian Void (#0B0B0B){RESET}"),
            ("Shortcuts:", f"Enter: Send · Shift+Enter: Newline · Ctrl+N: New Chat · Ctrl+,: Settings"),
        ],
        width=75
    )
    print(f"\n{box}\n", flush=True)
    return launch_native_qt_app()


if __name__ == "__main__":
    port_arg = int(os.getenv("CORE_PORT", 8000))
    sys.exit(launch_app(port=port_arg))
