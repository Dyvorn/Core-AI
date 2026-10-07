import os
import time
import pytest
from datetime import datetime, timezone, timedelta

from core.state import StateManager
from core.bus import EventBus
from tools.registry import ToolRegistry
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from brain.proactive import ProactiveDaemon

from tools.native.proactive_tools import (
    create_reminder,
    create_vitals_watcher,
    list_active_rules,
    cancel_proactive_rule,
    set_state_manager as set_proactive_sm
)
from tools.native.dev_tools import (
    get_git_status,
    manage_notes,
    set_state_manager as set_dev_sm
)
from main import setup_tools


@pytest.fixture
def fresh_state(tmp_path):
    db_file = os.path.join(tmp_path, "test_proactive_dev.db")
    sm = StateManager(db_path=db_file)
    set_proactive_sm(sm)
    set_dev_sm(sm)
    return sm


def test_create_and_list_reminder(fresh_state):
    res = create_reminder("Call dentist", seconds=30)
    assert res["status"] == "success"
    assert "Call dentist" in res["message"]
    rule_id = res["rule_id"]

    # Verify listing
    active = list_active_rules()
    assert active["status"] == "success"
    assert active["count"] >= 1
    names = [r["name"] for r in active["rules"]]
    assert any("Call dentist" in n for n in names)

    # Cancel
    cancel_res = cancel_proactive_rule(rule_id)
    assert cancel_res["status"] == "success"

    active_after = list_active_rules()
    assert all(r["rule_id"] != rule_id for r in active_after["rules"])


@pytest.mark.anyio
async def test_proactive_reminder_firing_and_auto_deactivation(tmp_path):
    db_file = os.path.join(tmp_path, "test_countdown.db")
    sm = StateManager(db_path=db_file)
    bus = EventBus()
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    planner = Planner(registry=registry, state_manager=sm)
    engine = PipelineEngine(registry=registry, state_manager=sm, bus=bus)

    daemon = ProactiveDaemon(
        state_manager=sm,
        planner=planner,
        pipeline_engine=engine,
        bus=bus,
        check_interval_seconds=0.05
    )

    set_proactive_sm(sm)
    # Schedule a reminder that is already due (delay 0 / target now or past)
    now = datetime.now(timezone.utc)
    from core.schemas import ProactiveTriggerRule
    rule = ProactiveTriggerRule(
        name="Past Reminder",
        condition_type="countdown",
        trigger_condition={
            "target_timestamp_utc": (now - timedelta(seconds=1)).isoformat(),
            "one_shot": True
        },
        action_goal="system status",
        priority="normal",
        cooldown_seconds=1
    )
    sm.save_proactive_rule(rule)

    assert len(sm.get_active_proactive_rules()) == 1

    # Run evaluation: condition is met -> should execute and auto-deactivate
    await daemon.evaluate_triggers()

    # Rule must be deactivated now
    active_now = sm.get_active_proactive_rules()
    assert len(active_now) == 0


def test_create_vitals_watcher(fresh_state):
    res = create_vitals_watcher(metric="ram", threshold_percent=90.0)
    assert res["status"] == "success"
    rule_id = res["rule_id"]

    active = list_active_rules()
    assert any(r["rule_id"] == rule_id for r in active["rules"])

    cancel_res = cancel_proactive_rule("Hardware Watcher")
    assert cancel_res["status"] == "success"


def test_get_git_status():
    status = get_git_status()
    assert status["status"] == "success"
    assert "branch" in status
    assert "is_clean" in status
    assert "summary" in status


def test_manage_notes(fresh_state):
    # Save Note
    save_res = manage_notes(action="save", title="deploy_target", content="prod-server-01")
    assert save_res["status"] == "success"

    # Read Note
    get_res = manage_notes(action="get", title="deploy_target")
    assert get_res["status"] == "success"
    assert get_res["content"] == "prod-server-01"

    # List Notes
    list_res = manage_notes(action="list")
    assert list_res["status"] == "success"
    assert list_res["count"] >= 1
    assert any(n["title"] == "deploy_target" for n in list_res["notes"])

    # Delete Note
    del_res = manage_notes(action="delete", title="deploy_target")
    assert del_res["status"] == "success"

    # Read After Delete
    not_found = manage_notes(action="get", title="deploy_target")
    assert not_found["status"] == "error"


def test_planner_heuristic_routing_and_spoken_response(fresh_state):
    registry = setup_tools(state=fresh_state)
    planner = Planner(registry=registry, state_manager=fresh_state, model_name="heuristic")

    # 1. Reminder routing
    plan = planner.plan_problem("remind me in 5 minutes to submit the PR")
    assert len(plan.steps) == 1
    assert plan.steps[0].tool_name == "create_reminder"
    assert "submit the pr" in plan.steps[0].arguments["reminder_text"].lower()
    assert plan.steps[0].arguments["minutes"] == 5.0
    assert plan.context.get("mode") == "instant_heuristic"

    # Simulate completed step and test spoken output
    plan.steps[0].status = "completed"
    plan.steps[0].output = {"status": "success", "message": "Reminder scheduled for submit the PR in 5m"}
    plan.status = "completed"
    spoken = planner.formulate_spoken_response(plan, profile=fresh_state.get_user_profile())
    assert "Reminder scheduled" in spoken

    # 2. List reminders routing
    plan_list = planner.plan_problem("list active reminders")
    assert len(plan_list.steps) == 1
    assert plan_list.steps[0].tool_name == "list_active_rules"

    # 3. Cancel reminder routing
    plan_cancel = planner.plan_problem("cancel reminder submit the PR")
    assert len(plan_cancel.steps) == 1
    assert plan_cancel.steps[0].tool_name == "cancel_proactive_rule"

    # 4. Git status routing
    plan_git = planner.plan_problem("git status")
    assert len(plan_git.steps) == 1
    assert plan_git.steps[0].tool_name == "get_git_status"

    plan_git.steps[0].status = "completed"
    plan_git.steps[0].output = {"status": "success", "branch": "main", "is_clean": True, "summary": "Working tree clean."}
    plan_git.status = "completed"
    spoken_git = planner.formulate_spoken_response(plan_git, profile=fresh_state.get_user_profile())
    assert "main" in spoken_git

    # 5. Scratch notes routing
    plan_note_save = planner.plan_problem("save note api_key: secret_1234")
    assert len(plan_note_save.steps) == 1
    assert plan_note_save.steps[0].tool_name == "manage_notes"
    assert plan_note_save.steps[0].arguments["title"] == "api_key"
    assert plan_note_save.steps[0].arguments["content"] == "secret_1234"

    plan_notes_list = planner.plan_problem("my notes")
    assert len(plan_notes_list.steps) == 1
    assert plan_notes_list.steps[0].tool_name == "manage_notes"
    assert plan_notes_list.steps[0].arguments["action"] == "list"
