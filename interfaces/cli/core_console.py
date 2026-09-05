import os
import sys
import time
import json
import asyncio
import logging
from typing import Optional

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.logging_setup import setup_logging
from core.state import StateManager
from core.bus import EventBus
from core.schemas import PipelineStep, PipelinePlan, HUDCardPayload, TextEvent
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema, get_system_status
from tools.native.file_tools import read_text_file, read_file_schema, write_text_file, write_file_schema, list_dir_contents, list_dir_schema
from tools.native.math_tools import calculate_math, calculate_math_schema, summarize_numbers, summarize_numbers_schema
from tools.remote_dispatcher import RemoteToolDispatcher
from brain.dynamic_generator import DynamicGenerator
from brain.pipeline_engine import PipelineEngine
from brain.planner import Planner
from brain.proactive import ProactiveDaemon
from core.gateway import connection_manager
from engines.voice_out import VoiceOutEngine
from engines.voice_in import VoiceInEngine
from brain.model_router import ModelRouter
from brain.spoken_to import SpokenToReasoning, DiscourseRole
from core.mesh_client import MeshClient
from engines.audio_router import SpatialAudioRouter, route_spatial_audio, route_spatial_audio_schema
from brain.spatial_handoff import SpatialHandoffEngine

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

def print_banner(operator_name: str, zone: str):
    print(f"\n{CYAN}╔═══════════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{CYAN}║{BRIGHT}    🌐 CORE AI SOVEREIGN LIFE OS — INTERACTIVE OPERATOR CONSOLE            {RESET}{CYAN}║{RESET}")
    print(f"{CYAN}║{RESET}    Self-Hosted • Privacy-First • Autonomous Problem Solver                {CYAN}║{RESET}")
    print(f"{CYAN}╠═══════════════════════════════════════════════════════════════════════════╣{RESET}")
    print(f"{CYAN}║{RESET}    Operator: {GREEN}{operator_name:<18}{RESET} Zone: {YELLOW}{zone:<18}{RESET} Status: {GREEN}ONLINE       {RESET}{CYAN}║{RESET}")
    print(f"{CYAN}╚═══════════════════════════════════════════════════════════════════════════╝{RESET}\n")
    print(f"{MAGENTA}Type any goal to solve it, or type 'help' for built-in management commands.{RESET}\n")

def print_help():
    print(f"\n{BRIGHT}Available Core Console Commands:{RESET}")
    print(f"  {GREEN}solve <goal>{RESET}              - Solve any task via autonomous DAG pipeline (or type directly)")
    print(f"  {GREEN}speak <text>{RESET}              - Synthesize neural speech via speakers")
    print(f"  {GREEN}spoken <text>{RESET}             - Test Spoken-To Reasoning classification on any phrase")
    print(f"  {GREEN}audio{RESET}                     - Inspect connected mics, studio interfaces & speakers")
    print(f"  {GREEN}handoff <zone>{RESET}            - Transition spatial anchor & auto-route audio to new zone")
    print(f"  {GREEN}voice on / voice off{RESET}       - Toggle background microphone listening")
    print(f"  {GREEN}status{RESET}                    - Inspect system health, platform architecture & model status")
    print(f"  {GREEN}profile{RESET}                   - View or update operator identity and preferences")
    print(f"  {GREEN}profile set <name> [alias]{RESET}- Update operator name and aliases")
    print(f"  {GREEN}zones{RESET}                     - List all dynamically discovered spatial zones")
    print(f"  {GREEN}zone add <id> [name]{RESET}      - Declare a new spatial zone on-the-fly")
    print(f"  {GREEN}devices{RESET}                   - List all connected fixed and roaming devices & trust tiers")
    print(f"  {GREEN}models{RESET}                    - Inspect configured AI providers, active models & health")
    print(f"  {GREEN}model set <role> <model>{RESET}   - Assign model to role (planner, fallback, deep_reasoning)")
    print(f"  {GREEN}api-key set <provider> <key>{RESET}- Set API key for provider (gemini, openai, anthropic)")
    print(f"  {GREEN}mesh{RESET}                      - Inspect intercontinental mesh status, role & server reachability")
    print(f"  {GREEN}mesh role <main|edge>{RESET}     - Switch node role between main_server and edge_node")
    print(f"  {GREEN}mesh connect <url>{RESET}        - Set central main server URL and test connection")
    print(f"  {GREEN}mesh export [path]{RESET}        - Export portable state bundle to migrate server")
    print(f"  {GREEN}mesh import <path>{RESET}        - Import state bundle to restore server on new machine")
    print(f"  {GREEN}hud <title> | <body{RESET}>       - Dispatch a live ambient HUD card to Smart Mirror")
    print(f"  {GREEN}logs [N]{RESET}                  - View recent execution audit logs from SQLite")
    print(f"  {GREEN}proactive{RESET}                 - Run proactive watcher evaluation on demand")
    print(f"  {GREEN}clear{RESET}                     - Clear terminal screen")
    print(f"  {GREEN}exit / quit{RESET}               - Exit console\n")

