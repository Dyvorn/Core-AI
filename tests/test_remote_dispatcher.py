import pytest
import os
import asyncio
from tools.registry import ToolRegistry
from tools.remote_dispatcher import RemoteToolDispatcher
from core.gateway import connection_manager
from core.schemas import ToolCallRequest

class MockWebSocket:
    def __init__(self):
        self.sent_messages = []

    async def accept(self):
        pass

    async def send_text(self, text: str):
        self.sent_messages.append(text)


@pytest.mark.anyio
async def test_remote_dispatcher_registration(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    dispatcher = RemoteToolDispatcher(registry=registry)

    dispatcher.register_remote_edge_tool(
        node_id="vehicle_car",
        tool_name="car_lock_doors",
        description="Lock vehicle doors",
        parameters_schema={"type": "object", "properties": {}}
    )

    assert registry.has_tool("car_lock_doors")
    catalog = registry.get_tool_catalog()
    tool_meta = next(t for t in catalog if t["name"] == "car_lock_doors")
    assert "vehicle_car" in tool_meta["description"]

@pytest.mark.anyio
async def test_remote_tool_dispatch_execution():
    mock_ws = MockWebSocket()
    node_id = "test_vehicle"
    await connection_manager.connect_edge_node(node_id, mock_ws)

    request = ToolCallRequest(
        source_node="kernel",
        room_id="remote",
        tool_name="car_lock",
        arguments={"all": True},
        target_node=node_id
    )

    # Spawn dispatch task in background
    dispatch_task = asyncio.create_task(
        connection_manager.dispatch_remote_tool_call(node_id=node_id, request=request, timeout=2.0)
    )

    # Allow task to send message over mock socket
    await asyncio.sleep(0.05)
    assert len(mock_ws.sent_messages) == 1
    assert "tool_call_request" in mock_ws.sent_messages[0]

    # Simulate client edge device replying
    fut = connection_manager.pending_tool_calls.get(request.id)
    assert fut is not None
    fut.set_result({"locked": True, "status": "ok"})

    result = await dispatch_task
    assert result["locked"] is True
    assert result["status"] == "ok"

    connection_manager.disconnect_edge_node(node_id)
