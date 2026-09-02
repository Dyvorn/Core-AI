from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class SpatialContext(BaseModel):
    """
    Universal spatial and topological context for pervasive multi-device operation:
    Supports house rooms, outdoor property, cars, bikes, phones, and smart glasses.
    """
    zone: str = "home/default"  # e.g., 'home/office', 'home/garden', 'vehicle/car', 'mobile/bike', 'mobile/glasses'
    device_type: str = "terminal"  # 'room_terminal', 'phone', 'smart_glasses', 'car', 'bike_computer', 'watch'
    capabilities: List[str] = Field(default_factory=lambda: ["audio_in", "audio_out"])
    coordinates: Optional[Dict[str, float]] = None  # e.g. {'lat': 52.52, 'lon': 13.405} or indoor anchor
    activity: Optional[str] = None  # 'driving', 'cycling', 'walking', 'working', 'idle'


class BaseEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=utc_now)
    source_node: str = "master"
    room_id: str = "default_zone"  # Retained for full backward-compatibility with existing code
    spatial_context: Optional[SpatialContext] = None

    def get_effective_zone(self) -> str:
        """Returns the specific zone (whether room, outdoor ground, car, bike, or glasses)."""
        if self.spatial_context and self.spatial_context.zone:
            return self.spatial_context.zone
        return self.room_id or "default_zone"

    def get_device_type(self) -> str:
        """Returns the client hardware category (e.g. 'smart_glasses', 'phone', 'car', 'bike_computer')."""
        if self.spatial_context and self.spatial_context.device_type:
            return self.spatial_context.device_type
        return "terminal"


class AudioEvent(BaseEvent):
    """Event for raw or transcribed audio"""
    audio_data: Optional[bytes] = None
    transcription: Optional[str] = None
    is_final: bool = False


class TextEvent(BaseEvent):
    """Event for text input (e.g., from a chat interface, mobile app, or after STT)"""
    text: str


class CommandEvent(BaseEvent):
    """Event indicating a determined action to take"""
    command: str
    args: Dict[str, Any] = Field(default_factory=dict)


class ToolCallRequest(BaseEvent):
    """Event representing a request to execute a tool (local or dispatched to a remote edge node)"""
    tool_name: str
    arguments: Dict[str, Any]
    target_node: Optional[str] = None  # If set, dispatched to specific edge device (e.g. phone, car, glasses)


class ToolCallResponse(BaseEvent):
    """Event representing the result of a tool execution"""
    request_id: str
    tool_name: str
    result: Any
    error: Optional[str] = None


class TTSRequestEvent(BaseEvent):
    """Request to synthesize and play text in a specific zone or device"""
    text: str
    voice: Optional[str] = None
    target_device: Optional[str] = None


class AdaptiveResponseEvent(BaseEvent):
    """
    Multi-modal context-aware response that formats itself dynamically based on device capabilities:
    - Smart glasses: concise HUD glance card / HUD alert
    - Car: driver-safe audio priority + dashboard tile
    - Bike: high-contrast HUD / audio cue
    - Phone: rich card with action buttons
    - Room: speaker voice output + optional ambient screen display
    """
    speech_text: Optional[str] = None
    hud_card_title: Optional[str] = None
    hud_card_body: Optional[str] = None
    action_buttons: List[str] = Field(default_factory=list)
    priority: str = "normal"  # 'low', 'normal', 'urgent', 'safety_critical'


class NodeInfo(BaseModel):
    id: str
    name: str
    type: str  # 'room', 'phone', 'smart_glasses', 'vehicle_car', 'vehicle_bike', 'outdoor_zone'
    capabilities: List[str]  # e.g., ['mic', 'speaker', 'hud_display', 'camera', 'gps', 'telemetry']
    zone: Optional[str] = None
    connectivity: str = "local"  # 'local', 'tailscale_mesh', 'cellular', 'ble'


# --- Pipeline and Autonomous Problem Solving Schemas ---

class PipelineStep(BaseModel):
    id: str
    name: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    status: str = "pending"  # pending, running, completed, failed, skipped
    output: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None

class PipelinePlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    steps: List[PipelineStep]
    status: str = "pending"  # pending, running, completed, failed
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None
    final_output: Optional[Any] = None
    error_summary: Optional[str] = None

class StepResult(BaseModel):
    step_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0

