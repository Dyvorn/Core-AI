# Intercontinental Sovereign Mesh & Machine Migration

```text
[ SYSTEM: CORE-AI-MESH ]   [ TRANSPORT: TAILSCALE / WS / REST ] [ SOVEREIGNTY: 100% ]
[ TOPOLOGY: CENTRAL+EDGE ] [ OFFLINE-FALLBACK: ZERO-LOCKOUT ]   [ PHILOSOPHY: #ANTISLOP ]
```

> **Core AI is designed to operate seamlessly across the planet. A central sovereign host runs 24/7 at your home base, while roaming companion nodes (laptops, phones, vehicles) connect from anywhere in the world. If connection to the central server is lost, the device never bricks -- it switches instantly to Local Autonomous Mode.**

---

## Table of Contents

- [The Intercontinental Vision](#the-intercontinental-vision)
- [Node Roles: Central Host vs. Roaming Edge](#node-roles-central-host-vs-roaming-edge)
- [Remote Operations Across the Planet](#remote-operations-across-the-planet)
- [Autonomous Local Fallback (Never a Brick)](#autonomous-local-fallback-never-a-brick)
- [Machine Migration & State Bundles](#machine-migration--state-bundles)
- [Harm-Free Unstoppable Agency Principle](#harm-free-unstoppable-agency-principle)
- [Console Commands & Setup](#console-commands--setup)

---

## The Intercontinental Vision

Core AI bridges the gap between your physical home environment and your life on the move:
1. **Central 24/7 Sovereign Server**: A primary workstation, home server, or homelab machine that stays online, connected to local smart appliances, soundcards, and sensor networks.
2. **Encrypted Private Mesh**: Roaming nodes connect back to the central host using encrypted WireGuard / Tailscale tunnels or secure WebSocket gateways with token authentication.
3. **True Local Sovereignty**: No proprietary big-tech cloud relay, no third-party data harvesting, and no subscription paywalls.

---

## Node Roles: Central Host vs. Roaming Edge

Every Core AI instance operates in one of two distinct roles:

```text
+-----------------------------------------------------------------------------+
| CENTRAL SOVEREIGN HOST (role: main_server)                                  |
| - Runs 24/7 at home base (workstation, server, or unRAID/TrueNAS).         |
| - Connects directly to Home Assistant, local audio interfaces, mirror HUDs. |
| - Holds master SQLite database, execution audit trails, and dynamic tools.  |
+-----------------------------------------------------------------------------+
                                       ^
                                       | Encrypted WAN (Tailscale WireGuard)
                                       v
+-----------------------------------------------------------------------------+
| ROAMING COMPANION NODE (role: edge_node)                                    |
| - Laptop, Android smartphone (Nothing OS), vehicle SBC, or smart glasses.   |
| - Dispatches commands back to central host when connected.                  |
| - Operates autonomously on local silicon when disconnected.                 |
+-----------------------------------------------------------------------------+
```

---

## Remote Operations Across the Planet

When travelling across cities or continents, your roaming device connects back to the Central Sovereign Host over Tailscale:

```text
[Operator in Tokyo on Phone] 
       | 
       | "Core, start the washing machine and check workshop temperatures"
       v
[FastAPI Gateway via Tailscale Mesh] 
       | 
       v
[Central Sovereign Server in Berlin / Home Base]
       |
       +---> [Home Assistant API: Start Washing Machine]
       +---> [Workshop Sensor Bridge: Read Temp 21.4C]
       +---> [Mirror HUD: Dispatch Status Card]
       v
[Response Streamed Back to Phone]: "Washing machine started. Workshop is at 21.4C."
```

If a physical action belongs to your home, Core AI routes the tool execution to the Central Host transparently.

---

## Autonomous Local Fallback (Never a Brick)

What happens if your phone or laptop is on an airplane, in a rural area without cellular signal, or your home server has a temporary power outage?

**Core AI never fails silently, never crashes, and never locks you out:**

1. **Automatic Health Probe**: Before dispatching remote tasks, the node checks `GET /api/v1/health` with a low-latency 1.5s timeout.
2. **Transparent Fallback Notice**: If the central host is unreachable, Core AI issues a clear diagnostic notice:
   ```text
   [!] Notice: Main Core Server at 'http://100.64.0.1:8000' is unreachable.
       Operating in Local Autonomous Mode.
   ```
3. **Local Silicon Execution**: The goal is immediately routed to the device's local microkernel, local tools, and local models (Ollama or deterministic heuristics).
4. **Offline Sync Buffer**: The executed task is logged in an offline sync queue (`offline_buffer`) so history reconciles when connection to home base is restored.

---

## Machine Migration & State Bundles

An operator must never be trapped on a single machine. If you purchase a new primary workstation or want to migrate your Central Server to a dedicated server, Core AI provides turnkey state portability.

### 1. Export State on Source Machine
```text
>>> mesh export my_core_backup.json
[OK] System state bundle exported to 'my_core_backup.json' for machine migration.
```

The state bundle captures:
- Operator Identity & Preferences (`user_profiles`)
- Dynamic Spatial Zones (`zones`)
- Hardware Topology & Connected Devices (`device_topology`)
- Zone-to-Soundcard Audio Routes (`audio_routes`)
- Self-Synthesized Dynamic Tools (`dynamic_tools`)

### 2. Import State on Destination Machine
```text
>>> mesh import my_core_backup.json
[OK] State bundle restored: {'zones': 4, 'devices': 8, 'audio_routes': 3, 'dynamic_tools': 2}!
     Machine ready as Main Server.
```

Within seconds, the new machine becomes your fully configured Central Sovereign Host.

---

## Harm-Free Unstoppable Agency Principle

A defining cornerstone of Core AI is **Constructive Permissiveness**:

> *"When an operator wants to do something, as long as it is helpful and not harming anyone, Core AI will do it. It will find a way to do it."*

1. **Zero Corporate Slop & Zero Nanny-Rails**: Core AI rejects patronizing, lecturing refusal filters.
2. **Real Physical Safety**: Core AI protects against actual destructive harm (system file deletion, disk formatting, malicious exploits against third-party machines).
3. **Unstoppable Problem Solving**: If a tool is unavailable, Core AI synthesizes it. If a device is in another room, it hands off audio. If an action requires remote hardware, it bridges across the mesh.

---

## Console Commands & Setup

Inside `python interfaces/cli/core_console.py`:

| Command | Action |
| :--- | :--- |
| `mesh` | Inspect current node role, central server URL, connectivity, and offline buffer count. |
| `mesh role <main|edge>` | Switch node between `main_server` and `edge_node`. |
| `mesh connect <url>` | Set target Central Host URL (e.g. Tailscale IP `http://100.x.y.z:8000`). |
| `mesh export [path]` | Export portable state bundle for backup or server migration. |
| `mesh import <path>` | Import state bundle to restore or promote a new machine. |
