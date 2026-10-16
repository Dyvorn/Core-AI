# C.O.R.E. AI :: CHANGELOG PROTOCOL

```text
╔══════════════════════════════════════════════════════════════════════════════════════╗
║   C.O.R.E. AI // SYSTEM EVOLUTION & CHANGELOG REGISTRY                               ║
║   CONCURRENT OMNIPRESENT REASONING ENGINE // SOVEREIGN LIFE OS                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
```

All notable engineering developments and protocol updates to **Core AI** are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [!TIP]
> For the comprehensive architectural deep-dive, topology diagrams, and the sovereign manifesto, see [RELEASE_NOTES.md](RELEASE_NOTES.md).

---

## [[0.2.3-alpha]](https://github.com/Dyvorn/Core-AI/releases/tag/v0.2.3-alpha) — 2026-10-16
### Codename: "Proactive Anticipatory Agency, Master Troubleshooting Wiki & Multiple Hardware-Aware Computing (MHAC)"

| Kernel | Status | Verification | Ethos |
| :---: | :---: | :---: | :---: |
| **`v0.2.3-alpha`** | 🟢 **OPERATIONAL** | 🧪 **194 / 194 PASSED** | 🛡️ **#ANTISLOP** |

Proactive Anticipatory Agency, Calendar & Schedule Reconciliation Engine, pre-event Preparation Buffer warnings, unscheduled note/evidence scanning, SQLite non-locking WAL & 30-second busy timeout hardening, Master Troubleshooting Wiki in `docs/wiki/`, and Multiple Hardware-Aware Computing (MHAC) opportunistic compute delegation.

### 🌟 Added & Enhanced

#### ⚡ Multiple Hardware-Aware Computing (MHAC) Mesh Framework (`brain/mhac.py`, `core/schemas.py`, `core/gateway.py`, `brain/model_router.py`)
- **Capability & Context Broker**: Transforms the central host (`core`) into an opportunistic compute broker. When high-spec client workstations connect to the mesh, `core` evaluates compute signatures, negotiates model placement, and delegates heavy LLM inference to client GPUs while keeping memory, state, and proactive hooks centralized.
- **Dynamic Hardware Scoring Formula**:
  $$\text{ComputeScore} = (\text{CPU Cores} \times 1.0) + (\text{RAM GB} \times 0.5) + (\text{Has GPU} \times 50.0) + (\text{VRAM GB} \times 5.0)$$
  Enables clear capability separation: low-power 2-core laptop scores ~10.0, client mobile phones score ~6.0, and desktop workstations with RTX GPUs score 150.0-220.0+.
- **Opportunistic Model Verification & Handshake Protocol**:
  - Automatically probes client Ollama instances (`GET /api/tags`).
  - **Accelerated Workstation Mode**: Binds execution layer to client local GPU when target model (`llama3.1:8b`) is present.
  - **Missing Model Handshake Mode**: Transparently informs operator (*"I can run this 4x faster on your machine, but llama3.1:8b is not installed..."*), offering one-click download via `/api/v1/mhac/pull` or seamless fallback to host CPU.
  - **Standalone Mode**: Runs self-contained on host internal processor when connecting clients are low-spec.
- **Decoupled Intelligence vs. Stateless Delegation**: SQLite WAL state, proactive daemons, conversation history, and tool execution remain on `core`; workstation acts strictly as a raw token execution worker.
- **Non-Blocking Gateway Endpoints**:
  - `POST /api/v1/mhac/handshake`: Capability evaluation and mesh-wide broadcast.
  - `GET /api/v1/mhac/status`: Telemetry matrix of connected compute clients.
  - `POST /api/v1/mhac/probe`: Remote/local Ollama model inventory inspection.
  - `POST /api/v1/mhac/pull`: Client model download triggering.
  - `POST /api/v1/mhac/reset`: Reset delegation back to host.
- **Comprehensive Verification Suite (`tests/test_mhac.py`)**: 7 automated tests covering scoring, handshakes, model routing, and gateway endpoints.

#### 🧠 Proactive Anticipatory Agency & Schedule Evidence Reconciliation (`brain/proactive.py`, `tools/native/calendar_tools.py`, `core/state.py`)
- **Anticipatory Intelligence vs. Passive Chatbots**: Eliminates the need to ask *"Do I have appointments?"*. Core AI proactively detects implicit commitments from notes and conversation, confirms evidence, adds missing events to the calendar, and configures preparation reminders autonomously.
- **Dual-Stage Anticipatory Notifications**: Pre-event **Preparation Warnings** fire dynamically when `remaining_time <= preparation_minutes` with custom preparation instructions (*"Review architectural RFC and benchmark slides"*), followed by an **Imminent Notice** (10-15m prior).
- **Persistent Notification Acknowledgment (`prep_notified`, `imminent_notified`)**: Persistent SQLite state flags ensure proactive warnings fire exactly once and never loop or nag the operator.
- **Unscheduled Note & Evidence Scanner (`_check_unreconciled_notes`)**: Automatically evaluates scratch notes for implicit appointment mentions, cross-checks the calendar, auto-schedules missing commitments, and alerts the operator transparently.
- **Calendar & Appointment Subsystem (Migration `v4`, `calendar_events`)**: High-performance SQLite calendar table with indices on `start_time` and `prep_notified`.
- **Native Calendar & Schedule Tools**:
  - `manage_calendar`: Full CRUD for appointments and preparation requirements.
  - `reconcile_schedule_evidence`: Natural language evidence extraction, deduplication, and auto-scheduling.
  - `get_upcoming_schedule`: Horizon-based schedule inspection with countdowns and preparation buffer metrics.

