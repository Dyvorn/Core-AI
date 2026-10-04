# Changelog
All notable changes to **Core AI** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0-alpha] - 2026-10-04
### Codename: "Genesis"

The inaugural public alpha release of **C.O.R.E. AI** (**C**oncurrent **O**mnipresent **R**easoning **E**ngine) — a sovereign, privacy-first, self-hosted pervasive life operating system microkernel built to free personal technology from cloud lock-in, recurring rents, and corporate surveillance (#ANTISLOP).

### Added
- **Concurrent DAG Pipeline Engine (`brain/pipeline_engine.py`)**:
  - Autonomous multi-step problem decomposition and scheduling.
  - Parallel task execution ("multiple things at once") with dependency graphs.
  - Dynamic inter-step variable resolution (`{{steps.<step_id>.output.<key>}}`).
  - Jarvis-like runtime failure detection and dynamic re-planning.
- **Dynamic Tool Synthesis & AST Sandbox (`brain/dynamic_generator.py`)**:
  - Autonomous Python tool generation on capability gap detection.
  - Strict AST safety inspection blocking destructive operations (`subprocess`, `ctypes`, `shutil`).
  - Hot-reloading directly from `tools/dynamic/` with zero microkernel restarts.
- **Universal Edge Gateway (`core/gateway.py`)**:
  - High-concurrency FastAPI microservice binding on customizable ports.
  - Bidirectional WebSockets for real-time telemetry (`/ws/events`, `/ws/logs`, `/ws/nodes/{id}`).
  - Synchronous instant problem solver endpoint (`/api/v1/pipeline/solve_sync`).
  - Interactive OpenAPI Swagger documentation at `http://localhost:8000/docs`.
- **Spatial Audio Matrix & Cross-Zone Handoff (`engines/audio_router.py`, `brain/spatial_handoff.py`)**:
  - Dynamic hardware audio device introspection for microphones and multi-channel interfaces.
  - Zone-to-soundcard binding with automated spatial room relocation.
  - Cross-space audio transfer and ambient HUD card dispatching.
- **Neural Voice & Perception Loop (`engines/voice_in.py`, `engines/voice_out.py`)**:
  - Local neural speech-to-text (`faster-whisper` + `silero-vad`).
  - High-fidelity neural voice synthesis (`edge-tts` / `piper`).
  - Spoken-to reasoning (`brain/spoken_to.py`) to classify intentional user address vs. ambient discourse.
- **Multi-Provider Neural Model Router (`brain/model_router.py`)**:
  - Zero-hardcoding architecture routing tasks to Google Gemini, OpenAI, Anthropic, or local offline Ollama (`qwen3.5:2b`, `llama3.2:3b`).
  - Natural language runtime prompt overrides (`solve ... using ollama/llama3`).
  - Sub-second cached offline reachability checks to prevent network hangs.
- **Intercontinental Sovereign Mesh (`core/mesh_client.py`)**:
  - Role separation between Central Sovereign Host (`main_server`) and Roaming Edge Nodes (`edge_node`).
  - Transparent Tailscale WireGuard WAN routing.
  - Full machine migration via portable state bundles (`mesh export` and `mesh import`).
- **Resilient State Management & Evolutionary Migrations (`core/state.py`, `core/updater.py`)**:
  - SQLite WAL mode state database with `PRAGMA user_version` migrations.
  - Online hot backups via SQLite backup API (`core backup`).
  - Automated pre-update snapshots and test-guarded git rollbacks (`core update`).
- **24/7 Headless Daemon & Daily CLI (`core/service.py`, `core.bat`, `core.sh`)**:
  - Headless background service management (`core start`, `core stop`, `core restart`, `core status`).
  - Colorized terminal status cards reporting PID, Gateway health, active model, and operator identity.
  - One-shot sub-100ms CLI goal dispatching (`core "what time is it"`).
- **3D Holographic Terminal Visualizer (`core/animation.py`)**:
  - Real-time mathematical 3D rendering engine with floating-point Z-buffering in 2D terminal space.
  - 3 geometric models: Quantum Gyroscopic Core, 4D Hypercube (Tesseract), and Hexagonal Sovereign Monolith.
  - 5 TrueColor themes (Cyber Cyan, Sovereign Void, Matrix Emerald, Solar Flare, Hyper Steel).
  - Interactive keyboard controls (`[T]` themes, `[M]` models, `[WASD]` camera rotation, `[Space]` pause).
  - Cinematic boot spin-up animation with skip-on-keypress.
- **Harm-Free Unstoppable Agency (`brain/safety.py`)**:
  - Rejection of corporate refusal slop and patronizing lectures.
  - Defense gates strictly targeting true catastrophic destruction (disk wipes, fork bombs).
- **Verification**:
  - 84 automated unit and integration tests passing with 100% green status.
