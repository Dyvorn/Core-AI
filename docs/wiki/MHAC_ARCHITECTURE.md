# Multiple Hardware-Aware Computing (MHAC)

```text
========================================================================================
[ SUBSYSTEM: MHAC ]   [ CAPABILITY & CONTEXT BROKER ]   [ MESH INFERENCE DELEGATION ]
[ ARCHITECTURE: DECOUPLED INTELLIGENCE ]                [ STATUS: PRODUCTION v0.2.3 ]
========================================================================================
```

## 1. Executive Summary

**Multiple Hardware-Aware Computing (MHAC)** is an opportunistic compute-delegation framework engineered for local, multi-device sovereign mesh environments.

In standard local AI architectures, connecting client devices (e.g. desktop PCs, laptops, tablets, smartphones) are treated as passive display terminals that offload all inference to a centralized server. However, homelab servers often run on low-power, energy-efficient hardware (e.g., a quiet 2-core laptop with 18GB RAM and no dedicated GPU), while client workstations connect with powerful hardware (e.g., an 8-core desktop with 32GB RAM and an NVIDIA RTX 4080 with 16GB VRAM).

MHAC flips this paradigm:
* The central server (`core`) operates as an intelligent **Capability & Context Broker**.
* It dynamically measures the compute signature of connecting clients.
* If a client out-competes the central server, `core` negotiates model placement and delegates token generation to the client's local inference engine (e.g., Ollama on port `11434`).
* **Decoupled Intelligence**: All conversation history, SQLite WAL state, proactive daemons, long-term memory, and tool execution remain strictly centralized on `core`. The client operates as a stateless acceleration worker.

---

## 2. Dynamic Hardware Scoring Matrix

When a device connects to `core`, it provides or is probed for a `ClientComputeSignature`. The broker calculates a normalized **Compute Score**:

$$\text{ComputeScore} = (\text{CPU Cores} \times 1.0) + (\text{RAM GB} \times 0.5) + (\text{Has GPU} \times 50.0) + (\text{VRAM GB} \times 5.0)$$

### Reference Hardware Scores

| Device Profile | Specs | Calculation | Score | Routing Tier |
| :--- | :--- | :--- | :--- | :--- |
| **Central Host Laptop (`core`)** | 2 Cores, 16GB RAM, Integrated GPU | $(2 \times 1.0) + (16 \times 0.5) + 0 + 0$ | **10.0** | Central Orchestrator / Host Fallback |
| **Client Phone / Tablet** | 4 Cores, 4GB RAM, Mobile SoC | $(4 \times 1.0) + (4 \times 0.5) + 0 + 0$ | **6.0** | Standalone Display (Host runs inference) |
| **Client Workstation PC** | 8 Cores, 32GB RAM, RTX 4080 (16GB VRAM) | $(8 \times 1.0) + (32 \times 0.5) + 50.0 + (16 \times 5.0)$ | **154.0** | **Accelerated Workstation (Offload)** |
| **Client Extreme Workstation** | 16 Cores, 64GB RAM, RTX 4090 (24GB VRAM) | $(16 \times 1.0) + (64 \times 0.5) + 50.0 + (24 \times 5.0)$ | **218.0** | **Accelerated Workstation (Offload)** |

When $\text{ComputeScore}_{\text{client}} > \text{ComputeScore}_{\text{host}}$, the host immediately initiates the **Model Verification & Placement Handshake**.

---

## 3. Handshake & Negotiation Flow