#### 🛡️ SQLite Concurrency & Database Locking Elimination (`core/state.py`)
- **30-Second Busy Timeout Hardening**: Set `timeout=30.0` in `_get_connection()` and `PRAGMA busy_timeout = 30000` in WAL mode, completely eliminating `sqlite3.OperationalError: database is locked` during concurrent daemon execution, test runs, and CLI invocations.
- **Flaky Subprocess Timeout Resolution (`tests/test_daily_driver.py`)**: Increased timeout in `test_oneshot_cli_goal_execution` to 30.0s to accommodate heavy concurrent test runs on Windows without false timeouts.

#### 📚 Comprehensive Master Wiki & Troubleshooting Knowledge Base (`docs/wiki/`)
- **`docs/wiki/README.md`**: Master Wiki portal, navigation matrix, and quick problem resolver index.
- **`docs/wiki/MHAC_ARCHITECTURE.md`**: Architectural blueprint of the Multiple Hardware-Aware Computing framework.
- **`docs/wiki/TROUBLESHOOTING_AND_SOLUTIONS.md`**: Comprehensive Problem $\to$ Symptom $\to$ Root Cause $\to$ Verified Fix catalog covering Audio/WASAPI -9997, Windows IPv6 loopback delay, SQLite locking, LLM timeouts, and distributed satellites.
- **`docs/wiki/PROACTIVE_ENGINE.md`**: Technical blueprint of the anticipatory reasoning loop, preparation buffers, and non-intrusive etiquette.
- **`docs/wiki/ARCHITECTURE_AND_SUBSYSTEMS.md`**: Architectural dossier covering Microkernel, StateManager, EventBus, Spoken-To Pragmatics, and Sovereign Mesh.
- **`docs/wiki/CLI_AND_TOOLS_REFERENCE.md`**: Complete dictionary of all CLI commands, flags, and native tools.
- **`docs/wiki/SUBMITTING_ISSUES_AND_SOLUTIONS.md`**: Standardized workflow and templates for operators to record new problems and contribute verified solutions.

---

## [[0.2.2-alpha]](https://github.com/Dyvorn/Core-AI/releases/tag/v0.2.2-alpha) — 2026-10-12
### Codename: "Distributed Voice Satellites & Mobile Mesh"

| Kernel | Status | Verification | Ethos |
| :---: | :---: | :---: | :---: |
| **`v0.2.2-alpha`** | 🟢 **OPERATIONAL** | 🧪 **180 / 180 PASSED** | 🛡️ **#ANTISLOP** |

Distributed Voice Satellite auto-discovery & dynamic re-discovery, adaptive operational modes (bidirectional, speak-only, listen-only), dynamic edge tool RPC registration and execution (`speak_{node_id}`, `status_{node_id}`, `interrupt_{node_id}`), autonomous DAG fallback executor, telemetry heartbeat registry, direct edge node speech push, Phase 4 Mobile Companion zero-friction enrollment with local session caching (`~/.core_ai_mobile_session.json`), reactive Nothing OS Glyph LED matrix patterns with ANSI visualizer, lock-screen glance telemetry, fast CLI mobile ask and speak dispatch with non-destructive flag forwarding, low-power Ollama smart relevance filtering, bidirectional delta state synchronization (`core mesh sync`), durable SQLite offline task replay (`mesh_offline_queue`), and inter-device message routing (`core mesh send`, `core mobile send`).

### 🌟 Added & Enhanced

#### 🌐 Sovereign Mesh Bidirectional Delta State Synchronization & Inter-Device Routing (`core/state.py`, `core/gateway.py`, `core/mesh_client.py`, `interfaces/voice/satellite.py`, `interfaces/mobile/companion.py`)
- **Durable SQLite Offline Task Queueing & Replay (`mesh_offline_queue`, migration `v3`)**: Every task executed under local autonomous fallback is durably recorded with input, context, status, and result into table 12 in SQLite (`enqueue_offline_task()`), surviving machine reboots and power losses. Upon mesh reconnection, all queued tasks are replayed into the central server log and marked synced (`mark_offline_tasks_synced()`).
- **Bidirectional Delta Synchronization Protocol (`POST /api/v1/mesh/sync/pull`, `POST /api/v1/mesh/sync/push`, `POST /api/v1/mesh/sync`, `core mesh sync [full|pull|push]`)**: Atomic synchronization exchanging entity deltas across `profile`, `kv_state` (notes/memory), `zones`, `devices`, `audio_routes`, and `proactive_rules` using timestamp-based last-write-wins merging (`get_state_deltas()`, `merge_state_deltas()`).
- **Intelligent Non-Destructive Identity Protection**: Discriminates between customized operator identities and fresh unconfigured default profiles ("User"), strictly protecting personalized identities across sync cycles.
- **Inter-Device WebSocket Routing & Dispatch Protocol (`POST /api/v1/mesh/message`, `core mesh send`, `core mobile send`)**: Real-time routing of commands, alerts, speech synthesis, and sync triggers to specific node IDs, spatial room zones, or mesh-wide broadcasts (`"all"`).
- **Voice Satellite & Mobile Real-Time Sync Adaptation**: Satellites and mobile companions automatically listen for `MESH_STATE_UPDATED` broadcasts to pull deltas immediately, replay offline queues upon heartbeat reconnection, and handle incoming `mesh_device_message` directives.
- **Unified Node Matrix Inventory (`GET /api/v1/mesh/nodes`, `core mesh nodes`, `core mobile nodes`)**: Aggregates all connected voice satellites, mobile companion sessions, edge worker nodes, and topological devices into a single real-time inspection view.

