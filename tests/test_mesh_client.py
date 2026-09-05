import os
import json
import pytest
from core.state import StateManager
from core.schemas import UserProfile, ZoneRecord, DeviceTopologyRecord, AudioRouteRecord
from core.mesh_client import MeshClient

def test_mesh_client_configuration(tmp_path):
    db_path = str(tmp_path / "mesh_test.db")
    state = StateManager(db_path=db_path)
    client = MeshClient(state_manager=state)

    # Defaults
    assert client.role == "main_server"

    # Switch configuration
    client.save_configuration(role="edge_node", main_server_url="http://100.64.0.1:8000")
    assert client.role == "edge_node"
    assert client.main_server_url == "http://100.64.0.1:8000"

    # Reload from state
    client2 = MeshClient(state_manager=state)
    assert client2.role == "edge_node"
    assert client2.main_server_url == "http://100.64.0.1:8000"

def test_mesh_client_local_execution(tmp_path):
    db_path = str(tmp_path / "mesh_local.db")
    state = StateManager(db_path=db_path)
    client = MeshClient(state_manager=state, role="main_server")

    executed = []
    def dummy_exec(goal, ctx):
        executed.append((goal, ctx))
        return {"status": "success", "goal": goal}

    res = client.execute_over_mesh("Turn off lights", local_executor=dummy_exec)
    assert res["status"] == "success"
    assert len(executed) == 1
    assert executed[0][0] == "Turn off lights"

def test_mesh_client_autonomous_offline_fallback(tmp_path):
    db_path = str(tmp_path / "mesh_fallback.db")
    state = StateManager(db_path=db_path)
    # Point to non-existent port to simulate offline server
    client = MeshClient(state_manager=state, role="edge_node", main_server_url="http://127.0.0.1:59999")

    fallback_notices = []
    def on_notice(msg):
        fallback_notices.append(msg)

    def dummy_local(goal, ctx):
        return {"status": "completed_locally", "goal": goal}

    res = client.execute_over_mesh(
        goal="Check workshop temperature",
        context={"zone": "workshop"},
        local_executor=dummy_local,
        on_fallback_notice=on_notice
    )

    # Must fall back gracefully without raising an exception or crashing
    assert res["execution_mode"] == "local_autonomous_fallback"
    assert len(fallback_notices) == 1
    assert "unreachable" in fallback_notices[0]
    assert res["result"]["status"] == "completed_locally"
    assert len(client.offline_buffer) == 1
    assert client.offline_buffer[0]["goal"] == "Check workshop temperature"

def test_mesh_state_bundle_export_and_import(tmp_path):
    # Server A
    db_a = str(tmp_path / "server_a.db")
    state_a = StateManager(db_path=db_a)
    state_a.set_user_preferred_name("Dyvorn", aliases=["Vyrn", "Refined"])
    state_a.ensure_zone_exists("sanctuary", display_name="Living Sanctuary")
    state_a.ensure_zone_exists("hangar", display_name="Airplane Hangar")
    state_a.set_audio_route(AudioRouteRecord(
        zone_id="sanctuary",
        input_device_name="Ceiling Mic",
        output_device_name="HiFi Monitors"
    ))

    client_a = MeshClient(state_manager=state_a)
    bundle_path = str(tmp_path / "state_bundle.json")
    bundle = client_a.export_state_bundle(export_path=bundle_path)

    assert bundle["profile"]["preferred_name"] == "Dyvorn"
    assert any(z["zone_id"] == "hangar" for z in bundle["zones"])
    assert any(r["zone_id"] == "sanctuary" for r in bundle["audio_routes"])
    assert os.path.exists(bundle_path)

    # Server B (New Machine)
    db_b = str(tmp_path / "server_b.db")
    state_b = StateManager(db_path=db_b)
    client_b = MeshClient(state_manager=state_b)

    counts = client_b.import_state_bundle(bundle_path)
    assert counts["zones"] >= 2
    assert counts["audio_routes"] >= 1

    # Verify Server B has Dyvorn's data
    prof_b = state_b.get_user_profile()
    assert prof_b.preferred_name == "Dyvorn"
    assert "Vyrn" in prof_b.aliases
    assert state_b.get_audio_route("sanctuary").output_device_name == "HiFi Monitors"
