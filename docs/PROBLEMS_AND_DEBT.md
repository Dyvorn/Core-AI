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

### Issue #004: StateManager `set_user_preferred_name` Keyword Discrepancy `[RESOLVED]`
- **Found**: 2026-09-06 during CLI identity update check.
- **Symptom**: `Unexpected keyword argument 'alias' in function core.state.StateManager.set_user_preferred_name`.
- **Root Cause**: `main.py` CLI invoked `set_user_preferred_name(new_name, alias=alias)` whereas method signature expected `aliases`.
- **Fix Applied**: Updated `main.py` to pass `aliases=[alias] if alias else None`, extended `StateManager.set_user_preferred_name` to support both `aliases` (list) and `alias` (str), and added unit tests.

### Issue #005: IDE Pyright Virtual Environment Resolution `[RESOLVED]`
- **Found**: 2026-09-06 in IDE problem diagnostics.
- **Symptom**: `Cannot find module litellm` across multiple modules.
- **Root Cause**: Language server evaluated dependencies against system Python rather than `.venv`.
- **Fix Applied**: Added `pyrightconfig.json` and `.vscode/settings.json` configured for `.venv`, and guarded dynamic completion imports with `# type: ignore`.

### Issue #006: Conversational Greetings Fabricating Unrelated Tool Steps `[RESOLVED]`
- **Found**: 2026-09-06 during CLI smoke testing.
- **Symptom**: Typing simple conversational greetings (`hi`, `hello`) triggered a DAG pipeline synthesizing `get_time`, responding `"It is 15:36, Dyvorn."`.
- **Root Cause**: REPL defaulted any unrecognized input to a problem-solving goal, and the heuristic planner's catch-all branch fabricated a `get_time` step.
- **Fix Applied**: Added conversational dialogue branches for greetings, small talk, identity, and pleasantries in `main.py` and `brain/spoken_to.py`. Updated `brain/planner.py` to produce zero steps for greetings, and updated `formulate_spoken_response` to reply conversationally and truthfully indicate when tools are absent.

### Issue #007: Pipeline Variable Cascading Regex & Parameter Mismatches `[RESOLVED]`
- **Found**: 2026-10-04 during network query execution.
- **Symptom**: `TypeError: inspect_lan_device() got an unexpected keyword argument 'target_ip_address'` and unparsed `{{steps.scan_local_network_step.output.discovered_devices.[0].ip_address}}`.
- **Root Cause**: Pipeline engine regex rejected brackets `[` and `]`, and strict tool signatures threw `TypeError` on LLM parameter variations.
- **Fix Applied**: Added `_traverse_field_path` to handle nested array bracket indices (`.[0]`, `[0]`, `.0`) and fuzzy property aliases (`discovered_devices` $\to$ `devices`, `ip_address` $\to$ `ip`). Added `**kwargs` and parameter aliases across all native tools (`network_tools.py`, `file_tools.py`, `system_tools.py`).

### Issue #008: RAM Process Consumption & Math Tool Keyword Invocation `[RESOLVED]`
- **Found**: 2026-10-04 during RAM query execution (`whats pulling most ram`).
- **Symptom**: `calculate_math() got an unexpected keyword argument 'field'`.
- **Root Cause**: LLM generated a step calling `calculate_math` with `field='memory_usage'`, and Windows process listing lacked RAM parsing and aggregation.
- **Fix Applied**: Added keyword argument resilience to `calculate_math`, implemented memory string parsing and process instance aggregation in `list_running_processes`, and routed RAM queries to concurrent hardware and process inspection.

### Issue #009: In-Memory Spatial Zone Filter Hallucination `[RESOLVED]`
- **Found**: 2026-10-04 during zone cleanup (`remove all zones exept office`).
- **Symptom**: Core AI dynamically synthesized `filter_list` and reported zones deleted, but SQLite was never modified and all zones remained active.
- **Root Cause**: No native zone removal or pruning tools existed in the registry or `StateManager`.
- **Fix Applied**: Implemented `StateManager.delete_zone()` and `StateManager.delete_all_zones_except()`, registered native tool `remove_spatial_zone` with `all_except` support, and added `zone rm <id>` to CLI REPL.

### Issue #010: One-Shot CLI Warmup Latency & Log Clutter `[RESOLVED]`
- **Found**: 2026-10-07 during daily driver productivity testing.
- **Symptom**: Running `core "<goal>"` launched the full `main.py` runtime importing heavy libraries (`torch`, `fastapi`, `whisper`, `uvicorn`), initializing `StateManager`, and printing diagnostic log noise even when the background daemon was already online. On Windows, `localhost` also triggered a 2.2-second IPv6 DNS resolution fallback.
- **Root Cause**: CLI entrypoints (`core.bat`, `core.sh`) routed one-shot tasks directly to `main.py`, incurring full microkernel startup overhead and logging setup.
- **Fix Applied**: Built lightweight standalone dispatcher `interfaces/cli/client.py` using standard library only (`urllib`), directing calls to `127.0.0.1` directly, achieving sub-50ms execution latency with zero log noise and clean exit codes. Routed `core.bat` and `core.sh` through `client.py` with automatic in-process fallback.

