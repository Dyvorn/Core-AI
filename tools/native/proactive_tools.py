import os
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from core.schemas import ProactiveTriggerRule
from core.state import StateManager

logger = logging.getLogger(__name__)

# StateManager reference injected by setup_tools or default
_state_manager: Optional[StateManager] = None

def set_state_manager(sm: StateManager):
    global _state_manager
    _state_manager = sm

def _get_sm() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def create_reminder(
    reminder_text: str,
    minutes: float = 0.0,
    seconds: float = 0.0,
    hours: float = 0.0,
    delay_seconds: Optional[float] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Schedules an autonomous proactive reminder. The Core AI daemon will automatically
    fire and announce the reminder when the countdown completes.
    """
    total_seconds = delay_seconds if delay_seconds is not None else (hours * 3600 + minutes * 60 + seconds)
    if total_seconds <= 0:
        total_seconds = 60.0  # Default fallback 1 minute

    sm = _get_sm()
    now = datetime.now(timezone.utc)
    target_dt = now + timedelta(seconds=total_seconds)

    rule = ProactiveTriggerRule(
        name=f"Reminder: {reminder_text}",
        condition_type="countdown",
        trigger_condition={
            "target_timestamp_utc": target_dt.isoformat(),
            "one_shot": True
        },
        action_goal=f"announce reminder: {reminder_text}",
        priority="normal",
        cooldown_seconds=10
    )
    sm.save_proactive_rule(rule)

    target_local_str = target_dt.strftime("%H:%M:%S UTC")
    duration_str = f"{int(total_seconds)}s" if total_seconds < 60 else f"{round(total_seconds / 60, 1)}m"
    return {
        "status": "success",
        "message": f"Reminder scheduled for '{reminder_text}' in {duration_str} (at {target_local_str}).",
        "rule_id": rule.rule_id,
        "fire_at": target_dt.isoformat()
    }


def create_vitals_watcher(
    metric: str = "ram",
    threshold_percent: float = 85.0,
    action_goal: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Creates a background hardware supervisor rule that triggers an alert or action
    whenever system RAM or CPU exceeds the given threshold.
    """
    sm = _get_sm()
    metric_clean = metric.lower().strip()
    cond_key = f"{metric_clean}_percent_gt"

    goal = action_goal or f"alert operator that {metric_clean.upper()} reached {threshold_percent}%"
    rule = ProactiveTriggerRule(
        name=f"Hardware Watcher ({metric_clean.upper()} > {threshold_percent}%)",
        condition_type="vitals",
        trigger_condition={
            cond_key: float(threshold_percent)
        },
        action_goal=goal,
        priority="urgent",
        cooldown_seconds=300
    )
    sm.save_proactive_rule(rule)

    return {
        "status": "success",
        "message": f"Hardware supervisor active: watching {metric_clean.upper()} for threshold > {threshold_percent}%.",
        "rule_id": rule.rule_id
    }


def list_active_rules(**kwargs) -> Dict[str, Any]:
    """Lists all active proactive supervisor rules and scheduled reminders."""
    sm = _get_sm()
    rules = sm.get_active_proactive_rules()
    now = datetime.now(timezone.utc)

    items = []
    for r in rules:
        remaining_s = None
        if r.condition_type == "countdown" and "target_timestamp_utc" in r.trigger_condition:
            try:
                t_dt = datetime.fromisoformat(str(r.trigger_condition["target_timestamp_utc"]).replace("Z", "+00:00"))
                remaining_s = max(0, int((t_dt - now).total_seconds()))
            except Exception:
                pass

        items.append({
            "rule_id": r.rule_id,
            "name": r.name,
            "condition_type": r.condition_type,
            "action_goal": r.action_goal,
            "remaining_seconds": remaining_s,
            "priority": r.priority
        })

    return {
        "status": "success",
        "count": len(items),
        "rules": items
    }


def cancel_proactive_rule(name_or_id: str, **kwargs) -> Dict[str, Any]:
    """Cancels or deletes an active reminder or proactive supervisor rule."""
    sm = _get_sm()
    ok = sm.delete_proactive_rule(name_or_id)
    if ok:
        return {"status": "success", "message": f"Proactive rule or reminder '{name_or_id}' cancelled."}
    return {"status": "error", "message": f"Could not find active rule matching '{name_or_id}'."}


# Schemas
create_reminder_schema = {
    "name": "create_reminder",
    "description": "Schedule a countdown reminder (e.g. remind me in 5 minutes to take a break).",
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_text": {"type": "string", "description": "What to remind the operator about"},
            "minutes": {"type": "number", "description": "Minutes from now"},
            "seconds": {"type": "number", "description": "Seconds from now"},
            "hours": {"type": "number", "description": "Hours from now"}
        },
        "required": ["reminder_text"]
    }
}

create_vitals_watcher_schema = {
    "name": "create_vitals_watcher",
    "description": "Create a proactive hardware watcher (e.g. alert me when RAM exceeds 90%).",
    "parameters": {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "description": "Metric to watch, e.g. 'ram'", "default": "ram"},
            "threshold_percent": {"type": "number", "description": "Threshold percentage, e.g. 85.0", "default": 85.0},
            "action_goal": {"type": "string", "description": "Optional custom goal to execute when threshold is crossed"}
        },
        "required": ["threshold_percent"]
    }
}

list_active_rules_schema = {
    "name": "list_active_rules",
    "description": "List all active reminders and proactive supervisor rules.",
    "parameters": {"type": "object", "properties": {}}
}

cancel_proactive_rule_schema = {
    "name": "cancel_proactive_rule",
    "description": "Cancel or delete an active reminder or proactive rule by name or ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "name_or_id": {"type": "string", "description": "Rule name or rule ID"}
        },
        "required": ["name_or_id"]
    }
}
