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

def test_gateway_headless_root_status(tmp_path):
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
        # GET / (Headless API Root)
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert "Core AI Universal Gateway" in data["name"]
        assert data["architecture"] == "headless_api"
