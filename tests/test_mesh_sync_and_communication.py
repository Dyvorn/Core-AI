"""
Core AI :: Automated Verification for Phase 5 Mesh Sync & Inter-Device Communication
Tests:
- Durable SQLite offline task queueing and replay
- StateManager delta extraction and conflict-free last-write-wins merging
- Gateway endpoints: /api/v1/mesh/sync/pull, /api/v1/mesh/sync/push, /api/v1/mesh/sync
- Inter-device message routing across nodes, room zones, and mesh broadcast
- MeshClient sync, send_message, and node matrix inventory
"""

import os
import time
import json
import pytest
from datetime import datetime, timezone
from starlette.testclient import TestClient

from core.state import StateManager
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.bus import EventBus
from core.gateway import create_gateway_app, connection_manager
from core.schemas import (
    UserProfile, ZoneRecord, DeviceTopologyRecord, ProactiveTriggerRule,
    MeshSyncPullRequest, MeshSyncPushRequest, MeshSyncFullRequest,
    MeshDeviceMessage, MeshSyncPayload
)
from core.mesh_client import MeshClient


@pytest.fixture
def mesh_gateway_env(tmp_path):
    db_file = os.path.join(tmp_path, "test_mesh_sync.db")
    state = StateManager(db_path=db_file)
    profile = state.get_user_profile()
    profile.preferred_name = "Dyvorn"
    profile.preferences["primary_space"] = "studio"
    state.save_user_profile(profile)

    # Prepopulate some initial zones and notes
    state.ensure_zone_exists("studio", "Music & Dev Studio")
    state.ensure_zone_exists("living_room", "Main Living Room")
    state.set_kv("note:initial", {"title": "initial", "content": "Welcome to Core AI"})

    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    registry.register_tool("get_time", get_time, time_schema)
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
    client = TestClient(app)
    return client, state, app


# ---------------------------------------------------------------------------
# 1. StateManager Offline Queue & Delta Merging Unit Tests
# ---------------------------------------------------------------------------

def test_offline_task_queue_and_replay(tmp_path):
    """Verify offline goals are durably enqueued into SQLite and marked synced upon replay."""
    db_file = os.path.join(tmp_path, "test_offline.db")
    sm = StateManager(db_path=db_file)

    # 1. Enqueue two offline tasks
    tid1 = sm.enqueue_offline_task(
        goal="check temperature in garage",
        context={"zone": "garage"},
        result={"temperature": 21.5},
        status="completed_locally"
    )
    tid2 = sm.enqueue_offline_task(
        goal="turn on studio desk lamp",
        context={"zone": "studio"},
        result={"status": "ok"},
        status="completed_locally"
    )

    # 2. Verify unsynced list
    unsynced = sm.get_unsynced_offline_tasks()
    assert len(unsynced) == 2
    assert unsynced[0]["id"] == tid1
    assert unsynced[0]["goal"] == "check temperature in garage"
    assert unsynced[1]["id"] == tid2

    # 3. Mark first task synced
    marked = sm.mark_offline_tasks_synced([tid1])
    assert marked == 1

    # 4. Only tid2 remains unsynced
    remaining = sm.get_unsynced_offline_tasks()
    assert len(remaining) == 1
    assert remaining[0]["id"] == tid2

    # 5. Mark remaining synced
    sm.mark_offline_tasks_synced([tid2])
    assert len(sm.get_unsynced_offline_tasks()) == 0


def test_state_delta_extraction_and_kv_merging(tmp_path):
    """Verify get_state_deltas extracts modified items and merge_kv_records adheres to last-write-wins."""
    db_file = os.path.join(tmp_path, "test_deltas.db")
    sm = StateManager(db_path=db_file)

    # Set initial note
    sm.set_kv("note:todo", {"task": "Write mesh sync test", "done": False})
    initial_records = sm.get_kv_with_metadata()
    assert len(initial_records) == 1
    assert initial_records[0]["key"] == "note:todo"

    # Delta extraction
    deltas = sm.get_state_deltas()
    assert len(deltas["kv_state"]) >= 1

    # Merge an updated record with a future timestamp
    future_ts = "2099-01-01T00:00:00+00:00"
    merged_count = sm.merge_kv_records([{
        "key": "note:todo",
        "value": {"task": "Write mesh sync test", "done": True},
        "updated_at": future_ts
    }])
    assert merged_count == 1
    assert sm.get_kv("note:todo")["done"] is True

    # Attempt to merge a stale record with past timestamp -> should NOT overwrite
    past_ts = "2000-01-01T00:00:00+00:00"
    sm.merge_kv_records([{
        "key": "note:todo",
        "value": {"task": "Stale overwrite", "done": False},
        "updated_at": past_ts
    }])
    assert sm.get_kv("note:todo")["done"] is True  # preserved future version