#### 🎙️ Distributed Voice Satellite Hardening & Auto-Discovery (`interfaces/voice/satellite.py`, `core/gateway.py`)
- **UDP LAN Auto-Discovery & Dynamic Re-Discovery**: Voice Satellites automatically scan the local network using `LANBeacon` auto-discovery (`discover_core_servers`) on startup and automatically re-probe the LAN if disconnected for consecutive heartbeat cycles.
- **Adaptive Hardware Operational Modes (`--mode`, `--speak-only`, `--listen-only`)**: Dynamic capability negotiation (`["audio_in", "audio_out"]`, `["audio_out"]`, or `["audio_in"]`). Voice satellites gracefully adapt to smart speakers, media sinks, or ceiling microphone arrays without crashing if an audio input or output is absent.
- **Autonomous Local Fallback DAG Executor ("Never a Brick")**: If the connection to the central server drops, the satellite falls back seamlessly to an autonomous in-process DAG planner and pipeline engine, executing local commands directly on edge silicon.
- **Satellite Telemetry Heartbeat Registry (`POST /api/v1/mesh/satellites/heartbeat`, `GET /api/v1/mesh/satellites`, `GET /api/v1/mesh/satellites/{node_id}`)**: Background heartbeat daemon streams satellite node ID, spatial room zone, audio device indices, model size, and uptime metrics. The gateway dynamically tracks online, stale, and offline satellites, and provides single-satellite inspection.
- **Direct Edge Node Speech Push (`POST /api/v1/mesh/satellites/{node_id}/speak`, `core speak`)**: The central gateway pushes speech playback directly across connected edge node WebSockets (`/ws/nodes/{node_id}`) or broadcasts to all nodes simultaneously (`node_id="all"`).
- **Dynamic Edge Tool Registration & Bidirectional RPC (`speak_{node_id}`, `status_{node_id}`, `interrupt_{node_id}`)**: Edge satellites dynamically expose their local actuators and sensor states to the Central Gateway, enabling the AI to actuate remote hardware anywhere across the sovereign mesh.
- **Service Status Matrix Integration (`core/service.py`)**: `core status` and `core metrics` display active satellite count and mobile companion clients directly on the high-contrast status card.

#### 📱 Phase 4 Mobile Companion & Nothing OS Glyph Integration (`interfaces/mobile/companion.py`, `core/gateway.py`, `core/schemas.py`)
- **Zero-Friction Mobile Enrollment (`POST /api/v1/mobile/enroll`)**: Secure onboarding endpoint for Android, Nothing OS, and iOS companion devices, assigning `OWNER` or `GUEST` trust tier session tokens and dedicated WebSocket endpoints.
- **Local Session Persistence (`~/.core_ai_mobile_session.json`)**: Automatic cryptographic token caching and reloading across CLI invocations (`core mobile ask`, `core mobile glance`) with explicit session clearing (`core mobile logout`, `core mobile reset-session`).
- **Reactive Nothing OS Glyph Matrix LED Driver (`POST /api/v1/mobile/glyph`, `core glyph`)**: Real-time pattern trigger protocol supporting `reasoning_pulse` (subtle breathing pulse during DAG reasoning), `success_flash` (action completion confirmation), and `alert_burst` (security or system alerts), integrated into mobile command dispatch.
- **ANSI Terminal Glyph Interface Visualizer**: Real-time ASCII/Unicode backplate rendering of the Nothing Phone (2) physical LED matrix (camera ring, diagonal slash, central reasoning arc, battery/alert strip) with cross-platform charmap resilience preventing any Windows console encoding crashes.
- **Lock-Screen Glanceable Telemetry (`GET /api/v1/mobile/glance`, `core mobile glance`, `core mobile status`)**: Lightweight glance payload and ANSI terminal viewer exposing operator name, active AI model, proactive countdown reminders, host CPU/RAM vitals, and active mesh satellites.
- **High-Speed Mobile WebSocket Gateway (`/ws/mobile/{client_id}`)**: Bidirectional companion stream for push-to-talk voice commands, real-time glance sync, and glyph acknowledgments.
- **Dedicated CLI Wrappers (`core mobile ask`, `core glyph`, `core speak`, `core.sh`, `core.bat`)**: Quick terminal helpers to dispatch mobile queries, trigger glyph patterns, and synthesize speech locally or across the mesh with non-destructive flag forwarding (`parse_known_args`).

#### ⚡ Planner & Low-Power Ollama CPU Hardening (`brain/planner.py`, `core/service.py`)
- **Smart Tool Relevance Filtering**: Automatically scores and selects relevant tools for local Ollama models on low-power CPUs, cutting JSON catalog overhead by over 70% and preventing CPU suffocation.
- **Deterministic Heuristic Mesh Pairing**: Natural directives ("connect pc to mesh", "pc verbinden") execute instantaneously in <5ms without LLM latency.
- **SO_REUSEADDR Port Fallback**: Auto-fallback detection and socket reuse preventing port conflicts during service reboots.

