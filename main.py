import os
import sys
import time
import asyncio
import logging
import argparse
import threading
import uvicorn
from typing import Optional
from dotenv import load_dotenv

from core.logging_setup import setup_logging
from core.bus import EventBus
from core.schemas import TextEvent, CommandEvent, AdaptiveResponseEvent, TTSRequestEvent
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
from core.gateway import create_gateway_app, connection_manager
from engines.voice_in import VoiceInEngine
from engines.voice_out import VoiceOutEngine
from brain.spoken_to import SpokenToReasoning, DiscourseRole

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

def parse_args():
    parser = argparse.ArgumentParser(description="Core AI Sovereign Life OS Microkernel")
    parser.add_argument("--voice", action="store_true", help="Enable full continuous voice loop (Mic STT + Speaker TTS)")
    parser.add_argument("--voice-in", action="store_true", help="Enable background microphone listening only")
    parser.add_argument("--no-tts", action="store_true", help="Disable audio speech output")
    parser.add_argument("--model-size", default="distil-large-v3", help="faster-whisper model size (distil-large-v3, base, small, tiny)")
    parser.add_argument("--device", default=None, help="Audio input/output device index or name substring")
    parser.add_argument("--host", default=None, help="Gateway host binding (defaults to CORE_HOST or 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="Gateway port (defaults to CORE_PORT or 8000)")
    return parser.parse_args()

def main():
    setup_logging()
    load_dotenv("config/.env")
    args = parse_args()
    
    logger.info("Initializing Core AI Microkernel with Universal Gateway, Proactive Engine & Voice Loop...")
    
    # 1. Init Core Services & State
    bus = EventBus()
    state = StateManager()
    context = ContextManager()
    registry = setup_tools()
    profile = state.get_user_profile()
    operator_name = profile.preferred_name
    primary_zone = profile.preferences.get("primary_space", "studio")
    state.ensure_zone_exists(primary_zone, display_name=f"{operator_name}'s Primary Zone")
    
    # 2. Remote Edge Dispatcher (for physical car, phone, glasses tools)
    remote_dispatcher = RemoteToolDispatcher(registry=registry)
    
    # 3. Brain Services
    dyn_gen = DynamicGenerator(registry=registry, state_manager=state)
    planner = Planner(registry=registry, state_manager=state, dynamic_generator=dyn_gen)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)
    spoken_to = SpokenToReasoning(state_manager=state, registry=registry, planner=planner)
    
    # 4. Proactive Watcher Daemon
    proactive = ProactiveDaemon(
        state_manager=state,
        planner=planner,
        pipeline_engine=engine,
        bus=bus,
        check_interval_seconds=4.0
    )
    
    # 5. Voice Out Engine (Text-to-Speech)
    voice_out: Optional[VoiceOutEngine] = None
    if not args.no_tts:
        voice_out = VoiceOutEngine(default_voice="auto", output_device=args.device)
        voice_out.attach_to_bus(bus, channel="tts_events")
        logger.info("VoiceOutEngine online with Edge Neural TTS & pyttsx3 fallback.")

    # 6. Universal Gateway App
    gateway_app = create_gateway_app(
        state_manager=state,
        registry=registry,
        planner=planner,
        pipeline_engine=engine,
        bus=bus
    )
    
    # Broadcast voice state helper
    def broadcast_voice_state(state_name: str, extra: dict = None):
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

            # 1. Spoken-To Reasoning: Cognitive Addressee & Intent Analysis
            decision = spoken_to.evaluate(event.text, profile=current_profile)
            logger.info(
                f"[Spoken-To Reasoning] Role: {decision.discourse_role.value} | "
                f"Action: {decision.action_type} | Respond: {decision.should_respond} | "
                f"Rationale: {decision.rationale}"
            )

            # A. If operator is talking ABOUT Core AI or in ambient side-talk, stay completely silent
            if not decision.should_respond:
                logger.info(f"[Spoken-To] Silently ignored non-addressed utterance: '{event.text}'")
                return

            # B. If operator is SHOWCASING / demonstrating Core AI to someone else, chime in charismatically!
            if decision.discourse_role == DiscourseRole.DEMONSTRATED and decision.autonomous_response:
                logger.info(f"[Spoken-To Showcase Chime-In]: '{decision.autonomous_response}'")
                bus.publish("tts_events", TTSRequestEvent(
                    source_node="brain",
                    room_id=effective_zone,
                    text=decision.autonomous_response
                ))
                asyncio.run(connection_manager.broadcast_event("hud_card", {
                    "title": f"Core AI — Live Showcase",
                    "body": decision.autonomous_response,
                    "accent_color": "#ffaa00",
                    "zone": effective_zone
                }))
                broadcast_voice_state("idle", {"zone": effective_zone})
                return

            # C. Direct command: use clean command stripped of vocatives
            command_text = decision.clean_command or event.text
            
            # Check for name change command
            text_lower = command_text.lower()
            if any(k in text_lower for k in ["call me", "name is", "nenne mich", "mein name ist"]):
                parts = command_text.split()
                new_name = parts[-1].strip("!?. ")
                if len(new_name) > 1:
                    state.set_user_preferred_name(new_name)
                    logger.info(f"Updated user preferred name to: {new_name}")
            
            # Broadcast 'thinking' status
            broadcast_voice_state("thinking", {"query": command_text, "zone": effective_zone})

            room_context = {"zone": effective_zone, "device_type": event.get_device_type()}
            
            # 2. Plan DAG problem
            plan = planner.plan_problem(command_text, room_context)
            
            # 3. Execute pipeline
            finished_plan = asyncio.run(engine.execute_pipeline(plan))
            
            # 4. Formulate natural conversational spoken response
            response_text = planner.formulate_spoken_response(finished_plan, profile=current_profile)
            
            # 5. Dispatch to TTS audio channel
            bus.publish("tts_events", TTSRequestEvent(
                source_node="brain",
                room_id=effective_zone,
                text=response_text
            ))
            logger.info(f"Dispatched spoken response to '{effective_zone}': {response_text}")

            # 6. Broadcast HUD update to smart mirrors / web dashboards
            asyncio.run(connection_manager.broadcast_event("hud_card", {
                "title": f"Core AI — {current_profile.preferred_name}",
                "body": response_text,
                "accent_color": "#00ffcc" if finished_plan.status == "completed" else "#ff3366",
                "zone": effective_zone
            }))
            
            broadcast_voice_state("idle", {"zone": effective_zone})
                
        except Exception as e:
            logger.error(f"Error handling text event: {e}", exc_info=True)
            broadcast_voice_state("idle", {"error": str(e)})

    # Subscribe to central event bus
    bus.subscribe("text_events", handle_text_event)
    bus.start_listening()
    
    # Start Proactive Daemon
    proactive.start()

    # 7. Voice In Engine (Microphone Capture & STT)
    voice_in: Optional[VoiceInEngine] = None
    if args.voice or args.voice_in:
        try:
            logger.info(f"Starting VoiceInEngine with model '{args.model_size}'...")
            voice_in = VoiceInEngine(
                model_size=args.model_size,
                input_device=args.device
            )
            voice_in.bridge_to_event_bus(
                bus=bus,
                zone=primary_zone,
                device_type="mic",
                state_callback=lambda st: broadcast_voice_state(st, {"zone": primary_zone})
            )
            logger.info(f"Voice capture active in primary zone: '{primary_zone}'. Speak anytime!")
        except Exception as e:
            logger.error(f"Failed to start VoiceInEngine ({e}). Core AI will continue in text/API mode.")

    # Launch Gateway Web & WebSocket Server
    host = args.host or os.getenv("CORE_HOST", "0.0.0.0")
    port = args.port or int(os.getenv("CORE_PORT", 8000))
    
    logger.info(f"Starting Core AI Gateway on http://{host}:{port}")
    logger.info(f" -> Roadmap Dashboard: http://localhost:{port}/roadmap")
    logger.info(f" -> Smart Mirror HUD:  http://localhost:{port}/mirror")
    logger.info(f" -> Swagger API Docs:  http://localhost:{port}/docs")
    if voice_in and voice_in.is_recording:
        logger.info(f" 🎙️ Live Voice Loop: ACTIVE (Speak into your microphone!)")
    
    try:
        uvicorn.run(gateway_app, host=host, port=port, log_level="info")
    except KeyboardInterrupt:
        logger.info("Shutdown requested by operator...")
    finally:
        logger.info("Stopping all background services cleanly...")
        if voice_in:
            voice_in.stop_listening()
        if voice_out:
            voice_out.stop()
        proactive.stop()
        bus.stop_listening()
        logger.info("Core AI shutdown complete.")

if __name__ == "__main__":
    main()
