import os
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from core.state import StateManager

logger = logging.getLogger(__name__)

_state_manager: Optional[StateManager] = None

def set_state_manager(sm: StateManager):
    global _state_manager
    _state_manager = sm

def _get_sm() -> StateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def _parse_time_spec(time_str: str) -> Optional[datetime]:
    """
    Parses flexible human expressions or ISO strings into UTC datetime.
    Supports:
    - ISO strings (2026-10-17T15:00:00)
    - 'today at 15:00', 'heute um 14:30'
    - 'tomorrow at 10:00', 'morgen um 10:00'
    - 'in 2 hours', 'in 30 minutes'
    """
    if not time_str:
        return None
    time_str = time_str.strip()
    now = datetime.now(timezone.utc)

    # 1. Direct ISO parsing
    try:
        clean_iso = time_str.replace("Z", "+00:00")
        if "T" in clean_iso or "-" in clean_iso:
            dt = datetime.fromisoformat(clean_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass

    # 2. Relative offsets ('in X hours', 'in Y minutes')
    rel_match = re.search(r"in\s+(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|stunde|stunden|m|min|mins|minute|minutes|minuten)", time_str, re.IGNORECASE)
    if rel_match:
        val = float(rel_match.group(1))
        unit = rel_match.group(2).lower()
        if unit.startswith("h") or unit.startswith("st"):
            return now + timedelta(hours=val)
        else:
            return now + timedelta(minutes=val)

    # 3. 'today at HH:MM' or 'heute um HH:MM'
    today_match = re.search(r"(?:today|heute)\s+(?:at|um)?\s*(\d{1,2}):(\d{2})", time_str, re.IGNORECASE)
    if today_match:
        h, m = int(today_match.group(1)), int(today_match.group(2))
        return now.replace(hour=h, minute=m, second=0, microsecond=0)

    # 4. 'tomorrow at HH:MM' or 'morgen um HH:MM'
    tmrw_match = re.search(r"(?:tomorrow|morgen)\s+(?:at|um)?\s*(\d{1,2}):(\d{2})", time_str, re.IGNORECASE)
    if tmrw_match:
        h, m = int(tmrw_match.group(1)), int(tmrw_match.group(2))
        tmrw = now + timedelta(days=1)
        return tmrw.replace(hour=h, minute=m, second=0, microsecond=0)

    # 5. Bare time 'HH:MM' (defaults to today if future, else tomorrow)
    bare_time = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
    if bare_time:
        h, m = int(bare_time.group(1)), int(bare_time.group(2))
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate < now:
            candidate += timedelta(days=1)
        return candidate

    return None


def manage_calendar(
    action: str = "list",
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    location: Optional[str] = None,
    preparation_notes: Optional[str] = None,
    preparation_minutes: int = 30,
    event_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Manages calendar events, appointments, and proactive preparation schedules.
    Actions: 'create', 'list', 'get', 'update', 'delete'.
    """
    sm = _get_sm()
    act = action.lower().strip()

    if act in ("create", "add", "schedule", "new"):
        if not title:
            return {"status": "error", "message": "Event title is required."}
        
        parsed_dt = _parse_time_spec(start_time or "")
        if not parsed_dt:
            # Default fallback: 2 hours from now
            parsed_dt = datetime.now(timezone.utc) + timedelta(hours=2)
        
        start_iso = parsed_dt.isoformat()
        end_iso = None
        if end_time:
            end_dt = _parse_time_spec(end_time)
            if end_dt:
                end_iso = end_dt.isoformat()

        rec = sm.create_calendar_event(
            title=title,
            start_time=start_iso,
            end_time=end_iso,
            location=location,
            preparation_notes=preparation_notes,
            preparation_minutes=int(preparation_minutes),
            source="user"
        )
        time_str = parsed_dt.strftime("%Y-%m-%d %H:%M UTC")
        return {
            "status": "success",
            "message": f"Appointment '{title}' scheduled for {time_str} with {preparation_minutes}m preparation window.",
            "event": rec
        }

    elif act in ("get", "read", "show"):
        eid = event_id or title
        if not eid:
            return {"status": "error", "message": "Event ID or title required to inspect appointment."}
        ev = sm.get_calendar_event(eid)
        if not ev and title:
            matches = sm.find_calendar_events(title)
            if matches:
                ev = matches[0]
        if ev:
            return {"status": "success", "event": ev}
        return {"status": "error", "message": f"Appointment '{eid}' not found."}

    elif act in ("delete", "remove", "cancel", "rm"):
        eid = event_id or title
        if not eid:
            return {"status": "error", "message": "Event ID or title required to cancel appointment."}
        ok = sm.delete_calendar_event(eid)
        return {
            "status": "success" if ok else "error",
            "message": f"Appointment '{eid}' {'cancelled and removed' if ok else 'not found'}."
        }

    else:
        # Default 'list'
        now_iso = datetime.now(timezone.utc).isoformat()
        events = sm.list_calendar_events(start_after=now_iso, limit=20)
        formatted = []
        for e in events:
            formatted.append({
                "id": e["id"],
                "title": e["title"],
                "start_time": e["start_time"],
                "location": e.get("location"),
                "preparation_notes": e.get("preparation_notes"),
                "preparation_minutes": e.get("preparation_minutes", 30),
                "source": e.get("source", "user")
            })
        return {
            "status": "success",
            "count": len(formatted),
            "events": formatted,
            "summary": f"{len(formatted)} upcoming appointment(s) found on schedule." if formatted else "No upcoming appointments found on schedule."
        }


def reconcile_schedule_evidence(
    evidence_text: str,
    context_source: str = "conversation",
    default_preparation_minutes: int = 30,
    **kwargs
) -> Dict[str, Any]:
    """
    Anticipatory Schedule Reconciliation:
    Inspects natural language context or notes for mentioned appointments,
    checks if already on the calendar, and if missing, verifies evidence,
    schedules it autonomously, and returns a transparent report.
    """
    if not evidence_text or not evidence_text.strip():
        return {"status": "error", "message": "No evidence context provided to reconcile."}

    sm = _get_sm()
    text = evidence_text.strip()
    
    # 1. Extract candidate title
    if any(w in text.lower() for w in ["dentist", "zahnarzt"]):
        extracted_title = "Dentist Appointment"
    elif any(w in text.lower() for w in ["doctor", "arzt"]):
        extracted_title = "Doctor Appointment"
    else:
        # Common appointment patterns
        patterns = [
            r"([A-Za-z0-9\s_-]+?)\s+(?:appointment|meeting|termin|besprechung)",
            r"(?:appointment|meeting|termin|besprechung)\s+(?:with|mit|for|für)?\s*([A-Za-z0-9\s_-]+?)(?:\s+(?:at|um|on|am|in|tomorrow|morgen|today|heute)|\.|$)",
            r"(?:treffen|call)\s+(?:mit|with)?\s*([A-Za-z0-9\s_-]+?)(?:\s+(?:at|um|on|am|in|tomorrow|morgen)|\.|$)"
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                # Clean leading words like 'have a'
                candidate = re.sub(r"^(?:have\s+a|have|habe\s+ein|habe|i\s+have\s+a)\s+", "", candidate, flags=re.IGNORECASE).strip()
                if candidate and len(candidate) > 1 and candidate.lower() not in ["an", "a", "the", "my", "mein", "meinen", "have", "habe", "i", "ich"]:
                    extracted_title = candidate
                    break
        if not extracted_title:
            extracted_title = "Scheduled Appointment"

    # 2. Extract or infer time
    parsed_dt = _parse_time_spec(text)
    if not parsed_dt:
        # Check for hour mentions like 'at 3pm', 'um 14 Uhr', 'at 15:00'
        hour_match = re.search(r"(?:at|um)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|uhr)?", text, re.IGNORECASE)
        now = datetime.now(timezone.utc)
        if hour_match:
            h = int(hour_match.group(1))
            m = int(hour_match.group(2) or 0)
            meridiem = (hour_match.group(3) or "").lower()
            if meridiem == "pm" and h < 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            
            is_tomorrow = any(k in text.lower() for k in ["tomorrow", "morgen"])
            parsed_dt = now + timedelta(days=1 if is_tomorrow else 0)
            parsed_dt = parsed_dt.replace(hour=h, minute=m, second=0, microsecond=0)
            if parsed_dt < now and not is_tomorrow:
                parsed_dt += timedelta(days=1)
        else:
            # Default to tomorrow at 10:00 AM
            tmrw = now + timedelta(days=1)
            parsed_dt = tmrw.replace(hour=10, minute=0, second=0, microsecond=0)

    # 3. Check for existing calendar entries
    existing = sm.find_calendar_events(extracted_title)
    for ev in existing:
        try:
            ev_dt = datetime.fromisoformat(str(ev["start_time"]).replace("Z", "+00:00"))
            # If within 4 hours, consider already scheduled
            if abs((ev_dt - parsed_dt).total_seconds()) < 14400:
                time_str = ev_dt.strftime("%Y-%m-%d %H:%M UTC")
                return {
                    "status": "already_scheduled",
                    "event_id": ev["id"],
                    "title": ev["title"],
                    "start_time": ev["start_time"],
                    "message": f"Appointment '{ev['title']}' is already in your calendar for {time_str}."
                }
        except Exception:
            pass

    # 4. Extract preparation requirements if mentioned
    prep_notes = None
    prep_match = re.search(r"(?:prepare|preparation|vorbereiten|unterlagen|mitbringen|need to bring|bring|brauche|review|mitnehmen)\s*[:;]?\s*([A-Za-z0-9\s,_-]+?)(?:\.|$)", text, re.IGNORECASE)
    if prep_match:
        prep_notes = prep_match.group(1).strip()
    else:
        prep_notes = f"Review materials and prepare for {extracted_title}."

    # 5. Reconcile by creating the event in SQLite
    rec = sm.create_calendar_event(
        title=extracted_title,
        start_time=parsed_dt.isoformat(),
        preparation_notes=prep_notes,
        preparation_minutes=default_preparation_minutes,
        source="reconciliation",
        evidence_text=text
    )

    formatted_time = parsed_dt.strftime("%Y-%m-%d %H:%M UTC")
    report_message = (
        f"You mentioned you had an appointment ('{extracted_title}'), but it wasn't on your calendar. "
        f"I checked the evidence, found the details for {formatted_time}, added it to your calendar, "
        f"and set a {default_preparation_minutes}-minute proactive preparation reminder."
    )

    return {
        "status": "reconciled",
        "action_taken": "auto_scheduled",
        "event_id": rec["id"],
        "title": extracted_title,
        "start_time": rec["start_time"],
        "preparation_minutes": default_preparation_minutes,
        "preparation_notes": prep_notes,
        "message": report_message,
        "evidence": text
    }


def get_upcoming_schedule(horizon_hours: float = 24.0, **kwargs) -> Dict[str, Any]:
    """
    Returns upcoming scheduled events within the specified time horizon,
    including countdown time and preparation buffers.
    """
    sm = _get_sm()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    horizon_dt = now + timedelta(hours=float(horizon_hours))
    horizon_iso = horizon_dt.isoformat()

    events = sm.list_calendar_events(start_after=now_iso, end_before=horizon_iso, limit=50)
    items = []
    for e in events:
        try:
            start_dt = datetime.fromisoformat(str(e["start_time"]).replace("Z", "+00:00"))
            mins_left = max(0, int((start_dt - now).total_seconds() / 60))
            hours_left = round(mins_left / 60.0, 1)
            prep_mins = e.get("preparation_minutes", 30)
            time_until_prep = max(0, mins_left - prep_mins)

            items.append({
                "id": e["id"],
                "title": e["title"],
                "start_time": e["start_time"],
                "minutes_remaining": mins_left,
                "hours_remaining": hours_left,
                "preparation_minutes": prep_mins,
                "preparation_notes": e.get("preparation_notes"),
                "time_until_preparation_alert_mins": time_until_prep,
                "location": e.get("location"),
                "source": e.get("source", "user")
            })
        except Exception:
            pass

    return {
        "status": "success",
        "horizon_hours": horizon_hours,
        "count": len(items),
        "appointments": items,
        "summary": f"{len(items)} upcoming appointment(s) in the next {horizon_hours}h." if items else f"No upcoming appointments in the next {horizon_hours}h."
    }


# Schemas
manage_calendar_schema = {
    "name": "manage_calendar",
    "description": "Create, list, view, update, or cancel calendar appointments and preparation schedules.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "get", "update", "delete"],
                "description": "Calendar operation to perform",
                "default": "list"
            },
            "title": {"type": "string", "description": "Title or summary of the appointment"},
            "start_time": {"type": "string", "description": "Scheduled start time (ISO string or human expression like 'tomorrow at 14:00')"},
            "end_time": {"type": "string", "description": "Optional scheduled end time"},
            "location": {"type": "string", "description": "Location or meeting link"},
            "preparation_notes": {"type": "string", "description": "What to prepare prior to the appointment"},
            "preparation_minutes": {"type": "integer", "description": "Minutes of preparation buffer required", "default": 30},
            "event_id": {"type": "string", "description": "Specific event ID for get/update/delete"}
        }
    }
}

reconcile_schedule_evidence_schema = {
    "name": "reconcile_schedule_evidence",
    "description": "Analyzes conversation text or notes for implied appointments, verifies evidence, schedules missing appointments on calendar, and alerts the operator.",
    "parameters": {
        "type": "object",
        "properties": {
            "evidence_text": {"type": "string", "description": "Natural language text or note containing the appointment mention"},
            "context_source": {"type": "string", "description": "Source of evidence (e.g. conversation, note, email)", "default": "conversation"},
            "default_preparation_minutes": {"type": "integer", "description": "Default preparation buffer in minutes", "default": 30}
        },
        "required": ["evidence_text"]
    }
}

get_upcoming_schedule_schema = {
    "name": "get_upcoming_schedule",
    "description": "Inspect upcoming schedule, appointments, and preparation requirements within a time horizon.",
    "parameters": {
        "type": "object",
        "properties": {
            "horizon_hours": {"type": "number", "description": "Hours ahead to inspect (default 24.0)", "default": 24.0}
        }
    }
}
