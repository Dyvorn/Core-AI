import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.service import ServiceManager
from core.updater import CoreUpdater
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

def create_desktop_launcher(root_dir: str):
    try:
        if os.name == "nt":
            desktop_dir = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
            if os.path.isdir(desktop_dir):
                bat_path = os.path.join(desktop_dir, "CoreAI.bat")
                content = (
                    "@echo off\r\n"
                    f'cd /d "{root_dir}"\r\n'
                    "call core.bat\r\n"
                )
                with open(bat_path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"[OK] Created Desktop launcher: {bat_path}")
                return bat_path
        else:
            desktop_dir = os.path.expanduser("~/Desktop")
            if os.path.isdir(desktop_dir):
                sh_path = os.path.join(desktop_dir, "CoreAI.desktop")
                content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=Core AI Sovereign Terminal\n"
                    f"Exec=bash -c 'cd \"{root_dir}\" && ./core.sh'\n"
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

def run_service_setup():
    print("\n" + "=" * 65)
    print("  CORE AI :: SYSTEM BOOTSTRAP & TERMINAL SETUP")
    print("=" * 65)
    print("Zero corporate telemetry. 100% self-hosted.\n")

    svc = ServiceManager()
    updater = CoreUpdater()
    state = StateManager()
    root_dir = svc.root_dir

    # 1. Identity & Zone Profile Check
    profile = state.get_user_profile()
    if profile.preferred_name == "User":
        print("Operator profile is currently using default 'User'.")
        run_identity = prompt_yn("[?] Configure your operator handle and primary space now?", default=True)
        if run_identity:
            run_identity_setup()

    # 2. Desktop Launcher Question
    enable_desktop = prompt_yn("[?] Place a 1-click launcher (CoreAI.bat) on your Desktop?", default=True)
    if enable_desktop:
        create_desktop_launcher(root_dir)

    # 3. Autostart Question
    enable_auto = prompt_yn("[?] Start Core AI automatically on system boot?", default=False)
    silent_watchdog = True
    if enable_auto:
        silent_watchdog = prompt_yn("    [?] Run silently in background with 24/7 self-healing Watchdog?", default=True)

    # 4. Update Check Question
    enable_update_check = prompt_yn("[?] Check for updates from GitHub on startup with automated test guard?", default=True)

    # Apply Autostart Configuration
    if enable_auto:
        ok, msg = svc.enable_autostart(in_terminal=not silent_watchdog, use_watchdog=silent_watchdog)
        if ok:
            print(f"[OK] {msg}")
        else:
            print(f"[WARNING] {msg}")
    else:
        svc.disable_autostart()

    print("\n" + "-" * 65)
    print("Bootstrap setup complete!")
    print(f"  Desktop Launcher:  {'Created' if enable_desktop else 'None'}")
    print(f"  Autostart on Boot: {'YES' if enable_auto else 'NO'}")
    print(f"  Auto-Update Guard: {'YES' if enable_update_check else 'NO'}")
    print("-" * 65)

    # 5. Launch Prompt
    start_now = prompt_yn("\n[?] Launch Core AI Sovereign Terminal now?", default=True)
    if start_now:
        print("\nStarting Core AI...\n")
        from main import main as launch_main
        launch_main()

if __name__ == "__main__":
    run_service_setup()
