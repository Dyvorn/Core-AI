import os
import sys
import time
import json
import asyncio
import logging

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.logging_setup import setup_logging
from core.state import StateManager
from core.bus import EventBus
from core.schemas import PipelineStep, PipelinePlan, HUDCardPayload
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
    print(f"  {GREEN}status{RESET}                    - Inspect system health, platform architecture & model status")
    print(f"  {GREEN}profile{RESET}                   - View or update operator identity and preferences")
    print(f"  {GREEN}profile set <name> [alias]{RESET}- Update operator name and aliases")
    print(f"  {GREEN}zones{RESET}                     - List all dynamically discovered spatial zones")
    print(f"  {GREEN}zone add <id> [name]{RESET}      - Declare a new spatial zone on-the-fly")
    print(f"  {GREEN}devices{RESET}                   - List all connected fixed and roaming devices & trust tiers")
    print(f"  {GREEN}tools{RESET}                     - Inspect native, dynamic, and remote edge tool catalog")
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
    registry.discover_dynamic_tools()

    remote_dispatcher = RemoteToolDispatcher(registry=registry)
    dyn_gen = DynamicGenerator(registry=registry, state_manager=state)
    planner = Planner(registry=registry, state_manager=state, dynamic_generator=dyn_gen)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)
    proactive = ProactiveDaemon(state_manager=state, planner=planner, pipeline_engine=engine, bus=bus)

    return state, bus, registry, planner, engine, proactive

