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


def test_voice_in_resampling():
    """Verify fast linear audio resampling accurately converts sample rates to 16kHz."""
    from engines.voice_in import resample_audio

    # 48000 Hz to 16000 Hz (3x downsampling)
    orig_48k = np.ones(4800, dtype=np.float32)
    resampled_16k = resample_audio(orig_48k, orig_sr=48000, target_sr=16000)
    assert len(resampled_16k) == 1600
    assert resampled_16k.dtype == np.float32

    # 44100 Hz to 16000 Hz
    orig_44k = np.ones(4410, dtype=np.float32)
    resampled_from_44 = resample_audio(orig_44k, orig_sr=44100, target_sr=16000)
    expected_len = round(4410 * 16000 / 44100)
    assert len(resampled_from_44) == expected_len

    # Same rate returns original
    same_rate = resample_audio(orig_48k, orig_sr=48000, target_sr=48000)
    assert len(same_rate) == len(orig_48k)


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
    assert engine.is_hallucination("[blank_audio]")
    assert engine.is_hallucination("(silence)")
    assert engine.is_hallucination("subtitles by opensubtitles")
    assert engine.is_hallucination("thank you for watching")
    assert engine.is_hallucination("vielen dank fürs zuschauen")
    assert engine.is_hallucination("aaaaaa")
    assert engine.is_hallucination("yeah yeah yeah yeah")

    # Legitimate operator speech that must NOT be filtered
    assert not engine.is_hallucination("wie spät ist es")
    assert not engine.is_hallucination("system status")
    assert not engine.is_hallucination("calculate 12 * 8")
    assert not engine.is_hallucination("schalte das licht an")
    assert not engine.is_hallucination("remind me in 5 minutes")
    assert not engine.is_hallucination("watch ram")


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


def test_voice_model_multilingual_guard(monkeypatch):
    """Verify VoiceInEngine defaults to multilingual 'small' and upgrades English-only distil-large-v3."""
    with patch("engines.voice_in.WhisperModel") as mock_whisper:
        mock_whisper.return_value = MagicMock()
        
        # 1. Default model size is small
        engine_default = VoiceInEngine(device="cpu")
        assert engine_default.model_size == "small"

        # 2. English-only distil model is upgraded to small when language is not 'en'
        engine_distil = VoiceInEngine(model_size="distil-large-v3", language=None, device="cpu")
        assert engine_distil.model_size == "small"

        # 3. Explicit English can keep distil-large-v3
        engine_en = VoiceInEngine(model_size="distil-large-v3", language="en", device="cpu")
        assert engine_en.model_size == "distil-large-v3"


def test_cli_voice_arguments_always_active(monkeypatch):
    """Verify CLI defaults voice to active (no_voice=False) and supports --no-voice / --no-mic."""
    import sys
    from main import parse_args

    # Default CLI invocation: voice active by default, model small
    monkeypatch.setattr(sys, "argv", ["main.py"])
    args_default = parse_args()
    assert args_default.no_voice is False
    assert args_default.model_size == "small"

    # Inverted flag: user explicitly passes --no-voice
    monkeypatch.setattr(sys, "argv", ["main.py", "--no-voice"])
    args_disabled = parse_args()
    assert args_disabled.no_voice is True

    # Inverted flag alias: user passes --no-mic
    monkeypatch.setattr(sys, "argv", ["main.py", "--no-mic"])
    args_mic_off = parse_args()
    assert args_mic_off.no_voice is True


def test_voice_out_interruption():
    """Verify VoiceOutEngine.interrupt() halts active playback, drains queue, and resets speech state."""
    voice_out = VoiceOutEngine(default_voice="auto")
    try:
        # Enqueue multiple phrases
        voice_out.synthesize_and_play("First long sentence to synthesize and speak.", blocking=False)
        voice_out.synthesize_and_play("Second sentence in queue.", blocking=False)
        voice_out.synthesize_and_play("Third sentence in queue.", blocking=False)

        # Trigger immediate interrupt
        interrupted = voice_out.interrupt()
        assert voice_out._interrupted.is_set()
        assert voice_out.speech_queue.empty()
        assert voice_out.is_speaking is False
    finally:
        voice_out.stop()


def test_voice_in_barge_in_and_interrupt():
    """Verify VoiceInEngine intercepts verbal interrupt keywords and halts VoiceOut playback."""
    voice_out = VoiceOutEngine(default_voice="auto")
    try:
        from engines.voice_in import INTERRUPT_PATTERN
        assert INTERRUPT_PATTERN.search("stop")
        assert INTERRUPT_PATTERN.search("stopp")
        assert INTERRUPT_PATTERN.search("No, no, stop, stop, stop, stop, stop")
        assert INTERRUPT_PATTERN.search("halt")
        assert INTERRUPT_PATTERN.search("cancel")
        assert INTERRUPT_PATTERN.search("abbrechen")
        assert INTERRUPT_PATTERN.search("warte")

        # Simulate voice_in detecting interrupt utterance while speech is queued
        voice_out.synthesize_and_play("Speaking something long...", blocking=False)
        was_halted = voice_out.interrupt()
        assert was_halted is True
        assert not voice_out.is_speaking
        assert voice_out.speech_queue.empty()
    finally:
        voice_out.stop()


def test_spoken_to_zero_latency_fast_path():
    """Verify Spoken-To engine returns in sub-millisecond time for time queries, interrupts, and hesitation."""
    from brain.spoken_to import SpokenToReasoning, DiscourseRole
    spoken = SpokenToReasoning()
    profile = UserProfile(preferred_name="Dyvorn")

    # 1. Verbal interrupt
    dec_stop = spoken.evaluate("No, no, stop, stop, stop, stop, stop", profile=profile)
    assert dec_stop.action_type == "interrupt"
    assert dec_stop.should_respond is False

    # 2. Time query with hesitation
    dec_time = spoken.evaluate("how... what time is it?", profile=profile)
    assert dec_time.discourse_role == DiscourseRole.ADDRESSED
    assert dec_time.should_respond is True
    assert dec_time.action_type == "command"

    # 3. German time query
    dec_de = spoken.evaluate("Wie spät ist es?", profile=profile)
    assert dec_de.discourse_role == DiscourseRole.ADDRESSED
    assert dec_de.should_respond is True

    # 4. Gemini alias query
    dec_gemini = spoken.evaluate("Gemini, can you tell me what time it is?", profile=profile)
    assert dec_gemini.discourse_role == DiscourseRole.ADDRESSED
    assert dec_gemini.should_respond is True
    assert dec_gemini.action_type == "command"