---

## [[0.2.1-alpha]](https://github.com/Dyvorn/Core-AI/releases/tag/v0.2.1-alpha) — 2026-10-11
### Codename: "Ubiquitous Mesh & Linux Polish"

| Kernel | Status | Verification | Ethos |
| :---: | :---: | :---: | :---: |
| **`v0.2.1-alpha`** | 🟢 **OPERATIONAL** | 🧪 **144 / 144 PASSED** | 🛡️ **#ANTISLOP** |

Linux terminal rendering overhaul, multi-machine ambient voice satellite mesh, dynamic mic/speaker hardware introspection, zero-slop configuration editing, and git permission hardening.

### 🌟 Added & Enhanced

#### 🐧 Linux Terminal Rendering & Readline ANSI Code Alignment (`core/terminal.py`, `main.py`)
- **Readline Escape Sequence Shielding (`make_readline_safe_prompt`)**: Wraps ANSI color codes in `\001` (`RL_PROMPT_START_IGNORE`) and `\002` (`RL_PROMPT_END_IGNORE`) control markers on POSIX hosts. Completely eliminates erratic cursor misalignment, phantom line-wraps, and corrupted backspaces caused by GNU Readline counting non-printable styling bytes.
- **Dynamic Pixel-Perfect Box Matrix (`render_box`)**: Calculates visual line widths using `strip_ansi` to guarantee perfectly symmetrical, closed Unicode borders across both Windows Terminal and Linux console sessions.

#### 🎙️ Distributed Voice Satellite & Multi-Machine Audio Mesh (`interfaces/voice/satellite.py`, `core/gateway.py`, `main.py`)
- **Dedicated Voice Satellite Daemon (`core satellite` / `core.sh satellite` / `core.bat satellite`)**: Allows any connected edge machine (laptop, desktop PC, Raspberry Pi / SBC) to act as an ambient voice station. Performs local Silero VAD + Faster-Whisper transcription, checks Spoken-To discourse filters, offloads DAG reasoning to the central server (Ollama / Cloud LLM), and speaks synthesized responses out of the local machine's speakers.
- **Universal Voice Gateway Transcription Endpoint (`POST /api/v1/voice/transcription`)**: Central gateway endpoint receiving audio transcripts from any edge device, running non-blocking DAG execution via `asyncio.to_thread`, and returning spoken responses.
- **Automatic Edge Node Voice Routing (`main.py`)**: Spoken queries captured while running in `edge_node` mode automatically route across the mesh to the primary reasoning server instead of failing on local model unavailability.

#### 🎛️ Dynamic Audio Device Management & Diagnostics (`interfaces/cli/settings.py`, `main.py`, `core.sh`, `core.bat`)
- **Device Introspection & Switching (`core audio`, `core mic`, `core speaker`)**: List, switch, and inspect all input microphones and output speakers dynamically with hardware sample rates and host APIs.
- **Interactive Audio Probing (`mic test`, `speaker test`)**: Quick hardware testing to verify capture levels and speaker output without restarting the daemon.

#### 📝 Zero-Slop Configuration Management (`interfaces/cli/settings.py`, `interfaces/cli/client.py`)
- **Direct System Editor Launch (`core edit config`, `core edit env`)**: Opens configuration files directly in the operator's preferred `$EDITOR` (Nano, Vim, VS Code, or Notepad) with automatic validation.
- **Interactive Configuration Explorer (`core config`)**: Displays current network, model, audio, and storage preferences with quick-toggle switches.

#### 🛡️ Git & Shell Script Permission Hardening (`.gitattributes`, `core.sh`)
- **Universal LF Enforcement (`.gitattributes`)**: Normalizes line endings (`*.sh text eol=lf`) repository-wide, preventing Windows CRLF git conversions from dirtying trees or failing bash execution on Debian/Ubuntu.
- **Pre-Pull Safeguard & Executable Perms (`core.sh update`)**: Automatically cleans untracked/modified script stubs and restores `chmod +x` executable permissions post-update.

---

## [[0.2.0-alpha]](https://github.com/Dyvorn/Core-AI/releases/tag/v0.2.0-alpha) — 2026-10-07
### Codename: "Precision & Flow"

| Kernel | Status | Verification | Ethos |
| :---: | :---: | :---: | :---: |
| **`v0.2.0-alpha`** | 🟢 **OPERATIONAL** | 🧪 **139 / 139 PASSED** | 🛡️ **#ANTISLOP** |

Major Quality of Life (QoL) and stability milestone dedicated to 100% daily driver productivity, sub-50ms CLI execution, always-on voice capture by default, neural Silero VAD, instant verbal barge-in, multilingual Whisper STT, spoken-to discourse awareness, mock tool eradication, asynchronous gateway event-loop offloading, system resource diagnostics, and microkernel streamlining.

### 🌟 Added & Enhanced

#### 🌐 High-Concurrency Async Gateway Offloading (`core/gateway.py`, `main.py`)
- **Event Loop Offloading via `asyncio.to_thread`**: Offloaded synchronous DAG planning (`planner.plan_problem`) and natural speech synthesis (`planner.formulate_spoken_response`) inside `/api/v1/pipeline` and `/api/v1/pipeline/solve_sync` to background thread pools. Prevents blocking FastAPI's async event loop when local models (Ollama) or external LLMs take seconds to plan.
- **Dynamic Port Beacon Resolution**: Multi-instance port fallbacks dynamically broadcast active ports over UDP `LANBeacon` via `CORE_PORT` environment variables.

