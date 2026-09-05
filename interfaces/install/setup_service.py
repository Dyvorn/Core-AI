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

def run_service_setup():
    print("\n" + "=" * 65)
    print("  CORE AI :: SYSTEM BOOTSTRAP & AUTOSTART SETUP")
    print("=" * 65)
    print("Zero corporate telemetry. 100% self-hosted.\n")

    svc = ServiceManager()
    updater = CoreUpdater()
    state = StateManager()

    # 1. Autostart Question
    enable_auto = prompt_yn("[?] Do you want Core AI to start automatically on system boot?", default=True)

    # 2. Update Check Question
    enable_update_check = prompt_yn("[?] Check for updates from GitHub on startup with automated test guard?", default=True)

    # 3. Launch Style
    print("\nLaunch Style on Startup:")
    print("  1) Visible Terminal Window (Server Kernel Shell)")
    print("  2) Headless Background Service")
    choice = input("Select [1-2, Default=1]: ").strip()
    in_terminal = choice != "2"

    # 4. Identity & Zone Profile check
    profile = state.get_user_profile()
    if profile.preferred_name == "User":
        print("\nOperator profile is currently using default 'User'.")
        run_identity = prompt_yn("[?] Would you like to configure your operator handle and primary space now?", default=True)
        if run_identity:
            run_identity_setup()

    # Apply configuration
    if enable_auto:
        # Create autostart launcher script that checks updates if enabled
        path = svc.get_autostart_path()
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            python_exe = sys.executable
            root_dir = svc.root_dir

            if os.name == "nt":
                update_cmd = f'"{python_exe}" -c "from core.updater import CoreUpdater; u = CoreUpdater(); u.apply_update()"\r\n' if enable_update_check else ""
                content = (
                    f"@echo off\r\n"
                    f"title Core AI Server Suite\r\n"
                    f'cd /d "{root_dir}"\r\n'
                    f"{update_cmd}"
                    f'"{python_exe}" main.py\r\n'
                )
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"\n[OK] Created Windows autostart file at: {path}")
            else:
                svc.enable_autostart(in_terminal=in_terminal)
                print(f"\n[OK] Configured Linux autostart at: {path}")
    else:
        svc.disable_autostart()
        print("\n[OK] Autostart disabled.")

    print("\n" + "-" * 65)
    print("Bootstrap setup complete!")
    print(f"  Autostart Enabled: {'YES' if enable_auto else 'NO'}")
    print(f"  Startup Mode:      {'Terminal Window' if in_terminal else 'Headless Daemon'}")
    print(f"  Auto-Update Guard: {'YES' if enable_update_check else 'NO'}")
    print("-" * 65)

    # Prompt to start now
    start_now = prompt_yn("\n[?] Would you like to start the Core AI Server Suite now?", default=True)
    if start_now:
        ok, msg = svc.start(in_new_terminal=in_terminal)
        print(f"[{'OK' if ok else 'INFO'}] {msg}")
        if ok:
            print("Server is online! Open browser at: http://localhost:8000/roadmap\n")

if __name__ == "__main__":
    run_service_setup()
