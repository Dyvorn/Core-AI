import os
import json
import pytest
import asyncio
from starlette.testclient import TestClient

from core.service import ServiceManager, get_host_vitals
from core.discovery import LANBeacon, discover_core_servers
from tools.registry import ToolRegistry
from tools.remote_dispatcher import RemoteToolDispatcher
from core.state import StateManager
from core.bus import EventBus
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.gateway import create_gateway_app, connection_manager

def test_service_manager_lan_ip_and_vitals():
    lan_ip = ServiceManager.get_lan_ip()
    assert isinstance(lan_ip, str)
    assert len(lan_ip.split(".")) == 4

    vitals = get_host_vitals()
    assert vitals["cpu_count"] >= 1
    assert isinstance(vitals["platform"], str)
    assert vitals["total_ram_gb"] >= 0.0
    assert "ram_used_percent" in vitals

def test_service_manager_systemd_generator(tmp_path):
    sm = ServiceManager(root_dir=str(tmp_path))
    unit = sm.generate_systemd_service(user="coreoperator", port=8000)
    assert "[Unit]" in unit
    assert "[Service]" in unit
    assert "User=coreoperator" in unit
    assert "ExecStart=" in unit
    assert "Restart=always" in unit
    assert "WantedBy=multi-user.target" in unit

def test_service_manager_metrics_dict(tmp_path):
    db_path = str(tmp_path / "core_ai.db")
    state = StateManager(db_path=db_path)
    state.ensure_zone_exists("lab", display_name="AI Lab")
    registry = ToolRegistry(dynamic_dir=str(tmp_path / "dynamic"))

    metrics = ServiceManager.get_system_metrics(
        state_manager=state,
        registry=registry,
        root_dir=str(tmp_path),
        port=8000
    )

    assert "process" in metrics
    assert "host" in metrics
    assert "storage" in metrics
    assert "network" in metrics
    assert "system" in metrics
    assert metrics["storage"]["zones_count"] >= 1
    assert metrics["network"]["port"] == 8000

def test_lan_discovery_beacon_and_scanner():
    test_port = 18008
    beacon = LANBeacon(
        service_port=8000,
        discovery_port=test_port,
        broadcast_interval=0.5,
        server_info_provider=lambda: {"active_user": "DyvornTest", "active_model": "heuristic"}
    )
    beacon.start()
    try:
        # Give beacon thread a moment to bind and announce
        discovered = discover_core_servers(timeout=1.0, discovery_port=test_port)
        assert len(discovered) >= 1
        found = discovered[0]
        assert found["magic"] == "CORE_AI_BEACON"
        assert found["service"] == "core_ai_gateway"
        assert found["active_user"] == "DyvornTest"
        assert found["port"] == 8000
    finally:
        beacon.stop()

def test_gateway_server_endpoints(tmp_path):
    os.environ["CORE_DISABLE_DISCOVERY"] = "1"
    db_path = str(tmp_path / "test_gw.db")
    state = StateManager(db_path=db_path)
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
        # 1. /api/v1/server/status
        status_resp = client.get("/api/v1/server/status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["status"] == "online"
        assert "lan_ip" in status_data
        assert status_data["port"] == 8000

        # 2. /api/v1/server/metrics
        metrics_resp = client.get("/api/v1/server/metrics")
        assert metrics_resp.status_code == 200
        metrics_data = metrics_resp.json()
        assert "process" in metrics_data
        assert "host" in metrics_data
        assert "storage" in metrics_data
        assert "network" in metrics_data

def test_edge_node_dynamic_tool_registration_and_cleanup(tmp_path):
    os.environ["CORE_DISABLE_DISCOVERY"] = "1"
    db_path = str(tmp_path / "test_edge_tools.db")
    state = StateManager(db_path=db_path)
    registry = ToolRegistry(dynamic_dir=str(tmp_path / "dyn"))
    dispatcher = RemoteToolDispatcher(registry=registry)
    bus = EventBus()
    planner = Planner(registry=registry, state_manager=state, model_name="heuristic")
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)

    app = create_gateway_app(
        state_manager=state,
        registry=registry,
        planner=planner,
        pipeline_engine=engine,
        bus=bus,
        remote_dispatcher=dispatcher
    )

    node_id = "phone_client_test"
    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/nodes/{node_id}") as ws:
            # Send registration handshake with dynamic tools
            ws.send_text(json.dumps({
                "type": "register",
                "data": {
                    "node_id": node_id,
                    "device_type": "phone",
                    "capabilities": ["mic", "haptic"],
                    "tools": [
                        {
                            "name": "trigger_phone_haptic",
                            "description": "Vibrate phone motor",
                            "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}}
                        }
                    ]
                }
            }))
            resp_str = ws.receive_text()
            resp = json.loads(resp_str)
            assert resp["type"] == "registered"
            assert resp["registered_tools_count"] == 1

            # Verify tool exists in active registry
            assert registry.has_tool("trigger_phone_haptic")

        # Now WebSocket is closed/disconnected
        # Verify tool was cleanly deregistered and removed from registry (no ghost tools)
        assert not registry.has_tool("trigger_phone_haptic")
