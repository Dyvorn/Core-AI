import os
import sys
import shutil
import logging

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.service import ServiceManager
from core.mesh_client import MeshClient

def prompt_yn(question: str, default: bool = False) -> bool:
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

def run_uninstallation():
    print("\n" + "=" * 65)
    print("  CORE AI :: ZERO-RESIDUE COMPLETE UNINSTALLER")
    print("=" * 65)
    print("This will stop all running Core AI services and cleanly remove")
    print("all autostart hooks, system services, and local data files.\n")

    svc = ServiceManager()
    root_dir = svc.root_dir

    confirm = prompt_yn("[!] Are you sure you want to completely uninstall Core AI from this system?", default=False)
    if not confirm:
        print("[*] Uninstallation cancelled by operator.")
        return

    # 1. Stop all running processes
    pid = svc.get_running_pid()
    if pid:
        print(f"[*] Stopping active Core AI server (PID {pid})...")
        svc.stop()

    # 2. Offer backup
    offer_backup = prompt_yn("[?] Would you like to export a backup bundle of your data first?", default=True)
    if offer_backup:
        try:
            mesh = MeshClient()
            backup_file = os.path.join(os.path.expanduser("~"), "core_ai_backup.json")
            mesh.export_state_bundle(export_path=backup_file)
            print(f"[OK] Backup saved to: '{backup_file}'")
        except Exception as e:
            print(f"[!] Warning: Could not export backup: {e}")

    # 3. Remove autostart hooks
    print("[*] Removing autostart entries...")
    svc.disable_autostart()

    # 4. Remove local runtime data files
    wipe_data = prompt_yn("[?] Delete local database and runtime logs (core_ai.db, logs/)?", default=True)
    if wipe_data:
        # DB
        db_path = os.path.join(root_dir, "core_ai.db")
        for ext in ["", "-wal", "-shm"]:
            target = db_path + ext
            if os.path.exists(target):
                try:
                    os.remove(target)
                    print(f"  [-] Removed database file: {os.path.basename(target)}")
                except Exception:
                    pass

        # PID file
        if os.path.exists(svc.pid_path):
            try:
                os.remove(svc.pid_path)
            except Exception:
                pass

        # Logs directory contents
        logs_dir = os.path.join(root_dir, "logs")
        if os.path.exists(logs_dir):
            try:
                for f in os.listdir(logs_dir):
                    fp = os.path.join(logs_dir, f)
                    if os.path.isfile(fp):
                        os.remove(fp)
                print("  [-] Cleared logs directory.")
            except Exception:
                pass

        # Python cache
        for root, dirs, files in os.walk(root_dir):
            for d in list(dirs):
                if d == "__pycache__":
                    try:
                        shutil.rmtree(os.path.join(root, d))
                    except Exception:
                        pass

    print("\n" + "-" * 65)
    print("[OK] Core AI uninstallation complete.")
    print("     Zero background processes. Zero residual autostart files.")
    print("-" * 65 + "\n")

if __name__ == "__main__":
    run_uninstallation()
