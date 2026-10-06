import os
import pytest
from starlette.testclient import TestClient

from core.state import StateManager
from core.bus import EventBus
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.gateway import create_gateway_app
from interfaces.cli.settings import SettingsCLI

def test_settings_cli_getters_and_setters(tmp_path):
    db_path = str(tmp_path / "test_settings.db")
    state = StateManager(db_path=db_path)
    cli = SettingsCLI(state_manager=state)

    # 1. Test model assignment
    cli.set_model("planner", "ollama/qwen3.5:2b")
    prefs = cli.model_router.get_model_preferences()
    assert prefs["planner"] == "ollama/qwen3.5:2b"

    # 2. Test operator handle update
    cli.set_operator("DyvornVyrn")
    prof = state.get_user_profile()
    assert prof.preferred_name == "DyvornVyrn"

    # 3. Test primary space update
    cli.set_zone("command_deck")
    prof = state.get_user_profile()
    assert prof.preferences["primary_space"] == "command_deck"
    assert any(z.zone_id == "command_deck" for z in state.list_zones())

    # 4. Test tone update
    cli.set_tone("jarvis_tactical")
    prof = state.get_user_profile()
    assert prof.preferred_tone == "jarvis_tactical"

    # 5. Test available models listing
    avail = cli.list_available_models()
    assert "ollama" in avail
    assert "cloud" in avail
    assert len(avail["ollama"]) >= 1

def test_sovereign_mesh_dashboard_serving(tmp_path):
    os.environ["CORE_DISABLE_DISCOVERY"] = "1"
    db_path = str(tmp_path / "test_dash.db")
    state = StateManager(db_path=db_path)
    from tools.registry import ToolRegistry
    registry = ToolRegistry(dynamic_dir=str(tmp_path / "dyn"))
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

    with TestClient(app) as client:
        # 1. GET / (Dashboard Index)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Sovereign Mesh Master Dashboard" in resp.text
        assert "Connected Mesh Topology &amp; Devices" in resp.text or "Connected Mesh Topology & Devices" in resp.text

        # 2. GET /dashboard
        resp_dash = client.get("/dashboard")
        assert resp_dash.status_code == 200
        assert "text/html" in resp_dash.headers["content-type"]

        # 3. GET /static/dashboard.css
        resp_css = client.get("/static/dashboard.css")
        assert resp_css.status_code == 200
        assert "glass-panel" in resp_css.text

        # 4. GET /static/dashboard.js
        resp_js = client.get("/static/dashboard.js")
        assert resp_js.status_code == 200
        assert "connectWebSocket" in resp_js.text
