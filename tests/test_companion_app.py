import os
import json
import pytest
from starlette.testclient import TestClient

from core.state import StateManager
from core.bus import EventBus
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.gateway import create_gateway_app
from tools.registry import ToolRegistry


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setenv("CORE_DISABLE_DISCOVERY", "1")
    db_path = str(tmp_path / "test_app.db")
    state = StateManager(db_path=db_path)
    from tools.native import register_all_native_tools
    registry = ToolRegistry(dynamic_dir=str(tmp_path / "dyn"))
    register_all_native_tools(registry)
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
    return TestClient(app), state, planner


def test_headless_gateway_root(app_client):
    client, state, planner = app_client

    # Verify root endpoint returns clean headless JSON status (No Web HTML)
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert data["architecture"] == "headless_api"
    assert "version" in data


def test_companion_chat_and_sessions(app_client):
    client, state, planner = app_client

    # 1. Post a chat message
    chat_payload = {
        "message": "Calculate math expression 14 + 28",
        "session_id": "test_sess_001"
    }
    resp = client.post("/api/v1/chat", json=chat_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "test_sess_001"
    assert data["status"] in ("completed", "success")
    assert "content" in data
    assert "steps" in data

    # 2. Check session was recorded in SQLite kv_state
    saved_sess = state.get_kv("chat_session:test_sess_001")
    assert saved_sess is not None
    assert len(saved_sess["messages"]) >= 2
    assert saved_sess["messages"][0]["role"] == "user"
    assert saved_sess["messages"][1]["role"] == "assistant"

    # 3. List sessions endpoint
    list_resp = client.get("/api/v1/chat/sessions")
    assert list_resp.status_code == 200
    sessions_data = list_resp.json()
    assert any(s["id"] == "test_sess_001" for s in sessions_data["sessions"])

    # 4. Delete session endpoint
    del_resp = client.delete("/api/v1/chat/sessions/test_sess_001")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Confirm deletion from SQLite
    assert state.get_kv("chat_session:test_sess_001") is None


def test_quota_endpoint(app_client):
    client, state, planner = app_client

    resp = client.get("/api/v1/quota")
    assert resp.status_code == 200
    quota = resp.json()
    assert "total_requests" in quota
    assert "tokens_estimated" in quota
    assert "providers" in quota
    assert "gemini" in quota["providers"]
    assert "ollama" in quota["providers"]
    assert "system_vitals" in quota


def test_api_key_update_endpoint(app_client, monkeypatch):
    client, state, planner = app_client

    payload = {
        "provider": "gemini",
        "api_key": "AIzaSyTest_Key_123456",
        "persist_to_env": False
    }
    resp = client.post("/api/v1/models/api-key", json=payload, headers={"x-trust-tier": "owner"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["provider"] == "GEMINI"
    assert os.getenv("GEMINI_API_KEY") == "AIzaSyTest_Key_123456"

    # Guest rejection test
    guest_resp = client.post("/api/v1/models/api-key", json=payload, headers={"x-trust-tier": "guest"})
    assert guest_resp.status_code == 403


def test_native_launcher_and_desktop_capabilities():
    from interfaces.app.app import check_gateway_online, launch_native_qt_app
    assert callable(check_gateway_online)
    assert callable(launch_native_qt_app)

    # Test PyQt6 and Core AI Desktop GUI components
    from PyQt6.QtWidgets import QApplication
    from interfaces.app.app import (
        ChatMessageItem, SettingsDialog, SystemDialog,
        LogsDialog, HelpDialog, CoreAIDesktopApp
    )
    app = QApplication.instance() or QApplication(["test_app", "-platform", "offscreen"])
    assert app is not None

    msg_item = ChatMessageItem(role="user", content="Hello test")
    assert msg_item.role == "user"

    asst_item = ChatMessageItem(
        role="assistant",
        content="Response test",
        steps=[{"tool_name": "calc", "status": "ok", "output": "42"}]
    )
    assert asst_item.role == "assistant"
    assert len(asst_item.steps) == 1


def test_satellite_deactivation_endpoint(app_client):
    client, state, planner = app_client

    # 1. Register a test satellite via heartbeat
    hb_payload = {
        "node_id": "test_satellite_alpha",
        "zone": "office",
        "capabilities": ["audio_in", "audio_out"],
        "status": "online"
    }
    client.post("/api/v1/mesh/satellites/heartbeat", json=hb_payload)

    # 2. Deactivate the satellite
    resp = client.post("/api/v1/mesh/satellites/test_satellite_alpha/deactivate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "deactivated"
    assert data["node_id"] == "test_satellite_alpha"

    # 3. Verify satellite effective status is offline
    sat_resp = client.get("/api/v1/mesh/satellites")
    satellites = sat_resp.json()
    alpha_sat = next((s for s in satellites if s["node_id"] == "test_satellite_alpha"), None)
    assert alpha_sat is not None
    assert alpha_sat["effective_status"] == "offline"


def test_logs_tail_and_audio_endpoints(app_client):
    client, state, planner = app_client

    # 1. Test logs tail endpoint
    resp = client.get("/api/v1/logs/tail?lines=20")
    assert resp.status_code == 200
    data = resp.json()
    assert "lines" in data
    assert "count" in data
    assert isinstance(data["lines"], list)

    # 2. Test audio devices endpoint
    audio_resp = client.get("/api/v1/audio/devices")
    assert audio_resp.status_code == 200
    audio_data = audio_resp.json()
    assert "microphones" in audio_data
    assert "speakers" in audio_data
    assert "voices" in audio_data
    assert len(audio_data["voices"]) >= 5

    # 3. Test audio config update
    cfg_resp = client.post("/api/v1/audio/config", json={"voice": "de-DE-KillianNeural", "tts_rate": "+20%"})
    assert cfg_resp.status_code == 200
    assert cfg_resp.json()["status"] == "saved"


def test_native_desktop_dialogs_and_toggles():
    from PyQt6.QtWidgets import QApplication
    from interfaces.app.app import (
        CoreAIDesktopApp, SettingsDialog, SystemDialog,
        LogsDialog, HelpDialog
    )
    app = QApplication.instance() or QApplication(["test_app", "-platform", "offscreen"])

    # Instantiate dialogs
    set_dlg = SettingsDialog()
    assert set_dlg is not None

    sys_dlg = SystemDialog()
    assert sys_dlg is not None

    logs_dlg = LogsDialog()
    assert logs_dlg is not None

    help_dlg = HelpDialog()
    assert help_dlg is not None

    # Main Window integration
    main_win = CoreAIDesktopApp()
    assert main_win.isVisible() is False

    # Test GUI microphone listening toggle update
    main_win._update_listening_ui(False)
    assert "MUTED" in main_win.mic_top_btn.text()
    assert "MUTED" in main_win.mic_sidebar_btn.text()

    main_win._update_listening_ui(True)
    assert "LISTENING" in main_win.mic_top_btn.text()
    assert "LISTENING" in main_win.mic_sidebar_btn.text()

    # Clean up timers and widgets to prevent background events during subsequent tests
    logs_dlg.poll_timer.stop()
    main_win.health_timer.stop()
    main_win.close()
    set_dlg.close()
    sys_dlg.close()
    logs_dlg.close()
    help_dlg.close()



def test_voice_listening_deactivation_and_reactivation(app_client):
    client, state, planner = app_client

    # 1. Initial status check
    resp_init = client.get("/api/v1/voice/status")
    assert resp_init.status_code == 200
    data_init = resp_init.json()
    assert "listening_enabled" in data_init
    assert "status" in data_init

    # 2. Deactivate / mute microphone listening
    mute_resp = client.post("/api/v1/voice/listening", json={"action": "mute"})
    assert mute_resp.status_code == 200
    mute_data = mute_resp.json()
    assert mute_data["listening_enabled"] is False
    assert mute_data["mode"] == "muted"

    # Verify state persistence in StateManager
    prof = state.get_user_profile()
    assert prof.preferences.get("audio", {}).get("listening_enabled") is False

    # 3. Confirm status endpoint reflects muted state
    st_resp = client.get("/api/v1/voice/status")
    assert st_resp.status_code == 200
    assert st_resp.json()["listening_enabled"] is False
    assert st_resp.json()["status"] == "muted"

    # 4. Toggle back to active listening
    toggle_resp = client.post("/api/v1/voice/listening", json={"action": "toggle"})
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["listening_enabled"] is True
    assert toggle_resp.json()["mode"] == "listening"

    prof = state.get_user_profile()
    assert prof.preferences.get("audio", {}).get("listening_enabled") is True

    # 5. Test explicit enabled boolean flags
    off_resp = client.post("/api/v1/voice/listening", json={"enabled": False})
    assert off_resp.status_code == 200
    assert off_resp.json()["listening_enabled"] is False

    on_resp = client.post("/api/v1/voice/listening", json={"enabled": True})
    assert on_resp.status_code == 200
    assert on_resp.json()["listening_enabled"] is True


def test_qt_custom_paint_widgets():
    """Verify that all custom Nothing OS visual widgets instantiate and paint cleanly."""
    import sys
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QImage, QPainter
    from interfaces.app.app import (
        DotRingGlyph, UserSilhouetteAvatar, PixelAvatar, GridContainerWidget
    )

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 1. DotRingGlyph
    glyph = DotRingGlyph(size=24, dot_color="#D71921")
    assert glyph.width() == 24
    img = QImage(24, 24, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    glyph.paintEvent(None)
    p.end()

    # 2. UserSilhouetteAvatar
    user_avatar = UserSilhouetteAvatar(size=22)
    assert user_avatar.width() == 22
    img2 = QImage(22, 22, QImage.Format.Format_ARGB32)
    p2 = QPainter(img2)
    user_avatar.paintEvent(None)
    p2.end()

    # 3. PixelAvatar
    pixel_avatar = PixelAvatar(size=32)
    assert pixel_avatar.width() == 32
    img3 = QImage(32, 32, QImage.Format.Format_ARGB32)
    p3 = QPainter(img3)
    pixel_avatar.paintEvent(None)
    p3.end()

    # 4. GridContainerWidget
    grid = GridContainerWidget()
    grid.resize(100, 100)
    img4 = QImage(100, 100, QImage.Format.Format_ARGB32)
    p4 = QPainter(img4)
    grid.paintEvent(None)
    p4.end()


