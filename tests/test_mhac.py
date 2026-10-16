import os
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from core.schemas import (
    ClientComputeSignature,
    MHACHandshakeRequest,
    MHACHandshakeResponse,
    MHACProbeRequest,
    MHACPullRequest
)
from brain.mhac import MHACBroker, get_mhac_broker
from brain.model_router import ModelRouter
from core.state import StateManager
from core.bus import EventBus
from tools.registry import ToolRegistry
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.gateway import create_gateway_app


# 1. Hardware-Aware Scoring Tests
def test_client_compute_signature_scoring():
    # Weak host laptop (2 cores, 16GB RAM, no GPU)
    # Score = (2 * 1.0) + (16 * 0.5) = 10.0
    host_sig = ClientComputeSignature(
        node_id="host",
        device_name="Central Host",
        device_type="server",
        cpu_cores=2,
        ram_total_gb=16.0,
        has_gpu=False
    )
    assert host_sig.calculate_score() == 10.0

    # Strong workstation (8 cores, 32GB RAM, RTX 4080 with 16GB VRAM)
    # Score = (8 * 1.0) + (32 * 0.5) + 50.0 + (16 * 5.0) = 8 + 16 + 50 + 80 = 154.0
    workstation_sig = ClientComputeSignature(
        node_id="workstation-alpha",
        device_name="Dev Workstation RTX",
        device_type="workstation",
        cpu_cores=8,
        ram_total_gb=32.0,
        has_gpu=True,
        gpu_name="NVIDIA GeForce RTX 4080",
        vram_gb=16.0,
        ollama_endpoint="http://192.168.1.150:11434"
    )
    assert workstation_sig.calculate_score() == 154.0

    # Mobile phone / low-spec tablet (4 cores, 4GB RAM, no GPU)
    # Score = (4 * 1.0) + (4 * 0.5) = 6.0
    phone_sig = ClientComputeSignature(
        node_id="phone-client",
        device_name="Mobile Companion",
        device_type="mobile",
        cpu_cores=4,
        ram_total_gb=4.0,
        has_gpu=False
    )
    assert phone_sig.calculate_score() == 6.0


# 2. Broker Handshake & Capability Evaluation Tests
def test_mhac_broker_standalone_mode():
    broker = MHACBroker(host_score_override=10.0)
    phone_sig = ClientComputeSignature(
        node_id="phone-client",
        device_name="Mobile Companion",
        cpu_cores=4,
        ram_total_gb=4.0,
        has_gpu=False
    )

    resp = broker.evaluate_handshake(phone_sig)
    assert resp.status == "standalone"
    assert resp.active_compute_node == "host"
    assert resp.delegated_endpoint is None
    assert broker.get_delegated_endpoint() is None
    assert "does not exceed host" in resp.notice_message


def test_mhac_broker_accelerated_workstation_mode():
    broker = MHACBroker(host_score_override=10.0)
    workstation_sig = ClientComputeSignature(
        node_id="workstation-alpha",
        device_name="Dev Workstation RTX",
        cpu_cores=8,
        ram_total_gb=32.0,
        has_gpu=True,
        gpu_name="RTX 4080",
        vram_gb=16.0,
        ollama_endpoint="http://192.168.1.150:11434"
    )

    # Mock probe to return llama3.1:8b present
    with patch.object(broker, "probe_client_models", return_value=["llama3.1:8b", "nomic-embed-text"]):
        resp = broker.evaluate_handshake(workstation_sig, preferred_models=["llama3.1:8b", "llama3.2:3b"])
        assert resp.status == "accelerated_workstation"
        assert resp.active_compute_node == "workstation-alpha"
        assert resp.delegated_endpoint == "http://192.168.1.150:11434"
        assert resp.target_model == "llama3.1:8b"
        assert "Offloading execution layer to local GPU" in resp.notice_message

        # Verify broker runtime state
        assert broker.get_delegated_endpoint() == "http://192.168.1.150:11434"
        assert broker.get_delegated_model() == "llama3.1:8b"
        status = broker.get_status()
        assert status["mode"] == "accelerated"
        assert status["active_compute_node"] == "workstation-alpha"