# ---------------------------------------------------------------------------
# 2. Gateway REST Endpoints Tests
# ---------------------------------------------------------------------------

def test_gateway_mesh_sync_pull(mesh_gateway_env):
    """Verify /api/v1/mesh/sync/pull returns all state entities from the central gateway."""
    client, state, _ = mesh_gateway_env

    req = {
        "node_id": "roaming_laptop",
        "since": None,
        "entities": ["profile", "kv_state", "zones"]
    }
    resp = client.post("/api/v1/mesh/sync/pull", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    payload = data["payload"]
    assert payload["profile"]["preferred_name"] == "Dyvorn"
    assert len(payload["zones"]) >= 2
    assert any(k["key"] == "note:initial" for k in payload["kv_state"])


def test_gateway_mesh_sync_push(mesh_gateway_env):
    """Verify /api/v1/mesh/sync/push ingests edge deltas and replays offline tasks."""
    client, state, _ = mesh_gateway_env

    push_req = {
        "node_id": "roaming_laptop",
        "payload": {
            "kv_state": [
                {"key": "note:laptop_scratch", "value": {"content": "Written on train"}, "updated_at": datetime.now(timezone.utc).isoformat()}
            ],
            "zones": [
                {"zone_id": "balcony", "display_name": "Outdoor Balcony", "metadata": {}}
            ],
            "offline_tasks": [
                {"id": "off_123", "goal": "mute audio", "result": {"muted": True}, "source_node": "roaming_laptop"}
            ]
        }
    }
    resp = client.post("/api/v1/mesh/sync/push", json=push_req)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "merged"
    counts = res_data["merged_counts"]
    assert counts["kv_state"] >= 1
    assert counts["zones"] >= 1
    assert counts["offline_tasks"] >= 1

    # Verify central state was updated
    assert state.get_kv("note:laptop_scratch")["content"] == "Written on train"
    zones = [z.zone_id for z in state.list_zones()]
    assert "balcony" in zones


def test_gateway_mesh_two_way_sync(mesh_gateway_env):
    """Verify /api/v1/mesh/sync performs atomic two-way synchronization in a single request."""
    client, state, _ = mesh_gateway_env

    sync_req = {
        "node_id": "phone_companion",
        "since": None,
        "client_payload": {
            "kv_state": [
                {"key": "note:mobile_idea", "value": {"content": "Mesh idea"}, "updated_at": datetime.now(timezone.utc).isoformat()}
            ]
        }
    }
    resp = client.post("/api/v1/mesh/sync", json=sync_req)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "synced"
    # Merged client payload on server
    assert res_data["merged_counts"]["kv_state"] >= 1
    # Received server payload in return
    server_p = res_data["server_payload"]
    assert server_p["profile"]["preferred_name"] == "Dyvorn"
    assert len(server_p["zones"]) >= 2


def test_gateway_mesh_nodes_inventory(mesh_gateway_env):
    """Verify /api/v1/mesh/nodes returns consolidated active satellites, mobile, and topology nodes."""
    client, _, _ = mesh_gateway_env

    # Register satellite heartbeat
    client.post("/api/v1/mesh/satellites/heartbeat", json={
        "node_id": "kitchen_speaker",
        "zone": "kitchen",
        "status": "listening",
        "uptime_seconds": 45.0
    })

    resp = client.get("/api/v1/mesh/nodes")
    assert resp.status_code == 200
    nodes = resp.json()
    assert len(nodes) >= 1
    kitchen = next((n for n in nodes if n["node_id"] == "kitchen_speaker"), None)
    assert kitchen is not None
    assert kitchen["zone"] == "kitchen"
    assert kitchen["status"] == "online"


def test_inter_device_message_dispatch(mesh_gateway_env):
    """Verify /api/v1/mesh/message routes commands to nodes, spatial zones, and broadcast."""
    import asyncio
    from unittest.mock import AsyncMock
    client, _, _ = mesh_gateway_env

    # 1. Attach mock socket for an edge node
    mock_socket = AsyncMock()
    connection_manager.edge_nodes["office_pc"] = mock_socket

    try:
        # 2. Dispatch direct message to office_pc
        msg = {
            "source_node": "phone_client",
            "target_node": "office_pc",
            "message_type": "command",
            "payload": {"goal": "lock workstation"}
        }
        res = client.post("/api/v1/mesh/message", json=msg)
        assert res.status_code == 200
        res_data = res.json()
        assert res_data["status"] == "delivered"
        assert "office_pc" in res_data["dispatched_to"]
        assert mock_socket.send_text.called

        # 3. Dispatch broadcast message to 'all'
        bcast_msg = {
            "source_node": "phone_client",
            "target_node": "all",
            "message_type": "notify",
            "payload": {"alert": "Doorbell pressed"}
        }
        b_res = client.post("/api/v1/mesh/message", json=bcast_msg)
        assert b_res.status_code == 200
        assert b_res.json()["status"] == "broadcasted"
    finally:
        connection_manager.edge_nodes.pop("office_pc", None)


# ---------------------------------------------------------------------------
# 3. MeshClient End-to-End Tests
# ---------------------------------------------------------------------------

def test_mesh_client_offline_fallback_enqueues_task(tmp_path):
    """Verify MeshClient enqueues offline tasks to SQLite when server is unreachable."""
    db_file = os.path.join(tmp_path, "test_client_offline.db")
    sm = StateManager(db_path=db_file)
    client = MeshClient(
        state_manager=sm,
        role="edge_node",
        main_server_url="http://127.0.0.1:9999",  # unreachable port
        node_id="laptop_edge"
    )

    def dummy_executor(goal, ctx):
        return {"result": f"Executed locally: {goal}"}

    res = client.execute_over_mesh(
        goal="calculate hashes",
        context={"speed": "fast"},
        local_executor=dummy_executor
    )

    assert res["execution_mode"] == "local_autonomous_fallback"
    assert "Executed locally" in res["result"]["result"]

    # Verify task was persisted into SQLite
    unsynced = sm.get_unsynced_offline_tasks()
    assert len(unsynced) == 1
    assert unsynced[0]["goal"] == "calculate hashes"


def test_mesh_client_sync_and_message_dispatch(tmp_path, mesh_gateway_env):
    """Verify MeshClient.sync and MeshClient.send_message communicate with live gateway."""
    from unittest.mock import patch, MagicMock

    test_client, state, _ = mesh_gateway_env
    db_file = os.path.join(tmp_path, "test_client_sync.db")
    sm = StateManager(db_path=db_file)
    mesh_client = MeshClient(
        state_manager=sm,
        role="edge_node",
        main_server_url="http://127.0.0.1:8000",
        node_id="laptop_vyrn"
    )

    # Enqueue local offline task and note on client
    sm.enqueue_offline_task("backup code", {"dir": "/src"}, {"done": True})
    sm.set_kv("note:client_note", {"title": "client_note", "content": "Local client content"})

    # Mock urllib calls in MeshClient to route through TestClient
    def mock_urlopen(req, timeout=None):
        url = req.full_url
        method = req.get_method()
        headers = dict(req.headers)
        data = req.data
        path = url.replace("http://127.0.0.1:8000", "")

        if method == "POST":
            json_body = json.loads(data.decode("utf-8")) if data else None
            resp = test_client.post(path, json=json_body)
        else:
            resp = test_client.get(path)

        mock_resp = MagicMock()
        mock_resp.status = resp.status_code
        mock_resp.read.return_value = resp.content
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        # 1. Perform bidirectional sync
        sync_res = mesh_client.sync()
        assert sync_res["status"] == "success"
        assert sync_res["mode"] == "two_way"

        # Client should now have server's profile and initial note
        assert sm.get_user_profile().preferred_name == "Dyvorn"
        assert sm.get_kv("note:initial") is not None

        # Server should now have client's note
        assert state.get_kv("note:client_note")["content"] == "Local client content"

        # Client's offline task should now be marked synced
        assert len(sm.get_unsynced_offline_tasks()) == 0

        # 2. Dispatch inter-device message
        msg_res = mesh_client.send_message(
            target_node="all",
            message_type="notify",
            payload={"msg": "Sync completed successfully"}
        )
        assert msg_res["status"] == "broadcasted"

        # 3. List mesh nodes
        nodes = mesh_client.list_mesh_nodes()
        assert isinstance(nodes, list)


def test_voice_satellite_mesh_message_and_sync_handling(tmp_path):
    """Verifies VoiceSatellite handles mesh device messages, broadcasts, and state updates cleanly."""
    from unittest.mock import MagicMock, patch
    from interfaces.voice.satellite import VoiceSatellite

    db_file = os.path.join(tmp_path, "sat_test.db")
    sm = StateManager(db_path=db_file)

    sat = VoiceSatellite(
        node_id="sat_lab",
        server_url="http://127.0.0.1:8000",
        zone="lab",
        state_manager=sm
    )
    sat.voice_out = MagicMock()

    # 1. Direct speak message
    speak_msg = {
        "type": "mesh_device_message",
        "message": {
            "message_type": "speak",
            "payload": {"text": "Calibration complete."}
        }
    }
    res = sat.handle_edge_message(speak_msg)
    assert res is None
    sat.voice_out.synthesize_and_play.assert_called_with("Calibration complete.", blocking=False)

    # 2. Interrupt message
    interrupt_msg = {
        "type": "mesh_device_message",
        "message": {
            "message_type": "interrupt",
            "payload": {}
        }
    }
    sat.handle_edge_message(interrupt_msg)
    sat.voice_out.interrupt.assert_called_once()

    # 3. Sync message
    with patch.object(sat, "sync_mesh_state") as mock_sync:
        sync_msg = {
            "type": "mesh_device_message",
            "message": {
                "message_type": "sync",
                "payload": {}
            }
        }
        res_sync = sat.handle_edge_message(sync_msg)
        assert res_sync is not None
        assert res_sync["type"] == "sync_ack"
        assert res_sync["node_id"] == "sat_lab"

    # 4. Command message
    with patch.object(sat, "_local_fallback_executor", return_value={"status": "executed"}) as mock_exec:
        cmd_msg = {
            "type": "mesh_device_message",
            "message": {
                "message_type": "command",
                "payload": {"command": "get status"}
            }
        }
        res_cmd = sat.handle_edge_message(cmd_msg)
        assert res_cmd is not None
        assert res_cmd["type"] == "command_result"
        assert isinstance(res_cmd["result"], dict)
        assert res_cmd["result"]["status"] == "executed"
        mock_exec.assert_called_with("get status")

    # 5. Broadcast MESH_DEVICE_MESSAGE
    sat.voice_out.reset_mock()
    bcast_msg = {
        "event": "MESH_DEVICE_MESSAGE",
        "data": {
            "message_type": "speak",
            "payload": {"text": "All nodes alert."}
        }
    }
    sat.handle_edge_message(bcast_msg)
    sat.voice_out.synthesize_and_play.assert_called_with("All nodes alert.", blocking=False)


def test_mobile_companion_mesh_sync_and_messaging(mesh_gateway_env):
    """Verifies MobileCompanionClient delta synchronization, node matrix query, and mesh messaging."""
    from unittest.mock import MagicMock, patch
    from interfaces.mobile.companion import MobileCompanionClient

    test_client, state, app = mesh_gateway_env

    mobile = MobileCompanionClient(
        server_url="http://127.0.0.1:8000",
        client_id="mobile_test_device"
    )

    def mock_urlopen(req, timeout=None):
        url = req.full_url
        method = req.get_method()
        data = req.data
        path = url.replace("http://127.0.0.1:8000", "")

        if method == "POST":
            json_body = json.loads(data.decode("utf-8")) if data else None
            resp = test_client.post(path, json=json_body)
        else:
            resp = test_client.get(path)

        mock_resp = MagicMock()
        mock_resp.status = resp.status_code
        mock_resp.read.return_value = resp.content
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        # 1. Sync deltas
        sync_res = mobile.sync()
        assert sync_res["status"] in ("ok", "success")
        payload = sync_res["payload"]
        assert len(payload["zones"]) >= 2
        assert any(z["zone_id"] == "studio" for z in payload["zones"])

        # 2. List mesh nodes
        nodes = mobile.list_mesh_nodes()
        assert isinstance(nodes, list)

        # 3. Send inter-device message
        msg_res = mobile.send_mesh_message(
            target_node="all",
            message_type="speak",
            payload={"text": "Broadcast from mobile companion."}
        )
        assert msg_res["status"] == "broadcasted"

