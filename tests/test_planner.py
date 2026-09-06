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