def test_mhac_broker_missing_model_handshake():
    broker = MHACBroker(host_score_override=10.0)
    workstation_sig = ClientComputeSignature(
        node_id="workstation-alpha",
        device_name="Dev Workstation RTX",
        cpu_cores=8,
        ram_total_gb=32.0,
        has_gpu=True,
        gpu_name="RTX 4080",
        vram_gb=16.0,
        ollama_endpoint="http://192.168.1.150:11434"
    )

    # Mock probe returning different model (missing llama3.1:8b)
    with patch.object(broker, "probe_client_models", return_value=["phi3:mini"]):
        resp = broker.evaluate_handshake(workstation_sig, preferred_models=["llama3.1:8b"])
        assert resp.status == "missing_model_handshake"
        assert resp.active_compute_node == "host"
        assert resp.delegated_endpoint is None
        assert "llama3.1:8b" in resp.missing_models
        assert "Would you like me to pull it, or should I fallback" in resp.notice_message

        # State remains safe on host
        assert broker.get_delegated_endpoint() is None
        assert broker.get_delegated_model() is None


def test_mhac_broker_reset_delegation():
    broker = MHACBroker(host_score_override=10.0)
    broker._active_compute_node = "workstation-alpha"
    broker._delegated_endpoint = "http://192.168.1.150:11434"
    broker._delegated_model = "llama3.1:8b"

    broker.reset_delegation()
    assert broker.get_delegated_endpoint() is None
    assert broker.get_delegated_model() is None
    assert broker.get_status()["mode"] == "standalone"
    assert broker.get_status()["active_compute_node"] == "host"


# 3. Model Router Integration with MHAC
def test_model_router_mhac_dynamic_routing(tmp_path):
    db_file = os.path.join(tmp_path, "router_test.db")
    sm = StateManager(db_path=db_file)
    router = ModelRouter(state_manager=sm)

    # Initially standalone: returns default endpoint
    broker = get_mhac_broker()
    broker.reset_delegation()
    assert router.get_ollama_api_base() == os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434")

    # Delegate to remote workstation
    broker._active_compute_node = "workstation-beta"
    broker._delegated_endpoint = "http://192.168.1.200:11434"
    broker._delegated_model = "llama3.1:8b"

    try:
        with patch.object(broker, "check_client_liveness", return_value=True):
            assert router.get_ollama_api_base() == "http://192.168.1.200:11434"
            clean_goal, resolved_model = router.resolve_model("analyze log files")
            assert resolved_model == "ollama/llama3.1:8b"
            assert clean_goal == "analyze log files"
    finally:
        broker.reset_delegation()


# 4. Universal Gateway MHAC Endpoints
@pytest.fixture
def mhac_test_app(tmp_path):
    db_file = os.path.join(tmp_path, "gate_mhac.db")
    state = StateManager(db_path=db_file)
    bus = EventBus()
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry, state_manager=state)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)
    broker = MHACBroker(host_score_override=10.0)

    app = create_gateway_app(
        state_manager=state,
        registry=registry,
        planner=planner,
        pipeline_engine=engine,
        bus=bus,
        mhac_broker=broker
    )
    return TestClient(app), broker