```
[ Client Workstation PC ]                               [ Central Host: "core" ]
           │                                                        │
           │─── 1. Connect / Client-Hello ─────────────────────────>│
           │    (Signature: RTX 4080, 16GB VRAM, :11434)            │
           │                                                        │
           │<── 2. Capability Evaluation Notice ───────────────────│
           │    "Higher-tier compute detected on Workstation.       │
           │     Verifying local model inventory..."                │
           │                                                        │
           │<── 3. Model Inventory Probe ───────────────────────────│
           │    (GET http://192.168.1.150:11434/api/tags)           │
           │                                                        │
           │─── 4. Model Inventory Payload ────────────────────────>│
           │    [llama3.1:8b present / missing]                     │
           │                                                        │
┌──────────┴────────────────────────────────────────────────────────┴─────────┐
│ Dynamic Routing Execution:                                                │
│ IF llama3.1:8b present  -> Offload execution layer to client GPU          │
│ IF llama3.1:8b missing  -> Prompt operator to pull / Fallback to host CPU │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 4. System Behavior Modes

### Mode A: Accelerated Workstation Mode
* **Condition**: Client Compute Score exceeds Host, and preferred model (`llama3.1:8b`) is installed on client.
* **Routing**: `ModelRouter` binds the active Ollama API base to the client's endpoint (`http://<client-ip>:11434`).
* **Operator Notice**:
  > *"Higher-tier compute detected on your workstation [RTX 4080 (16.0GB VRAM)]. Offloading execution layer to local GPU using 'llama3.1:8b'."*
* **Outcome**: Blazing-fast inference utilizing the workstation's GPU, with zero token degradation and zero server overload.

### Mode B: Missing Model Handshake Mode
* **Condition**: Client Compute Score exceeds Host, but target model (`llama3.1:8b`) is not installed on client's Ollama instance.
* **Routing**: System gracefully defaults to Host CPU without dropping the user's prompt.
* **Operator Notice**:
  > *"I can run this significantly faster on your machine (Dev Workstation), but 'llama3.1:8b' is not installed on this device. Would you like me to pull it, or should I fallback to my internal processor?"*
* **Remediation**: Operator can trigger model installation with a single click or command via `POST /api/v1/mhac/pull`.

### Mode C: Standalone / Host Mode
* **Condition**: No high-spec clients connected, or connecting clients are low-power devices (smartphones, IoT glasses).
* **Routing**: `core` runs self-contained on its internal processor (`llama3.2:1b` or offline DAG heuristics).
* **Operator Notice**:
  > *"Client compute (6.0) does not exceed host (10.0). Running self-contained on host internal processor."*

---

## 5. Centralized State vs. Distributed Inference

Core AI guarantees strict architectural decoupling:

