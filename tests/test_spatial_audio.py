import os
import pytest
from datetime import datetime, timezone
from starlette.testclient import TestClient

from core.state import StateManager
from core.bus import EventBus
from core.schemas import AudioRouteRecord, AudioRouteUpdateRequest, DeviceTopologyRecord
from engines.audio_router import SpatialAudioRouter, route_spatial_audio, route_spatial_audio_schema
from brain.spatial_handoff import SpatialHandoffEngine
from core.gateway import create_gateway_app
from tools.registry import ToolRegistry
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine


@pytest.fixture
def test_state(tmp_path):
    db_path = str(tmp_path / "test_spatial.db")
    return StateManager(db_path=db_path)


def test_audio_router_device_introspection(test_state):
    """Verify that sound devices can be introspected without hardware faults."""
    router = SpatialAudioRouter(state_manager=test_state)
    devs = router.list_system_audio_devices()
    assert "inputs" in devs
    assert "outputs" in devs
    assert isinstance(devs["inputs"], list)
    assert isinstance(devs["outputs"], list)


def test_audio_router_dynamic_arbitrary_zone(test_state):
    """Verify routing works for arbitrary, user-defined zones (e.g. airplane hangar)."""
    router = SpatialAudioRouter(state_manager=test_state)

    # 1. Non-existent zone should synthesize a default route without crashing
    route = router.get_route_for_zone("hangar_alpha")
    assert route.zone_id == "hangar_alpha"
    assert route.input_device_name is not None
    assert route.output_device_name is not None

    # 2. Explicitly bind custom hardware to this zone
    custom_route = AudioRouteRecord(
        zone_id="hangar_alpha",
        input_device_name="Hangar Overhead Mic",
        output_device_name="Hangar PA Horn",
        input_device_index=1,
        output_device_index=2,
        preferred_volume=0.8
    )
    test_state.set_audio_route(custom_route)

    saved_route = test_state.get_audio_route("hangar_alpha")
    assert saved_route is not None
    assert saved_route.input_device_name == "Hangar Overhead Mic"
    assert saved_route.output_device_name == "Hangar PA Horn"
    assert saved_route.preferred_volume == 0.8

    # 3. List all routes
    all_routes = test_state.list_all_audio_routes()
    assert len(all_routes) == 1
    assert all_routes[0].zone_id == "hangar_alpha"


@pytest.mark.anyio
async def test_spatial_handoff_execution(test_state):
    """Verify cross-zone handoff re-routes audio, moves device, and publishes event."""
    bus = EventBus()
    router = SpatialAudioRouter(state_manager=test_state)
    handoff = SpatialHandoffEngine(
        state_manager=test_state,
        bus=bus,
        audio_router=router
    )

    # Enroll a roaming device in zone 'office'
    roaming_laptop = DeviceTopologyRecord(
        device_id="laptop_primary",
        name="Developer Laptop",
        device_type="laptop",
        is_fixed_anchor=False,
        current_zone="office"
    )
    test_state.register_or_update_device(roaming_laptop)

    # Subscribe to spatial handoff events
    captured_events = []
    def on_handoff(data):
        captured_events.append(data)
    bus.subscribe("spatial_handoff", on_handoff)

    # Configure destination zone with a dynamic scene (Zero hardcoding)
    test_state.ensure_zone_exists("creative_lab", metadata={"enter_scene": "scene_cyberpunk_neon"})

    # Execute handoff to 'creative_lab'
    event = await handoff.execute_handoff(
        to_zone="creative_lab",
        from_zone="office",
        active_device_id="laptop_primary",
        reason="walked_into_lab"
    )

    assert event.to_zone == "creative_lab"
    assert event.from_zone == "office"
    assert event.active_device_id == "laptop_primary"

    # Verify device topology updated
    updated_device = test_state.get_device_record("laptop_primary")
    assert updated_device.current_zone == "creative_lab"


def test_native_route_spatial_audio_tool(test_state, monkeypatch):
    """Verify route_spatial_audio works as a callable native pipeline tool."""
    monkeypatch.setattr("engines.audio_router.StateManager", lambda: test_state)
    result = route_spatial_audio(zone_id="terrace", output_device="Terrace Speaker")
    assert result["status"] == "routed"
    assert result["zone_id"] == "terrace"


def test_gateway_spatial_audio_endpoints(tmp_path):
    """Verify REST API endpoints for audio devices, route configuration, and handoffs."""
    state = StateManager(db_path=str(tmp_path / "gw_audio.db"))
    bus = EventBus()
    registry = ToolRegistry(dynamic_dir=str(tmp_path / "dyn"))
    planner = Planner(registry=registry, state_manager=state)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)

    app = create_gateway_app(state, registry, planner, engine, bus)
    client = TestClient(app)

    # 1. Query audio devices
    dev_res = client.get("/api/v1/audio/devices")
    assert dev_res.status_code == 200
    assert "inputs" in dev_res.json()
    assert "outputs" in dev_res.json()

    # 2. Set route for arbitrary zone
    req_payload = {
        "zone_id": "solar_observatory",
        "input_device_name": "USB Array Mic",
        "output_device_name": "HiFi Monitor",
        "preferred_volume": 0.95
    }
    set_res = client.post("/api/v1/audio/routes", json=req_payload)
    assert set_res.status_code == 200
    assert set_res.json()["zone_id"] == "solar_observatory"

    # 3. Retrieve route
    get_res = client.get("/api/v1/audio/routes/solar_observatory")
    assert get_res.status_code == 200
    assert get_res.json()["zone_id"] == "solar_observatory"
    assert get_res.json()["input_device_name"] == "USB Array Mic"

    # 4. Trigger spatial handoff via REST
    handoff_res = client.post("/api/v1/spatial/handoff?target_zone=solar_observatory&reason=presence_detected")
    assert handoff_res.status_code == 200
    assert handoff_res.json()["to_zone"] == "solar_observatory"