def test_gateway_mhac_endpoints(mhac_test_app):
    client, broker = mhac_test_app

    # 1. Health check includes MHAC keys
    health_resp = client.get("/api/v1/health")
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert "mhac_mode" in h_data
    assert "mhac_active_node" in h_data
    assert h_data["mhac_mode"] == "standalone"
    assert h_data["mhac_active_node"] == "host"

    # 2. Status endpoint
    status_resp = client.get("/api/v1/mhac/status")
    assert status_resp.status_code == 200
    s_data = status_resp.json()
    assert s_data["mode"] == "standalone"
    assert s_data["host"]["compute_score"] == 10.0

    # 3. Handshake endpoint (Accelerated)
    with patch.object(broker, "probe_client_models", return_value=["llama3.1:8b", "qwen2.5:7b"]):
        payload = {
            "client_signature": {
                "node_id": "desktop-rtx",
                "device_name": "Studio Desktop",
                "device_type": "workstation",
                "cpu_cores": 16,
                "ram_total_gb": 64.0,
                "has_gpu": True,
                "gpu_name": "RTX 4090",
                "vram_gb": 24.0,
                "ollama_endpoint": "http://192.168.1.180:11434"
            },
            "preferred_models": ["llama3.1:8b"]
        }
        hs_resp = client.post("/api/v1/mhac/handshake", json=payload)
        assert hs_resp.status_code == 200
        hs_data = hs_resp.json()
        assert hs_data["status"] == "accelerated_workstation"
        assert hs_data["active_compute_node"] == "desktop-rtx"
        assert hs_data["delegated_endpoint"] == "http://192.168.1.180:11434"
        assert hs_data["target_model"] == "llama3.1:8b"

        # Check health reflects accelerated mode
        h2 = client.get("/api/v1/health").json()
        assert h2["mhac_mode"] == "accelerated"
        assert h2["mhac_active_node"] == "desktop-rtx"

    # 4. Probe endpoint
    with patch.object(broker, "probe_client_models", return_value=["llama3.1:8b"]):
        probe_resp = client.post("/api/v1/mhac/probe", json={"endpoint": "http://192.168.1.180:11434"})
        assert probe_resp.status_code == 200
        p_data = probe_resp.json()
        assert p_data["installed_models"] == ["llama3.1:8b"]
        assert p_data["count"] == 1

    # 5. Pull endpoint
    with patch.object(broker, "trigger_client_model_pull", return_value={"status": "success", "message": "Pulled model"}):
        pull_resp = client.post("/api/v1/mhac/pull", json={
            "endpoint": "http://192.168.1.180:11434",
            "model_name": "llama3.2:3b"
        })
        assert pull_resp.status_code == 200
        assert pull_resp.json()["status"] == "success"

    # 6. Reset endpoint
    reset_resp = client.post("/api/v1/mhac/reset")
    assert reset_resp.status_code == 200
    r_data = reset_resp.json()
    assert r_data["status"] == "ok"
    assert r_data["active_compute_node"] == "host"

    # Health reflects return to standalone
    h3 = client.get("/api/v1/health").json()
    assert h3["mhac_mode"] == "standalone"
    assert h3["mhac_active_node"] == "host"


# 5. Workload Matrix & Asymmetric Transition Tests
def test_mhac_workload_matrix():
    broker = MHACBroker(host_score_override=10.0)
    matrix = broker.get_workload_matrix()

    assert matrix["mode"] == "standalone"
    assert matrix["active_compute_node"] == "host"
    assert "proactive_watcher_daemon" in matrix["server_node"]["workloads"]
    assert "context_sentinel_track2" in matrix["server_node"]["workloads"]
    assert len(matrix["pc_node"]["workloads"]) == 0

    # Accelerate with a workstation
    workstation_sig = ClientComputeSignature(
        node_id="studio-pc",
        device_name="Studio Workstation",
        cpu_cores=16,
        ram_total_gb=64.0,
        has_gpu=True,
        gpu_name="RTX 4090",
        vram_gb=24.0,
        ollama_endpoint="http://192.168.1.199:11434"
    )
    with patch.object(broker, "probe_client_models", return_value=["llama3.1:8b"]):
        broker.evaluate_handshake(workstation_sig)
        acc_matrix = broker.get_workload_matrix()
        assert acc_matrix["mode"] == "accelerated"
        assert acc_matrix["active_compute_node"] == "studio-pc"
        assert "interactive_llm_reasoning" in acc_matrix["pc_node"]["workloads"]
        assert "foreground_spoken_to_track1" in acc_matrix["pc_node"]["workloads"]
        assert acc_matrix["pc_node"]["target_model"] == "llama3.1:8b"


def test_mhac_failover_and_recovery():
    import time
    bus = EventBus()
    transitions = []
    bus.subscribe("mhac_events", lambda e: transitions.append(e))
    bus.start_listening()

    try:
        broker = MHACBroker(host_score_override=10.0, bus=bus)
        workstation_sig = ClientComputeSignature(
            node_id="dev-rig",
            device_name="Developer Rig RTX",
            cpu_cores=12,
            ram_total_gb=32.0,
            has_gpu=True,
            gpu_name="RTX 3090",
            vram_gb=24.0,
            ollama_endpoint="http://192.168.1.77:11434"
        )

        with patch.object(broker, "probe_client_models", return_value=["llama3.1:8b"]):
            broker.evaluate_handshake(workstation_sig)
            assert broker.get_status()["mode"] == "accelerated"
            assert broker.get_active_devices_count() == 1

            # Simulate workstation sleep / network drop -> failover
            failover_res = broker.failover_to_host(reason="Workstation went to sleep")
            assert failover_res["status"] == "failed_over"
            assert failover_res["active_compute_node"] == "host"
            assert broker.get_status()["mode"] == "standalone"
            assert "dev-rig" in broker._dormant_clients

            # Verify event was published
            time.sleep(0.05)
            assert any(t.get("event_type") == "mhac_transition" for t in transitions)

            # Simulate workstation waking back up -> recovery
            with patch.object(broker, "check_client_liveness", return_value=True):
                recovered = broker.recover_delegation("dev-rig")
                assert recovered is True
                assert broker.get_status()["mode"] == "accelerated"
                assert broker.get_status()["active_compute_node"] == "dev-rig"
    finally:
        bus.stop_listening()