```
┌──────────────────────────────────────────────────────────────┐
│ CENTRAL SERVER ("core")                                      │
│  - SQLite WAL Database (State, History, Profiles)            │
│  - Proactive Anticipatory Engine (Calendar, Prep Buffers)    │
│  - Native Tool Registry (Filesystem, Shell, Network, OS)     │
│  - DAG Planning & Validation Pipeline                        │
│  - EventBus & Universal Gateway                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
            System Context &   │   Token Stream &
            Task Prompt        │   Next-Token Generation
                               │
┌──────────────────────────────▼───────────────────────────────┐
│ DELEGATED CLIENT WORKER (e.g. RTX Workstation)               │
│  - Stateless Ollama Endpoint (:11434)                        │
│  - High-Speed Local VRAM Matrix Multiplication               │
│  - Zero Local State / Zero Long-Term Storage                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 6. Gateway REST API Reference

All MHAC operations are exposed through clean, non-blocking asynchronous endpoints:

### `POST /api/v1/mhac/handshake`
Evaluates a client compute signature and preferred models. Returns capability response and broadcasts notification over the mesh.

**Request Payload**:
```json
{
  "client_signature": {
    "node_id": "workstation-alpha",
    "device_name": "Dev Workstation RTX",
    "device_type": "workstation",
    "cpu_cores": 8,
    "ram_total_gb": 32.0,
    "has_gpu": true,
    "gpu_name": "NVIDIA GeForce RTX 4080",
    "vram_gb": 16.0,
    "ollama_endpoint": "http://192.168.1.150:11434"
  },
  "preferred_models": ["llama3.1:8b", "llama3.2:3b"]
}
```

### `GET /api/v1/mhac/status`
Returns full telemetry on host score, connected clients, active compute node, and active model.

### `POST /api/v1/mhac/probe`
Probes a target Ollama instance and returns all installed model tags.
```json
{
  "endpoint": "http://192.168.1.150:11434",
  "timeout": 2.0
}
```

### `POST /api/v1/mhac/pull`
Instructs client's Ollama instance to pull a missing model in the background.
```json
{
  "endpoint": "http://192.168.1.150:11434",
  "model_name": "llama3.1:8b"
}
```

### `POST /api/v1/mhac/reset`
Instantly resets compute delegation back to the central host processor.

---

## 7. Concurrency & Non-Blocking Design

In alignment with Core AI's voice responsiveness directives:
* All HTTP probes and network handshakes are executed via `asyncio.to_thread` or non-blocking HTTP clients.
* Proactive background agents, health monitors, and calendar reconcilers run concurrently on separate asynchronous threads.
* Foreground voice conversation with Core AI remains instant and uninterrupted while background compute negotiation takes place.

---

## 8. Asymmetric Workload Matrix (Server vs. PC)

To optimize hardware resources without sacrificing real-time conversational snappiness, Core AI partitions compute dynamically into asymmetric workload tiers:

| Tier | Host Node | Workload Type | Responsibilities | Latency Profile |
| :--- | :--- | :--- | :--- | :--- |
| **Sovereign Backbone** | **Central Server (`core`)** | Background / Persistent | • 24/7 Proactive Watcher Daemon<br>• Context Sentinel (Track 2 Workspace/Git Scan)<br>• SQLite WAL State & Memory Persistence<br>• Track 3 Background Daemons & Watchdogs<br>• Embedding & Historical Note Consolidation<br>• Offline Heuristic DAG Fallback | Non-critical background (1s – 60s) |
| **High-Compute Tier** | **Operator Workstation (PC / GPU)** | Urgent / Interactive | • Track 1 Foreground Spoken-To (<50ms)<br>• Interactive LLM DAG Planning & Reasoning<br>• Emergent Dynamic Code Synthesis<br>• Heavy Vision / Multimodal Generation | Low latency (<50ms – 1.5s) |

```
┌────────────────────────────────────────────────────────┐
│ CENTRAL SERVER ("core")                                │
│  • Proactive Daemon (watches calendar, notes, vitals)  │
│  • Track 2 Context Sentinel (workspace awareness)      │
│  • SQLite WAL State & Audit Logs                       │
│  • Track 3 Daemons (Heartbeat, consolidation)          │
└───────────────────────────┬────────────────────────────┘
                            │
               Continuous   │  Dynamic
               Background   │  Foreground
               Coordination │  Inference
                            │
┌───────────────────────────▼────────────────────────────┐
│ OPERATOR WORKSTATION PC (RTX GPU / VRAM)               │
│  • High-Speed Interactive LLM Inference                │
│  • Foreground Spoken-To (<50ms fastpath)               │
│  • Heavy Multi-Step DAG Planning                       │
└────────────────────────────────────────────────────────┘
```

---

## 9. Seamless Zero-Downtime Transition & Auto-Recovery

If the operator's PC goes to sleep, shuts down, or disconnects from the LAN, Core AI maintains 100% operational continuity:

1. **Continuous Liveness Heartbeat (Track 3)**:
   A dedicated daemon (`mhac_liveness_heartbeat`) runs every 15s in the background on the central server, performing a lightweight probe to the PC's Ollama port.
2. **Graceful Failover to Host**:
   If the PC fails to respond within 500ms, the broker preserves the PC's configuration in `_dormant_clients`, resets active delegation to `"host"`, and routes ongoing interactive requests to the server's internal model or instant deterministic DAG without raising errors or dropping user prompts.
3. **Automatic Reconnection & Recovery**:
   When the workstation wakes up and responds to probes, the server automatically renegotiates model placement and seamlessly restores accelerated GPU offload.
4. **Operator CLI Controls**:
   - `mhac` or `compute`: Displays live Asymmetric Computing Matrix and workload distribution.
   - `connect-pc <endpoint>`: Directly pairs an external workstation (e.g. `connect-pc 192.168.1.150:11434`).
   - `mhac heartbeat`: Manually triggers liveness evaluation and state transition reconciliation.
   - `mhac reset`: Reverts compute delegation back to central host.

