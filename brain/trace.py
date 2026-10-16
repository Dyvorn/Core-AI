"""
Core AI TRACE Concurrency Coordinator
Tri-Track Asynchronous Concurrent Execution Engine (v0.3.0)

Architecture:
- Track 1 (Foreground / Spoken-To): Sub-50ms fastpath for voice, REPL, and interactive queries.
- Track 2 (Context Sentinel): 24/7 background loop evaluating workspace, dirty git status,
  scratch notes, and calendar buffers.
- Track 3 (Daemons & Workers): Independent persistent workers (countdown timers, watchdogs,
  mesh sync, MHAC model pulls).
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable

from core.schemas import PipelinePlan
from core.state import StateManager
from core.bus import EventBus

logger = logging.getLogger("CoreAI.TRACE")


@dataclass
class SentinelContext:
    """Snapshot of active operator and workspace context produced by Track 2 Sentinel."""
    active_workspace_branch: str = "unknown"
    git_dirty: bool = False
    git_status_summary: str = "clean"
    pending_notes_count: int = 0
    recent_notes: List[Dict[str, Any]] = field(default_factory=list)
    upcoming_event: Optional[Dict[str, Any]] = None
    system_vitals: Dict[str, Any] = field(default_factory=dict)
    active_node: Dict[str, Any] = field(default_factory=dict)
    last_scanned_at: float = 0.0
    scan_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_summary_prompt(self) -> str:
        """Returns a concise summary suitable for system prompt augmentation."""
        branch_str = f"Git: '{self.active_workspace_branch}' ({'dirty' if self.git_dirty else 'clean'})"
        notes_str = f"{self.pending_notes_count} scratch note(s)"
        
        event_str = "No events within 24h"
        if self.upcoming_event:
            title = self.upcoming_event.get("title", "Event")
            start = self.upcoming_event.get("start_time", "")
            event_str = f"Next event: '{title}' at {start}"
            
        cpu = self.system_vitals.get("cpu_percent", "N/A")
        ram = self.system_vitals.get("memory_percent", "N/A")
        vitals_str = f"Vitals: CPU {cpu}%, RAM {ram}%"

        node_str = f"Node: {self.active_node.get('role', 'local_host')}"

        return f"{branch_str} | {notes_str} | {event_str} | {vitals_str} | {node_str}"


@dataclass
class DaemonTask:
    """Metadata tracking a background worker in Track 3."""
    name: str
    interval_seconds: float
    last_run: float = 0.0
    run_count: int = 0
    status: str = "registered"
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TraceEngine:
    """
    TRACE Concurrency Coordinator (v0.3.0).
    Coordinates Track 1 (Foreground), Track 2 (Context Sentinel), and Track 3 (Daemons).
    """

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        pipeline_engine: Optional[Any] = None,
        planner: Optional[Any] = None,
        bus: Optional[EventBus] = None,
        workspace_root: Optional[str] = None
    ):
        self.state_manager = state_manager or StateManager()
        self.pipeline_engine = pipeline_engine
        self.planner = planner
        self.bus = bus
        self.workspace_root = workspace_root or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Track 2 state
        self._sentinel_context = SentinelContext()
        self._lock = threading.Lock()
        self._sentinel_thread: Optional[threading.Thread] = None
        self._sentinel_stop_event = threading.Event()
        self._sentinel_interval = 60.0

        # Track 3 state
        self._daemons: Dict[str, DaemonTask] = {}
        self._daemon_callables: Dict[str, Callable] = {}
        self._daemon_thread: Optional[threading.Thread] = None
        self._daemon_stop_event = threading.Event()

        # Telemetry & Metrics
        self._track1_stats = {
            "total_requests": 0,
            "total_latency_ms": 0.0,
            "avg_latency_ms": 0.0,
            "last_latency_ms": 0.0,
        }
        self._track2_stats = {
            "total_scans": 0,
            "last_scan_duration_ms": 0.0,
            "last_scan_timestamp": 0.0
        }
        self._track3_stats = {
            "total_daemon_executions": 0
        }

        # Automatically register default Track 3 sovereign daemons
        self._register_default_daemons()

    def _register_default_daemons(self):
        """Registers default Track 3 background daemons (MHAC heartbeat, memory watchdogs)."""
        def _mhac_heartbeat_worker():
            try:
                from brain.mhac import get_mhac_broker
                broker = get_mhac_broker()
                return broker.heartbeat_step()
            except Exception as e:
                logger.debug(f"[TRACE Track 3] MHAC heartbeat skipped: {e}")
                return {"status": "skipped", "error": str(e)}

        self.register_daemon(
            name="mhac_liveness_heartbeat",
            fn=_mhac_heartbeat_worker,
            interval_seconds=15.0,
            metadata={"description": "Monitors PC workstation liveness and triggers auto-failover/recovery"}
        )

    # =========================================================================
    # TRACK 1: Foreground Spoken-To / Interactive Pipeline
    # =========================================================================

    def execute_interactive(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Executes a foreground interactive request with <50ms context preparation.
        Injects the pre-computed SentinelContext without blocking on git or IO.
        """
        start_ts = time.perf_counter()
        self._track1_stats["total_requests"] += 1

        # Snapshot cached SentinelContext instantaneously (non-blocking)
        sentinel_snap = self.get_sentinel_context()
        merged_context = dict(context or {})
        merged_context["sentinel"] = sentinel_snap.to_dict()
        merged_context["sentinel_summary"] = sentinel_snap.get_summary_prompt()

        plan: Optional[PipelinePlan] = None
        plan_dict: Optional[Dict[str, Any]] = None

        def _dump_plan(p: Any) -> Optional[Dict[str, Any]]:
            if p is None:
                return None
            if hasattr(p, "model_dump"):
                return p.model_dump()
            if hasattr(p, "dict"):
                return p.dict()
            if hasattr(p, "to_dict"):
                return p.to_dict()
            try:
                return asdict(p)
            except Exception:
                return {"id": getattr(p, "id", ""), "goal": getattr(p, "goal", "")}

        if self.planner:
            try:
                plan = self.planner.plan_problem(goal, context=merged_context)
                if plan:
                    plan_dict = _dump_plan(plan)
            except Exception as e:
                logger.error(f"[TRACE Track 1] Planning error: {e}")

        # If pipeline engine is wired and plan has steps, execute
        execution_result = None
        if self.pipeline_engine and plan and len(getattr(plan, "steps", [])) > 0:
            import asyncio
            try:
                # Run pipeline asynchronously in event loop or runner
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    # Thread-safe dispatch if inside another loop
                    import concurrent.futures
                    future = asyncio.run_coroutine_threadsafe(
                        self.pipeline_engine.execute_pipeline(plan),
                        loop
                    )
                    finished_plan = future.result(timeout=timeout)
                else:
                    finished_plan = asyncio.run(self.pipeline_engine.execute_pipeline(plan))

                plan = finished_plan
                plan_dict = _dump_plan(plan)
                execution_result = getattr(finished_plan, "status", "completed")
            except Exception as pipe_err:
                logger.error(f"[TRACE Track 1] Execution error: {pipe_err}")
                execution_result = f"error: {pipe_err}"

        elapsed_ms = (time.perf_counter() - start_ts) * 1000.0
        self._track1_stats["last_latency_ms"] = round(elapsed_ms, 2)
        self._track1_stats["total_latency_ms"] += elapsed_ms
        self._track1_stats["avg_latency_ms"] = round(
            self._track1_stats["total_latency_ms"] / max(1, self._track1_stats["total_requests"]),
            2
        )

        return {
            "status": "success" if execution_result != "failed" else "failed",
            "goal": goal,
            "plan": plan_dict,
            "latency_ms": round(elapsed_ms, 2),
            "sentinel_context": sentinel_snap.to_dict(),
            "sentinel_summary": sentinel_snap.get_summary_prompt()
        }

    # =========================================================================
    # TRACK 2: Context Sentinel (24/7 Background Awareness Loop)
    # =========================================================================

    def run_sentinel_scan(self, workspace_path: Optional[str] = None) -> SentinelContext:
        """
        Runs an audit of workspace git status, scratch notes, upcoming schedule,
        and system vitals. Caches result thread-safely in self._sentinel_context.
        """
        scan_start = time.perf_counter()
        target_ws = workspace_path or self.workspace_root

        # 1. Inspect Git Status (Non-blocking with strict timeout)
        branch = "unknown"
        is_dirty = False
        summary = "git unavailable"
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain", "-b"],
                cwd=target_ws,
                capture_output=True,
                text=True,
                timeout=2.0
            )
            if res.returncode == 0:
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                if lines:
                    header = lines[0]
                    if header.startswith("## "):
                        branch = header[3:].split("...")[0].strip()
                    dirty_entries = [l for l in lines[1:] if not l.startswith("??")]
                    untracked_entries = [l for l in lines[1:] if l.startswith("??")]
                    is_dirty = len(dirty_entries) > 0 or len(untracked_entries) > 0
                    summary = f"{len(dirty_entries)} changed, {len(untracked_entries)} untracked" if is_dirty else "clean"
                else:
                    branch = "clean"
                    summary = "clean"
        except Exception as e:
            logger.debug(f"[TRACE Sentinel] Git status check skipped/failed: {e}")

        # 2. Inspect Scratch Notes in SQLite
        notes_count = 0
        recent_notes_list = []
        try:
            if self.state_manager:
                all_notes = self.state_manager.list_kv(prefix="note:")
                notes_count = len(all_notes)
                for k, v in list(all_notes.items())[:5]:
                    if isinstance(v, dict):
                        recent_notes_list.append({"title": v.get("title", k.replace("note:", "")), "content": v.get("content", "")})
                    else:
                        recent_notes_list.append({"title": k.replace("note:", ""), "content": str(v)})
        except Exception as e:
            logger.debug(f"[TRACE Sentinel] Notes inspection error: {e}")

        # 3. Inspect Upcoming Calendar Schedule
        upcoming_event = None
        try:
            if self.state_manager:
                from datetime import datetime, timezone
                now_iso = datetime.now(timezone.utc).isoformat()
                events = self.state_manager.list_calendar_events(start_after=now_iso, limit=1)
                if events:
                    ev = events[0]
                    upcoming_event = {
                        "id": getattr(ev, "event_id", ""),
                        "title": getattr(ev, "title", ""),
                        "start_time": getattr(ev, "start_time", ""),
                        "location": getattr(ev, "location", ""),
                        "prep_notes": getattr(ev, "preparation_notes", "")
                    }
        except Exception as e:
            logger.debug(f"[TRACE Sentinel] Calendar inspection error: {e}")

        # 4. Inspect Hardware & Vitals
        vitals = {}
        try:
            import psutil
            vitals = {
                "cpu_percent": round(psutil.cpu_percent(interval=None), 1),
                "memory_percent": round(psutil.virtual_memory().percent, 1),
                "disk_free_gb": round(psutil.disk_usage(target_ws).free / (1024 ** 3), 1)
            }
        except Exception:
            vitals = {"cpu_percent": 0.0, "memory_percent": 0.0, "disk_free_gb": 0.0}

        # 5. Inspect Active Mesh / MHAC Broker
        active_node = {"role": "local_host", "state": "standalone"}
        try:
            from brain.mhac import get_mhac_broker
            broker = get_mhac_broker()
            active_node = {
                "role": "mhac_broker",
                "state": "active",
                "mode": "accelerated" if broker.get_delegated_endpoint() else "standalone",
                "active_compute_node": broker._active_compute_node,
                "active_devices": broker.get_active_devices_count(),
                "delegated_models": len(broker.delegated_routes),
                "workload_distribution": broker.get_workload_matrix()
            }
        except Exception:
            pass

        duration_ms = (time.perf_counter() - scan_start) * 1000.0

        ctx = SentinelContext(
            active_workspace_branch=branch,
            git_dirty=is_dirty,
            git_status_summary=summary,
            pending_notes_count=notes_count,
            recent_notes=recent_notes_list,
            upcoming_event=upcoming_event,
            system_vitals=vitals,
            active_node=active_node,
            last_scanned_at=time.time(),
            scan_duration_ms=round(duration_ms, 2)
        )

        with self._lock:
            self._sentinel_context = ctx
            self._track2_stats["total_scans"] += 1
            self._track2_stats["last_scan_duration_ms"] = round(duration_ms, 2)
            self._track2_stats["last_scan_timestamp"] = ctx.last_scanned_at

        # Notify EventBus if active
        if self.bus:
            try:
                self.bus.publish("sentinel_events", {
                    "event_type": "sentinel_scan_completed",
                    "summary": ctx.get_summary_prompt(),
                    "duration_ms": ctx.scan_duration_ms
                })
            except Exception:
                pass

        return ctx

    def get_sentinel_context(self) -> SentinelContext:
        """Returns the latest cached SentinelContext snapshot."""
        with self._lock:
            return self._sentinel_context

    def start_sentinel(self, interval_seconds: float = 60.0):
        """Starts Track 2 Context Sentinel loop in background thread."""
        if self._sentinel_thread and self._sentinel_thread.is_alive():
            return

        self._sentinel_interval = interval_seconds
        self._sentinel_stop_event.clear()

        def _loop():
            logger.info(f"[TRACE Track 2] Context Sentinel started (cadence: {interval_seconds}s)")
            while not self._sentinel_stop_event.is_set():
                try:
                    self.run_sentinel_scan()
                except Exception as e:
                    logger.error(f"[TRACE Track 2] Sentinel scan failed: {e}")
                
                # Sleep in small slices to allow prompt exit
                for _ in range(int(max(1.0, self._sentinel_interval) * 10)):
                    if self._sentinel_stop_event.is_set():
                        break
                    time.sleep(0.1)

        self._sentinel_thread = threading.Thread(target=_loop, name="TraceSentinelThread", daemon=True)
        self._sentinel_thread.start()

    def stop_sentinel(self):
        """Stops the Track 2 Context Sentinel thread."""
        self._sentinel_stop_event.set()
        if self._sentinel_thread and self._sentinel_thread.is_alive():
            self._sentinel_thread.join(timeout=2.0)
            self._sentinel_thread = None

    # =========================================================================
    # TRACK 3: Daemons & Background Workers
    # =========================================================================

    def register_daemon(
        self,
        name: str,
        fn: Callable,
        interval_seconds: float = 30.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> DaemonTask:
        """Registers a recurring background task on Track 3."""
        task = DaemonTask(
            name=name,
            interval_seconds=interval_seconds,
            metadata=metadata or {}
        )
        self._daemons[name] = task
        self._daemon_callables[name] = fn
        logger.info(f"[TRACE Track 3] Registered daemon worker '{name}' (every {interval_seconds}s)")
        return task

    def run_daemon_once(self, name: str) -> Any:
        """Executes a specific daemon worker synchronously and records telemetry."""
        if name not in self._daemon_callables:
            raise KeyError(f"Daemon worker '{name}' is not registered.")

        task = self._daemons[name]
        fn = self._daemon_callables[name]
        task.status = "running"
        try:
            result = fn()
            task.last_run = time.time()
            task.run_count += 1
            task.status = "active"
            task.last_error = None
            self._track3_stats["total_daemon_executions"] += 1
            return result
        except Exception as e:
            task.status = "error"
            task.last_error = str(e)
            logger.error(f"[TRACE Track 3] Daemon '{name}' raised error: {e}")
            raise

    def start_daemons(self):
        """Starts the Track 3 daemon scheduler loop."""
        if self._daemon_thread and self._daemon_thread.is_alive():
            return

        self._daemon_stop_event.clear()

        def _daemon_loop():
            logger.info("[TRACE Track 3] Daemon supervisor loop started")
            while not self._daemon_stop_event.is_set():
                now = time.time()
                for name, task in list(self._daemons.items()):
                    if now - task.last_run >= task.interval_seconds:
                        try:
                            self.run_daemon_once(name)
                        except Exception:
                            pass
                time.sleep(1.0)

        self._daemon_thread = threading.Thread(target=_daemon_loop, name="TraceDaemonSupervisor", daemon=True)
        self._daemon_thread.start()

    def stop_daemons(self):
        """Stops the Track 3 daemon scheduler loop."""
        self._daemon_stop_event.set()
        if self._daemon_thread and self._daemon_thread.is_alive():
            self._daemon_thread.join(timeout=2.0)
            self._daemon_thread = None

    # =========================================================================
    # High-Level Status & Telemetry
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Provides status and health metrics across all three TRACE tracks."""
        sentinel_snap = self.get_sentinel_context()
        return {
            "status": "online",
            "tracks": {
                "track_1_foreground": {
                    "name": "Foreground Spoken-To / Interactive",
                    "status": "ready",
                    "total_requests": self._track1_stats["total_requests"],
                    "avg_latency_ms": self._track1_stats["avg_latency_ms"],
                    "last_latency_ms": self._track1_stats["last_latency_ms"]
                },
                "track_2_sentinel": {
                    "name": "Context Sentinel Pipeline",
                    "status": "running" if (self._sentinel_thread and self._sentinel_thread.is_alive()) else "standby",
                    "total_scans": self._track2_stats["total_scans"],
                    "last_scan_duration_ms": self._track2_stats["last_scan_duration_ms"],
                    "last_scanned_at": self._track2_stats["last_scan_timestamp"],
                    "summary": sentinel_snap.get_summary_prompt(),
                    "active_branch": sentinel_snap.active_workspace_branch,
                    "is_dirty": sentinel_snap.git_dirty,
                    "notes_count": sentinel_snap.pending_notes_count
                },
                "track_3_daemons": {
                    "name": "Background Workers & Watchdogs",
                    "status": "running" if (self._daemon_thread and self._daemon_thread.is_alive()) else "standby",
                    "registered_daemons": len(self._daemons),
                    "total_executions": self._track3_stats["total_daemon_executions"],
                    "daemons": [d.to_dict() for d in self._daemons.values()]
                }
            }
        }


# =============================================================================
# Global Singleton Accessor
# =============================================================================

_GLOBAL_TRACE_ENGINE: Optional[TraceEngine] = None
_TRACE_LOCK = threading.Lock()


def get_trace_engine(
    state_manager: Optional[StateManager] = None,
    pipeline_engine: Optional[Any] = None,
    planner: Optional[Any] = None,
    bus: Optional[EventBus] = None,
    workspace_root: Optional[str] = None
) -> TraceEngine:
    """Retrieves or initializes the global TraceEngine singleton."""
    global _GLOBAL_TRACE_ENGINE
    with _TRACE_LOCK:
        if _GLOBAL_TRACE_ENGINE is None:
            _GLOBAL_TRACE_ENGINE = TraceEngine(
                state_manager=state_manager,
                pipeline_engine=pipeline_engine,
                planner=planner,
                bus=bus,
                workspace_root=workspace_root
            )
        return _GLOBAL_TRACE_ENGINE


def reset_trace_engine():
    """Resets the singleton for clean test environments."""
    global _GLOBAL_TRACE_ENGINE
    with _TRACE_LOCK:
        if _GLOBAL_TRACE_ENGINE is not None:
            _GLOBAL_TRACE_ENGINE.stop_sentinel()
            _GLOBAL_TRACE_ENGINE.stop_daemons()
        _GLOBAL_TRACE_ENGINE = None