### Issue #011: Unregistered Mock Tool Catalog Residue (`tools/native/home_assistant.py`) `[RESOLVED]`
- **Found**: 2026-10-07 during Anti-Slop audit.
- **Symptom**: `HomeAssistantMock` was registered as a native tool, returning hardcoded dummy states rather than interfacing with real hardware.
- **Root Cause**: Early testing prototype code remained in native tools catalog.
- **Fix Applied**: Purged `tools/native/home_assistant.py` and removed hardcoded planner assumptions in `brain/planner.py`. Smart home service planning now dynamically verifies tool presence in `ToolRegistry` rather than fabricating steps.

### Issue #012: General Status Query Interception of Git Status `[RESOLVED]`
- **Found**: 2026-10-07 during developer tool integration testing.
- **Symptom**: Calling `core "git status"` triggered general system status (time + OS status) instead of `get_git_status`.
- **Root Cause**: The regex pattern for system diagnostics matched the substring `"status"` before the git pattern was evaluated.
- **Fix Applied**: Added exclusion of `"git"` in the system diagnostics pattern in `brain/planner.py` and routed git queries to `get_git_status` deterministically.

### Issue #013: Strict Exact String Matching in Proactive Rule Deletion `[RESOLVED]`
- **Found**: 2026-10-07 during reminder cancellation testing.
- **Symptom**: `cancel_proactive_rule("Hardware Watcher")` returned error when the rule name was `"Hardware Watcher (RAM > 90.0%)"`.
- **Root Cause**: `StateManager.delete_proactive_rule` only checked `LOWER(name) = LOWER(?)` exact equivalence.
- **Fix Applied**: Added `OR LOWER(name) LIKE ?` with wildcard substring matching in `core/state.py` to allow forgiving, natural cancellations.

---

## 2. Watchlist & Architectural Debt to Address in Future Phases

### Debt #101: Remote Edge Node Tool Transport `[RESOLVED]`
- **Context**: In `core/schemas.py`, `ToolCallRequest` has `target_node: Optional[str]`.
- **Resolution**:
  1. Built `RemoteToolDispatcher` in `tools/remote_dispatcher.py` to create dynamic proxy tools in `ToolRegistry` that transparently dispatch `ToolCallRequest` over active WebSockets (`/ws/nodes/{node_id}`).
  2. Implemented bidirectional JSON RPC handshake in `core/gateway.py`: edge nodes advertise capabilities and dynamic tool definitions on connection, which are dynamically registered in `ToolRegistry`.
  3. Built automatic tool lifecycle cleanup: when an edge node disconnects, its proxy tools are cleanly unregistered from the catalog, preventing phantom/ghost tools.
  4. Verified with automated tests in `tests/test_remote_dispatcher.py` and `tests/test_server_upgrades.py`.

### Debt #102: Proactive Daemon & State Trigger Engine `[RESOLVED]`
- **Context**: Autonomous proactive agency, scheduled countdown reminders, and hardware supervising.
- **Resolution**:
  1. Built and integrated `ProactiveDaemon` in `brain/proactive.py` running continuous ambient loop inspecting countdown timers, hardware vitals (`ram_percent_gt`), spatial state, and roaming devices.
  2. Implemented native tools `create_reminder`, `create_vitals_watcher`, `list_active_rules`, and `cancel_proactive_rule` in `tools/native/proactive_tools.py`.
  3. Configured automatic one-shot rule deactivation upon firing to eliminate repetitive reminder alerts.
  4. Connected deterministic heuristic routing and spoken synthesis in `brain/planner.py`.
  5. Verified with 100% automated test coverage in `tests/test_proactive_and_dev_tools.py` and `tests/test_proactive.py`.

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

### Debt #107: Dynamic Spatial Anchoring & User Profile Memory `[RESOLVED]`
- **Context**: The AI needs persistent identity memory ("know who I am", names, nicknames like "Dyvorn" / "Vyrn" / "Refined", preferences) and spatial awareness of roaming vs. fixed devices.

- **Resolution**:
  1. Built `user_profiles` table in SQLite with `get_user_profile`, `save_user_profile`, and `set_user_preferred_name` methods.
  2. Built `device_topology` table distinguishing **Fixed Anchor Devices** from **Roaming Devices** with verbal and proximity anchoring (`update_device_zone`).
  3. Implemented three security trust tiers (`OWNER`, `AMBIENT`, `GUEST`) protecting private profile memory with `403 Forbidden` defense gates.
  4. Added zero-friction 1-line onboarding script in `interfaces/install/enroll.py`. Verified with 100% automated test coverage in `tests/test_gateway.py`.




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
