import os
import sys
import shutil
import logging
import argparse
from typing import Dict, Any, Optional, List

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.service import ServiceManager

logger = logging.getLogger(__name__)

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    CYAN = Fore.CYAN
    GREEN = Fore.GREEN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    MAGENTA = Fore.MAGENTA
    BRIGHT = Style.BRIGHT
    RESET = Style.RESET_ALL
except ImportError:
    CYAN = GREEN = YELLOW = RED = MAGENTA = BRIGHT = RESET = ""


def prompt_yn(question: str, default: bool = False) -> bool:
    """Prompts operator for a Y/n answer with a default."""
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


def clean_system_state(
    root_dir: Optional[str] = None,
    wipe_db: bool = True,
    wipe_env: bool = True,
    wipe_logs: bool = True,
    wipe_backups: bool = True,
    wipe_dynamic_tools: bool = True,
    wipe_pycache: bool = True,
    stop_services: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Deletes all local runtime state, database records, audit logs, credential configs,
    backups, and dynamic tools for a completely fresh Day-Zero server setup,
    while leaving all source code, Python virtual environments, and installed packages intact.

    Safety Directives:
    - NEVER touches .venv (virtualenv stays 100% installed).
    - NEVER touches .git (repository integrity is preserved).
    - NEVER touches native code files (core/, brain/, engines/, tools/native/, interfaces/, tests/).
    """
    base_dir = root_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

    summary: Dict[str, Any] = {
        "root_dir": base_dir,
        "stopped_processes": [],
        "removed_db_files": [],
        "removed_env_files": [],
        "cleared_log_files": [],
        "cleared_backup_files": [],
        "cleared_dynamic_tools": [],
        "cleared_pycache_dirs": [],
        "preserved_components": [
            "Python Virtual Environment (.venv) & installed packages",
            "Git Repository (.git) & revision history",
            "Core AI source architecture (core, brain, engines, interfaces, tools/native)",
            "System configuration templates (config/.env.example, config/settings.yaml)"
        ],
        "dry_run": dry_run,
        "status": "success"
    }

    # 1. Stop background processes (free sockets & file handles)
    if stop_services:
        try:
            svc = ServiceManager(root_dir=base_dir)
            pid = svc.get_running_pid()
            if pid:
                if not dry_run:
                    svc.stop()
                summary["stopped_processes"].append(f"Core AI Microkernel (PID {pid})")

            w_pid = svc.get_watchdog_pid()
            if w_pid:
                if not dry_run:
                    svc.stop_watchdog()
                summary["stopped_processes"].append(f"Watchdog Supervisor (PID {w_pid})")

            # Clean stale PID files
            for p_file in [".core_ai.pid", ".core_watchdog.pid"]:
                p_path = os.path.join(base_dir, p_file)
                if os.path.exists(p_path) and not dry_run:
                    try:
                        os.remove(p_path)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Notice while stopping services: {e}")

    # 2. Wipe SQLite Database (core_ai.db, WAL, SHM)
    if wipe_db:
        db_path = os.path.join(base_dir, "core_ai.db")
        for ext in ["", "-wal", "-shm"]:
            target = db_path + ext
            if os.path.exists(target):
                if not dry_run:
                    try:
                        os.remove(target)
                        summary["removed_db_files"].append(os.path.basename(target))
                    except Exception as e:
                        logger.warning(f"Could not remove database file '{target}': {e}")
                else:
                    summary["removed_db_files"].append(os.path.basename(target))

        # Check for any test databases left in root
        try:
            for item in os.listdir(base_dir):
                if (item.startswith("test_") or item.startswith("state_backup_")) and item.endswith(".db"):
                    fp = os.path.join(base_dir, item)
                    if os.path.isfile(fp):
                        if not dry_run:
                            try:
                                os.remove(fp)
                                summary["removed_db_files"].append(item)
                            except Exception:
                                pass
                        else:
                            summary["removed_db_files"].append(item)
        except Exception:
            pass

    # 3. Wipe Configuration & Secrets (config/.env)
    if wipe_env:
        for env_rel in [os.path.join("config", ".env"), ".env"]:
            env_target = os.path.join(base_dir, env_rel)
            if os.path.exists(env_target):
                if not dry_run:
                    try:
                        os.remove(env_target)
                        summary["removed_env_files"].append(env_rel)
                    except Exception as e:
                        logger.warning(f"Could not remove env file '{env_target}': {e}")
                else:
                    summary["removed_env_files"].append(env_rel)

    # 4. Clear Runtime Logs (logs/*)
    if wipe_logs:
        logs_dir = os.path.join(base_dir, "logs")
        if os.path.exists(logs_dir):
            try:
                for fname in os.listdir(logs_dir):
                    fp = os.path.join(logs_dir, fname)
                    if os.path.isfile(fp):
                        if not dry_run:
                            try:
                                os.remove(fp)
                                summary["cleared_log_files"].append(fname)
                            except Exception:
                                pass
                        else:
                            summary["cleared_log_files"].append(fname)
            except Exception as e:
                logger.warning(f"Notice while clearing logs directory: {e}")

    # 5. Clear Backup Snapshots (backups/*)
    if wipe_backups:
        backups_dir = os.path.join(base_dir, "backups")
        if os.path.exists(backups_dir):
            try:
                for fname in os.listdir(backups_dir):
                    fp = os.path.join(backups_dir, fname)
                    if os.path.isfile(fp):
                        if not dry_run:
                            try:
                                os.remove(fp)
                                summary["cleared_backup_files"].append(fname)
                            except Exception:
                                pass
                        else:
                            summary["cleared_backup_files"].append(fname)
            except Exception as e:
                logger.warning(f"Notice while clearing backups directory: {e}")

    # 6. Clear Dynamically Synthesized Tools (tools/dynamic/* except __init__.py)
    if wipe_dynamic_tools:
        dyn_dir = os.path.join(base_dir, "tools", "dynamic")
        if os.path.exists(dyn_dir):
            try:
                for fname in os.listdir(dyn_dir):
                    if fname == "__init__.py":
                        continue
                    fp = os.path.join(dyn_dir, fname)
                    if os.path.isfile(fp) and fname.endswith(".py"):
                        if not dry_run:
                            try:
                                os.remove(fp)
                                summary["cleared_dynamic_tools"].append(fname)
                            except Exception:
                                pass
                        else:
                            summary["cleared_dynamic_tools"].append(fname)
                pycache_dyn = os.path.join(dyn_dir, "__pycache__")
                if os.path.exists(pycache_dyn) and not dry_run:
                    shutil.rmtree(pycache_dyn, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Notice while pruning dynamic tools: {e}")

    # 7. Clear Bytecode & Test Caches (__pycache__, .pytest_cache)
    if wipe_pycache:
        try:
            for root, dirs, _ in os.walk(base_dir):
                # Never traverse into virtual environment or git internals
                if ".venv" in dirs:
                    dirs.remove(".venv")
                if ".git" in dirs:
                    dirs.remove(".git")
                for d in list(dirs):
                    if d == "__pycache__":
                        p = os.path.join(root, d)
                        if not dry_run:
                            shutil.rmtree(p, ignore_errors=True)
                        summary["cleared_pycache_dirs"].append(os.path.relpath(p, base_dir))
            pytest_cache = os.path.join(base_dir, ".pytest_cache")
            if os.path.exists(pytest_cache) and not dry_run:
                shutil.rmtree(pytest_cache, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Notice while pruning bytecode caches: {e}")

    return summary


def print_clean_summary_card(summary: Dict[str, Any]):
    """Renders a high-contrast terminal matrix card detailing the clean slate state."""
    dry_tag = f" {YELLOW}[DRY RUN]{RESET}" if summary.get("dry_run") else ""
    print(f"\n{CYAN}+=====================================================================+{RESET}")
    print(f"{CYAN}|{BRIGHT}   C.O.R.E. AI :: ZERO-RESIDUE CLEAN SLATE MATRIX{dry_tag:<21}{RESET}{CYAN}|{RESET}")
    print(f"{CYAN}+=====================================================================+{RESET}")

    stopped = summary.get("stopped_processes", [])
    stopped_str = f"{len(stopped)} terminated" if stopped else "None (idle)"
    print(f"{CYAN}|{RESET}   Active Processes:   {GREEN}{stopped_str:<46}{RESET}{CYAN}|{RESET}")

    dbs = summary.get("removed_db_files", [])
    db_str = f"Purged ({', '.join(dbs)})" if dbs else "Clean / Not Found"
    print(f"{CYAN}|{RESET}   Database State:     {GREEN}{db_str:<46}{RESET}{CYAN}|{RESET}")

    envs = summary.get("removed_env_files", [])
    env_str = f"Reset ({', '.join(envs)})" if envs else "Clean / Not Present"
    print(f"{CYAN}|{RESET}   Config & Secrets:   {GREEN}{env_str:<46}{RESET}{CYAN}|{RESET}")

    logs = summary.get("cleared_log_files", [])
    log_str = f"{len(logs)} log files cleared" if logs else "Logs empty"
    print(f"{CYAN}|{RESET}   Audit Trails:       {GREEN}{log_str:<46}{RESET}{CYAN}|{RESET}")

    backups = summary.get("cleared_backup_files", [])
    bk_str = f"{len(backups)} snapshot files removed" if backups else "Backups empty"
    print(f"{CYAN}|{RESET}   Point-in-Time:      {GREEN}{bk_str:<46}{RESET}{CYAN}|{RESET}")

    tools = summary.get("cleared_dynamic_tools", [])
    tool_str = f"{len(tools)} dynamic tools pruned" if tools else "Zero dynamic tools"
    print(f"{CYAN}|{RESET}   Dynamic Tools:      {GREEN}{tool_str:<46}{RESET}{CYAN}|{RESET}")

    caches = summary.get("cleared_pycache_dirs", [])
    cache_str = f"{len(caches)} __pycache__ trees purged"
    print(f"{CYAN}|{RESET}   Bytecode Caches:    {GREEN}{cache_str:<46}{RESET}{CYAN}|{RESET}")

    print(f"{CYAN}+---------------------------------------------------------------------+{RESET}")
    print(f"{CYAN}|{BRIGHT}   PRESERVED COMPONENTS (100% INTACT & INSTALLED):                  {RESET}{CYAN}|{RESET}")
    print(f"{CYAN}|{RESET}   {GREEN}[OK]{RESET} Python Virtual Environment (.venv) & dependencies installed     {CYAN}|{RESET}")
    print(f"{CYAN}|{RESET}   {GREEN}[OK]{RESET} Git Repository (.git) & all source code files                    {CYAN}|{RESET}")
    print(f"{CYAN}|{RESET}   {GREEN}[OK]{RESET} Configuration templates ready for fresh bootstrap                {CYAN}|{RESET}")
    print(f"{CYAN}+=====================================================================+{RESET}\n")


def run_clean_setup(
    interactive: bool = True,
    auto_setup: bool = False,
    force: bool = False,
    keep_env: bool = False,
    keep_backups: bool = False,
    keep_logs: bool = False,
    dry_run: bool = False,
    root_dir: Optional[str] = None
):
    """Interactive or headless orchestrator for full clean slate server setup."""
    print("\n" + "=" * 67)
    print(f"  {CYAN}C.O.R.E. AI :: ZERO-RESIDUE CLEAN SLATE SERVER RESET{RESET}")
    print("=" * 67)
    print("Purges all runtime data, database state, logs, secrets, and caches")
    print("so you can perform a brand new, clean setup on your server.")
    print("All code files, dependencies, and virtual environments remain intact.\n")

    if not force and interactive:
        confirm = prompt_yn(f"{RED}[!] Are you sure you want to clean-wipe all server state?{RESET}", default=False)
        if not confirm:
            print(f"{YELLOW}[*] Clean reset cancelled by operator.{RESET}\n")
            return

    results = clean_system_state(
        root_dir=root_dir,
        wipe_db=True,
        wipe_env=not keep_env,
        wipe_logs=not keep_logs,
        wipe_backups=not keep_backups,
        wipe_dynamic_tools=True,
        wipe_pycache=True,
        stop_services=True,
        dry_run=dry_run
    )

    print_clean_summary_card(results)

    if dry_run:
        print("[*] Dry-run completed. No files were removed.")
        return

    # Post-clean handover
    if auto_setup:
        print(f"\n{CYAN}[*] Automatically launching system bootstrap wizard...{RESET}\n")
        from interfaces.install.setup_service import run_service_setup
        run_service_setup()
    elif interactive:
        run_now = prompt_yn("[?] Would you like to run the setup wizard now for your fresh server?", default=True)
        if run_now:
            from interfaces.install.setup_service import run_service_setup
            run_service_setup()
        else:
            print("\nClean setup complete! Ready whenever you are:")
            print(f"   {GREEN}core setup{RESET}            Configure operator identity, models & autostart")
            print(f"   {GREEN}core run{RESET}              Launch Core AI Interactive Terminal")
            print(f"   {GREEN}core start{RESET}            Start 24/7 background headless server daemon\n")
    else:
        print("[OK] Clean reset complete. Run 'core setup' or 'core run' to initialize your fresh server.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Core AI Zero-Residue Clean Slate Reset: Purge all runtime data while keeping all files installed."
    )
    parser.add_argument(
        "-y", "--yes", "--force",
        dest="force",
        action="store_true",
        help="Bypass interactive confirmation prompt."
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Automatically launch the setup wizard immediately after cleaning."
    )
    parser.add_argument(
        "--no-setup",
        action="store_true",
        help="Do not prompt to launch setup wizard."
    )
    parser.add_argument(
        "--keep-env",
        action="store_true",
        help="Keep config/.env without deleting API keys or secrets."
    )
    parser.add_argument(
        "--keep-backups",
        action="store_true",
        help="Keep snapshot files in backups/ directory."
    )
    parser.add_argument(
        "--keep-logs",
        action="store_true",
        help="Keep existing logs in logs/ directory."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview files that would be deleted without deleting anything."
    )

    args = parser.parse_args()

    run_clean_setup(
        interactive=not args.force and not args.no_setup,
        auto_setup=args.setup,
        force=args.force,
        keep_env=args.keep_env,
        keep_backups=args.keep_backups,
        keep_logs=args.keep_logs,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
