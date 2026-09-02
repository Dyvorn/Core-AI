# Core AI — Problems, Known Limitations & Technical Debt Ledger

> **Purpose**: A persistent, version-controlled ledger to track architectural challenges, edge cases, bugs, and technical debt across the multi-year development of Core AI. Never lose track of what needs hardening.

---

## Status Legend
- `[OPEN]` — Identified, needs implementation or architectural fix.
- `[IN PROGRESS]` — Active investigation or partial implementation.
- `[RESOLVED]` — Tested, verified, and closed.
- `[WATCHLIST]` — Known hardware/edge dependency to monitor.

---

## 1. Active Issues & Limitations

### Issue #001: Windows Console CP1252 Unicode Handling `[RESOLVED]`
- **Found**: 2026-09-02 during CLI demonstration.
- **Symptom**: `UnicodeEncodeError: 'charmap' codec can't encode character` when logging emojis on standard Windows terminals using cp1252.
- **Root Cause**: Colorama win32 stream wrapper passes strings through Python's cp1252 encoding.
- **Fix Applied**: Added `sys.stdout.reconfigure(encoding='utf-8')` and standardized CLI markers to ASCII-safe tags (`[*]`, `[+]`, `[OK]`, `[WARN]`).

### Issue #002: Dynamic Tool Synthesis Try-Block Indentation `[RESOLVED]`
- **Found**: 2026-09-02 during test suite execution.
- **Symptom**: Syntax error: `expected an indented block after 'try' statement on line 8`.
- **Root Cause**: Fallback template generator in `DynamicGenerator._template_synthesize` had multiline string indentation misaligned with the `try:` block.
- **Fix Applied**: Explicitly indented synthesized code block with 8 spaces inside the `try:` block and verified with `ast.parse`.

### Issue #003: LLM Connection Latency on Offline Providers `[RESOLVED]`
- **Found**: 2026-09-02 when Ollama was offline.
- **Symptom**: LiteLLM blocked for 10-15 seconds per call waiting for connection timeout before failing.
- **Root Cause**: Direct API calls to unreachable endpoints trigger internal retries.
- **Fix Applied**: Built fast socket/HTTP ping in `Planner.check_model_availability` (0.3s timeout on `http://localhost:11434/api/tags`) and environment variable pre-checks for API keys before invoking LiteLLM.

---

## 2. Watchlist & Architectural Debt to Address in Future Phases

### Debt #101: Remote Edge Node Tool Transport `[OPEN]`
- **Context**: In `core/schemas.py`, `ToolCallRequest` has `target_node: Optional[str]`.
- **Current State**: Tools currently execute within the local Python process on the Core AI host.
- **Needed**: A transport bridge (e.g. WebSocket / Tailscale WireGuard / MQTT) to dispatch `ToolCallRequest` across the network to physical edge nodes (car head-unit, phone companion app, smart glasses) and receive asynchronous `ToolCallResponse`.

### Debt #102: Proactive Daemon & State Trigger Engine `[OPEN]`
- **Context**: Autonomous behavior like *"I get a call from it while riding to work saying you forgot that, but don't worry, I handled it for you"*.
- **Current State**: System operates reactively on incoming events (`TextEvent`, `AudioEvent`).
- **Needed**: A background proactive reasoning loop / cron watcher that inspects `StateManager` state changes (e.g. user left home zone while kitchen window is open) and automatically instantiates a `PipelinePlan` and outgoing notification/call.

### Debt #103: Dynamic Tool Sandboxing Security Isolation `[OPEN]`
- **Context**: Generated tools currently run via Python's `exec()` with AST checking.
- **Current State**: AST filter blocks `subprocess`, `shutil`, `ctypes`, etc., which provides good baseline security.
- **Needed for Production**: For untrusted or fully open web-generated tools, transition execution to an isolated subprocess or lightweight Docker/WASM container with restricted filesystem and network permissions.

### Debt #104: Offline Vector Memory & Knowledge Graph `[OPEN]`
- **Context**: Persistent long-term memory across devices.
- **Current State**: SQLite `memory` table stores JSON key-values.
- **Needed**: Integrate `sqlite-vec` or local embeddings for semantic recall of user habits, past interactions, and device state histories.

### Debt #105: Cross-Platform Audio Layer (Linux PipeWire/ALSA & Android Audio) `[OPEN]`
- **Context**: Transition from Windows dev machine to Linux workstation / Raspberry Pi / Automotive SBC / Android.
- **Current State**: `sounddevice` and `pyttsx3` work across platforms, but Linux headless setups require PipeWire / PulseAudio / ALSA daemon configuration.
- **Needed**: Add an audio backend selector in `config/settings.yaml` supporting ALSA, PulseAudio, PipeWire, and a network streaming audio sink (RTP/WebRTC/MQTT) for low-latency streaming to Android and smart glasses.

### Debt #106: Mobile Companion Client (Android / Nothing OS / Wearable Edge) `[OPEN]`
- **Context**: Mobile daily driver integration (Android, Nothing OS, Custom ROMs).
- **Current State**: Core AI runs as a server/microkernel.
- **Needed**: 
  1. Lightweight mobile client (Flutter / React Native or native Kotlin) connecting over Tailscale/WebSocket.
  2. Nothing OS Glyph Matrix integration: trigger Glyph LED patterns for AI thinking, alerts, and subtle status indications without turning on the screen.
  3. Lock screen widgets and quick settings tiles for 1-tap voice interaction.

### Debt #107: Dynamic Spatial Anchoring & User Profile Memory `[OPEN]`
- **Context**: The AI needs persistent identity memory ("know who I am", names, nicknames like "Daevron", preferences) and spatial awareness of roaming vs. fixed devices.
- **Current State**: Static node list in `config/nodes.yaml` with in-memory lookup.
- **Needed**:
  1. `user_profiles` table in SQLite (`core_ai.db`) for preferred name, persona style, and preferences updated via speech or settings.
  2. `device_topology` table distinguishing **Fixed Anchor Devices** (studio mic, smart mirror, garden sensor) from **Roaming Devices** (laptop, phone, glasses).
  3. Dynamic proximity and verbal anchoring: *"This laptop is in the studio right now"* or proximity to studio anchors automatically maps the roaming laptop to `home/indoor/studio`.



---

## 3. How to Log New Problems
Whenever a bug or edge-case is discovered:
1. Assign the next sequential ID (`Issue #...`).
2. Document:
   - **Date & Component**
   - **Symptom & Stacktrace**
   - **Root Cause**
   - **Resolution or Planned Fix**
   - **Status Tag** (`[OPEN]`, `[RESOLVED]`, `[WATCHLIST]`)