#### 🛰️ Intercontinental Mesh Latency Diagnostic Probe (`core/mesh_client.py`, `interfaces/cli/client.py`, `core.bat`, `core.sh`)
- **Latency Diagnostic Probe (`core mesh ping`)**: Added sub-millisecond round-trip time measurements against configured main servers, reporting round-trip latency (ms), host model provider, and connected edge nodes.
- **Cross-Platform ANSI Safety**: Implemented Windows CP1252 safe formatting and `sys.stdout.reconfigure(encoding="utf-8")` to prevent terminal encoding crashes across Windows CMD, PowerShell, and Linux.

#### 📊 Sovereign System Resource Inspector (`tools/native/system_tools.py`, `brain/planner.py`, `main.py`)
- **Hardware Vitals Tooling (`inspect_system_resources`)**: Introspects logical CPU core count, load averages (Unix), total/free/used disk metrics, and physical memory utilization.
- **Deterministic DAG Heuristic Routing**: Natural language queries (*"system vitals"*, *"hardware health"*, *"disk space"*, *"festplatte"*, *"ram usage"*, *"speicher frei"*) bypass LLM inference entirely and execute in <10ms with bilingual German and English spoken summaries.

#### 🔖 System Version Protocol (`interfaces/cli/client.py`, `core.bat`, `core.sh`)
- **Version Matrix Command (`core version` / `-v` / `--version`)**: Added instant ASCII matrix displaying system kernel version (`v0.2.0-alpha`), Git commit SHA, node operational role (`EDGE_NODE` / `MAIN_SERVER`), gateway server URL, and AGPL-3.0 sovereignty guarantee.

#### 🐧 Detached Linux Daemon Persistence (`core/service.py`)
- **Session Isolation (`setsid`)**: Added `start_new_session=True` on POSIX hosts ensuring background daemons started via `core start` over SSH survive terminal hangups (SIGHUP) indefinitely.

#### 🧹 Clean Slate Server Reset & Zero-Residue Purge (`interfaces/install/clean_setup.py`, `core.bat`, `core.sh`, `main.py`)
- **Zero-Residue Clean State Wipe (`core clean` / `core reset`)**: Operators can now wipe all local SQLite database records (`core_ai.db`, WAL, SHM), credentials (`config/.env`), execution audit trails (`logs/*`), backup snapshots (`backups/*`), dynamically generated tools (`tools/dynamic/*.py`), and bytecode caches with a single command to perform a pristine Day-Zero setup on their server.
- **Strict File & Virtualenv Preservation**: Strictly protects the Python virtual environment (`.venv`), Git repository (`.git`), installed packages, and all project source code files ("delete everything but the files so everything is still installed").
- **Interactive & Headless Automation**: Supports interactive confirmation with automatic post-wipe handover to the bootstrap setup wizard (`core setup`), as well as headless flags (`-y` / `--yes`, `--setup`, `--keep-env`, `--dry-run`).
- **Native Tool & Natural Language Planner Routing**: Integrated `factory_reset` into `SafetyGate.CRITICAL_CONFIRMATION_TOOLS` and deterministic DAG planner, recognizing natural requests such as `core "delete everything but the files"` and `core "clean new setup"`.

#### 🎙️ Ultra-Low-Latency Voice Detection, Silero VAD & Verbal Barge-In (`engines/voice_in.py`, `engines/voice_out.py`, `brain/spoken_to.py`, `main.py`)
- **Neural Silero VAD (ONNX)**: Integrated on-device Silero VAD operating on 512-sample (32ms at 16kHz) frames. Accurately pinpoints vocal onset, ignores fan noise, breathing, typing, and room reflections, and cleanly cuts off speech after ~350ms of trailing silence (eliminating 7.0s safety lockouts).
- **Verbal Barge-In & Instant Playback Interruption**: Operator can interrupt Core AI mid-speech at any moment by speaking *"Stop"*, *"Stopp"*, *"No, no, stop, stop, stop"*, *"Halt"*, or *"Warte"*. The audio worker halts hardware sounddevice playback within 20ms and purges pending queues.
- **Fast-Path Semantic Discourse (<0.1ms Latency)**: Reordered discourse evaluation to process deterministic room imperatives, time queries (*"what time is it"*, *"how... what time is it"*), and assistant vocatives (*"Gemini"*, *"Core"*, *"Jarvis"*) instantly without blocking on external cognitive LLM roundtrips.
- **Greedy Whisper STT Decoding (`beam_size=1`)**: Streamlined faster-whisper inference to greedy beam_size=1 with bilingual acoustic priming, accelerating speech-to-text throughput by 3-4x.
- **Decoupled Asynchronous Audio Capture**: Microphone processing runs in an isolated non-blocking loop with background dispatch, keeping voice detection receptive 100% of the time even while executing tools or synthesizing audio.
- **Always-Active Voice In by Default**: Inverted the voice activation lifecycle so microphone capture is **always active on boot** across both interactive REPL and headless background daemon modes. Operators no longer need to type `voice on` or pass `--voice`.
- **Operator Privacy & Pausing (`voice off` / `--no-voice`)**: Easily paused with `voice off` (or `mic off`) in the REPL and resumed with `voice on`, or disabled at startup via `--no-voice` / `--no-mic` CLI flags or `CORE_DISABLE_VOICE=1` environment variable.
- **Bilingual Acoustic Decoding Priming**: Injected domain initial prompts (`initial_prompt`) covering common German and English terminology (Core AI, Gemini, Dyvorn, Uhrzeit, Wetter, Systemstatus, Erinnerung, Notizen, Office, Studio) to eliminate decoding ambiguities.
- **Native Hardware Rate Auto-Detection & Resampling**: Introspects native hardware sample rates (WASAPI / DirectSound 44.1kHz or 48kHz audio interfaces) to completely eliminate `PaErrorCode -9997 (Invalid sample rate)` on Windows. Integrates zero-dependency fast linear interpolation (`resample_audio`) downsampling directly to Whisper's 16kHz target.
- **Pre-Roll Audio Ring Buffer**: Maintains a ~320ms pre-speech circular buffer that is prepended the millisecond voice activity is confirmed, eliminating clipped opening syllables ("Hey...", "Core...", "Wie...", "What...").
- **Expanded Hallucination Suppression**: Filters silence artifacts, subtitle captions, bracketed noise tokens (`[blank_audio]`, `(silence)`), and repetitive word stutter loops.

