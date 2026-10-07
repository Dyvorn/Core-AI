import os
import pytest
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema, get_system_status
from brain.dynamic_generator import DynamicGenerator
from brain.planner import Planner

def test_planner_tool_introspection_and_planning(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    registry.register_tool("get_time", get_time, time_schema)
    
    def dummy_ha_service(entity_id: str, action: str) -> dict:
        return {"status": "success", "entity_id": entity_id, "state": "on" if action == "turn_on" else "off"}
        
    ha_schema = {
        "name": "home_assistant_call",
        "description": "Call a Home Assistant service on an entity",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "action": {"type": "string"}
            },
            "required": ["entity_id", "action"]
        }
    }
    registry.register_tool("home_assistant_call", dummy_ha_service, ha_schema)

    planner = Planner(registry=registry, model_name="heuristic")

    # Test home assistant action
    plan = planner.plan_problem("Schalte das Licht ein")
    assert plan.goal == "Schalte das Licht ein"
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "home_assistant_call"
    assert plan.steps[0].arguments["action"] == "turn_on"

def test_planner_missing_tool_synthesis(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    dyn_gen = DynamicGenerator(registry=registry, dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry, dynamic_generator=dyn_gen, model_name="heuristic")

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
    planner = Planner(registry=registry, model_name="heuristic")
    plan = planner.plan_problem("what time is it and check system status")
    assert len(plan.steps) == 2
    tool_names = [s.tool_name for s in plan.steps]
    assert "get_time" in tool_names
    assert "get_system_status" in tool_names


def test_planner_greeting_response_not_time(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry, model_name="heuristic")
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
    planner = Planner(registry=registry, model_name="heuristic")
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

def test_planner_spatial_relocation(tmp_path):
    from main import setup_tools
    from core.state import StateManager
    from core.schemas import UserProfile
    db_path = str(tmp_path / "test_reloc.db")
    state = StateManager(db_path=db_path)
    registry = setup_tools(state=state)
    planner = Planner(registry=registry, state_manager=state, model_name="heuristic")

    # 1. English statement: "I'm in the office rn"
    plan_en = planner.plan_problem("I'm in the office rn")
    assert len(plan_en.steps) == 1
    assert plan_en.steps[0].tool_name == "relocate_operator"
    assert plan_en.steps[0].arguments["target_zone"] == "office"

    # Execute tool directly to simulate pipeline completion
    res = registry.execute_tool("relocate_operator", plan_en.steps[0].arguments)
    assert res.success is True
    plan_en.steps[0].status = "completed"
    plan_en.steps[0].output = res.output
    plan_en.status = "completed"

    spoken = planner.formulate_spoken_response(plan_en, profile=UserProfile(preferred_name="Dyvorn"))
    assert "Dyvorn" in spoken
    assert "Office" in spoken

    # 2. German statement: "ich bin jetzt im büro"
    plan_de = planner.plan_problem("ich bin jetzt im büro")
    assert len(plan_de.steps) == 1
    assert plan_de.steps[0].tool_name == "relocate_operator"
    assert plan_de.steps[0].arguments["target_zone"] == "büro"

def test_weather_and_knowledge_tools(tmp_path):
    from main import setup_tools
    from core.state import StateManager
    from core.schemas import UserProfile, PipelinePlan, PipelineStep
    db_path = str(tmp_path / "test_weather.db")
    state = StateManager(db_path=db_path)
    registry = setup_tools(state=state)
    planner = Planner(registry=registry, state_manager=state, model_name="heuristic")

    # 1. Weather tool execution
    w_res = registry.execute_tool("get_weather", {"location": "Halle (Saale)"})
    if w_res.success and isinstance(w_res.output, dict) and w_res.output.get("status") == "success":
        assert "temperature_c" in w_res.output
        weather_out = w_res.output
    else:
        # Fallback payload if external public weather API is 503 / offline
        weather_out = {
            "status": "success",
            "location": "Halle (Saale)",
            "temperature_c": 18.5,
            "condition": "Clear Sky"
        }

    # 2. Weather spoken formulation
    plan_w = PipelinePlan(
        goal="whats the temp in Halle (Saale)",
        steps=[PipelineStep(
            id="w1", name="Weather", tool_name="get_weather",
            arguments={"location": "Halle (Saale)"}, status="completed",
            output=weather_out
        )],
        status="completed"
    )
    spoken_w = planner.formulate_spoken_response(plan_w, profile=UserProfile(preferred_name="Dyvorn"))
    assert "Halle" in spoken_w
    assert "°C" in spoken_w or "degrees" in spoken_w

    # 3. Knowledge tool execution
    k_res = registry.execute_tool("lookup_knowledge", {"query": "Albert Einstein", "language": "en"})
    if k_res.success and isinstance(k_res.output, dict) and k_res.output.get("status") == "success":
        assert "Albert Einstein" in k_res.output.get("topic", "")

def test_greeting_override_prevention(tmp_path):
    from main import setup_tools
    from core.state import StateManager
    from core.schemas import UserProfile, PipelinePlan
    db_path = str(tmp_path / "test_greet.db")
    state = StateManager(db_path=db_path)
    registry = setup_tools(state=state)
    planner = Planner(registry=registry, state_manager=state, model_name="heuristic")

    # If an LLM returns a direct response, a query starting with 'hi' must NOT return a generic greeting
    plan = PipelinePlan(
        goal="hi what is the capital of France?",
        steps=[],
        context={"direct_response": "The capital of France is Paris."},
        status="completed"
    )
    spoken = planner.formulate_spoken_response(plan, profile=UserProfile(preferred_name="Dyvorn"))
    assert spoken == "The capital of France is Paris."
    assert "Online and ready" not in spoken




