"""
Core AI :: Automated Verification for v0.2.2-alpha
Tests:
- Distributed Voice Satellite telemetry, heartbeat registry, and remote speak dispatch
- Mobile Companion zero-friction enrollment (Owner / Guest trust tiers)
- Lock-screen glanceable telemetry & vitals stream
- Nothing OS Glyph Matrix pattern triggers (reasoning_pulse, success_flash, alert_burst)
- Mobile companion client and service status card integration
"""

import os
import time
import json
import pytest
from starlette.testclient import TestClient

from core.state import StateManager
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.bus import EventBus
from core.gateway import create_gateway_app, connection_manager
from core.schemas import TrustTier, GlyphPattern
from interfaces.voice.satellite import VoiceSatellite
from interfaces.mobile.companion import MobileCompanionClient
from core.service import ServiceManager


@pytest.fixture
def gateway_test_env(tmp_path):
    db_file = os.path.join(tmp_path, "test_v022.db")
    state = StateManager(db_path=db_file)
    profile = state.get_user_profile()
    profile.preferred_name = "Dyvorn"
    profile.preferences["primary_space"] = "studio"
    state.save_user_profile(profile)

    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    registry.register_tool("get_time", get_time, time_schema)
    bus = EventBus()
    planner = Planner(registry=registry, state_manager=state, model_name="heuristic")
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)

    app = create_gateway_app(
        state_manager=state,
        registry=registry,
        planner=planner,
        pipeline_engine=engine,
        bus=bus
    )
    client = TestClient(app)
    return client, state, app


def test_satellite_heartbeat_and_registry(gateway_test_env):
    """Verify satellite heartbeat reports and dynamic satellite tracking."""
    client, state, _ = gateway_test_env

    # 1. Send satellite heartbeat
    hb_payload = {
        "node_id": "living_room_satellite",
        "zone": "living_room",
        "mic_device": "Microphone Array",
        "speaker_device": "Studio Monitors",
        "model_size": "small",
        "status": "listening",
        "uptime_seconds": 120.5
    }
    resp = client.post("/api/v1/mesh/satellites/heartbeat", json=hb_payload)
    assert resp.status_code == 200
    hb_data = resp.json()
    assert hb_data["status"] == "acknowledged"
    assert hb_data["node_id"] == "living_room_satellite"

    # 2. Inspect registered satellites list
    list_resp = client.get("/api/v1/mesh/satellites")
    assert list_resp.status_code == 200
    satellites = list_resp.json()
    assert len(satellites) >= 1
    target = next((s for s in satellites if s["node_id"] == "living_room_satellite"), None)
    assert target is not None
    assert target["zone"] == "living_room"
    assert target["effective_status"] == "online"

    # 3. Health probe includes satellite metrics
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert h_data["active_satellites_count"] >= 1
    assert h_data["version"] == "0.2.2-alpha"


