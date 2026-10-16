"""
Core AI Version 0.3.0 Test Suite
Automated Verification for QTM (Quadrillion Tool Matrix) and TRACE Engine
"""

import os
import json
import time
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from core.state import StateManager
from core.bus import EventBus
from tools.registry import ToolRegistry
from tools.native import register_all_native_tools
from tools.native.system_tools import get_disk_usage, get_battery_status, get_network_interfaces
from tools.native.dev_tools import compute_file_hash, find_files_by_pattern, read_json_file, write_json_file, git_diff_summary
from tools.native.network_tools import check_port_open, dns_lookup, ping_host, wake_on_lan
from tools.native.media_tools import set_system_volume, toggle_audio_mute, get_audio_devices
from tools.native.web_tools import fetch_url_text, http_request_json, download_file
from brain.trace import TraceEngine, SentinelContext, DaemonTask, get_trace_engine, reset_trace_engine
from core.gateway import create_gateway_app


@pytest.fixture
def fresh_state():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    sm = StateManager(db_path=db_path)
    yield sm
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


@pytest.fixture
def clean_registry():
    return ToolRegistry(dynamic_dir=tempfile.mkdtemp())


# =============================================================================
# PILLAR 1: QTM (Quadrillion Tool Matrix) Test Suite
# =============================================================================

