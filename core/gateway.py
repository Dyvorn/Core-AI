import os
import sys
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Depends, Header
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.schemas import (
    BaseEvent, TextEvent, PipelinePlan, UserProfile,
    DeviceTopologyRecord, EdgeNodeRegistration, HUDCardPayload, ToolCallRequest, ToolCallResponse,
    TrustTier, DeviceEnrollmentRequest, DeviceEnrollmentResponse,
    AudioRouteRecord, AudioRouteUpdateRequest, SpatialHandoffEvent,
    SatelliteHeartbeatRequest, SatelliteHeartbeatResponse, SatelliteSpeakRequest,
    MobileEnrollmentRequest, MobileEnrollmentResponse, GlyphPattern, GlyphTriggerRequest, MobileGlanceStatus,
    MeshSyncPullRequest, MeshSyncPullResponse, MeshSyncPushRequest, MeshSyncPushResponse,
    MeshSyncFullRequest, MeshSyncFullResponse, MeshDeviceMessage, MeshDeviceMessageResponse, MeshSyncPayload,
    ClientComputeSignature, MHACHandshakeRequest, MHACHandshakeResponse, MHACProbeRequest, MHACPullRequest,
    TraceInteractiveRequest
)
from core.state import StateManager
from core.bus import EventBus
from core import __version__, __codename__
from tools.registry import ToolRegistry
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from engines.audio_router import SpatialAudioRouter
from brain.spatial_handoff import SpatialHandoffEngine
from brain.mhac import get_mhac_broker, MHACBroker
import uuid

logger = logging.getLogger("CoreAI.Gateway")



