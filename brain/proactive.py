import asyncio
import logging
from datetime import datetime, timezone, timedelta
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
    Watches system, spatial, temporal, and calendar states, evaluates condition triggers,
    anticipates upcoming appointments with preparation buffers, reconciles implicit notes,
    and initiates proactive actions non-intrusively.
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
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread = None

    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        if self._running:
            return
        self._running = True
        try:
            running_loop = loop or asyncio.get_running_loop()
            self._task = running_loop.create_task(self._watcher_loop())
            logger.info("Proactive reasoning daemon started (in existing event loop).")
        except RuntimeError:
            # Fallback when started from synchronous context before uvicorn/asyncio loop starts
            import threading
            def _thread_runner():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                self._task = self._loop.create_task(self._watcher_loop())
                try:
                    self._loop.run_until_complete(self._task)
                except asyncio.CancelledError:
                    pass
                finally:
                    self._loop.close()

            self._thread = threading.Thread(target=_thread_runner, daemon=True, name="ProactiveDaemonThread")
            self._thread.start()
            logger.info("Proactive reasoning daemon started (in dedicated background thread).")

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
        """Evaluates active trigger rules, calendar preparation buffers, and un-reconciled evidence."""
        now = datetime.now(timezone.utc)

        # 1. Custom Proactive Trigger Rules & Hardware Supervisors
        rules = self.state_manager.get_active_proactive_rules()
        if rules:
            for rule in rules:
                # Check cooldown
                if rule.last_triggered_at:
                    elapsed = (now - rule.last_triggered_at).total_seconds()
                    if elapsed < rule.cooldown_seconds:
                        continue

                should_fire = self._check_condition(rule.trigger_condition, rule.condition_type, now)
                if should_fire:
                    logger.info(f"[Proactive Jarvis Trigger] Condition met for rule '{rule.name}'! Initiating goal: '{rule.action_goal}'")
                    self.state_manager.update_rule_last_triggered(rule.rule_id)

                    # Automatically deactivate one-shot reminders and countdowns
                    if rule.condition_type == "countdown" or rule.trigger_condition.get("one_shot", False):
                        self.state_manager.deactivate_proactive_rule(rule.rule_id)

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

        # 2. Anticipatory Calendar & Preparation Buffer Checks
        await self._check_calendar_anticipations(now)

        # 3. Unscheduled Notes & Context Evidence Reconciliation
        await self._check_unreconciled_notes(now)

    async def _check_calendar_anticipations(self, now: datetime):
        """
        Anticipates upcoming appointments and delivers proactive preparation warnings
        before the event, respecting required preparation minutes.
        """
        try:
            now_iso = now.isoformat()
            horizon_iso = (now + timedelta(hours=12)).isoformat()
            events = self.state_manager.list_calendar_events(start_after=now_iso, end_before=horizon_iso, limit=20)
            if not events:
                return

            profile = self.state_manager.get_user_profile()
            name = profile.preferred_name or "Operator"

            for ev in events:
                try:
                    start_dt = datetime.fromisoformat(str(ev["start_time"]).replace("Z", "+00:00"))
                    seconds_left = (start_dt - now).total_seconds()
                    if seconds_left <= 0:
                        continue

                    mins_left = int(seconds_left / 60)
                    prep_mins = ev.get("preparation_minutes") or 30
                    prep_notes = ev.get("preparation_notes") or "Review agenda and prepare"
                    event_id = ev["id"]
                    title = ev["title"]

                    # Pre-event Preparation Buffer Warning
                    if seconds_left <= (prep_mins * 60) and not ev.get("prep_notified"):
                        logger.info(f"[Proactive Calendar] Preparation warning for '{title}' (starts in {mins_left}m, prep={prep_mins}m).")
                        self.state_manager.mark_event_notified(event_id, prep_notified=True)

                        speech = (
                            f"Hey {name}, your appointment '{title}' is in {mins_left} minutes. "
                            f"You have {prep_mins} minutes to prepare: {prep_notes}."
                        )
                        event = AdaptiveResponseEvent(
                            source_node="proactive_calendar",
                            room_id="default_zone",
                            speech_text=speech,
                            hud_card_title=f"Preparation: {title}",
                            hud_card_body=f"Starts in {mins_left}m | Prep buffer: {prep_mins}m\n{prep_notes}",
                            priority="normal"
                        )
                        self.bus.publish("tts_events", event)

                        card = HUDCardPayload(
                            title=f"Preparation: {title}",
                            subtitle=f"Starts in {mins_left}m",
                            icon="calendar-clock",
                            metrics={"prep_minutes": prep_mins, "starts_in_mins": mins_left},
                            accent_color="#29b6f6"
                        )
                        await connection_manager.broadcast_event("HUD_CARD", card.model_dump())

                    # Imminent Warning (15 minutes or less)
                    elif seconds_left <= (15 * 60) and not ev.get("imminent_notified"):
                        logger.info(f"[Proactive Calendar] Imminent warning for '{title}' (starts in {mins_left}m).")
                        self.state_manager.mark_event_notified(event_id, imminent_notified=True)

                        speech = f"Hey {name}, '{title}' starts in {mins_left} minutes."
                        event = AdaptiveResponseEvent(
                            source_node="proactive_calendar",
                            room_id="default_zone",
                            speech_text=speech,
                            hud_card_title=f"Upcoming: {title}",
                            hud_card_body=f"Starts in {mins_left} minutes.",
                            priority="urgent"
                        )
                        self.bus.publish("tts_events", event)
                except Exception as ee:
                    logger.warning(f"Error evaluating event {ev.get('id')}: {ee}")
        except Exception as e:
            logger.error(f"Error in calendar anticipations check: {e}")

    async def _check_unreconciled_notes(self, now: datetime):
        """
        Scans persistent scratch notes for un-reconciled appointment mentions,
        verifies evidence, auto-schedules onto the calendar, and proactively informs the operator.
        """
        try:
            notes = self.state_manager.list_kv(prefix="note:")
            if not notes:
                return

            profile = self.state_manager.get_user_profile()
            name = profile.preferred_name or "Operator"

            for k, val in notes.items():
                if not isinstance(val, dict):
                    continue
                if val.get("schedule_reconciled"):
                    continue

                content = val.get("content", "")
                title = val.get("title", "")
                full_text = f"{title} {content}".lower()

                # Check if note mentions appointment/meeting/calendar cues
                keywords = ["appointment", "meeting", "termin", "dentist", "doctor", "arzt", "besprechung", "zahnarzt"]
                if any(w in full_text for w in keywords):
                    from tools.native.calendar_tools import reconcile_schedule_evidence
                    res = reconcile_schedule_evidence(
                        evidence_text=f"{title}: {content}",
                        context_source=f"note:{title}"
                    )
                    # Mark note as reconciled in KV store so it never repeats
                    val["schedule_reconciled"] = True
                    self.state_manager.set_kv(k, val)

                    if res.get("status") == "reconciled":
                        logger.info(f"[Proactive Note Reconciliation] Auto-scheduled appointment from note '{title}': {res.get('title')}")
                        msg = (
                            f"Hey {name}, you mentioned an appointment ('{res.get('title')}'), but hadn't put it in your calendar. "
                            f"I checked the evidence, added it to your calendar, and configured a preparation reminder."
                        )
                        event = AdaptiveResponseEvent(
                            source_node="proactive_reconciliation",
                            room_id="default_zone",
                            speech_text=msg,
                            hud_card_title=f"Scheduled: {res.get('title')}",
                            hud_card_body=msg,
                            priority="normal"
                        )
                        self.bus.publish("tts_events", event)

                        card = HUDCardPayload(
                            title=f"Calendar: {res.get('title')}",
                            subtitle="Auto-reconciled from note",
                            icon="calendar-plus",
                            metrics={"status": "auto_scheduled", "title": res.get("title")},
                            accent_color="#00e676"
                        )
                        await connection_manager.broadcast_event("HUD_CARD", card.model_dump())
        except Exception as e:
            logger.error(f"Error in proactive note reconciliation: {e}")


    def _check_condition(self, condition: Dict[str, Any], condition_type: str = "state_change", now: Optional[datetime] = None) -> bool:
        """
        Evaluates condition dictionary against real-time spatial, temporal, and system state.
        Supports:
        - 'countdown': { 'target_timestamp_utc': ISO/timestamp }
        - 'vitals': { 'ram_percent_gt': 85.0 }
        - 'periodic': fires on recurring interval
        - 'require_state': { 'room_id': {'key': 'expected_val'} }
        - 'require_device_zone': { 'device_id': 'expected_zone' }
        """
        curr_now = now or datetime.now(timezone.utc)

        # 1. Countdown / Scheduled Reminders
        if condition_type == "countdown" or "target_timestamp_utc" in condition:
            target_raw = condition.get("target_timestamp_utc")
            if target_raw:
                try:
                    if isinstance(target_raw, (int, float)):
                        target_dt = datetime.fromtimestamp(target_raw, timezone.utc)
                    else:
                        target_dt = datetime.fromisoformat(str(target_raw).replace("Z", "+00:00"))
                    if curr_now < target_dt:
                        return False
                except Exception as e:
                    logger.warning(f"Invalid timestamp in countdown condition ({target_raw}): {e}")
                    return False

        # 2. Host Hardware & System Vitals Thresholds (e.g. RAM > 85%)
        if condition_type == "vitals" or "ram_percent_gt" in condition or "ram_percent_lt" in condition:
            try:
                from core.service import get_host_vitals
                vitals = get_host_vitals()
                ram_used = vitals.get("ram_used_percent", 0.0)
                if "ram_percent_gt" in condition and ram_used < float(condition["ram_percent_gt"]):
                    return False
                if "ram_percent_lt" in condition and ram_used > float(condition["ram_percent_lt"]):
                    return False
            except Exception as e:
                logger.warning(f"Could not inspect host vitals for rule: {e}")
                return False

        # 3. Periodic recurring interval
        if condition_type == "periodic":
            return True

        # 4. Check required room/spatial state
        if "require_state" in condition:
            for room_id, expected_kv in condition["require_state"].items():
                actual_state = self.state_manager.get_room_state(room_id) or {}
                for k, v in expected_kv.items():
                    if actual_state.get(k) != v:
                        return False

        # 5. Check roaming device zone
        if "require_device_zone" in condition:
            for device_id, expected_zone in condition["require_device_zone"].items():
                device_rec = self.state_manager.get_device_record(device_id)
                if not device_rec or device_rec.current_zone != expected_zone:
                    return False

        return True
