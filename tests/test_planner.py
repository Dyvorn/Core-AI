import os
import pytest
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema, get_system_status
from tools.native.home_assistant import HomeAssistantMock, ha_call_schema
from brain.dynamic_generator import DynamicGenerator
from brain.planner import Planner

def test_planner_tool_introspection_and_planning(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    registry.register_tool("get_time", get_time, time_schema)
    ha = HomeAssistantMock("http://localhost:8123", "token")
    registry.register_tool("home_assistant_call", ha.call_service, ha_call_schema)

    planner = Planner(registry=registry)

    # Test home assistant action
    plan = planner.plan_problem("Schalte das Licht ein")
    assert plan.goal == "Schalte das Licht ein"
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "home_assistant_call"
    assert plan.steps[0].arguments["action"] == "turn_on"

def test_planner_missing_tool_synthesis(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    dyn_gen = DynamicGenerator(registry=registry, dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry, dynamic_generator=dyn_gen)

    assert not registry.has_tool("hash_string")

    # Planning a problem that needs hash_string should trigger dynamic synthesis
    plan = planner.plan_problem("Please hash this secret string")
    assert registry.has_tool("hash_string")
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "hash_string"

def test_planner_model_availability_check(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry, model_name="non_existent/model:offline")
    # Health check should return False without crashing
    is_avail = planner.check_model_availability("non_existent/model:offline")
    assert is_avail is False


def test_planner_compound_time_and_system_status(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry)
    plan = planner.plan_problem("what time is it and check system status")
    assert len(plan.steps) == 2
    tool_names = [s.tool_name for s in plan.steps]
    assert "get_time" in tool_names
    assert "get_system_status" in tool_names


def test_planner_greeting_response_not_time(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry)
    plan = planner.plan_problem("hi")
    # Should not fabricate a get_time step
    assert len(plan.steps) == 0
    from core.schemas import UserProfile
    spoken = planner.formulate_spoken_response(plan, profile=UserProfile(preferred_name="Dyvorn"))
    assert "Dyvorn" in spoken
    assert "Online and ready" in spoken
    assert "It is" not in spoken

def test_planner_open_ended_offline_ai_notice(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry)
    plan = planner.plan_problem("what is in my fridge right now?")
    # No fabricated tools for unhandled open-ended questions
    assert len(plan.steps) == 0
    assert plan.context.get("offline_ai_notice") is True

    from core.schemas import UserProfile
    spoken = planner.formulate_spoken_response(plan, profile=UserProfile(preferred_name="Dyvorn"))
    assert "Dyvorn" in spoken
    assert "no AI reasoning model" in spoken or "kein KI-Modell" in spoken
    assert "api-key set" in spoken

def test_network_tools_registration(tmp_path):
    from main import setup_tools
    from core.state import StateManager
    db_path = str(tmp_path / "test_net.db")
    state = StateManager(db_path=db_path)
    registry = setup_tools(state=state)

    assert registry.has_tool("scan_local_network")
    assert registry.has_tool("inspect_lan_device")
    assert registry.has_tool("list_registered_devices")
    assert registry.has_tool("list_spatial_zones")

    # Execute list_registered_devices tool
    res = registry.execute_tool("list_registered_devices", {})
    assert res.success is True
    assert isinstance(res.output, dict)
    assert res.output["status"] == "success"
    assert "devices" in res.output

    # Execute scan_local_network tool
    scan_res = registry.execute_tool("scan_local_network", {"timeout_sec": 0.5})
    assert scan_res.success is True
    assert isinstance(scan_res.output, dict)
    assert scan_res.output["status"] == "success"
    assert "devices" in scan_res.output



