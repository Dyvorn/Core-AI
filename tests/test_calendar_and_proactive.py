import os
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock

from core.state import StateManager
from core.bus import EventBus
from core.schemas import CalendarEventRecord
from tools.native.calendar_tools import (
    manage_calendar,
    reconcile_schedule_evidence,
    get_upcoming_schedule,
    set_state_manager as set_cal_sm
)
from brain.proactive import ProactiveDaemon
from brain.planner import Planner
from brain.pipeline_engine import PipelineEngine
from tools.registry import ToolRegistry


@pytest.fixture
def temp_sm(tmp_path):
    db_file = str(tmp_path / "test_core_ai.db")
    sm = StateManager(db_path=db_file)
    set_cal_sm(sm)
    return sm


def test_state_manager_calendar_migration_and_crud(temp_sm):
    assert temp_sm.get_schema_version() >= 4

    # Create event
    now = datetime.now(timezone.utc)
    start_dt = now + timedelta(hours=3)
    event = temp_sm.create_calendar_event(
        title="Engineering Design Review",
        start_time=start_dt.isoformat(),
        location="Studio Conference Link",
        preparation_notes="Review architectural RFC and benchmark results",
        preparation_minutes=45,
        source="user"
    )
    assert event["id"] is not None
    assert event["title"] == "Engineering Design Review"
    assert event["preparation_minutes"] == 45
    assert not event["prep_notified"]

    # List events
    events = temp_sm.list_calendar_events()
    assert len(events) == 1
    assert events[0]["id"] == event["id"]

    # Get event
    fetched = temp_sm.get_calendar_event(event["id"])
    assert fetched is not None
    assert fetched["title"] == "Engineering Design Review"

    # Mark notified
    ok = temp_sm.mark_event_notified(event["id"], prep_notified=True)
    assert ok
    fetched_updated = temp_sm.get_calendar_event(event["id"])
    assert fetched_updated["prep_notified"] == 1

    # Find events
    found = temp_sm.find_calendar_events("Engineering")
    assert len(found) == 1

    # Delete event
    del_ok = temp_sm.delete_calendar_event(event["id"])
    assert del_ok
    assert temp_sm.get_calendar_event(event["id"]) is None


def test_sqlite_concurrent_non_locking(temp_sm):
    import threading
    errors = []

    def writer_task(idx):
        try:
            for i in range(10):
                temp_sm.set_kv(f"thread_{idx}_key_{i}", {"val": i})
                temp_sm.create_calendar_event(
                    title=f"Event {idx}-{i}",
                    start_time=datetime.now(timezone.utc).isoformat()
                )
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer_task, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent database operations produced errors: {errors}"


def test_native_calendar_tools(temp_sm):
    # 1. Create appointment via manage_calendar
    res = manage_calendar(
        action="create",
        title="Quarterly Review",
        start_time="in 2 hours",
        preparation_notes="Prepare deck",
        preparation_minutes=20
    )
    assert res["status"] == "success"
    assert "Quarterly Review" in res["message"]
    event_id = res["event"]["id"]

    # 2. List schedule
    list_res = manage_calendar(action="list")
    assert list_res["status"] == "success"
    assert list_res["count"] >= 1

    # 3. Get upcoming schedule with buffers
    sched_res = get_upcoming_schedule(horizon_hours=24.0)
    assert sched_res["status"] == "success"
    assert sched_res["count"] >= 1
    app = sched_res["appointments"][0]
    assert app["title"] == "Quarterly Review"
    assert app["preparation_minutes"] == 20

    # 4. Cancel appointment
    del_res = manage_calendar(action="delete", event_id=event_id)
    assert del_res["status"] == "success"


def test_reconcile_schedule_evidence(temp_sm):
    # Case 1: Unscheduled mention -> auto schedules
    text = "I have a dentist appointment tomorrow at 14:00, need to bring insurance card"
    res1 = reconcile_schedule_evidence(text, context_source="conversation")
    assert res1["status"] == "reconciled"
    assert res1["action_taken"] == "auto_scheduled"
    assert "Dentist" in res1["title"] or "dentist" in res1["title"].lower()
    assert "insurance card" in res1["preparation_notes"]
    assert "wasn't on your calendar" in res1["message"]

    # Case 2: Mentioning the same appointment again -> detects duplicate
    res2 = reconcile_schedule_evidence(text, context_source="conversation")
    assert res2["status"] == "already_scheduled"
    assert "already in your calendar" in res2["message"]