class DynamicToolSpec(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    code: str
    test_code: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

class FailureDiagnosis(BaseModel):
    """Structured diagnosis when a tool or pipeline step fails (Jarvis-like awareness)"""
    failed_step_id: str
    tool_name: str
    error_message: str
    root_cause_analysis: str
    suggested_fix: str
    can_retry: bool = True
    revised_arguments: Optional[Dict[str, Any]] = None
    alternative_tool: Optional[str] = None


# --- Phase 2: Ubiquitous Profiles, Edge Topology, & Proactive Schemas ---

class ZoneRecord(BaseModel):
    """Dynamic spatial zone created on-demand as the user mentions or connects rooms/spaces."""
    zone_id: str  # e.g., 'studio', 'patio', 'garage', 'living_room'
    display_name: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UserProfile(BaseModel):
    """Personal identity memory: who the user is, nicknames, preferences, and persona settings."""
    user_id: str = "primary_user"
    preferred_name: str = "User"  # Clean open-source default (configured by operator on first run)
    aliases: List[str] = Field(default_factory=list)
    pronouns: Optional[str] = None
    preferred_tone: str = "friendly_concise"
    preferences: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)




class DeviceTopologyRecord(BaseModel):
    """Tracks physical and roaming devices, fixed spatial anchors, and proximity mappings."""
    device_id: str
    name: str
    device_type: str  # 'mic', 'speaker', 'laptop', 'phone', 'smart_glasses', 'vehicle_car'
    is_fixed_anchor: bool = False  # Fixed anchor in a zone (studio mic) vs. Roaming (laptop)
    current_zone: str = "home/default"
    nearest_anchor_id: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    trust_tier: str = "owner"  # 'owner', 'ambient', 'guest'
    last_seen: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EdgeNodeRegistration(BaseModel):
    """Handshake message sent by an edge node (car, phone, mirror) when connecting to Gateway."""
    node_id: str
    device_type: str
    capabilities: List[str]
    initial_zone: Optional[str] = None
    is_fixed_anchor: bool = False
    trust_tier: str = "owner"  # 'owner', 'ambient', 'guest'
    battery_level: Optional[float] = None
    network_type: str = "lan"  # 'lan', 'tailscale', 'cellular', 'ble'



class ProactiveTriggerRule(BaseModel):
    """Defines an autonomous proactive rule evaluated by the background watcher daemon."""
    rule_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    condition_type: str  # 'zone_change', 'state_change', 'periodic'
    trigger_condition: Dict[str, Any]  # e.g., {'zone_from': 'home', 'zone_to': 'mobile/vehicle', 'require_state': {'window': 'open'}}
    action_goal: str  # Goal handed to Planner/PipelineEngine
    target_zone: Optional[str] = None
    priority: str = "normal"  # 'low', 'normal', 'urgent', 'safety_critical'
    is_active: bool = True
    cooldown_seconds: int = 300  # Avoid firing repeatedly
    last_triggered_at: Optional[datetime] = None


class NothingGlyphEvent(BaseEvent):
    """Nothing OS Glyph Matrix illumination pattern."""
    pattern_name: str = "pulse"  # 'pulse', 'beacon', 'alert', 'progress'
    brightness: int = 100
    duration_ms: int = 1500
    repeat: int = 1


class HUDCardPayload(BaseModel):
    """Ambient HUD card for Smart Mirrors, Wall Projections, or smart glasses."""
    card_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    subtitle: Optional[str] = None
    icon: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    action_labels: List[str] = Field(default_factory=list)
    accent_color: str = "#00ffcc"
    expires_in_seconds: Optional[int] = 30


class TrustTier(str, Enum):
    OWNER = "owner"         # Full personal access, sensitive memory, all tools, all zones
    AMBIENT = "ambient"     # Public/shared home devices (mirror, wall projector, room mic): zone-scoped actions
    GUEST = "guest"         # Untrusted external devices (friend's phone on WiFi, guest laptop): requires owner permission



class DeviceEnrollmentRequest(BaseModel):
    """Payload sent by a new device enrolling itself into Core AI mesh."""
    device_id: str
    device_name: str
    device_type: str  # 'laptop', 'phone', 'raspberry_pi', 'arduino_bridge', 'smart_glasses'
    target_zone: str = "home/default"
    requested_trust_tier: TrustTier = TrustTier.GUEST
    capabilities: List[str] = Field(default_factory=list)
    auth_secret: Optional[str] = None


class DeviceEnrollmentResponse(BaseModel):
    """Response returned upon enrolling a device."""
    status: str  # 'enrolled', 'pending_owner_approval', 'rejected'
    device_id: str
    assigned_trust_tier: TrustTier
    session_token: str
    gateway_ws_url: str
    message: str