#### 🧠 Discourse Pragmatics & Spoken-To Awareness (`brain/spoken_to.py`, `core/gateway.py`)
- **Four-Role Discourse Classification Engine**: Dynamically discerns operator communicative intention between `ADDRESSED` (direct commands or natural imperatives), `DEMONSTRATED` (showing off Core AI to guests/friends), `REFERENCED` (third-person discussion/development talk $\to$ stays silent), and `BYSTANDER` (ambient dialogue between humans $\to$ stays silent).
- **Wake-Word-Free Room Directives**: Natural room-level imperatives are automatically recognized as `ADDRESSED` without requiring "Hey Core": reminders (`"erinnere mich in 5 Minuten..."`), timers (`"set a timer for 10 minutes"`), hardware monitoring (`"watch ram"`, `"git status"`), notes (`"save note..."`), clipboard (`"what's on my clipboard"`), and presence (`"ich bin jetzt im büro"`).
- **Intelligent Conversational Filler Stripping**: Normalizes spoken commands by recursively peeling leading particles (`"Core, bitte zeig mir den git status"` $\to$ `"git status"`).
- **REST Discourse Gateway Endpoint**: Added `POST /api/v1/voice/spoken_to` allowing Smart Mirrors, mobile satellites, and remote web clients to query the discourse engine remotely.

#### ⚡ Instant-Dispatch Zero-Overhead CLI (`interfaces/cli/client.py`, `core.bat`, `core.sh`)
- **Sub-50ms One-Shot Execution**: One-shot CLI goals (`core "<goal>"`) bypass all heavy Python module warmups (`torch`, `whisper`, `fastapi`, `uvicorn`) by dispatching directly to the running 24/7 background daemon over a persistent loopback socket.
- **Zero Console Log Pollution**: Eliminated logging framework initialization and SQLite database mounting noise from terminal outputs; quick one-shot queries return pure, colored ANSI responses.
- **Seamless Local Fallback**: Automatically and transparently falls back to in-process microkernel execution if the background daemon is not running.
- **Raw JSON Scripting Output**: Added `--json` and `--quiet` flags to support piping and external shell automation.

#### 🧠 Proactive Autonomous Agency & Reminders (`tools/native/proactive_tools.py`, `brain/proactive.py`)
- **Natural Language Countdown Reminders**: Schedule autonomous alerts directly via voice or CLI (`core "remind me in 10 minutes to review code"` / `"erinnere mich in 5 minuten an kaffee"`).
- **Instant Deterministic Dispatch**: Bypasses LLM reasoning latency entirely; routine reminder scheduling executes sub-millisecond with instant spoken audio / terminal confirmation.
- **Background Autonomous Firing & Auto-Deactivation**: The 24/7 `ProactiveDaemon` continuously tracks countdown timers, fires notifications via TTS and HUD card broadcasts upon expiry, and cleanly deactivates one-shot rules in SQLite.
- **Rule Management & Substring Cancellation**: Query active reminders (`core "list reminders"`) and cancel them on-the-fly (`core "cancel reminder review code"`) with fuzzy substring matching in `StateManager`.
- **Proactive Hardware Vitals Watcher**: Setup background supervisors (`core "watch my ram"`) to monitor host health and alert operator when RAM exceeds thresholds.

#### 🛠️ Daily Driver Developer Tools & Scratch Notes (`tools/native/dev_tools.py`, `brain/planner.py`)
- **Instant Git Repository Status**: Query project branch, working tree cleanliness, modified file counts, and latest commit (`core "git status"`) with zero cold-start delay.
- **Persistent Scratch Notes & Recall**: Fast CRUD operations for operator notes stored persistently in SQLite (`core "save note <title>: <content>"`, `core "my notes"`, `core "read note <title>"`, `core "delete note <title>"`).
- **Desktop Clipboard Integration**: Read and populate system clipboard dynamically (`core "what's in my clipboard"`, `core "copy <text> to clipboard"`).

#### 🚀 Zero-Delay Terminal Launch (`main.py`)
- **Instant Interactive REPL Boot**: Terminal starts instantaneously (<5ms) by defaulting animation to skipped and eliminating artificial micro-delays. 3D holographic boot animation is preserved via explicit `--anim` flag or `anim` terminal command.

