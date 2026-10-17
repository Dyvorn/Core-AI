import os
import sys
import json
import argparse
import subprocess
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

# Ensure project root is on sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Standard ANSI colors for clean terminal output
ESC = "\033"
CYAN = f"{ESC}[36m"
GREEN = f"{ESC}[32m"
YELLOW = f"{ESC}[33m"
RED = f"{ESC}[31m"
BOLD = f"{ESC}[1m"
RESET = f"{ESC}[0m"

# Windows console UTF-8 setup
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def execute_via_daemon(
    goal: str,
    host: str = "127.0.0.1",
    port: int = 8000,
    timeout: float = 60.0,
    context: Optional[Dict[str, Any]] = None,
    base_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends one-shot goal directly to the 24/7 background microkernel daemon or central mesh server via HTTP POST.
    Uses 127.0.0.1 directly to bypass Windows IPv6 localhost DNS resolution delays.
    """
    url = f"{base_url.rstrip('/')}/api/v1/pipeline/solve_sync" if base_url else f"http://{host}:{port}/api/v1/pipeline/solve_sync"
    payload = {
        "goal": goal,
        "context": context or {"channel": "fast_cli", "client": "client.py"}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "CoreAI-FastCLI/2.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fallback_in_process(goal: str, port: int) -> int:
    """Seamlessly falls back to in-process execution if the daemon is offline."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    main_script = os.path.join(root_dir, "main.py")
    python_bin = sys.executable

    print(f"{YELLOW}[*] Daemon offline. Launching in-process microkernel...{RESET}")
    cmd = [python_bin, "-u", main_script, "--headless", "--port", str(port), "--solve", goal]
    try:
        return subprocess.call(cmd, cwd=root_dir)
    except Exception as e:
        print(f"{RED}[!] Failed to run in-process solver: {e}{RESET}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Core AI Instant CLI Dispatcher (Alpha 0.2)",
        prog="core"
    )
    parser.add_argument("goal", nargs="*", help="Goal or task to execute")
    parser.add_argument("--port", type=int, default=int(os.getenv("CORE_PORT", 8000)), help="Gateway daemon port")
    parser.add_argument("--host", type=str, default=os.getenv("CORE_HOST", "127.0.0.1"), help="Gateway daemon host")
    parser.add_argument("--timeout", type=float, default=60.0, help="Execution timeout in seconds")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress prefix header")

    args, extra_cli_flags = parser.parse_known_args()
    if extra_cli_flags:
        args.goal.extend(extra_cli_flags)

    goal_text = " ".join(args.goal).strip()
    if not goal_text:
        # If no goal provided, launch interactive console via main.py
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        main_script = os.path.join(root_dir, "main.py")
        return subprocess.call([sys.executable, "-u", main_script], cwd=root_dir)

    if goal_text.lower() in ("clean", "clean-setup", "factory-reset", "factory_reset"):
        from interfaces.install.clean_setup import run_clean_setup
        run_clean_setup(interactive=True)
        return 0

    if goal_text.lower() in ("app", "chat", "ui", "companion"):
        from interfaces.app.app import launch_app
        return launch_app(port=args.port)

    if goal_text.lower().startswith("audio") or goal_text.lower().startswith("mics") or goal_text.lower().startswith("speakers"):
        from interfaces.cli.settings import SettingsCLI
        SettingsCLI().list_audio_devices()
        return 0

    if goal_text.lower() in ("mute", "mic off", "voice off", "listen off"):
        from interfaces.cli.settings import SettingsCLI
        SettingsCLI().set_listening(enabled=False)
        return 0

    if goal_text.lower() in ("unmute", "mic on", "voice on", "listen on"):
        from interfaces.cli.settings import SettingsCLI
        SettingsCLI().set_listening(enabled=True)
        return 0

    if goal_text.lower() in ("mic status", "listen status", "voice status", "mic state", "listen state"):
        from interfaces.cli.settings import SettingsCLI
        SettingsCLI().get_listening_status()
        return 0

    if goal_text.lower().startswith("listen"):
        from interfaces.cli.settings import SettingsCLI
        cli = SettingsCLI()
        parts = goal_text.split(maxsplit=2)
        if len(parts) > 1 and parts[1].lower() in ("off", "pause", "mute", "disable", "deactivate", "stop"):
            cli.set_listening(enabled=False)
        elif len(parts) > 1 and parts[1].lower() in ("on", "resume", "unmute", "enable", "activate", "start"):
            cli.set_listening(enabled=True)
        elif len(parts) > 1 and parts[1].lower() == "toggle":
            cli.set_listening(action="toggle")
        else:
            cli.get_listening_status()
        return 0

    if goal_text.lower().startswith("mic"):
        from interfaces.cli.settings import SettingsCLI
        cli = SettingsCLI()
        parts = goal_text.split(maxsplit=2)
        if len(parts) == 1:
            cli.list_audio_devices()
        elif parts[1].lower() in ("off", "pause", "mute", "disable", "deactivate", "stop"):
            cli.set_listening(enabled=False)
        elif parts[1].lower() in ("on", "resume", "unmute", "enable", "activate", "start"):
            cli.set_listening(enabled=True)
        elif parts[1].lower() in ("toggle",):
            cli.set_listening(action="toggle")
        elif parts[1].lower() in ("status", "state"):
            cli.get_listening_status()
        elif parts[1] == "test":
            cli.test_mic()
        elif parts[1] == "set" and len(parts) > 2:
            cli.set_mic(parts[2])
        else:
            cli.set_mic(" ".join(parts[1:]))
        return 0

    if goal_text.lower().startswith("speaker"):
        from interfaces.cli.settings import SettingsCLI
        cli = SettingsCLI()
        parts = goal_text.split(maxsplit=2)
        if len(parts) == 1:
            cli.list_audio_devices()
        elif parts[1] == "set" and len(parts) > 2:
            cli.set_speaker(parts[2])
        else:
            cli.set_speaker(" ".join(parts[1:]))
        return 0

    if goal_text.lower().startswith("edit"):
        from interfaces.cli.settings import SettingsCLI
        parts = goal_text.split(maxsplit=1)
        target = parts[1] if len(parts) > 1 else "config"
        SettingsCLI().edit_file(target)
        return 0

    if goal_text.lower().startswith("mesh"):
        from core.mesh_client import main as mesh_main
        old_argv = sys.argv
        try:
            parts = goal_text.split()
            sys.argv = ["mesh_client"] + parts[1:]
            mesh_main()
            return 0
        finally:
            sys.argv = old_argv

    if goal_text.lower().startswith("speak"):
        parts = goal_text.split(maxsplit=1)
        phrase = parts[1] if len(parts) > 1 else ""
        if not phrase:
            print(f"{YELLOW}Usage: core speak <text>{RESET}")
            return 1
        try:
            from engines.voice_out import VoiceOutEngine
            vo = VoiceOutEngine(default_voice="auto")
            print(f"[*] Speaking: \"{phrase}\"")
            vo.synthesize_and_play(phrase, blocking=True)
            return 0
        except Exception as e:
            print(f"{RED}[!] Speech synthesis failed: {e}{RESET}")
            return 1

    if goal_text.lower() in ("version", "--version", "-v"):
        from core import __version__, __codename__
        from core.updater import CoreUpdater
        from core.terminal import render_box
        updater = CoreUpdater()
        commit = updater.get_current_commit() or "dev"
        try:
            from core.mesh_client import MeshClient
            mc = MeshClient()
            role_str = mc.role.upper()
            server_str = mc.main_server_url
        except Exception:
            role_str = "STANDALONE"
            server_str = "http://localhost:8000"

        card = render_box(
            title="C.O.R.E. AI :: SYSTEM VERSION PROTOCOL",
            rows=[
                ("Version:", f"{GREEN}v{__version__}{RESET}"),
                ("Codename:", f"{CYAN}{__codename__}{RESET}"),
                ("Commit:", f"{YELLOW}{commit}{RESET}"),
                ("Node Role:", f"{CYAN}{role_str}{RESET}"),
                ("Mesh Server:", server_str),
                ("Sovereignty:", f"{GREEN}Zero Telemetry · 100% Local Compute · AGPL-3.0{RESET}")
            ],
            width=71
        )
        print(f"\n{card}\n")
        return 0

    # Normalize localhost to 127.0.0.1 to avoid Windows IPv6 DNS resolution latency
    target_host = "127.0.0.1" if args.host.lower() in ("localhost", "127.0.0.1") else args.host
    server_base_url = None

    # Auto-detect if this machine is configured as an edge node paired to a central server
    try:
        from core.mesh_client import MeshClient
        mc = MeshClient()
        if mc.role == "edge_node" and mc.main_server_url and args.host in ("127.0.0.1", "localhost", os.getenv("CORE_HOST", "127.0.0.1")):
            server_base_url = mc.main_server_url
    except Exception:
        pass

    try:
        res = execute_via_daemon(
            goal=goal_text,
            host=target_host,
            port=args.port,
            timeout=args.timeout,
            base_url=server_base_url
        )
        if args.json:
            print(json.dumps(res, indent=2))
            return 0 if res.get("status") == "completed" else 1

        spoken = res.get("spoken_response") or res.get("final_output")
        if not spoken and res.get("steps"):
            last_step = res["steps"][-1]
            step_out = last_step.get("output")
            if isinstance(step_out, dict):
                spoken = step_out.get("message") or step_out.get("status") or str(step_out)
            else:
                spoken = str(step_out)

        if not spoken:
            spoken = "Task completed."

        status = res.get("status", "completed")
        if status == "completed":
            if args.quiet:
                print(spoken)
            else:
                print(f"\n{CYAN}Core AI:{RESET} {BOLD}{spoken}{RESET}\n")
            return 0
        else:
            err = res.get("error_summary") or "Pipeline encountered an execution issue."
            print(f"\n{RED}Core AI [Error]:{RESET} {spoken}")
            if err:
                print(f"{YELLOW}Details:{RESET} {err}\n")
            return 1

    except (urllib.error.URLError, ConnectionRefusedError, OSError):
        # Daemon is offline or refused connection -> Instant fallback
        return fallback_in_process(goal_text, args.port)
    except Exception as e:
        print(f"{RED}[!] Daemon dispatch error: {e}{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
