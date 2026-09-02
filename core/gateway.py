import os
import sys
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.schemas import (
    BaseEvent, TextEvent, PipelinePlan, UserProfile,
    DeviceTopologyRecord, EdgeNodeRegistration, HUDCardPayload, ToolCallRequest, ToolCallResponse,
    TrustTier, DeviceEnrollmentRequest, DeviceEnrollmentResponse
)
from core.state import StateManager
from core.bus import EventBus
from tools.registry import ToolRegistry
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
import uuid

logger = logging.getLogger("CoreAI.Gateway")


class ConnectionManager:
    """Manages active WebSockets for UI clients and Edge Nodes (Car, Phone, Glasses, Mirrors)."""
    
    def __init__(self):
        # General broadcast clients (e.g. smart mirrors, dashboard)
        self.broadcast_clients: Set[WebSocket] = set()
        # Dedicated edge node sockets: node_id -> WebSocket
        self.edge_nodes: Dict[str, WebSocket] = {}
        # Pending remote tool calls: request_id -> asyncio.Future
        self.pending_tool_calls: Dict[str, asyncio.Future] = {}

    async def connect_broadcast(self, websocket: WebSocket):
        await websocket.accept()
        self.broadcast_clients.add(websocket)
        logger.info(f"Broadcast client connected. Total: {len(self.broadcast_clients)}")

    def disconnect_broadcast(self, websocket: WebSocket):
        self.broadcast_clients.discard(websocket)
        logger.info(f"Broadcast client disconnected. Remaining: {len(self.broadcast_clients)}")

    async def connect_edge_node(self, node_id: str, websocket: WebSocket):
        await websocket.accept()
        self.edge_nodes[node_id] = websocket
        logger.info(f"Edge Node '{node_id}' connected. Active nodes: {list(self.edge_nodes.keys())}")

    def disconnect_edge_node(self, node_id: str):
        self.edge_nodes.pop(node_id, None)
        logger.info(f"Edge Node '{node_id}' disconnected. Remaining: {list(self.edge_nodes.keys())}")

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcasts a JSON message to all connected ambient displays and dashboards."""
        if not self.broadcast_clients:
            return
        payload = json.dumps({"event": event_type, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
        disconnected = set()
        for client in self.broadcast_clients:
            try:
                await client.send_text(payload)
            except Exception:
                disconnected.add(client)
        for dead in disconnected:
            self.broadcast_clients.discard(dead)

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


def create_gateway_app(
    state_manager: StateManager,
    registry: ToolRegistry,
    planner: Planner,
    pipeline_engine: PipelineEngine,
    bus: EventBus
) -> FastAPI:
    """Factory creating the configured FastAPI Gateway Application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: subscribe bus events to WebSocket broadcast
        def bus_event_bridge(data: dict):
            # Forward event bus traffic into the async event loop for WebSocket clients
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        connection_manager.broadcast_event("BUS_EVENT", data),
                        loop
                    )
            except Exception:
                pass

        bus.subscribe("tts_events", bus_event_bridge)
        bus.subscribe("hud_events", bus_event_bridge)
        logger.info("Gateway bridge subscribed to EventBus channels")
        yield
        logger.info("Gateway shutting down")

    app = FastAPI(
        title="Core AI Universal Gateway",
        version="2.0.0",
        description="Protocol-Agnostic Edge Gateway for Smart Mirrors, Vehicles, Phones, Glasses, and Homelab.",
        lifespan=lifespan
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- REST Endpoints ---

    @app.get("/api/v1/health")
    def get_health():
        import platform
        profile = state_manager.get_user_profile()
        return {
            "status": "online",
            "version": "2.0.0",
            "active_user": profile.preferred_name,
            "platform": platform.system(),
            "active_model": planner.get_active_model() or "offline_heuristic",
            "connected_edge_nodes": list(connection_manager.edge_nodes.keys()),
            "broadcast_clients_count": len(connection_manager.broadcast_clients)
        }

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
        plan = planner.plan_problem(request.goal, request.context)
        
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

    @app.get("/api/v1/logs")
    def get_logs(limit: int = 50):
        """Returns recent structured execution logs from database."""
        return state_manager.get_recent_execution_logs(limit=min(limit, 200))

    @app.get("/mirror", include_in_schema=False)
    def serve_mirror_ui():
        """Serves the Smart Mirror & Wall Projection Ambient HUD Interface."""
        from fastapi.responses import FileResponse
        mirror_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../interfaces/mirror/index.html"))
        if os.path.exists(mirror_path):
            return FileResponse(mirror_path)
        raise HTTPException(status_code=404, detail="Mirror UI file not found")

    @app.get("/roadmap", include_in_schema=False)
    def serve_roadmap_ui():
        """Serves the Interactive Master Architectural Roadmap Visualizer."""
        from fastapi.responses import FileResponse
        roadmap_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../interfaces/mirror/roadmap_visualizer.html"))
        if os.path.exists(roadmap_path):
            return FileResponse(roadmap_path)
        raise HTTPException(status_code=404, detail="Roadmap Visualizer file not found")

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
                        reg = EdgeNodeRegistration(**msg.get("data", {}))
                        topo_record = DeviceTopologyRecord(
                            device_id=node_id,
                            name=reg.node_id,
                            device_type=reg.device_type,
                            is_fixed_anchor=reg.is_fixed_anchor,
                            current_zone=reg.initial_zone or "mobile/default",
                            capabilities=reg.capabilities
                        )
                        state_manager.register_or_update_device(topo_record)
                        await websocket.send_text(json.dumps({"type": "registered", "status": "ok"}))

                    # Response to a dispatched remote tool call
                    elif msg_type == "tool_call_response":
                        req_id = msg.get("request_id")
                        if req_id in connection_manager.pending_tool_calls:
                            fut = connection_manager.pending_tool_calls.pop(req_id)
                            if not fut.done():
                                fut.set_result(msg.get("result"))

                    # Incoming event from node (e.g. button press, speech transcript)
                    elif msg_type == "event":
                        event_data = msg.get("data", {})
                        logger.info(f"Received event from edge node '{node_id}': {event_data}")
                        await connection_manager.broadcast_event("EDGE_EVENT", {"node_id": node_id, "payload": event_data})

                except Exception as parse_err:
                    logger.error(f"Error parsing edge node message from '{node_id}': {parse_err}")

        except WebSocketDisconnect:
            connection_manager.disconnect_edge_node(node_id)
        except Exception:
            connection_manager.disconnect_edge_node(node_id)

    return app