#### ⚡ Windows IPv6 Loopback Latency Elimination (`interfaces/cli/client.py`, `main.py`)
- Standardized local HTTP loopback targeting to `127.0.0.1` instead of `localhost`, eliminating Windows IPv6 (`::1`) DNS resolution timeouts and cutting socket latency from 2,240ms down to 60ms.

### 🛡️ #ANTISLOP & Bloat Removal

#### 🚫 Fake Tool Purge (`tools/native/home_assistant.py`)
- **Erased `HomeAssistantMock`**: Removed simulated in-memory smart home mock. In strict compliance with the **#ANTISLOP** standard, tools are only exposed when backed by real physical integrations.
- **Dynamic Introspection Guard**: Hardened `brain/planner.py` to only schedule smart home service calls when real implementations are actively registered in `ToolRegistry`, preventing phantom step hallucinations.

#### 🧹 Repository & Artifact Pruning
- **Binary Archive Cleanup**: Purged binary distribution packages (`dist/Core-AI-v0.1.1-alpha.zip`) from git tracking.
- **Dynamic Tool Artifact Cleanup**: Removed ephemeral test generation residue (`tools/dynamic/hash_string.py`).

### 🧪 Automated Verification
- **139 / 139 Tests Passing**: Comprehensive test coverage across all subsystems including system resource diagnostics, intercontinental mesh latency, version protocol, proactive countdown evaluation, hardware supervision, git inspection, notes persistence, and planner routing (`tests/test_v020_release.py`).

---

## [[0.1.1-alpha]](https://github.com/Dyvorn/Core-AI/releases/tag/v0.1.1-alpha) — 2026-10-04
### Codename: "Genesis (Patch 1)"

| Kernel | Status | Verification | Ethos |
| :---: | :---: | :---: | :---: |
| **`v0.1.1-alpha`** | 🟢 **OPERATIONAL** | 🧪 **96 / 96 PASSED** | 🛡️ **#ANTISLOP** |


Critical patch release hardening pipeline variable resolution, OS process resource tracking, and physical spatial zone lifecycle management.

### 🐛 Fixed & Hardened

#### 🧠 Pipeline Engine Nested Array Resolution & Fuzzy Property Matching (`brain/pipeline_engine.py`)
- **Nested Bracket Template Parsing**: Added `_traverse_field_path` to support array and index bracket syntax (`discovered_devices.[0].ip_address`, `devices[0].ip`, `devices.0.ip`).
- **Semantic Field Aliasing**: Resolves common LLM hallucinations transparently (e.g. mapping `discovered_devices` $\to$ `devices`, `ip_address` $\to$ `ip`, and `device_name` $\to$ `name`).

#### ⚡ RAM & Hardware Metric Process Inspection (`tools/native/process_tools.py`, `brain/planner.py`)
- **Memory Consumption Aggregation & Sorting**: Parses raw OS process memory strings on Windows/Linux, sorting processes descending by RAM usage and aggregating instances across applications (e.g., grouping multi-process browser tabs and background workers).
- **Native RAM Query Routing**: Directly routes queries like *"whats pulling most ram"* and *"whats my ram doing"* to concurrent hardware metrics and sorted process analysis, delivering concrete utilization numbers and top memory consumers in spoken output.
- **Resilient Math Evaluation (`tools/native/math_tools.py`)**: Added keyword argument resilience to `calculate_math` to gracefully handle unexpected parameter calls (`field="memory_usage"`) without raising `TypeError`.

#### 🏛️ True Spatial Zone Pruning & Removal Lifecycle (`core/state.py`, `main.py`)
- **Database-Level Zone Deletion**: Implemented `StateManager.delete_zone()` and `StateManager.delete_all_zones_except()`, ensuring spatial zone cleanup persists cleanly in SQLite.
- **Native Tool `remove_spatial_zone`**: Registered native deletion tool with support for `all_except` / `keep_zone` filtering (e.g., *"remove all zones exept office"* cleanly purges unneeded zones from SQLite without generating unneeded dynamic tools).
- **CLI REPL Command**: Added `zone rm <zone_id>` and `zone remove <zone_id>` to the interactive Core Terminal shell.

---

## [[0.1.0-alpha]](https://github.com/Dyvorn/Core-AI/releases/tag/v0.1.0-alpha) — 2026-10-04
### Codename: "Genesis"

```text
┌───────────────────────┬───────────────────────┬───────────────────────┬───────────────────────┐
│ KERNEL: v0.1.0-alpha  │ STATUS: OPERATIONAL   │ VERIFICATION: 87/87   │ ETHOS: #ANTISLOP      │
└───────────────────────┴───────────────────────┴───────────────────────┴───────────────────────┘
```

The inaugural public alpha release of **C.O.R.E. AI** (**C**oncurrent **O**mnipresent **R**easoning **E**ngine) — a sovereign, privacy-first, self-hosted pervasive life operating system microkernel built to free personal technology from cloud lock-in, recurring rents, and corporate surveillance.

### 🌟 Added

