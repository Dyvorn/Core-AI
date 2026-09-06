# CORE AI

```
+-----------------------------------------------------------------------------+
|    ____ ___  ____  _____     _    ___                                       |
|   / ___/ _ \|  _ \| ____|   / \  |_ _|                                      |
|  | |  | | | | |_) |  _|    / _ \  | |                                       |
|  | |__| |_| |  _ <| |___  / ___ \ | |                                       |
|   \____\___/|_| \_\_____|/_/   \_\___|   Sovereign Ubiquitous Life OS       |
+-----------------------------------------------------------------------------+
```

```text
[ SYSTEM: CORE-AI-KERNEL ]  [ STATUS: 74/74 TESTS PASSED ]  [ PYTHON: 3.13+ ]
[ LICENSE: AGPL-3.0-ONLY ]  [ ARCHITECTURE: ASYNC-DAG ]     [ ETHOS: #ANTISLOP ]
```

> **A self-hosted, sovereign, and privacy-first AI companion built to integrate into daily life across your workspace, living spaces, grounds, vehicle, bicycle, wearables, and mobile devices. Zero big-tech cloud lock-in, zero hardcoded assumptions, and engineered for multi-year evolution.**

---

### Core Identity & The #ANTISLOP Movement

> *"We use AI to become more sustainable, smarter, and make human life genuinely easier -- not to extract rent, hoard personal data, or pump low-effort corporate cash-grabs."*
> — **Dyvorn**, Lead Architect

Core AI is built around a non-negotiable sovereign identity and purpose:

1. **Human Elevation, Not Exploitation**: Technology must serve the human being, eliminate daily friction, and protect personal privacy. We reject intrusive corporate surveillance and walled-garden platforms.
2. **Minimizing AI Compute Costs & Planetary Resource Impact (Water & Power)**:
   Modern cloud AI data centers consume astronomical electrical grids and evaporate billions of liters of potable freshwater every year for evaporative cooling. Core AI is engineered to minimize unnecessary LLM inference:
   - Deterministic DAG planning and rule-based heuristic routing resolve frequent tasks instantly with zero external API calls.
   - On-device speech recognition (`faster-whisper`) and local audio synthesis run directly on host hardware.
   - Dynamic Python tools run natively in memory rather than passing bloated token context windows through cloud servers.
   We refuse to boil the planet's water supply to generate low-effort marketing slop.
3. **100% Charity Commitment**:
   Core AI is not a for-profit commercial scheme. If donations or sponsorships are ever accepted, **100% of all proceeds are directed to verified humanitarian and ecological charities** (providing clean drinking water, disaster relief, and nature conservation). We will never monetize your home, your life, or your sovereign data.
4. **Zero Hardcoded Devices & Zero Hardcoded UIs (Dynamic Device Synthesis)**:
   The open-source Core AI repository contains zero hardcoded gadget interfaces. Whether you build your own smart glasses, assemble a bicycle telemetry head unit, station a smart mirror, or deploy a headless Raspberry Pi in your workshop -- Core AI does not impose a static interface:
   - Core AI connects over the terminal or Universal Gateway WebSocket mesh.
   - It introspects the device's screen geometry, file tree, sensors, and capabilities.
   - It reasons about the operator's lifestyle and current intent, and **autonomously synthesizes custom UIs, widgets, or telemetry streams on-demand**.
   - Custom hardware adaptations belong in lightweight community plugins, keeping the core microkernel clean, fast, and unbloated.
5. **Deep Contextual & Intent Reasoning**:
   Core AI is not a reactive bot or a trigger-happy chatbot. It reasons continuously before acting:
   - *Does this action make sense for what the operator is doing right now?*
   - *What is the operator's true underlying intent?*
   - *Are they deeply engaged in focused work, demonstrating Core AI to guests, resting, or commuting?*

---

### Contributors & Stewardship