@pytest.mark.anyio
async def test_proactive_calendar_preparation_anticipation(temp_sm):
    # Setup appointment starting in 20 minutes with 30m prep buffer
    now = datetime.now(timezone.utc)
    start_dt = now + timedelta(minutes=20)
    ev = temp_sm.create_calendar_event(
        title="Doctor Appointment",
        start_time=start_dt.isoformat(),
        preparation_notes="Bring medical history",
        preparation_minutes=30
    )

    bus = MagicMock()
    planner = MagicMock()
    pipeline_engine = MagicMock()

    daemon = ProactiveDaemon(
        state_manager=temp_sm,
        planner=planner,
        pipeline_engine=pipeline_engine,
        bus=bus
    )

    await daemon._check_calendar_anticipations(now)

    # Verify notification published to bus
    assert bus.publish.called
    args, kwargs = bus.publish.call_args
    assert args[0] == "tts_events"
    event_payload = args[1]
    assert "Doctor Appointment" in event_payload.speech_text
    assert "20 minutes" in event_payload.speech_text
    assert "Bring medical history" in event_payload.speech_text

    # Verify marked notified in database (no double firing)
    updated = temp_sm.get_calendar_event(ev["id"])
    assert updated["prep_notified"] == 1

    bus.publish.reset_mock()
    # Second evaluation should NOT fire again
    await daemon._check_calendar_anticipations(now)
    assert not bus.publish.called


@pytest.mark.anyio
async def test_proactive_daemon_unreconciled_note_reconciliation(temp_sm):
    # Save a scratch note mentioning an appointment
    temp_sm.set_kv("note:dentist", {
        "title": "Dentist Appointment",
        "content": "Meeting Dr. Meyer tomorrow at 15:00, prepare x-rays"
    })

    bus = MagicMock()
    planner = MagicMock()
    pipeline_engine = MagicMock()

    daemon = ProactiveDaemon(
        state_manager=temp_sm,
        planner=planner,
        pipeline_engine=pipeline_engine,
        bus=bus
    )

    now = datetime.now(timezone.utc)
    await daemon._check_unreconciled_notes(now)

    # Verify event was auto-scheduled in calendar
    events = temp_sm.list_calendar_events()
    assert len(events) >= 1
    scheduled = [e for e in events if "Dentist" in e["title"] or "Dr. Meyer" in e.get("evidence_text", "")][0]
    assert scheduled["source"] == "reconciliation"

    # Verify notification sent informing operator
    assert bus.publish.called
    args, _ = bus.publish.call_args
    event_payload = args[1]
    assert "you mentioned an appointment" in event_payload.speech_text.lower()

    # Verify note is marked reconciled
    note_val = temp_sm.get_kv("note:dentist")
    assert note_val["schedule_reconciled"] is True


def test_planner_calendar_heuristic_and_spoken(temp_sm):
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    registry.register_tool("manage_calendar", manage_calendar, {})
    registry.register_tool("reconcile_schedule_evidence", reconcile_schedule_evidence, {})
    registry.register_tool("get_upcoming_schedule", get_upcoming_schedule, {})

    planner = Planner(registry=registry, state_manager=temp_sm)

    # 1. Inspection goal
    plan1 = planner.plan_problem("what are my appointments today")
    assert len(plan1.steps) == 1
    assert plan1.steps[0].tool_name == "get_upcoming_schedule"
    assert plan1.context.get("mode") == "instant_heuristic"

    # 2. Create goal
    plan2 = planner.plan_problem("add appointment dentist tomorrow at 15:00")
    assert len(plan2.steps) == 1
    assert plan2.steps[0].tool_name == "manage_calendar"

    # 3. Reconciliation goal
    plan3 = planner.plan_problem("reconcile schedule mentions from chat")
    assert len(plan3.steps) == 1
    assert plan3.steps[0].tool_name == "reconcile_schedule_evidence"