def test_satellite_speak_dispatch(gateway_test_env):
    """Verify central server can dispatch remote speech synthesis to a satellite."""
    client, _, _ = gateway_test_env

    speak_req = {
        "text": "The render pipeline has finished in the studio.",
        "voice": "auto",
        "priority": "normal"
    }
    resp = client.post("/api/v1/mesh/satellites/living_room_satellite/speak", json=speak_req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "dispatched"
    assert data["node_id"] == "living_room_satellite"
    assert "render pipeline" in data["text"]


def test_mobile_companion_enrollment(gateway_test_env):
    """Verify mobile companion onboarding with owner secret and guest tier."""
    client, state, _ = gateway_test_env

    # 1. Enroll as Owner with correct auth secret
    valid_secret = os.getenv("CORE_AUTH_SECRET", "core_sovereign_secret")
    owner_req = {
        "client_id": "phone_nothing_2",
        "device_name": "Dyvorn Phone (2)",
        "model": "Nothing Phone (2)",
        "os_version": "Nothing OS 2.6",
        "target_zone": "mobile/roaming",
        "auth_secret": valid_secret
    }
    resp1 = client.post("/api/v1/mobile/enroll", json=owner_req)
    assert resp1.status_code == 200
    res1 = resp1.json()
    assert res1["status"] == "enrolled"
    assert res1["assigned_tier"] == TrustTier.OWNER
    assert res1["token"].startswith("mob_")
    assert res1["operator_name"] == "Dyvorn"
    assert "/ws/mobile/phone_nothing_2" in res1["gateway_ws_url"]

    # Verify device record saved in SQLite
    dev = state.get_device_record("phone_nothing_2")
    assert dev is not None
    assert dev.name == "Dyvorn Phone (2)"
    assert dev.trust_tier == "owner"

    # 2. Enroll with incorrect secret -> Assigned Guest
    guest_req = {
        "client_id": "phone_guest_friend",
        "device_name": "Guest Pixel 8",
        "model": "Pixel 8",
        "auth_secret": "wrong_password_123"
    }
    resp2 = client.post("/api/v1/mobile/enroll", json=guest_req)
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["assigned_tier"] == TrustTier.GUEST


def test_mobile_companion_glance(gateway_test_env):
    """Verify mobile lock screen glance state returns accurate vitals and reminders."""
    client, state, _ = gateway_test_env

    # Add a sample countdown reminder rule
    from core.schemas import ProactiveTriggerRule
    rule = ProactiveTriggerRule(
        name="Review code PR",
        condition_type="countdown",
        trigger_condition={"target_timestamp_utc": "2026-10-12T20:00:00Z"},
        action_goal="system vitals"
    )
    state.save_proactive_rule(rule)

    resp = client.get("/api/v1/mobile/glance")
    assert resp.status_code == 200
    data = resp.json()
    assert data["operator_name"] == "Dyvorn"
    assert data["primary_space"] == "studio"
    assert "cpu_percent" in data["system_vitals"]
    assert any("Review code PR" in r.get("name", "") for r in data["unread_reminders"])
    assert data["version"] == "0.2.2-alpha"


def test_nothing_os_glyph_pattern_trigger(gateway_test_env):
    """Verify triggering Nothing OS Glyph LED matrix patterns."""
    client, _, _ = gateway_test_env

    glyph_req = {
        "pattern": "reasoning_pulse",
        "brightness": 200,
        "duration_ms": 600,
        "zone": "studio"
    }
    resp = client.post("/api/v1/mobile/glyph", json=glyph_req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "dispatched"
    assert data["pattern"] == "reasoning_pulse"
    assert data["brightness"] == 200
    assert data["duration_ms"] == 600


def test_voice_satellite_offline_transition(tmp_path):
    """Verify satellite unregistering / reporting offline status updates registry."""
    db_file = os.path.join(tmp_path, "sat_test.db")
    sm = StateManager(db_path=db_file)
    sat = VoiceSatellite(
        node_id="desk_mic",
        server_url="http://127.0.0.1:8000",
        zone="office",
        state_manager=sm
    )
    assert sat.node_id == "desk_mic"
    assert sat.zone == "office"
    # Stopping satellite sends offline heartbeat without crashing even if offline
    sat.stop()
    assert sat.is_running is False


def test_status_card_display_with_satellites(capsys):
    """Verify ServiceManager status card properly formats voice satellites."""
    sm = ServiceManager()
    # Mocking status output
    from unittest.mock import patch
    mock_status = {
        "is_running": True,
        "pid": 12345,
        "watchdog_pid": None,
        "watchdog_running": False,
        "gateway_healthy": True,
        "details": {
            "_active_port": 8000,
            "active_user": "Dyvorn",
            "active_model": "heuristic",
            "connected_edge_nodes": ["node_1"],
            "active_satellites_count": 2,
            "mobile_clients_count": 1
        }
    }
    with patch.object(sm, "status", return_value=mock_status):
        sm.print_status_card(port=8000)
        captured = capsys.readouterr()
        assert "Voice Satellites:" in captured.out
        assert "2 Active" in captured.out
        assert "Mobile Clients:" in captured.out
        assert "1 Active" in captured.out


def test_satellite_demonstration_chime_in(tmp_path):
    """Verify VoiceSatellite plays immediate autonomous chime-in during demonstrations."""
    db_file = os.path.join(tmp_path, "sat_chime.db")
    sm = StateManager(db_path=db_file)
    prof = sm.get_user_profile()
    prof.preferred_name = "Dyvorn"
    sm.save_user_profile(prof)

    sat = VoiceSatellite(
        node_id="chime_mic",
        server_url="http://127.0.0.1:8000",
        zone="studio",
        state_manager=sm
    )
    # Mock voice_out
    from unittest.mock import MagicMock
    mock_voice_out = MagicMock()
    mock_voice_out.is_speaking = False
    sat.voice_out = mock_voice_out

    # Utterance demonstrating Core AI to others
    demo_phrase = "Ja, das ist Core AI, ich zeig dir mal was"
    sat.on_speech_detected(demo_phrase)

    # Must invoke synthesize_and_play with the charismatic demonstration statement
    assert mock_voice_out.synthesize_and_play.called
    played_args = mock_voice_out.synthesize_and_play.call_args[0]
    assert any("Demonstration" in str(a) or "Dyvorn" in str(a) for a in played_args)


def test_fast_cli_glyph_and_mobile_dispatch(capsys):
    """Verify Fast CLI dispatches 'mobile' and 'glyph' subcommands."""
    import sys
    from interfaces.cli.client import main as cli_main
    from unittest.mock import patch

    with patch("interfaces.mobile.companion.MobileCompanionClient.trigger_glyph", return_value={"status": "dispatched"}):
        old_argv = sys.argv
        try:
            sys.argv = ["core", "glyph", "alert_burst"]
            res = cli_main()
            assert res == 0
            captured = capsys.readouterr()
            assert "alert_burst" in captured.out
        finally:
            sys.argv = old_argv


def test_satellite_details_endpoint(gateway_test_env):
    """Verify GET /api/v1/mesh/satellites/{node_id} returns accurate satellite status and handles 404s."""
    client, _, _ = gateway_test_env

    # 1. Register a satellite
    hb = {
        "node_id": "balcony_satellite",
        "zone": "balcony",
        "mic_device": "USB Mic",
        "speaker_device": "Balcony Speaker",
        "status": "listening",
        "uptime_seconds": 45.0
    }
    client.post("/api/v1/mesh/satellites/heartbeat", json=hb)

    # 2. Fetch specific satellite details
    res = client.get("/api/v1/mesh/satellites/balcony_satellite")
    assert res.status_code == 200
    data = res.json()
    assert data["node_id"] == "balcony_satellite"
    assert data["zone"] == "balcony"
    assert data["effective_status"] == "online"
    assert "is_connected_ws" in data

    # 3. Request nonexistent satellite -> 404
    missing_res = client.get("/api/v1/mesh/satellites/nonexistent_satellite_node")
    assert missing_res.status_code == 404


def test_mobile_companion_send_command_and_ask_cli(capsys):
    """Verify MobileCompanionClient.send_command and 'core mobile ask' CLI action."""
    import sys
    from unittest.mock import patch
    from interfaces.mobile.companion import MobileCompanionClient
    from interfaces.cli.client import main as cli_main

    mock_resp = {
        "status": "success",
        "spoken_response": "The living room lights have been adjusted to ambient warm.",
        "final_output": {"state": "on"}
    }
    with patch.object(MobileCompanionClient, "send_command", return_value=mock_resp), \
         patch.object(MobileCompanionClient, "trigger_glyph", return_value={"status": "dispatched"}):
        old_argv = sys.argv
        try:
            sys.argv = ["core", "mobile", "ask", "adjust lighting"]
            code = cli_main()
            assert code == 0
            captured = capsys.readouterr()
            assert "living room lights" in captured.out
        finally:
            sys.argv = old_argv


def test_service_manager_metrics_includes_satellites_and_mobile(tmp_path):
    """Verify ServiceManager.get_system_metrics includes active satellites and mobile companion counts."""
    from unittest.mock import MagicMock
    mock_conn = MagicMock()
    mock_conn.edge_nodes = {"sat_1": None}
    mock_conn.broadcast_clients = set()
    mock_conn.mobile_clients = {"phone_1": None, "phone_2": None}
    mock_conn.get_active_satellites_count.return_value = 1

    metrics = ServiceManager.get_system_metrics(
        state_manager=None,
        planner=None,
        connection_manager=mock_conn,
        registry=None
    )
    assert "network" in metrics
    net = metrics["network"]
    assert net["active_satellites_count"] == 1
    assert net["mobile_clients_count"] == 2


def test_fast_cli_speak_command(capsys):
    """Verify 'core speak <phrase>' executes local speech playback."""
    import sys
    from unittest.mock import patch
    from interfaces.cli.client import main as cli_main

    with patch("engines.voice_out.VoiceOutEngine.synthesize_and_play") as mock_play:
        old_argv = sys.argv
        try:
            sys.argv = ["core", "speak", "Welcome back, Operator"]
            code = cli_main()
            assert code == 0
            assert mock_play.called
            played_text = mock_play.call_args[0][0]
            assert "Welcome back" in played_text
            captured = capsys.readouterr()
            assert "Welcome back" in captured.out
        finally:
            sys.argv = old_argv


def test_satellite_adaptive_operational_modes():
    """Verify VoiceSatellite adapts correctly to speak_only and listen_only operational modes."""
    from unittest.mock import patch, MagicMock

    with patch("interfaces.voice.satellite.VoiceOutEngine") as mock_vout, \
         patch("interfaces.voice.satellite.VoiceInEngine") as mock_vin:
        mock_vout.return_value = MagicMock()
        mock_vin.return_value = MagicMock()

        # 1. Test speak_only mode
        sat_spk = VoiceSatellite(node_id="media_soundbar", mode="speak_only")
        ok_spk, msg_spk = sat_spk.initialize_hardware()
        assert ok_spk is True
        assert sat_spk.operational_mode == "speaker_only"
        assert sat_spk.voice_in is None
        assert "audio_out" in sat_spk.capabilities
        assert "audio_in" not in sat_spk.capabilities
        # Test card printing doesn't raise
        sat_spk.print_satellite_card()

        # 2. Test listen_only mode
        sat_mic = VoiceSatellite(node_id="ceiling_mic", mode="listen_only")
        ok_mic, msg_mic = sat_mic.initialize_hardware()
        assert ok_mic is True
        assert sat_mic.operational_mode == "listen_only"
        assert sat_mic.voice_out is None
        assert "audio_in" in sat_mic.capabilities
        assert "audio_out" not in sat_mic.capabilities
        # Test card printing doesn't raise
        sat_mic.print_satellite_card()


def test_glyph_matrix_ansi_renderer():
    """Verify render_glyph_matrix generates accurate ANSI representations for all Nothing OS patterns."""
    from interfaces.mobile.companion import render_glyph_matrix

    patterns = ["reasoning_pulse", "success_flash", "alert_burst", "listening", "idle"]
    for pat in patterns:
        rendered = render_glyph_matrix(pat, brightness=200)
        assert "Nothing Phone (2) Glyph Backplate" in rendered
        assert "Zone: Rear Glass Transparency" in rendered
        assert "Intensity:" in rendered
        assert "Camera Ring:" in rendered
        assert "Central Arc:" in rendered
        assert "Exclamation:" in rendered


def test_satellite_cli_mode_flags():
    """Verify VoiceSatellite CLI parses mode flags (--speak-only, --listen-only, --mode)."""
    import sys
    from unittest.mock import patch

    with patch("interfaces.voice.satellite.VoiceSatellite.run", return_value=0) as mock_run:
        from interfaces.voice.satellite import main as sat_main

        # Test --speak-only flag
        old_argv = sys.argv
        try:
            sys.argv = ["satellite", "--speak-only", "--node-id", "test_soundbar"]
            with pytest.raises(SystemExit) as exc:
                sat_main()
            assert exc.value.code == 0
            assert mock_run.called
        finally:
            sys.argv = old_argv


def test_pipeline_engine_sync_and_local_fallback(tmp_path):
    """Verify PipelineEngine.execute_pipeline_sync and VoiceSatellite._local_fallback_executor."""
    from core.schemas import PipelinePlan, PipelineStep
    db_file = os.path.join(tmp_path, "sync_exec.db")
    sm = StateManager(db_path=db_file)
    reg = ToolRegistry(dynamic_dir=str(tmp_path))
    reg.register_tool("get_time", get_time, time_schema)
    engine = PipelineEngine(registry=reg, state_manager=sm)

    # 1. Test execute_pipeline_sync
    plan = PipelinePlan(
        id="test_sync_1",
        goal="check current time",
        steps=[
            PipelineStep(id="s1", name="Get Current Time", tool_name="get_time", arguments={})
        ]
    )
    finished = engine.execute_pipeline_sync(plan)
    assert finished.status == "completed"
    assert ":" in str(finished.final_output)

    # 2. Test VoiceSatellite._local_fallback_executor
    sat = VoiceSatellite(
        node_id="fallback_node",
        server_url="http://127.0.0.1:8000",
        state_manager=sm
    )
    sat._local_planner = Planner(registry=reg, state_manager=sm, model_name="heuristic")
    sat._local_engine = engine

    res = sat._local_fallback_executor("what time is it")
    assert res["status"] == "completed"
    assert "spoken_response" in res
    assert len(res["spoken_response"]) > 0


def test_voice_in_stop_alias():
    """Verify VoiceInEngine has stop method alias pointing to stop_listening."""
    from engines.voice_in import VoiceInEngine
    assert hasattr(VoiceInEngine, "stop")
    assert callable(getattr(VoiceInEngine, "stop"))


def test_mobile_enrollment_cli_safe_none_handling(capsys):
    """Verify mobile companion CLI gracefully handles None values in enrollment response."""
    import sys
    from unittest.mock import patch
    from interfaces.mobile.companion import main as comp_main

    mock_enroll_none = {
        "status": "enrolled",
        "client_id": "phone_test",
        "assigned_tier": None,
        "token": None,
        "gateway_ws_url": "/ws/mobile/phone_test"
    }
    with patch("interfaces.mobile.companion.MobileCompanionClient.enroll", return_value=mock_enroll_none):
        old_argv = sys.argv
        try:
            sys.argv = ["companion", "enroll"]
            comp_main()
            captured = capsys.readouterr()
            assert "Successfully enrolled 'phone_test' as GUEST!" in captured.out
            assert "Session Token: N/A" in captured.out
        finally:
            sys.argv = old_argv


def test_satellite_edge_tool_schemas_and_dispatch():
    """Verify VoiceSatellite.get_edge_tools schemas and handle_edge_message RPC execution."""
    from unittest.mock import MagicMock
    sat = VoiceSatellite(node_id="kitchen_sat", zone="kitchen", mode="speak_only")
    mock_vout = MagicMock()
    mock_vout.is_speaking = False
    sat.voice_out = mock_vout

    # 1. Tool schemas
    tools = sat.get_edge_tools()
    assert len(tools) == 3
    tool_names = [t["name"] for t in tools]
    assert "speak_kitchen_sat" in tool_names
    assert "status_kitchen_sat" in tool_names
    assert "interrupt_kitchen_sat" in tool_names

    # 2. Tool call request for speak
    speak_req = {
        "type": "tool_call_request",
        "request_id": "req-101",
        "tool_name": "speak_kitchen_sat",
        "arguments": {"text": "Tea kettle is ready"}
    }
    reply = sat.handle_edge_message(speak_req)
    assert reply is not None
    assert reply["type"] == "tool_call_response"
    assert reply["request_id"] == "req-101"
    assert reply["result"]["status"] == "success"
    assert reply["result"]["spoken"] == "Tea kettle is ready"
    assert mock_vout.synthesize_and_play.called

    # 3. Tool call request for status
    status_req = {
        "type": "tool_call_request",
        "request_id": "req-102",
        "tool_name": "status_kitchen_sat",
        "arguments": {}
    }
    reply_status = sat.handle_edge_message(status_req)
    assert reply_status is not None
    assert reply_status["type"] == "tool_call_response"
    assert reply_status["request_id"] == "req-102"
    assert reply_status["result"]["node_id"] == "kitchen_sat"
    assert reply_status["result"]["zone"] == "kitchen"

    # 4. Tool call request for interrupt
    interrupt_req = {
        "type": "tool_call_request",
        "request_id": "req-103",
        "tool_name": "interrupt_kitchen_sat",
        "arguments": {}
    }
    reply_int = sat.handle_edge_message(interrupt_req)
    assert reply_int is not None
    assert reply_int["result"]["status"] == "success"
    assert reply_int["result"]["interrupted"] is True
    assert mock_vout.interrupt.called

    # 5. Ping message
    ping_msg = {"type": "ping"}
    pong_reply = sat.handle_edge_message(ping_msg)
    assert pong_reply is not None
    assert pong_reply["type"] == "pong"
    assert pong_reply["node_id"] == "kitchen_sat"


def test_mobile_companion_session_persistence(tmp_path):
    """Verify MobileCompanionClient session persistence, token reload, and clearing."""
    session_file = str(tmp_path / "test_mobile_session.json")
    client1 = MobileCompanionClient(
        server_url="http://127.0.0.1:8000",
        client_id="phone_persisted",
        session_file=session_file
    )
    assert client1.token is None

    # Simulate saving session credentials
    client1._save_session({
        "token": "mob_test_tok_999",
        "client_id": "phone_persisted",
        "server_url": "http://127.0.0.1:8000",
        "device_name": "Persisted Phone",
        "assigned_tier": "owner"
    })
    assert os.path.exists(session_file)

    # Instantiate fresh client without passing token
    client2 = MobileCompanionClient(session_file=session_file)
    assert client2.token == "mob_test_tok_999"
    assert client2.client_id == "phone_persisted"
    assert client2.device_name == "Persisted Phone"

    # Clear session
    client2.clear_session()
    assert client2.token is None
    assert not os.path.exists(session_file)


def test_fast_cli_satellite_full_flags():
    """Verify CLI forwards --node-id, --server, and --headless to VoiceSatellite."""
    import sys
    from unittest.mock import patch
    from interfaces.cli.client import main as cli_main

    with patch("interfaces.voice.satellite.VoiceSatellite.run", return_value=0) as mock_run, \
         patch("interfaces.voice.satellite.VoiceSatellite.__init__", return_value=None) as mock_init:
        old_argv = sys.argv
        try:
            sys.argv = [
                "core", "satellite",
                "--node-id", "sat_attic",
                "--server", "http://192.168.1.100:8000",
                "--zone", "attic",
                "--speak-only",
                "--headless"
            ]
            code = cli_main()
            assert code == 0
            mock_init.assert_called_once_with(
                mode="speak_only",
                zone="attic",
                node_id="sat_attic",
                server_url="http://192.168.1.100:8000"
            )
            mock_run.assert_called_once_with(headless=True)
        finally:
            sys.argv = old_argv


def test_spatial_zone_speak_routing(gateway_test_env):
    """Verify speak_on_satellite routes to edge nodes by spatial room zone name."""
    import asyncio
    from unittest.mock import AsyncMock
    client, _, _ = gateway_test_env

    # 1. Register satellite in zone 'studio'
    client.post("/api/v1/mesh/satellites/heartbeat", json={
        "node_id": "studio_speaker",
        "zone": "studio",
        "status": "listening",
        "uptime_seconds": 10.0
    })

    # 2. Attach mock edge node socket in connection_manager
    mock_socket = AsyncMock()
    connection_manager.edge_nodes["studio_speaker"] = mock_socket

    try:
        # 3. Call speak endpoint using the room zone name 'studio' instead of node ID
        res = client.post("/api/v1/mesh/satellites/studio/speak", json={
            "text": "Audio render finalized in studio",
            "voice": "auto",
            "priority": "high"
        })
        assert res.status_code == 200
        assert mock_socket.send_text.called
        sent_payload = json.loads(mock_socket.send_text.call_args[0][0])
        assert sent_payload["type"] == "speak"
        assert "Audio render finalized" in sent_payload["text"]
    finally:
        connection_manager.edge_nodes.pop("studio_speaker", None)


def test_mobile_send_command_glyph_alert_on_error():
    """Verify MobileCompanionClient triggers alert_burst when command returns error status."""
    from unittest.mock import patch, MagicMock
    client = MobileCompanionClient(server_url="http://127.0.0.1:8000")

    mock_error_resp = MagicMock()
    mock_error_resp.read.return_value = json.dumps({
        "status": "error",
        "message": "Tool execution rejected by policy"
    }).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=mock_error_resp), \
         patch.object(client, "trigger_glyph") as mock_glyph:
        res = client.send_command("wipe all system files")
        assert res["status"] == "error"
        # Must have triggered reasoning_pulse first, then alert_burst (never success_flash)
        glyph_calls = [c[0][0] for c in mock_glyph.call_args_list]
        assert "reasoning_pulse" in glyph_calls
        assert "alert_burst" in glyph_calls
        assert "success_flash" not in glyph_calls


def test_satellite_and_companion_identifier_sanitization():
    """Verify VoiceSatellite and MobileCompanionClient sanitize node/client IDs against URL injection."""
    sat = VoiceSatellite(node_id="Desk PC #1 (Main)")
    assert sat.node_id == "Desk_PC__1__Main_"

    comp = MobileCompanionClient(client_id="Phone: Dyvorn's Nothing (2)")
    assert comp.client_id == "Phone__Dyvorn_s_Nothing__2_"




