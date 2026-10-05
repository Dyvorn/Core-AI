# 24/7 Sovereign Server Setup, Autostart & Local Ollama Guide

```text
[ SYSTEM: CORE-AI-SERVICE ]    [ PERSISTENCE: 24/7 AUTOSTART ] [ SUPERVISOR: SELF-HEALING WATCHDOG ]
[ ENGINE: OLLAMA / LOCAL LLM ] [ MESH: REST + WS ]             [ ETHOS: #ANTISLOP ]
```

> **Transform any machine—whether a dedicated desktop, homelab box, mini PC, or a Linux Fedora laptop staying at home—into a permanent, sovereign, 24/7 Core AI Main Server. Zero IDE required, zero corporate telemetry, and 100% self-hosted.**

---

## Table of Contents

- [Core Principles & Server Architecture](#core-principles--server-architecture)
- [1. Headless Server Setup (No IDE Needed)](#1-headless-server-setup-no-ide-needed)
  - [Windows Server / Windows Desktop](#a-windows-server--windows-desktop)
  - [Linux Server / Fedora / Ubuntu / Debian](#b-linux-server--fedora--ubuntu--debian)
- [2. Always-On 24/7 Autostart & Self-Healing Watchdog](#2-always-on-247-autostart--self-healing-watchdog)
  - [Windows Zero-Console Autostart](#windows-zero-console-autostart)
  - [Linux systemd 24/7 Service](#linux-systemd-247-service)
  - [How the Watchdog Daemon Protects Your Server](#how-the-watchdog-daemon-protects-your-server)
- [3. Special Guide: Using a Laptop as a 24/7 Home Server](#3-special-guide-using-a-laptop-as-a-247-home-server)
  - [Prevent Sleep on Lid Close (Fedora / Linux)](#prevent-sleep-on-lid-close-fedora--linux)
  - [Prevent Wi-Fi Power-Save Sleep](#prevent-wi-fi-power-save-sleep)
  - [Battery Care for 24/7 Wall Power](#battery-care-for-247-wall-power)
- [4. Local Ollama AI Setup & Model Roles](#4-local-ollama-ai-setup--model-roles)
  - [Installing Ollama](#installing-ollama)
  - [Pulling Recommended Models](#pulling-recommended-models)
  - [Binding Model Roles in Core AI](#binding-model-roles-in-core-ai)
  - [Exposing Ollama over LAN (Optional)](#exposing-ollama-over-lan-optional)
- [5. Connecting Roaming Clients (Laptops, PCs, Phones)](#5-connecting-roaming-clients-laptops-pcs-phones)
  - [Pairing via the Intercontinental Mesh](#pairing-via-the-intercontinental-mesh)
  - [Autonomous Local Fallback](#autonomous-local-fallback)
  - [Accessing via Web Browser & REST API](#accessing-via-web-browser--rest-api)
- [6. CLI Command Cheat Sheet](#6-cli-command-cheat-sheet)

---

## Core Principles & Server Architecture

```text
+---------------------------------------------------------------------------------+
|                         SOVEREIGN MAIN SERVER                                   |
|   (Always-On Desktop / Homelab Box / Fedora Home Laptop)                        |
|                                                                                 |
|   +-------------------------------------------------------------------------+   |
|   | 24/7 Self-Healing Watchdog Daemon (.venv/bin/python -m core.watchdog)   |   |
|   |  - Monitors PID, auto-revives crashed processes with backoff defense    |   |
|   +-------------------------------------------------------------------------+   |
|                                      |                                          |
|                                      v                                          |
|   +-------------------------------------------------------------------------+   |
|   | Core AI Microkernel (main.py --headless)                                |   |
|   |  - Universal Gateway: http://0.0.0.0:8000 (REST + WebSocket Mesh)       |   |
|   |  - SQLite WAL Database (core_ai.db)                                     |   |
|   |  - DAG Problem-Solving Engine & Dynamic Tool Registry                   |   |
|   +-------------------------------------------------------------------------+   |
|                                      |                                          |
|                                      v                                          |
|   +-------------------------------------------------------------------------+   |
|   | Local Ollama Instance (http://localhost:11434)                          |   |
|   |  - Models: llama3:latest, qwen2.5-coder, etc.                           |   |
|   +-------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------+
          ^                                                    ^
          | LAN / Wi-Fi                                        | Mesh / WAN
          v                                                    v
+-----------------------------+                    +------------------------------+
| Daily Driver PC (Windows)   |                    | Roaming Laptop / Phone       |
|  - Role: edge_node          |                    |  - Role: edge_node           |
|  - Offloads tasks to server |                    |  - Dispatches over network   |
|  - Local fallback if offline|                    |  - Local fallback if offline |
+-----------------------------+                    +------------------------------+
```

---

## 1. Headless Server Setup (No IDE Needed)

Core AI requires **no IDE** (no VS Code, PyCharm, or GUI tools). Everything runs directly through native shells (`cmd`, `PowerShell`, `bash`, or `SSH`).

### A. Windows Server / Windows Desktop

1. Open PowerShell or Command Prompt.
2. Navigate to your target directory and clone or copy the project:
   ```cmd
   git clone https://github.com/Dyvorn/Core-AI.git "C:\Core-AI"
   cd "C:\Core-AI"
   ```
3. Initialize the Python environment:
   ```cmd
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
   *(Or run `powershell -ExecutionPolicy Bypass -File .\install.ps1` for fully automated bootstrap).*

### B. Linux Server / Fedora / Ubuntu / Debian

1. Connect via SSH or open a terminal.
2. Clone the repository and install system dependencies:
   ```bash
   # Fedora / RHEL
   sudo dnf install -y python3 python3-pip git

   # Ubuntu / Debian
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
   ```
3. Clone and build the isolated virtual environment:
   ```bash
   git clone https://github.com/Dyvorn/Core-AI.git ~/Core-AI
   cd ~/Core-AI
   python3 -m venv .venv
   .venv/bin/pip install --upgrade pip
   .venv/bin/pip install -r requirements.txt
   chmod +x core.sh
   ```

---

## 2. Always-On 24/7 Autostart & Self-Healing Watchdog

### Windows Zero-Console Autostart

On Windows, Core AI uses `pythonw.exe` inside your user Startup folder (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CoreAI_Startup.bat`). This ensures **zero black console window flash** on startup or login.

1. **Enable silent 24/7 autostart**:
   ```cmd
   core autostart on
   ```
2. **Inspect autostart status**:
   ```cmd
   core autostart status
   ```
3. **Start the background service right now (no reboot needed)**:
   ```cmd
   core start
   ```
4. **Check live server card**:
   ```cmd
   core status
   ```
5. **Disable autostart anytime**:
   ```cmd
   core autostart off
   ```

---

### Linux systemd 24/7 Service

On Linux servers, `systemd` is the industry standard for production services that survive reboots and process crashes.

1. Inside your `Core-AI` directory, generate and install the systemd service:
   ```bash
   sudo tee /etc/systemd/system/core-ai.service > /dev/null <<EOF
   [Unit]
   Description=Core AI Sovereign 24/7 Server
   After=network.target

   [Service]
   Type=simple
   User=$(whoami)
   WorkingDirectory=$(pwd)
   ExecStart=$(pwd)/.venv/bin/python -m core.watchdog
   Restart=always
   RestartSec=5
   StandardOutput=append:$(pwd)/logs/server_stdout.log
   StandardError=append:$(pwd)/logs/server_stdout.log

   [Install]
   WantedBy=multi-user.target
   EOF
   ```

2. Reload and enable the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now core-ai
   ```

3. Check live service status:
   ```bash
   systemctl status core-ai
   ```

---

### How the Watchdog Daemon Protects Your Server

Process stability is critical when running local LLM inference, which can occasionally trigger Out-Of-Memory (OOM) errors.

The Core AI Watchdog (`core/watchdog.py`):
1. Runs independently from the microkernel process.
2. Detects unexpected process exits (`ret_code != 0`).
3. Automatically respawns Core AI with **exponential backoff defense** (prevents rapid crash-loops if configuration is broken).
4. Logs all supervisor events to `logs/watchdog.log` and microkernel tracebacks to `logs/server_stdout.log`.
5. **Clean Shutdown**: When you run `core stop`, it terminates the supervisor *first*, ensuring the watchdog won't fight you when you manually stop the service to free RAM/GPU.

---

## 3. Special Guide: Using a Laptop as a 24/7 Home Server

Using a laptop as a dedicated home server is cost-effective, energy-efficient, and comes with a built-in battery backup (UPS). However, laptops require special power configuration.

### Prevent Sleep on Lid Close (Fedora / Linux)

By default, Linux laptops suspend when the lid is closed. To keep Core AI running 24/7 with the lid closed:

1. Edit the `systemd-logind` configuration:
   ```bash
   sudo nano /etc/systemd/logind.conf
   ```
2. Locate or add the following directive:
   ```ini
   HandleLidSwitch=ignore
   HandleLidSwitchExternalPower=ignore
   HandleLidSwitchDocked=ignore
   ```
3. Save the file (`Ctrl+O`, `Enter`, `Ctrl+X`) and restart the login manager:
   ```bash
   sudo systemctl restart systemd-logind
   ```
Now you can close the laptop lid, plug it into wall power and Ethernet/Wi-Fi, and place it neatly on a shelf.

### Prevent Wi-Fi Power-Save Sleep

If your laptop connects via Wi-Fi rather than Ethernet, disable Wi-Fi power-saving mode so your connection does not drop during idle hours:

```bash
# Check current connection name
nmcli connection show

# Disable power saving on your active connection
sudo nmcli connection modify "<Your-WiFi-Name>" 802-11-wireless.powersave 2
```

### Battery Care for 24/7 Wall Power

If your laptop stays plugged in 24/7, set a battery charging threshold (e.g. 60–80%) to maximize lithium-ion lifespan:
- **Lenovo (ThinkPad/IdeaPad)**:
  ```bash
  sudo dnf install -y tlp
  sudo tlp start
  ```
- **ASUS (ROG/ZenBook)**:
  ```bash
  echo 60 | sudo tee /sys/class/power_supply/BAT0/charge_control_limit_max
  ```
- **Dell**: Configure battery charging threshold in UEFI/BIOS ("Primarily AC Use").

---

## 4. Local Ollama AI Setup & Model Roles

Core AI natively routes reasoning to local Ollama instances with **zero external cloud API costs and zero token data leakage**.

### Installing Ollama

- **Linux (Fedora / Ubuntu / Debian)**:
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```
- **Windows**:
  Download and run the installer from [ollama.com/download](https://ollama.com/download).

Verify Ollama is running:
```bash
ollama --version
curl http://localhost:11434/api/tags
```

### Pulling Recommended Models

Pull lightweight, high-performance models tailored to your hardware:

```bash
# High-quality general reasoning (Default recommendation)
ollama pull llama3:latest

# Coding & dynamic tool generation specialist
ollama pull qwen2.5-coder:7b

# Ultra-lightweight for low-RAM machines (16GB or less)
ollama pull llama3.2:3b
```

### Binding Model Roles in Core AI

Inspect all detected providers and Ollama models from inside Core AI:

```bash
# Windows
.\core.bat models

# Linux
./core.sh models
```

Assign models to specific reasoning roles:
```bash
# Windows
.\core.bat "model set planner ollama/llama3:latest"
.\core.bat "model set deep_reasoning ollama/qwen2.5-coder:7b"

# Linux
./core.sh "model set planner ollama/llama3:latest"
./core.sh "model set deep_reasoning ollama/qwen2.5-coder:7b"
```

### Exposing Ollama over LAN (Optional)

By default, Core AI acts as the secure gateway to Ollama on port `8000`. If you also want other machines on your local network to query the Ollama engine directly on port `11434`:

1. Edit the Ollama systemd service:
   ```bash
   sudo systemctl edit ollama.service
   ```
2. Add:
   ```ini
   [Service]
   Environment="OLLAMA_HOST=0.0.0.0:11434"
   ```
3. Restart Ollama:
   ```bash
   sudo systemctl restart ollama
   ```

---

## 5. Connecting Roaming Clients (Laptops, PCs, Phones)

Once your server is online, any machine on your network (or across the world via Tailscale) can pair into your sovereign mesh.

### Pairing via the Intercontinental Mesh

1. **Find your server's LAN IP**:
   - On Linux server: `ip a | grep inet`
   - On Windows server: `ipconfig`
   *(e.g., `192.168.1.120`)*

2. **On your daily client machine (e.g. Windows PC or roaming laptop)**:
   Launch the interactive terminal:
   ```bash
   # Windows
   .\core.bat

   # Linux
   ./core.sh
   ```

3. **Bind your client as an edge node**:
   ```text
   mesh role edge_node
   mesh connect http://192.168.1.120:8000
   mesh
   ```

You will see:
```text
--- Intercontinental Sovereign Mesh Status ---
  Node Role:        EDGE_NODE
  Main Server URL:  http://192.168.1.120:8000
  Server Status:    REACHABLE (Online)
  Offline Buffer:   0 items queued
```

Now, any goal you execute on your client:
```cmd
core "whats pulling most ram"
```
is dispatched across the network to your server, processed by the server's local Ollama and hardware, and returned to your screen seamlessly.

### Autonomous Local Fallback

If you disconnect from Wi-Fi or leave home with your laptop:
- Core AI detects the server is unreachable.
- It switches automatically to **Local Autonomous Mode**.
- It uses local Python tools and local lightweight models on your laptop's own CPU/GPU.
- **You are never locked out of your system.**

### Accessing via Web Browser & REST API

Your server exposes open, interactive REST and WebSocket endpoints:
- **Interactive Swagger Documentation**: `http://<SERVER-IP>:8000/docs`
- **System Health Probe**: `http://<SERVER-IP>:8000/api/v1/health`
- **Real-Time Event Stream**: `ws://<SERVER-IP>:8000/ws/events`
- **Audit Log Stream**: `ws://<SERVER-IP>:8000/ws/logs`

---

## 6. CLI Command Cheat Sheet

| Command | Purpose |
| :--- | :--- |
| `core autostart on` | Enable 24/7 background boot with self-healing Watchdog |
| `core autostart off` | Disable automatic boot |
| `core autostart status` | Inspect autostart status, path, and supervisor mode |
| `core autostart visible` | Enable visible terminal window on system boot |
| `core start` | Start detached background daemon immediately |
| `core stop` | Gracefully stop both Core AI server and Watchdog (frees GPU/RAM) |
| `core restart` | Hot restart the background microkernel |
| `core status` | View PID, gateway health, active operator, and connected nodes |
| `core models` | Inspect configured AI providers and installed Ollama models |
| `core watchdog` | Launch process supervisor in foreground |
| `core run` | Launch interactive terminal shell |
| `core "<goal>"` | Execute one-shot goal directly from terminal |
| `core update` | Self-update from GitHub with state backup & pytest guard |
| `core backup` | Snapshot SQLite state database and `.env` config |
| `core test` | Run automated test suite (pytest) |
| `core setup` | Run interactive bootstrap and identity wizard |
| `core uninstall` | Clean zero-residue uninstallation |

---

*Core AI is open-source sovereign software licensed under the [GNU Affero General Public License v3.0](LICENSE).*
