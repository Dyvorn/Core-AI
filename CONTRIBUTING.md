# Contributing to Core AI

Thank you for contributing to Core AI. Core AI is an autonomous, open-source, sovereign personal companion built for privacy, independence, and ubiquitous multi-device harmony.

---

## 1. Guiding Principles

- **Sovereign & Local-First**: No corporate cloud lock-in, no telemetry phoning home, no closed-source dependencies for core functions.
- **Truthful Capabilities (Anti-Slop Standard)**: Never build components that hallucinate abilities they don't have. If something fails or isn't installed, diagnose it transparently.
- **Zero-Friction Portability**: All components must remain cross-platform (Linux primary, Windows supported, Android/embedded ready).
- **Extensible without Rewrites**: New devices (cars, bikes, glasses, mirrors) must connect over the Universal Gateway without altering brain or pipeline engine logic.

---

## 2. Development Setup

1. **Clone and Setup Virtual Environment**:
   ```bash
   git clone <repo-url>
   cd "Core AI"
   python -m venv .venv
   
   # Linux/macOS
   source .venv/bin/activate
   # Windows
   .venv\Scripts\activate
   
   pip install -r requirements.txt
   pip install pytest
   ```

2. **Run the Test Suite**:
   ```bash
   python -m pytest tests
   ```
   All tests must pass before submitting a PR.

---

## 3. Adding Tools

- **Native Tools**: Add deterministic, system-level, or hardware tools to [tools/native/](file:///g:/VSC_Projects/Core%20AI/tools/native/) and expose a valid JSON schema.
- **Dynamic Tools**: Tools generated dynamically by the AI are persisted in [tools/dynamic/](file:///g:/VSC_Projects/Core%20AI/tools/dynamic/). Dynamic tools must pass AST security inspection (no `subprocess`, `ctypes`, or arbitrary code injection).
- **Remote Edge Tools**: Register physical device capabilities via [tools/remote_dispatcher.py](file:///g:/VSC_Projects/Core%20AI/tools/remote_dispatcher.py).

---

## 4. Pull Request Guidelines

1. Create a feature branch: `git checkout -b feature/your-feature-name`.
2. Follow PEP 8 style conventions and use strict Pydantic v2 typing for all event and message schemas.
3. Add corresponding unit tests in `tests/`.
4. Ensure zero regressions by running `python -m pytest tests`.
5. Submit your Pull Request with a clear summary of your architectural rationale.
