import pytest
from tools.native.network_tools import scan_local_network, scan_local_network_schema, inspect_lan_device, inspect_lan_device_schema
from brain.pipeline_engine import PipelineEngine
from core.schemas import PipelinePlan, PipelineStep
from core.state import StateManager
from tools.registry import ToolRegistry

def test_scan_local_network_runs():
    res = scan_local_network(timeout_sec=0.5)
    assert res["status"] == "success"
    assert "device_count" in res
    assert isinstance(res["devices"], list)
    assert len(res["devices"]) >= 1

def test_inspect_lan_device_resilience():
    # Calling with unexpected keyword argument from LLM should NOT raise TypeError
    res1 = inspect_lan_device(target_ip_address="127.0.0.1", timeout_sec=0.2)
    assert "is_reachable" in res1
    assert res1["host"] == "127.0.0.1"

    res2 = inspect_lan_device(ip_address="127.0.0.1", timeout_sec=0.2)
    assert res2["host"] == "127.0.0.1"

    # Calling with unresolved template expression should safely fall back
    res3 = inspect_lan_device(target_ip_address="{{steps.scan.output.devices[0].ip}}", timeout_sec=0.2)
    assert res3["host"] == "127.0.0.1"

def test_pipeline_engine_nested_traversal(tmp_path):
    engine = PipelineEngine(registry=ToolRegistry(), state_manager=StateManager(db_path=str(tmp_path / "test.db")))
    
    mock_output = {
        "status": "success",
        "devices": [
            {"ip": "192.168.1.42", "mac": "00:11:22:33:44:55", "hostname": "my-phone"}
        ]
    }

    # 1. Standard bracket index
    val1 = engine._traverse_field_path(mock_output, "devices[0].ip")
    assert val1 == "192.168.1.42"

    # 2. Dot index format
    val2 = engine._traverse_field_path(mock_output, "devices.0.ip")
    assert val2 == "192.168.1.42"

    # 3. LLM alias format with discovered_devices and .[0].ip_address
    val3 = engine._traverse_field_path(mock_output, "discovered_devices.[0].ip_address")
    assert val3 == "192.168.1.42"

@pytest.mark.anyio
async def test_network_inspection_pipeline(tmp_path):
    state = StateManager(db_path=str(tmp_path / "test_pipeline.db"))
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    registry.register_tool("scan_local_network", scan_local_network, scan_local_network_schema)
    registry.register_tool("inspect_lan_device", inspect_lan_device, inspect_lan_device_schema)

    engine = PipelineEngine(registry=registry, state_manager=state)

    plan = PipelinePlan(
        goal="Scan and inspect network devices",
        steps=[
            PipelineStep(
                id="scan_local_network_step",
                name="Scan local network",
                tool_name="scan_local_network",
                arguments={},
                depends_on=[]
            ),
            PipelineStep(
                id="inspect_lan_devices_step",
                name="Inspect discovered device",
                tool_name="inspect_lan_device",
                arguments={"target_ip_address": "{{steps.scan_local_network_step.output.discovered_devices.[0].ip_address}}"},
                depends_on=["scan_local_network_step"]
            )
        ]
    )

    result = await engine.execute_pipeline(plan)
    assert result.status == "completed"
    assert len(result.steps) == 2
    assert result.steps[0].status == "completed"
    assert result.steps[1].status == "completed"
    assert "is_reachable" in result.steps[1].output
