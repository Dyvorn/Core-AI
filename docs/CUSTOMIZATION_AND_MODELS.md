# Model Routing & AI Provider Customization

```text
[ SYSTEM: CORE-AI-ROUTER ]  [ PROTOCOL: LITELLM / OLLAMA ]  [ PERSISTENCE: SQLITE ]
[ ARCHITECTURE: ZERO-HARDCODING ]  [ STATUS: ACTIVE ]       [ PHILOSOPHY: #ANTISLOP ]
```

> **Core AI imposes zero hardcoded assumptions about model providers, API endpoints, or model names. The operator has sovereign control over which intelligence engines handle which tasks, with persistent memory of preferences and effortless runtime overrides.**

---

## Table of Contents

- [Architectural Philosophy](#architectural-philosophy)
- [Model Roles & Hierarchy](#model-roles--hierarchy)
- [Supported Providers & Key Setup](#supported-providers--key-setup)
- [Interactive Setup Wizard](#interactive-setup-wizard)
- [Operator Core Console Commands](#operator-core-console-commands)
- [Natural Language Runtime Overrides](#natural-language-runtime-overrides)
- [REST API Endpoints](#rest-api-endpoints)
- [Autonomous Offline Fallback](#autonomous-offline-fallback)

---

## Architectural Philosophy

In traditional AI software, model names and providers are frequently hardcoded inside source code. Core AI rejects this practice:

1. **Sovereign Choice**: You can run 100% offline via local Ollama models, high-performance cloud APIs (Google Gemini, OpenAI, Anthropic), or custom local HTTP endpoints (vLLM, LM Studio, Text-Gen-WebUI).
2. **Persistent Identity Memory**: Preferences are saved directly into your operator profile in SQLite (`user_profiles.preferences['models']`), remaining active across restarts without manual configuration.
3. **Dynamic Task Routing**: Different roles (DAG planning, multi-step deep reasoning, quick local responses) can use distinct models optimized for cost, speed, or intelligence.
4. **Instant Runtime Overrides**: You can tell Core AI to use a specific model for a single query (e.g. `using ollama/llama3`) without altering your global defaults.

---

## Model Roles & Hierarchy

Core AI assigns intelligence tasks to four configurable operational roles:

| Role | Default Target | Intended Purpose |
| :--- | :--- | :--- |
| **`planner`** | `ollama/qwen3.5:2b` or `gemini/gemini-2.5-flash` | Decomposing user goals into executable DAG steps and checking capability gaps. |
| **`fallback`** | `gemini/gemini-2.5-flash` | Secondary engine automatically engaged if the primary planner is offline or unreachable. |
| **`deep_reasoning`** | `gemini/gemini-2.5-pro` | Heavy multi-faceted architectural analysis, creative synthesis, and complex planning. |
| **`fast_local`** | `ollama/qwen3.5:2b` | Sub-second offline queries, natural speech classification, and local system operations. |

---

## Supported Providers & Key Setup

### 1. Local Ollama (100% Offline Silicon)
Run any open-weight model locally on your own GPU/NPU:
```bash
# Start Ollama service (default: http://localhost:11434)
ollama run qwen3.5:2b
ollama run llama3.2:3b
```
No API keys required. Core AI detects your local Ollama instance automatically via fast health checks on `http://localhost:11434/api/tags`.

### 2. Google Gemini API
High-speed reasoning with large context windows:
```bash
# Set in config/.env or via console:
GEMINI_API_KEY=AIzaSy...
```
Supported models: `gemini/gemini-2.5-flash`, `gemini/gemini-2.5-pro`, `gemini/gemini-3.1-pro`.

### 3. OpenAI API
```bash
# Set in config/.env or via console:
OPENAI_API_KEY=sk-...
```
Supported models: `openai/gpt-4o`, `openai/gpt-4o-mini`.

### 4. Anthropic Claude API
```bash
# Set in config/.env or via console:
ANTHROPIC_API_KEY=sk-ant-...
```
Supported models: `anthropic/claude-3-5-sonnet-20241022`, `anthropic/claude-3-5-haiku-20241022`.

---

## Interactive Setup Wizard

To configure your preferred AI provider, API keys, and model preferences on first run:

```bash
python interfaces/cli/setup_wizard.py
```

The wizard prompts you for:
1. Operator Handle & Nicknames.
2. Initial Primary Space (Workspace, Living Sanctuary, Workshop, Hangar).
3. Communication Tone (Friendly Concise, Tactical Direct, Casual).
4. **AI Intelligence Provider**: Select Ollama, Gemini, OpenAI, or Pure Heuristic, and enter API keys.
5. **Mesh Role**: Declare whether the machine is a Central 24/7 Server or a Roaming Edge Node.

---

## Operator Core Console Commands

Inside `python interfaces/cli/core_console.py`, manage models on the fly:

### 1. Inspect Models & Providers
```text
>>> models
--- Configured AI Providers & Models ---
  * gemini           : [Configured / Online]
  * openai           : [Not Configured / Offline]
  * anthropic        : [Not Configured / Offline]
  * ollama_local     : [Configured / Online]

--- Active Model Roles & Assignments ---
  * planner          : gemini/gemini-2.5-flash    [ONLINE]
  * fallback         : ollama/qwen3.5:2b          [ONLINE]
  * deep_reasoning   : gemini/gemini-2.5-pro      [ONLINE]
  * fast_local       : ollama/qwen3.5:2b          [ONLINE]
```

### 2. Change Model Roles at Runtime
```text
>>> model set planner gemini/gemini-2.5-flash
[OK] Assigned model 'gemini/gemini-2.5-flash' to role 'planner'.

>>> model set fallback ollama/qwen3.5:2b
[OK] Assigned model 'ollama/qwen3.5:2b' to role 'fallback'.
```

### 3. Save API Keys Dynamically
```text
>>> api-key set gemini AIzaSyExampleKey12345
[OK] Saved API key for 'gemini' to GEMINI_API_KEY and config/.env.
```

---

## Natural Language Runtime Overrides

You can instruct Core AI to use a specific model for any individual command without modifying your saved defaults.

### Syntax Examples:
```text
>>> solve compute sha256 of 'secret' with ollama/llama3
>>> solve plan a 3-day itinerary using gemini/gemini-2.5-pro
>>> solve calculate prime numbers on model ollama/qwen3.5:2b
```

Core AI automatically:
1. Detects the `with <model>` or `using <model>` clause.
2. Verifies provider availability.
3. Decomposes the goal using the requested engine.
4. Leaves default model assignments intact for subsequent commands.

---

## REST API Endpoints

External clients, smart mirrors, and mobile companions can inspect and update model preferences over HTTP:

### `GET /api/v1/models`
Returns configured providers, active model preferences, and real-time connectivity status:
```json
{
  "configured_providers": {
    "gemini": true,
    "openai": false,
    "anthropic": false,
    "ollama_local": true
  },
  "roles": {
    "planner": { "model": "gemini/gemini-2.5-flash", "online": true },
    "fallback": { "model": "ollama/qwen3.5:2b", "online": true }
  },
  "offline_heuristic_available": true
}
```

### `POST /api/v1/models/preferences`
Assigns a model to an operational role (requires `X-Trust-Tier: owner`):
```json
{
  "role": "planner",
  "model_name": "gemini/gemini-2.5-flash"
}
```

---

## Autonomous Offline Fallback

If network connectivity drops or third-party APIs experience outages:
1. Core AI immediately tries the configured `fallback` model (e.g. local Ollama).
2. If all LLM providers are unreachable, Core AI shifts seamlessly to its **deterministic heuristic planner**.
3. Built-in tools, dynamic tools, file operations, audio routing, and voice synthesis remain **100% operational** without crashing or throwing unhandled exceptions.
