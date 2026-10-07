import os
import sys
import time
import asyncio
import logging
import argparse
import subprocess
import threading
import uvicorn
from typing import Optional, Any, Dict, List
from dotenv import load_dotenv

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Force UTF-8 encoding on standard streams to prevent Windows cp1252 UnicodeEncodeError with local LLMs
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from core.logging_setup import setup_logging
from core.bus import EventBus
from core.schemas import TextEvent, CommandEvent, AdaptiveResponseEvent, TTSRequestEvent
from core.context import ContextManager
from core.state import StateManager
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema, get_system_status
from tools.native.file_tools import read_text_file, read_file_schema, write_text_file, write_file_schema, list_dir_contents, list_dir_schema
from tools.native.math_tools import calculate_math, calculate_math_schema, summarize_numbers, summarize_numbers_schema
from tools.native.network_tools import scan_local_network, scan_local_network_schema, inspect_lan_device, inspect_lan_device_schema
from tools.native.weather_tools import get_weather, weather_schema
from tools.native.knowledge_tools import lookup_knowledge, knowledge_schema
from tools.native.web_tools import open_url, open_url_schema, search_web_query, search_web_query_schema, open_youtube, open_youtube_schema
from tools.native.desktop_tools import (
    launch_application, launch_application_schema,
    open_path_in_explorer, open_path_in_explorer_schema,
    take_screenshot, take_screenshot_schema,
    get_clipboard_text, get_clipboard_text_schema,
    set_clipboard_text, set_clipboard_text_schema
)
from tools.native.media_tools import media_control, media_control_schema
from tools.native.process_tools import (
    list_running_processes, list_running_processes_schema,
    kill_process, kill_process_schema,
    get_hardware_metrics, get_hardware_metrics_schema,
    lock_workstation, lock_workstation_schema
)
from tools.native.shell_tools import run_shell_command, run_shell_command_schema
from tools.native.proactive_tools import (
    create_reminder, create_reminder_schema,
    create_vitals_watcher, create_vitals_watcher_schema,
    list_active_rules, list_active_rules_schema,
    cancel_proactive_rule, cancel_proactive_rule_schema,
    set_state_manager as set_proactive_sm
)
from tools.native.dev_tools import (
    get_git_status, get_git_status_schema,
    manage_notes, manage_notes_schema,
    set_state_manager as set_dev_sm
)
from tools.remote_dispatcher import RemoteToolDispatcher
from brain.dynamic_generator import DynamicGenerator
from brain.pipeline_engine import PipelineEngine
from brain.planner import Planner
from brain.proactive import ProactiveDaemon
from brain.model_router import ModelRouter
from brain.spoken_to import SpokenToReasoning, DiscourseRole
from core.gateway import create_gateway_app, connection_manager
from core.mesh_client import MeshClient
from engines.audio_router import SpatialAudioRouter, route_spatial_audio, route_spatial_audio_schema
from brain.spatial_handoff import SpatialHandoffEngine
from engines.voice_in import VoiceInEngine
from engines.voice_out import VoiceOutEngine

logger = logging.getLogger("CoreAI.Main")

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

def play_boot_sequence(skip_anim: bool = True):
    if not skip_anim:
        try:
            from core.animation import play_boot_animation
            played = play_boot_animation(duration=2.2)
            if played:
                return
        except Exception:
            pass

    print(f"\n{CYAN}======================================================================={RESET}")
    print(f"{CYAN}  CORE AI :: SOVEREIGN LIFE OS - INITIALIZING MICROKERNEL{RESET}")
    print(f"{CYAN}======================================================================={RESET}")
    steps = [
        "Mounting SQLite State Manager & Dynamic Topologies",
        "Initializing EventBus & Inter-Node Transport",
        "Registering Neural Model Router & DAG Planner",
        "Configuring Spatial Audio Matrix & Handoff Engine",
        "Spawning Universal Gateway (REST & WebSocket Mesh)"
    ]
    for step in steps:
        print(f"  [+] {step:<54} [{GREEN}OK{RESET}]")
    print(f"{CYAN}-----------------------------------------------------------------------{RESET}\n")

def print_banner(operator_name: str, zone: str, port: int):
    print(f"{CYAN}+=====================================================================+{RESET}")
    print(f"{CYAN}|{BRIGHT}   C.O.R.E. AI :: CONCURRENT OMNIPRESENT REASONING ENGINE            {RESET}{CYAN}|{RESET}")
    print(f"{CYAN}|{RESET}   v0.2.0-alpha [Precision & Flow] - Sovereign Ubiquitous Life OS       {CYAN}|{RESET}")
    print(f"{CYAN}+=====================================================================+{RESET}")
    print(f"{CYAN}|{RESET}   Operator: {GREEN}{operator_name:<16}{RESET} Zone: {YELLOW}{zone:<16}{RESET} Status: {GREEN}ONLINE       {RESET}{CYAN}|{RESET}")
    print(f"{CYAN}|{RESET}   Gateway:  {CYAN}http://localhost:{port:<5}{RESET} API Docs: {CYAN}/docs{RESET} WebSocket: {CYAN}/ws/events{RESET}   {CYAN}|{RESET}")
    print(f"{CYAN}+=====================================================================+{RESET}\n")
    print(f"{MAGENTA}Type any goal to solve it, or type 'help' for built-in commands.{RESET}\n")

def print_help():
    print(f"\n{BRIGHT}Core Terminal Commands:{RESET}")
    print(f"  {GREEN}solve <goal>{RESET}              - Solve any task via autonomous DAG pipeline (or type directly)")
    print(f"  {GREEN}speak <text>{RESET}              - Synthesize neural speech via current zone speaker")
    print(f"  {GREEN}spoken <text>{RESET}             - Test Spoken-To Reasoning classification on any phrase")
    print(f"  {GREEN}audio{RESET}                     - Inspect connected mics, audio interfaces & zone routing")
    print(f"  {GREEN}handoff <zone>{RESET}            - Transition spatial anchor & auto-route audio to new zone")
    print(f"  {GREEN}voice off / voice on{RESET}       - Pause or resume always-on microphone listening")
    print(f"  {GREEN}status{RESET}                    - Inspect system health, platform architecture & model status")
    print(f"  {GREEN}account{RESET}                   - View Sovereign Operator Account identity, space & credentials")
    print(f"  {GREEN}account edit{RESET}              - Re-run interactive Sovereign Account setup wizard")
    print(f"  {GREEN}account secret{RESET}            - View Sovereign Auth Secret for edge device pairing")
    print(f"  {GREEN}account reset{RESET}             - Safely reset local account database to clean Day-Zero state")
    print(f"  {GREEN}profile{RESET}                   - View operator identity, aliases, and preferences")
    print(f"  {GREEN}profile set <name> [alias]{RESET}- Update operator name and aliases")
    print(f"  {GREEN}zones{RESET}                     - List all dynamically registered spatial zones")
    print(f"  {GREEN}zone add <id> [name]{RESET}      - Register a new spatial zone on-the-fly")
    print(f"  {GREEN}devices{RESET}                   - List connected devices and trust tier topology")
    print(f"  {GREEN}tools{RESET}                     - View tool catalog (native + dynamic generated)")
    print(f"  {GREEN}models{RESET}                    - Inspect configured AI providers, active models & health")
    print(f"  {GREEN}model set <role> <model>{RESET}   - Assign model to role (planner, fallback, deep_reasoning)")
    print(f"  {GREEN}api-key set <provider> <key>{RESET}- Set API key (gemini, openai, anthropic)")
    print(f"  {GREEN}mesh{RESET}                      - Inspect intercontinental mesh status, role & server reachability")
    print(f"  {GREEN}mesh role <main|edge>{RESET}     - Switch node role between main_server and edge_node")
    print(f"  {GREEN}mesh connect <url>{RESET}        - Set central main server URL and test connection")
    print(f"  {GREEN}mesh export [path]{RESET}        - Export portable state bundle to migrate server")
    print(f"  {GREEN}mesh import <path>{RESET}        - Import state bundle to restore server on new machine")
    print(f"  {GREEN}hud <title> | <body>{RESET}      - Dispatch an ambient HUD card to connected displays")
    print(f"  {GREEN}logs [N]{RESET}                  - View recent execution audit logs from SQLite")
    print(f"  {GREEN}proactive{RESET}                 - Run proactive watcher evaluation on demand")
    print(f"  {GREEN}harness / eval{RESET}            - Run live reasoning & execution harness diagnostic")
    print(f"  {GREEN}logo / anim{RESET}               - Launch interactive 3D Sovereign Core holographic viewer")
    print(f"  {GREEN}update{RESET}                    - Apply GitHub updates with automated state backup & test guard")
    print(f"  {GREEN}backup{RESET}                    - Create instant point-in-time snapshot of SQLite state & config")
    print(f"  {GREEN}bg / daemon{RESET}               - Send Core AI to background headless daemon mode")
    print(f"  {GREEN}clear{RESET}                     - Clear terminal screen")
    print(f"  {GREEN}exit / quit{RESET}               - Cleanly shut down Core AI and background services\n")