#### ⚡ Concurrent Reasoning & DAG Pipeline Engine
- **Autonomous DAG Planning (`brain/planner.py`)**: Multi-step decomposition of natural language goals into non-linear directed acyclic dependency graphs.
- **Concurrent Execution Engine (`brain/pipeline_engine.py`)**: Parallel asynchronous execution of independent steps with dynamic inter-step variable cascading (`{{steps.<id>.output.<key>}}`).
- **Jarvis Failure Awareness**: Dynamic runtime exception isolation, root-cause diagnostics, and dynamic in-flight re-planning.
- **Deterministic Heuristic Routing**: Sub-10ms instant execution for everyday status, time, calculation, and local queries without LLM round-trips.

#### 🛡️ Sovereign Account & Day-Zero Blank Slate
- **Pure Day-Zero Isolation (`interfaces/cli/setup_wizard.py`)**: Zero hardcoded identities or accounts in Git. Every fresh clone initializes as a clean slate.
- **Interactive First-Boot Wizard**: Automatically prompts new operators on initial launch to choose their call sign, aliases, primary space, communication tone, and AI backends.
- **256-Bit Cryptographic Sovereign Secret**: Auto-generates a master authorization secret saved to `config/.env` for authenticating external devices into the `OWNER` trust tier.
- **Terminal Identity Card (`core account`)**: ANSI-styled high-contrast terminal card displaying operator handle, tone, registered zones, and secret status.
- **Factory Reset CLI (`core reset`)**: Complete zero-residue wipe restoring the local database, topology, and account back to Day-Zero.

#### 🌐 Universal Gateway & Intercontinental Mesh
- **High-Concurrency FastAPI Microkernel (`core/gateway.py`)**: REST endpoints and WebSockets for real-time telemetry (`/ws/events`, `/ws/logs`, `/ws/nodes/{id}`).
- **Synchronous Pipeline API (`/api/v1/pipeline/solve_sync`)**: Instant execution endpoint returning both machine step outputs and synthesized spoken conversational replies.
- **Role Specialization (`core/mesh_client.py`)**: Dynamic switching between `main_server` and roaming `edge_node`.
- **WireGuard / Tailscale WAN Routing**: Seamless interconnectivity across distributed devices worldwide.
- **State Bundle Portability**: Export and import full system state bundles (`core "mesh export"` / `core "mesh import"`).
- **Zero-Friction Device Onboarding (`interfaces/install/enroll.py`)**: One-command device enrollment with automated trust-tier assignment (`OWNER`, `AMBIENT`, `GUEST`).

#### 🎙️ Ambient Perception & Neural Voice Matrix
- **Local Neural Speech-to-Text (`engines/voice_in.py`)**: On-device Whisper inference (`faster-whisper` + `silero-vad`).
- **Neural Voice Synthesis (`engines/voice_out.py`)**: High-fidelity speech synthesis via Edge Neural TTS with offline fallback.
- **Spoken-To Discourse Classifier (`brain/spoken_to.py`)**: Semantic discrimination classifying user address vs. third-party showcase vs. ambient chatter.
- **Spatial Audio Routing (`engines/audio_router.py`, `brain/spatial_handoff.py`)**: Dynamic hardware introspection binding soundcards to spatial zones with automatic room relocation.

#### 📐 Terminal-Native 3D Holographic Rendering Engine
- **Pure-Math Wireframe Engine (`core/animation.py`)**: Real-time 3D vector graphics with floating-point Z-buffering in 2D terminal space.
- **3 Geometric Models**: Quantum Gyroscopic Core, 4D Hypercube (Tesseract), and Hexagonal Sovereign Monolith.
- **5 TrueColor Themes**: Cyber Cyan, Sovereign Void, Matrix Emerald, Solar Flare, and Hyper Steel.
- **Interactive Controls**: Real-time WASD camera rotation, theme toggling (`T`), model toggling (`M`), and animation pausing (`Space`).
- **Boot Sequence**: Cinematic terminal spin-up with skip-on-keypress.

#### 🔄 Dynamic Tool Synthesis & AST Sandboxing
- **On-Demand Capability Generation (`brain/dynamic_generator.py`)**: Autonomous Python tool authoring when capability gaps are encountered.
- **Strict AST Sandbox Security**: Static syntax inspection rejecting dangerous imports (`subprocess`, `ctypes`, `shutil`, `pty`) and unauthorized file operations.
- **Hot-Reloading**: Immediate registration and hot-loading into `tools/dynamic/` with zero microkernel downtime.

#### 🚀 24/7 Headless Daemon & Daily CLI Suite
- **Windows & Linux Service Management (`core/service.py`, `core.bat`, `core.sh`)**:
  - `core start` — Starts 24/7 background headless server.
  - `core status` — Displays status card showing PID, Gateway health, and active model.
  - `core stop` — Gracefully terminates server and frees GPU/RAM.
  - `core restart` — Restarts daemon.
- **Daily One-Shot Execution**: Direct terminal task dispatching (`core "<goal>"`).
- **Automated Self-Update Guard (`core/updater.py`)**: GitHub updates with automatic pre-update state snapshots and test verification rollbacks.

### 🧪 Quality Assurance & Test Verification
- **Automated Test Harness**: 87/87 tests passing with 100% green status across 20 test modules.
- **Windowless Daemon Hardening**: Safeguarded console logging against `sys.stdout is None` in detached processes.
- **Resilient Network Timeouts**: Guarded third-party weather/lookup tools against external 503 errors.
- **High-Speed Network Scanning**: Stripped blocking reverse DNS lookups, cutting ARP scan latencies from ~45 seconds to <20 milliseconds.
