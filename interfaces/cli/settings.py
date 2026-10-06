import os
import sys
import json
from typing import Optional, List, Dict, Any

# Ensure project root is on sys.path
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


class SettingsCLI:
    """
    Dedicated CLI Configuration & Settings Controller:
    - Easy inspection and assignment of AI model roles (planner, fallback, deep_reasoning, fast_local).
    - Provider API key configuration with automatic persistent updates to config/.env.
    - Operator identity, communication tone, and primary spatial zone customization.
    - Mesh role and server URL pairing.
    """

    def __init__(self, state_manager: Optional[StateManager] = None):
        self.state_manager = state_manager or StateManager()
        self.model_router = ModelRouter(state_manager=self.state_manager)

    def print_settings_overview(self):
        """Prints a comprehensive high-contrast terminal settings overview."""
        profile = self.state_manager.get_user_profile()
        prefs = profile.preferences
        models = self.model_router.get_model_preferences()
        summary = self.model_router.get_status_summary()
        zones = self.state_manager.list_zones()
        devices = self.state_manager.list_all_devices()

        primary_space = prefs.get("primary_space", "office")
        mesh_role = prefs.get("mesh", {}).get("role", "main_server")
        server_url = prefs.get("mesh", {}).get("main_server_url", "http://localhost:8000")

        print(f"\n{CYAN}+=====================================================================+{RESET}")
        print(f"{CYAN}|{BRIGHT}   CORE AI :: SOVEREIGN SYSTEM SETTINGS & CUSTOMIZATION MATRIX       {RESET}{CYAN}|{RESET}")
        print(f"{CYAN}+=====================================================================+{RESET}")
        print(f"{CYAN}|{RESET}   Operator Handle:    {GREEN}{profile.preferred_name:<20}{RESET} Tone: {YELLOW}{profile.preferred_tone:<16}{RESET} {CYAN}|{RESET}")
        aliases_str = ", ".join(profile.aliases) if profile.aliases else "None"
        print(f"{CYAN}|{RESET}   Operator Aliases:   {aliases_str:<42} {CYAN}|{RESET}")
        print(f"{CYAN}|{RESET}   Primary Space:      {YELLOW}{primary_space:<20}{RESET} Registered Zones: {len(zones):<7} {CYAN}|{RESET}")
        print(f"{CYAN}|{RESET}   Mesh Node Role:     {CYAN}{mesh_role.upper():<20}{RESET} Mesh Server: {server_url:<12} {CYAN}|{RESET}")
        print(f"{CYAN}+---------------------------------------------------------------------+{RESET}")
        print(f"{CYAN}|{BRIGHT}   AI MODEL ROLES                                                    {RESET}{CYAN}|{RESET}")
        print(f"{CYAN}+---------------------------------------------------------------------+{RESET}")
        for role, model_name in models.items():
            avail = self.model_router.check_model_availability(model_name)
            st_lbl = f"{GREEN}[ONLINE]{RESET}" if avail else f"{YELLOW}[OFFLINE/UNREACHABLE]{RESET}"
            print(f"{CYAN}|{RESET}   {role:<16}: {BRIGHT}{model_name:<28}{RESET} {st_lbl}")

        print(f"{CYAN}+---------------------------------------------------------------------+{RESET}")
        print(f"{CYAN}|{BRIGHT}   CONFIGURED AI PROVIDERS                                            {RESET}{CYAN}|{RESET}")
        print(f"{CYAN}+---------------------------------------------------------------------+{RESET}")
        for prov, online in summary.get("configured_providers", {}).items():
            st_str = f"{GREEN}CONNECTED / AVAILABLE{RESET}" if online else f"{YELLOW}NOT CONFIGURED{RESET}"
            print(f"{CYAN}|{RESET}   - {prov:<18}: {st_str}")

        ollama_models = summary.get("ollama_models", [])
        if ollama_models:
            print(f"{CYAN}|{RESET}   Installed in Ollama: {CYAN}{', '.join(ollama_models)}{RESET}")

        print(f"{CYAN}+=====================================================================+{RESET}\n")
        print(f"  Configuration Commands:")
        print(f"    core config model                     (Interactive easy AI model selector)")
        print(f"    core config model <role> <model>      (Assign model to role: planner, fallback, ...)")
        print(f"    core config key <provider> <key>      (Set API key for gemini, openai, anthropic, ...)")
        print(f"    core config operator <name>           (Set operator preferred name)")
        print(f"    core config zone <zone_name>          (Set operator primary spatial zone)")
        print(f"    core config tone <tone_style>         (Set communication tone: concise, cyberpunk, ...)")
        print(f"    core config mesh <main_server|edge>   (Set mesh operational role)\n")

    def list_available_models(self) -> Dict[str, List[str]]:
        """Collects all detectable models across local Ollama and configured providers."""
        available: Dict[str, List[str]] = {
            "ollama": [],
            "cloud": []
        }
        # Check Ollama
        if self.model_router.is_ollama_online():
            for m in self.model_router.get_installed_ollama_models():
                available["ollama"].append(f"ollama/{m}")
        if not available["ollama"]:
            available["ollama"] = ["ollama/qwen3.5:2b", "ollama/llama3", "ollama/qwen2.5-coder"]

        # Check cloud providers
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            available["cloud"].extend(["gemini/gemini-2.5-flash", "gemini/gemini-2.5-pro"])
        if os.getenv("OPENAI_API_KEY"):
            available["cloud"].extend(["openai/gpt-4o-mini", "openai/gpt-4o"])
        if os.getenv("ANTHROPIC_API_KEY"):
            available["cloud"].extend(["anthropic/claude-3-5-sonnet-20241022", "anthropic/claude-3-5-haiku-20241022"])
        if os.getenv("GROQ_API_KEY"):
            available["cloud"].extend(["groq/llama-3.3-70b-versatile"])
        if os.getenv("DEEPSEEK_API_KEY"):
            available["cloud"].extend(["deepseek/deepseek-chat", "deepseek/deepseek-reasoner"])

        return available

    def interactive_model_selector(self):
        """Provides an interactive terminal menu for selecting and binding AI models."""
        avail = self.list_available_models()
        all_candidates: List[str] = []
        for cat, m_list in avail.items():
            all_candidates.extend(m_list)

        # Deduplicate preserving order
        unique_candidates: List[str] = []
        for c in all_candidates:
            if c not in unique_candidates:
                unique_candidates.append(c)

        print(f"\n{CYAN}+=====================================================================+{RESET}")
        print(f"{CYAN}|{BRIGHT}   CORE AI :: DEDICATED AI MODEL SELECTOR                             {RESET}{CYAN}|{RESET}")
        print(f"{CYAN}+=====================================================================+{RESET}")
        print(f"Detected & Available AI Models:\n")
        for idx, model in enumerate(unique_candidates, 1):
            is_online = self.model_router.check_model_availability(model)
            st = f"{GREEN}[ONLINE]{RESET}" if is_online else f"{YELLOW}[AVAILABLE/OFFLINE]{RESET}"
            print(f"  [{idx}] {BRIGHT}{model:<36}{RESET} {st}")

        print(f"\nSelect target role:")
        print(f"  [1] planner        (Main cognitive decomposition & tool calling)")
        print(f"  [2] deep_reasoning (Heavy multi-step analysis & mathematics)")
        print(f"  [3] fallback       (Backup model if primary provider is offline)")
        print(f"  [4] fast_local     (Ultra-low latency local execution)")
        print(f"  [5] ALL ROLES      (Apply selection to all roles at once)")

        try:
            role_choice = input(f"\nEnter role number [1-5, or Enter to cancel]: ").strip()
            if not role_choice:
                print("[*] Selection cancelled.")
                return

            role_map = {
                "1": "planner",
                "2": "deep_reasoning",
                "3": "fallback",
                "4": "fast_local",
                "5": "all"
            }
            target_role = role_map.get(role_choice)
            if not target_role:
                print(f"{RED}[-] Invalid role selection.{RESET}")
                return

            model_choice = input(f"Enter model number [1-{len(unique_candidates)}, or custom name]: ").strip()
            if not model_choice:
                print("[*] Selection cancelled.")
                return

            if model_choice.isdigit() and 1 <= int(model_choice) <= len(unique_candidates):
                selected_model = unique_candidates[int(model_choice) - 1]
            else:
                selected_model = model_choice.strip()

            if target_role == "all":
                for r in ["planner", "deep_reasoning", "fallback", "fast_local"]:
                    self.model_router.set_model_preference(r, selected_model)
                print(f"{GREEN}[OK] Successfully assigned '{selected_model}' to ALL AI roles!{RESET}")
            else:
                self.model_router.set_model_preference(target_role, selected_model)
                print(f"{GREEN}[OK] Successfully assigned '{selected_model}' to role '{target_role}'!{RESET}")

        except (KeyboardInterrupt, EOFError):
            print("\n[*] Selection cancelled.")

    def set_model(self, role: str, model_name: str):
        """Sets model preference directly via CLI arguments."""
        clean_role = role.lower().strip()
        if clean_role == "all":
            for r in ["planner", "deep_reasoning", "fallback", "fast_local"]:
                self.model_router.set_model_preference(r, model_name)
            print(f"{GREEN}[OK] Assigned '{model_name}' to ALL model roles.{RESET}")
        else:
            self.model_router.set_model_preference(clean_role, model_name)
            print(f"{GREEN}[OK] Role '{clean_role}' assigned to: {model_name}{RESET}")

    def set_key(self, provider: str, key: str):
        """Sets API key directly via CLI arguments."""
        env_var = self.model_router.set_api_key(provider=provider, api_key=key, persist_to_env=True)
        print(f"{GREEN}[OK] Configured API key for '{provider.upper()}' (persisted to {env_var}).{RESET}")

    def set_operator(self, name: str):
        """Sets operator preferred name."""
        profile = self.state_manager.get_user_profile()
        profile.preferred_name = name.strip()
        self.state_manager.save_user_profile(profile)
        print(f"{GREEN}[OK] Sovereign Operator handle updated to: {name.strip()}{RESET}")

    def set_zone(self, zone_name: str):
        """Sets operator primary spatial zone."""
        clean_zone = zone_name.strip().lower()
        self.state_manager.ensure_zone_exists(clean_zone, display_name=clean_zone.title())
        profile = self.state_manager.get_user_profile()
        profile.preferences["primary_space"] = clean_zone
        self.state_manager.save_user_profile(profile)
        print(f"{GREEN}[OK] Operator primary spatial space updated to: '{clean_zone}'{RESET}")

    def set_tone(self, tone: str):
        """Sets communication tone."""
        clean_tone = tone.strip().lower()
        profile = self.state_manager.get_user_profile()
        profile.preferred_tone = clean_tone
        self.state_manager.save_user_profile(profile)
        print(f"{GREEN}[OK] Communication tone updated to: '{clean_tone}'{RESET}")

    def set_mesh(self, role: str, url: Optional[str] = None):
        """Sets mesh role and optional main server URL."""
        clean_role = "main_server" if "main" in role.lower() else "edge_node"
        profile = self.state_manager.get_user_profile()
        if "mesh" not in profile.preferences:
            profile.preferences["mesh"] = {}
        profile.preferences["mesh"]["role"] = clean_role
        if url:
            profile.preferences["mesh"]["main_server_url"] = url.rstrip("/")
        self.state_manager.save_user_profile(profile)
        print(f"{GREEN}[OK] Mesh configuration updated: role='{clean_role}'{RESET}")


