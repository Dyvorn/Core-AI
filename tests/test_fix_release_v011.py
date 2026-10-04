import pytest
from core.state import StateManager
from tools.native.process_tools import list_running_processes, list_running_processes_schema
from tools.native.math_tools import calculate_math, calculate_math_schema
from tools.registry import ToolRegistry
from brain.planner import Planner
from core.schemas import UserProfile, PipelinePlan, PipelineStep

def test_calculate_math_graceful_field_handling():
    # Calling with unexpected keyword argument 'field' should not raise TypeError
    res1 = calculate_math(field="memory_usage")
    assert res1["status"] == "success"
    assert res1["result"] == 0

    res2 = calculate_math("25 * 4")
    assert res2["status"] == "success"
    assert res2["result"] == 100

def test_list_running_processes_memory_sorting():
    res = list_running_processes(sort_by="memory", limit=5)
    assert res["status"] == "success"
    assert "count" in res
    assert "top_consumer" in res
    assert "top_apps" in res
    assert isinstance(res["processes"], list)
    if res["processes"]:
        # Verify descending order of memory_kb
        mem_vals = [p.get("memory_kb", 0) for p in res["processes"]]
        assert mem_vals == sorted(mem_vals, reverse=True)

def test_state_delete_all_zones_except(tmp_path):
    state = StateManager(db_path=str(tmp_path / "test_zones.db"))
    state.ensure_zone_exists("office", display_name="Executive Office")
    state.ensure_zone_exists("studio", display_name="Studio")
    state.ensure_zone_exists("workspace", display_name="Primary Workspace")
    state.ensure_zone_exists("default", display_name="Default")

    initial = state.list_zones()
    assert len(initial) == 4

    deleted = state.delete_all_zones_except(["office"])
    assert "studio" in deleted
    assert "workspace" in deleted
    assert "default" in deleted

    remaining = state.list_zones()
    assert len(remaining) == 1
    assert remaining[0].zone_id == "office"

def test_planner_ram_query_and_spoken_response(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    state = StateManager(db_path=str(tmp_path / "test_planner.db"))
    planner = Planner(registry=registry, state_manager=state, model_name="heuristic")

    plan = planner.plan_problem("whats pulling most ram")
    assert len(plan.steps) == 2
    tool_names = [s.tool_name for s in plan.steps]
    assert "list_running_processes" in tool_names
    assert "get_hardware_metrics" in tool_names

    # Test spoken formulation
    plan.steps[0].status = "completed"
    plan.steps[0].output = {"metrics": {"memory": {"percent_used": 78.5}}}
    plan.steps[1].status = "completed"
    plan.steps[1].output = {
        "status": "success",
        "top_consumer": "chrome.exe pulling 1.8 GB across 12 process(es)",
        "processes": []
    }
    plan.status = "completed"

    spoken = planner.formulate_spoken_response(plan, profile=UserProfile(preferred_name="Dyvorn"))
    assert "Dyvorn" in spoken
    assert "78.5%" in spoken
    assert "chrome.exe" in spoken

def test_planner_remove_zones_except_office(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    state = StateManager(db_path=str(tmp_path / "test_planner_zones.db"))
    planner = Planner(registry=registry, state_manager=state, model_name="heuristic")

    plan = planner.plan_problem("remove all zones exept office")
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "remove_spatial_zone"
    assert plan.steps[0].arguments["all_except"] == "office"

    # Test spoken formulation
    plan.steps[0].status = "completed"
    plan.steps[0].output = {
        "status": "success",
        "action": "delete_all_except",
        "kept_zones": ["office"],
        "deleted_count": 3
    }
    plan.status = "completed"

    spoken = planner.formulate_spoken_response(plan, profile=UserProfile(preferred_name="Dyvorn"))
    assert "Dyvorn" in spoken
    assert "Office" in spoken
    assert "removed" in spoken or "gelöscht" in spoken