def setup_kernel():
    state = StateManager()
    bus = EventBus()
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("get_system_status", get_system_status, {
        "name": "get_system_status",
        "description": "Get current operating system and platform status",
        "parameters": {"type": "object", "properties": {}}
    })
    registry.register_tool("read_text_file", read_text_file, read_file_schema)
    registry.register_tool("write_text_file", write_text_file, write_file_schema)
    registry.register_tool("list_dir_contents", list_dir_contents, list_dir_schema)
    registry.register_tool("calculate_math", calculate_math, calculate_math_schema)
    registry.register_tool("summarize_numbers", summarize_numbers, summarize_numbers_schema)
    registry.register_tool("route_spatial_audio", route_spatial_audio, route_spatial_audio_schema)
    registry.discover_dynamic_tools()

    model_router = ModelRouter(state_manager=state)
    planner = Planner(registry=registry, state_manager=state, dynamic_generator=dyn_gen, model_router=model_router)
    mesh_client = MeshClient(state_manager=state)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)
    proactive = ProactiveDaemon(state_manager=state, planner=planner, pipeline_engine=engine, bus=bus)
    voice_out = VoiceOutEngine(default_voice="auto")
    voice_out.attach_to_bus(bus)
    spoken_to = SpokenToReasoning(state_manager=state, registry=registry, planner=planner)
    audio_router = SpatialAudioRouter(state_manager=state)
    spatial_handoff = SpatialHandoffEngine(
        state_manager=state,
        bus=bus,
        audio_router=audio_router,
        voice_out_engine=voice_out
    )

    return state, bus, registry, planner, engine, proactive, voice_out, spoken_to, audio_router, spatial_handoff, model_router, mesh_client

