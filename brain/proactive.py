import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from core.schemas import ProactiveTriggerRule, AdaptiveResponseEvent, HUDCardPayload
from core.state import StateManager
from core.bus import EventBus
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from core.gateway import connection_manager

logger = logging.getLogger(__name__)

class ProactiveDaemon:
    """
    Autonomous ambient reasoning loop:
    Watches system and spatial state changes, evaluates condition triggers,
    and initiates proactive actions (e.g. alerts when driving away while window is open).
    """

    def __init__(
        self,
        state_manager: StateManager,
        planner: Planner,
        pipeline_engine: PipelineEngine,
        bus: EventBus,
        check_interval_seconds: float = 3.0
    ):
        self.state_manager = state_manager
        self.planner = planner
        self.pipeline_engine = pipeline_engine
        self.bus = bus
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._watcher_loop())
        logger.info("Proactive reasoning daemon started.")

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Proactive reasoning daemon stopped.")

    async def _watcher_loop(self):
        """Continuously inspects active proactive rules against real-time state."""
        while self._running:
            try:
                await self.evaluate_triggers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in proactive watcher loop: {e}", exc_info=True)

            await asyncio.sleep(self.check_interval_seconds)

    async def evaluate_triggers(self):
        """Evaluates all active trigger rules against current spatial and device states."""
        rules = self.state_manager.get_active_proactive_rules()
        if not rules:
            return

        now = datetime.now(timezone.utc)

        for rule in rules:
            # Check cooldown
            if rule.last_triggered_at:
                elapsed = (now - rule.last_triggered_at).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            should_fire = self._check_condition(rule.trigger_condition)
            if should_fire:
                logger.info(f"[Proactive Jarvis Trigger] Condition met for rule '{rule.name}'! Initiating goal: '{rule.action_goal}'")
                self.state_manager.update_rule_last_triggered(rule.rule_id)

                # Plan and execute autonomous solution
                plan = self.planner.plan_problem(rule.action_goal, context={"trigger_rule": rule.rule_id, "priority": rule.priority})
                finished_plan = await self.pipeline_engine.execute_pipeline(plan)

                # Send proactive adaptive notification to user (e.g. Car HUD or Phone)
                profile = self.state_manager.get_user_profile()
                speech = f"Hey {profile.preferred_name}, {rule.name}: {finished_plan.final_output or 'Aktion proaktiv ausgeführt.'}"
                
                adaptive_event = AdaptiveResponseEvent(
                    source_node="proactive_daemon",
                    room_id=rule.target_zone or "mobile/vehicle/car",
                    speech_text=speech,
                    hud_card_title=rule.name,
                    hud_card_body=str(finished_plan.final_output or "Proaktiv erledigt."),
                    priority=rule.priority
                )
                self.bus.publish("tts_events", adaptive_event)

                # Broadcast ambient HUD card to mirror/projector
                card = HUDCardPayload(
                    title=rule.name,
                    subtitle=f"Proaktive Meldung für {profile.preferred_name}",
                    icon="shield-check",
                    metrics={"status": finished_plan.status, "zone": rule.target_zone},
                    accent_color="#00e676" if finished_plan.status == "completed" else "#ff5252"
                )
                await connection_manager.broadcast_event("HUD_CARD", card.model_dump())

    def _check_condition(self, condition: Dict[str, Any]) -> bool:
        """
        Evaluates condition dictionary.
        Supports:
        - 'require_state': { 'room_id': {'key': 'expected_val'} }
        - 'require_device_zone': { 'device_id': 'expected_zone' }
        """
        # 1. Check required room/spatial state
        if "require_state" in condition:
            for room_id, expected_kv in condition["require_state"].items():
                actual_state = self.state_manager.get_room_state(room_id) or {}
                for k, v in expected_kv.items():
                    if actual_state.get(k) != v:
                        return False

        # 2. Check roaming device zone
        if "require_device_zone" in condition:
            for device_id, expected_zone in condition["require_device_zone"].items():
                device_rec = self.state_manager.get_device_record(device_id)
                if not device_rec or device_rec.current_zone != expected_zone:
                    return False

        return True
