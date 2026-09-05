import os
import pytest
from core.state import StateManager
from brain.model_router import ModelRouter
from brain.planner import Planner
from tools.registry import ToolRegistry

def test_model_router_defaults_and_persistence(tmp_path):
    db_path = str(tmp_path / "test_state.db")
    state = StateManager(db_path=db_path)
    router = ModelRouter(state_manager=state)

    # Defaults
    prefs = router.get_model_preferences()
    assert "planner" in prefs
    assert "fallback" in prefs

    # Persist custom preference
    updated = router.set_model_preference("planner", "gemini/gemini-2.5-pro")
    assert updated["planner"] == "gemini/gemini-2.5-pro"

    # Verify loaded from state
    reloaded_prefs = router.get_model_preferences()
    assert reloaded_prefs["planner"] == "gemini/gemini-2.5-pro"

def test_extract_model_override():
    state = StateManager(":memory:")
    router = ModelRouter(state_manager=state)

    # Case 1: with model
    goal1 = "compute sha256 of 'secret' with ollama/llama3"
    clean, model = router.extract_model_override(goal1)
    assert model == "ollama/llama3"
    assert clean == "compute sha256 of 'secret'"

    # Case 2: using model
    goal2 = "plan trip to Tokyo using gemini/gemini-2.5-flash"
    clean2, model2 = router.extract_model_override(goal2)
    assert model2 == "gemini/gemini-2.5-flash"
    assert clean2 == "plan trip to Tokyo"

    # Case 3: no override
    goal3 = "turn on the studio lights"
    clean3, model3 = router.extract_model_override(goal3)
    assert model3 is None
    assert clean3 == goal3

def test_set_api_key(monkeypatch):
    state = StateManager(":memory:")
    router = ModelRouter(state_manager=state)

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert os.getenv("GEMINI_API_KEY") is None

    env_var = router.set_api_key("gemini", "test_key_12345", persist_to_env=False)
    assert env_var == "GEMINI_API_KEY"
    assert os.getenv("GEMINI_API_KEY") == "test_key_12345"

def test_planner_model_override_integration(tmp_path):
    db_path = str(tmp_path / "test_planner.db")
    state = StateManager(db_path=db_path)
    registry = ToolRegistry(dynamic_dir=str(tmp_path / "dynamic"))
    router = ModelRouter(state_manager=state)
    planner = Planner(registry=registry, state_manager=state, model_router=router)

    # Resolve model with explicit prompt override
    goal = "calculate 2 + 2 using ollama/qwen3.5:2b"
    clean_goal, resolved = router.resolve_model(goal)
    assert clean_goal == "calculate 2 + 2"
    # Even if offline, prompt extraction works properly
    assert router.extract_model_override(goal)[1] == "ollama/qwen3.5:2b"

def test_status_summary():
    state = StateManager(":memory:")
    router = ModelRouter(state_manager=state)
    summary = router.get_status_summary()

    assert "configured_providers" in summary
    assert "roles" in summary
    assert "planner" in summary["roles"]