def test_mhac_heartbeat_step():
    broker = MHACBroker(host_score_override=10.0)
    workstation_sig = ClientComputeSignature(
        node_id="dev-rig",
        device_name="Developer Rig RTX",
        cpu_cores=12,
        ram_total_gb=32.0,
        has_gpu=True,
        gpu_name="RTX 3090",
        vram_gb=24.0,
        ollama_endpoint="http://192.168.1.77:11434"
    )

    with patch.object(broker, "probe_client_models", return_value=["llama3.1:8b"]):
        broker.evaluate_handshake(workstation_sig)

        # 1. Heartbeat healthy
        with patch.object(broker, "check_client_liveness", return_value=True):
            hb = broker.heartbeat_step()
            assert hb["status"] == "healthy"
            assert hb["mode"] == "accelerated"

        # 2. Heartbeat detects unreachable -> failover
        with patch.object(broker, "check_client_liveness", return_value=False):
            hb_fail = broker.heartbeat_step()
            assert hb_fail["status"] == "failed_over"
            assert broker.get_status()["mode"] == "standalone"

        # 3. Heartbeat in standalone detects dormant node back online -> recovery
        with patch.object(broker, "check_client_liveness", return_value=True):
            hb_rec = broker.heartbeat_step()
            assert hb_rec["status"] == "recovered"
            assert hb_rec["mode"] == "accelerated"


def test_model_router_failover_when_workstation_unreachable(tmp_path):
    db_file = os.path.join(tmp_path, "router_failover.db")
    sm = StateManager(db_path=db_file)
    router = ModelRouter(state_manager=sm)
    broker = get_mhac_broker()

    workstation_sig = ClientComputeSignature(
        node_id="pc-unreachable",
        device_name="Unreachable Rig",
        cpu_cores=16,
        ram_total_gb=32.0,
        has_gpu=True,
        gpu_name="RTX 4080",
        vram_gb=16.0,
        ollama_endpoint="http://192.168.1.250:11434"
    )

    try:
        with patch.object(broker, "probe_client_models", return_value=["llama3.1:8b"]):
            broker.evaluate_handshake(workstation_sig)
            assert broker.get_delegated_endpoint() == "http://192.168.1.250:11434"

            # Workstation goes offline / liveness returns False
            with patch.object(broker, "check_client_liveness", return_value=False):
                # resolve_model should detect liveness failure, trigger failover, and NOT raise
                clean_goal, model = router.resolve_model("calculate fast fibonacci")
                # Broker must have failed over to host
                assert broker.get_delegated_endpoint() is None
                assert broker.get_status()["mode"] == "standalone"
    finally:
        broker.reset_delegation()


def test_gateway_workload_and_connect_endpoints(mhac_test_app):
    client, broker = mhac_test_app

    # 1. Workload matrix endpoint
    wl_resp = client.get("/api/v1/mhac/workload")
    assert wl_resp.status_code == 200
    wl_data = wl_resp.json()
    assert "server_node" in wl_data
    assert "pc_node" in wl_data
    assert "proactive_watcher_daemon" in wl_data["server_node"]["workloads"]

    # 2. Heartbeat trigger endpoint
    hb_resp = client.post("/api/v1/mhac/heartbeat")
    assert hb_resp.status_code == 200
    assert "status" in hb_resp.json()

    # 3. Direct connect endpoint
    with patch.object(broker, "probe_client_models", return_value=["llama3.1:8b"]):
        connect_payload = {
            "endpoint": "http://192.168.1.155:11434",
            "device_name": "Studio Laptop",
            "gpu_name": "NVIDIA RTX 4070",
            "vram_gb": 8.0,
            "cpu_cores": 14,
            "ram_gb": 32.0,
            "preferred_models": ["llama3.1:8b"]
        }
        conn_resp = client.post("/api/v1/mhac/connect", json=connect_payload)
        assert conn_resp.status_code == 200
        c_data = conn_resp.json()
        assert c_data["status"] == "accelerated_workstation"
        assert c_data["target_model"] == "llama3.1:8b"

