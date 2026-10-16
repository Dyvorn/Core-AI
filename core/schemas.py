from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid
import time


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

    @property
    def direct_response(self) -> Optional[str]:
        return self.context.get("direct_response")

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

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class UserProfile(BaseModel):
    """Personal identity memory: who the user is, nicknames, preferences, and persona settings."""
    user_id: str = "primary_user"
    preferred_name: str = "User"  # Clean open-source default (configured by operator on first run)
    aliases: List[str] = Field(default_factory=list)
    pronouns: Optional[str] = None
    preferred_tone: str = "friendly_concise"
    preferences: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


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
    status: str = "online"  # 'online', 'offline', 'roaming'
    last_seen: datetime = Field(default_factory=utc_now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


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


# --- Phase 3: Spatial Audio Routing & Cross-Zone Unity ---

class AudioRouteRecord(BaseModel):
    """Dynamic mapping between a spatial zone and its physical/network audio interfaces."""
    zone_id: str
    input_device_name: Optional[str] = None
    output_device_name: Optional[str] = None
    input_device_index: Optional[int] = None
    output_device_index: Optional[int] = None
    preferred_volume: float = 1.0
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=utc_now)


class AudioRouteUpdateRequest(BaseModel):
    """Payload to configure or update audio routing for an arbitrary zone."""
    zone_id: str
    input_device_name: Optional[str] = None
    output_device_name: Optional[str] = None
    preferred_volume: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class SpatialHandoffEvent(BaseModel):
    """Emitted when an operator or roaming device transitions between zones."""
    operator_id: str = "primary_user"
    from_zone: Optional[str] = None
    to_zone: str
    active_device_id: Optional[str] = None
    reason: str = "proximity_or_verbal"
    auto_routed_audio: bool = True
    timestamp: datetime = Field(default_factory=utc_now)
 
 
# --- Satellite Telemetry & Remote Voice Control ---

class SatelliteHeartbeatRequest(BaseModel):
    """Periodic telemetry report emitted by a distributed VoiceSatellite."""
    node_id: str
    zone: str = "office"
    mic_device: Optional[str] = None
    speaker_device: Optional[str] = None
    model_size: str = "small"
    status: str = "listening"  # 'listening', 'speaking', 'offline'
    uptime_seconds: float = 0.0
    latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SatelliteHeartbeatResponse(BaseModel):
    """Response returned upon receiving a satellite heartbeat."""
    status: str = "acknowledged"
    node_id: str
    server_time: float = Field(default_factory=lambda: time.time())
    message: str = "Heartbeat registered."


class SatelliteSpeakRequest(BaseModel):
    """Request to synthesize and speak audio on a specific voice satellite."""
    text: str
    voice: Optional[str] = "auto"
    priority: str = "normal"


# --- Phase 4: Mobile Companion & Nothing OS Integration ---

class MobileEnrollmentRequest(BaseModel):
    """Request from a mobile companion device enrolling with the gateway."""
    client_id: str
    device_name: str
    model: Optional[str] = "Mobile Device"
    os_version: Optional[str] = None
    target_zone: str = "mobile/default"
    pairing_code: Optional[str] = None
    auth_secret: Optional[str] = None
    capabilities: List[str] = Field(
        default_factory=lambda: ["glance_cards", "voice_stream", "glyph_matrix", "ble_gateway"]
    )


class MobileEnrollmentResponse(BaseModel):
    """Response returned to mobile companion upon successful enrollment."""
    status: str
    client_id: str
    token: str
    assigned_tier: TrustTier
    gateway_ws_url: str
    operator_name: str
    primary_space: str
    message: str


class GlyphPattern(str, Enum):
    """Nothing OS Glyph Matrix light patterns."""
    IDLE = "idle"
    LISTENING = "listening"
    REASONING_PULSE = "reasoning_pulse"
    SUCCESS_FLASH = "success_flash"
    ALERT_BURST = "alert_burst"
    OFF = "off"


class GlyphTriggerRequest(BaseModel):
    """Request to trigger a Nothing OS Glyph LED matrix pattern."""
    pattern: GlyphPattern = GlyphPattern.REASONING_PULSE
    brightness: int = 255
    duration_ms: int = 500
    zone: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MobileGlanceStatus(BaseModel):
    """Lightweight glanceable status payload for mobile lock screens and widgets."""
    operator_name: str
    primary_space: str
    active_model: str
    unread_reminders: List[Dict[str, Any]] = Field(default_factory=list)
    system_vitals: Dict[str, Any] = Field(default_factory=dict)
    active_satellites_count: int = 0
    server_time: float = Field(default_factory=lambda: time.time())
    version: str = "0.3.0-alpha"
    sentinel_summary: Optional[str] = None
    active_branch: Optional[str] = None


# --- Phase 5: Sovereign Mesh State Sync & Inter-Device Communication ---

class MeshSyncPayload(BaseModel):
    """Container for mesh state deltas exchanged between nodes and main server."""
    timestamp: float = Field(default_factory=lambda: time.time())
    profile: Optional[Dict[str, Any]] = None
    kv_state: List[Dict[str, Any]] = Field(default_factory=list)
    zones: List[Dict[str, Any]] = Field(default_factory=list)
    devices: List[Dict[str, Any]] = Field(default_factory=list)
    proactive_rules: List[Dict[str, Any]] = Field(default_factory=list)
    audio_routes: List[Dict[str, Any]] = Field(default_factory=list)
    dynamic_tools: List[Dict[str, Any]] = Field(default_factory=list)
    offline_tasks: List[Dict[str, Any]] = Field(default_factory=list)


