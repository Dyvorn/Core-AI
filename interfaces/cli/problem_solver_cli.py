import asyncio
import os
import sys

# Ensure workspace root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from core.logging_setup import setup_logging
from core.state import StateManager
from core.bus import EventBus
from core.schemas import PipelinePlan, PipelineStep
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema, get_system_status
from tools.native.home_assistant import HomeAssistantMock, ha_call_schema
from tools.native.file_tools import read_text_file, read_file_schema, write_text_file, write_file_schema, list_dir_contents, list_dir_schema
from tools.native.math_tools import calculate_math, calculate_math_schema, summarize_numbers, summarize_numbers_schema
from brain.dynamic_generator import DynamicGenerator
from brain.pipeline_engine import PipelineEngine
from brain.planner import Planner

def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    # Register Native Tools
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("get_system_status", get_system_status, {
        "name": "get_system_status",
        "description": "Fetch current operating system and platform status",
        "parameters": {"type": "object", "properties": {}}
    })
    ha = HomeAssistantMock("http://localhost:8123", "mock_token")
    registry.register_tool("home_assistant_call", ha.call_service, ha_call_schema)
    registry.register_tool("read_text_file", read_text_file, read_file_schema)
    registry.register_tool("write_text_file", write_text_file, write_file_schema)
    registry.register_tool("list_dir_contents", list_dir_contents, list_dir_schema)
    registry.register_tool("calculate_math", calculate_math, calculate_math_schema)
    registry.register_tool("summarize_numbers", summarize_numbers, summarize_numbers_schema)
    
    # Auto-discover any existing dynamic tools
    registry.discover_dynamic_tools()
    return registry

async def run_autonomous_solver():
    setup_logging()
    print("=" * 70)
    print("[*] CORE AI - AUTONOMOUS PROBLEM SOLVER & DYNAMIC TOOL ENGINE")
    print("=" * 70)

    state = StateManager()
    bus = EventBus()
    bus.start_listening()
    registry = build_tool_registry()
    
    dyn_gen = DynamicGenerator(registry=registry, state_manager=state)
    planner = Planner(registry=registry, state_manager=state, dynamic_generator=dyn_gen)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)

    print(f"\n[+] [1. TOOL INTROSPECTION] Active Tools ({len(registry.tools)}):")
    for name in registry.tools:
        meta = registry.metadata[name]
        dyn_marker = "[DYNAMIC]" if meta["is_dynamic"] else "[NATIVE]"
        print(f"  {dyn_marker:<9} {name:<22}: {meta['description']}")

    # Demo 1: Multi-step Concurrent Pipeline ("multiple things at once")
    print("\n" + "=" * 70)
    print("[*] DEMO 1: Concurrency - Parallel Multi-Step Execution")
    print("Goal: 'Perform system health diagnostics (fetch time and OS status in parallel)'")
    print("=" * 70)
    
    plan1 = planner.plan_problem("fetch system status and time overview")
    print(f"Generated Pipeline: {len(plan1.steps)} steps (Dependencies: {[s.depends_on for s in plan1.steps]})")
    finished_plan1 = await engine.execute_pipeline(plan1)
    print(f"[OK] Pipeline 1 Result: Status={finished_plan1.status}")
    for s in finished_plan1.steps:
        print(f"   - Step '{s.id}' output: {s.output} ({s.duration_ms:.2f}ms)")

    # Demo 2: Missing Tool Detection, Dynamic Synthesis, AST Validation & Persistence
    print("\n" + "=" * 70)
    print("[*] DEMO 2: Self-Extension - Missing Tool Synthesis & Immediate Use")
    print("Goal: 'Compute cryptographic sha256 hash of secret string'")
    print("=" * 70)

    plan2 = planner.plan_problem("hash the text 'CoreAI_Autonomous_Token_2026'")
    print(f"Pipeline created using tool '{plan2.steps[0].tool_name}'.")
    finished_plan2 = await engine.execute_pipeline(plan2)
    print(f"[OK] Pipeline 2 Result: Status={finished_plan2.status}")
    print(f"   - Step output: {finished_plan2.final_output}")

    # Demo 3: Variable Resolution between Steps
    print("\n" + "=" * 70)
    print("[*] DEMO 3: Dynamic Variable Piping Between Steps")
    print("Goal: Step 1 computes math -> Step 2 writes result to a file")
    print("=" * 70)

    pipe_plan3 = PipelinePlan(
        goal="Calculate computation and save to disk",
        steps=[
            PipelineStep(
                id="math_step",
                name="Evaluate complex calculation",
                tool_name="calculate_math",
                arguments={"expression": "128 * 64 + sqrt(256)"},
                depends_on=[]
            ),
            PipelineStep(
                id="save_step",
                name="Save computation result to file",
                tool_name="write_text_file",
                arguments={
                    "file_path": "logs/computation_output.txt",
                    "content": "Computation Result: {{steps.math_step.output.result}}"
                },
                depends_on=["math_step"]
            )
        ]
    )
    finished_plan3 = await engine.execute_pipeline(pipe_plan3)
    print(f"[OK] Pipeline 3 Result: Status={finished_plan3.status}")
    print(f"   - Saved output: {finished_plan3.final_output}")

    # Demo 4: Jarvis-like Failure Awareness
    print("\n" + "=" * 70)
    print("[*] DEMO 4: Failure Awareness & Diagnostics (Intentional invalid tool call)")
    print("=" * 70)
    fail_plan = PipelinePlan(
        goal="Attempt invalid file read",
        steps=[
            PipelineStep(
                id="bad_read",
                name="Read non-existent file",
                tool_name="read_text_file",
                arguments={"file_path": "non_existent_directory_999/does_not_exist.txt"},
                max_retries=1
            )
        ]
    )
    finished_fail = await engine.execute_pipeline(fail_plan)
    print(f"[WARN] Pipeline 4 Failure Handled: Status={finished_fail.status}")
    print(f"   - Error summary: {finished_fail.error_summary}")

    print("\n" + "=" * 70)
    print("[DONE] ALL DEMOS COMPLETED SUCCESSFULLY. Log files written to logs/core_ai.log & logs/pipelines.jsonl")
    print("=" * 70)


    bus.stop_listening()

if __name__ == "__main__":
    asyncio.run(run_autonomous_solver())
