import pytest
import os
import asyncio
from core.state import StateManager
from core.bus import EventBus
from core.schemas import ProactiveTriggerRule
from tools.registry import ToolRegistry
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from brain.proactive import ProactiveDaemon

@pytest.mark.anyio
async def test_proactive_daemon_trigger_evaluation(tmp_path):
    state_file = os.path.join(tmp_path, "test_proactive.db")
    state = StateManager(db_path=state_file)
    bus = EventBus()
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry, state_manager=state)
    engine = PipelineEngine(registry=registry, state_manager=state, bus=bus)

    daemon = ProactiveDaemon(
        state_manager=state,
        planner=planner,
        pipeline_engine=engine,
        bus=bus,
        check_interval_seconds=0.1
    )

    # 1. Condition: living room window is open
    rule = ProactiveTriggerRule(
        rule_id="rule_window_check",
        name="Open Window Alert",
        condition_type="state_change",
        trigger_condition={
            "require_state": {
                "room_living": {"window": "open"}
            }
        },
        action_goal="Inform user that window is open",
        target_zone="mobile/vehicle/car",
        cooldown_seconds=1
    )
    state.save_proactive_rule(rule)

    # State not matching yet
    state.set_room_state("room_living", {"window": "closed"})
    await daemon.evaluate_triggers()
    updated_rules = state.get_active_proactive_rules()
    assert updated_rules[0].last_triggered_at is None

    # Update state to open -> should trigger
    state.set_room_state("room_living", {"window": "open"})
    await daemon.evaluate_triggers()

    updated_rules = state.get_active_proactive_rules()
    assert updated_rules[0].last_triggered_at is not None
