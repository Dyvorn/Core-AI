import os
import sys
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from core.schemas import SpatialHandoffEvent, HUDCardPayload
from core.state import StateManager
from core.bus import EventBus
from engines.audio_router import SpatialAudioRouter

logger = logging.getLogger("CoreAI.SpatialHandoff")


class SpatialHandoffEngine:
    """
    Cross-Zone Spatial Handoff Engine:
    Coordinates seamless transitions between arbitrary physical zones
    (studio, living sanctuary, workshop, patio, airplane hangar, etc.)
    with zero hardcoding. Re-routes audio, dispatches ambient HUD cards,
    and executes user-defined zone scene transitions dynamically.
    """

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        bus: Optional[EventBus] = None,
        audio_router: Optional[SpatialAudioRouter] = None,
        voice_in_engine=None,
        voice_out_engine=None,
        gateway_connection_manager=None
    ):
        self.state_manager = state_manager or StateManager()
        self.bus = bus or EventBus()
        self.audio_router = audio_router or SpatialAudioRouter(state_manager=self.state_manager)
        self.voice_in_engine = voice_in_engine
        self.voice_out_engine = voice_out_engine
        self.gateway_connection_manager = gateway_connection_manager
        self.current_zone: str = "default"

    async def execute_handoff(
        self,
        to_zone: str,
        from_zone: Optional[str] = None,
        active_device_id: Optional[str] = None,
        reason: str = "proximity_or_verbal"
    ) -> SpatialHandoffEvent:
        """
        Executes a complete cross-zone spatial handoff:
        1. Ensures zone exists in SQLite.
        2. Re-routes microphone and speaker audio.
        3. Relocates the active device in topology.
        4. Broadcasts ambient HUD card to target zone screens.
        5. Fires dynamic scene transitions (if configured in zone metadata).
        6. Publishes SpatialHandoffEvent to EventBus.
        """
        if not from_zone:
            from_zone = self.current_zone

        # 1. Ensure zone exists dynamically
        zone_record = self.state_manager.ensure_zone_exists(to_zone)
        logger.info(f"Initiating spatial handoff: '{from_zone}' -> '{to_zone}' (reason: {reason})")

        # 2. Dynamic Audio Routing
        routing_info = self.audio_router.route_audio_for_zone(
            to_zone,
            voice_in_engine=self.voice_in_engine,
            voice_out_engine=self.voice_out_engine
        )

        # 3. Update device topology if a roaming device triggered this
        if active_device_id:
            self.state_manager.update_device_zone(active_device_id, to_zone)

        self.current_zone = to_zone

        # 4. Broadcast Ambient HUD Card to displays in target zone
        profile = self.state_manager.get_user_profile()
        hud_card = HUDCardPayload(
            title=f"Welcome to {zone_record.display_name}",
            subtitle=f"Active audio: {routing_info.get('output_device') or 'Default'}",
            metrics={
                "ZONE": to_zone,
                "OPERATOR": profile.preferred_name,
                "MIC": routing_info.get("input_device") or "Default",
                "TIME": datetime.now(timezone.utc).strftime("%H:%M")
            },
            accent_color="#00ffcc"
        )

        if self.gateway_connection_manager:
            try:
                await self.gateway_connection_manager.broadcast_event("HUD_CARD", hud_card.model_dump())
            except Exception as e:
                logger.warning(f"Could not broadcast HUD card via gateway: {e}")

        # 5. Dynamic Zone Scene Transition (Zero hardcoded scene names)
        # Reads enter_scene / exit_scene from zone metadata if operator configured it
        to_metadata = zone_record.metadata or {}
        enter_scene = to_metadata.get("enter_scene")
        if enter_scene:
            logger.info(f"Triggering zone scene for '{to_zone}': '{enter_scene}'")
            self.bus.publish("scene_events", {
                "action": "activate_scene",
                "scene_id": enter_scene,
                "zone_id": to_zone
            })

        # Check if previous zone had an exit scene
        if from_zone and from_zone != to_zone:
            from_record = self.state_manager.ensure_zone_exists(from_zone)
            from_metadata = from_record.metadata or {}
            exit_scene = from_metadata.get("exit_scene")
            if exit_scene:
                logger.info(f"Triggering exit scene for '{from_zone}': '{exit_scene}'")
                self.bus.publish("scene_events", {
                    "action": "activate_scene",
                    "scene_id": exit_scene,
                    "zone_id": from_zone
                })

        # 6. Publish Handoff Event on EventBus
        event = SpatialHandoffEvent(
            operator_id=profile.user_id,
            from_zone=from_zone,
            to_zone=to_zone,
            active_device_id=active_device_id,
            reason=reason,
            auto_routed_audio=True
        )
        self.bus.publish("spatial_handoff", event.model_dump())
        logger.info(f"Spatial handoff to '{to_zone}' completed successfully.")
        return event