def main():
    state, bus, registry, planner, engine, proactive, voice_out, spoken_to, audio_router, spatial_handoff, model_router, mesh_client = setup_kernel()

    
    profile = state.get_user_profile()
    active_name = profile.preferred_name
    active_zone = profile.preferences.get("primary_space", "studio")
    state.ensure_zone_exists(active_zone, display_name=f"{active_name}'s Primary Zone")

    voice_in: Optional[VoiceInEngine] = None
    voice_feedback_enabled = True

    print_banner(active_name, active_zone)

    while True:
        try:
            mic_indicator = f" {RED}●REC{RESET}" if (voice_in and voice_in.is_recording) else ""
            prompt = f"{CYAN}Core{RESET} [{GREEN}{active_name}{RESET}@{YELLOW}{active_zone}{RESET}{mic_indicator}] {BRIGHT}>{RESET} "
            user_input = input(prompt).strip()
            if not user_input:
                continue

            cmd_lower = user_input.lower()

            if cmd_lower in ["exit", "quit"]:
                print(f"{YELLOW}[*] Shutting down Core Console. Goodbye {active_name}!{RESET}")
                if voice_in:
                    voice_in.stop_listening()
                voice_out.stop()
                break

            elif cmd_lower == "help":
                print_help()

            elif cmd_lower == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                print_banner(active_name, active_zone)

            elif cmd_lower == "status":
                status = get_system_status()
                print(f"\n{BRIGHT}--- Core AI System Status ---{RESET}")
                print(f"  Operator:     {GREEN}{active_name}{RESET}")
                print(f"  Platform:     {status.get('os')} {status.get('release')} ({status.get('architecture')})")
                print(f"  Active Model: {planner.get_active_model() or 'offline_heuristic'}")
                print(f"  Tools Loaded: {len(registry.tools)}")
                print(f"  Active Zones: {len(state.list_zones())}")
                print(f"  Devices:      {len(state.list_all_devices())}")
                print(f"  Voice Out:    {GREEN}Edge Neural TTS + pyttsx3{RESET}")
                print(f"  Voice In:     {GREEN}Active{RESET}" if (voice_in and voice_in.is_recording) else f"  Voice In:     {YELLOW}Standby (type 'voice on'){RESET}")
                print()

            elif cmd_lower == "audio":
                print(f"\n{BRIGHT}--- Connected Audio Interfaces & Devices ---{RESET}")
                out_devs = voice_out.list_output_devices()
                in_devs = VoiceInEngine(model_size="tiny").list_input_devices()
                print(f"{CYAN}Input Devices ({len(in_devs)}):{RESET}")
                for d in in_devs[:8]:
                    print(f"  [{d['index']}] {d['name']} (channels: {d['channels']})")
                if len(in_devs) > 8:
                    print(f"  ... and {len(in_devs) - 8} more")

                print(f"\n{CYAN}Output Devices ({len(out_devs)}):{RESET}")
                for d in out_devs[:8]:
                    print(f"  [{d['index']}] {d['name']} (channels: {d['channels']})")
                if len(out_devs) > 8:
                    print(f"  ... and {len(out_devs) - 8} more")
                print()

            elif cmd_lower.startswith("speak "):
                text_to_speak = user_input[6:].strip()
                print(f"{CYAN}[*] Synthesizing speech:{RESET} '{text_to_speak}'")
                voice_out.synthesize_and_play(text_to_speak)

            elif cmd_lower == "voice on":
                if voice_in and voice_in.is_recording:
                    print(f"{YELLOW}[!] Voice capture is already listening.{RESET}")
                else:
                    print(f"{YELLOW}[*] Initializing VoiceInEngine (faster-whisper)...{RESET}")
                    try:
                        voice_in = VoiceInEngine(model_size="distil-large-v3")
                        
                        def on_speech(text: str):
                            print(f"\n{MAGENTA}[🎙️ SPEECH DETECTED]{RESET} \"{text}\"")
                            prof = state.get_user_profile()
                            decision = spoken_to.evaluate(text, profile=prof)
                            print(f"  {CYAN}[Spoken-To Decision]{RESET} Role: {decision.discourse_role.value} | Action: {decision.action_type}")

                            if not decision.should_respond:
                                print(f"  {YELLOW}↳ Silently ignored (ambient / not addressed to Core AI){RESET}\n")
                                print(prompt, end="", flush=True)
                                return

                            if decision.discourse_role == DiscourseRole.DEMONSTRATED and decision.autonomous_response:
                                print(f"{CYAN}Core AI [Showcase]:{RESET} {decision.autonomous_response}\n")
                                voice_out.synthesize_and_play(decision.autonomous_response)
                                print(prompt, end="", flush=True)
                                return

                            # Direct Command
                            target_cmd = decision.clean_command or text
                            plan = planner.plan_problem(target_cmd, context={"zone": active_zone, "operator": active_name})
                            finished = asyncio.run(engine.execute_pipeline(plan))
                            spoken = planner.formulate_spoken_response(finished, profile=prof)
                            print(f"{CYAN}Core AI:{RESET} {spoken}\n")
                            voice_out.synthesize_and_play(spoken)
                            print(prompt, end="", flush=True)

                        voice_in.start_listening(callback=on_speech)
                        print(f"{GREEN}[✓] Voice capture online! Speak into your microphone anytime.{RESET}")
                    except Exception as e:
                        print(f"{RED}[✗] Failed to start voice capture: {e}{RESET}")

            elif cmd_lower.startswith("test-spoken ") or cmd_lower.startswith("spoken "):
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

            elif cmd_lower == "voice off":
                if voice_in and voice_in.is_recording:
                    voice_in.stop_listening()
                    print(f"{YELLOW}[*] Voice capture stopped.{RESET}")
                else:
                    print(f"{YELLOW}[!] Voice capture was not active.{RESET}")

            elif cmd_lower == "audio":
                devs = audio_router.list_system_audio_devices()
                print(f"\n{BRIGHT}--- Connected Audio Inputs ({len(devs['inputs'])}) ---{RESET}")
                for d in devs["inputs"]:
                    print(f"  [{d['index']:2d}] 🎙️  {d['name']} (ch={d['max_input_channels']})")
                print(f"\n{BRIGHT}--- Connected Audio Outputs ({len(devs['outputs'])}) ---{RESET}")
                for d in devs["outputs"]:
                    print(f"  [{d['index']:2d}] 🔊 {d['name']} (ch={d['max_output_channels']})")
                routes = state.list_all_audio_routes()
                if routes:
                    print(f"\n{BRIGHT}--- Configured Zone Audio Routes ({len(routes)}) ---{RESET}")
                    for r in routes:
                        print(f"  • {YELLOW}{r.zone_id:<18}{RESET} : Mic='{r.input_device_name}' | Speaker='{r.output_device_name}'")
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
                print(f"{GREEN}[✓] Relocated to '{target_z}'! Audio re-routed & HUD card broadcast.{RESET}\n")

            elif cmd_lower == "profile":

                p = state.get_user_profile()
                print(f"\n{BRIGHT}--- Operator Profile ---{RESET}")
                print(f"  Name:       {GREEN}{p.preferred_name}{RESET}")
                print(f"  Aliases:    {', '.join(p.aliases) if p.aliases else 'None'}")
                print(f"  Tone:       {p.preferred_tone}")
                print(f"  Primary Zone:{p.preferences.get('primary_space', 'studio')}")
                print(f"  Updated At: {p.updated_at}\n")

            elif cmd_lower.startswith("profile set"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 3:
                    new_name = parts[2]
                    alias = parts[3] if len(parts) > 3 else None
                    state.set_user_preferred_name(new_name, alias=alias)
                    active_name = new_name
                    print(f"{GREEN}[✓] Operator identity updated to: {new_name}{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: profile set <name> [alias]{RESET}")

            elif cmd_lower == "zones":
                zones = state.list_zones()
                print(f"\n{BRIGHT}--- Dynamically Discovered Spatial Zones ({len(zones)}) ---{RESET}")
                for z in zones:
                    print(f"  - {YELLOW}{z['zone_id']:<16}{RESET} Display: {z['display_name']} (Discovered: {z['created_at'][:19]})")
                print()

            elif cmd_lower.startswith("zone add"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 3:
                    zid = parts[2]
                    zname = parts[3] if len(parts) > 3 else zid.title()
                    state.ensure_zone_exists(zid, display_name=zname)
                    print(f"{GREEN}[✓] Spatial zone '{zid}' registered.{RESET}")
                else:
                    print(f"{RED}[!] Usage: zone add <zone_id> [display_name]{RESET}")

            elif cmd_lower == "devices":
                devs = state.list_all_devices()
                print(f"\n{BRIGHT}--- Connected Devices & Trust Topology ({len(devs)}) ---{RESET}")
                for d in devs:
                    anchor = "Fixed Anchor" if d["is_fixed_anchor"] else "Roaming"
                    print(f"  - {CYAN}{d['device_id']:<16}{RESET} Type: {d['device_type']:<12} Zone: {d['current_zone']:<14} Tier: {GREEN}{d['trust_tier']:<8}{RESET} ({anchor})")
                print()

            elif cmd_lower == "tools":
                cat = registry.get_tool_catalog()
                print(f"\n{BRIGHT}--- Core AI Tool Catalog ({len(cat)} tools) ---{RESET}")
                for t in cat:
                    dyn_flag = f"{MAGENTA}[DYNAMIC]{RESET} " if t.get("is_dynamic") else f"{GREEN}[NATIVE]{RESET}  "
                    print(f"  {dyn_flag}{t['name']:<24} {t.get('description', '')[:50]}")
                print()

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
                print(f"{GREEN}[✓] Dispatched ambient HUD card to mirror: '{title}'{RESET}")

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

            elif cmd_lower == "models":
                summary = model_router.get_status_summary()
                print(f"\n{BRIGHT}--- Configured AI Providers & Models ---{RESET}")
                for prov, enabled in summary["configured_providers"].items():
                    col = GREEN if enabled else YELLOW
                    status_lbl = "Configured / Online" if enabled else "Not Configured / Offline"
                    print(f"  • {prov:<16} : [{col}{status_lbl}{RESET}]")

                print(f"\n{BRIGHT}--- Active Model Roles & Assignments ---{RESET}")
                for role, info in summary["roles"].items():
                    col = GREEN if info["online"] else YELLOW
                    status_lbl = "ONLINE" if info["online"] else "OFFLINE (Heuristic Fallback)"
                    print(f"  • {role:<16} : {CYAN}{info['model']:<26}{RESET} [{col}{status_lbl}{RESET}]")
                print()

            elif cmd_lower.startswith("model set"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 4:
                    role, m_name = parts[2], parts[3]
                    model_router.set_model_preference(role, m_name)
                    print(f"{GREEN}[✓] Assigned model '{m_name}' to role '{role}'.{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: model set <role> <model_name> (roles: planner, fallback, deep_reasoning, fast_local){RESET}\n")

            elif cmd_lower.startswith("api-key set") or cmd_lower.startswith("key set"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 4:
                    provider, key_val = parts[2], parts[3]
                    env_var = model_router.set_api_key(provider, key_val, persist_to_env=True)
                    print(f"{GREEN}[✓] Saved API key for '{provider}' to {env_var} and config/.env.{RESET}\n")
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
                    print(f"{GREEN}[✓] Node role switched to: {new_role}{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: mesh role <main_server|edge_node>{RESET}\n")

            elif cmd_lower.startswith("mesh connect"):
                parts = user_input.split(maxsplit=2)
                if len(parts) >= 3:
                    new_url = parts[2]
                    mesh_client.save_configuration(role=mesh_client.role, main_server_url=new_url)
                    is_online, ping_info = mesh_client.ping_main_server()
                    if is_online:
                        print(f"{GREEN}[✓] Connected to Main Server at {new_url}!{RESET}\n")
                    else:
                        print(f"{YELLOW}[!] Main Server at {new_url} is currently unreachable ({ping_info.get('error')}). Local fallback ready.{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: mesh connect <http://host:port>{RESET}\n")

            elif cmd_lower.startswith("mesh export"):
                parts = user_input.split(maxsplit=2)
                out_path = parts[2] if len(parts) >= 3 else "core_state_bundle.json"
                mesh_client.export_state_bundle(export_path=out_path)
                print(f"{GREEN}[✓] System state bundle exported to '{out_path}' for machine migration.{RESET}\n")

            elif cmd_lower.startswith("mesh import"):
                parts = user_input.split(maxsplit=2)
                if len(parts) >= 3:
                    in_path = parts[2]
                    counts = mesh_client.import_state_bundle(in_path)
                    print(f"{GREEN}[✓] State bundle restored: {counts}! Machine ready as Main Server.{RESET}\n")
                else:
                    print(f"{RED}[!] Usage: mesh import <bundle_file.json>{RESET}\n")

            else:
                # Treat as problem / goal solving query
                goal = user_input
                if cmd_lower.startswith("solve "):
                    goal = user_input[6:].strip()

                print(f"\n{CYAN}[*] Decomposing goal with Planner:{RESET} '{goal}'")
                
                def local_exec(target_goal, ctx):
                    plan = planner.plan_problem(target_goal, context=ctx)
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
                        print(f"{GREEN}[✓] Executed centrally on Main Server ({mesh_res['server_url']})!{RESET}")
                        print(f"{CYAN}Core AI [Remote]:{RESET} {BRIGHT}{res_data.get('final_output') or 'Task complete.'}{RESET}\n")
                        continue
                    else:
                        finished_plan, elapsed = mesh_res["result"]
                else:
                    finished_plan, elapsed = local_exec(goal, {"zone": active_zone, "operator": active_name})

                if finished_plan.status == "completed":
                    print(f"\n{GREEN}[✓] Pipeline Succeeded in {elapsed:.2f}s!{RESET}")
                else:
                    print(f"\n{RED}[✗] Pipeline Failed in {elapsed:.2f}s!{RESET}")

                spoken = planner.formulate_spoken_response(finished_plan, profile=state.get_user_profile())
                print(f"\n{CYAN}Core AI:{RESET} {BRIGHT}{spoken}{RESET}\n")

                # Speak response through VoiceOutEngine
                if voice_feedback_enabled:
                    voice_out.synthesize_and_play(spoken)

        except KeyboardInterrupt:
            print(f"\n{YELLOW}[*] Session interrupted. Exiting...{RESET}")
            if voice_in:
                voice_in.stop_listening()
            voice_out.stop()
            break
        except Exception as e:
            print(f"{RED}[-] Error: {e}{RESET}")

if __name__ == "__main__":
    main()
