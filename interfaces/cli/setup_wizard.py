import os
import sys

# Ensure root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.state import StateManager
from core.schemas import UserProfile
from brain.model_router import ModelRouter

def run_setup():
    print("\n" + "=" * 65)
    print("  CORE AI :: SOVEREIGN LIFE OS - FIRST-RUN SETUP WIZARD")
    print("=" * 65)
    print("Zero corporate telemetry. 100% self-hosted and private.")
    print("This wizard configures your local instance with zero hardcoded defaults.\n")

    state = StateManager()
    router = ModelRouter(state_manager=state)

    # 1. Primary Operator Identity
    current_profile = state.get_user_profile()
    current_name = current_profile.preferred_name if current_profile.preferred_name != "User" else "Operator"

    name = input(f"[*] What name or handle should Core AI call you? [{current_name}]: ").strip()
    if not name:
        name = current_name

    aliases_raw = input("[*] Any nicknames or aliases? (comma-separated, optional): ").strip()
    aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()] if aliases_raw else current_profile.aliases

    # 2. Initial Primary Zone (Zero Hardcoding)
    initial_zone = input("[*] What is your primary initial space? (e.g. studio, sanctuary, workshop, office) [workspace]: ").strip()
    if not initial_zone:
        initial_zone = "workspace"

    # 3. Tone Preference
    print("\nPreferred communication style:")
    print("  1) Friendly & Concise (Default)")
    print("  2) Tactical & Direct (Jarvis-style)")
    print("  3) Casual & Relaxed")
    tone_choice = input("Select [1-3]: ").strip()
    tones = {"1": "friendly_concise", "2": "tactical_direct", "3": "casual_relaxed"}
    selected_tone = tones.get(tone_choice, "friendly_concise")

    # 4. Primary AI Provider & Model Customization
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

    # 5. Intercontinental Mesh Role
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
    state.save_user_profile(profile)
    state.ensure_zone_exists(initial_zone, display_name=initial_zone.title())

    print("\n" + "-" * 65)
    print(f"[OK] Identity Configured:     {name} (Aliases: {', '.join(aliases) if aliases else 'None'})")
    print(f"[OK] Primary Zone:            '{initial_zone}'")
    print(f"[OK] Communication Tone:      '{selected_tone}'")
    print(f"[OK] Default Planner Model:   '{models_pref['planner']}'")
    print(f"[OK] Intercontinental Mesh:   Role='{node_role}' | Server='{main_server_url}'")
    print("-" * 65)
    print("\nSetup complete! You can start Core AI with:")
    print("   python main.py")
    print("And open your browser at http://localhost:8000/roadmap\n")

if __name__ == "__main__":
    run_setup()