class ConnectionManager:
    """Manages active WebSockets for UI clients and Edge Nodes (Car, Phone, Glasses, Mirrors)."""
    
    def __init__(self):
        # General broadcast clients (e.g. smart mirrors, dashboard)
        self.broadcast_clients: Set[WebSocket] = set()
        # Dedicated edge node sockets: node_id -> WebSocket
        self.edge_nodes: Dict[str, WebSocket] = {}
        # Dedicated mobile companion clients: client_id -> WebSocket
        self.mobile_clients: Dict[str, WebSocket] = {}
        # Voice Satellite Registry: node_id -> satellite metadata dict
        self.registered_satellites: Dict[str, Dict[str, Any]] = {}
        # Pending remote tool calls: request_id -> asyncio.Future
        self.pending_tool_calls: Dict[str, asyncio.Future] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def register_satellite(self, data: Dict[str, Any]):
        node_id = data.get("node_id")
        if node_id:
            data["last_seen"] = time.time()
            self.registered_satellites[node_id] = data
            logger.info(f"Registered voice satellite '{node_id}' in zone '{data.get('zone', 'office')}'. Total: {len(self.registered_satellites)}")

    def get_active_satellites(self) -> List[Dict[str, Any]]:
        now = time.time()
        results = []
        for s in self.registered_satellites.values():
            sat = dict(s)
            elapsed = now - sat.get("last_seen", 0)
            if sat.get("status") == "offline":
                sat["effective_status"] = "offline"
            elif elapsed > 60:
                sat["effective_status"] = "stale"
            else:
                sat["effective_status"] = "online"
            results.append(sat)
        return results

    def get_active_satellites_count(self) -> int:
        now = time.time()
        return sum(
            1 for s in self.registered_satellites.values()
            if s.get("status") != "offline" and (now - s.get("last_seen", 0)) <= 60
        )

    async def connect_broadcast(self, websocket: WebSocket):
        await websocket.accept()
        self.broadcast_clients.add(websocket)
        logger.info(f"Broadcast client connected. Total: {len(self.broadcast_clients)}")

    def disconnect_broadcast(self, websocket: WebSocket):
        self.broadcast_clients.discard(websocket)
        logger.info(f"Broadcast client disconnected. Remaining: {len(self.broadcast_clients)}")

    async def connect_mobile_client(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.mobile_clients[client_id] = websocket
        logger.info(f"Mobile Companion '{client_id}' connected. Total mobile clients: {len(self.mobile_clients)}")

    def disconnect_mobile_client(self, client_id: str):
        self.mobile_clients.pop(client_id, None)
        logger.info(f"Mobile Companion '{client_id}' disconnected. Remaining: {len(self.mobile_clients)}")

    async def connect_edge_node(self, node_id: str, websocket: WebSocket):
        await websocket.accept()
        self.edge_nodes[node_id] = websocket
        logger.info(f"Edge Node '{node_id}' connected. Active nodes: {list(self.edge_nodes.keys())}")

    def disconnect_edge_node(self, node_id: str):
        self.edge_nodes.pop(node_id, None)
        logger.info(f"Edge Node '{node_id}' disconnected. Remaining: {list(self.edge_nodes.keys())}")

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcasts a JSON message to all connected ambient displays, dashboards, and mobile companions."""
        if not self.broadcast_clients and not self.mobile_clients:
            return
        payload = json.dumps({"event": event_type, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
        disconnected_bc = set()
        for client in self.broadcast_clients:
            try:
                await client.send_text(payload)
            except Exception:
                disconnected_bc.add(client)
        for dead in disconnected_bc:
            self.broadcast_clients.discard(dead)

        disconnected_mob = set()
        for cid, sock in self.mobile_clients.items():
            try:
                await sock.send_text(payload)
            except Exception:
                disconnected_mob.add(cid)
        for dead_id in disconnected_mob:
            self.mobile_clients.pop(dead_id, None)

    async def broadcast_glyph(self, pattern: str, brightness: int = 255, duration_ms: int = 500, metadata: Optional[Dict[str, Any]] = None):
        """Dispatches Nothing OS Glyph Matrix pattern to all connected mobile companion clients."""
        if not self.mobile_clients:
            return
        payload = json.dumps({
            "event": "GLYPH_TRIGGER",
            "pattern": pattern,
            "brightness": brightness,
            "duration_ms": duration_ms,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        disconnected = set()
        for cid, sock in self.mobile_clients.items():
            try:
                await sock.send_text(payload)
            except Exception:
                disconnected.add(cid)
        for dead in disconnected:
            self.mobile_clients.pop(dead, None)

    async def dispatch_remote_tool_call(self, node_id: str, request: ToolCallRequest, timeout: float = 20.0) -> Any:
        """Sends a tool execution request across the WebSocket to a physical edge device (car, phone)."""
        if node_id not in self.edge_nodes:
            raise RuntimeError(f"Target edge node '{node_id}' is not currently connected to Core AI Gateway.")

        socket = self.edge_nodes[node_id]
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self.pending_tool_calls[request.id] = fut

        msg = {
            "type": "tool_call_request",
            "request_id": request.id,
            "tool_name": request.tool_name,
            "arguments": request.arguments
        }
        await socket.send_text(json.dumps(msg))

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self.pending_tool_calls.pop(request.id, None)
            raise TimeoutError(f"Remote tool call '{request.tool_name}' on node '{node_id}' timed out after {timeout}s")

    async def send_to_node(self, node_id: str, message: Dict[str, Any]) -> bool:
        """Sends a JSON message directly to a connected edge node or mobile companion."""
        payload = json.dumps(message)
        if node_id in self.edge_nodes:
            try:
                await self.edge_nodes[node_id].send_text(payload)
                return True
            except Exception:
                self.edge_nodes.pop(node_id, None)
                return False
        elif node_id in self.mobile_clients:
            try:
                await self.mobile_clients[node_id].send_text(payload)
                return True
            except Exception:
                self.mobile_clients.pop(node_id, None)
                return False
        return False

    async def broadcast_mesh(self, event_type: str, data: Dict[str, Any]) -> int:
        """Broadcasts across all active edge nodes, mobile companions, and broadcast terminals."""
        payload = json.dumps({
            "event": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        sent_count = 0
        dead_edges = set()
        for nid, sock in self.edge_nodes.items():
            try:
                await sock.send_text(payload)
                sent_count += 1
            except Exception:
                dead_edges.add(nid)
        for dead in dead_edges:
            self.edge_nodes.pop(dead, None)

        dead_mobs = set()
        for cid, sock in self.mobile_clients.items():
            try:
                await sock.send_text(payload)
                sent_count += 1
            except Exception:
                dead_mobs.add(cid)
        for dead in dead_mobs:
            self.mobile_clients.pop(dead, None)

        dead_bcs = set()
        for sock in self.broadcast_clients:
            try:
                await sock.send_text(payload)
                sent_count += 1
            except Exception:
                dead_bcs.add(sock)
        for dead in dead_bcs:
            self.broadcast_clients.discard(dead)

        return sent_count

    def get_all_nodes_summary(self, state_manager: Optional[StateManager] = None) -> List[Dict[str, Any]]:
        """Returns consolidated inventory of all connected and registered nodes across the mesh."""
        nodes = []
        seen_ids = set()

        # 1. Active Voice Satellites
        for sat in self.get_active_satellites():
            nid = sat.get("node_id")
            if nid:
                seen_ids.add(nid)
                nodes.append({
                    "node_id": nid,
                    "name": nid,
                    "type": "voice_satellite",
                    "zone": sat.get("zone", "office"),
                    "status": sat.get("effective_status", "online"),
                    "connected_ws": nid in self.edge_nodes,
                    "last_seen": sat.get("last_seen"),
                    "capabilities": sat.get("capabilities", ["audio_in", "audio_out"])
                })

        # 2. Connected Mobile Companions
        for cid in list(self.mobile_clients.keys()):
            seen_ids.add(cid)
            nodes.append({
                "node_id": cid,
                "name": cid,
                "type": "mobile_companion",
                "zone": "mobile/default",
                "status": "online",
                "connected_ws": True,
                "last_seen": time.time(),
                "capabilities": ["glance_cards", "glyph_matrix", "voice_stream"]
            })

        # 3. Other Connected Edge Nodes
        for nid in list(self.edge_nodes.keys()):
            if nid not in seen_ids:
                seen_ids.add(nid)
                nodes.append({
                    "node_id": nid,
                    "name": nid,
                    "type": "edge_node",
                    "zone": "roaming",
                    "status": "online",
                    "connected_ws": True,
                    "last_seen": time.time(),
                    "capabilities": ["remote_exec"]
                })

        # 4. Registered Devices from Topology if not already in list
        if state_manager:
            for dev in state_manager.list_all_devices():
                if dev.device_id not in seen_ids:
                    seen_ids.add(dev.device_id)
                    nodes.append({
                        "node_id": dev.device_id,
                        "name": dev.name or dev.device_id,
                        "type": dev.device_type,
                        "zone": dev.current_zone or "unassigned",
                        "status": "offline",
                        "connected_ws": False,
                        "last_seen": dev.last_seen.isoformat() if dev.last_seen else None,
                        "capabilities": dev.capabilities or []
                    })

        return nodes


# Global Gateway Context
connection_manager = ConnectionManager()

class PipelineSubmitRequest(BaseModel):
    goal: str
    context: Dict[str, Any] = Field(default_factory=dict)

class ProfileUpdateRequest(BaseModel):
    preferred_name: Optional[str] = None
    pronouns: Optional[str] = None
    preferred_tone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class DeviceAnchorRequest(BaseModel):
    device_id: str
    zone: str
    is_fixed_anchor: bool = False
    nearest_anchor_id: Optional[str] = None

class ModelPreferenceUpdateRequest(BaseModel):
    role: str
    model_name: str

class SpokenToEvaluateRequest(BaseModel):
    utterance: str
    zone: Optional[str] = None

class VoiceTranscriptionRequest(BaseModel):
    utterance: str
    source_node: Optional[str] = "edge_satellite"
    zone: Optional[str] = "office"
    operator: Optional[str] = None


def create_gateway_app(
    state_manager: StateManager,
    registry: ToolRegistry,
    planner: Planner,
    pipeline_engine: PipelineEngine,
    bus: EventBus,
    remote_dispatcher: Optional[Any] = None,
    spoken_to: Optional[Any] = None,
    mhac_broker: Optional[MHACBroker] = None,
    trace_engine: Optional[Any] = None
) -> FastAPI:
    """Factory creating the configured FastAPI Gateway Application."""

    active_mhac_broker = mhac_broker or get_mhac_broker()

    if trace_engine is None:
        from brain.trace import get_trace_engine
        active_trace_engine = get_trace_engine(
            state_manager=state_manager,
            pipeline_engine=pipeline_engine,
            planner=planner,
            bus=bus
        )
    else:
        active_trace_engine = trace_engine

    if remote_dispatcher is None:
        from tools.remote_dispatcher import RemoteToolDispatcher
        remote_dispatcher = RemoteToolDispatcher(registry=registry)

    if spoken_to is None:
        from brain.spoken_to import SpokenToReasoning
        spoken_to = SpokenToReasoning(state_manager=state_manager, registry=registry, planner=planner)

    audio_router = SpatialAudioRouter(state_manager=state_manager)
    spatial_handoff = SpatialHandoffEngine(
        state_manager=state_manager,
        bus=bus,
        audio_router=audio_router,
        gateway_connection_manager=connection_manager
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        connection_manager.loop = asyncio.get_running_loop()

        # Startup: subscribe bus events to WebSocket broadcast
        def bus_event_bridge(data: dict):
            # Forward event bus traffic into the async event loop for WebSocket clients
            try:
                loop = connection_manager.loop or asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        connection_manager.broadcast_event("BUS_EVENT", data),
                        loop
                    )
            except Exception:
                pass

        bus.subscribe("tts_events", bus_event_bridge)
        bus.subscribe("hud_events", bus_event_bridge)
        bus.subscribe("glyph_events", bus_event_bridge)
        logger.info("Gateway bridge subscribed to EventBus channels (tts, hud, glyph)")

        # Zero-UI LAN Auto-Discovery Beacon
        beacon = None
        if os.getenv("CORE_DISABLE_DISCOVERY", "0") != "1":
            try:
                from core.discovery import LANBeacon
                configured_port = int(os.getenv("CORE_PORT", 8000))
                beacon = LANBeacon(
                    service_port=configured_port,
                    server_info_provider=lambda: {
                        "active_user": state_manager.get_user_profile().preferred_name,
                        "active_model": planner.get_active_model() or "heuristic"
                    }
                )
                beacon.start()
            except Exception as b_err:
                logger.warning(f"Could not initialize LAN discovery beacon: {b_err}")

        yield

        if beacon:
            try:
                beacon.stop()
            except Exception:
                pass
        try:
            active_trace_engine.stop_sentinel()
            active_trace_engine.stop_daemons()
        except Exception:
            pass
        logger.info("Gateway shutting down")

    app = FastAPI(
        title="Core AI Universal Gateway",
        version=__version__,
        description="C.O.R.E. (Concurrent Omnipresent Reasoning Engine) - Protocol-Agnostic Edge Gateway for Smart Mirrors, Vehicles, Phones, Glasses, and Homelab.",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    dashboard_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "interfaces", "dashboard"))
    if os.path.exists(dashboard_dir):
        app.mount("/static", StaticFiles(directory=dashboard_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/dashboard", response_class=HTMLResponse)
    def serve_dashboard():
        """Serves the dedicated Sovereign Mesh Master Dashboard."""
        index_file = os.path.join(dashboard_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return HTMLResponse("<h1>Core AI Universal Gateway Online</h1>")

    # --- REST Endpoints ---

    @app.get("/api/v1/health")
    def get_health():
        import platform
        profile = state_manager.get_user_profile()
        mhac_info = active_mhac_broker.get_status()
        return {
            "status": "online",
            "version": __version__,
            "codename": __codename__,
            "acronym": "Concurrent Omnipresent Reasoning Engine",
            "active_user": profile.preferred_name,
            "platform": platform.system(),
            "active_model": planner.get_active_model() or "offline_heuristic",
            "connected_edge_nodes": list(connection_manager.edge_nodes.keys()),
            "broadcast_clients_count": len(connection_manager.broadcast_clients),
            "active_satellites_count": connection_manager.get_active_satellites_count(),
            "mobile_clients_count": len(connection_manager.mobile_clients),
            "mhac_mode": mhac_info.get("mode", "standalone"),
            "mhac_active_node": mhac_info.get("active_compute_node", "host")
        }

    @app.get("/api/v1/server/status")
    def get_server_status():
        """Returns concise high-level server status, LAN endpoints, and active operator."""
        profile = state_manager.get_user_profile()
        from core.discovery import LANBeacon
        lan_ip = LANBeacon.get_lan_ip()
        return {
            "status": "online",
            "lan_ip": lan_ip,
            "port": 8000,
            "url": f"http://{lan_ip}:8000",
            "active_user": profile.preferred_name,
            "active_model": planner.get_active_model() or "offline_heuristic",
            "connected_edge_nodes": list(connection_manager.edge_nodes.keys()),
            "connected_nodes_count": len(connection_manager.edge_nodes),
            "broadcast_clients_count": len(connection_manager.broadcast_clients),
            "active_satellites_count": connection_manager.get_active_satellites_count(),
            "mobile_clients_count": len(connection_manager.mobile_clients)
        }

    @app.get("/api/v1/server/metrics")
    def get_server_metrics():
        """Returns comprehensive host hardware, memory, storage, and edge mesh telemetry."""
        from core.service import ServiceManager
        return ServiceManager.get_system_metrics(
            state_manager=state_manager,
            planner=planner,
            connection_manager=connection_manager,
            registry=registry
        )

    @app.get("/api/v1/tools")
    def get_tool_catalog():
        """Returns introspectable tool catalog."""
        return {
            "count": len(registry.tools),
            "tools": registry.get_tool_catalog()
        }

    @app.post("/api/v1/pipeline")
    async def submit_pipeline(request: PipelineSubmitRequest, background_tasks: BackgroundTasks):
        """Submit a problem / goal for the AI to decompose and solve."""
        plan = await asyncio.to_thread(planner.plan_problem, request.goal, request.context)
        
        # Execute asynchronously in background
        async def run_plan():
            finished = await pipeline_engine.execute_pipeline(plan)
            await connection_manager.broadcast_event("PIPELINE_COMPLETED", {
                "pipeline_id": finished.id,
                "status": finished.status,
                "output": finished.final_output,
                "error": finished.error_summary
            })

        background_tasks.add_task(run_plan)
        return {
            "pipeline_id": plan.id,
            "status": "submitted",
            "step_count": len(plan.steps),
            "steps": [{"id": s.id, "name": s.name, "tool": s.tool_name} for s in plan.steps]
        }

    @app.get("/api/v1/pipeline/{pipeline_id}")
    def get_pipeline_status(pipeline_id: str):
        record = state_manager.get_pipeline(pipeline_id)
        if not record:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return record

    @app.post("/api/v1/pipeline/solve_sync")
    async def solve_pipeline_sync(request: PipelineSubmitRequest):
        """Synchronously decompose, execute, and return completed pipeline result."""
        plan = await asyncio.to_thread(planner.plan_problem, request.goal, request.context)
        finished = await pipeline_engine.execute_pipeline(plan)
        profile = state_manager.get_user_profile()
        spoken = await asyncio.to_thread(planner.formulate_spoken_response, finished, profile=profile)
        return {
            "pipeline_id": finished.id,
            "status": finished.status,
            "goal": finished.goal,
            "final_output": finished.final_output,
            "spoken_response": spoken,
            "error_summary": finished.error_summary,
            "step_count": len(finished.steps),
            "steps": [s.model_dump() for s in finished.steps]
        }

    @app.get("/api/v1/models")
    def get_models_status():
        """Returns configured AI providers, active model preferences, and connectivity."""
        if hasattr(planner, "model_router"):
            return planner.model_router.get_status_summary()
        return {
            "active_model": planner.get_active_model() or "offline_heuristic"
        }

    @app.post("/api/v1/models/preferences")
    def set_model_preference(req: ModelPreferenceUpdateRequest, x_trust_tier: Optional[str] = Header(default="owner")):
        if x_trust_tier and x_trust_tier.lower() != "owner":
            raise HTTPException(status_code=403, detail="Security Protection: Only owner can modify model routing.")
        if hasattr(planner, "model_router"):
            updated = planner.model_router.set_model_preference(req.role, req.model_name)
            return {"status": "success", "models": updated}
        return {"status": "error", "message": "ModelRouter not initialized on planner."}

    @app.get("/api/v1/profile")
    def get_profile(x_trust_tier: Optional[str] = Header(default="owner")):
        """Returns personal user profile, protected from untrusted/guest devices."""
        if x_trust_tier and x_trust_tier.lower() == "guest":
            raise HTTPException(
                status_code=403,
                detail="Security Protection: Guest device detected. Access to personal identity memory denied."
            )
        return state_manager.get_user_profile()

    @app.post("/api/v1/profile")
    def update_profile(req: ProfileUpdateRequest, x_trust_tier: Optional[str] = Header(default="owner")):
        if x_trust_tier and x_trust_tier.lower() != "owner":
            raise HTTPException(
                status_code=403,
                detail="Security Protection: Only authenticated owner devices can modify personal profile."
            )
        profile = state_manager.get_user_profile()
        if req.preferred_name:
            profile.preferred_name = req.preferred_name
        if req.pronouns:
            profile.pronouns = req.pronouns
        if req.preferred_tone:
            profile.preferred_tone = req.preferred_tone
        if req.preferences:
            profile.preferences.update(req.preferences)
        state_manager.save_user_profile(profile)
        return profile

    @app.post("/api/v1/devices/enroll", response_model=DeviceEnrollmentResponse)
    def enroll_device(req: DeviceEnrollmentRequest):
        """Zero-friction onboarding endpoint for new laptops, SBCs, Arduinos, and phones."""
        assigned_tier = req.requested_trust_tier
        
        # Check security secret if owner tier is requested
        expected_secret = os.getenv("CORE_AUTH_SECRET", "core_sovereign_secret")
        if req.requested_trust_tier == TrustTier.OWNER:
            if req.auth_secret and req.auth_secret == expected_secret:
                assigned_tier = TrustTier.OWNER
                status = "enrolled"
                msg = f"Device '{req.device_name}' authenticated and enrolled as OWNER."
            else:
                assigned_tier = TrustTier.GUEST
                status = "enrolled_as_guest"
                msg = f"Device '{req.device_name}' enrolled as GUEST (owner secret mismatch)."
        else:
            status = "enrolled"
            msg = f"Device '{req.device_name}' enrolled under tier '{assigned_tier.value}'."

        token = f"tok_{uuid.uuid4().hex[:16]}"
        topo_record = DeviceTopologyRecord(
            device_id=req.device_id,
            name=req.device_name,
            device_type=req.device_type,
            current_zone=req.target_zone,
            capabilities=req.capabilities,
            trust_tier=assigned_tier.value,
            metadata={"session_token": token}
        )
        state_manager.register_or_update_device(topo_record)

        return DeviceEnrollmentResponse(
            status=status,
            device_id=req.device_id,
            assigned_trust_tier=assigned_tier,
            session_token=token,
            gateway_ws_url=f"/ws/nodes/{req.device_id}",
            message=msg
        )


    @app.get("/api/v1/zones")
    def list_zones():
        """Lists all dynamically discovered and created spatial zones."""
        return state_manager.list_zones()

    @app.post("/api/v1/zones")
    def create_zone(zone_id: str, display_name: Optional[str] = None, description: Optional[str] = None):
        """Explicitly declare a new spatial zone dynamically without hardcoding."""
        return state_manager.ensure_zone_exists(zone_id, display_name, metadata={"description": description})

    @app.get("/api/v1/devices")
    def list_devices():
        return state_manager.list_all_devices()


    @app.post("/api/v1/devices/anchor")
    def anchor_device(req: DeviceAnchorRequest):
        """Associates or relocates a device to a spatial zone."""
        existing = state_manager.get_device_record(req.device_id)
        if existing:
            state_manager.update_device_zone(req.device_id, req.zone, req.nearest_anchor_id)
            existing.current_zone = req.zone
            existing.nearest_anchor_id = req.nearest_anchor_id
            return existing
        else:
            new_record = DeviceTopologyRecord(
                device_id=req.device_id,
                name=req.device_id,
                device_type="generic",
                is_fixed_anchor=req.is_fixed_anchor,
                current_zone=req.zone,
                nearest_anchor_id=req.nearest_anchor_id
            )
            state_manager.register_or_update_device(new_record)
            return new_record

    @app.post("/api/v1/hud/card")
    async def post_hud_card(card: HUDCardPayload):
        """Sends an ambient card to Smart Mirrors, Wall Projections, or Glasses."""
        await connection_manager.broadcast_event("HUD_CARD", card.model_dump())
        return {"status": "dispatched", "card_id": card.card_id}

    # --- Phase 3: Spatial Audio Routing & Cross-Zone Unity ---

    @app.get("/api/v1/audio/devices")
    def list_audio_devices():
        """Introspects host audio hardware for microphones, studio monitors, and ambient speakers."""
        return audio_router.list_system_audio_devices()

    @app.get("/api/v1/audio/routes")
    def list_audio_routes():
        """Lists all dynamic zone-to-audio-device routes."""
        return state_manager.list_all_audio_routes()

    @app.get("/api/v1/audio/routes/{zone_id}")
    def get_audio_route_for_zone(zone_id: str):
        """Fetches active audio route for a specific zone, dynamically resolving device indices."""
        return audio_router.get_route_for_zone(zone_id)

    @app.post("/api/v1/audio/routes")
    def set_audio_route_for_zone(req: AudioRouteUpdateRequest):
        """Binds an arbitrary spatial zone to specific microphone and speaker hardware with zero hardcoding."""
        in_idx = audio_router.resolve_device_index(req.input_device_name, kind="input")
        out_idx = audio_router.resolve_device_index(req.output_device_name, kind="output")
        route = AudioRouteRecord(
            zone_id=req.zone_id,
            input_device_name=req.input_device_name,
            output_device_name=req.output_device_name,
            input_device_index=in_idx,
            output_device_index=out_idx,
            preferred_volume=req.preferred_volume if req.preferred_volume is not None else 1.0,
            metadata=req.metadata or {}
        )
        state_manager.set_audio_route(route)
        return route

    @app.post("/api/v1/spatial/handoff")
    async def trigger_spatial_handoff(target_zone: str, from_zone: Optional[str] = None, reason: str = "api_trigger"):
        """Executes a seamless cross-zone handoff (re-routing audio, updating HUD cards, firing scenes)."""
        event = await spatial_handoff.execute_handoff(
            to_zone=target_zone,
            from_zone=from_zone,
            reason=reason
        )
        return event

    @app.post("/api/v1/voice/spoken_to")
    def evaluate_spoken_to(req: SpokenToEvaluateRequest):
        """Discourse Reasoning Engine: Evaluates pragmatic discourse role for an utterance."""
        profile = state_manager.get_user_profile()
        decision = spoken_to.evaluate(req.utterance, profile=profile)
        return decision.model_dump()

    @app.post("/api/v1/voice/transcription")
    async def process_voice_transcription(req: VoiceTranscriptionRequest):
        """
        Universal Distributed Voice Perception Endpoint:
        Receives transcribed speech from any edge satellite, phone, or connected PC.
        Applies Discourse Reasoning, executes the DAG pipeline asynchronously,
        and returns the natural spoken response.
        """
        profile = state_manager.get_user_profile()
        decision = await asyncio.to_thread(spoken_to.evaluate, req.utterance, profile=profile)

        if decision.action_type == "interrupt":
            return {
                "status": "interrupted",
                "should_respond": False,
                "action_type": "interrupt",
                "spoken_response": "Stopped."
            }

        if not decision.should_respond:
            return {
                "status": "ignored",
                "should_respond": False,
                "role": decision.discourse_role.value,
                "spoken_response": None
            }

        target_cmd = decision.clean_command or req.utterance
        context = {
            "zone": req.zone or profile.preferences.get("primary_space", "office"),
            "operator": req.operator or profile.preferred_name,
            "source_node": req.source_node,
            "via": "gateway_voice_transcription"
        }

        plan = await asyncio.to_thread(planner.plan_problem, target_cmd, context)
        finished = await pipeline_engine.execute_pipeline(plan)
        spoken = await asyncio.to_thread(planner.formulate_spoken_response, finished, profile=profile)

        # Broadcast HUD notification card to ambient displays
        await connection_manager.broadcast_event("hud_card", {
            "title": f"Core AI - {req.source_node}",
            "body": spoken,
            "accent_color": "#00ffcc" if finished.status == "completed" else "#ff3366",
            "zone": context["zone"]
        })

        return {
            "status": finished.status,
            "should_respond": True,
            "spoken_response": spoken,
            "final_output": finished.final_output,
            "pipeline_id": finished.id,
            "role": decision.discourse_role.value
        }

    @app.get("/api/v1/logs")

    def get_logs(limit: int = 50):
        """Returns recent structured execution logs from database."""
        return state_manager.get_recent_execution_logs(limit=min(limit, 200))

    # --- WebSocket Endpoints ---

    @app.websocket("/ws/logs")
    async def websocket_logs(websocket: WebSocket):
        """Streams real-time execution and audit logs directly to attached terminals/dashboards."""
        await websocket.accept()
        connection_manager.broadcast_clients.add(websocket)
        try:
            recent = state_manager.get_recent_execution_logs(limit=30)
            await websocket.send_text(json.dumps({"event": "LOG_BACKSCROLL", "data": recent}))
            while True:
                await websocket.receive_text()
        except (WebSocketDisconnect, Exception):
            connection_manager.broadcast_clients.discard(websocket)

    @app.websocket("/ws/events")
    async def websocket_events(websocket: WebSocket):
        """Real-time event stream for Smart Mirrors, Wall Projections, and dashboards."""
        await connection_manager.connect_broadcast(websocket)
        try:
            while True:
                # Keep-alive receive
                data = await websocket.receive_text()
        except WebSocketDisconnect:

            connection_manager.disconnect_broadcast(websocket)
        except Exception:
            connection_manager.disconnect_broadcast(websocket)

    @app.websocket("/ws/nodes/{node_id}")
    async def websocket_edge_node(websocket: WebSocket, node_id: str):
        """Dedicated bidirectional session for edge nodes (Car, Phone, Glasses, Mirror)."""
        await connection_manager.connect_edge_node(node_id, websocket)
        try:
            while True:
                raw_text = await websocket.receive_text()
                try:
                    msg = json.loads(raw_text)
                    msg_type = msg.get("type")

                    # Edge Registration
                    if msg_type == "register":
                        reg_data = msg.get("data", {})
                        reg = EdgeNodeRegistration(**reg_data)
                        topo_record = DeviceTopologyRecord(
                            device_id=node_id,
                            name=reg.node_id,
                            device_type=reg.device_type,
                            is_fixed_anchor=reg.is_fixed_anchor,
                            current_zone=reg.initial_zone or "mobile/default",
                            capabilities=reg.capabilities
                        )
                        state_manager.register_or_update_device(topo_record)

                        # Immediate registration in satellite manager if device is a voice satellite
                        if reg.device_type == "voice_satellite":
                            connection_manager.register_satellite({
                                "node_id": node_id,
                                "zone": reg.initial_zone or "office",
                                "capabilities": reg.capabilities,
                                "status": "online",
                                "last_seen": time.time(),
                                "uptime_seconds": 0.0
                            })

                        # Dynamic Remote Tool Registration (Debt #101)
                        edge_tools = reg_data.get("tools", [])
                        registered_tools_count = 0
                        for t in edge_tools:
                            if isinstance(t, dict) and "name" in t:
                                remote_dispatcher.register_remote_edge_tool(
                                    node_id=node_id,
                                    tool_name=t["name"],
                                    description=t.get("description", f"Remote tool on {node_id}"),
                                    parameters_schema=t.get("parameters", {"type": "object", "properties": {}}),
                                    timeout=float(t.get("timeout", 15.0))
                                )
                                registered_tools_count += 1

                        await websocket.send_text(json.dumps({
                            "type": "registered",
                            "status": "ok",
                            "registered_tools_count": registered_tools_count
                        }))

                    # Response to a dispatched remote tool call
                    elif msg_type == "tool_call_response":
                        req_id = msg.get("request_id")
                        if req_id in connection_manager.pending_tool_calls:
                            fut = connection_manager.pending_tool_calls.pop(req_id)
                            if not fut.done():
                                fut.set_result(msg.get("result"))

                    # Real-time WebSocket Heartbeat from Voice Satellite
                    elif msg_type == "heartbeat":
                        hb = msg.get("data", {})
                        if not hb.get("node_id"):
                            hb["node_id"] = node_id
                        connection_manager.register_satellite(hb)
                        await websocket.send_text(json.dumps({
                            "type": "heartbeat_ack",
                            "node_id": node_id,
                            "time": time.time()
                        }))

                    elif msg_type == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "node_id": node_id,
                            "time": time.time()
                        }))

                    # Incoming event from node (e.g. button press, speech transcript)
                    elif msg_type == "event":
                        event_data = msg.get("data", {})
                        logger.info(f"Received event from edge node '{node_id}': {event_data}")
                        await connection_manager.broadcast_event("EDGE_EVENT", {"node_id": node_id, "payload": event_data})

                    # Real-time WebSocket state synchronization pull
                    elif msg_type == "sync_pull":
                        since = msg.get("since")
                        ents = msg.get("entities")
                        deltas = state_manager.get_state_deltas(since=since, entities=ents)
                        await websocket.send_text(json.dumps({
                            "type": "sync_response",
                            "server_time": time.time(),
                            "payload": deltas
                        }))

                    # Real-time WebSocket state synchronization push
                    elif msg_type == "sync_push":
                        client_deltas = msg.get("payload", {})
                        counts = state_manager.merge_state_deltas(client_deltas)
                        await connection_manager.broadcast_mesh("MESH_STATE_UPDATED", {
                            "source_node": node_id,
                            "merged_counts": counts,
                            "timestamp": time.time()
                        })
                        await websocket.send_text(json.dumps({
                            "type": "sync_ack",
                            "merged_counts": counts,
                            "time": time.time()
                        }))

                    # Inter-device message forwarding over WebSocket
                    elif msg_type == "mesh_message":
                        m_payload = msg.get("message", {})
                        tgt = m_payload.get("target_node")
                        if tgt:
                            await connection_manager.send_to_node(tgt, {"type": "mesh_device_message", "message": m_payload})

                except Exception as parse_err:
                    logger.error(f"Error parsing edge node message from '{node_id}': {parse_err}")

        except WebSocketDisconnect:
            remote_dispatcher.unregister_tools_for_node(node_id)
            connection_manager.disconnect_edge_node(node_id)
        except Exception:
            remote_dispatcher.unregister_tools_for_node(node_id)
            connection_manager.disconnect_edge_node(node_id)

    # --- Phase 4: Distributed Voice Satellite Endpoints ---

    @app.post("/api/v1/mesh/satellites/heartbeat", response_model=SatelliteHeartbeatResponse)
    def satellite_heartbeat(req: SatelliteHeartbeatRequest):
        """Ingests periodic telemetry reports from distributed voice satellites."""
        connection_manager.register_satellite(req.model_dump())
        return SatelliteHeartbeatResponse(
            status="acknowledged",
            node_id=req.node_id,
            server_time=time.time(),
            message=f"Heartbeat registered for node '{req.node_id}' in zone '{req.zone}'."
        )

    @app.get("/api/v1/mesh/satellites")
    def list_satellites():
        """Lists active and registered voice satellites across the sovereign mesh."""
        return connection_manager.get_active_satellites()

    @app.get("/api/v1/mesh/satellites/{node_id}")
    def get_satellite_details(node_id: str):
        """Returns detailed telemetry and connection status for a specific voice satellite."""
        satellites = connection_manager.get_active_satellites()
        for sat in satellites:
            if sat.get("node_id") == node_id:
                sat_data = dict(sat)
                sat_data["is_connected_ws"] = node_id in connection_manager.edge_nodes
                return sat_data
        raise HTTPException(status_code=404, detail=f"Voice satellite '{node_id}' not found.")

    @app.post("/api/v1/mesh/satellites/{node_id}/speak")
    async def speak_on_satellite(node_id: str, req: SatelliteSpeakRequest):
        """Dispatches an audio speech synthesis command to a specific voice satellite or zone."""
        payload = {
            "node_id": node_id,
            "text": req.text,
            "voice": req.voice,
            "priority": req.priority
        }
        await connection_manager.broadcast_event("SATELLITE_SPEAK", payload)

        # Directly push speech playback payload to connected edge node WebSockets
        target_nodes = []
        if node_id in connection_manager.edge_nodes:
            target_nodes.append((node_id, connection_manager.edge_nodes[node_id]))
        elif node_id == "all":
            target_nodes.extend(list(connection_manager.edge_nodes.items()))
        else:
            # Check if node_id corresponds to a spatial room zone (e.g. 'living_room', 'office')
            for sat in connection_manager.get_active_satellites():
                if sat.get("zone") == node_id:
                    snid = sat.get("node_id")
                    if snid and snid in connection_manager.edge_nodes:
                        target_nodes.append((snid, connection_manager.edge_nodes[snid]))

        for nid, sock in target_nodes:
            try:
                await sock.send_text(json.dumps({
                    "type": "speak",
                    "text": req.text,
                    "voice": req.voice,
                    "priority": req.priority
                }))
            except Exception as e:
                logger.warning(f"Failed to push speak command to edge node '{nid}': {e}")

        bus.publish("tts_events", {
            "type": "satellite_speak",
            "target_node": node_id,
            "text": req.text
        })
        return {"status": "dispatched", "node_id": node_id, "text": req.text}

    # --- Phase 4: Mobile Companion & Nothing OS Integration Endpoints ---

    @app.post("/api/v1/mobile/enroll", response_model=MobileEnrollmentResponse)
    def enroll_mobile_companion(req: MobileEnrollmentRequest):
        """Zero-friction onboarding endpoint for mobile companions (Android, Nothing OS)."""
        expected_secret = os.getenv("CORE_AUTH_SECRET", "core_sovereign_secret")
        is_owner = (
            (req.auth_secret is not None and req.auth_secret == expected_secret)
            or (req.pairing_code is not None and (req.pairing_code == expected_secret or req.pairing_code == expected_secret[-6:]))
            or (req.auth_secret is None and req.pairing_code is None and not os.getenv("CORE_REQUIRE_AUTH"))
        )
        assigned_tier = TrustTier.OWNER if is_owner else TrustTier.GUEST

        token = f"mob_{uuid.uuid4().hex[:16]}"
        topo_record = DeviceTopologyRecord(
            device_id=req.client_id,
            name=req.device_name,
            device_type="phone",
            current_zone=req.target_zone,
            capabilities=req.capabilities,
            trust_tier=assigned_tier.value,
            metadata={"session_token": token, "model": req.model, "os_version": req.os_version}
        )
        state_manager.register_or_update_device(topo_record)
        profile = state_manager.get_user_profile()

        return MobileEnrollmentResponse(
            status="enrolled",
            client_id=req.client_id,
            token=token,
            assigned_tier=assigned_tier,
            gateway_ws_url=f"/ws/mobile/{req.client_id}",
            operator_name=profile.preferred_name or "Operator",
            primary_space=profile.preferences.get("primary_space", "office"),
            message=f"Mobile companion '{req.device_name}' successfully enrolled into Core AI mesh."
        )

    @app.get("/api/v1/mobile/glance", response_model=MobileGlanceStatus)
    def get_mobile_glance():
        """Returns real-time glanceable status telemetry for mobile lock-screens and quick settings."""
        profile = state_manager.get_user_profile()
        active_rules = state_manager.get_active_proactive_rules()
        reminders = [
            {"name": r.name, "action": r.action_goal, "type": r.condition_type}
            for r in active_rules if r.condition_type in ("countdown", "timer")
        ]
        from tools.native.system_tools import inspect_system_resources
        vitals = inspect_system_resources()

        return MobileGlanceStatus(
            operator_name=profile.preferred_name or "Operator",
            primary_space=profile.preferences.get("primary_space", "office"),
            active_model=planner.get_active_model() or "offline_heuristic",
            unread_reminders=reminders,
            system_vitals=vitals,
            active_satellites_count=connection_manager.get_active_satellites_count(),
            server_time=time.time(),
            version=__version__
        )

    @app.post("/api/v1/mobile/glyph")
    async def trigger_glyph(req: GlyphTriggerRequest):
        """Triggers Nothing OS Glyph Matrix LED patterns across connected mobile devices."""
        bus.publish("glyph_events", {
            "pattern": req.pattern.value,
            "brightness": req.brightness,
            "duration_ms": req.duration_ms,
            "zone": req.zone
        })
        await connection_manager.broadcast_glyph(
            pattern=req.pattern.value,
            brightness=req.brightness,
            duration_ms=req.duration_ms,
            metadata=req.metadata
        )
        return {
            "status": "dispatched",
            "pattern": req.pattern.value,
            "brightness": req.brightness,
            "duration_ms": req.duration_ms
        }

    # --- Phase 5: Sovereign Mesh State Sync & Inter-Device Communication ---

    @app.get("/api/v1/mesh/nodes")
    def get_mesh_nodes():
        """Returns consolidated inventory of all connected and registered nodes across the sovereign mesh."""
        return connection_manager.get_all_nodes_summary(state_manager=state_manager)

    @app.post("/api/v1/mesh/sync/pull", response_model=MeshSyncPullResponse)
    def pull_mesh_state(req: MeshSyncPullRequest):
        """Pulls updated state deltas from the central gateway since a timestamp."""
        deltas = state_manager.get_state_deltas(since=req.since, entities=req.entities)
        return MeshSyncPullResponse(
            status="ok",
            server_time=time.time(),
            payload=MeshSyncPayload(**deltas)
        )

    @app.post("/api/v1/mesh/sync/push", response_model=MeshSyncPushResponse)
    async def push_mesh_state(req: MeshSyncPushRequest):
        """Merges locally created/modified state deltas from a mesh node into central state."""
        counts = state_manager.merge_state_deltas(req.payload.model_dump())
        await connection_manager.broadcast_mesh("MESH_STATE_UPDATED", {
            "source_node": req.node_id,
            "merged_counts": counts,
            "timestamp": time.time()
        })
        return MeshSyncPushResponse(
            status="merged",
            server_time=time.time(),
            merged_counts=counts,
            message="State deltas merged successfully."
        )

    @app.post("/api/v1/mesh/sync", response_model=MeshSyncFullResponse)
    async def sync_mesh_full(req: MeshSyncFullRequest):
        """Two-way atomic synchronization: merges client deltas and returns server deltas."""
        merged_counts = state_manager.merge_state_deltas(req.client_payload.model_dump())
        server_deltas = state_manager.get_state_deltas(since=req.since)
        await connection_manager.broadcast_mesh("MESH_STATE_UPDATED", {
            "source_node": req.node_id,
            "merged_counts": merged_counts,
            "timestamp": time.time()
        })
        return MeshSyncFullResponse(
            status="synced",
            server_time=time.time(),
            merged_counts=merged_counts,
            server_payload=MeshSyncPayload(**server_deltas),
            message="Bidirectional mesh synchronization completed."
        )

    @app.post("/api/v1/mesh/message", response_model=MeshDeviceMessageResponse)
    async def dispatch_mesh_message(msg: MeshDeviceMessage):
        """Routes an inter-device command, alert, speech, or notification across the sovereign mesh."""
        dispatched_to = []
        target = msg.target_node.lower().strip()

        # 1. Mesh-wide broadcast
        if target in ("all", "broadcast"):
            count = await connection_manager.broadcast_mesh("MESH_DEVICE_MESSAGE", msg.model_dump())
            dispatched_to.append(f"all ({count} nodes)")
            return MeshDeviceMessageResponse(
                status="broadcasted",
                dispatched_to=dispatched_to,
                message=f"Broadcasted to {count} connected mesh nodes."
            )

        # 2. Direct Node targeting (WebSocket)
        if msg.target_node in connection_manager.edge_nodes or msg.target_node in connection_manager.mobile_clients:
            delivered = await connection_manager.send_to_node(
                msg.target_node,
                {"type": "mesh_device_message", "message": msg.model_dump()}
            )
            if delivered:
                dispatched_to.append(msg.target_node)

        # 3. Spatial Room Zone targeting
        zones = state_manager.list_zones()
        matching_zone = next((z for z in zones if z.zone_id.lower() == target or z.display_name.lower() == target), None)
        if matching_zone or target in [s.get("zone") for s in connection_manager.get_active_satellites()]:
            zone_id = matching_zone.zone_id if matching_zone else target
            for sat in connection_manager.get_active_satellites():
                if sat.get("zone") == zone_id:
                    snid = sat.get("node_id")
                    if snid and snid in connection_manager.edge_nodes:
                        await connection_manager.send_to_node(
                            snid,
                            {"type": "mesh_device_message", "message": msg.model_dump()}
                        )
                        dispatched_to.append(snid)

        # 4. Message-type specific actions (Speech, Glyph)
        if msg.message_type == "speak" and msg.payload.get("text"):
            speech_text = msg.payload["text"]
            bus.publish("tts_events", {"text": speech_text, "target": msg.target_node})
            if not dispatched_to:
                for sat in connection_manager.get_active_satellites():
                    if sat.get("node_id") == msg.target_node or sat.get("zone") == msg.target_node:
                        snid = sat.get("node_id")
                        if snid and snid in connection_manager.edge_nodes:
                            await connection_manager.send_to_node(
                                snid,
                                {"type": "speak", "text": speech_text}
                            )
                            dispatched_to.append(snid)

        elif msg.message_type == "glyph" and msg.payload.get("pattern"):
            pat = msg.payload["pattern"]
            dur = msg.payload.get("duration_ms", 500)
            await connection_manager.broadcast_glyph(pat, duration_ms=dur)
            dispatched_to.append("mobile_glyph_mesh")

        if dispatched_to:
            return MeshDeviceMessageResponse(
                status="delivered",
                dispatched_to=dispatched_to,
                message=f"Dispatched message to {len(dispatched_to)} node(s)."
            )
        else:
            return MeshDeviceMessageResponse(
                status="queued_or_unreachable",
                dispatched_to=[],
                message=f"Target '{msg.target_node}' is not currently active on the mesh."
            )

    # --- Phase 6: Multiple Hardware-Aware Computing (MHAC) Inference Delegation ---

    @app.post("/api/v1/mhac/handshake", response_model=MHACHandshakeResponse)
    async def mhac_handshake(req: MHACHandshakeRequest):
        """
        MHAC Capability Evaluation & Context Broker Handshake:
        Evaluates client compute score vs central host.
        If client out-competes host and has target model, delegates heavy inference to client.
        Broadcasts status notice across UI/mesh so the user is actively informed.
        """
        response = await asyncio.to_thread(
            active_mhac_broker.evaluate_handshake,
            req.client_signature,
            req.preferred_models
        )
        await connection_manager.broadcast_event("MHAC_HANDSHAKE", response.model_dump())
        return response

    @app.get("/api/v1/mhac/status")
    def get_mhac_status():
        """Returns the current MHAC runtime status, active compute node, and host/client scores."""
        return active_mhac_broker.get_status()

    @app.post("/api/v1/mhac/probe")
    async def mhac_probe(req: MHACProbeRequest):
        """Probes a remote or local Ollama instance for installed models."""
        models = await asyncio.to_thread(
            active_mhac_broker.probe_client_models,
            req.endpoint,
            req.timeout
        )
        return {
            "endpoint": req.endpoint,
            "installed_models": models,
            "count": len(models)
        }

    @app.post("/api/v1/mhac/pull")
    async def mhac_pull_model(req: MHACPullRequest):
        """Instructs a remote client's Ollama instance to pull a missing model."""
        res = await asyncio.to_thread(
            active_mhac_broker.trigger_client_model_pull,
            req.endpoint,
            req.model_name
        )
        return res

    @app.post("/api/v1/mhac/reset")
    async def mhac_reset():
        """Resets compute delegation back to the central host processor."""
        active_mhac_broker.reset_delegation()
        await connection_manager.broadcast_event("MHAC_RESET", {"status": "reset", "active_compute_node": "host"})
        return {"status": "ok", "message": "Compute delegation reset to central host.", "active_compute_node": "host"}

    # =========================================================================
    # TRACE (Tri-Track Asynchronous Concurrent Execution) Routes
    # =========================================================================

    @app.get("/api/v1/trace/status")
    def get_trace_status():
        """Returns TRACE status, metrics, and health across Track 1, 2, and 3."""
        return active_trace_engine.get_status()

    @app.get("/api/v1/trace/context")
    def get_trace_context():
        """Returns the latest SentinelContext snapshot cached by Track 2."""
        return active_trace_engine.get_sentinel_context().to_dict()

    @app.post("/api/v1/trace/sentinel/scan")
    def trigger_sentinel_scan():
        """Triggers an on-demand Track 2 Sentinel scan of workspace, git status, and vitals."""
        ctx = active_trace_engine.run_sentinel_scan()
        return {
            "status": "success",
            "context": ctx.to_dict(),
            "summary": ctx.get_summary_prompt()
        }

    @app.post("/api/v1/trace/interactive")
    def execute_trace_interactive(req: TraceInteractiveRequest):
        """Executes a foreground interactive request through Track 1 with non-blocking sentinel context."""
        return active_trace_engine.execute_interactive(goal=req.goal, context=req.context, timeout=req.timeout)

    @app.websocket("/ws/mobile/{client_id}")
    async def websocket_mobile_companion(websocket: WebSocket, client_id: str):
        """Dedicated bidirectional session for mobile companion clients (glance cards, voice, glyph)."""
        await connection_manager.connect_mobile_client(client_id, websocket)
        try:
            profile = state_manager.get_user_profile()
            sync_data = {
                "event": "GLANCE_SYNC",
                "client_id": client_id,
                "operator": profile.preferred_name,
                "version": __version__,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await websocket.send_text(json.dumps(sync_data))

            while True:
                raw_text = await websocket.receive_text()
                try:
                    msg = json.loads(raw_text)
                    m_type = msg.get("type")
                    if m_type == "ping":
                        await websocket.send_text(json.dumps({"type": "pong", "time": time.time()}))
                    elif m_type == "voice_command":
                        cmd_text = msg.get("text", "")
                        if cmd_text:
                            await connection_manager.broadcast_glyph("reasoning_pulse", duration_ms=400)
                            plan = await asyncio.to_thread(planner.plan_problem, cmd_text, {"source": "mobile", "client_id": client_id})
                            finished = await pipeline_engine.execute_pipeline(plan)
                            spoken = await asyncio.to_thread(planner.formulate_spoken_response, finished, profile=profile)
                            await connection_manager.broadcast_glyph("success_flash", duration_ms=200)
                            await websocket.send_text(json.dumps({
                                "type": "voice_response",
                                "text": spoken,
                                "final_output": finished.final_output,
                                "status": finished.status
                            }))
                    elif m_type == "glyph_ack":
                        logger.debug(f"Mobile client '{client_id}' acknowledged glyph: {msg.get('pattern')}")
                    elif m_type == "glyph_trigger":
                        pat = msg.get("pattern", "reasoning_pulse")
                        dur = int(msg.get("duration_ms", 500))
                        bright = int(msg.get("brightness", 255))
                        await connection_manager.broadcast_glyph(pat, brightness=bright, duration_ms=dur)
                        await websocket.send_text(json.dumps({
                            "type": "glyph_trigger_ack",
                            "pattern": pat,
                            "time": time.time()
                        }))
                except json.JSONDecodeError as jde:
                    logger.debug(f"Malformed JSON payload from mobile client '{client_id}': {jde}")
        except (WebSocketDisconnect, Exception):
            connection_manager.disconnect_mobile_client(client_id)

    return app