def main():
    cli = SettingsCLI()
    args = sys.argv[1:]

    if not args or args[0] in ["status", "overview", "show", "info"]:
        cli.print_settings_overview()
    elif args[0] in ["model", "models"]:
        if len(args) == 1 or args[1] in ["select", "picker", "choose"]:
            cli.interactive_model_selector()
        elif len(args) >= 3:
            cli.set_model(role=args[1], model_name=args[2])
        elif len(args) == 2:
            cli.set_model(role="planner", model_name=args[1])
    elif args[0] in ["key", "api-key"]:
        if len(args) >= 3:
            cli.set_key(provider=args[1], key=args[2])
        else:
            print("Usage: core config key <provider> <api_key> (e.g. core config key gemini AIza...)")
    elif args[0] in ["operator", "name", "user"]:
        if len(args) >= 2:
            cli.set_operator(" ".join(args[1:]))
        else:
            print("Usage: core config operator <name>")
    elif args[0] in ["zone", "space"]:
        if len(args) >= 2:
            cli.set_zone(args[1])
        else:
            print("Usage: core config zone <zone_name>")
    elif args[0] in ["tone"]:
        if len(args) >= 2:
            cli.set_tone(args[1])
        else:
            print("Usage: core config tone <concise|professional|warm|jarvis|cyberpunk>")
    elif args[0] in ["mesh"]:
        if len(args) >= 3:
            cli.set_mesh(args[1], args[2])
        elif len(args) == 2:
            cli.set_mesh(args[1])
        else:
            print("Usage: core config mesh <main_server|edge_node> [server_url]")
    else:
        print(f"Unknown config command: {args[0]}")
        cli.print_settings_overview()

if __name__ == "__main__":
    main()
