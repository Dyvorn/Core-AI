import os
import sys
import pytest
from tools.native.system_tools import inspect_system_resources, system_resources_schema
from tools.registry import ToolRegistry
from brain.planner import Planner
from core.schemas import PipelinePlan, PipelineStep
from core.mesh_client import MeshClient
from core.state import StateManager


def test_inspect_system_resources():
    res = inspect_system_resources()
    assert isinstance(res, dict)
    assert "os" in res
    assert "cpu_count" in res
    assert res["cpu_count"] >= 1
    assert "disk" in res
    assert "total_gb" in res["disk"]
    assert "free_gb" in res["disk"]
    assert res["disk"]["total_gb"] > 0
    assert system_resources_schema["name"] == "inspect_system_resources"


def test_planner_system_resources_heuristic():
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    registry.register_tool("inspect_system_resources", inspect_system_resources, system_resources_schema)
    planner = Planner(registry=registry, model_name="heuristic")

    plan = planner.plan_problem("check system vitals")
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "inspect_system_resources"

    plan_de = planner.plan_problem("wie viel speicher frei ist auf der festplatte")
    assert len(plan_de.steps) == 1
    assert plan_de.steps[0].tool_name == "inspect_system_resources"


def test_spoken_response_system_resources():
    planner = Planner(registry=ToolRegistry(), model_name="heuristic")
    dummy_plan = PipelinePlan(
        id="test-plan-1",
        goal="system vitals",
        status="completed",
        steps=[
            PipelineStep(
                id="s1",
                name="Inspect",
                tool_name="inspect_system_resources",
                status="completed",
                output={
                    "cpu_percent": 12.5,
                    "memory": {"total_gb": 32.0, "available_gb": 16.5, "used_percent": 48.4},
                    "disk": {"total_gb": 1000.0, "free_gb": 450.0, "used_percent": 55.0}
                }
            )
        ]
    )

    spoken_en = planner.formulate_spoken_response(dummy_plan, language="en")
    assert "System vitals:" in spoken_en
    assert "CPU: 12.5%" in spoken_en

    spoken_de = planner.formulate_spoken_response(dummy_plan, language="de")
    assert "Hardwarestatus:" in spoken_de
    assert "CPU: 12.5%" in spoken_de


def test_mesh_client_ping_latency(tmp_path):
    state = StateManager(db_path=str(tmp_path / "test_ping.db"))
    client = MeshClient(state_manager=state, main_server_url="http://127.0.0.1:59999")
    is_online, data, latency = client.ping_latency(timeout=0.2)
    assert is_online is False
    assert isinstance(latency, float)
    assert latency >= 0.0


def test_client_cli_version_command(capsys):
    from interfaces.cli.client import main
    old_argv = sys.argv
    try:
        sys.argv = ["core", "version"]
        code = main()
        assert code == 0
        captured = capsys.readouterr()
        assert "SYSTEM VERSION PROTOCOL" in captured.out
        assert "v0.2.1-alpha" in captured.out
    finally:
        sys.argv = old_argv