class TestQuadrillionToolMatrix:

    def test_register_all_native_tools(self, clean_registry, fresh_state):
        count = register_all_native_tools(clean_registry, state_manager=fresh_state)
        assert count >= 30
        assert "get_disk_usage" in clean_registry.tools
        assert "compute_file_hash" in clean_registry.tools
        assert "ping_host" in clean_registry.tools
        assert "fetch_url_text" in clean_registry.tools
        assert "set_system_volume" in clean_registry.tools

    def test_disk_usage_tool(self):
        res = get_disk_usage()
        assert res["status"] == "success"
        assert "total_gb" in res
        assert "free_gb" in res
        assert res["total_gb"] > 0

    def test_battery_status_tool(self):
        res = get_battery_status()
        assert res["status"] in ("success", "unavailable")
        assert "has_battery" in res

    def test_network_interfaces_tool(self):
        res = get_network_interfaces()
        assert res["status"] in ("success", "unavailable")
        assert "count" in res
        assert "interfaces" in res

    def test_file_hash_tool(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("Core AI Sovereign Life OS Test Content")
            tf.flush()
            temp_path = tf.name

        try:
            res_sha = compute_file_hash(temp_path, algorithm="sha256")
            assert res_sha["status"] == "success"
            assert len(res_sha["hash"]) == 64

            res_md5 = compute_file_hash(temp_path, algorithm="md5")
            assert res_md5["status"] == "success"
            assert len(res_md5["hash"]) == 32
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def test_find_files_by_pattern(self):
        with tempfile.TemporaryDirectory() as td:
            file_a = os.path.join(td, "alpha.py")
            file_b = os.path.join(td, "beta.json")
            with open(file_a, "w") as f:
                f.write("a = 1")
            with open(file_b, "w") as f:
                f.write("{}")

            res = find_files_by_pattern("*.py", directory=td)
            assert res["status"] == "success"
            assert res["count"] == 1
            assert "alpha.py" in res["files"][0]["relpath"]

    def test_json_read_write_tools(self):
        with tempfile.TemporaryDirectory() as td:
            target_json = os.path.join(td, "config.json")
            payload = {"operator": "Dyvorn", "version": "0.3.0", "active": True}

            w_res = write_json_file(target_json, payload)
            assert w_res["status"] == "success"
            assert os.path.exists(target_json)

            r_res = read_json_file(target_json)
            assert r_res["status"] == "success"
            assert r_res["data"]["operator"] == "Dyvorn"
            assert r_res["data"]["version"] == "0.3.0"

    def test_port_check_and_dns_lookup(self):
        dns_res = dns_lookup("localhost")
        assert dns_res["status"] == "success"
        assert "ips" in dns_res
        assert len(dns_res["ips"]) > 0

        # Port check on closed port or localhost
        port_res = check_port_open("127.0.0.1", 65432, timeout_sec=0.2)
        assert port_res["status"] == "success"
        assert port_res["is_open"] is False

    def test_ping_host(self):
        res = ping_host("127.0.0.1", count=1, timeout_sec=0.5)
        assert res["status"] in ("success", "offline")
        assert "host" in res

    def test_wake_on_lan(self):
        # Test valid broadcast of WOL frame
        res = wake_on_lan("AA:BB:CC:DD:EE:FF")
        assert res["status"] == "success"
        assert "magic packet" in res["message"].lower()

        # Test invalid MAC
        bad_res = wake_on_lan("invalid-mac")
        assert bad_res["status"] == "error"

    def test_media_volume_and_mute(self):
        vol_res = set_system_volume(50)
        assert vol_res["status"] in ("success", "simulated", "unsupported")

        mute_res = toggle_audio_mute(mute=True)
        assert mute_res["status"] in ("success", "simulated", "unsupported")

        devs_res = get_audio_devices()
        assert devs_res["status"] in ("success", "fallback")
        assert "devices" in devs_res

    def test_web_download_and_fetch_text(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = os.path.join(td, "downloaded.txt")
            with patch("urllib.request.urlopen") as mock_url:
                mock_resp = MagicMock()
                mock_resp.read.side_effect = [b"Mocked binary chunk", b""]
                mock_resp.__enter__.return_value = mock_resp
                mock_url.return_value = mock_resp

                res = download_file("http://example.com/asset.txt", out_file)
                assert res["status"] == "success"
                assert os.path.exists(out_file)

        # Test URL text fetcher with mock
        with patch("urllib.request.urlopen") as mock_url:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"<html><body><h1>Core AI Gateway</h1><p>Running on port 8000.</p></body></html>"
            mock_resp.headers.get_content_charset.return_value = "utf-8"
            mock_resp.__enter__.return_value = mock_resp
            mock_url.return_value = mock_resp

            text_res = fetch_url_text("http://localhost:8000")
            assert text_res["status"] == "success"
            assert "Core AI Gateway" in text_res["text"]


# =============================================================================
# PILLAR 2: TRACE (Tri-Track Asynchronous Concurrent Execution) Tests
# =============================================================================

class TestTraceEngine:

    def setup_method(self):
        reset_trace_engine()

    def teardown_method(self):
        reset_trace_engine()

    def test_sentinel_context_summary(self):
        ctx = SentinelContext(
            active_workspace_branch="master",
            git_dirty=False,
            pending_notes_count=2,
            upcoming_event={"title": "Mesh Sync Standup", "start_time": "2026-10-16T18:00:00Z"},
            system_vitals={"cpu_percent": 14.5, "memory_percent": 45.0}
        )
        summary = ctx.get_summary_prompt()
        assert "master" in summary
        assert "clean" in summary
        assert "2 scratch note(s)" in summary
        assert "Mesh Sync Standup" in summary

    def test_sentinel_scan_execution(self, fresh_state):
        bus = EventBus()
        bus.start_listening()
        events_received = []
        bus.subscribe("sentinel_events", lambda ev: events_received.append(ev))

        # Add a note in state manager
        fresh_state.set_kv("note:deploy_spec", {"title": "Deploy Spec", "content": "Deploy v0.3.0 to mesh"})

        engine = TraceEngine(state_manager=fresh_state, bus=bus)
        ctx = engine.run_sentinel_scan()

        time.sleep(0.05)
        bus.stop_listening()

        assert ctx.pending_notes_count >= 1
        assert ctx.scan_duration_ms >= 0.0
        assert len(events_received) == 1
        assert "sentinel_scan_completed" == events_received[0]["event_type"]

    def test_track1_foreground_nonblocking(self, fresh_state):
        engine = TraceEngine(state_manager=fresh_state)
        # Pre-seed sentinel context
        engine.run_sentinel_scan()

        t1_res = engine.execute_interactive(
            goal="Inspect memory status",
            context={"caller": "operator_repl"}
        )

        assert t1_res["status"] == "success"
        assert t1_res["latency_ms"] < 200.0  # Fastpath non-blocking target
        assert "sentinel_context" in t1_res
        assert "sentinel_summary" in t1_res
        assert engine.get_status()["tracks"]["track_1_foreground"]["total_requests"] == 1

    def test_track3_daemons(self, fresh_state):
        engine = TraceEngine(state_manager=fresh_state)
        counter = {"runs": 0}

        def mock_worker():
            counter["runs"] += 1
            return "worker_completed"

        task = engine.register_daemon("watchdog", mock_worker, interval_seconds=1.0)
        assert task.name == "watchdog"
        assert task.status == "registered"

        result = engine.run_daemon_once("watchdog")
        assert result == "worker_completed"
        assert counter["runs"] == 1
        assert task.run_count == 1
        assert task.status == "active"

    def test_trace_status_reporting(self, fresh_state):
        engine = TraceEngine(state_manager=fresh_state)
        status = engine.get_status()

        assert status["status"] == "online"
        assert "track_1_foreground" in status["tracks"]
        assert "track_2_sentinel" in status["tracks"]
        assert "track_3_daemons" in status["tracks"]


# =============================================================================
# GATEWAY REST ENDPOINTS FOR TRACE
# =============================================================================

class TestTraceGatewayIntegration:

    @pytest.fixture
    def client(self, fresh_state, clean_registry):
        reset_trace_engine()
        register_all_native_tools(clean_registry, state_manager=fresh_state)
        from brain.planner import Planner
        from brain.pipeline_engine import PipelineEngine

        bus = EventBus()
        planner = Planner(registry=clean_registry, model_router=None, state_manager=fresh_state)
        engine = PipelineEngine(registry=clean_registry, state_manager=fresh_state, bus=bus)
        trace = TraceEngine(state_manager=fresh_state, pipeline_engine=engine, planner=planner, bus=bus)

        app = create_gateway_app(
            state_manager=fresh_state,
            registry=clean_registry,
            planner=planner,
            pipeline_engine=engine,
            bus=bus,
            trace_engine=trace
        )
        return TestClient(app)

    def test_get_trace_status_endpoint(self, client):
        resp = client.get("/api/v1/trace/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "online"
        assert "track_1_foreground" in data["tracks"]
        assert "track_2_sentinel" in data["tracks"]

    def test_get_trace_context_endpoint(self, client):
        resp = client.get("/api/v1/trace/context")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_workspace_branch" in data
        assert "system_vitals" in data

    def test_trigger_sentinel_scan_endpoint(self, client):
        resp = client.post("/api/v1/trace/sentinel/scan")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "context" in data
        assert "summary" in data

    def test_trace_interactive_endpoint(self, client):
        resp = client.post("/api/v1/trace/interactive", json={
            "goal": "Check system resources",
            "context": {"priority": "high"}
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "latency_ms" in data
        assert "sentinel_summary" in data
