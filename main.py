import os
import sys
import time
import asyncio
import logging
import threading
import uvicorn
from dotenv import load_dotenv

from core.logging_setup import setup_logging
from core.bus import EventBus
from core.schemas import TextEvent, CommandEvent, AdaptiveResponseEvent
from core.context import ContextManager
from core.state import StateManager
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema, get_system_status
from tools.native.home_assistant import HomeAssistantMock, ha_call_schema
from tools.native.file_tools import read_text_file, read_file_schema, write_text_file, write_file_schema, list_dir_contents, list_dir_schema
from tools.native.math_tools import calculate_math, calculate_math_schema, summarize_numbers, summarize_numbers_schema
from tools.remote_dispatcher import RemoteToolDispatcher
from brain.dynamic_generator import DynamicGenerator
from brain.pipeline_engine import PipelineEngine
from brain.planner import Planner
from brain.proactive import ProactiveDaemon
from core.gateway import create_gateway_app

logger = logging.getLogger("CoreAI.Main")

def setup_tools() -> ToolRegistry:
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    
    # Register Native Tools
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("get_system_status", get_system_status, {
        "name": "get_system_status",
        "description": "Get current operating system, distribution, and hardware architecture status",
        "parameters": {"type": "object", "properties": {}}
    })
    
    ha_url = os.getenv("HA_URL", "http://localhost:8123")
    ha_token = os.getenv("HA_TOKEN", "mock_token")
    ha = HomeAssistantMock(ha_url, ha_token)
    registry.register_tool("home_assistant_call", ha.call_service, ha_call_schema)
    
    registry.register_tool("read_text_file", read_text_file, read_file_schema)
    registry.register_tool("write_text_file", write_text_file, write_file_schema)
    registry.register_tool("list_dir_contents", list_dir_contents, list_dir_schema)
    registry.register_tool("calculate_math", calculate_math, calculate_math_schema)
    registry.register_tool("summarize_numbers", summarize_numbers, summarize_numbers_schema)
    
    # Auto-discover any existing dynamic tools
    registry.discover_dynamic_tools()
    return registry

def main():
    setup_logging()
    load_dotenv("config/.env")
    
    logger.info("Initializing Core AI Microkernel with Universal Gateway & Proactive Engine...")
    
    # 1. Init Core Services & State
    bus = EventBus()
    state = StateManager()
    context = ContextManager()
    registry = setup_tools()
    
    # 2. Remote Edge Dispatcher (for physical car, phone, glasses tools)
    remote_dispatcher = RemoteToolDispatcher(registry=registry)
    
    # 3. Brain Services
    dyn_gen = DynamicGenerator(registry=registry, state_manager=state)
    planner = Planner(registry=registry, state_manager=state, dynamic_generator=dyn_gen)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)
    
    # 4. Proactive Watcher Daemon
    proactive = ProactiveDaemon(
        state_manager=state,
        planner=planner,
        pipeline_engine=engine,
        bus=bus,
        check_interval_seconds=4.0
    )
    
    # 5. Create Universal Gateway FastAPI App
    gateway_app = create_gateway_app(
        state_manager=state,
        registry=registry,
        planner=planner,
        pipeline_engine=engine,
        bus=bus
    )
    
    # Event Handlers
    def handle_text_event(data: dict):
        try:
            event = TextEvent(**data)
            logger.info(f"Received text event from {event.get_effective_zone()}: {event.text}")
            
            # Check for name change command
            text_lower = event.text.lower()
            if "call me" in text_lower or "name is" in text_lower or "nenne mich" in text_lower:
                parts = event.text.split()
                new_name = parts[-1].strip("!?. ")
                state.set_user_preferred_name(new_name)
                logger.info(f"Updated user preferred name to: {new_name}")
            
            room_context = {"zone": event.get_effective_zone(), "device_type": event.get_device_type()}
            plan = planner.plan_problem(event.text, room_context)
            
            finished_plan = asyncio.run(engine.execute_pipeline(plan))
            
            profile = state.get_user_profile()
            if finished_plan.status == "completed":
                response_text = f"Hey {profile.preferred_name}, Aktion abgeschlossen: {finished_plan.final_output}"
            else:
                response_text = f"Hey {profile.preferred_name}, die Aktion konnte nicht vollständig ausgeführt werden: {finished_plan.error_summary}"
                
            bus.publish("tts_events", TextEvent(
                source_node="brain",
                room_id=event.get_effective_zone(),
                text=response_text
            ))
            logger.info(f"Published response: {response_text}")
                
        except Exception as e:
            logger.error(f"Error handling text event: {e}", exc_info=True)

    # Subscribe to event bus
    bus.subscribe("text_events", handle_text_event)
    bus.start_listening()
    
    # Start Proactive Daemon
    proactive.start()

    # Launch Gateway Web & WebSocket Server
    host = os.getenv("CORE_HOST", "0.0.0.0")
    port = int(os.getenv("CORE_PORT", 8000))
    
    logger.info(f"Starting Core AI Gateway on http://{host}:{port} (Mirror: http://localhost:{port}/mirror, Docs: http://localhost:{port}/docs)")
    
    try:
        uvicorn.run(gateway_app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        proactive.stop()
        bus.stop_listening()

if __name__ == "__main__":
    main()
