import pytest
import os
from starlette.testclient import TestClient

from core.state import StateManager
from core.bus import EventBus
from tools.registry import ToolRegistry
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.gateway import create_gateway_app

@pytest.fixture
def gateway_client(tmp_path):
    state_file = os.path.join(tmp_path, "test_gate.db")
    state = StateManager(db_path=state_file)
    bus = EventBus()
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry, state_manager=state)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)

    app = create_gateway_app(
        state_manager=state,
        registry=registry,
        planner=planner,
        pipeline_engine=engine,
        bus=bus
    )
    return TestClient(app), state

def test_gateway_health_endpoint(gateway_client):
    client, _ = gateway_client
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["version"] == "2.0.0"

def test_gateway_user_profile_crud(gateway_client):
    client, state = gateway_client
    
    # 1. Fetch initial profile on fresh install (blank-slate default)
    res1 = client.get("/api/v1/profile")
    assert res1.status_code == 200
    assert res1.json()["preferred_name"] == "User"

    # 2. Update to custom user handle and preferences
    res2 = client.post("/api/v1/profile", json={"preferred_name": "Dyvorn", "preferred_tone": "focused"})
    assert res2.status_code == 200
    assert res2.json()["preferred_name"] == "Dyvorn"
    assert res2.json()["preferred_tone"] == "focused"

    # 3. Verify persisted in DB
    db_profile = state.get_user_profile()
    assert db_profile.preferred_name == "Dyvorn"

def test_gateway_dynamic_zone_provisioning(gateway_client):
    client, state = gateway_client

    # 1. Initially zones list can be empty or default
    res = client.get("/api/v1/zones")
    assert res.status_code == 200

    # 2. Dynamically declare a new zone on-the-fly without hardcoded assumptions
    create_res = client.post("/api/v1/zones?zone_id=custom_workshop&display_name=My%20Custom%20Workshop")
    assert create_res.status_code == 200
    assert create_res.json()["zone_id"] == "custom_workshop"

    # 3. Verify it shows up in list_zones
    list_res = client.get("/api/v1/zones")
    assert list_res.status_code == 200
    zone_ids = [z["zone_id"] for z in list_res.json()]
    assert "custom_workshop" in zone_ids



def test_gateway_device_anchoring(gateway_client):
    client, state = gateway_client

    # Anchor a studio mic
    req = {
        "device_id": "studio_mic_01",
        "zone": "home/indoor/studio",
        "is_fixed_anchor": True
    }
    res = client.post("/api/v1/devices/anchor", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["current_zone"] == "home/indoor/studio"
    assert data["is_fixed_anchor"] is True

    # Check listing
    list_res = client.get("/api/v1/devices")
    assert list_res.status_code == 200
    devices = list_res.json()
    assert len(devices) == 1
    assert devices[0]["device_id"] == "studio_mic_01"

def test_gateway_hud_card_dispatch(gateway_client):
    client, _ = gateway_client
    card = {
        "card_id": "test-card-1",
        "title": "Welcome Home",
        "subtitle": "Ambient card for mirror",
        "metrics": {"LIGHTS": "ON"}
    }
    res = client.post("/api/v1/hud/card", json=card)
    assert res.status_code == 200
    assert res.json()["status"] == "dispatched"

def test_gateway_device_enrollment_owner_and_guest(gateway_client):
    client, state = gateway_client

    # 1. Enroll Owner Laptop with valid secret
    owner_req = {
        "device_id": "laptop_thinkpad",
        "device_name": "Lennard ThinkPad",
        "device_type": "laptop",
        "target_zone": "home/indoor/studio",
        "requested_trust_tier": "owner",
        "auth_secret": "core_sovereign_secret"
    }
    res1 = client.post("/api/v1/devices/enroll", json=owner_req)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["assigned_trust_tier"] == "owner"
    assert data1["status"] == "enrolled"

    # 2. Enroll Guest phone with no secret
    guest_req = {
        "device_id": "phone_guest_friend",
        "device_name": "Friend Phone",
        "device_type": "phone",
        "target_zone": "home/indoor/living_room",
        "requested_trust_tier": "guest"
    }
    res2 = client.post("/api/v1/devices/enroll", json=guest_req)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["assigned_trust_tier"] == "guest"

def test_gateway_guest_security_tier_rejection(gateway_client):
    client, _ = gateway_client

    # Guest tries to read personal profile -> must be denied (403)
    res = client.get("/api/v1/profile", headers={"X-Trust-Tier": "guest"})
    assert res.status_code == 403
    assert "Security Protection" in res.json()["detail"]

    # Guest tries to update personal profile -> must be denied (403)
    res_update = client.post("/api/v1/profile", json={"preferred_name": "Hacker"}, headers={"X-Trust-Tier": "guest"})
    assert res_update.status_code == 403