| Role | Identity | Profile / Contact | Focus Areas |
| :--- | :--- | :--- | :--- |
| **Lead Architect & Maintainer** | **Dyvorn** *(aka Vyrn / Refined)* | [@Dyvorn](https://github.com/Dyvorn) | Core Microkernel, DAG Engine, Spatial Mesh, Voice Pipeline |
| **Open Source Community** | *Community Contributors* | [CONTRIBUTING.md](CONTRIBUTING.md) | Device Drivers, Edge Adapters, Hardware Plugins, Test Coverage |

---

### Full Technology Stack

| Layer | Technologies & Protocols | Purpose |
| :--- | :--- | :--- |
| **Core Microkernel** | `Python 3.13+` / `Asyncio` / `Pydantic v2` | High-concurrency event loop, strict schema validation, zero-bloat foundation |
| **Intelligence & Brain** | `DAG Engine` / `AST Security Gate` / `Dynamic Sandbox` | Autonomous multi-step planning, capability gap detection, verified self-extension |
| **State & Persistence** | `SQLite (WAL mode)` / `Redis EventBus` *(InMemory fallback)* | Ultra-low latency thread-safe state, execution audit logs, pub/sub messaging |
| **Universal Edge Gateway** | `FastAPI` / `Uvicorn` / `WebSockets` / `REST` | High-speed event streams (`/ws/events`, `/ws/logs`), OpenAPI docs, edge node mesh |
| **Spatial Audio & Unity** | `SoundDevice` / `SpatialHandoffEngine` / `SpatialContext` | Zone-to-hardware binding, cross-space audio transfer, dynamic acoustic routing |
| **Voice & Perception** | `Silero-VAD` / `faster-whisper (STT)` / `Piper` / `Edge-TTS` | Local voice activity detection, rapid transcription, neural speech synthesis |
| **Ambient & Edge Interfaces** | `Dynamic UI Synthesis` / `Nothing OS Glyph` / `Core Terminal` | On-demand UI generation, tactile phone feedback, interactive CLI shell |
| **Hardware Interoperability** | `Home Assistant API` / `Tailscale WireGuard` / `PipeWire` | Sovereign smart-home orchestration, encrypted mesh tunneling, audio routing |

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Core Philosophy & Invariants](#core-philosophy--invariants)
  - [Zero Hardcoding: Hierarchical Spatial Topology](#1-zero-hardcoding-hierarchical-spatial-topology)
  - [Protocol-Agnostic Event Mesh](#2-protocol-agnostic-event-mesh)
  - [Distributed Edge Tool Dispatch](#3-distributed-edge-tool-dispatch)
  - [Security Tiers & Privacy Defense](#4-security-tiers--privacy-defense)
- [Subsystem Deep Dive](#subsystem-deep-dive)
  - [Tool Introspection & Discovery](#1-tool-introspection--registry)
  - [Autonomous DAG Pipeline Engine](#2-autonomous-dag-pipeline-engine)
  - [Self-Extension & Dynamic Tool Synthesis](#3-self-extension--dynamic-tool-synthesis)
  - [Jarvis-Like Failure Awareness](#4-jarvis-like-failure-awareness)
  - [Multi-Sink Logging & Audit Trails](#5-multi-sink-logging--audit-trails)
  - [Spatial Audio Routing & Cross-Zone Handoff](#6-spatial-audio-routing--cross-zone-handoff)
  - [Sovereign Reasoning & Execution Harness](#7-sovereign-reasoning--execution-harness)
- [Repository Structure](#repository-structure)
- [Ubiquitous Device & Zone Ecosystem](#ubiquitous-device--zone-ecosystem)
- [Multi-Platform & Operating System Strategy](#multi-platform--operating-system-strategy)
- [Cool Little Extras](#cool-little-extras)
  - [Interactive Shell Session Preview](#interactive-shell-session-preview)
  - [Failure Diagnosis Specimen](#failure-diagnosis-specimen)
  - [Nothing OS Glyph Matrix Pulse Spec](#nothing-os-glyph-matrix-pulse-spec)
  - [Dynamic Spatial Audio Routing Specimen](#dynamic-spatial-audio-routing-specimen)
- [Current Status: What Works vs. Roadmap](#current-status-what-works-vs-roadmap)
- [Problem Logging & Technical Debt Ledger](#problem-logging--technical-debt-ledger)
- [Getting Started & Sovereign Usage](#getting-started--sovereign-usage)

---

## System Architecture

```text
               +---------------------------------------------+
               |         PHYSICAL REALITY & SENSORS          |
               |  (Rooms, Workshop, Vehicles, Wearables)     |
               +----------------------+----------------------+
                                      |
                                      v
               +---------------------------------------------+
               |           UNIVERSAL EDGE GATEWAY            |
               |   FastAPI / WebSockets / Tailscale WireGuard|
               +----------------------+----------------------+
                                      |
                         +------------+------------+
                         |                         |
                         v                         v
               +-------------------+     +-------------------+
               |  IN-MEMORY / REDIS|     |   PROACTIVE LOOP  |
               |     EVENT BUS     |     |   DAEMON (STATE)  |
               +---------+---------+     +---------+---------+
                         |                         |
                         +------------+------------+
                                      |
                                      v
               +---------------------------------------------+
               |            CORE AI MICROKERNEL              |
               |                                             |
               |   +-------------------------------------+   |
               |   |  Autonomous DAG Pipeline Engine     |   |
               |   |  - Concurrency ("Multiple At Once") |   |
               |   |  - Dynamic Variable Piping          |   |
               |   |  - Jarvis-Like Failure Awareness    |   |
               |   +------------------+------------------+   |
               |                      |                      |
               |   +------------------v------------------+   |
               |   |  AST Security Gate & Dynamic Sandbox|   |
               |   |  - Tool Synthesis & Hot-Reload      |   |
               |   +------------------+------------------+   |
               |                      |                      |
               |   +------------------v------------------+   |
               |   |  Spatial Audio & Cross-Zone Handoff |   |
               |   |  - SoundDevice Introspection        |   |
               |   |  - Ambient Mirror / Projection HUD  |   |
               |   +-------------------------------------+   |
               +----------------------+----------------------+
                                      |
                      +---------------+---------------+
                      |                               |
                      v                               v
            +-------------------+           +-------------------+
            |  SQLITE (WAL MODE)|           |  ACTUATOR MESH    |
            |  - State & Zones  |           |  - Audio Hardware |
            |  - Audit Trails   |           |  - Edge Displays  |
            |  - Operator Profil|           |  - Home Assistant |
            +-------------------+           +-------------------+
```

---

## Core Philosophy & Invariants

### 1. Zero Hardcoding: Hierarchical Spatial Topology

Hardcoding assumptions like *"everything is a living room"* breaks down when scaling to an outdoor workshop, garden, vehicle, bicycle, smart glasses, or airplane hangar. Core AI structures physical reality into flexible, hierarchical zones:

```text
zone: home/indoor/<space>       :: Studio, Office, Sanctuary, Kitchen
zone: home/outdoor/<space>      :: Workshop, Garden, Patio, Hangar
zone: mobile/vehicle/<type>     :: Car (OBD-II, Head-Unit), Bicycle (GPS, Cadence)
zone: mobile/wearable/<type>    :: Smart Glasses (AR HUD, FOV Cam), Phone (Glyph, Push)
```

Every event (`BaseEvent`) carries its `spatial_context`, `device_type`, and `capabilities`. Operators provision new spaces on the fly without writing code.

### 2. Protocol-Agnostic Event Mesh

Devices communicate across distinct physical and network media:
- **Local LAN**: High-bandwidth studio monitors, smart mirrors, home servers.
- **WireGuard / Tailscale Mesh**: Secure private encrypted WAN connecting your vehicle and phone back to the core.
- **BLE (Bluetooth Low Energy)**: Battery-constrained smart glasses and bicycle sensors bridging via mobile companion.

The `EventBus` abstracts message passing with automatic in-memory fallback, allowing seamless transport transitions without altering core logic.

### 3. Distributed Edge Tool Dispatch

Tools are not confined to the central host. Through `ToolCallRequest.target_node`, operations execute wherever the physical capability exists:
- **Central Host**: Heavy model inference, database persistence, audio routing.
- **Phone Companion**: Sending notifications, tactile vibration patterns, cellular routing.
- **Vehicle Unit**: Remote climate preconditioning, door locks, querying battery/fuel telemetry.
- **Smart Glasses**: Displaying micro-glance HUD cards, low-latency bone conduction voice.

### 4. Security Tiers & Privacy Defense

Core AI enforces three immutable security tiers:

| Tier | Identity | Scope & Privileges | Enforcement |
| :--- | :--- | :--- | :--- |
| **`OWNER`** | Host Operator | Full access to identity memory, private documents, critical actuator tools, and all spatial zones. | Full Access |
| **`AMBIENT`** | Displays & Mics | Smart mirrors, wall projections, room microphones. Can render HUD cards, play audio, and stream sensor data. Cannot dump private identity profiles. | Scoped Access |
| **`GUEST`** | Untrusted Network | Unknown devices on local network. Access to private profiles and sensitive tools is strictly rejected. Interaction requires explicit owner approval. | `HTTP 403 Forbidden` |

---

## Subsystem Deep Dive

### 1. Tool Introspection & Registry
- **File Reference**: [tools/registry.py](file:///g:/VSC_Projects/Core%20AI/tools/registry.py)
- Maintains both native built-in tools and self-synthesized dynamic tools.
- Generates runtime JSON schemas via `get_tool_catalog()` formatted for LLM reasoning.
- Scans `tools/dynamic/` on startup with zero-restart hot-reloading (`reload_dynamic_tools()`).
- Yields structured `StepResult` objects containing exact execution duration (`duration_ms`), success status, output payloads, and stacktraces.

### 2. Autonomous DAG Pipeline Engine
- **File Reference**: [brain/pipeline_engine.py](file:///g:/VSC_Projects/Core%20AI/brain/pipeline_engine.py)
- Parses multi-step dependency graphs from arbitrary operational goals.
- **Concurrent Execution ("Multiple Things At Once")**: Automatically identifies independent branches and runs them in parallel via `asyncio.gather` and thread worker pools.
- **Dynamic Variable Piping**: Steps reference earlier outputs using runtime syntax like `{{steps.math_step.output.result}}` or `$step_id.field`.
- Persists step state transitions directly to SQLite (`core_ai.db`).

### 3. Self-Extension & Dynamic Tool Synthesis
- **File Reference**: [brain/dynamic_generator.py](file:///g:/VSC_Projects/Core%20AI/brain/dynamic_generator.py)
- When a required tool is missing:
  1. **Code Generation**: Generates compliant Python implementations conforming to strict schema rules.
  2. **Security Gate (AST Validation)**: Validates the abstract syntax tree to disallow unsafe packages (`subprocess`, `shutil`, `ctypes`) and dangerous calls (`fork`, `eval`, `exec`).
  3. **Sandbox Verification**: Executes the generated code in an isolated dictionary namespace with test parameters.
  4. **Persistence & Hot-Reload**: Writes the tool to `tools/dynamic/<tool_name>.py`, stores metadata in SQLite, and registers it into `ToolRegistry` with zero downtime.

### 4. Jarvis-Like Failure Awareness
- **File Reference**: [brain/pipeline_engine.py](file:///g:/VSC_Projects/Core%20AI/brain/pipeline_engine.py) & [brain/planner.py](file:///g:/VSC_Projects/Core%20AI/brain/planner.py)
- When a tool returns an error status or throws an exception:
  - Generates a structured `FailureDiagnosis` (failed step, tool name, error message, root-cause analysis, remediation strategy).
  - Distinguishes between retryable faults (transient network glitches, parameter formatting) and fatal faults (missing hardware, unregistered tools).
  - Triggers self-healing retries with exponential backoff or re-plans alternative tool routes.

### 5. Multi-Sink Logging & Audit Trails
- **File Reference**: [core/logging_setup.py](file:///g:/VSC_Projects/Core%20AI/core/logging_setup.py)
- **High-Contrast Console**: Formatted log lines with timestamps, log levels, and subsystem tags.
- **Rotating System Log**: `logs/core_ai.log` with automatic 5MB rotation and 5 archival backups.
- **Immutable JSONL Audit Trail**: `logs/pipelines.jsonl` recording machine-readable lifecycle transitions for every pipeline execution.
- **Database Logs**: Structured execution history stored in the `execution_logs` SQLite table.

### 6. Spatial Audio Routing & Cross-Zone Handoff
- **File References**: [engines/audio_router.py](file:///g:/VSC_Projects/Core%20AI/engines/audio_router.py) & [brain/spatial_handoff.py](file:///g:/VSC_Projects/Core%20AI/brain/spatial_handoff.py)
- Dynamically queries host soundcards via `sounddevice.query_devices()` without hardcoding device indices.
- Binds audio inputs and outputs to arbitrary zone IDs in SQLite.
- Seamlessly transfers active microphone and speaker streams when the operator moves between spaces (`SpatialHandoffEvent`).
- Dispatches ambient greeting and status HUD cards to the destination mirror or wall projection.

### 7. Sovereign Reasoning & Execution Harness
- **File References**: [brain/planner.py](brain/planner.py), [brain/safety.py](brain/safety.py), [brain/model_router.py](brain/model_router.py), [tools/native/weather_tools.py](tools/native/weather_tools.py), [tools/native/knowledge_tools.py](tools/native/knowledge_tools.py)
- The execution harness wraps neural and heuristic models within a deterministic, sandboxed, and presence-aware operating runtime:
  1. **Intent Normalization & Prefix Stripping**: Conversational greetings and casual fillers (`"hi, "`, `"hey core, "`, `"hallo, "`) are stripped from the core intent so questions like `"hi whats the temp in Halle (Saale)"` are planned accurately without triggering canned greeting overrides.
  2. **Verbal Spatial Relocation**: Natural relocation commands (e.g. `"I'm in the office rn"`, `"ich bin jetzt im büro"`, `"moved to kitchen"`) dynamically synthesize a relocation step, re-route audio streams, dispatch ambient HUD cards, and update the interactive prompt (`Core [Dyvorn@office] >`).
  3. **The #ANTISLOP Anti-Hallucination Invariant**: When external hardware or integrations are missing (e.g. smart fridge), Core AI refuses to fabricate tool steps or hallucinate false data. Instead, it inspects the physical LAN via ARP/IP scanning (`scan_local_network`, `inspect_lan_device`) to search for smart hardware, or provides an honest, polite offline notification when no AI model is connected.
  4. **Harm-Free Unstoppable Agency (`SafetyGate`)**: Protects against catastrophic system destruction (`format c:`, `rm -rf /`, fork bombs) while leaving ordinary human tasks completely unhindered by artificial corporate moralizing.
  5. **Thinking Model Safeguards**: Generous token headroom (`1024` tokens) and `finish_reason` safety checks prevent reasoning models with internal chain-of-thought tokens (such as Gemini 2.5 Flash Thinking) from cutting off spoken sentences mid-speech.
  6. **Real-Time World & Network Sensing**:
     - `get_weather`: Free, zero-auth global weather, temperature (°C/°F), conditions, humidity, and wind via Open-Meteo.
     - `lookup_knowledge`: Factual encyclopedic summaries via Wikipedia (EN/DE).
     - `scan_local_network` & `inspect_lan_device`: Local hardware discovery and edge node inspection.
  7. **Harness Diagnostic Command (`harness` / `eval`)**: Live multi-subsystem diagnostic in the Core Terminal evaluating State Manager, Tool Registry, Model Router, EventBus, Audio Matrix, Safety Gate, and Universal Gateway in one command.

### 8. Sovereign Desktop & Host OS Automation (Zero-Refusal Agency)
- **File References**: [tools/native/web_tools.py](tools/native/web_tools.py), [tools/native/desktop_tools.py](tools/native/desktop_tools.py), [tools/native/media_tools.py](tools/native/media_tools.py), [tools/native/process_tools.py](tools/native/process_tools.py), [tools/native/shell_tools.py](tools/native/shell_tools.py), [brain/dynamic_generator.py](brain/dynamic_generator.py)
- Fully empowers Core AI as an autonomous, proactive workstation companion on the host machine without relying on external bloatware:
  1. **Zero-Refusal Workplace Rule**: Core AI rejects canned corporate disclaimers (*"I can't open applications on your machine"*). It possesses native tools to execute host actions directly.
  2. **Browser & Video Navigation**: `open_youtube` (searches or plays topics/videos), `open_url` (any web address), and `search_web_query` (DuckDuckGo, Google, Bing).
  3. **Desktop Application Launching**: `launch_application` runs applications (e.g. `youtube`, `spotify`, `vscode`, `chrome`, `firefox`, `calc`, `notepad`, `terminal`, `explorer`) in non-blocking detached processes across Windows, Linux, and macOS.
  4. **Hardware Media & Audio Keys**: `media_control` emulates hardware multimedia keyboard keys (`play_pause`, `next`, `previous`, `volume_up`, `volume_down`, `mute`) using standard OS APIs.
  5. **Display & Clipboard Perception**: `take_screenshot` captures the active display to timestamped PNG files with zero pip dependencies (using PowerShell .NET Graphics on Windows); `get_clipboard_text` and `set_clipboard_text` allow bidirectional clipboard interaction.
  6. **Process & Resource Inspection**: `list_running_processes`, `get_hardware_metrics` (live CPU %, RAM total/used/free, disk capacity), `lock_workstation`, and `kill_process` (strictly protected by SafetyGate against terminating vital OS processes or Core AI itself).
  7. **Audited Shell Execution**: `run_shell_command` runs terminal commands safe-listed through `SafetyGate`.
  8. **Autonomous Tool Self-Generation**: If a specialized calculation, data transformer, or parser is missing from the catalog, Core AI's planner synthesizes the tool code on the fly via `DynamicGenerator`, validates its AST against forbidden imports, executes it in a sandboxed scope, and persists it to `tools/dynamic/` for instant execution.

---

## Repository Structure

```text
Core AI/
+-- brain/                      # Intelligence, Planning, & Spatial Unity
|   +-- dynamic_generator.py    # Synthesizes, verifies (AST + sandbox), & persists new tools
|   +-- model_router.py         # Dynamic AI provider & model router with runtime overrides
|   +-- pipeline_engine.py      # Async DAG engine; concurrent step execution & variable piping
|   +-- planner.py              # Tool introspection, capability gap detector & DAG architect
|   +-- proactive.py            # Proactive background watcher & conditional trigger daemon
|   +-- safety.py               # Harm-free unstoppable agency & safety gate
|   +-- spatial_handoff.py      # Cross-zone spatial handoff & dynamic audio stream migration
+-- config/                     # Configuration & Environment
|   +-- nodes.yaml              # Multi-device topology (rooms, outdoor, car, bike, glasses)
|   +-- settings.yaml           # Model endpoints, logging paths, audio & bus settings
|   +-- .env.example            # API keys and local endpoint credentials template
+-- core/                       # Foundational Microkernel Services
|   +-- bus.py                  # Protocol-agnostic EventBus (Redis with auto in-memory fallback)
|   +-- context.py              # Ubiquitous ContextManager (spatial zones, device profiles)
|   +-- gateway.py              # FastAPI Universal Gateway (REST, WebSockets, OpenAPI)
|   +-- logging_setup.py        # Multi-sink logger: Console, Rotating File, & JSONL audit
|   +-- mesh_client.py          # Intercontinental mesh client & autonomous offline fallback
|   +-- schemas.py              # Pydantic v2 schemas (events, pipelines, dynamic tools, spatial)
|   +-- service.py              # Service & process suite controller (start, stop, RAM/GPU free)
|   +-- state.py                # SQLite WAL-mode state manager (pipelines, audio routes, profiles)
|   +-- updater.py              # Self-updater with automated test-guard & rollback
+-- docs/                       # Project Documentation & Issue Tracking
|   +-- CUSTOMIZATION_AND_MODELS.md # AI provider setup, model roles, & per-task overrides
|   +-- INTERCONTINENTAL_MESH.md    # Global mesh architecture, offline fallback, & migration
|   +-- ROADMAP.md              # Long-term multi-year milestone roadmap (Phases 1-6)
|   +-- PROBLEMS_AND_DEBT.md    # Dedicated ledger tracking known bugs, edge cases & debt
|   +-- SESSION_HANDOVER.md     # Engineering handovers, architecture decisions, & session context
+-- engines/                    # Audio & Perception Processing Engines
|   +-- audio_router.py         # Dynamic spatial audio hardware introspection & route binding
|   +-- voice_in.py             # Silero-VAD + faster-whisper STT audio capture
|   +-- voice_out.py            # Text-To-Speech engine (Kokoro / Piper / Pyttsx3)
+-- interfaces/                 # Client Interfaces & Installers
|   +-- cli/
|   |   +-- core_console.py     # Command center launcher (delegates to main.py)
|   |   +-- setup_wizard.py     # Interactive zero-hardcoding operator profile initializer
|   +-- install/
|   |   +-- enroll.py           # 1-line zero-friction edge device onboarding client
|   |   +-- setup_service.py    # Interactive bootstrap, desktop launcher & autostart setup
|   |   +-- uninstall.py        # Clean zero-residue complete uninstaller
+-- logs/                       # System & Audit Logs
|   +-- core_ai.log             # Rotating system logs (5MB, 5 backups)
|   +-- pipelines.jsonl         # Detailed JSONL audit records of all pipeline executions
+-- install.ps1                 # Windows PowerShell one-line bootstrap installer
+-- install.sh                  # Linux/macOS Bash one-line bootstrap installer
+-- core.bat                    # Windows turnkey CLI command center (run/setup/status/stop)
+-- core.sh                     # Linux/macOS turnkey CLI command center
+-- tools/                      # Tool Ecosystem
|   +-- dynamic/                # Self-generated tools written, verified, and saved by Core AI
|   |   +-- hash_string.py      # Example auto-synthesized dynamic tool
|   +-- native/                 # Built-in native tools
|   |   +-- file_tools.py       # File reading, writing, and directory listing
|   |   +-- home_assistant.py   # Home Assistant smart device integration mock
|   |   +-- knowledge_tools.py  # Factual encyclopedic summaries via Wikipedia
|   |   +-- math_tools.py       # Safe mathematical evaluation & statistics
|   |   +-- network_tools.py    # ARP/IP local network scan & device discovery
|   |   +-- spatial_tools.py    # Spatial audio routing tool for autonomous planner
|   |   +-- system_tools.py     # System time and platform status
|   |   +-- weather_tools.py    # Real-time weather & temperature via Open-Meteo
|   +-- registry.py             # Dynamic tool registry, catalog introspection, & safe execution
+-- tests/                      # Automated Test Suite (pytest, 68/68 tests passing)
|   +-- test_bus.py             # EventBus pub/sub and in-memory queue tests
|   +-- test_dynamic_generator.py # AST security validation & sandbox execution tests
|   +-- test_gateway.py         # REST & WebSocket endpoint tests
|   +-- test_logging.py         # JSONL pipeline audit and logger tests
|   +-- test_mesh_client.py     # Intercontinental mesh, export/import & offline tests
|   +-- test_model_router.py    # Dynamic provider auto-discovery & role routing tests
|   +-- test_pipeline_engine.py # DAG concurrency, variable piping, and retry tests
|   +-- test_planner.py         # Introspection, gap detection, weather, & relocation tests
|   +-- test_proactive.py       # Proactive daemon condition-action watcher tests
|   +-- test_registry.py        # Tool discovery, catalog schemas, and execution timing tests
|   +-- test_remote_dispatcher.py # Distributed RPC edge tool dispatch tests
|   +-- test_safety.py          # SafetyGate catastrophic protection & agency tests
|   +-- test_service_and_updater.py # Lifecycle, PID, and update guard tests
|   +-- test_spatial_audio.py   # Dynamic audio routing, handoff, and soundcard tests
|   +-- test_spoken_to.py       # Discourse posture, showcase, and bystander tests
|   +-- test_voice_pipeline.py  # Voice input, STT, and neural TTS synthesis tests
+-- core_ai.db                  # SQLite database (pipelines, steps, dynamic tools, audio routes)
+-- requirements.txt            # Python dependencies
+-- main.py                     # Core AI microkernel runtime entrypoint
```

---

## Ubiquitous Device & Zone Ecosystem

Configured dynamically or initialized via `config/nodes.yaml`:

| Node ID | Zone ID | Form Factor | Primary Capabilities | Transport |
| :--- | :--- | :--- | :--- | :--- |
| `room_workspace` | `home/indoor/workspace` | `room` | Mic Array, Studio Monitor, Ambient HUD | Local LAN |
| `room_sanctuary` | `home/indoor/sanctuary` | `room` | Hi-Fi Audio, Soft Lighting, Mic | Local LAN |
| `ground_workshop`| `home/outdoor/workshop`  | `outdoor_zone` | Mic, PA Speaker, Industrial Telemetry | Local LAN |
| `ground_hangar`  | `home/outdoor/hangar`    | `outdoor_zone` | Long-Range PA, Environmental Sensors | Local LAN / Mesh |
| `vehicle_car`    | `mobile/vehicle/car`     | `vehicle_car` | Car Audio, Dashboard HUD Tile, GPS, OBD-II | Tailscale Mesh |
| `vehicle_bike`   | `mobile/vehicle/bike`    | `vehicle_bike` | High-Contrast HUD, Cadence, GPS, Haptic | BLE / Phone Bridge |
| `wearable_glasses`| `mobile/wearable/glasses`| `smart_glasses`| Micro HUD, Bone Conduction Audio, FOV Cam | BLE / Phone Bridge |
| `wearable_phone` | `mobile/wearable/phone`   | `phone` | Rich Screen, Push Notifications, GPS, Mic | Cellular / Mesh |

---

## Multi-Platform & Operating System Strategy

Core AI is designed with **strict platform neutrality and zero OS vendor lock-in**:

```text
                            +-------------------+
                            |  CORE AI RUNTIME  |
                            +---------+---------+
                                      |
         +-----------------+----------+----------+-----------------+
         |                 |                     |                 |
         v                 v                     v                 v
   +-----------+     +-----------+         +-----------+     +-----------+
   |   LINUX   |     |  ANDROID  |         | EMBEDDED  |     |  WINDOWS  |
   | (PRIMARY) |     | NOTHING OS|         |   LINUX   |     |   MACOS   |
   +-----+-----+     +-----+-----+         +-----+-----+     +-----+-----+
         |                 |                     |                 |
   +-----+-----+     +-----+-----+         +-----+-----+     +-----+-----+
   | Arch/Fedora     | Glyph LED           | Car SBC /   |     | Workstation
   | Debian/Alpine   | Matrix              | Raspberry Pi|     | Local Dev
   | PipeWire/ALSA   | Quick Tiles         | Alpine/Yocto|     | Cross-Plat
   | Systemd Units   | BLE Bridge          | Kiosk HUD   |     | POSIX Py3
   +-----------+     +-----------+         +-----------+     +-----------+
```

### 1. Linux (Primary Production & Workstation Target)
- **Role**: Primary host for home servers, automotive SBCs, and main developer rigs.
- **Distros**: Arch, Debian, Ubuntu, Fedora, Alpine.
- **Audio Stack**: Direct PipeWire, PulseAudio, and ALSA integration via `sounddevice`.
- **Daemons**: Native `systemd` user services and headless background execution.

### 2. Android & Nothing OS (Tier-1 Mobile Companion)
- **Role**: Ubiquitous companion bridge outside the physical home.
- **Nothing OS Specialization**:
  - **Glyph Matrix Integration**: Rear Glyph LEDs render subtle ambient feedback (pulsing glyph patterns while Core AI reasons, quiet flashes on completion, discreet security warnings).
  - **Quick Tiles & Ambient Widgets**: 1-tap voice invocation and status indicators.
- **Edge Gateway**: Bridges Bluetooth Low Energy (BLE) peripherals (smart glasses, bike sensors) back to Core AI over cellular wireguard.

### 3. Custom OS & Embedded Linux (Automotive, Bike, Smart Mirror, Projections)
- **Smart Mirror & Wall Projections**: Lightweight micro-browsers running in fullscreen kiosk mode displaying real-time HUD cards.
- **Automotive & Bike**: Minimalist Alpine/Yocto builds on ARM/x86 SBCs with direct CAN-bus/OBD-II and GPS access.

### 4. Windows & macOS (Portable Development)
- Cross-platform UTF-8 console output, POSIX-compliant file paths, and zero Windows-specific binary dependencies.

---

## Cool Little Extras

### Interactive Shell Session Preview

An authentic trace from the `Core Console` showing concurrent multi-step DAG planning and dynamic variable piping:

```text
>>> solve compute the sha256 hash of 'AntiSlop-2026' and print current time
[CoreAI.Planner] Introspecting catalog: 6 native tools, 1 dynamic tools found.
[CoreAI.DAG] Formulating execution graph:
  +-- [Step 1: hash_string] target: 'AntiSlop-2026' (dynamic tool)
  +-- [Step 2: get_time] timezone: 'UTC' (native tool)
  Dependency check: Independent steps detected -> executing concurrently.
[CoreAI.DAG] Step 'hash_string' dispatched to worker pool...
[CoreAI.DAG] Step 'get_time' dispatched to worker pool...
[CoreAI.DAG] Step 'hash_string' completed in 1.42ms -> output: 7f83b165...
[CoreAI.DAG] Step 'get_time' completed in 0.88ms -> output: 2026-09-05T22:45:00Z
[CoreAI.Audit] Persisted execution log to SQLite and logs/pipelines.jsonl.
Pipeline completed successfully in 2.30ms.
```

### Failure Diagnosis Specimen

When an error occurs, Core AI outputs structured diagnostic data rather than failing silently:

```json
{
  "failed_step": "fetch_weather",
  "tool_name": "weather_api",
  "error_message": "ConnectionRefusedError: [Errno 111] Connection refused at 10.0.0.45:8080",
  "root_cause": "Local environmental sensor bridge at 10.0.0.45 is offline or unreachable.",
  "suggested_fix": "Verify power to workshop sensor node or fall back to outdoor_meteo_backup.",
  "is_retryable": true,
  "retry_strategy": "exponential_backoff_3x"
}
```

### Nothing OS Glyph Matrix Pulse Spec

The rear Glyph LED hardware patterns mapped to Core AI operational states:

```text
Idle State:
LED [ ] ------------------------------------------------ (Off / Low Ambient)

Thinking / DAG Reasoning:
LED [*] ~~~~~~ [***] ~~~~~~ [*] ~~~~~~ [***] ~~~~~~~~~~~ (Subtle Sine Wave Pulse)

Action Completed:
LED [***] ---------------------------------------------- (Single 150ms Soft Flash)

Security Alert / Guest Warning:
LED [***] [   ] [***] [   ] [***] ---------------------- (Triple Staccato Burst)
```

### Dynamic Spatial Audio Routing Specimen

Real-time audio route binding stored in SQLite and managed on the fly:

```text
+-------------------+----------------------------+----------------------------+---------+
| ZONE ID           | INPUT DEVICE               | OUTPUT DEVICE              | STATUS  |
+-------------------+----------------------------+----------------------------+---------+
| workspace         | Studio Mic Array (USB)     | Reference Monitors (Ch 1-2)| ACTIVE  |
| sanctuary         | Acoustic Ceiling Mic (In 3)| Hi-Fi DAC (USB-C)          | ACTIVE  |
| workshop          | Industrial Mic (Line In)   | Overhead Horn (Line Out)   | STANDBY |
| hangar            | Long-Range Array           | PA Main (Ch 3-4)           | STANDBY |
+-------------------+----------------------------+----------------------------+---------+
```

---

## Current Status: What Works vs. Roadmap

| Capability / Subsystem | Phase | Status | Verification Reference |
| :--- | :--- | :--- | :--- |
| **Tool Introspection & Discovery** | Phase 1 | `[COMPLETED]` | Scans native + dynamic tools; provides full schemas |
| **Multi-Step DAG Pipeline Planner** | Phase 1 | `[COMPLETED]` | Heuristic and LLM decomposition with dependency graph |
| **Concurrent Step Execution** | Phase 1 | `[COMPLETED]` | Independent steps run in parallel via `asyncio.gather` |
| **Dynamic Variable Piping** | Phase 1 | `[COMPLETED]` | `{{steps.<id>.output.<field>}}` resolved at runtime |
| **Dynamic Tool Synthesis & Sandbox** | Phase 1 | `[COMPLETED]` | AST security gate + isolated sandbox + disk save |
| **Jarvis-Like Failure Awareness** | Phase 1 | `[COMPLETED]` | Diagnoses root causes, suggests fixes, auto-retries |
| **Multi-Sink Logging** | Phase 1 | `[COMPLETED]` | Console + `core_ai.log` + `pipelines.jsonl` + SQLite |
| **In-Memory Bus Fallback** | Phase 1 | `[COMPLETED]` | Zero-setup testing without requiring external Redis |
| **Universal Edge Gateway** | Phase 2 | `[COMPLETED]` | FastAPI REST + WebSockets (`/ws/events`, `/ws/logs`) |
| **Proactive Reasoning Daemon** | Phase 2 | `[COMPLETED]` | Autonomous background condition-action evaluation |
| **Personal Identity Memory** | Phase 2 | `[COMPLETED]` | Dynamic operator profile in SQLite (`user_profiles`) |
| **Dynamic Spatial Zones & Security**| Phase 2 | `[COMPLETED]` | Dynamic zone creation, `OWNER`/`AMBIENT`/`GUEST` tiers |
| **1-Line Zero-Friction Enrollment** | Phase 2 | `[COMPLETED]` | `interfaces/install/enroll.py` automated token onboarding |
| **Ambient HUD Card Protocol** | Phase 2 | `[COMPLETED]` | Generic WebSocket HUD payload dispatch to any connected display |
| **Dynamic Spatial Audio Router** | Phase 3 | `[COMPLETED]` | `engines/audio_router.py` introspects soundcards dynamically |
| **Cross-Zone Spatial Handoff** | Phase 3 | `[COMPLETED]` | `brain/spatial_handoff.py` auto-relocates audio and context |
| **Dynamic Hardware / UI Synthesis** | Phase 3 | `[COMPLETED]` | On-demand UI generation & community plugin architecture |
| **Dynamic Model & Provider Router** | Core | `[COMPLETED]` | `brain/model_router.py` persistent roles & prompt overrides |
| **Intercontinental Sovereign Mesh** | Core | `[COMPLETED]` | `core/mesh_client.py` offline fallback & machine migration |
| **Automated Test Suite** | All | `[COMPLETED]` | **56/56 tests passing 100% green** (`pytest tests`) |
| **Mobile Companion & Nothing OS** | Phase 4 | `[ACTIVE]` | WebSocket client, rear Glyph Matrix LED driver, BLE bridge |
| **Automotive & Bicycle SBC Unit** | Phase 5 | `[QUEUED]` | CAN-bus / OBD-II integration, bicycle computer bridge |
| **Smart Glasses AR & Spatial Cam** | Phase 6 | `[QUEUED]` | Micro HUD projection, bone conduction, FOV camera |

---

## Problem Logging & Technical Debt Ledger

To ensure issues and edge-cases are **never lost** over this multi-year initiative, all bugs, limitations, and architectural debts are logged in:

**[docs/PROBLEMS_AND_DEBT.md](file:///g:/VSC_Projects/Core%20AI/docs/PROBLEMS_AND_DEBT.md)**

Whenever you discover a bug or limitation, record:
1. Issue ID & Component.
2. Symptom & Stacktrace.
3. Root Cause Analysis.
4. Resolution or Planned Architectural Fix.
5. Status Tag (`[OPEN]`, `[RESOLVED]`, `[WATCHLIST]`).

---

## Getting Started & Sovereign Usage

Core AI offers **two official paths**:
1. **Sovereign One-Line Terminal Setup** (for operators deploying on their primary workstation, server, or mini-PC).
2. **Developer Mode in IDE** (for contributors engineering the microkernel and DAG pipeline).

In both workflows, Core AI operates as a **Unified Sovereign Terminal**: running the kernel boots the background Universal Gateway (port 8000) for your smart mirror, mobile device, and edge nodes, plays a sleek ASCII boot sequence, and hosts the interactive command terminal in the very same window.

---

### Path A: Sovereign One-Line Bootstrap (Recommended)

Run a single command in your terminal. It checks Python and Git, clones the repository, provisions an isolated virtual environment, installs dependencies, runs the interactive setup wizard, and drops straight into the Core AI Terminal:

#### Windows (PowerShell)
```powershell
irm https://raw.githubusercontent.com/Dyvorn/Core-AI/master/install.ps1 | iex
```

#### Linux / macOS (Bash)
```bash
curl -fsSL https://raw.githubusercontent.com/Dyvorn/Core-AI/master/install.sh | bash
```

During the 30-second setup, the terminal will ask:
- **Operator Handle**: Your preferred name or call sign (e.g. `Dyvorn`).
- **Primary Space**: Your starting spatial zone (e.g. `studio`, `lab`, `workshop`).
- **Desktop Launcher**: Place a 1-click `CoreAI.bat` launcher on your Desktop (`[Y/n]`).
- **Autostart on Boot**: Automatically boot Core AI on system startup (`[Y/n]`).
- **Auto-Update Guard**: Verify GitHub updates with automated test guards on launch (`[Y/n]`).

Once answered, Core AI boots immediately.

---

### Path B: Developer Mode (In Your IDE)

For developers hacking on Core AI in VS Code, Cursor, or your preferred IDE:

```bash
# 1. Clone repository
git clone https://github.com/Dyvorn/Core-AI.git
cd Core-AI

# 2. Set up virtual environment
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run automated test suite
pytest tests

# 5. Launch Unified Core AI Terminal
python main.py
```

> [!NOTE]
> Running `python main.py` runs the Universal Gateway in the background on `http://localhost:8000` while providing you the interactive command shell in your IDE terminal.
> If deploying in a headless container or systemd service, pass `--headless` or `--server-only`.

---

### Unified Core Terminal Commands

Inside the terminal shell (`Core [Operator@zone] > `), type any natural language goal directly, or execute built-in commands:

| Command | Action |
| :--- | :--- |
| `solve <goal>` | Synthesize and execute concurrent DAG pipeline (or type goal directly) |
| `speak <text>` | Synthesize neural speech through current zone's speakers |
| `spoken <text>` | Run Spoken-To Reasoning classification (detects showcase vs command) |
| `voice on / off` | Toggle background continuous microphone listening (faster-whisper) |
| `audio` | Introspect physical microphones, studio audio interfaces & active routes |
| `handoff <zone>` | Shift spatial anchor to target zone & dynamically switch audio routing |
| `status` | Inspect microkernel health, platform architecture & model assignments |
| `profile` | View or update operator identity, preferred aliases, and tone |
| `zones` | List all dynamically registered spatial zones (zero hardcoding) |
| `zone add <id> [name]` | Register a new physical space on-the-fly |
| `devices` | Inspect connected edge devices, trust tiers & roaming anchors |
| `tools` | Inspect all loaded tools (native tools + dynamic synthesized tools) |
| `models` | Inspect configured AI providers (Gemini, OpenAI, Anthropic, local) |
| `model set <role> <model>` | Assign model to role (`planner`, `fallback`, `deep_reasoning`) |
| `api-key set <prov> <key>` | Set API key persistently in `config/.env` |
| `mesh` | Inspect intercontinental mesh status, node role & reachability |
| `mesh role <main\|edge>` | Toggle between central main server and local offline edge node |
| `mesh connect <url>` | Pair edge node to central server URL |
| `mesh export / import` | Export or restore full SQLite state bundle for zero-downtime machine migration |
| `hud <title> \| <body>` | Dispatch ambient HUD card to smart mirror / wall projection |
| `logs [count]` | View recent execution audit logs stored in SQLite |
| `proactive` | Trigger proactive state evaluation cycle on demand |
| `harness / eval` | Run live reasoning & execution harness diagnostic across all subsystems |
| `clear` | Clear terminal screen |
| `exit / quit` | Cleanly terminate all background servers, audio threads, and bus |

---

### 1-Click Desktop Launcher & CLI (`core.bat` / `core.sh`)

Whenever you want to start, stop, or manage Core AI:

- **Desktop**: Double-click `CoreAI.bat` on your Desktop to open the Sovereign Terminal.
- **Terminal CLI**:
  ```bash
  # Windows
  .\core.bat             # Launch Unified Terminal & Gateway Server
  .\core.bat setup       # Re-run interactive bootstrap wizard
  .\core.bat status      # Inspect process PID, memory usage, and health
  .\core.bat stop        # Stop server suite and free GPU / RAM (for video editing)
  .\core.bat update      # Update from GitHub with automated test guard
  .\core.bat test        # Run pytest test suite (68+ tests)
  .\core.bat uninstall   # Clean zero-residue uninstallation

  # Linux / macOS
  ./core.sh              # Launch Unified Terminal & Gateway Server
  ./core.sh setup
  ./core.sh status
  ./core.sh stop
  ./core.sh update
  ./core.sh test
  ./core.sh uninstall
  ```

---

### Connecting Additional Edge Devices

Once your Main Server is running, onboard other devices around your home or workspace:

- **Laptops, SBCs & Raspberry Pi Nodes**:
  Pair any edge machine into the mesh in one command:
  ```bash
  python -m interfaces.install.enroll --server http://<core-ip>:8000 --device-name "Laptop-01" --device-type laptop --zone "workspace" --secret core_sovereign_secret
  ```
- **Custom Hardware & Peripherals (Smart Glasses, Smart Mirrors, Bike Computers, SBCs)**:
  Any device connects over the high-speed WebSocket stream (`ws://<core-ip>:8000/ws/events`). Core AI's dynamic synthesis engine inspects the device's display resolution, sensors, and file system, and autonomously generates custom UIs, widgets, or telemetry streams on-demand without hardcoded bloat.
- **REST APIs & WebSockets**:
  - Swagger REST API Docs: `http://localhost:8000/docs`
  - Real-Time Event Stream: `ws://localhost:8000/ws/events`
  - Real-Time Audit Log Stream: `ws://localhost:8000/ws/logs`

---

### Zero-Residue Clean Uninstallation

If you ever want to completely remove Core AI from your machine:
```bash
# Windows
.\core.bat uninstall

# Linux / macOS
./core.sh uninstall
```
Stops running processes, removes autostart entries and desktop shortcuts, offers an optional state backup, and cleanly purges all runtime databases and logs.

---

*Core AI is open-source software licensed under the [GNU Affero General Public License v3.0](LICENSE).*