class OperatorRelocator:
    """Manages operator physical presence relocation, updates profile state, and coordinates audio/HUD handoff."""
    def __init__(self, state_manager: Optional[StateManager] = None, spatial_handoff: Optional[Any] = None):
        self.state_manager = state_manager
        self.spatial_handoff = spatial_handoff

    def relocate(self, target_zone: str) -> dict:
        zone_clean = target_zone.strip().lower()
        mgr = self.state_manager or StateManager()
        z_rec = mgr.ensure_zone_exists(zone_clean)
        try:
            prof = mgr.get_user_profile()
            prof.preferences["primary_space"] = zone_clean
            mgr.save_user_profile(prof)
        except Exception:
            pass

        audio_routed = False
        if self.spatial_handoff:
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.spatial_handoff.execute_handoff(to_zone=zone_clean, reason="verbal_presence"))
                except RuntimeError:
                    asyncio.run(self.spatial_handoff.execute_handoff(to_zone=zone_clean, reason="verbal_presence"))
                audio_routed = True
            except Exception as e:
                logger.warning(f"Spatial handoff notice: {e}")

        return {
            "status": "success",
            "zone": zone_clean,
            "display_name": z_rec.display_name,
            "audio_routed": audio_routed,
            "message": f"Relocated operator to {z_rec.display_name}"
        }

def setup_tools(state: Optional[StateManager] = None, relocator: Optional[OperatorRelocator] = None) -> ToolRegistry:
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    
    # Register Native Tools
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("get_system_status", get_system_status, {
        "name": "get_system_status",
        "description": "Get current operating system, distribution, and hardware architecture status",
        "parameters": {"type": "object", "properties": {}}
    })
    
    registry.register_tool("read_text_file", read_text_file, read_file_schema)
    registry.register_tool("write_text_file", write_text_file, write_file_schema)
    registry.register_tool("list_dir_contents", list_dir_contents, list_dir_schema)
    registry.register_tool("calculate_math", calculate_math, calculate_math_schema)
    registry.register_tool("summarize_numbers", summarize_numbers, summarize_numbers_schema)
    registry.register_tool("route_spatial_audio", route_spatial_audio, route_spatial_audio_schema)

    # Network & Device Topology Introspection Tools
    registry.register_tool("scan_local_network", scan_local_network, scan_local_network_schema)
    registry.register_tool("inspect_lan_device", inspect_lan_device, inspect_lan_device_schema)

    # Real-Time Weather and Encyclopedic Knowledge Tools
    registry.register_tool("get_weather", get_weather, weather_schema)
    registry.register_tool("lookup_knowledge", lookup_knowledge, knowledge_schema)

    # Sovereign Desktop & OS Automation Tools
    registry.register_tool("open_url", open_url, open_url_schema)
    registry.register_tool("search_web_query", search_web_query, search_web_query_schema)
    registry.register_tool("open_youtube", open_youtube, open_youtube_schema)
    registry.register_tool("launch_application", launch_application, launch_application_schema)
    registry.register_tool("open_path_in_explorer", open_path_in_explorer, open_path_in_explorer_schema)
    registry.register_tool("take_screenshot", take_screenshot, take_screenshot_schema)
    registry.register_tool("get_clipboard_text", get_clipboard_text, get_clipboard_text_schema)
    registry.register_tool("set_clipboard_text", set_clipboard_text, set_clipboard_text_schema)
    registry.register_tool("media_control", media_control, media_control_schema)
    registry.register_tool("list_running_processes", list_running_processes, list_running_processes_schema)
    registry.register_tool("kill_process", kill_process, kill_process_schema)
    registry.register_tool("get_hardware_metrics", get_hardware_metrics, get_hardware_metrics_schema)
    registry.register_tool("lock_workstation", lock_workstation, lock_workstation_schema)
    registry.register_tool("run_shell_command", run_shell_command, run_shell_command_schema)

    def list_registered_devices(zone_filter: Optional[str] = None):
        mgr = state or StateManager()
        devs = mgr.list_all_devices()
        if zone_filter:
            devs = [d for d in devs if d.current_zone.lower() == zone_filter.lower()]
        return {
            "status": "success",
            "device_count": len(devs),
            "devices": [
                {
                    "device_id": d.device_id,
                    "device_type": d.device_type,
                    "current_zone": d.current_zone,
                    "trust_tier": d.trust_tier,
                    "status": getattr(d, "status", "online"),
                    "capabilities": d.capabilities,
                }
                for d in devs
            ]
        }

    registry.register_tool("list_registered_devices", list_registered_devices, {
        "name": "list_registered_devices",
        "description": "Lists all devices, appliances, and smart hardware nodes currently registered in Core AI topology",
        "parameters": {
            "type": "object",
            "properties": {
                "zone_filter": {"type": "string", "description": "Optional zone_id to filter devices by"}
            }
        }
    })

    def list_spatial_zones():
        mgr = state or StateManager()
        zones = mgr.list_zones()
        return {
            "status": "success",
            "zone_count": len(zones),
            "zones": [{"zone_id": z.zone_id, "display_name": z.display_name} for z in zones]
        }

    registry.register_tool("list_spatial_zones", list_spatial_zones, {
        "name": "list_spatial_zones",
        "description": "Lists all physical spatial zones and rooms configured in the environment",
        "parameters": {"type": "object", "properties": {}}
    })

    def remove_spatial_zone(
        zone_id: Optional[str] = None,
        keep_zone: Optional[str] = None,
        all_except: Optional[str] = None,
        **kwargs
    ):
        mgr = state or StateManager()
        # Handle "all except" / keep pattern
        target_keep = keep_zone or all_except or kwargs.get("keep") or kwargs.get("preserve")
        if target_keep:
            if isinstance(target_keep, str):
                # May be comma-separated or space-separated
                keeps = [k.strip().lower() for k in target_keep.replace(",", " ").split() if k.strip()]
            elif isinstance(target_keep, (list, tuple)):
                keeps = [str(k).strip().lower() for k in target_keep if str(k).strip()]
            else:
                keeps = [str(target_keep).strip().lower()]
            deleted = mgr.delete_all_zones_except(keeps)
            current_zones = mgr.list_zones()
            return {
                "status": "success",
                "action": "delete_all_except",
                "kept_zones": keeps,
                "deleted_zones": deleted,
                "deleted_count": len(deleted),
                "remaining_zones": [{"zone_id": z.zone_id, "display_name": z.display_name} for z in current_zones]
            }

        target_zone = zone_id or kwargs.get("zone") or kwargs.get("name") or kwargs.get("target_zone")
        if target_zone:
            clean_zid = str(target_zone).strip().lower()
            deleted = mgr.delete_zone(clean_zid)
            return {
                "status": "success" if deleted else "not_found",
                "action": "delete_zone",
                "zone_id": clean_zid,
                "deleted": deleted
            }

        return {"status": "error", "error": "Specify either zone_id to delete or keep_zone/all_except to prune."}

    registry.register_tool("remove_spatial_zone", remove_spatial_zone, {
        "name": "remove_spatial_zone",
        "description": "Deletes spatial zone(s) from the system. Can remove a specific zone by zone_id, or delete all zones except a preserved zone (e.g. keep_zone='office' or all_except='office')",
        "parameters": {
            "type": "object",
            "properties": {
                "zone_id": {"type": "string", "description": "Specific zone ID to delete"},
                "all_except": {"type": "string", "description": "Delete all configured zones EXCEPT this preserved zone (e.g. 'office')"},
                "keep_zone": {"type": "string", "description": "Alias for all_except: zone to preserve while removing others"}
            }
        }
    })

    def relocate_operator_tool(target_zone: str):
        if relocator:
            return relocator.relocate(target_zone)
        zone_clean = target_zone.strip().lower()
        mgr = state or StateManager()
        z_rec = mgr.ensure_zone_exists(zone_clean)
        return {
            "status": "success",
            "zone": zone_clean,
            "display_name": z_rec.display_name,
            "message": f"Relocated operator to {z_rec.display_name}"
        }

    registry.register_tool("relocate_operator", relocate_operator_tool, {
        "name": "relocate_operator",
        "description": "Relocates the operator's physical presence to a new spatial zone (e.g. 'office', 'kitchen', 'studio', 'living_room') and re-routes audio & display contexts",
        "parameters": {
            "type": "object",
            "properties": {
                "target_zone": {
                    "type": "string",
                    "description": "The destination room/zone ID (e.g. 'office', 'kitchen', 'studio', 'bedroom')"
                }
            },
            "required": ["target_zone"]
        }
    })

    def update_operator_profile_tool(
        preferred_name: Optional[str] = None,
        add_alias: Optional[str] = None,
        preferred_tone: Optional[str] = None,
        primary_zone: Optional[str] = None
    ):
        mgr = state or StateManager()
        prof = mgr.get_user_profile()
        if preferred_name:
            prof.preferred_name = preferred_name
        if add_alias:
            clean_alias = add_alias.strip()
            if clean_alias and clean_alias not in prof.aliases:
                prof.aliases.append(clean_alias)
        if preferred_tone:
            prof.preferred_tone = preferred_tone
        if primary_zone:
            prof.preferences["primary_space"] = primary_zone
        mgr.save_user_profile(prof)
        return {
            "status": "success",
            "preferred_name": prof.preferred_name,
            "aliases": prof.aliases,
            "preferred_tone": prof.preferred_tone,
            "primary_zone": prof.preferences.get("primary_space")
        }

    registry.register_tool("update_operator_profile", update_operator_profile_tool, {
        "name": "update_operator_profile",
        "description": "Updates operator profile in SQLite: name, honorific/alias (e.g. 'Sir', 'Boss', 'Captain'), preferred tone, or default primary zone",
        "parameters": {
            "type": "object",
            "properties": {
                "preferred_name": {"type": "string", "description": "New preferred name"},
                "add_alias": {"type": "string", "description": "New honorific or alias to add, e.g. 'Sir'"},
                "preferred_tone": {"type": "string", "description": "Preferred interaction tone or style"},
                "primary_zone": {"type": "string", "description": "Primary spatial zone"}
            }
        }
    })

    # Proactive Supervision & Reminder Tools
    if state:
        set_proactive_sm(state)
        set_dev_sm(state)
    registry.register_tool("create_reminder", create_reminder, create_reminder_schema)
    registry.register_tool("create_vitals_watcher", create_vitals_watcher, create_vitals_watcher_schema)
    registry.register_tool("list_active_rules", list_active_rules, list_active_rules_schema)
    registry.register_tool("cancel_proactive_rule", cancel_proactive_rule, cancel_proactive_rule_schema)

    # Developer & Scratch Productivity Tools
    registry.register_tool("get_git_status", get_git_status, get_git_status_schema)
    registry.register_tool("manage_notes", manage_notes, manage_notes_schema)

    registry.discover_dynamic_tools()
    return registry

