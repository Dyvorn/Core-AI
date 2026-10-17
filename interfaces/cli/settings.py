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

# Windows console UTF-8 setup
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


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

    def edit_file(self, target: str = "config"):
        """Opens configuration file in operator's system editor."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        t_lower = target.lower()
        if t_lower in ("env", "keys", "secrets", ".env"):
            file_path = os.path.join(root_dir, "config", ".env")
        else:
            file_path = os.path.join(root_dir, "config", "settings.yaml")

        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# Core AI Sovereign Configuration\n")

        editor = os.environ.get("EDITOR")
        if not editor:
            if os.name == "nt":
                editor = "notepad.exe"
            else:
                for candidate in ["nano", "vim", "vi"]:
                    import shutil
                    if shutil.which(candidate):
                        editor = candidate
                        break
                editor = editor or "nano"

        print(f"{CYAN}[*] Opening {file_path} in {editor}...{RESET}")
        import subprocess
        subprocess.call([editor, file_path])

    def list_audio_devices(self):
        """Displays all host input (mic) and output (speaker) devices."""
        from engines.audio_router import SpatialAudioRouter
        router = SpatialAudioRouter(state_manager=self.state_manager)
        devs = router.list_system_audio_devices()
        profile = self.state_manager.get_user_profile()
        audio_prefs = profile.preferences.get("audio", {})
        active_mic = os.getenv("CORE_MIC_DEVICE", audio_prefs.get("mic_device"))
        active_spk = os.getenv("CORE_SPEAKER_DEVICE", audio_prefs.get("speaker_device"))

        print(f"\n{BRIGHT}=== Host Audio Input Interfaces (Microphones) [{len(devs['inputs'])}] ==={RESET}")
        for d in devs["inputs"]:
            is_active = " [ACTIVE]" if (active_mic is not None and (str(active_mic) == str(d['index']) or str(active_mic).lower() in d['name'].lower())) else ""
            print(f"  [{d['index']:2d}] {d['name']} (Channels={d['max_input_channels']}, {d['default_samplerate']:.0f}Hz){GREEN}{is_active}{RESET}")

        print(f"\n{BRIGHT}=== Host Audio Output Interfaces (Speakers) [{len(devs['outputs'])}] ==={RESET}")
        for d in devs["outputs"]:
            is_active = " [ACTIVE]" if (active_spk is not None and (str(active_spk) == str(d['index']) or str(active_spk).lower() in d['name'].lower())) else ""
            print(f"  [{d['index']:2d}] {d['name']} (Channels={d['max_output_channels']}, {d['default_samplerate']:.0f}Hz){GREEN}{is_active}{RESET}")

        print(f"\n  To set microphone:  {CYAN}core mic <index|name>{RESET}")
        print(f"  To set speaker:     {CYAN}core speaker <index|name>{RESET}")
        print(f"  To test microphone: {CYAN}core mic test{RESET}\n")

    def set_mic(self, query: str):
        """Sets active microphone device by index or substring name."""
        from engines.audio_router import SpatialAudioRouter
        router = SpatialAudioRouter(state_manager=self.state_manager)
        dev_idx = int(query) if query.isdigit() else router.resolve_device_index(query, kind="input")
        if dev_idx is None:
            print(f"{RED}[!] Microphone '{query}' not found. Run 'core audio' to inspect devices.{RESET}")
            return
        profile = self.state_manager.get_user_profile()
        if "audio" not in profile.preferences:
            profile.preferences["audio"] = {}
        profile.preferences["audio"]["mic_device"] = dev_idx
        self.state_manager.save_user_profile(profile)
        self.set_env_key("CORE_MIC_DEVICE", str(dev_idx))
        print(f"{GREEN}[OK] Default microphone set to index [{dev_idx}].{RESET}")

    def set_speaker(self, query: str):
        """Sets active speaker device by index or substring name."""
        from engines.audio_router import SpatialAudioRouter
        router = SpatialAudioRouter(state_manager=self.state_manager)
        dev_idx = int(query) if query.isdigit() else router.resolve_device_index(query, kind="output")
        if dev_idx is None:
            print(f"{RED}[!] Speaker '{query}' not found. Run 'core audio' to inspect devices.{RESET}")
            return
        profile = self.state_manager.get_user_profile()
        if "audio" not in profile.preferences:
            profile.preferences["audio"] = {}
        profile.preferences["audio"]["speaker_device"] = dev_idx
        self.state_manager.save_user_profile(profile)
        self.set_env_key("CORE_SPEAKER_DEVICE", str(dev_idx))
        print(f"{GREEN}[OK] Default speaker set to index [{dev_idx}].{RESET}")

    def test_mic(self):
        """Records 2.5 seconds of audio and displays a visual peak level meter."""
        print(f"{CYAN}[*] Testing microphone for 3 seconds... speak into your mic now!{RESET}")
        try:
            import sounddevice as sd
            import numpy as np
            profile = self.state_manager.get_user_profile()
            mic_id = profile.preferences.get("audio", {}).get("mic_device")
            recorded = sd.rec(int(16000 * 3.0), samplerate=16000, channels=1, device=mic_id, dtype='float32')
            sd.wait()
            rms = float(np.sqrt(np.mean(recorded**2))) if len(recorded) > 0 else 0.0
            peak = float(np.max(np.abs(recorded))) if len(recorded) > 0 else 0.0
            pct = min(100, int((peak / 0.8) * 100))
            bar = "█" * (pct // 5) + "░" * (20 - (pct // 5))
            status = f"{GREEN}EXCELLENT{RESET}" if peak > 0.05 else (f"{YELLOW}QUIET{RESET}" if peak > 0.01 else f"{RED}NO SIGNAL{RESET}")
            print(f"  Level: [{CYAN}{bar}{RESET}] Peak: {pct}% ({status}) | RMS: {rms:.4f}")
        except Exception as e:
            print(f"{RED}[!] Microphone test error: {e}{RESET}")

    def set_listening(self, enabled: Optional[bool] = None, action: Optional[str] = None) -> bool:
        """
        Activates, deactivates, or toggles Core AI room microphone listening.
        Sends directive to background daemon if running, and persists in user profile state.
        """
        target_enabled = enabled
        if target_enabled is None and action:
            act = action.lower()
            if act in ("pause", "stop", "mute", "off", "disable", "deactivate"):
                target_enabled = False
            elif act in ("resume", "start", "unmute", "on", "enable", "activate"):
                target_enabled = True

        port = int(os.getenv("CORE_PORT", 8000))
        url = f"http://127.0.0.1:{port}/api/v1/voice/listening"
        payload = {}
        if target_enabled is not None:
            payload["enabled"] = target_enabled
        if action:
            payload["action"] = action

        daemon_contacted = False
        new_state = target_enabled
        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "CoreAI-CLI/2.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                daemon_contacted = True
                new_state = res.get("listening_enabled", target_enabled)
        except Exception:
            # Daemon offline: apply directly to local StateManager
            profile = self.state_manager.get_user_profile()
            if "audio" not in profile.preferences:
                profile.preferences["audio"] = {}
            if target_enabled is not None:
                new_state = target_enabled
            elif action == "toggle":
                new_state = not profile.preferences["audio"].get("listening_enabled", True)
            else:
                new_state = False
            profile.preferences["audio"]["listening_enabled"] = new_state
            self.state_manager.save_user_profile(profile)

        if not new_state:
            print(f"\n{RED}[MUTED] Core AI microphone room listening DEACTIVATED.{RESET}")
            print(f"  Microphone capture is halted. Core will NOT listen or record room audio.")
            if daemon_contacted:
                print(f"  {GREEN}[OK] Daemon microphone stream closed & satellites notified.{RESET}\n")
            else:
                print(f"  {YELLOW}[OK] Preference saved. Daemon will start in muted mode.{RESET}\n")
        else:
            print(f"\n{GREEN}[LISTENING] Core AI microphone room listening ACTIVATED.{RESET}")
            print(f"  Microphone capture is live and listening for wake words.")
            if daemon_contacted:
                print(f"  {GREEN}[OK] Daemon microphone stream active.{RESET}\n")
            else:
                print(f"  {YELLOW}[OK] Preference saved. Daemon will listen when launched.{RESET}\n")

        return bool(new_state)

    def get_listening_status(self) -> bool:
        """Checks and displays whether Core AI is listening to room audio."""
        port = int(os.getenv("CORE_PORT", 8000))
        url = f"http://127.0.0.1:{port}/api/v1/voice/status"
        daemon_online = False
        is_listening = True
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "CoreAI-CLI/2.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                is_listening = data.get("listening_enabled", True)
                daemon_online = True
        except Exception:
            profile = self.state_manager.get_user_profile()
            is_listening = profile.preferences.get("audio", {}).get("listening_enabled", True)

        daemon_tag = f"{GREEN}[DAEMON ONLINE]{RESET}" if daemon_online else f"{YELLOW}[STANDALONE / SAVED PREF]{RESET}"
        if is_listening:
            print(f"\n{GREEN}[LISTENING]{RESET} Core AI microphone listening is {GREEN}ACTIVE{RESET}. {daemon_tag}")
            print(f"  Wake word detection and room speech perception are enabled.")
            print(f"  To deactivate: run {BRIGHT}'core mute'{RESET} or {BRIGHT}'core mic off'{RESET}.\n")
        else:
            print(f"\n{RED}[MUTED]{RESET} Core AI microphone listening is {RED}DEACTIVATED (MUTED){RESET}. {daemon_tag}")
            print(f"  Microphone stream is stopped. Core is NOT listening to the room.")
            print(f"  To activate: run {BRIGHT}'core unmute'{RESET} or {BRIGHT}'core mic on'{RESET}.\n")

        return bool(is_listening)

    def set_voice(self, voice_name: str):
        """Sets active neural voice by short alias or full name."""
        from engines.voice_out import VOICE_ALIASES
        clean = voice_name.strip().lower()
        resolved = VOICE_ALIASES.get(clean, voice_name.strip())
        profile = self.state_manager.get_user_profile()
        if "audio" not in profile.preferences:
            profile.preferences["audio"] = {}
        profile.preferences["audio"]["voice"] = resolved
        self.state_manager.save_user_profile(profile)
        self.set_env_key("CORE_VOICE", resolved)
        self.set_env_key("CORE_DEFAULT_DE_VOICE", resolved)
        print(f"{GREEN}[OK] Neural voice set to '{resolved}'.{RESET}")

    def set_rate(self, rate_str: str):
        """Sets speech playback speed (e.g. '+15%', '+20%')."""
        clean = rate_str.strip()
        if not clean.startswith(("+", "-")):
            clean = f"+{clean}"
        if not clean.endswith("%"):
            clean = f"{clean}%"
        profile = self.state_manager.get_user_profile()
        if "audio" not in profile.preferences:
            profile.preferences["audio"] = {}
        profile.preferences["audio"]["tts_rate"] = clean
        self.state_manager.save_user_profile(profile)
        self.set_env_key("CORE_TTS_RATE", clean)
        print(f"{GREEN}[OK] Neural speech rate set to '{clean}'.{RESET}")

    def list_voices(self):
        """Lists recommended high-fidelity neural voices."""
        print(f"\n{CYAN}+=====================================================================+{RESET}")
        print(f"{CYAN}|{BRIGHT}   CORE AI :: RECOMMENDED HIGH-FIDELITY NEURAL VOICES                {RESET}{CYAN}|{RESET}")
        print(f"{CYAN}+=====================================================================+{RESET}")
        voices = [
            ("killian", "de-DE-KillianNeural", "Männlich (Dynamisch, modern, reaktiv - Empfohlen)"),
            ("florian", "de-DE-FlorianMultilingualNeural", "Männlich (Natürlich, multilingual)"),
            ("seraphina", "de-DE-SeraphinaMultilingualNeural", "Weiblich (Modern, warm, ultra-realistisch)"),
            ("conrad", "de-DE-ConradNeural", "Männlich (Tief, ruhig, autoritär - Jarvis-Stil)"),
            ("katja", "de-DE-KatjaNeural", "Weiblich (Klar, professionell)"),
            ("amala", "de-DE-AmalaNeural", "Weiblich (Jugendlich, frisch)"),
            ("christopher", "en-US-ChristopherNeural", "Englisch Männlich (Tech Lead)"),
            ("aria", "en-US-AriaNeural", "Englisch Weiblich (Expressive)")
        ]
        for alias, full, desc in voices:
            print(f"  {BRIGHT}{alias:<14}{RESET} -> {full:<36} | {desc}")
        print(f"\nVerwende: core config voice <alias> (z.B. core config voice killian)")
        print(f"Geschwindigkeit: core config speed <rate> (z.B. core config speed +20%)\n")

    def set_env_key(self, key: str, value: str):
        """Updates or sets an environment key in config/.env."""
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
        env_path = os.path.join(root, "config", ".env")
        lines = []
        found = False
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith(f"{key}=") or line.startswith(f"export {key}="):
                        lines.append(f"{key}={value}\n")
                        found = True
                    else:
                        lines.append(line)
        if not found:
            lines.append(f"{key}={value}\n")
        os.makedirs(os.path.dirname(env_path), exist_ok=True)
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(lines)


def main():
    cli = SettingsCLI()
    args = sys.argv[1:]

    if not args or args[0] in ["status", "overview", "show", "info"]:
        cli.print_settings_overview()
    elif args[0] in ["edit"]:
        target = args[1] if len(args) > 1 else "config"
        cli.edit_file(target)
    elif args[0] in ["audio", "mics", "speakers"]:
        cli.list_audio_devices()
    elif args[0] in ["mic"]:
        if len(args) == 1 or args[1] in ["list", "show", "devices"]:
            cli.list_audio_devices()
        elif args[1] in ["test"]:
            cli.test_mic()
        elif args[1] in ["off", "pause", "mute", "disable", "deactivate", "stop"]:
            cli.set_listening(enabled=False)
        elif args[1] in ["on", "resume", "unmute", "enable", "activate", "start"]:
            cli.set_listening(enabled=True)
        elif args[1] in ["toggle"]:
            cli.set_listening(action="toggle")
        elif args[1] in ["status", "state"]:
            cli.get_listening_status()
        elif args[1] in ["set"] and len(args) >= 3:
            cli.set_mic(" ".join(args[2:]))
        elif len(args) >= 2:
            cli.set_mic(" ".join(args[1:]))
    elif args[0] in ["mute"]:
        cli.set_listening(enabled=False)
    elif args[0] in ["unmute"]:
        cli.set_listening(enabled=True)
    elif args[0] in ["listen", "listening"]:
        if len(args) >= 2 and args[1] in ["off", "pause", "mute", "disable", "deactivate", "stop"]:
            cli.set_listening(enabled=False)
        elif len(args) >= 2 and args[1] in ["on", "resume", "unmute", "enable", "activate", "start"]:
            cli.set_listening(enabled=True)
        elif len(args) >= 2 and args[1] in ["toggle"]:
            cli.set_listening(action="toggle")
        else:
            cli.get_listening_status()
    elif args[0] in ["speaker"]:
        if len(args) == 1 or args[1] in ["list", "show"]:
            cli.list_audio_devices()
        elif args[1] in ["set"] and len(args) >= 3:
            cli.set_speaker(" ".join(args[2:]))
        elif len(args) >= 2:
            cli.set_speaker(" ".join(args[1:]))
    elif args[0] in ["voice", "voices"]:
        if len(args) >= 2:
            cli.set_voice(args[1])
        else:
            cli.list_voices()
    elif args[0] in ["speed", "rate"]:
        if len(args) >= 2:
            cli.set_rate(args[1])
        else:
            print("Usage: core config speed <+15%|+20%|+25%>")
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
