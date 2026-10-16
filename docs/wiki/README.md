# Core AI Master Wiki & Knowledge Base

```text
========================================================================================
[ KNOWLEDGE BASE ]   [ STATUS: VERIFIED v0.2.3 ]   [ ARCHITECTURE: SOVEREIGN ASYNC DAG ]
[ SYSTEM: WIKI ]     [ ANTI-SLOP: ENFORCED ]       [ LICENSE: AGPL-3.0-ONLY ]
========================================================================================
```

Welcome to the **Core AI Master Wiki**. This documentation hub is a living, version-controlled repository of architectural guides, system references, operational workflows, and verified troubleshooting solutions.

> **The Sovereign Rule**: If you encounter an issue or error with Core AI, you **will** find the tested root cause and step-by-step fix in this Wiki. If you encounter an unlisted edge case, submit it using our [Issue & Solution Submission Guide](SUBMITTING_ISSUES_AND_SOLUTIONS.md), and it will be tested, resolved, and documented permanently.

---

## 📚 Master Wiki Navigation

| Section | Description | Target Audience |
| :--- | :--- | :--- |
| 🛠️ **[Troubleshooting & Solutions](TROUBLESHOOTING_AND_SOLUTIONS.md)** | **Start here if anything goes wrong.** Problem $\to$ Symptom $\to$ Solution catalog for audio, WASAPI, SQLite locks, networking, and LLMs. | All Operators & Developers |
| 🧠 **[Proactive Autonomous Engine](PROACTIVE_ENGINE.md)** | Deep dive into anticipatory intelligence, calendar/schedule evidence reconciliation, preparation buffers, and non-intrusive alerts. | Architects & Users |
| 🏗️ **[Architecture & Subsystems](ARCHITECTURE_AND_SUBSYSTEMS.md)** | Technical anatomy: Microkernel, SQLite WAL StateManager, Async DAG Engine, Spoken-To Pragmatics, and Sovereign Mesh. | Engineers & Contributors |
| ⚡ **[CLI & Tools Master Reference](CLI_AND_TOOLS_REFERENCE.md)** | Comprehensive dictionary of all CLI commands (`core ...`), flags, native tool schemas, arguments, and return types. | Daily Operators |
| 📝 **[Submitting Issues & Solutions](SUBMITTING_ISSUES_AND_SOLUTIONS.md)** | How to report uncataloged errors, test proposed remedies, and merge solutions into the central Wiki. | Community & Testers |

---

## ⚡ Quick Problem Resolver (Common Pain Points)

If you are experiencing any of the following symptoms, jump straight to the verified fix:

1. **"Audio error: PaErrorCode -9997 on Windows"**  
   $\to$ See [Audio WASAPI Sample Rate Auto-Detection](TROUBLESHOOTING_AND_SOLUTIONS.md#a1-windows-wasapi--directsound-sample-rate-mismatch-paerrorcode--9997).
2. **"Database is locked / sqlite3.OperationalError"**  
   $\to$ See [SQLite Concurrency, WAL Mode & Busy Timeout Hardening](TROUBLESHOOTING_AND_SOLUTIONS.md#c1-sqlite3operationalerror-database-is-locked).
3. **"CLI takes 2+ seconds to respond on Windows loopback"**  
   $\to$ See [Windows IPv6 DNS Loopback Delay](TROUBLESHOOTING_AND_SOLUTIONS.md#b1-windows-localhost-ipv6-loopback-delay-22s-latency).
4. **"Ollama is offline and Core AI hangs waiting"**  
   $\to$ See [LLM Provider Health Checks & Fallback Pipeline](TROUBLESHOOTING_AND_SOLUTIONS.md#d1-offline-llm-provider-blocking-and-timeouts).
5. **"Proactive notifications repeating or intrusive"**  
   $\to$ See [Proactive Cooldowns, One-Shot Rules & Preparation Buffer Etiquette](TROUBLESHOOTING_AND_SOLUTIONS.md#e1-proactive-reminders-or-preparation-alerts-repeating).
6. **"Voice playback won't stop when I talk"**  
   $\to$ See [Verbal Barge-In & Speech Interruption Configuration](TROUBLESHOOTING_AND_SOLUTIONS.md#a2-verbal-barge-in-interruption-sensitivity).

---

## 💎 Core Philosophy & Tenets

Core AI is designed in strict accordance with the **#ANTISLOP** engineering standard:

1. **Anticipatory, Not Passive**:  
   If you have to ask *"Do I have appointments?"*, you might as well look at your calendar. Core AI monitors context, identifies implicit commitments, confirms evidence, schedules missing events, and provides pre-event preparation buffers automatically.
2. **Non-Intrusive & Non-Locking**:  
   Smart agency means never creating barriers. The microkernel never freezes terminal input, never blocks the event bus, and respects operator focus with polite, tiered alerts.
3. **Deterministic Fast-Paths**:  
   Routine commands (`get_time`, `git status`, `manage_notes`, `manage_calendar`) bypass local LLM inference, executing in under 5ms with deterministic reliability.
4. **Permanent Knowledge Ledger**:  
   No bug is ever fixed without its solution being permanently recorded in this Wiki.