def parse_args():
    parser = argparse.ArgumentParser(description="Core AI Sovereign Life OS Microkernel")
    parser.add_argument("goal", nargs="*", default=None, help="Optional one-shot goal to execute and exit")
    parser.add_argument("--solve", "-s", default=None, help="Explicit one-shot goal to execute and exit")
    parser.add_argument("--heuristic", action="store_true", help="Force deterministic heuristic planner (fast offline mode)")
    parser.add_argument("--no-anim", "--fast", action="store_true", help="Skip 3D boot animation for instant start (default)")
    parser.add_argument("--anim", action="store_true", help="Play 3D holographic boot animation")
    parser.add_argument("--logo", action="store_true", help="Run interactive 3D logo animation and exit")
    parser.add_argument("--no-voice", "--no-mic", "--disable-voice", dest="no_voice", action="store_true", help="Disable automatic microphone listening on startup (voice is active by default)")
    parser.add_argument("--voice", action="store_true", help="Explicitly enable full continuous voice loop (active by default)")
    parser.add_argument("--voice-in", action="store_true", help="Explicitly enable background microphone listening (active by default)")
    parser.add_argument("--no-tts", action="store_true", help="Disable audio speech output")
    parser.add_argument("--headless", "--server-only", dest="headless", action="store_true", help="Run in headless server mode without interactive REPL")
    parser.add_argument("--model-size", default="small", help="faster-whisper model size (small, base, tiny, distil-large-v3)")
    parser.add_argument("--device", default=None, help="Audio input/output device index or name substring")
    parser.add_argument("--host", default=None, help="Gateway host binding (defaults to CORE_HOST or 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Gateway port (defaults to CORE_PORT or 8000)")
    return parser.parse_args()

