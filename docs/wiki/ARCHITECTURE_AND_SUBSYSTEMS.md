# Core AI — System Architecture & Subsystems Dossier

```text
========================================================================================
[ SUBSYSTEM: ARCHITECTURE ]   [ PATTERN: MICROKERNEL + ASYNC DAG ] [ VERSION: v0.2.3 ]
[ STATE: SQLITE WAL ]         [ IPC: REST / WEBSOCKET ]             [ LICENSE: AGPL-3.0-ONLY ]
========================================================================================
```

## 1. High-Level Architectural Anatomy

Core AI is structured as an **asynchronous microkernel** surrounded by decoupled engine satellites and dynamic interfaces. It rejects monolithic bloat and enforces clean boundaries between persistent state, dynamic reasoning, and hardware actuation.

```text
                                  +-----------------------------+
                                  |     OPERATOR INTERFACES     |
                                  |  Terminal REPL | Fast CLI   |
                                  |  Voice Loop    | Mobile App |
                                  |  Spatial Mirror Kiosk       |
                                  +--------------+--------------+
                                                 |
                                     (REST / WebSockets / CLI)
                                                 v
+-----------------------------------------------------------------------------------------------+
|                                      CORE MICROKERNEL                                         |
|                                                                                               |
|  +--------------------+    +----------------------+    +-----------------------------------+  |
|  |     EventBus       |    |     StateManager     |    |         ProactiveDaemon           |  |
|  | In-Memory Pub/Sub  |    | SQLite WAL (30s Lock)|    | Anticipation, Prep Buffers, Vitals|  |
|  +---------+----------+    +----------+-----------+    +-----------------+-----------------+  |
|            |                          |                                  |                    |
|            +--------------------------+----------------------------------+                    |
|                                       v                                                       |
|                        +------------------------------+                                       |
|                        |        Planner Engine        |                                       |
|                        | Fast-Path Heuristic / LiteLLM|                                       |
|                        +--------------+---------------+                                       |
|                                       v                                                       |
|                        +------------------------------+                                       |
|                        |     Async DAG Pipeline       |                                       |
|                        | Concurrent Step Scheduling   |                                       |
|                        +--------------+---------------+                                       |
|                                       v                                                       |
|  +------------------------------------+----------------------------------------------------+  |
|  |                                    ToolRegistry                                         |  |
|  |   Native Tools (System, Dev, Notes, Calendar, Proactive, Files, Math, Desktop, OS)      |  |
|  |   Dynamic Tools (AST Sandbox Verified, Hot-Reloaded from tools/dynamic/)                |  |
|  |   Remote Dispatcher (Proxied over WebSockets to Cars, Edge Satellites, Mobile)          |  |
|  +-----------------------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------------------+
                                                 ^
                                                 | (Bidirectional JSON-RPC / LAN Discovery)
                                  +--------------+--------------+
                                  |    DISTRIBUTED SATELLITES   |
                                  |  Living Room Voice Satellite|
                                  |  Mobile Companion Edge Node |
                                  |  Vehicle / Automotive SBC   |
                                  +-----------------------------+
```

---

## 2. Deep Dive: Core Subsystems

### 2.1 StateManager (`core/state.py`)
- **Engine**: SQLite 3 operating in **Write-Ahead Logging (WAL)** mode.
- **Concurrency & Non-Locking**:
  - `PRAGMA journal_mode = WAL`: Readers never block writers; writers never block readers.
  - `PRAGMA synchronous = NORMAL`: Balances ACID persistence with maximum throughput.
  - `PRAGMA busy_timeout = 30000`: Built-in 30-second backoff defense eliminating `OperationalError: database is locked`.
  - Sequential, forward-only migrations tracked by `PRAGMA user_version`.
- **Key Tables**:
  - `pipelines` & `pipeline_steps`: Complete historical DAG execution logs.
  - `kv_state`: Dynamic key-value store with prefix queries (notes, user preferences).
  - `calendar_events`: Scheduled appointments, prep buffer metadata, notification flags.
  - `proactive_rules`: Persistent watcher triggers and countdown timers.
  - `device_topology` & `zones`: Physical spatial anchor catalog.
  - `audio_routes`: Dynamic soundcard and microphone bindings per room.
  - `mesh_offline_queue`: Offline task buffering for roaming nodes.

### 2.2 EventBus (`core/bus.py`)
- **Transport**: In-memory asynchronous pub/sub default, falling back to external Redis if configured.
- **Zero-Latency Inversion**: Immediately initializes in-memory transport without probing non-existent Redis hosts on Windows IPv6 loopback, saving 3.14 seconds on boot.
- **Core Channels**:
  - `command_events`: Incoming operator requests.
  - `tts_events`: Outgoing speech requests.
  - `hud_events`: Ambient HUD card broadcasts.
  - `state_events`: Synchronization signals across the mesh.

### 2.3 Spoken-To Pragmatics Discourse Engine (`brain/spoken_to.py`)
Distinguishes between direct human-to-AI directives and ambient room noise without requiring rigid wake words:
1. `ADDRESSED`: Direct instructions intended for Core AI $\to$ processed immediately.
2. `DEMONSTRATED`: Charismatic live demonstrations $\to$ acknowledged verbally.
3. `REFERENCED`: Operator speaking about Core AI in the third person $\to$ remains completely silent.
4. `BYSTANDER`: Background chatter, phone conversations, TV audio $\to$ discarded.

### 2.4 Async DAG Pipeline Engine (`brain/pipeline_engine.py`)
- Schedules execution steps as a Directed Acyclic Graph.
- Independent steps execute concurrently in parallel (`asyncio.gather`).
- Variable cascading resolves dynamic parameter references (`{{steps.scan_lan.output.devices.[0].ip}}`).
- Robust failure handling diagnoses tool failures and provides corrective diagnostics.

### 2.5 Dynamic Tool Generator & AST Sandbox (`brain/dynamic_generator.py`)
- Synthesizes Python tool modules on-the-fly when operators request novel capabilities.
- Enforces an Abstract Syntax Tree (AST) security barrier: forbids `subprocess`, `ctypes`, and unauthorized low-level OS calls.
- Persists valid code to `tools/dynamic/` and hot-reloads dynamically into `ToolRegistry` with zero server restart.

### 2.6 Sovereign Intercontinental Mesh & Mobile Companion (`core/mesh_client.py`)
- Distinguishes the **Central Host** (24/7 home server) from **Roaming Edge Nodes** (laptops, phones, vehicles).
- Connects securely across Tailscale or WebSockets.
- If connectivity drops, edge nodes switch instantly to Local Autonomous Mode and queue actions in SQLite `mesh_offline_queue` for later bidirectional replay.
