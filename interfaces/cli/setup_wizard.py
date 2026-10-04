import os
import sys
import secrets
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Ensure root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.state import StateManager
from core.schemas import UserProfile
from brain.model_router import ModelRouter

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


def is_account_initialized(state: Optional[StateManager] = None) -> bool:
    """Checks whether the operator has completed first-run sovereign account setup."""
    mgr = state or StateManager()
    profile = mgr.get_user_profile()
    # If the preferred_name is default "User" and has no custom preferences, it is uninitialized
    if profile.preferred_name == "User" and not profile.preferences.get("primary_space"):
        return False
    return True


def save_env_variable(key: str, value: str, env_path: str = "config/.env"):
    """Atomically sets or updates an environment variable in config/.env."""
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    lines: List[str] = []
    found = False

    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"export {key}="):
            prefix = "export " if stripped.startswith("export ") else ""
            lines[idx] = f"{prefix}{key}={value}\n"
            found = True
            break

    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    os.environ[key] = value


def print_account_status_card(state: Optional[StateManager] = None):
    """Prints a high-contrast terminal card of the Sovereign Account."""
    mgr = state or StateManager()
    profile = mgr.get_user_profile()
    zones = mgr.list_zones()
    devices = mgr.list_all_devices()
    auth_secret = os.getenv("CORE_AUTH_SECRET", "core_sovereign_secret")
    is_custom_secret = auth_secret not in ["core_sovereign_secret", "generate_your_own_sovereign_secret_key_here", ""]

    primary_space = profile.preferences.get("primary_space", "office")
    models = profile.preferences.get("models", {})
    planner_model = models.get("planner", "offline_heuristic")

    print(f"\n{CYAN}+=====================================================================+{RESET}")
    print(f"{CYAN}|{BRIGHT}   C.O.R.E. AI :: SOVEREIGN ACCOUNT IDENTITY & ACCESS MATRIX          {RESET}{CYAN}|{RESET}")
    print(f"{CYAN}+=====================================================================+{RESET}")
    print(f"{CYAN}|{RESET}   Operator Handle:    {GREEN}{profile.preferred_name:<20}{RESET} Tone: {YELLOW}{profile.preferred_tone:<16}{RESET} {CYAN}|{RESET}")
    aliases_str = ", ".join(profile.aliases) if profile.aliases else "None"
    print(f"{CYAN}|{RESET}   Aliases:            {aliases_str:<42} {CYAN}|{RESET}")
    print(f"{CYAN}|{RESET}   Primary Space:      {YELLOW}{primary_space:<20}{RESET} Total Registered Zones: {len(zones):<6} {CYAN}|{RESET}")
    auth_display = f"{GREEN}ACTIVE (Custom 256-bit){RESET}" if is_custom_secret else f"{YELLOW}DEFAULT (Setup Recommended){RESET}"
    print(f"{CYAN}|{RESET}   Sovereign Secret:   {auth_display:<50} {CYAN}|{RESET}")
    print(f"{CYAN}|{RESET}   Enrolled Devices:   {len(devices):<20} Active Model: {CYAN}{planner_model:<16}{RESET} {CYAN}|{RESET}")
    print(f"{CYAN}+=====================================================================+{RESET}\n")


def ensure_env_template(env_path: str = "config/.env", example_path: str = "config/.env.example"):
    """Ensures config/.env exists initialized from example template if absent."""
    if not os.path.exists(env_path) and os.path.exists(example_path):
        import shutil
        os.makedirs(os.path.dirname(env_path), exist_ok=True)
        shutil.copy(example_path, env_path)


def reset_account_to_day_zero(state: Optional[StateManager] = None, full_wipe: bool = True) -> bool:
    """Resets local state database to a clean Day-Zero blank slate."""
    mgr = state or StateManager()
    default_profile = UserProfile(
        user_id="primary_user",
        preferred_name="User",
        aliases=[],
        preferred_tone="friendly_concise",
        preferences={}
    )
    mgr.save_user_profile(default_profile)
    if full_wipe:
        conn = mgr._get_connection()
        try:
            conn.execute("DELETE FROM zones")
            conn.execute("DELETE FROM device_topology")
            conn.execute("DELETE FROM audio_routes")
            conn.execute("DELETE FROM execution_logs")
            conn.execute("DELETE FROM pipeline_steps")
            conn.execute("DELETE FROM pipelines")
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
    return True


