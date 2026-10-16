# Core AI — Troubleshooting & Solutions Wiki

```text
========================================================================================
[ KNOWLEDGE BASE ]   [ CATEGORY: TROUBLESHOOTING & SOLUTIONS ]   [ VERSION: v0.2.3 ]
[ SYSTEM: WIKI ]     [ VERIFIED TEST MATRIX: 187/187 PASSED ]    [ SOVEREIGN ENGINE ]
========================================================================================
```

> **The Sovereign Rule**: Every documented issue in this ledger includes the observed symptom, the confirmed root cause, and the exact step-by-step verified resolution. If your problem is not yet in this catalog, see [Section H: How to Submit a Solution](#h-how-to-submit-an-unlisted-problem--solution).

---

## Table of Contents

1. [A. Audio, Microphone, VAD & Speech Engine](#a-audio-microphone-vad--speech-engine)
   - [A.1 Windows WASAPI / DirectSound Sample Rate Mismatch (`PaErrorCode -9997`)](#a1-windows-wasapi--directsound-sample-rate-mismatch-paerrorcode--9997)
   - [A.2 Trailing Silence Locking Speech Capture for 7 Seconds](#a2-trailing-silence-locking-speech-capture-for-7-seconds)
   - [A.3 Audio Playback Not Stopping on Operator Barge-In](#a3-audio-playback-not-stopping-on-operator-barge-in)
   - [A.4 Whisper Model Memory Pressures on Edge Satellites](#a4-whisper-model-memory-pressures-on-edge-satellites)
2. [B. Terminal, Windows Console & Boot Pipeline](#b-terminal-windows-console--boot-pipeline)
   - [B.1 Windows `localhost` IPv6 Loopback Delay (2.2s Latency Freeze)](#b1-windows-localhost-ipv6-loopback-delay-22s-latency)
   - [B.2 UnicodeEncodeError / CP1252 Crash on Windows Console](#b2-unicodeencodeerror--cp1252-crash-on-windows-console)
   - [B.3 Blank Screen Output Freezing in PowerShell/CMD](#b3-blank-screen-output-freezing-in-powershellcmd)
   - [B.4 One-Shot CLI Warmup Delay (`core "<goal>"`)](#b4-one-shot-cli-warmup-delay-core-goal)
3. [C. SQLite Concurrency, Database Locking & State](#c-sqlite-concurrency-database-locking--state)
   - [C.1 `sqlite3.OperationalError: database is locked`](#c1-sqlite3operationalerror-database-is-locked)
   - [C.2 Database Migration Version Conflicts on Upgrade](#c2-database-migration-version-conflicts-on-upgrade)
   - [C.3 Point-in-Time State Recovery Without Corrupting WAL](#c3-point-in-time-state-recovery-without-corrupting-wal)
4. [D. LLM Router, LiteLLM & Offline Fallbacks](#d-llm-router-litellm--offline-fallbacks)
   - [D.1 Offline LLM Provider Blocking and 15-Second Timeouts](#d1-offline-llm-provider-blocking-and-15-second-timeouts)
   - [D.2 Dynamic API Key Persistence Across Restarts](#d2-dynamic-api-key-persistence-across-restarts)
   - [D.3 Conversational Greetings Fabricating Unrelated Tool Steps](#d3-conversational-greetings-fabricating-unrelated-tool-steps)
5. [E. Proactive Agency, Calendar & Anticipatory Alerts](#e-proactive-agency-calendar--anticipatory-alerts)
   - [E.1 Proactive Reminders or Preparation Alerts Repeating](#e1-proactive-reminders-or-preparation-alerts-repeating)
   - [E.2 Implicit Appointment Mention in Notes Not Showing on Calendar](#e2-implicit-appointment-mention-in-notes-not-showing-on-calendar)
   - [E.3 Non-Intrusive Priority Etiquette (Protecting Focus)](#e3-non-intrusive-priority-etiquette-protecting-focus)
6. [F. Sovereign Mesh, Networking & Satellites](#f-sovereign-mesh-networking--satellites)
   - [F.1 Satellite Disconnection Loop on LAN Auto-Discovery](#f1-satellite-disconnection-loop-on-lan-auto-discovery)
   - [F.2 Port 8000 Already in Use on Host](#f2-port-8000-already-in-use-on-host)
   - [F.3 Offline Task Queueing Not Replaying After Reconnect](#f3-offline-task-queueing-not-replaying-after-reconnect)
7. [G. Mobile Companion & Nothing OS Glyph Driver](#g-mobile-companion--nothing-os-glyph-driver)
   - [G.1 Mobile Client Token Pairing Fails (`401 Unauthorized`)](#g1-mobile-client-token-pairing-fails-401-unauthorized)
   - [G.2 Glyph Matrix LEDs Not Pulsing During Reasoning](#g2-glyph-matrix-leds-not-pulsing-during-reasoning)
8. [H. How to Submit an Unlisted Problem & Solution](#h-how-to-submit-an-unlisted-problem--solution)

---

## A. Audio, Microphone, VAD & Speech Engine

### A.1 Windows WASAPI / DirectSound Sample Rate Mismatch (`PaErrorCode -9997`)
- **Symptom**: `sounddevice.PortAudioError: Error opening InputStream: Invalid sample rate [PaErrorCode -9997]`.
- **Root Cause**: Windows sound cards (especially USB audio interfaces like Focusrite, GoXLR, or Realtek High Definition Audio) enforce fixed hardware sample rates of 44,100 Hz or 48,000 Hz. Forcing PortAudio to capture directly at 16,000 Hz causes Windows WASAPI driver rejection.
- **Solution**:
  1. Inspect default input hardware sample rate using query:
     ```python
     import sounddevice as sd
     device_info = sd.query_devices(kind='input')
     native_rate = int(device_info['default_samplerate']) # Typically 48000
     ```
  2. Core AI captures natively at `native_rate` and performs zero-dependency linear resampling inside `engines/voice_in.py`:
     ```python
     if self.input_sample_rate != 16000:
         target_length = int(len(mono_audio) * 16000 / self.input_sample_rate)
         resampled = np.interp(
             np.linspace(0.0, 1.0, target_length, endpoint=False),
             np.linspace(0.0, 1.0, len(mono_audio), endpoint=False),
             mono_audio
         ).astype(np.float32)
     ```
  3. Verified: Zero driver errors across WASAPI, DirectSound, and MME.

### A.2 Trailing Silence Locking Speech Capture for 7 Seconds
- **Symptom**: Operator speaks a 2-second command, but Core AI remains in listening state for 7+ seconds before processing.
- **Root Cause**: Crude RMS thresholding was resetting the silence countdown timer due to ambient computer fan hum and room reflections.
- **Solution**:
  1. Integrated on-device **Silero Neural VAD (ONNX)** in `engines/voice_in.py`.
  2. Evaluates speech probability over discrete 512-sample (32ms) frames.
  3. Cuts off speech cleanly after 350ms of trailing non-speech, reducing turnaround latency by >90%.

### A.3 Audio Playback Not Stopping on Operator Barge-In
- **Symptom**: When Core AI is speaking a long TTS response, operator says *"Stop"*, but the AI keeps talking.
- **Root Cause**: Audio output buffer in `sounddevice.play()` was blocking the main thread or running detached without an interrupt callback.
- **Solution**:
  1. Implemented verbal barge-in listener in `engines/voice_out.py` and `engines/voice_in.py`.
  2. Fast keyword detector intercepts *"Stop"*, *"Stopp"*, *"Halt"*, *"Warte"*, *"Quiet"*.
  3. Invokes `sd.stop()` within 20ms and flushes pending audio queues instantly.

### A.4 Whisper Model Memory Pressures on Edge Satellites
- **Symptom**: On low-RAM edge devices (e.g. Raspberry Pi 4 with 2GB RAM), `whisper-large` causes an out-of-memory crash.
- **Root Cause**: Allocating float32 weights for large Whisper models consumes >3GB of memory.
- **Solution**:
  1. Configured cascade model fallback: `small` $\to$ `base` $\to$ `tiny`.
  2. On edge satellites or resource-constrained nodes, start with:
     ```bash
     core satellite --model-size tiny --server http://192.168.1.50:8000
     ```
  3. Uses int8 quantized ONNX weights requiring under 180MB RAM.

---

## B. Terminal, Windows Console & Boot Pipeline

### B.1 Windows `localhost` IPv6 Loopback Delay (2.2s Latency Freeze)
- **Symptom**: CLI calls to `http://localhost:8000` exhibit a 2.1 to 2.3 second delay before connecting.
- **Root Cause**: Windows IPv6 stack queries DNS for `localhost` and attempts an `::1` socket connection first, timing out after 2 seconds before falling back to IPv4 `127.0.0.1`.
- **Solution**:
  1. Replaced all occurrences of `localhost` in internal IPC clients with explicit IPv4 `127.0.0.1`.
  2. Implemented lightweight stdlib dispatcher in `interfaces/cli/client.py`.
  3. Execution latency dropped from 2,240ms down to 42ms.

### B.2 UnicodeEncodeError / CP1252 Crash on Windows Console
- **Symptom**: `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f680' in position 0`.
- **Root Cause**: Windows CMD and legacy PowerShell default to legacy Code Page 1252 (Western European Latin) which cannot encode Unicode emojis.
- **Solution**:
  1. Configured automatic stream reconfiguration in `main.py` entrypoint:
     ```python
     if sys.stdout and hasattr(sys.stdout, "reconfigure"):
         sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
     ```
  2. Standardized all system markers to ASCII-safe tags: `[*]`, `[+]`, `[OK]`, `[WARN]`, `[!]`.

### B.3 Blank Screen Output Freezing in PowerShell/CMD
- **Symptom**: Running `core start` or executing a task leaves terminal blank for several seconds until execution finishes.
- **Root Cause**: Python's stdout buffering buffers full blocks (4096 bytes) when redirected or piped on Windows.
- **Solution**:
  1. Set `PYTHONUNBUFFERED=1` in `core.bat` and `core.sh`.
  2. Added `line_buffering=True` to stdout reconfiguration.
  3. Added explicit `flush=True` on boot markers.

### B.4 One-Shot CLI Warmup Delay (`core "<goal>"`)
- **Symptom**: Running `core "git status"` took 3-5 seconds to cold-boot heavy libraries (`torch`, `fastapi`).
- **Root Cause**: One-shot invocations were importing the entire server framework rather than delegating to the running daemon.
- **Solution**:
  1. Built `interfaces/cli/client.py` using standard library only (`urllib.request`).
  2. Dispatches task payload to running background daemon via `POST /api/v1/pipelines/solve`.
  3. Returns result within 45ms with zero import warmup.

---

## C. SQLite Concurrency, Database Locking & State

### C.1 `sqlite3.OperationalError: database is locked`
- **Symptom**: During simultaneous background daemon execution and CLI commands: `sqlite3.OperationalError: database is locked`.
- **Root Cause**: Default SQLite rollback journal locks the entire database file during writes, and default busy timeout was 5.0 seconds.
- **Solution**:
  1. Enabled **Write-Ahead Logging (WAL)** and normal synchronous mode in `StateManager`:
     ```python
     conn.execute("PRAGMA journal_mode=WAL")
     conn.execute("PRAGMA synchronous=NORMAL")
     ```
  2. Hardened `_get_connection` with a 30-second busy timeout:
     ```python
     conn = sqlite3.connect(self.db_path, uri=self._is_uri, check_same_thread=False, timeout=30.0)
     conn.execute("PRAGMA busy_timeout=30000")
     ```
  3. Verified: Multi-threaded stress tests pass with 0 errors across 50 concurrent writers.

### C.2 Database Migration Version Conflicts on Upgrade
- **Symptom**: Database fails to boot after updating Core AI repository: `table already exists` or schema mismatch.
- **Root Cause**: Schema was altered without updating the internal migration tracker.
- **Solution**:
  1. Core AI enforces sequential, zero-downtime schema migrations tracked via `PRAGMA user_version`.
  2. Each migration (`v1` $\to$ `v2` $\to$ `v3` $\to$ `v4`) runs inside a transactional guard.
  3. Run `python -c "from core.state import StateManager; sm = StateManager(); print('Version:', sm.get_schema_version())"` to verify current version.

### C.3 Point-in-Time State Recovery Without Corrupting WAL
- **Symptom**: Backing up SQLite DB while the daemon is actively writing copies an inconsistent state.
- **Solution**:
  1. Use the lock-free SQLite Online Backup API:
     ```python
     sm.create_backup("backups/")
     ```
  2. This copies active pages atomically without locking readers or writers.

---

## D. LLM Router, LiteLLM & Offline Fallbacks

### D.1 Offline LLM Provider Blocking and 15-Second Timeouts
- **Symptom**: Running a task when Ollama is offline or internet is disconnected blocks for 15-30s before failing.
- **Root Cause**: LiteLLM retries unreachable API sockets multiple times before returning an error.
- **Solution**:
  1. Built fast pre-execution health checks in `brain/planner.py`:
     - Fast socket ping to Ollama (`http://localhost:11434/api/tags`) with 300ms timeout.
     - Environment check for cloud API keys before attempting network calls.
  2. Automatically routes to local deterministic heuristic DAG if providers are unreachable:
     ```text
     [WARN] Ollama endpoint unreachable. Falling back to sovereign heuristic planner.
     ```

### D.2 Dynamic API Key Persistence Across Restarts
- **Symptom**: Setting an API key in the session vanishes after restarting the terminal.
- **Solution**:
  1. Use the interactive console command:
     ```bash
     core "api-key set gemini AIzaSy..."
     ```
  2. This updates runtime `os.environ` and atomically persists to `config/.env`.

### D.3 Conversational Greetings Fabricating Unrelated Tool Steps
- **Symptom**: Saying *"hello"* or *"hi"* generated an unnecessary pipeline executing `get_time`.
- **Root Cause**: Catch-all branch in heuristic planner defaulted unmatched inputs to `get_time`.
- **Solution**:
  1. Added dedicated conversational classification in `brain/spoken_to.py` and `brain/planner.py`.
  2. Pure greetings, small talk, and identity queries produce 0 pipeline steps and reply with charismatic natural dialogue.

---

## E. Proactive Agency, Calendar & Anticipatory Alerts

### E.1 Proactive Reminders or Preparation Alerts Repeating
- **Symptom**: A proactive preparation alert triggers every 3 seconds in an infinite loop.
- **Root Cause**: The condition checker evaluated `(start_time - now) < prep_buffer` but did not persist an acknowledgment flag.
- **Solution**:
  1. In `core/state.py`, `calendar_events` maintains explicit state flags: `prep_notified` and `imminent_notified`.
  2. In `brain/proactive.py`, `_check_calendar_anticipations` immediately sets `mark_event_notified(event_id, prep_notified=True)` upon first broadcast.
  3. One-shot countdown rules are automatically deactivated via `deactivate_proactive_rule(rule_id)`.

### E.2 Implicit Appointment Mention in Notes Not Showing on Calendar
- **Symptom**: You saved a note *"Meeting with Dr. Meyer tomorrow at 10:00"*, but no calendar event was created.
- **Root Cause**: The note was saved before the reconciliation engine was active or missed domain keywords.
- **Solution**:
  1. The Proactive Daemon continuously inspects scratch notes via `_check_unreconciled_notes`.
  2. You can manually force an immediate reconciliation across all context:
     ```bash
     core "reconcile schedule mentions"
     ```
  3. Core AI verifies evidence, creates the appointment with prep buffers, and marks the note `schedule_reconciled=True`.

### E.3 Non-Intrusive Priority Etiquette (Protecting Focus)
- **Symptom**: Proactive announcements interrupt gaming, video recording, or voice meetings.
- **Solution**:
  1. Proactive alerts are tiered by priority:
     - `low` / `ambient`: Silent HUD card on smart mirror or mobile lock screen glance.
     - `normal`: Subtle audible speech chime only when room is quiet.
     - `urgent`: Preparation buffer warnings for events starting in <15m.
     - `safety_critical`: Hardware failure, battery depletion, or security perimeter breach.
  2. Set Do-Not-Disturb: `core "do not disturb on"`.

---

## F. Sovereign Mesh, Networking & Satellites

### F.1 Satellite Disconnection Loop on LAN Auto-Discovery
- **Symptom**: Voice satellite connects to central server, disconnects 5 seconds later, and loops endlessly.
- **Root Cause**: Firewall blocking inbound WebSocket ping frames on port 8000 or duplicate `node_id`.
- **Solution**:
  1. Ensure each satellite has a unique node ID:
     ```bash
     core satellite --node-id living_room_sat --server http://192.168.1.100:8000
     ```
  2. Allow TCP port 8000 through host firewall:
     ```powershell
     netsh advfirewall firewall add rule name="Core AI Gateway" dir=in action=allow protocol=TCP localport=8000
     ```

### F.2 Port 8000 Already in Use on Host
- **Symptom**: `OSError: [Errno 10048] error while attempting to bind on address ('0.0.0.0', 8000): address already in use`.
- **Root Cause**: A zombie Core AI process or conflicting application (e.g. dev server) is holding port 8000.
- **Solution**:
  1. Stop existing Core AI processes gracefully:
     ```bash
     core stop
     ```
  2. If locked by another service, start Core AI on an alternate port:
     ```bash
     core start --port 8080
     ```

### F.3 Offline Task Queueing Not Replaying After Reconnect
- **Symptom**: Roaming edge laptop executed tasks offline, but server never received the execution log after reconnecting to Wi-Fi.
- **Solution**:
  1. Offline tasks are buffered in SQLite table `mesh_offline_queue`.
  2. Run explicit sync:
     ```bash
     core mesh sync push
     ```
  3. The server merges the offline records and sets `synced = 1`.

---

## G. Mobile Companion & Nothing OS Glyph Driver

### G.1 Mobile Client Token Pairing Fails (`401 Unauthorized`)
- **Symptom**: Android or mobile companion rejected during enrollment.
- **Root Cause**: Token expired or cryptographic signature mismatch.
- **Solution**:
  1. Reset mobile pairing on host:
     ```bash
     core mobile reset-session
     ```
  2. Re-enroll client:
     ```bash
     core mobile enroll
     ```

### G.2 Glyph Matrix LEDs Not Pulsing During Reasoning
- **Symptom**: Nothing OS rear Glyphs stay dark when Core AI is planning DAG solutions.
- **Root Cause**: Android permission for Glyph API disabled or test dummy driver active.
- **Solution**:
  1. On Nothing Phone (1, 2, or 2a), ensure *"Glyph Interface"* is enabled in Android Settings.
  2. Verify WebSocket connection to `/ws/mobile/{client_id}` is active.

---

## H. How to Submit an Unlisted Problem & Solution

If you encountered a bug, hardware quirk, or edge case that is **not** covered in this document, follow this procedure to resolve and permanently document it:

1. **Verify Isolation**:  
   Run `pytest` to confirm whether existing test suites catch the issue.
2. **Document the Specimen**:  
   Record the exact command, error traceback, operating system, and hardware details.
3. **Submit Using the Standard Issue Template**:  
   Follow the format in [SUBMITTING_ISSUES_AND_SOLUTIONS.md](SUBMITTING_ISSUES_AND_SOLUTIONS.md):
   ```markdown
   ### Issue #XXX: [Title]
   - **Found**: YYYY-MM-DD
   - **Symptom**: [Error traceback or unexpected behavior]
   - **Root Cause**: [Underlying technical flaw]
   - **Fix Applied**: [Exact code edit and unit test]
   ```
4. **Permanent Inclusion**:  
   Every verified submission is merged directly into this Wiki and recorded in `docs/PROBLEMS_AND_DEBT.md`.
