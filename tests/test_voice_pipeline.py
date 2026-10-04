import pytest
import asyncio
import time
import numpy as np
from unittest.mock import MagicMock, patch

from core.bus import EventBus
from core.schemas import TextEvent, SpatialContext, PipelinePlan, PipelineStep, UserProfile, TTSRequestEvent
from core.state import StateManager
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema, get_system_status
from tools.native.math_tools import calculate_math, calculate_math_schema
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from engines.voice_in import VoiceInEngine
from engines.voice_out import VoiceOutEngine


def test_voice_in_hardware_detection():
    """Verify hardware detection cleanly selects CPU and int8 when CUDA is absent."""
    engine = VoiceInEngine(model_size="tiny", device="auto", compute_type="default")
    assert engine.device == "cpu"
    assert engine.compute_type == "int8"
    assert engine.current_state == "idle"
    devices = engine.list_input_devices()
    assert isinstance(devices, list)


def test_voice_in_hallucination_suppression():
    """Verify whisper hallucination filter catches noise artifacts and allows valid speech."""
    engine = VoiceInEngine(model_size="tiny")
    
    # Noise and artifacts to suppress
    assert engine.is_hallucination("")
    assert engine.is_hallucination("   ")
    assert engine.is_hallucination("...")
    assert engine.is_hallucination("you")
    assert engine.is_hallucination("[music]")
    assert engine.is_hallucination("(applause)")
    assert engine.is_hallucination("thank you for watching")
    assert engine.is_hallucination("vielen dank fürs zuschauen")
    assert engine.is_hallucination("aaaaaa")

    # Legitimate operator speech that must NOT be filtered
    assert not engine.is_hallucination("wie spät ist es")
    assert not engine.is_hallucination("system status")
    assert not engine.is_hallucination("calculate 12 * 8")
    assert not engine.is_hallucination("schalte das licht an")


def test_voice_out_language_detection():
    """Verify natural language detection and neural voice selection."""
    engine = VoiceOutEngine(default_voice="auto")
    try:
        assert engine.detect_language("Wie spät ist es gerade?") == "de"
        assert engine.detect_language("Hallo Dyvorn, das System läuft stabil.") == "de"
        assert engine.detect_language("What is the current system status?") == "en"
        assert engine.detect_language("Calculate math expression.") == "en"

        de_voice = engine.select_voice("Hallo Dyvorn")
        en_voice = engine.select_voice("Hello world")
        assert "de-DE" in de_voice
        assert "en-US" in en_voice
    finally:
        engine.stop()


def test_voice_out_edge_tts_synthesis():
    """Verify Edge-TTS synthesizes neural speech into an in-memory audio buffer."""
    engine = VoiceOutEngine(default_voice="auto")
    try:
        async def run_synth():
            return await engine._synthesize_edge_tts("Test", "en-US-ChristopherNeural")

        samples, sample_rate = asyncio.run(run_synth())
        assert isinstance(samples, np.ndarray)
        assert sample_rate > 0
        assert len(samples) > 0
    finally:
        engine.stop()


def test_planner_spoken_formulation():
    """Verify conversational spoken response formulation for various tools."""
    registry = ToolRegistry()
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("calculate_math", calculate_math, calculate_math_schema)
    
    planner = Planner(registry=registry)
    profile = UserProfile(preferred_name="Dyvorn")

    # 1. Time Plan
    time_plan = PipelinePlan(
        goal="wie spät ist es",
        steps=[PipelineStep(
            id="time_step",
            name="Get Time",
            tool_name="get_time",
            status="completed",
            output="17:45"
        )],
        status="completed",
        final_output="17:45"
    )
    spoken_time = planner.formulate_spoken_response(time_plan, profile=profile, language="de")
    assert "17:45" in spoken_time
    assert "Dyvorn" in spoken_time
    assert "Uhr" in spoken_time

    # 2. Math Plan
    math_plan = PipelinePlan(
        goal="berechne 25 * 4",
        steps=[PipelineStep(
            id="math_step",
            name="Calc",
            tool_name="calculate_math",
            status="completed",
            output={"status": "success", "expression": "25 * 4", "result": 100}
        )],
        status="completed",
        final_output={"status": "success", "expression": "25 * 4", "result": 100}
    )
    spoken_math = planner.formulate_spoken_response(math_plan, profile=profile, language="de")
    assert "100" in spoken_math
    assert "Dyvorn" in spoken_math

    # 3. Failed Plan
    failed_plan = PipelinePlan(
        goal="do something broken",
        steps=[],
        status="failed",
        error_summary="Tool not found"
    )
    spoken_fail = planner.formulate_spoken_response(failed_plan, profile=profile, language="de")
    assert "leider nicht" in spoken_fail
    assert "Tool not found" in spoken_fail


def test_end_to_end_voice_loop(tmp_path):
    """
    Test closed-loop voice pipeline:
    Mic TextEvent -> EventBus -> Planner DAG -> PipelineEngine -> Spoken Response -> TTS Event
    """
    bus = EventBus()
    state_file = str(tmp_path / "test_voice.db")
    state = StateManager(db_path=state_file)
    registry = ToolRegistry()
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("get_system_status", get_system_status, {
        "name": "get_system_status",
        "description": "System status",
        "parameters": {"type": "object", "properties": {}}
    })

    planner = Planner(registry=registry, state_manager=state)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)
    profile = state.get_user_profile()

    received_tts_events = []

    def on_tts(data: dict):
        received_tts_events.append(data)

    bus.subscribe("tts_events", on_tts)
    bus.start_listening()

    # Define the text event handler exactly as in main.py
    def handle_text_event(data: dict):
        event = TextEvent(**data)
        room_context = {"zone": event.get_effective_zone(), "device_type": event.get_device_type()}
        plan = planner.plan_problem(event.text, room_context)
        finished_plan = asyncio.run(engine.execute_pipeline(plan))
        response_text = planner.formulate_spoken_response(finished_plan, profile=profile)
        bus.publish("tts_events", TTSRequestEvent(
            source_node="brain",
            room_id=event.get_effective_zone(),
            text=response_text
        ))

    bus.subscribe("text_events", handle_text_event)

    try:
        # Simulate voice capture emitting a TextEvent from the studio mic
        simulated_voice_event = TextEvent(
            source_node="local_mic",
            room_id="studio",
            spatial_context=SpatialContext(zone="studio", device_type="mic"),
            text="wie spät ist es"
        )
        bus.publish("text_events", simulated_voice_event)

        # Wait for in-memory pubsub processing
        for _ in range(80):
            if received_tts_events:
                break
            time.sleep(0.1)

        assert len(received_tts_events) > 0
        tts_payload = received_tts_events[0]
        assert "text" in tts_payload
        assert "Uhr" in tts_payload["text"]
        assert tts_payload["room_id"] == "studio"

    finally:
        bus.stop_listening()