def run_setup(state: Optional[StateManager] = None):
    """Interactive first-run configuration wizard for Day-Zero initialization."""
    ensure_env_template()
    load_dotenv("config/.env")
    mgr = state or StateManager()
    router = ModelRouter(state_manager=mgr)

    print("\n" + "=" * 67)
    print(f"  {CYAN}C.O.R.E. AI :: SOVEREIGN LIFE OS - FIRST-RUN SETUP WIZARD{RESET}")
    print("=" * 67)
    print("Zero corporate telemetry. 100% self-hosted and private.")
    print("This wizard configures your local sovereign instance with zero hardcoding.\n")

    current_profile = mgr.get_user_profile()
    current_name = current_profile.preferred_name if current_profile.preferred_name != "User" else "Operator"

    # 1. Operator Identity
    name = input(f"[*] What name or call sign should Core AI call you? [{current_name}]: ").strip()
    if not name:
        name = current_name

    aliases_raw = input("[*] Any nicknames or aliases? (comma-separated, optional): ").strip()
    aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()] if aliases_raw else current_profile.aliases

    # 2. Primary Initial Physical Space
    initial_zone = input("[*] What is your primary initial space? (e.g. office, studio, sanctuary, lab, workshop) [office]: ").strip()
    if not initial_zone:
        initial_zone = "office"

    # 3. Communication Style Tone
    print("\nPreferred communication style:")
    print("  1) Friendly & Concise (Default)")
    print("  2) Tactical & Direct (Jarvis-style)")
    print("  3) Casual & Relaxed")
    tone_choice = input("Select [1-3, Default=1]: ").strip()
    tones = {"1": "friendly_concise", "2": "tactical_direct", "3": "casual_relaxed"}
    selected_tone = tones.get(tone_choice, "friendly_concise")

    # 4. Intelligence Provider
    print("\nPreferred AI Intelligence Provider:")
    print("  1) Local Ollama (100% Offline Silicon - e.g. qwen3.5, llama3)")
    print("  2) Google Gemini API (High-Speed Cloud Reasoning - e.g. gemini-2.5-flash)")
    print("  3) OpenAI API (e.g. gpt-4o)")
    print("  4) Pure Offline Heuristic Engine (Zero external dependencies)")
    ai_choice = input("Select [1-4, Default=1]: ").strip()

    models_pref = dict(router.get_model_preferences())
    if ai_choice == "2":
        models_pref["planner"] = "gemini/gemini-2.5-flash"
        models_pref["deep_reasoning"] = "gemini/gemini-2.5-pro"
        if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
            key_input = input("[*] Enter your GEMINI_API_KEY (leave blank to skip): ").strip()
            if key_input:
                router.set_api_key("GEMINI", key_input, persist_to_env=True)
    elif ai_choice == "3":
        models_pref["planner"] = "openai/gpt-4o-mini"
        models_pref["deep_reasoning"] = "openai/gpt-4o"
        if not os.getenv("OPENAI_API_KEY"):
            key_input = input("[*] Enter your OPENAI_API_KEY (leave blank to skip): ").strip()
            if key_input:
                router.set_api_key("OPENAI", key_input, persist_to_env=True)
    elif ai_choice == "4":
        models_pref["planner"] = "offline_heuristic"
    else:
        models_pref["planner"] = "ollama/qwen3.5:2b"
        models_pref["fallback"] = "offline_heuristic"

    # 5. Master Sovereign Auth Secret (for Owner Tier Enrollment)
    existing_secret = os.getenv("CORE_AUTH_SECRET", "")
    if not existing_secret or existing_secret in ["core_sovereign_secret", "generate_your_own_sovereign_secret_key_here"]:
        suggested_secret = secrets.token_hex(16)
        print(f"\n[*] A secure Sovereign Auth Secret is required to enroll external devices (phone, laptop) into OWNER tier.")
        sec_input = input(f"[*] Enter master secret or press Enter to auto-generate [{suggested_secret}]: ").strip()
        auth_secret = sec_input if sec_input else suggested_secret
        save_env_variable("CORE_AUTH_SECRET", auth_secret)
        print(f"    [+] Saved master secret to config/.env")
    else:
        auth_secret = existing_secret

    # 6. Intercontinental Mesh Role
    print("\nIntercontinental Mesh Role for this device:")
    print("  1) Main Server (Always-on host machine / homelab / workstation)")
    print("  2) Roaming Edge Node (Mobile companion, laptop, or vehicle unit)")
    role_choice = input("Select [1-2, Default=1]: ").strip()
    node_role = "edge_node" if role_choice == "2" else "main_server"
    main_server_url = "http://localhost:8000"
    if node_role == "edge_node":
        custom_url = input("[*] Enter Main Core Server URL [http://localhost:8000]: ").strip()
        if custom_url:
            main_server_url = custom_url

    # Save profile to local SQLite database
    profile = UserProfile(
        user_id="primary_user",
        preferred_name=name,
        aliases=aliases,
        preferred_tone=selected_tone,
        preferences={
            "primary_space": initial_zone,
            "models": models_pref,
            "mesh": {
                "role": node_role,
                "main_server_url": main_server_url
            }
        }
    )
    mgr.save_user_profile(profile)
    mgr.ensure_zone_exists(initial_zone, display_name=initial_zone.title())

    print("\n" + "-" * 67)
    print(f"  {GREEN}[OK]{RESET} Sovereign Operator:  {name} (Aliases: {', '.join(aliases) if aliases else 'None'})")
    print(f"  {GREEN}[OK]{RESET} Primary Space:       '{initial_zone}'")
    print(f"  {GREEN}[OK]{RESET} Communication Tone:  '{selected_tone}'")
    print(f"  {GREEN}[OK]{RESET} Default Planner:     '{models_pref['planner']}'")
    print(f"  {GREEN}[OK]{RESET} Sovereign Secret:    [CONFIGURED]")
    print(f"  {GREEN}[OK]{RESET} Mesh Role:           Role='{node_role}' | Server='{main_server_url}'")
    print("-" * 67)
    print("\nSetup complete! You can interact with Core AI via:")
    print("   core run              Launch the Core AI Interactive Terminal")
    print("   core start            Start 24/7 background headless server daemon")
    print("   core status           Inspect server status card")
    print("   core \"your goal\"      Execute one-shot task directly from terminal\n")
    return profile


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print_account_status_card()
    elif len(sys.argv) > 1 and sys.argv[1] == "reset":
        force = "--force" in sys.argv or "-f" in sys.argv
        if not force:
            confirm = input("[!] Are you sure you want to reset your local Sovereign Account and data to Day-Zero? [y/N]: ").strip().lower()
            do_reset = confirm in ["y", "yes"]
        else:
            do_reset = True
        if do_reset:
            reset_account_to_day_zero(full_wipe=True)
            print("[OK] Local database and operator account reset to Day-Zero blank slate.")
        else:
            print("[*] Reset cancelled.")
    else:
        run_setup()