def main():
    state, bus, registry, planner, engine, proactive = setup_kernel()
    
    profile = state.get_user_profile()
    active_name = profile.preferred_name
    active_zone = "workspace"
    state.ensure_zone_exists(active_zone, display_name="Primary Workspace")

    print_banner(active_name, active_zone)

    while True:
        try:
            prompt = f"{CYAN}Core{RESET} [{GREEN}{active_name}{RESET}@{YELLOW}{active_zone}{RESET}] {BRIGHT}>{RESET} "
            user_input = input(prompt).strip()
            if not user_input:
                continue

            cmd_lower = user_input.lower()

            if cmd_lower in ["exit", "quit"]:
                print(f"{YELLOW}[*] Shutting down Core Console. Goodbye {active_name}!{RESET}")
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
                print(f"  Platform:     {status.get('system')} {status.get('release')} ({status.get('machine')})")
                print(f"  Active Model: {planner.get_active_model() or 'offline_heuristic'}")
                print(f"  Tools Loaded: {len(registry.tools)}")
                print(f"  Active Zones: {len(state.list_zones())}")
                print(f"  Devices:      {len(state.list_all_devices())}\n")

            elif cmd_lower == "profile":
                p = state.get_user_profile()
                print(f"\n{BRIGHT}--- Operator Profile ---{RESET}")
                print(f"  Name:       {GREEN}{p.preferred_name}{RESET}")
                print(f"  Aliases:    {', '.join(p.aliases) if p.aliases else 'None'}")
                print(f"  Tone:       {p.preferred_tone}")
                print(f"  Updated At: {p.updated_at}\n")

            elif cmd_lower.startswith("profile set"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 3:
                    new_name = parts[2]
                    aliases = [parts[3]] if len(parts) > 3 else []
                    state.set_user_preferred_name(new_name, aliases=aliases)
                    active_name = new_name
                    print(f"{GREEN}[OK] Updated profile name to '{new_name}'!{RESET}")
                else:
                    print(f"{RED}[-] Usage: profile set <name> [aliases]{RESET}")

            elif cmd_lower == "zones":
                zones = state.list_zones()
                print(f"\n{BRIGHT}--- Discovered Spatial Zones ({len(zones)}) ---{RESET}")
                for z in zones:
                    print(f"  • {YELLOW}{z.zone_id:<20}{RESET} : {z.display_name}")
                print()

            elif cmd_lower.startswith("zone add"):
                parts = user_input.split(maxsplit=3)
                if len(parts) >= 3:
                    zid = parts[2]
                    zname = parts[3] if len(parts) > 3 else zid.replace("_", " ").title()
                    state.ensure_zone_exists(zid, display_name=zname)
                    print(f"{GREEN}[OK] Dynamically created spatial zone '{zid}' ('{zname}')!{RESET}")
                else:
                    print(f"{RED}[-] Usage: zone add <zone_id> [display_name]{RESET}")

            elif cmd_lower == "devices":
                devs = state.list_all_devices()
                print(f"\n{BRIGHT}--- Connected & Enrolled Devices ({len(devs)}) ---{RESET}")
                if not devs:
                    print("  No devices enrolled yet. Run 'python -m interfaces.install.enroll' to add one.")
                for d in devs:
                    tier_col = GREEN if d.trust_tier == "owner" else (YELLOW if d.trust_tier == "ambient" else RED)
                    anchor_str = "Fixed Anchor" if d.is_fixed_anchor else "Roaming"
                    print(f"  • {BRIGHT}{d.device_id:<22}{RESET} [{tier_col}{d.trust_tier.upper():<7}{RESET}] ({anchor_str}) Zone: {YELLOW}{d.current_zone}{RESET}")
                print()

            elif cmd_lower == "tools":
                catalog = registry.get_tool_catalog()
                print(f"\n{BRIGHT}--- Available Tool Catalog ({len(catalog)}) ---{RESET}")
                for t in catalog:
                    dyn_str = f"{CYAN}[DYNAMIC]{RESET}" if t.get("is_dynamic") else f"{GREEN}[NATIVE]{RESET}"
                    print(f"  • {dyn_str} {BRIGHT}{t['name']:<24}{RESET}: {t['description']}")
                print()

            elif cmd_lower.startswith("hud"):
                payload_text = user_input[3:].strip()
                if "|" in payload_text:
                    title, body = [p.strip() for p in payload_text.split("|", 1)]
                else:
                    title, body = "Operator Message", payload_text

                card = HUDCardPayload(
                    title=title,
                    subtitle=body,
                    metrics={"SENDER": active_name, "ZONE": active_zone}
                )
                asyncio.run(connection_manager.broadcast_event("HUD_CARD", card.model_dump()))
                print(f"{GREEN}[OK] Ambient HUD card dispatched to Smart Mirror & Projectors!{RESET}")

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

            else:
                # Treat as problem / goal solving query
                goal = user_input
                if cmd_lower.startswith("solve "):
                    goal = user_input[6:].strip()

                print(f"\n{CYAN}[*] Decomposing goal with Planner:{RESET} '{goal}'")
                plan = planner.plan_problem(goal, context={"zone": active_zone, "operator": active_name})
                
                print(f"{CYAN}[+] Synthesized Pipeline DAG:{RESET} {len(plan.steps)} steps (ID: {plan.id[:8]})")
                for s in plan.steps:
                    dep_str = f"(depends on: {', '.join(s.depends_on)})" if s.depends_on else "(independent)"
                    print(f"    - Step '{s.id}': {s.name} -> tool '{s.tool_name}' {dep_str}")

                print(f"\n{YELLOW}[*] Executing pipeline concurrently...{RESET}")
                start_time = time.time()
                finished_plan = asyncio.run(engine.execute_pipeline(plan))
                elapsed = time.time() - start_time

                if finished_plan.status == "completed":
                    print(f"\n{GREEN}[✓] Pipeline Succeeded in {elapsed:.2f}s!{RESET}")
                    print(f"{BRIGHT}Final Result:{RESET} {finished_plan.final_output}\n")
                else:
                    print(f"\n{RED}[✗] Pipeline Failed in {elapsed:.2f}s!{RESET}")
                    print(f"{RED}Error Summary:{RESET} {finished_plan.error_summary}\n")

        except KeyboardInterrupt:
            print(f"\n{YELLOW}[*] Session interrupted. Exiting...{RESET}")
            break
        except Exception as e:
            print(f"{RED}[-] Error: {e}{RESET}")

if __name__ == "__main__":
    main()
