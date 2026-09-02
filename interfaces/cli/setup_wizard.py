import os
import sys

# Ensure root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.state import StateManager
from core.schemas import UserProfile

def run_setup():
    print("\n" + "=" * 60)
    print("  🌐 Core AI Sovereign Life OS — First-Run Setup Wizard")
    print("=" * 60)
    print("Zero corporate telemetry. 100% self-hosted and private.")
    print("This wizard configures your local instance with zero hardcoded defaults.\n")

    state = StateManager()

    # 1. Primary Operator Identity
    current_profile = state.get_user_profile()
    current_name = current_profile.preferred_name if current_profile.preferred_name != "User" else "Operator"

    name = input(f"[*] What name or handle should Core AI call you? [{current_name}]: ").strip()
    if not name:
        name = current_name

    aliases_raw = input("[*] Any nicknames or aliases? (comma-separated, optional): ").strip()
    aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()] if aliases_raw else current_profile.aliases

    # 2. Initial Primary Zone
    initial_zone = input("[*] What is your primary initial space? (e.g. studio, office, workshop) [workspace]: ").strip()
    if not initial_zone:
        initial_zone = "workspace"

    # 3. Tone preference
    print("\nPreferred communication style:")
    print("  1) Friendly & Concise (Default)")
    print("  2) Tactical & Direct (Jarvis-style)")
    print("  3) Casual & Relaxed")
    tone_choice = input("Select [1-3]: ").strip()
    tones = {"1": "friendly_concise", "2": "tactical_direct", "3": "casual_relaxed"}
    selected_tone = tones.get(tone_choice, "friendly_concise")

    # Save to local database
    profile = UserProfile(
        user_id="primary_user",
        preferred_name=name,
        aliases=aliases,
        preferred_tone=selected_tone
    )
    state.save_user_profile(profile)
    state.ensure_zone_exists(initial_zone, display_name=initial_zone.title())

    print("\n" + "-" * 60)
    print(f"[OK] Identity Configured: {name} (Aliases: {', '.join(aliases) if aliases else 'None'})")
    print(f"[OK] Primary Zone Provisioned: '{initial_zone}'")
    print(f"[OK] Communication Style: '{selected_tone}'")
    print("-" * 60)
    print("\nSetup complete! You can now start Core AI with:")
    print("   python main.py")
    print("And open your browser at http://localhost:8000/roadmap\n")

if __name__ == "__main__":
    run_setup()
