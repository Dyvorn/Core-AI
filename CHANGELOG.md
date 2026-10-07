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

## [[0.2.0-alpha]](https://github.com/Dyvorn/Core-AI/releases/tag/v0.2.0-alpha) — 2026-10-07
### Codename: "Precision & Flow"

| Kernel | Status | Verification | Ethos |
| :---: | :---: | :---: | :---: |
| **`v0.2.0-alpha`** | 🟢 **OPERATIONAL** | 🧪 **123 / 123 PASSED** | 🛡️ **#ANTISLOP** |

Major Quality of Life (QoL) and stability milestone dedicated to 100% daily driver productivity, sub-50ms CLI execution, high-fidelity microphone capture & adaptive VAD, spoken-to discourse awareness, mock tool eradication, and microkernel streamlining.

### 🌟 Added & Enhanced

#### 🎙️ High-Fidelity Audio Capture & Resilient STT (`engines/voice_in.py`)
- **Native Hardware Rate Auto-Detection & Resampling**: Introspects native hardware sample rates (WASAPI / DirectSound 44.1kHz or 48kHz audio interfaces) to completely eliminate `PaErrorCode -9997 (Invalid sample rate)` on Windows. Integrates zero-dependency fast linear interpolation (`resample_audio`) downsampling directly to Whisper's 16kHz target.
- **Dynamic Noise-Floor Adaptive RMS VAD**: Replaced static peak energy thresholds with continuous ambient room noise floor estimation (`self.ambient_noise_floor`) and dynamic RMS tracking (`adaptive_threshold = max(0.008, ambient_noise_floor * 2.2)`). Ensures effortless triggering on quiet headsets while preventing runaway recordings in noisy rooms.
- **Pre-Roll Audio Ring Buffer**: Maintains a ~400ms pre-speech circular buffer that is prepended the millisecond voice activity is detected, eliminating clipped opening syllables ("Hey...", "Core...").
- **STT Model Cascade Fallback**: Supports `CORE_STT_MODEL` and `CORE_STT_LANGUAGE` environment overrides. Gracefully cascades down the model tier (`distil-large-v3` $\to$ `small` $\to$ `base` $\to$ `tiny`) if VRAM allocation or memory pressure occurs.
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
- **118 / 118 Tests Passing**: Comprehensive test coverage across all subsystems including proactive countdown evaluation, hardware supervision, git inspection, notes persistence, and planner routing (`tests/test_proactive_and_dev_tools.py`).

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