class MeshSyncPullRequest(BaseModel):
    """Request from a mesh client to pull updated state entities since a timestamp."""
    node_id: str
    since: Optional[str] = None  # ISO timestamp string or None for full sync
    entities: List[str] = Field(
        default_factory=lambda: ["profile", "kv_state", "zones", "devices", "proactive_rules", "audio_routes"]
    )


class MeshSyncPullResponse(BaseModel):
    """Payload returned when pulling state from the central gateway."""
    status: str = "ok"
    server_time: float = Field(default_factory=lambda: time.time())
    payload: MeshSyncPayload


class MeshSyncPushRequest(BaseModel):
    """Request from a mesh client pushing locally created/modified state deltas."""
    node_id: str
    payload: MeshSyncPayload


class MeshSyncPushResponse(BaseModel):
    """Response returned upon merging pushed state deltas."""
    status: str = "merged"
    server_time: float = Field(default_factory=lambda: time.time())
    merged_counts: Dict[str, int] = Field(default_factory=dict)
    message: str = "State deltas merged successfully."


class MeshSyncFullRequest(BaseModel):
    """Two-way atomic synchronization request combining client push and server pull."""
    node_id: str
    since: Optional[str] = None
    client_payload: MeshSyncPayload


class MeshSyncFullResponse(BaseModel):
    """Two-way atomic synchronization response returning merged results and server deltas."""
    status: str = "synced"
    server_time: float = Field(default_factory=lambda: time.time())
    merged_counts: Dict[str, int] = Field(default_factory=dict)
    server_payload: MeshSyncPayload
    message: str = "Full bidirectional synchronization completed."


class MeshDeviceMessage(BaseModel):
    """Inter-device communication message routed across the sovereign mesh."""
    source_node: str
    target_node: str  # specific node_id, 'all', or spatial room zone (e.g. 'living_room')
    message_type: str = "command"  # 'command', 'notify', 'speak', 'glyph', 'sync_signal', 'query'
    payload: Dict[str, Any] = Field(default_factory=dict)
    priority: str = "normal"
    timestamp: float = Field(default_factory=lambda: time.time())


class MeshDeviceMessageResponse(BaseModel):
    """Response returned upon dispatching an inter-device mesh message."""
    status: str
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    dispatched_to: List[str] = Field(default_factory=list)
    message: str = "Message routed."


class CalendarEventRecord(BaseModel):
    """
    Structured calendar and appointment record for anticipatory scheduling and preparation.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    start_time: str  # ISO-8601 string or timestamp
    end_time: Optional[str] = None
    location: Optional[str] = None
    preparation_notes: Optional[str] = None
    preparation_minutes: int = 30
    prep_notified: bool = False
    imminent_notified: bool = False
    source: str = "user"  # 'user', 'reconciliation', 'note_evidence', 'voice_mention'
    evidence_text: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# --- Multiple Hardware-Aware Computing (MHAC) Schemas ---

class ClientComputeSignature(BaseModel):
    """Compute capabilities reported by or probed from a mesh client device."""
    node_id: str
    device_name: str
    device_type: str = "workstation"  # 'workstation', 'desktop', 'laptop', 'phone', 'server'
    cpu_cores: int = 4
    ram_total_gb: float = 16.0
    has_gpu: bool = False
    gpu_name: Optional[str] = None  # e.g., 'NVIDIA GeForce RTX 4080'
    vram_gb: Optional[float] = None  # e.g., 16.0
    ollama_endpoint: Optional[str] = None  # e.g., 'http://192.168.1.150:11434'
    installed_models: List[str] = Field(default_factory=list)
    compute_score: float = 0.0

    def calculate_score(self) -> float:
        """
        Computes dynamic compute score:
        Score = (CPU Cores * 1.0) + (RAM GB * 0.5) + (Has GPU * 50.0) + (VRAM GB * 5.0)
        """
        score = (self.cpu_cores * 1.0) + (self.ram_total_gb * 0.5)
        if self.has_gpu:
            score += 50.0
            if self.vram_gb:
                score += (self.vram_gb * 5.0)
        self.compute_score = round(score, 1)
        return self.compute_score


class MHACHandshakeRequest(BaseModel):
    """Handshake request sent by client or initiated by gateway upon client connection."""
    client_signature: ClientComputeSignature
    preferred_models: List[str] = Field(default_factory=lambda: ["llama3.1:8b", "llama3.2:3b", "qwen2.5:7b"])


class MHACHandshakeResponse(BaseModel):
    """Response returned by Central Host following MHAC capability evaluation."""
    status: str  # 'accelerated_workstation', 'standalone', 'missing_model_handshake', 'error'
    active_compute_node: str  # 'host' or client node_id
    host_score: float
    client_score: float
    delegated_endpoint: Optional[str] = None
    target_model: Optional[str] = None
    notice_message: str
    installed_on_client: List[str] = Field(default_factory=list)
    missing_models: List[str] = Field(default_factory=list)


class MHACProbeRequest(BaseModel):
    """Request to probe model inventory of a remote or local Ollama endpoint."""
    endpoint: str = "http://127.0.0.1:11434"
    timeout: float = 2.0


class MHACPullRequest(BaseModel):
    """Request to instruct a client Ollama instance to pull a missing model."""
    endpoint: str
    model_name: str


class MHACConnectRequest(BaseModel):
    """Direct connect request for pairing an external PC or workstation."""
    endpoint: str = "http://127.0.0.1:11434"
    device_name: str = "External Workstation"
    gpu_name: str = "NVIDIA RTX"
    vram_gb: float = 16.0
    cpu_cores: int = 16
    ram_gb: float = 32.0
    preferred_models: Optional[List[str]] = None


class TraceInteractiveRequest(BaseModel):
    """Request payload for TRACE Track 1 interactive foreground execution."""
    goal: str
    context: Optional[Dict[str, Any]] = None
    timeout: float = 30.0






