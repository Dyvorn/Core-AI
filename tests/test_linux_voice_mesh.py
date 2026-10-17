"""
Core AI :: Automated Tests for Linux Terminal Alignment, Voice Satellites & Distributed Perception
"""

import os
from starlette.testclient import TestClient
from core.terminal import render_box, strip_ansi, make_readline_safe_prompt, visible_len
from core.state import StateManager


from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.bus import EventBus
from core.gateway import create_gateway_app


def test_strip_ansi_and_visible_len():
    """Verify ANSI escape codes are stripped accurately for visual length calculation."""
    colored_text = "\x1b[36mCore AI\x1b[0m \x1b[32m[ONLINE]\x1b[0m"
    assert strip_ansi(colored_text) == "Core AI [ONLINE]"
    assert visible_len(colored_text) == 16


def test_make_readline_safe_prompt():
    """Verify Readline prompt wrapping prevents cursor and backspace glitches."""
    raw_prompt = "\x1b[36mCore\x1b[0m [\x1b[32mLennard\x1b[0m] > "
    wrapped = make_readline_safe_prompt(raw_prompt)
    if os.name != "nt":
        # On POSIX, non-printing codes must be enclosed in \001 and \002
        assert "\001\x1b[36m\002" in wrapped
        assert "\001\x1b[0m\002" in wrapped
    else:
        # On Windows, returned unmodified
        assert wrapped == raw_prompt


def test_render_box_alignment():
    """Verify all rows in render_box have identical visual width with no crooked borders."""
    title = "SYSTEM TEST STATUS"
    rows = [
        ("Kernel Version:", "\x1b[32mv0.2.1-alpha\x1b[0m"),
        ("Active Operator:", "Lennard"),
        ("Mesh Server:", "http://192.168.2.203:8000")
    ]
    card = render_box(title=title, rows=rows, width=65)
    lines = card.strip().split("\n")
    assert len(lines) == 7  # top, title, div, 3 rows, bottom
    for line in lines:
        assert visible_len(line) == 65
        clean_line = strip_ansi(line)
        assert clean_line.startswith("+") or clean_line.startswith("|")
        assert clean_line.endswith("+") or clean_line.endswith("|")




def test_gateway_voice_transcription_endpoint(tmp_path):
    """Verify /api/v1/voice/transcription endpoint receives speech, executes DAG, and returns spoken output."""
    db_file = os.path.join(tmp_path, "gw_voice.db")
    sm = StateManager(db_path=db_file)
    reg = ToolRegistry()
    reg.register_tool("get_time", get_time, time_schema)
    bus = EventBus()
    planner = Planner(registry=reg, state_manager=sm)
    engine = PipelineEngine(registry=reg, state_manager=sm, bus=bus)

    app = create_gateway_app(
        state_manager=sm,
        registry=reg,
        planner=planner,
        pipeline_engine=engine,
        bus=bus
    )
    client = TestClient(app)

    # 1. Addressed query
    resp = client.post("/api/v1/voice/transcription", json={
        "utterance": "Core, what time is it?",
        "source_node": "office_satellite",
        "zone": "office"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["should_respond"] is True
    assert "spoken_response" in data
    assert len(data["spoken_response"]) > 0

    # 2. Ambient utterance not addressed to Core AI
    resp_ambient = client.post("/api/v1/voice/transcription", json={
        "utterance": "Pass me the butter please.",
        "source_node": "kitchen_satellite",
        "zone": "kitchen"
    })
    assert resp_ambient.status_code == 200
    data_ambient = resp_ambient.json()
    assert data_ambient["status"] == "ignored"
    assert data_ambient["should_respond"] is False

    # 3. Verbal interrupt
    resp_interrupt = client.post("/api/v1/voice/transcription", json={
        "utterance": "Stop",
        "source_node": "living_room_satellite",
        "zone": "living_room"
    })
    assert resp_interrupt.status_code == 200
    data_interrupt = resp_interrupt.json()
    assert data_interrupt["status"] == "interrupted"
    assert data_interrupt["should_respond"] is False
