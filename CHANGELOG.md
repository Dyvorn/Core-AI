# Changelog

All notable changes to **Core AI** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> [!TIP]
> For the complete visual release overview, architecture diagrams, and the sovereign manifesto, see [RELEASE_NOTES.md](RELEASE_NOTES.md).

---

## [[0.1.0-alpha]](https://github.com/Dyvorn/Core-AI/releases/tag/v0.1.0-alpha) — 2026-10-04
### Codename: "Genesis"

```text
[ VERSION: v0.1.0-alpha ]  [ TESTS: 87/87 PASSED (100%) ]  [ ETHOS: #ANTISLOP ]
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