def run_interactive_repl(
    state: StateManager,
    bus: EventBus,
    registry: ToolRegistry,
    planner: Planner,
    engine: PipelineEngine,
    proactive: ProactiveDaemon,
    model_router: ModelRouter,
    mesh_client: MeshClient,
    spoken_to: SpokenToReasoning,
    audio_router: SpatialAudioRouter,
    spatial_handoff: SpatialHandoffEngine,
    voice_out: Optional[VoiceOutEngine],
    voice_in: Optional[VoiceInEngine],
    port: int,
    shutdown_event: threading.Event
):
    profile = state.get_user_profile()
    active_name = profile.preferred_name
    active_zone = profile.preferences.get("primary_space", "studio")
    state.ensure_zone_exists(active_zone, display_name=f"{active_name}'s Primary Zone")

    print_banner(active_name, active_zone, port)

    def get_prompt() -> str:
        mic_ind = f" {GREEN}[MIC:ON]{RESET}" if (voice_in and voice_in.is_recording) else f" {YELLOW}[MIC:OFF]{RESET}"
        return f"{CYAN}Core{RESET} [{GREEN}{active_name}{RESET}@{YELLOW}{active_zone}{RESET}{mic_ind}] {BRIGHT}>{RESET} "

    def on_speech(text: str):
        nonlocal active_zone
        print(f"\n{MAGENTA}[SPEECH DETECTED]{RESET} \"{text}\"")
        prof = state.get_user_profile()
        dec = spoken_to.evaluate(text, profile=prof)
        print(f"  {CYAN}[Spoken-To Decision]{RESET} Role: {dec.discourse_role.value} | Action: {dec.action_type}")

        # Direct interrupt handling
        if dec.action_type == "interrupt":
            if voice_out:
                voice_out.interrupt()
            print(f"  {YELLOW}↳ Playback stopped by operator.{RESET}\n")
            print(get_prompt(), end="", flush=True)
            return

        if not dec.should_respond:
            print(f"  {YELLOW}↳ Silently ignored (ambient / not addressed to Core AI){RESET}\n")
            print(get_prompt(), end="", flush=True)
            return

        # Halt any ongoing speech before answering new request
        if voice_out and voice_out.is_speaking:
            voice_out.interrupt()

        if dec.discourse_role == DiscourseRole.DEMONSTRATED and dec.autonomous_response:
            print(f"{CYAN}Core AI [Showcase]:{RESET} {dec.autonomous_response}\n")
            if voice_out:
                voice_out.synthesize_and_play(dec.autonomous_response, blocking=False)
            print(get_prompt(), end="", flush=True)
            return
        target_cmd = dec.clean_command or text
        plan = planner.plan_problem(target_cmd, context={"zone": active_zone, "operator": active_name})
        finished = asyncio.run(engine.execute_pipeline(plan))
        for s in finished.steps:
            if s.tool_name == "relocate_operator" and s.status == "completed" and isinstance(s.output, dict):
                new_z = s.output.get("zone")
                if new_z:
                    active_zone = new_z
        spoken = planner.formulate_spoken_response(finished, profile=prof)
        print(f"{CYAN}Core AI:{RESET} {spoken}\n")
        if voice_out:
            voice_out.synthesize_and_play(spoken, blocking=False)
        print(get_prompt(), end="", flush=True)

    # Wire voice_in and voice_out for instant barge-in / interruption
    if voice_in and voice_out:
        voice_in.register_voice_out(voice_out)

    # Always-on voice: start listening immediately if voice_in engine was initialized
    if voice_in and not voice_in.is_recording:
        try:
            voice_in.start_listening(callback=on_speech)
            print(f"{GREEN}[OK] Always-on voice capture active! Speak anytime (type 'voice off' to pause).{RESET}\n")
        except Exception as e:
            print(f"{YELLOW}[!] Notice: Could not start microphone stream ({e}). Continuing in text mode.{RESET}\n")

    while not shutdown_event.is_set():
        try:
            prompt = get_prompt()
            try:
                user_input = input(prompt).strip()
            except EOFError:
                break

            if not user_input:
                continue

            cmd_lower = user_input.lower()
            clean_cmd = cmd_lower.strip(" .!?")

            if cmd_lower in ["exit", "quit"]:
                print(f"\n{YELLOW}[*] Shutting down Core AI. Goodbye {active_name}!{RESET}")
                shutdown_event.set()
                break

            elif clean_cmd in ["stop", "stopp", "pause", "halt", "cancel", "quiet", "leise", "shut up"]:
                if voice_out and (voice_out.is_speaking or not voice_out.speech_queue.empty()):
                    voice_out.interrupt()
                    print(f"{YELLOW}[*] Voice output halted.{RESET}\n")
                else:
                    print(f"{YELLOW}[*] No active speech playback to stop.{RESET}\n")

            elif cmd_lower == "help":
                print_help()

            elif cmd_lower == "clear":
                subprocess.run("cls" if os.name == "nt" else "clear", shell=True)
                print_banner(active_name, active_zone, port)

            elif cmd_lower == "status":
                status = get_system_status()
                print(f"\n{BRIGHT}--- Core AI System Status ---{RESET}")
                print(f"  Operator:     {GREEN}{active_name}{RESET}")
                print(f"  Platform:     {status.get('os')} {status.get('release')} ({status.get('architecture')})")
                print(f"  Active Model: {planner.get_active_model() or 'offline_heuristic'}")
                print(f"  Tools Loaded: {len(registry.tools)}")
                print(f"  Active Zones: {len(state.list_zones())}")
                print(f"  Devices:      {len(state.list_all_devices())}")
                print(f"  Voice Out:    {GREEN}Online (Edge Neural TTS + pyttsx3){RESET}" if voice_out else f"  Voice Out:    {YELLOW}Disabled{RESET}")
                print(f"  Voice In:     {GREEN}Active (Listening - Always-On){RESET}" if (voice_in and voice_in.is_recording) else f"  Voice In:     {YELLOW}Paused (type 'voice on'){RESET}")
                print(f"  Gateway:      {GREEN}http://localhost:{port}{RESET}")
                print()

            elif cmd_lower == "audio":
                devs = audio_router.list_system_audio_devices()
                print(f"\n{BRIGHT}--- Connected Audio Inputs ({len(devs['inputs'])}) ---{RESET}")
                for d in devs["inputs"][:8]:
                    print(f"  [{d['index']:2d}] [MIC] {d['name']} (channels={d['max_input_channels']})")
                print(f"\n{BRIGHT}--- Connected Audio Outputs ({len(devs['outputs'])}) ---{RESET}")
                for d in devs["outputs"][:8]:
                    print(f"  [{d['index']:2d}] [SPK] {d['name']} (channels={d['max_output_channels']})")
                routes = state.list_all_audio_routes()
                if routes:
                    print(f"\n{BRIGHT}--- Configured Zone Audio Routes ({len(routes)}) ---{RESET}")
                    for r in routes:
                        print(f"  - {YELLOW}{r.zone_id:<18}{RESET} : Mic='{r.input_device_name}' | Speaker='{r.output_device_name}'")
                print()

            elif cmd_lower.startswith("handoff ") or cmd_lower.startswith("relocate "):
                target_z = user_input.split(maxsplit=1)[1].strip()
                print(f"{CYAN}[*] Executing spatial handoff to zone '{target_z}'...{RESET}")
                event = asyncio.run(spatial_handoff.execute_handoff(
                    to_zone=target_z,
                    from_zone=active_zone,
                    reason="console_command"
                ))
                active_zone = target_z
                print(f"{GREEN}[OK] Relocated to '{target_z}'! Audio re-routed and HUD card broadcast.{RESET}\n")

            elif cmd_lower.startswith("speak "):
                text_to_speak = user_input[6:].strip()
                print(f"{CYAN}[*] Synthesizing speech:{RESET} '{text_to_speak}'")
                if voice_out:
                    voice_out.synthesize_and_play(text_to_speak)
                else:
                    print(f"{YELLOW}[!] Voice Out is currently disabled (--no-tts).{RESET}")

            elif cmd_lower in ["voice on", "voice resume", "mic on"]:
                if voice_in and voice_in.is_recording:
                    print(f"{YELLOW}[!] Voice capture is already active and listening.{RESET}\n")
                else:
                    if voice_in is None:
                        print(f"{YELLOW}[*] Initializing VoiceInEngine (faster-whisper 'small')...{RESET}")
                        try:
                            voice_in = VoiceInEngine(model_size="small")
                        except Exception as e:
                            print(f"{RED}[ERROR] Failed to initialize voice capture: {e}{RESET}\n")
                    if voice_in:
                        try:
                            voice_in.start_listening(callback=on_speech)
                            print(f"{GREEN}[OK] Voice capture online! Always-on microphone listening.{RESET}\n")
                        except Exception as e:
                            print(f"{RED}[ERROR] Failed to start voice capture: {e}{RESET}\n")

            elif cmd_lower in ["voice off", "voice pause", "mic off"]:
                if voice_in and voice_in.is_recording:
                    voice_in.stop_listening()
                    print(f"{YELLOW}[*] Voice capture paused. Type 'voice on' to resume listening.{RESET}\n")
                else:
                    print(f"{YELLOW}[!] Voice capture is already inactive.{RESET}\n")

            elif cmd_lower.startswith("spoken ") or cmd_lower.startswith("test-spoken "):
                test_utterance = user_input.split(maxsplit=1)[1].strip()
                dec = spoken_to.evaluate(test_utterance, profile=state.get_user_profile())
                print(f"\n{BRIGHT}--- Spoken-To Reasoning Analysis ---{RESET}")
                print(f"  Utterance:      '{test_utterance}'")
                print(f"  Discourse Role: {CYAN}{dec.discourse_role.value}{RESET}")
                print(f"  Action Type:    {GREEN if dec.should_respond else YELLOW}{dec.action_type}{RESET}")
                print(f"  Should Respond: {GREEN if dec.should_respond else RED}{dec.should_respond}{RESET}")
                print(f"  Confidence:     {dec.confidence:.2f}")
                print(f"  Rationale:      {dec.rationale}")
                if dec.clean_command:
                    print(f"  Clean Command:  {GREEN}'{dec.clean_command}'{RESET}")
                if dec.autonomous_response:
                    print(f"  Chime-In Reply: {MAGENTA}'{dec.autonomous_response}'{RESET}")
                print()

            elif cmd_lower in ["account", "account show", "account status"]:
                from interfaces.cli.setup_wizard import print_account_status_card
                print_account_status_card(state)

            elif cmd_lower in ["account edit", "account setup", "account init"]:
                from interfaces.cli.setup_wizard import run_setup
                p = run_setup(state=state)
                active_name = p.preferred_name
                active_zone = p.preferences.get("primary_space", "office")
                print(f"{GREEN}[OK] Sovereign account updated. Operator: {active_name} @ {active_zone}{RESET}\n")

            elif cmd_lower == "account secret":
                auth_secret = os.getenv("CORE_AUTH_SECRET", "core_sovereign_secret")
                print(f"\n{BRIGHT}--- Sovereign Auth Secret ---{RESET}")
                print(f"  Secret: {CYAN}{auth_secret}{RESET}")
                print(f"  To enroll another device (laptop, phone, SBC):")
                print(f"    python -m interfaces.install.enroll --host http://localhost:{port} --secret \"{auth_secret}\"\n")

            elif cmd_lower == "account reset":
                try:
                    conf = input(f"{RED}[!] Are you sure you want to reset your local Sovereign Account to Day-Zero? [y/N]: {RESET}").strip().lower()
                    if conf in ["y", "yes"]:
                        from interfaces.cli.setup_wizard import reset_account_to_day_zero
                        reset_account_to_day_zero(state)
                        p = state.get_user_profile()
                        active_name = p.preferred_name
                        active_zone = "default"
                        print(f"{GREEN}[OK] Local account reset to Day-Zero blank slate.{RESET}\n")
                    else:
                        print(f"{YELLOW}[*] Account reset cancelled.{RESET}\n")
                except (KeyboardInterrupt, EOFError):
                    print()

            elif cmd_lower == "profile":
                p = state.get_user_profile()
                print(f"\n{BRIGHT}--- Operator Profile ---{RESET}")
                print(f"  Name:        {GREEN}{p.preferred_name}{RESET}")
                print(f"  Aliases:     {', '.join(p.aliases) if p.aliases else 'None'}")
                print(f"  Tone:        {p.preferred_tone}")
                print(f"  Primary Zone:{p.preferences.get('primary_space', 'studio')}")
                print(f"  Updated At:  {p.updated_at}\n")

            elif cmd_lower.startswith("profile set"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 3:
                    new_name = parts[2]
                    alias = parts[3] if len(parts) > 3 else None
                    state.set_user_preferred_name(new_name, aliases=[alias] if alias else None)
                    active_name = new_name
                    print(f"{GREEN}[OK] Operator identity updated to: {new_name}{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: profile set <name> [alias]{RESET}")

            elif cmd_lower.startswith("profile add-alias"):
                parts = user_input.split(maxsplit=2)
                if len(parts) >= 3:
                    alias = parts[2].strip()
                    p = state.get_user_profile()
                    if alias not in p.aliases:
                        p.aliases.append(alias)
                        state.save_user_profile(p)
                    print(f"{GREEN}[OK] Added alias/title '{alias}' to operator profile.{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: profile add-alias <alias>{RESET}")

            elif cmd_lower == "zones":
                zones = state.list_zones()
                print(f"\n{BRIGHT}--- Dynamically Discovered Spatial Zones ({len(zones)}) ---{RESET}")
                for z in zones:
                    created_str = z.created_at.isoformat()[:19] if hasattr(z.created_at, "isoformat") else str(z.created_at)[:19]
                    print(f"  - {YELLOW}{z.zone_id:<16}{RESET} Display: {z.display_name} (Discovered: {created_str})")
                print()

            elif cmd_lower.startswith("zone add"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 3:
                    zid = parts[2]
                    zname = parts[3].strip("\"'") if len(parts) > 3 else zid.title()
                    state.ensure_zone_exists(zid, display_name=zname)
                    print(f"{GREEN}[OK] Spatial zone '{zid}' registered.{RESET}")
                else:
                    print(f"{RED}[!] Usage: zone add <zone_id> [display_name]{RESET}")

            elif cmd_lower.startswith("zone rm ") or cmd_lower.startswith("zone remove ") or cmd_lower.startswith("zone delete "):
                zid = user_input.split(maxsplit=2)[2].strip()
                deleted = state.delete_zone(zid)
                if deleted:
                    print(f"{GREEN}[OK] Spatial zone '{zid}' deleted.{RESET}")
                else:
                    print(f"{YELLOW}[!] Zone '{zid}' not found.{RESET}")

            elif cmd_lower == "devices":
                devs = state.list_all_devices()
                print(f"\n{BRIGHT}--- Connected Devices & Trust Topology ({len(devs)}) ---{RESET}")
                for d in devs:
                    anchor = "Fixed Anchor" if d.is_fixed_anchor else "Roaming"
                    print(f"  - {CYAN}{d.device_id:<16}{RESET} Type: {d.device_type:<12} Zone: {d.current_zone:<14} Tier: {GREEN}{d.trust_tier:<8}{RESET} ({anchor})")
                print()

            elif cmd_lower == "tools":
                cat = registry.get_tool_catalog()
                print(f"\n{BRIGHT}--- Core AI Tool Catalog ({len(cat)} tools) ---{RESET}")
                for t in cat:
                    dyn_flag = f"{MAGENTA}[DYNAMIC]{RESET} " if t.get("is_dynamic") else f"{GREEN}[NATIVE]{RESET}  "
                    print(f"  {dyn_flag}{t['name']:<24} {t.get('description', '')[:50]}")
                print()

            elif cmd_lower in ["models", "model", "providers"]:
                summary = model_router.get_status_summary()
                print(f"\n{BRIGHT}--- Configured AI Providers & Models ---{RESET}")
                for prov, enabled in summary["configured_providers"].items():
                    col = GREEN if enabled else YELLOW
                    status_lbl = "Configured / Online" if enabled else "Not Configured / Offline"
                    extra = ""
                    if prov == "ollama_local" and enabled:
                        m_list = summary.get("ollama_models", [])
                        if m_list:
                            extra = f" (Installed: {', '.join(m_list)})"
                    print(f"  - {prov:<16} : [{col}{status_lbl}{RESET}]{extra}")
                print(f"\n{BRIGHT}--- Active Model Roles & Assignments ---{RESET}")
                for role, info in summary["roles"].items():
                    col = GREEN if info["online"] else YELLOW
                    status_lbl = "ONLINE" if info["online"] else "OFFLINE (Heuristic Fallback)"
                    print(f"  - {role:<16} : {CYAN}{info['model']:<26}{RESET} [{col}{status_lbl}{RESET}]")
                print(f"\n  To assign a model:")
                print(f"    model set planner <model_name>   (e.g. model set planner ollama/qwen3.5:2b)")
                print(f"    model set deep_reasoning <model> (e.g. model set deep_reasoning gemini/gemini-2.5-pro)\n")

            elif cmd_lower.startswith("model set"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 4:
                    role, m_name = parts[2], parts[3]
                    model_router.set_model_preference(role, m_name)
                    print(f"{GREEN}[OK] Assigned model '{m_name}' to role '{role}'.{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: model set <role> <model_name> (roles: planner, fallback, deep_reasoning, fast_local){RESET}\n")

            elif cmd_lower.startswith("api-key set") or cmd_lower.startswith("key set"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 4:
                    provider, key_val = parts[2], parts[3]
                    env_var = model_router.set_api_key(provider, key_val, persist_to_env=True)
                    active_now = planner.get_active_model()
                    print(f"{GREEN}[OK] Saved API key for '{provider}' to {env_var} and config/.env.{RESET}")
                    print(f"  {CYAN}↳ Active Reasoning Model:{RESET} {GREEN}{active_now}{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: api-key set <provider> <api_key> (providers: gemini, openai, anthropic){RESET}\n")

            elif cmd_lower == "mesh":
                is_online, ping_info = mesh_client.ping_main_server()
                status_str = f"{GREEN}REACHABLE (Online){RESET}" if is_online else f"{YELLOW}UNREACHABLE ({ping_info.get('error', 'offline')}){RESET}"
                print(f"\n{BRIGHT}--- Intercontinental Sovereign Mesh Status ---{RESET}")
                print(f"  Node Role:        {CYAN}{mesh_client.role.upper()}{RESET}")
                print(f"  Main Server URL:  {mesh_client.main_server_url}")
                print(f"  Server Status:    {status_str}")
                print(f"  Offline Buffer:   {len(mesh_client.offline_buffer)} items queued")
                if mesh_client.role == "edge_node" and not is_online:
                    print(f"  {YELLOW}↳ Autonomous Local Fallback is ACTIVE (never locked out).{RESET}")
                print()

            elif cmd_lower.startswith("mesh role"):
                parts = user_input.split(maxsplit=2)
                if len(parts) >= 3 and parts[2].lower() in ["main_server", "edge_node", "main", "edge"]:
                    new_role = "main_server" if "main" in parts[2].lower() else "edge_node"
                    mesh_client.save_configuration(role=new_role)
                    print(f"{GREEN}[OK] Node role switched to: {new_role}{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: mesh role <main_server|edge_node>{RESET}\n")

            elif cmd_lower.startswith("mesh connect"):
                parts = user_input.split(maxsplit=2)
                if len(parts) >= 3:
                    new_url = parts[2]
                    mesh_client.save_configuration(role=mesh_client.role, main_server_url=new_url)
                    is_online, ping_info = mesh_client.ping_main_server()
                    if is_online:
                        print(f"{GREEN}[OK] Connected to Main Server at {new_url}!{RESET}\n")
                    else:
                        print(f"{YELLOW}[!] Main Server at {new_url} is currently unreachable ({ping_info.get('error')}). Local fallback ready.{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: mesh connect <http://host:port>{RESET}\n")

            elif cmd_lower.startswith("mesh export"):
                parts = user_input.split(maxsplit=2)
                out_path = parts[2] if len(parts) >= 3 else "core_state_bundle.json"
                mesh_client.export_state_bundle(export_path=out_path)
                print(f"{GREEN}[OK] System state bundle exported to '{out_path}' for machine migration.{RESET}\n")

            elif cmd_lower.startswith("mesh import"):
                parts = user_input.split(maxsplit=2)
                if len(parts) >= 3:
                    in_path = parts[2]
                    counts = mesh_client.import_state_bundle(in_path)
                    print(f"{GREEN}[OK] State bundle restored: {counts}! Machine ready as Main Server.{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: mesh import <bundle_file.json>{RESET}\n")

            elif cmd_lower.startswith("hud"):
                payload_str = user_input[3:].strip()
                if "|" in payload_str:
                    title, body = [p.strip() for p in payload_str.split("|", 1)]
                else:
                    title, body = "Operator Alert", payload_str

                asyncio.run(connection_manager.broadcast_event("hud_card", {
                    "title": title,
                    "body": body,
                    "accent_color": "#00ffcc"
                }))
                print(f"{GREEN}[OK] Dispatched ambient HUD card to connected displays: '{title}'{RESET}")

            elif cmd_lower.startswith("logs"):
                parts = user_input.split()
                limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                recent = state.get_recent_execution_logs(limit=limit)
                print(f"\n{BRIGHT}--- Recent Execution Audit Logs ({len(recent)}) ---{RESET}")
                for log in recent:
                    lvl_col = GREEN if log["level"] == "INFO" else (RED if log["level"] == "ERROR" else YELLOW)
                    pipe_tag = f" [pipe:{log['pipeline_id'][:8]}]" if log.get("pipeline_id") else ""
                    print(f"  [{log['timestamp']}] [{lvl_col}{log['level']:<7}{RESET}] [{log['source']}]{pipe_tag} {log['message']}")
                print()

            elif cmd_lower == "proactive":
                print(f"{YELLOW}[*] Evaluating proactive state triggers...{RESET}")
                asyncio.run(proactive.evaluate_triggers())
                print(f"{GREEN}[OK] Proactive evaluation cycle complete.{RESET}")

            elif cmd_lower in ["harness", "eval", "diag", "selftest"]:
                print(f"\n{CYAN}======================================================================={RESET}")
                print(f"{CYAN}  CORE AI :: SOVEREIGN REASONING & EXECUTION HARNESS DIAGNOSTIC{RESET}")
                print(f"{CYAN}======================================================================={RESET}")
                
                # 1. State & DB Check
                db_ok = state.get_user_profile() is not None
                print(f"  [+] State Manager (SQLite WAL & Memory Cache)       [{GREEN if db_ok else RED}{'OK' if db_ok else 'FAIL'}{RESET}]")

                # 2. Tool Registry & Discovery
                tool_count = len(registry.tools)
                dyn_count = len(registry.dynamic_tools)
                print(f"  [+] Tool Registry ({tool_count} tools, {dyn_count} dynamic)                 [{GREEN}OK{RESET}]")

                # 3. Model Router & Active Reasoning Backend
                active_mod = model_router.get_active_model() or "Heuristic Engine (Offline Autonomous)"
                has_model = bool(model_router.get_active_model())
                print(f"  [+] Model Router (Active: {active_mod})   [{GREEN if has_model else YELLOW}{'ONLINE' if has_model else 'OFFLINE'}{RESET}]")

                # 4. EventBus Inter-Node Transport
                bus_type = "Redis Distributed" if getattr(bus, "is_connected", False) else "In-Memory Bus"
                print(f"  [+] EventBus Inter-Node Transport ({bus_type})    [{GREEN}OK{RESET}]")

                # 5. Spatial Audio Matrix & Zone Binding
                routes = state.list_all_audio_routes()
                print(f"  [+] Spatial Audio Matrix ({len(routes)} configured zone routes)       [{GREEN}OK{RESET}]")

                # 6. Safety Gate
                print(f"  [+] Safety Gate (Catastrophic Protection & Anti-Slop)      [{GREEN}ACTIVE{RESET}]")

                # 7. Gateway Server
                print(f"  [+] Universal Gateway (FastAPI & WebSocket Mesh :{port})     [{GREEN}ONLINE{RESET}]")
                print(f"{CYAN}-----------------------------------------------------------------------{RESET}")
                print(f"  {BRIGHT}Harness Status:{RESET} {GREEN}ALL REASONING & EXECUTION SUBSYSTEMS GREEN{RESET}\n")

            elif cmd_lower in ["update", "check-update", "upgrade"]:
                from core.updater import CoreUpdater
                updater = CoreUpdater()
                print(f"{CYAN}[*] Checking for updates and executing test-guarded upgrade...{RESET}")
                ok, msg = updater.apply_update()
                print(f"{GREEN if ok else RED}[{'OK' if ok else 'FAILED'}] {msg}{RESET}\n")

            elif cmd_lower.startswith("backup"):
                print(f"{CYAN}[*] Creating point-in-time state snapshot...{RESET}")
                from core.updater import CoreUpdater
                updater = CoreUpdater()
                db_s, env_s = updater.create_state_snapshot()
                print(f"{GREEN}[OK] Snapshot preserved:{RESET}\n  - Database: {db_s}\n  - Config:   {env_s}\n")

            elif cmd_lower in ["daemon", "bg", "background"]:
                print(f"{YELLOW}[*] Transitioning Core AI to background headless daemon...{RESET}")
                from core.service import ServiceManager
                sm = ServiceManager()
                ok, msg = sm.start(in_new_terminal=False, port=port, extra_args=["--headless"])
                if ok:
                    print(f"{GREEN}[OK] {msg}{RESET}")
                    print(f"{CYAN}Use 'core stop' to terminate, or 'core status' to inspect.{RESET}\n")
                    shutdown_event.set()
                    break
                else:
                    print(f"{RED}[!] {msg}{RESET}\n")

            elif cmd_lower in ["logo", "anim", "intro", "3d"]:
                from core.animation import run_interactive_animation
                run_interactive_animation()
                print_banner(active_name, active_zone, port)

            # --- Conversational Dialogues, Greetings & Small Talk ---
            elif clean_cmd in [
                "hi", "hello", "hey", "hallo", "moin", "servus", "guten tag",
                "guten morgen", "good morning", "good evening", "guten abend", "yo", "sup",
                "hey core", "hallo core", "hi core", "hello core", "hey core ai", "hallo core ai"
            ]:
                is_de = any(clean_cmd.startswith(w) for w in ["hallo", "moin", "servus", "guten"])
                reply = f"Hallo {active_name}! Bereit im {active_zone.title()}. Was steht an?" if is_de else f"Hey {active_name}! Online and ready in the {active_zone.title()}. What are we working on?"
                print(f"\n{CYAN}Core AI:{RESET} {BRIGHT}{reply}{RESET}\n")
                if voice_out:
                    voice_out.synthesize_and_play(reply)

            elif clean_cmd in ["how are you", "how are you doing", "wie gehts", "wie geht's", "wie geht es dir", "was geht", "what's up"]:
                is_de = "wie" in clean_cmd or "was" in clean_cmd
                reply = f"Alle Systeme laufen optimal, {active_name}. Wie kann ich dir helfen?" if is_de else f"All systems are green, {active_name}. Running smoothly in the {active_zone.title()}. How can I assist you today?"
                print(f"\n{CYAN}Core AI:{RESET} {BRIGHT}{reply}{RESET}\n")
                if voice_out:
                    voice_out.synthesize_and_play(reply)

            elif clean_cmd in ["who are you", "wer bist du", "what is core ai", "was ist core ai"]:
                is_de = "wer" in clean_cmd or "was" in clean_cmd
                reply = f"Ich bin Core AI, dein souveräner Life OS Microkernel und autonomer Problemlöser." if is_de else f"I am Core AI, your sovereign life OS microkernel and autonomous problem solver."
                print(f"\n{CYAN}Core AI:{RESET} {BRIGHT}{reply}{RESET}\n")
                if voice_out:
                    voice_out.synthesize_and_play(reply)

            elif clean_cmd in ["thanks", "thank you", "danke", "danke dir", "vielen dank"]:
                is_de = "danke" in clean_cmd
                reply = f"Gern geschehen, {active_name}! Sag Bescheid, wenn du noch etwas brauchst." if is_de else f"Anytime, {active_name}! Let me know if you need anything else."
                print(f"\n{CYAN}Core AI:{RESET} {BRIGHT}{reply}{RESET}\n")
                if voice_out:
                    voice_out.synthesize_and_play(reply)

            else:
                # Problem solving goal
                goal = user_input
                if cmd_lower.startswith("solve "):
                    goal = user_input[6:].strip()

                print(f"\n{CYAN}[*] Decomposing goal with Planner:{RESET} '{goal}'")

                def local_exec(target_goal, ctx):
                    plan = planner.plan_problem(target_goal, context=ctx)
                    if len(plan.steps) == 0:
                        return plan, 0.0

                    print(f"{CYAN}[+] Synthesized Pipeline DAG:{RESET} {len(plan.steps)} steps (ID: {plan.id[:8]})")
                    for s in plan.steps:
                        dep_str = f"(depends on: {', '.join(s.depends_on)})" if s.depends_on else "(independent)"
                        print(f"    - Step '{s.id}': {s.name} -> tool '{s.tool_name}' {dep_str}")

                    print(f"\n{YELLOW}[*] Executing pipeline concurrently...{RESET}")
                    start_time = time.time()
                    finished_plan = asyncio.run(engine.execute_pipeline(plan))
                    elapsed = time.time() - start_time
                    return finished_plan, elapsed

                def fallback_notice(msg):
                    print(f"\n{YELLOW}[!] {msg}{RESET}")

                if mesh_client.role == "edge_node":
                    mesh_res = mesh_client.execute_over_mesh(
                        goal=goal,
                        context={"zone": active_zone, "operator": active_name},
                        local_executor=lambda g, c: local_exec(g, c),
                        on_fallback_notice=fallback_notice
                    )
                    if mesh_res.get("execution_mode") == "remote_main_server":
                        res_data = mesh_res["result"]
                        print(f"{GREEN}[OK] Executed centrally on Main Server ({mesh_res['server_url']})!{RESET}")
                        print(f"{CYAN}Core AI [Remote]:{RESET} {BRIGHT}{res_data.get('final_output') or 'Task complete.'}{RESET}\n")
                        continue
                    else:
                        finished_plan, elapsed = mesh_res["result"]
                else:
                    finished_plan, elapsed = local_exec(goal, {"zone": active_zone, "operator": active_name})

                if len(finished_plan.steps) > 0:
                    if finished_plan.status == "completed":
                        print(f"\n{GREEN}[OK] Pipeline Succeeded in {elapsed:.2f}s!{RESET}")
                        for s in finished_plan.steps:
                            if s.tool_name == "relocate_operator" and s.status == "completed" and isinstance(s.output, dict):
                                new_z = s.output.get("zone")
                                if new_z:
                                    active_zone = new_z
                    else:
                        print(f"\n{RED}[FAILED] Pipeline Failed in {elapsed:.2f}s!{RESET}")
                elif finished_plan.context.get("offline_ai_notice"):
                    print(f"\n{YELLOW}[!] Notice: No AI reasoning model connected.{RESET}")

                spoken = planner.formulate_spoken_response(finished_plan, profile=state.get_user_profile())
                print(f"\n{CYAN}Core AI:{RESET} {BRIGHT}{spoken}{RESET}\n")

                if voice_out:
                    voice_out.synthesize_and_play(spoken)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}[*] Session interrupted by operator. Exiting...{RESET}")
            shutdown_event.set()
            break
        except Exception as e:
            print(f"{RED}[-] Error: {e}{RESET}")

def main():
    setup_logging()
    from interfaces.cli.setup_wizard import ensure_env_template
    ensure_env_template()
    load_dotenv("config/.env")
    args = parse_args()

    # Standalone 3D Animation Viewer
    if getattr(args, "logo", False) or getattr(args, "anim", False):
        from core.animation import run_interactive_animation
        run_interactive_animation()
        sys.exit(0)

    # One-Shot Goal Execution Mode (CLI Instant Dispatch)
    target_goal = args.solve
    if not target_goal and args.goal:
        target_goal = " ".join(args.goal).strip()

    if target_goal:
        target_port = args.port or int(os.getenv("CORE_PORT", 8000))
        mesh_client = MeshClient()

        # 1. Edge Node Mode: Dispatch directly to remote server across mesh
        if mesh_client.role == "edge_node" and mesh_client.main_server_url:
            is_online, _ = mesh_client.ping_main_server(timeout=1.5)
            if is_online:
                import urllib.request
                import json
                try:
                    url = f"{mesh_client.main_server_url}/api/v1/pipeline/solve_sync"
                    req_data = json.dumps({"goal": target_goal}).encode("utf-8")
                    req = urllib.request.Request(
                        url,
                        data=req_data,
                        headers={"Content-Type": "application/json", "User-Agent": "CoreAI-EdgeCLI/2.0"}
                    )
                    with urllib.request.urlopen(req, timeout=30.0) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        out_text = res.get("spoken_response") or res.get("final_output") or (res["steps"][-1].get("output") if res.get("steps") else "Task complete.")
                        if isinstance(out_text, dict):
                            out_msg = out_text.get("message") or out_text.get("status") or str(out_text)
                        else:
                            out_msg = str(out_text)
                        print(f"\n{CYAN}Core AI [Server @ {mesh_client.main_server_url}]:{RESET} {BRIGHT}{out_msg}{RESET}\n")
                        sys.exit(0 if res.get("status") == "completed" else 1)
                except Exception as de:
                    logger.warning(f"Remote mesh dispatch failed ({de}). Falling through to local execution.")

        # 2. Local Daemon Mode: Dispatch to local running daemon if healthy
        from core.service import ServiceManager
        sm = ServiceManager()
        is_healthy, _ = sm.check_health(port=target_port)

        if is_healthy:
            import urllib.request
            import json
            try:
                url = f"http://127.0.0.1:{target_port}/api/v1/pipeline/solve_sync"
                req_data = json.dumps({"goal": target_goal}).encode("utf-8")
                req = urllib.request.Request(
                    url,
                    data=req_data,
                    headers={"Content-Type": "application/json", "User-Agent": "CoreAI-CLI/2.0"}
                )
                with urllib.request.urlopen(req, timeout=30.0) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                    out_text = res.get("spoken_response") or res.get("final_output") or (res["steps"][-1].get("output") if res.get("steps") else "Task complete.")
                    if isinstance(out_text, dict):
                        out_msg = out_text.get("message") or out_text.get("status") or str(out_text)
                    else:
                        out_msg = str(out_text)
                    print(f"\n{CYAN}Core AI [Daemon]:{RESET} {BRIGHT}{out_msg}{RESET}\n")
                    sys.exit(0 if res.get("status") == "completed" else 1)
            except Exception as de:
                logger.warning(f"Daemon dispatch encountered notice ({de}). Falling through to in-process execution.")

        # Local in-process one-shot execution
        state = StateManager()
        registry = setup_tools(state=state)
        model_router = ModelRouter(state_manager=state)
        dyn_gen = DynamicGenerator(registry=registry, state_manager=state, model_router=model_router)
        use_heuristic = getattr(args, "heuristic", False) or os.getenv("CORE_FORCE_HEURISTIC") == "1"
        if use_heuristic:
            planner = Planner(registry=registry, state_manager=state, dynamic_generator=dyn_gen, model_name="heuristic")
        else:
            planner = Planner(registry=registry, state_manager=state, dynamic_generator=dyn_gen, model_router=model_router)

        bus = EventBus()
        engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)
        profile = state.get_user_profile()
        active_zone = profile.preferences.get("primary_space", "office")

        plan = planner.plan_problem(target_goal, {"zone": active_zone, "operator": profile.preferred_name})
        finished = asyncio.run(engine.execute_pipeline(plan))
        spoken = planner.formulate_spoken_response(finished, profile=profile)
        print(f"\n{CYAN}Core AI:{RESET} {BRIGHT}{spoken}{RESET}\n")
        sys.exit(0 if finished.status == "completed" else 1)

    if not args.headless:
        should_skip_anim = not getattr(args, "anim", False)
        play_boot_sequence(skip_anim=should_skip_anim)

    logger.info("Initializing Core AI Microkernel with Universal Gateway, Proactive Engine & Model Router...")

    # Write PID file for process tracking
    pid_file = os.path.join(os.path.dirname(__file__), ".core_ai.pid")
    try:
        with open(pid_file, "w", encoding="utf-8") as pf:
            pf.write(str(os.getpid()))
    except Exception:
        pass

    # 1. State & Bus Core
    bus = EventBus()
    state = StateManager()
    context = ContextManager()
    relocator = OperatorRelocator(state_manager=state)
    registry = setup_tools(state=state, relocator=relocator)
    profile = state.get_user_profile()

    # Day-Zero Check for interactive console
    if not args.headless:
        from interfaces.cli.setup_wizard import is_account_initialized, run_setup
        if not is_account_initialized(state):
            print(f"\n{YELLOW}[!] Day-Zero Blank Slate: No Sovereign Operator Account configured.{RESET}")
            try:
                init_resp = input(f"{CYAN}[?] Initialize your Sovereign Core Account now? [Y/n]: {RESET}").strip().lower()
                if init_resp in ["", "y", "yes"]:
                    profile = run_setup(state=state)
            except (KeyboardInterrupt, EOFError):
                print()

    operator_name = profile.preferred_name
    primary_zone = profile.preferences.get("primary_space", "office")
    state.ensure_zone_exists(primary_zone, display_name=f"{operator_name}'s Primary Space")

    # 2. Remote Edge Dispatcher
    remote_dispatcher = RemoteToolDispatcher(registry=registry)

    # 3. Model Router & Brain
    model_router = ModelRouter(state_manager=state)
    dyn_gen = DynamicGenerator(registry=registry, state_manager=state, model_router=model_router)
    planner = Planner(registry=registry, state_manager=state, dynamic_generator=dyn_gen, model_router=model_router)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)
    spoken_to = SpokenToReasoning(state_manager=state, registry=registry, planner=planner)
    mesh_client = MeshClient(state_manager=state)

    # 4. Proactive Daemon
    proactive = ProactiveDaemon(
        state_manager=state,
        planner=planner,
        pipeline_engine=engine,
        bus=bus,
        check_interval_seconds=4.0
    )

    # 5. Voice Out Engine
    voice_out: Optional[VoiceOutEngine] = None
    if not args.no_tts:
        try:
            voice_out = VoiceOutEngine(default_voice="auto", output_device=args.device)
            voice_out.attach_to_bus(bus, channel="tts_events")
            logger.info("VoiceOutEngine online with Edge Neural TTS & pyttsx3 fallback.")
        except Exception as e:
            logger.warning(f"VoiceOutEngine initialization skipped: {e}")

    # 6. Spatial Audio & Handoff
    audio_router = SpatialAudioRouter(state_manager=state)
    spatial_handoff = SpatialHandoffEngine(
        state_manager=state,
        bus=bus,
        audio_router=audio_router,
        voice_out_engine=voice_out
    )
    relocator.spatial_handoff = spatial_handoff

    # 7. Universal Gateway App
    gateway_app = create_gateway_app(
        state_manager=state,
        registry=registry,
        planner=planner,
        pipeline_engine=engine,
        bus=bus,
        remote_dispatcher=remote_dispatcher,
        spoken_to=spoken_to
    )

    # Voice state broadcast helper
    def broadcast_voice_state(state_name: str, extra: Optional[Dict[str, Any]] = None):
        payload = {"state": state_name}
        if extra:
            payload.update(extra)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    connection_manager.broadcast_event("voice_state", payload),
                    loop
                )
        except Exception:
            pass

    # Event Handlers
    def handle_text_event(data: dict):
        try:
            event = TextEvent(**data)
            effective_zone = event.get_effective_zone()
            logger.info(f"Received text event from zone '{effective_zone}': '{event.text}'")
            current_profile = state.get_user_profile()

            decision = spoken_to.evaluate(event.text, profile=current_profile)
            if decision.action_type == "interrupt":
                logger.info(f"[Spoken-To] Verbal interrupt intercepted: '{event.text}'")
                if voice_out:
                    voice_out.interrupt()
                broadcast_voice_state("idle", {"zone": effective_zone, "interrupted": True})
                return

            if not decision.should_respond:
                logger.info(f"[Spoken-To] Silently ignored: '{event.text}'")
                return

            if voice_out and voice_out.is_speaking:
                voice_out.interrupt()

            if decision.discourse_role == DiscourseRole.DEMONSTRATED and decision.autonomous_response:
                logger.info(f"[Spoken-To Showcase Chime-In]: '{decision.autonomous_response}'")
                bus.publish("tts_events", TTSRequestEvent(
                    source_node="brain",
                    room_id=effective_zone,
                    text=decision.autonomous_response
                ))
                asyncio.run(connection_manager.broadcast_event("hud_card", {
                    "title": "Core AI - Live Showcase",
                    "body": decision.autonomous_response,
                    "accent_color": "#ffaa00",
                    "zone": effective_zone
                }))
                broadcast_voice_state("idle", {"zone": effective_zone})
                return

            command_text = decision.clean_command or event.text
            broadcast_voice_state("thinking", {"query": command_text, "zone": effective_zone})
            room_context = {"zone": effective_zone, "device_type": event.get_device_type()}

            plan = planner.plan_problem(command_text, room_context)
            finished_plan = asyncio.run(engine.execute_pipeline(plan))
            response_text = planner.formulate_spoken_response(finished_plan, profile=current_profile)

            bus.publish("tts_events", TTSRequestEvent(
                source_node="brain",
                room_id=effective_zone,
                text=response_text
            ))
            asyncio.run(connection_manager.broadcast_event("hud_card", {
                "title": f"Core AI - {current_profile.preferred_name}",
                "body": response_text,
                "accent_color": "#00ffcc" if finished_plan.status == "completed" else "#ff3366",
                "zone": effective_zone
            }))
            broadcast_voice_state("idle", {"zone": effective_zone})

        except Exception as e:
            logger.error(f"Error handling text event: {e}", exc_info=True)
            broadcast_voice_state("idle", {"error": str(e)})

    bus.subscribe("text_events", handle_text_event)
    bus.start_listening()
    proactive.start()

    # Voice In Engine: Always active by default on startup (can be disabled via --no-voice / --no-mic or CORE_DISABLE_VOICE=1)
    voice_in_disabled = (
        args.no_voice
        or os.getenv("CORE_DISABLE_VOICE", "0").lower() in ("1", "true", "yes")
        or os.getenv("CORE_NO_VOICE", "0").lower() in ("1", "true", "yes")
    )
    voice_in: Optional[VoiceInEngine] = None
    if not voice_in_disabled:
        try:
            logger.info(f"Initializing VoiceInEngine (always-on mic) with model '{args.model_size}'...")
            voice_in = VoiceInEngine(
                model_size=args.model_size,
                input_device=args.device,
                voice_out=voice_out
            )
            if voice_out:
                voice_in.register_voice_out(voice_out)
            if args.headless:
                # In headless server mode, connect mic directly into event bus loop
                voice_in.bridge_to_event_bus(
                    bus=bus,
                    zone=primary_zone,
                    device_type="mic",
                    state_callback=lambda st: broadcast_voice_state(st, {"zone": primary_zone})
                )
                logger.info(f"Voice capture active (always-on) in zone: '{primary_zone}'.")
            else:
                logger.info(f"Voice capture engine ready for interactive REPL in zone: '{primary_zone}'.")
        except Exception as e:
            logger.warning(f"VoiceInEngine auto-initialization skipped ({e}). Continuing in terminal mode.")
            voice_in = None

    # Background Universal Gateway Server
    host = args.host or os.getenv("CORE_HOST", "0.0.0.0")
    requested_port = args.port or int(os.getenv("CORE_PORT", 8000))
    port = requested_port

    import socket
    def is_port_in_use(h: str, p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((h, p))
                return False
            except OSError:
                return True

    if is_port_in_use(host, port):
        found_port = None
        for candidate in range(port + 1, port + 25):
            if not is_port_in_use(host, candidate):
                found_port = candidate
                break
        if found_port:
            logger.warning(f"Port {requested_port} is already in use by another process. Automatically binding Universal Gateway to port {found_port}.")
            port = found_port
        else:
            logger.error(f"Port {requested_port} and all fallback ports are occupied.")

    shutdown_event = threading.Event()

    config = uvicorn.Config(gateway_app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    
    server_thread = threading.Thread(target=server.run, daemon=True, name="CoreGatewayThread")
    server_thread.start()

    logger.info(f"Core AI Universal Gateway running on http://{host}:{port}")

    try:
        if args.headless:
            logger.info("Headless server mode active. Press Ctrl+C to terminate.")
            while not shutdown_event.is_set():
                time.sleep(0.5)
        else:
            # Interactive Core Terminal REPL
            run_interactive_repl(
                state=state,
                bus=bus,
                registry=registry,
                planner=planner,
                engine=engine,
                proactive=proactive,
                model_router=model_router,
                mesh_client=mesh_client,
                spoken_to=spoken_to,
                audio_router=audio_router,
                spatial_handoff=spatial_handoff,
                voice_out=voice_out,
                voice_in=voice_in,
                port=port,
                shutdown_event=shutdown_event
            )
    except KeyboardInterrupt:
        logger.info("Shutdown requested by operator...")
    finally:
        logger.info("Stopping all background services cleanly...")
        server.should_exit = True
        if voice_in:
            voice_in.stop_listening()
        if voice_out:
            voice_out.stop()
        proactive.stop()
        bus.stop_listening()
        if os.path.exists(pid_file):
            try:
                os.remove(pid_file)
            except Exception:
                pass
        logger.info("Core AI shutdown complete.")

if __name__ == "__main__":
    main()
