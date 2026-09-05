import os
import sys
import logging
from typing import Dict, Any, Optional, List, Tuple
import sounddevice as sd

from core.schemas import AudioRouteRecord
from core.state import StateManager

logger = logging.getLogger("CoreAI.AudioRouter")


class SpatialAudioRouter:
    """
    Dynamic Spatial Audio Routing Engine:
    Agnostically binds spatial zones (e.g. workspace, living area, patio, hangar)
    to physical host soundcards (microphones, studio monitors, ambient speakers)
    or network edge devices without hardcoding room or hardware names.
    """

    def __init__(self, state_manager: Optional[StateManager] = None):
        self.state_manager = state_manager or StateManager()
        self.current_zone: str = "default"
        self.active_input_index: Optional[int] = None
        self.active_output_index: Optional[int] = None

    def list_system_audio_devices(self) -> Dict[str, List[Dict[str, Any]]]:
        """Queries host audio subsystem for all available input and output devices."""
        try:
            raw_devices = sd.query_devices()
        except Exception as e:
            logger.warning(f"Unable to query host sound devices directly ({e}). Returning fallback defaults.")
            raw_devices = []

        inputs = []
        outputs = []

        for idx, dev in enumerate(raw_devices):
            item = {
                "index": idx,
                "name": dev.get("name", f"Device #{idx}"),
                "max_input_channels": dev.get("max_input_channels", 0),
                "max_output_channels": dev.get("max_output_channels", 0),
                "default_samplerate": dev.get("default_samplerate", 44100),
                "hostapi": dev.get("hostapi", 0)
            }
            if dev.get("max_input_channels", 0) > 0:
                inputs.append(item)
            if dev.get("max_output_channels", 0) > 0:
                outputs.append(item)

        return {"inputs": inputs, "outputs": outputs}

    def resolve_device_index(self, name_query: Optional[str], kind: str = "input") -> Optional[int]:
        """
        Dynamically matches a device name/substring to its active sounddevice index.
        Resilient against system restarts where device indices shift.
        """
        if not name_query:
            return None

        devs = self.list_system_audio_devices()
        candidate_pool = devs["inputs"] if kind == "input" else devs["outputs"]
        name_lower = name_query.lower()

        # 1. Exact match
        for d in candidate_pool:
            if d["name"].lower() == name_lower:
                return d["index"]

        # 2. Substring match
        for d in candidate_pool:
            if name_lower in d["name"].lower() or d["name"].lower() in name_lower:
                return d["index"]

        return None

    def get_route_for_zone(self, zone_id: str) -> AudioRouteRecord:
        """
        Retrieves or resolves the best audio route for an arbitrary zone.
        If no explicit route is configured, falls back dynamically to system defaults.
        """
        explicit_route = self.state_manager.get_audio_route(zone_id)
        if explicit_route and explicit_route.is_active:
            # Re-resolve indices in case OS device order shifted
            resolved_in = self.resolve_device_index(explicit_route.input_device_name, kind="input")
            resolved_out = self.resolve_device_index(explicit_route.output_device_name, kind="output")
            
            if resolved_in is not None:
                explicit_route.input_device_index = resolved_in
            if resolved_out is not None:
                explicit_route.output_device_index = resolved_out
            return explicit_route

        # Fallback: check device topology for devices anchored in this zone
        all_devices = self.state_manager.list_all_devices()
        zone_devices = [d for d in all_devices if d.current_zone == zone_id]
        
        in_name = None
        out_name = None
        for zd in zone_devices:
            if "audio_in" in zd.capabilities or zd.device_type in ("mic", "studio_mic"):
                in_name = zd.name
            if "audio_out" in zd.capabilities or zd.device_type in ("speaker", "monitor"):
                out_name = zd.name

        in_idx = self.resolve_device_index(in_name, kind="input") if in_name else None
        out_idx = self.resolve_device_index(out_name, kind="output") if out_name else None

        # Return synthesized route without hardcoded room assumptions
        return AudioRouteRecord(
            zone_id=zone_id,
            input_device_name=in_name or "System Default Mic",
            output_device_name=out_name or "System Default Speaker",
            input_device_index=in_idx,
            output_device_index=out_idx,
            metadata={"inferred": True}
        )

    def route_audio_for_zone(
        self,
        zone_id: str,
        voice_in_engine=None,
        voice_out_engine=None
    ) -> Dict[str, Any]:
        """
        Applies audio routing for a given spatial zone, re-targeting voice in/out engines.
        """
        self.state_manager.ensure_zone_exists(zone_id)
        route = self.get_route_for_zone(zone_id)

        self.current_zone = zone_id
        self.active_input_index = route.input_device_index
        self.active_output_index = route.output_device_index

        applied_input = None
        applied_output = None

        # Re-target VoiceIn capture stream if provided
        if voice_in_engine is not None and hasattr(voice_in_engine, "device"):
            voice_in_engine.device = route.input_device_index
            applied_input = route.input_device_name or f"Device #{route.input_device_index}"
            logger.info(f"Routed VoiceIn capture to: {applied_input} (idx={route.input_device_index})")

        # Re-target VoiceOut playback sink if provided
        if voice_out_engine is not None and hasattr(voice_out_engine, "output_device"):
            voice_out_engine.output_device = route.output_device_index
            applied_output = route.output_device_name or f"Device #{route.output_device_index}"
            logger.info(f"Routed VoiceOut playback to: {applied_output} (idx={route.output_device_index})")

        logger.info(f"Spatial audio successfully routed for zone '{zone_id}'")
        return {
            "status": "routed",
            "zone_id": zone_id,
            "input_device": route.input_device_name,
            "input_index": route.input_device_index,
            "output_device": route.output_device_name,
            "output_index": route.output_device_index,
            "preferred_volume": route.preferred_volume
        }


# --- Native Tool Definition for Planner & Pipeline Engine ---

def route_spatial_audio(
    zone_id: str,
    input_device: Optional[str] = None,
    output_device: Optional[str] = None
) -> Dict[str, Any]:
    """Dynamically sets or switches audio capture and playback routes for a spatial zone."""
    state = StateManager()
    router = SpatialAudioRouter(state_manager=state)

    if input_device or output_device:
        # User explicitly requested specific hardware for this zone
        in_idx = router.resolve_device_index(input_device, kind="input")
        out_idx = router.resolve_device_index(output_device, kind="output")
        new_route = AudioRouteRecord(
            zone_id=zone_id,
            input_device_name=input_device,
            output_device_name=output_device,
            input_device_index=in_idx,
            output_device_index=out_idx
        )
        state.set_audio_route(new_route)

    return router.route_audio_for_zone(zone_id)


route_spatial_audio_schema = {
    "name": "route_spatial_audio",
    "description": "Switch or configure microphone and speaker audio routing for an arbitrary spatial zone with zero hardcoded rooms.",
    "parameters": {
        "type": "object",
        "properties": {
            "zone_id": {
                "type": "string",
                "description": "Target spatial zone identifier (e.g. 'workspace', 'patio', 'lounge', 'garage', 'hangar')"
            },
            "input_device": {
                "type": "string",
                "description": "Optional name or substring of the microphone/input device to bind"
            },
            "output_device": {
                "type": "string",
                "description": "Optional name or substring of the speaker/monitor device to bind"
            }
        },
        "required": ["zone_id"]
    }
}
