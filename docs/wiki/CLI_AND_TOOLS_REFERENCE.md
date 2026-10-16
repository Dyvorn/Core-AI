# Core AI — CLI & Tools Master Reference

```text
========================================================================================
[ SUBSYSTEM: TOOLS & CLI REFERENCE ]   [ ENTRYPOINT: core / main.py ] [ VERSION: v0.2.3 ]
[ SCOPE: FULL OPERATIONAL DICTIONARY ]  [ LICENSE: AGPL-3.0-ONLY ]
========================================================================================
```

## 1. CLI Commands (`core` & `main.py`)

Core AI provides a unified Windows and POSIX wrapper: `core.bat` (Windows) and `core.sh` (Linux/macOS).

### 1.1 Process Management & Lifecycle
| Command | Description | Example |
| :--- | :--- | :--- |
| `core start` | Starts background microkernel daemon with voice online. | `core start --port 8000` |
| `core stop` | Gracefully terminates daemon, freeing RAM/GPU/VRAM. | `core stop` |
| `core restart` | Performs clean reboot of background daemon. | `core restart` |
| `core status` | Displays high-contrast status card with PID and vitals. | `core status` |
| `core update` | Pulls Git updates, runs test suite, rolls back on failure. | `core update` |
| `core clean` | Purges database and logs while preserving environment. | `core clean` |
| `core setup` | Interactive terminal configuration wizard. | `core setup` |

### 1.2 One-Shot Instant Task Dispatch
Running `core "<goal>"` connects directly to the background daemon via lightweight IPC (<50ms):
```bash
core "what time is it"
core "git status"
core "remind me in 10 minutes to review code"
core "watch my ram"
core "save note project_ideas: build sovereign mesh"
core "what are my upcoming appointments"
core "reconcile schedule mentions"
```

### 1.3 Distributed Satellites & Sovereign Mesh
| Command | Description | Example |
| :--- | :--- | :--- |
| `core satellite` | Spawns edge microphone/speaker voice satellite node. | `core satellite --node-id office_sat --server http://192.168.1.100:8000` |
| `core mesh ping` | Tests round-trip latency to central host (<1ms). | `core mesh ping` |
| `core mesh sync [full\|push\|pull]` | Synchronizes SQLite state deltas across mesh nodes. | `core mesh sync full` |
| `core mesh nodes` | Lists all active connected edge nodes and satellites. | `core mesh nodes` |
| `core mesh export [file]` | Bundles state (profile, zones, audio routes) into portable JSON. | `core mesh export backup.json` |
| `core mesh import <file>` | Restores state bundle onto a new central host. | `core mesh import backup.json` |

---

## 2. Native Tools Reference Catalog

### 2.1 Calendar & Anticipatory Schedule Tools (`tools/native/calendar_tools.py`)

#### `manage_calendar`
Creates, lists, inspects, updates, or cancels calendar appointments with preparation buffers.
- **Parameters**:
  - `action`: `str` (`'create'`, `'list'`, `'get'`, `'update'`, `'delete'`). Default: `'list'`.
  - `title`: `str` (Optional). Title of the appointment.
  - `start_time`: `str` (Optional). ISO string or natural relative time (`"tomorrow at 14:00"`, `"in 2 hours"`).
  - `end_time`: `str` (Optional). Scheduled end time.
  - `location`: `str` (Optional). Physical address or conference link.
  - `preparation_notes`: `str` (Optional). Actions or materials required before the event.
  - `preparation_minutes`: `int` (Optional). Buffer time in minutes (default: 30).
  - `event_id`: `str` (Optional). Unique ID for get/update/delete.
- **Return**: `{ "status": "success", "event": {...}, "message": "..." }`.

#### `reconcile_schedule_evidence`
Scans conversation or note text for implicit appointment commitments, verifies existing schedule, and auto-schedules missing events with preparation reminders.
- **Parameters**:
  - `evidence_text`: `str` (Required). Natural language text containing the mention.
  - `context_source`: `str` (Optional). Source of evidence (e.g. `'conversation'`, `'note'`).
  - `default_preparation_minutes`: `int` (Optional). Default buffer (30).
- **Return**:
  ```json
  {
    "status": "reconciled",
    "action_taken": "auto_scheduled",
    "title": "Dentist Appointment",
    "start_time": "2026-10-17T14:00:00+00:00",
    "preparation_minutes": 30,
    "message": "You mentioned an appointment ('Dentist Appointment'), but it wasn't on your calendar..."
  }
  ```

#### `get_upcoming_schedule`
Inspects upcoming appointments within a time horizon, returning minutes/hours remaining and preparation alert timing.
- **Parameters**:
  - `horizon_hours`: `float` (Default: 24.0).
- **Return**: `{ "status": "success", "count": 2, "appointments": [...] }`.

---

### 2.2 Developer & Productivity Tools (`tools/native/dev_tools.py`)

#### `get_git_status`
Audits repository branch, clean/dirty state, modified files, untracked files, and recent commit.
- **Parameters**:
  - `repo_path`: `str` (Optional). Target directory (defaults to current project).
- **Return**: `{ "branch": "main", "is_clean": true, "summary": "Working tree clean." }`.

#### `manage_notes`
Stores, retrieves, lists, and deletes key-value operator notes in SQLite WAL.
- **Parameters**:
  - `action`: `str` (`'save'`, `'get'`, `'list'`, `'delete'`). Default: `'list'`.
  - `title`: `str` (Optional). Note key/title.
  - `content`: `str` (Optional). Note body.
- **Return**: `{ "status": "success", "notes": [...] }`.

---

### 2.3 Proactive Supervisor & Reminder Tools (`tools/native/proactive_tools.py`)

#### `create_reminder`
Schedules a natural language countdown reminder with automatic daemon deactivation upon firing.
- **Parameters**:
  - `reminder_text`: `str` (Required). The prompt to announce.
  - `minutes`: `float`, `seconds`: `float`, `hours`: `float`.
- **Return**: `{ "status": "success", "message": "Reminder scheduled for 'review PR' in 10.0m" }`.

#### `create_vitals_watcher`
Monitors system hardware metrics (RAM, CPU) in the background and alerts the operator if crossed.
- **Parameters**:
  - `metric`: `str` (`'ram'`, `'cpu'`). Default: `'ram'`.
  - `threshold_percent`: `float` (Default: 85.0).
  - `action_goal`: `str` (Optional). Custom action to take on threshold breach.

#### `list_active_rules`
Returns all active countdown timers, vitals watchers, and scheduled rules with seconds remaining.

#### `cancel_proactive_rule`
Cancels a proactive rule or countdown reminder by ID or forgiving substring match.

---

### 2.4 Desktop & Operating System Tools (`tools/native/desktop_tools.py`, `system_tools.py`)

- `get_time`: Current local and UTC time with formatted string.
- `get_system_status`: OS architecture, CPU model, RAM metrics, Python runtime version.
- `inspect_system_resources`: Deterministic CPU load, RAM usage, and disk space with bilingual synthesis.
- `get_clipboard_text` / `set_clipboard_text`: Direct clipboard integration.
- `take_screenshot`: Captures desktop display to timestamped PNG.
- `launch_application` / `open_path_in_explorer`: OS application launcher.
- `list_running_processes` / `kill_process`: Inspects and terminates processes by PID or name.
- `lock_workstation`: Locks active OS user session.
- `media_control`: Play/pause/next/volume desktop multimedia controls.
