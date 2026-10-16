"""
Core AI :: Sovereign Distributed Voice Satellite
Enables any connected machine (PC, laptop, Raspberry Pi, workstation) to act as a
sovereign spatial voice satellite with dedicated microphone capture, local Silero VAD,
and central reasoning over the Core AI Mesh.
"""

import os
import sys
import time
import signal
import logging
import argparse
import platform
import threading
import re
from typing import Optional, Dict, Any, Tuple, List

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.state import StateManager
from core.mesh_client import MeshClient
from engines.voice_in import VoiceInEngine
from engines.voice_out import VoiceOutEngine
from brain.spoken_to import SpokenToReasoning, DiscourseRole
from core.terminal import render_box, CYAN, GREEN, YELLOW, RED, MAGENTA, BOLD, RESET

logger = logging.getLogger("CoreAI.VoiceSatellite")


class VoiceSatellite:
    """
    Sovereign Voice Satellite Daemon:
    - Runs always-on neural voice capture on any host hardware
    - Dispatches spoken commands across the sovereign mesh to the Central Main Server
    - Plays synthesized voice responses back through the local machine's speakers
    - Eliminates central cloud lock-in with 100% local hardware perception
    """

    def __init__(
        self,
        node_id: Optional[str] = None,
        server_url: Optional[str] = None,
        zone: Optional[str] = None,
        mic_device: Optional[Any] = None,
        speaker_device: Optional[Any] = None,
        model_size: str = "small",
        state_manager: Optional[StateManager] = None,
        mode: str = "auto"
    ):
        self.state_manager = state_manager or StateManager()
        profile = self.state_manager.get_user_profile()
        prefs = profile.preferences

        default_node = f"{platform.node().lower() or 'satellite'}_node"
        raw_node = node_id or prefs.get("mesh", {}).get("node_id") or default_node
        self.node_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(raw_node))
        self.server_url = (server_url or prefs.get("mesh", {}).get("main_server_url") or "http://localhost:8000").rstrip("/")
        self.zone = zone or prefs.get("primary_space") or "office"
        self.operator_name = profile.preferred_name or "Operator"
        self.mode = mode
        self.capabilities: List[str] = ["audio_in", "audio_out"]
        self.operational_mode: str = "bidirectional"

        # Hardware audio indices
        audio_prefs = prefs.get("audio", {})
        self.mic_device = mic_device if mic_device is not None else os.getenv("CORE_MIC_DEVICE", audio_prefs.get("mic_device"))
        self.speaker_device = speaker_device if speaker_device is not None else os.getenv("CORE_SPEAKER_DEVICE", audio_prefs.get("speaker_device"))
        self.model_size = model_size

        # Mesh transport
        self.mesh_client = MeshClient(
            state_manager=self.state_manager,
            role="edge_node",
            main_server_url=self.server_url,
            node_id=self.node_id
        )

        # LAN Auto-Discovery: If server_url was not explicitly given, or if pointing to localhost and localhost is offline, scan LAN
        self.auto_discovered = False
        if not server_url:
            is_local_online, _, _ = self.mesh_client.ping_latency(timeout=0.6)
            if not is_local_online:
                try:
                    from core.discovery import discover_core_servers
                    found = discover_core_servers(timeout=1.2)
                    if found:
                        self.server_url = found[0]["url"]
                        self.mesh_client.main_server_url = self.server_url
                        self.auto_discovered = True
                        logger.info(f"Auto-discovered Core AI Main Server at {self.server_url}")
                except Exception as d_err:
                    logger.debug(f"LAN auto-discovery probe failed: {d_err}")

        # Local autonomous executor fallback (Never-a-Brick guarantee when mesh drops)
        self._local_planner = None
        self._local_engine = None
        try:
            from tools.registry import ToolRegistry
            from brain.planner import Planner
            from brain.pipeline_engine import PipelineEngine
            reg = ToolRegistry()
            self._local_planner = Planner(registry=reg, state_manager=self.state_manager, model_name="heuristic")
            self._local_engine = PipelineEngine(registry=reg, state_manager=self.state_manager)
        except Exception as loc_err:
            logger.debug(f"Local fallback planner initialization deferred: {loc_err}")

        # Perception engines
        self.spoken_to = SpokenToReasoning()
        self.voice_out: Optional[VoiceOutEngine] = None
        self.voice_in: Optional[VoiceInEngine] = None
        self.is_running = False
        self._start_time = time.time()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._ws_thread: Optional[threading.Thread] = None

    def _local_fallback_executor(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executes goals locally on this device's silicon if central server is unreachable."""
        if self._local_planner and self._local_engine:
            try:
                plan = self._local_planner.plan_problem(goal, context or {})
                res = self._local_engine.execute_pipeline_sync(plan)
                spoken = self._local_planner.formulate_spoken_response(res, profile=self.state_manager.get_user_profile())
                return {
                    "status": res.status,
                    "goal": goal,
                    "spoken_response": spoken,
                    "final_output": res.final_output
                }
            except Exception as e:
                logger.warning(f"Local autonomous execution failed: {e}")
                return {"status": "error", "message": f"Local execution failed: {e}"}
        return {"status": "error", "message": "No local executor available."}

    def get_status_dict(self) -> Dict[str, Any]:
        """Returns structured status dictionary for telemetry, heartbeat, and remote RPC."""
        return {
            "node_id": self.node_id,
            "zone": self.zone,
            "mic_device": str(self.mic_device) if self.mic_device is not None else "default",
            "speaker_device": str(self.speaker_device) if self.speaker_device is not None else "default",
            "model_size": self.model_size,
            "uptime_seconds": round(time.time() - self._start_time, 2),
            "is_speaking": bool(self.voice_out and getattr(self.voice_out, "is_speaking", False)),
            "is_listening": bool(self.voice_in and getattr(self.voice_in, "is_recording", False)),
            "metadata": {
                "capabilities": self.capabilities,
                "operational_mode": self.operational_mode,
                "mode": self.mode
            }
        }

    def send_heartbeat(self, status: str = "listening") -> bool:
        """Sends telemetry heartbeat to Central Gateway."""
        import urllib.request
        import json
        payload = self.get_status_dict()
        payload["status"] = status
        url = f"{self.server_url}/api/v1/mesh/satellites/heartbeat"
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "CoreAI-VoiceSatellite"}
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                return resp.status == 200
        except Exception as e:
            logger.debug(f"Heartbeat dispatch failed to {url}: {e}")
            return False

    def sync_mesh_state(self) -> Dict[str, Any]:
        """Performs bidirectional delta sync, pulling latest state and replaying any offline tasks."""
        try:
            res = self.mesh_client.sync()
            if res.get("status") == "success":
                counts = res.get("merged_counts", {})
                logger.info(f"Voice satellite '{self.node_id}' synchronized with mesh: {counts}")
            return res
        except Exception as e:
            logger.debug(f"Voice satellite state sync notice: {e}")
            return {"status": "error", "message": str(e)}

    def _heartbeat_loop(self):
        """Background daemon thread dispatching heartbeats periodically with auto re-discovery and state sync."""
        consecutive_failures = 0
        if self.send_heartbeat(status="listening"):
            threading.Thread(target=self.sync_mesh_state, daemon=True).start()
        else:
            consecutive_failures += 1

        while self.is_running:
            for _ in range(30):
                if not self.is_running:
                    break
                time.sleep(0.5)
            if self.is_running:
                ok = self.send_heartbeat(status="listening")
                if not ok:
                    consecutive_failures += 1
                    # After 3 consecutive failed heartbeats (~45s), attempt dynamic LAN re-discovery
                    if consecutive_failures >= 3:
                        try:
                            from core.discovery import discover_core_servers
                            found = discover_core_servers(timeout=1.0)
                            if found and found[0]["url"] != self.server_url:
                                logger.info(f"Re-discovered Core AI Gateway at {found[0]['url']}")
                                self.server_url = found[0]["url"]
                                self.mesh_client.main_server_url = self.server_url
                                consecutive_failures = 0
                                threading.Thread(target=self.sync_mesh_state, daemon=True).start()
                        except Exception as re_err:
                            logger.debug(f"LAN re-discovery notice: {re_err}")
                else:
                    if consecutive_failures > 0:
                        # Reconnection detected: reconcile offline tasks and pull state deltas
                        threading.Thread(target=self.sync_mesh_state, daemon=True).start()
                    consecutive_failures = 0

    def get_edge_tools(self) -> List[Dict[str, Any]]:
        """Returns schemas for dynamic edge tools exposed by this voice satellite."""
        return [
            {
                "name": f"speak_{self.node_id}",
                "description": f"Synthesizes and plays speech through voice satellite '{self.node_id}' in zone '{self.zone}'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Phrase to synthesize and play."}
                    },
                    "required": ["text"]
                }
            },
            {
                "name": f"status_{self.node_id}",
                "description": f"Retrieves current hardware vitals, spatial zone, and operational capabilities of voice satellite '{self.node_id}'.",
                "parameters": {"type": "object", "properties": {}}
            },
            {
                "name": f"interrupt_{self.node_id}",
                "description": f"Halts active speech synthesis on voice satellite '{self.node_id}'.",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

    def handle_edge_message(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processes an incoming mesh message from the Central Gateway.
        Returns a response dictionary if a reply should be transmitted back over WebSocket, or None.
        """
        mtype = msg.get("type")

        # 0. Inter-device mesh message dispatched from gateway
        if mtype == "mesh_device_message":
            inner = msg.get("message", {})
            itype = inner.get("message_type")
            ipayload = inner.get("payload", {})
            if itype == "speak" and ipayload.get("text"):
                phrase = ipayload["text"]
                if self.voice_out:
                    print(f"\n{CYAN}[MESH INTER-DEVICE SPEECH]{RESET} \"{phrase}\"\n", flush=True)
                    self.voice_out.synthesize_and_play(phrase, blocking=False)
                return None
            elif itype in ("interrupt", "stop"):
                if self.voice_out:
                    self.voice_out.interrupt()
                    print(f"\n{YELLOW}[MESH INTER-DEVICE INTERRUPT]{RESET} Speech playback halted.\n", flush=True)
                return None
            elif itype == "sync":
                threading.Thread(target=self.sync_mesh_state, daemon=True).start()
                return {"type": "sync_ack", "node_id": self.node_id, "timestamp": time.time()}
            elif itype == "command":
                cmd = ipayload.get("command") or ipayload.get("goal")
                if cmd:
                    exec_res = self._local_fallback_executor(cmd)
                    return {"type": "command_result", "node_id": self.node_id, "result": exec_res}
            return None

        # 1. Direct speech command
        if mtype == "speak":
            text = msg.get("text")
            if text and self.voice_out:
                print(f"\n{CYAN}[REMOTE SPEECH PLAYBACK]{RESET} \"{text}\"\n", flush=True)
                self.voice_out.synthesize_and_play(text, blocking=False)
            return None

        # 2. Remote stop / interrupt
        elif mtype in ("interrupt", "stop"):
            if self.voice_out:
                self.voice_out.interrupt()
                print(f"\n{YELLOW}[REMOTE INTERRUPT]{RESET} Speech playback halted.\n", flush=True)
            return None

        # 3. WebSocket ping / keepalive
        elif mtype == "ping":
            return {"type": "pong", "node_id": self.node_id, "timestamp": time.time()}

        # 4. Dispatched remote tool call from Gateway
        elif mtype == "tool_call_request":
            req_id = msg.get("request_id")
            t_name = msg.get("tool_name", "")
            args = msg.get("arguments", {})
            if "speak" in t_name:
                phrase = args.get("text", "")
                if phrase and self.voice_out:
                    self.voice_out.synthesize_and_play(phrase, blocking=False)
                    t_res = {"status": "success", "spoken": phrase}
                elif not phrase:
                    t_res = {"status": "error", "message": "Empty text provided for speech"}
                else:
                    t_res = {"status": "error", "message": "Voice out engine unavailable"}
            elif "status" in t_name:
                t_res = self.get_status_dict()
            elif "interrupt" in t_name:
                if self.voice_out:
                    self.voice_out.interrupt()
                t_res = {"status": "success", "interrupted": True}
            else:
                t_res = {"status": "error", "message": f"Unknown tool '{t_name}'"}

            return {
                "type": "tool_call_response",
                "request_id": req_id,
                "result": t_res
            }

        # 5. Broadcast event format (SATELLITE_SPEAK)
        elif msg.get("event") == "SATELLITE_SPEAK":
            event_data = msg.get("data", {})
            tgt = event_data.get("node_id")
            if tgt in (self.node_id, "all") and event_data.get("text") and self.voice_out:
                print(f"\n{CYAN}[BROADCAST SPEECH PLAYBACK]{RESET} \"{event_data['text']}\"\n", flush=True)
                self.voice_out.synthesize_and_play(event_data["text"], blocking=False)
            return None

        # 6. Broadcast event format (MESH_DEVICE_MESSAGE)
        elif msg.get("event") == "MESH_DEVICE_MESSAGE":
            inner = msg.get("data", {})
            itype = inner.get("message_type")
            ipayload = inner.get("payload", {})
            if itype == "speak" and ipayload.get("text") and self.voice_out:
                print(f"\n{CYAN}[BROADCAST SPEECH PLAYBACK]{RESET} \"{ipayload['text']}\"\n", flush=True)
                self.voice_out.synthesize_and_play(ipayload["text"], blocking=False)
            elif itype in ("interrupt", "stop") and self.voice_out:
                self.voice_out.interrupt()
            elif itype == "sync":
                threading.Thread(target=self.sync_mesh_state, daemon=True).start()
            return None

        # 7. Broadcast event format (MESH_STATE_UPDATED)
        elif msg.get("event") == "MESH_STATE_UPDATED":
            # Real-time state change notice from server: pull deltas immediately
            threading.Thread(target=self.sync_mesh_state, daemon=True).start()
            return None

        return None

    def _mesh_ws_loop(self):
        """Background thread keeping a persistent WebSocket connection to Gateway for remote speech commands."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _client():
            try:
                import websockets
            except ImportError:
                logger.info("Optional package 'websockets' not installed. WebSocket command reception disabled.")
                return

            import json
            reconnect_delay = 1.0
            max_reconnect_delay = 5.0
            while self.is_running:
                ws_url = self.server_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws/nodes/{self.node_id}"
                try:
                    tools = self.get_edge_tools()
                    async with websockets.connect(ws_url, close_timeout=1.0) as ws:
                        # Register node with current capabilities and edge tools
                        reg = {
                            "type": "register",
                            "data": {
                                "node_id": self.node_id,
                                "device_type": "voice_satellite",
                                "is_fixed_anchor": True,
                                "initial_zone": self.zone,
                                "capabilities": self.capabilities,
                                "tools": tools
                            }
                        }
                        await ws.send(json.dumps(reg))
                        logger.info(f"Connected to Central Gateway WebSocket at {ws_url} (mode: {self.operational_mode})")

                        while self.is_running:
                            try:
                                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
                            except asyncio.TimeoutError:
                                continue
                            try:
                                msg = json.loads(raw)
                                reply = self.handle_edge_message(msg)
                                if reply:
                                    await ws.send(json.dumps(reply))

                            except Exception as msg_err:
                                logger.debug(f"Error processing edge message: {msg_err}")
                except Exception as e:
                    logger.debug(f"Mesh WebSocket disconnected ({e}), retrying in {reconnect_delay:.1f}s...")
                    steps = int(reconnect_delay / 0.25)
                    for _ in range(max(1, steps)):
                        if not self.is_running:
                            return
                        await asyncio.sleep(0.25)
                    reconnect_delay = min(max_reconnect_delay, reconnect_delay * 1.5)

        try:
            loop.run_until_complete(_client())
        except Exception as loop_err:
            logger.debug(f"Mesh WebSocket client thread finished: {loop_err}")
        finally:
            try:
                loop.close()
            except Exception:
                pass

    def speak(self, text: str, blocking: bool = False):
        """Plays speech directly through the satellite's local speakers."""
        if self.voice_out:
            self.voice_out.synthesize_and_play(text, blocking=blocking)
        else:
            logger.warning("Local voice_out engine not initialized; speak command dropped.")

    def initialize_hardware(self) -> Tuple[bool, str]:
        """Initializes voice in/out hardware with dynamic adaptive fallback."""
        # 1. Speaker output setup (unless listen-only mode explicitly forced)
        if self.mode != "listen_only":
            try:
                self.voice_out = VoiceOutEngine(
                    output_device=self.speaker_device,
                    default_voice="auto"
                )
            except Exception as out_err:
                logger.warning(f"VoiceOut initialization warning ({out_err}). Speech playback disabled.")
                self.voice_out = None
        else:
            self.voice_out = None

        # 2. Microphone input setup (unless speak-only mode explicitly forced)
        if self.mode != "speak_only":
            try:
                self.voice_in = VoiceInEngine(
                    model_size=self.model_size,
                    input_device=self.mic_device,
                    voice_out=self.voice_out
                )
                if self.voice_out and self.voice_in:
                    self.voice_in.register_voice_out(self.voice_out)
            except Exception as in_err:
                logger.warning(f"VoiceIn initialization warning ({in_err}). Microphone perception disabled.")
                self.voice_in = None
        else:
            self.voice_in = None

        # 3. Determine operational capabilities
        caps = []
        if self.voice_in is not None:
            caps.append("audio_in")
        if self.voice_out is not None:
            caps.append("audio_out")
        self.capabilities = caps

        if "audio_in" in caps and "audio_out" in caps:
            self.operational_mode = "bidirectional"
            return True, "Full bidirectional audio hardware initialized (Perception In + Speech Out)."
        elif "audio_out" in caps:
            self.operational_mode = "speaker_only"
            return True, "Running in Speaker-Only mode (remote audio receiver / media playback anchor)."
        elif "audio_in" in caps:
            self.operational_mode = "listen_only"
            return True, "Running in Listen-Only mode (dedicated microphone spatial perception anchor)."
        else:
            return False, "Neither microphone nor speaker hardware could be initialized."

    def on_speech_detected(self, text: str):
        """Callback executed when voice capture confirms speech transcript."""
        if not text or not text.strip():
            return

        print(f"\n{MAGENTA}[SPEECH CAPTURED]{RESET} \"{text}\"", flush=True)

        prof = self.state_manager.get_user_profile()
        decision = self.spoken_to.evaluate(text, profile=prof)

        # 1. Verbal barge-in / stop
        if decision.action_type == "interrupt":
            if self.voice_out:
                self.voice_out.interrupt()
            print(f"  {YELLOW}↳ Playback interrupted by operator.{RESET}\n", flush=True)
            return

        # 2. Ambient room noise / not addressed
        if not decision.should_respond:
            print(f"  {YELLOW}↳ Silently ignored (ambient discourse / not addressed to Core AI){RESET}\n", flush=True)
            return

        # 3. Halt existing speech before answering new directive
        if self.voice_out and self.voice_out.is_speaking:
            self.voice_out.interrupt()

        # 4. Immediate Demonstration / Showcase Chime-in
        if decision.action_type == "chime_in" and decision.autonomous_response:
            print(f"  {CYAN}[Demonstration Chime-In]{RESET} {decision.autonomous_response}\n", flush=True)
            if self.voice_out:
                self.voice_out.synthesize_and_play(decision.autonomous_response, blocking=False)
            return

        command = decision.clean_command or text
        print(f"  {CYAN}[Dispatching to Mesh]{RESET} '{command}' -> {self.server_url}", flush=True)

        # 5. Dispatch over mesh to central main server (with autonomous fallback)
        context = {
            "zone": self.zone,
            "operator": self.operator_name,
            "source_node": self.node_id,
            "client_type": "voice_satellite"
        }

        start_time = time.time()
        mesh_res = self.mesh_client.execute_over_mesh(
            goal=command,
            context=context,
            local_executor=self._local_fallback_executor
        )
        elapsed = time.time() - start_time

        if mesh_res.get("execution_mode") == "remote_main_server":
            res_data = mesh_res.get("result", {})
            if res_data.get("status") == "error":
                spoken = res_data.get("spoken_response") or res_data.get("error_summary") or res_data.get("error") or "Execution failed on main server."
            else:
                spoken = res_data.get("spoken_response") or res_data.get("final_output") or "Done."
            if isinstance(spoken, dict):
                spoken = spoken.get("message") or spoken.get("status") or str(spoken)

            print(f"{GREEN}[OK] Received Central Response in {elapsed:.2f}s:{RESET} {BOLD}{spoken}{RESET}\n", flush=True)
            if self.voice_out:
                self.voice_out.synthesize_and_play(str(spoken), blocking=False)
        elif mesh_res.get("execution_mode") == "local_autonomous_fallback":
            res_data = mesh_res.get("result", {})
            spoken = res_data.get("spoken_response") or res_data.get("final_output") or "Done locally."
            if isinstance(spoken, dict):
                spoken = spoken.get("message") or spoken.get("status") or str(spoken)
            print(f"{YELLOW}[AUTONOMOUS LOCAL FALLBACK in {elapsed:.2f}s]{RESET} {BOLD}{spoken}{RESET}\n", flush=True)
            if self.voice_out:
                self.voice_out.synthesize_and_play(str(spoken), blocking=False)
        else:
            # Fallback or error notice
            notice = mesh_res.get("notice") or "Command executed locally."
            print(f"{YELLOW}[!] Notice: {notice}{RESET}\n", flush=True)
            if self.voice_out:
                self.voice_out.synthesize_and_play(str(notice), blocking=False)

    def print_satellite_card(self):
        """Displays high-contrast satellite status matrix."""
        is_online, _, latency = self.mesh_client.ping_latency(timeout=2.0)
        if not is_online:
            is_online, _, latency = self.mesh_client.ping_latency(timeout=3.0)
        status_lbl = f"{GREEN}ONLINE ({latency}ms){RESET}" if is_online else f"{YELLOW}OFFLINE (Autonomous Fallback){RESET}"

        mic_name = f"Device #{self.mic_device}" if self.mic_device is not None else "Default System Microphone"
        if not self.voice_in:
            mic_name = f"{YELLOW}Disabled / Not Detected{RESET}"
        spk_name = f"Device #{self.speaker_device}" if self.speaker_device is not None else "Default System Speaker"
        if not self.voice_out:
            spk_name = f"{YELLOW}Disabled / Not Detected{RESET}"

        mode_labels = {
            "bidirectional": f"{GREEN}BIDIRECTIONAL (Listen & Speak){RESET}",
            "speak_only": f"{YELLOW}SPEAKER-ONLY (Broadcast / Media Sink){RESET}",
            "listen_only": f"{CYAN}LISTEN-ONLY (Sensor Array / Mic Only){RESET}",
            "auto": f"{GREEN}AUTO ADAPTIVE{RESET}"
        }
        mode_lbl = mode_labels.get(self.mode, self.mode.upper())
        status_txt = f"{GREEN}LISTENING FOR COMMANDS{RESET}" if self.voice_in else f"{YELLOW}RECEIVING MESH BROADCASTS ONLY{RESET}"

        card = render_box(
            title="C.O.R.E. AI :: SOVEREIGN VOICE SATELLITE",
            rows=[
                ("Satellite Node ID:", f"{CYAN}{self.node_id}{RESET}"),
                ("Spatial Zone:", f"{YELLOW}{self.zone}{RESET}"),
                ("Operational Mode:", mode_lbl),
                ("Main Server URL:", f"{self.server_url} [{status_lbl}]"),
                ("Microphone Input:", mic_name),
                ("Speaker Playback:", spk_name),
                ("Perception Engine:", f"{GREEN}ALWAYS-ON (Silero Neural VAD + Whisper {self.model_size}){RESET}" if self.voice_in else f"{YELLOW}OFF (Audio Sink Only){RESET}"),
                ("Mesh Status:", status_txt)
            ],
            width=73
        )
        print(f"\n{card}\n", flush=True)
        if self.voice_in:
            print(f"{MAGENTA}Speak naturally at any time. Say 'Stop' to interrupt speech output.{RESET}\n", flush=True)
        else:
            print(f"{MAGENTA}Satellite operating as sovereign audio output sink over Core AI Mesh.{RESET}\n", flush=True)

    def run(self, headless: bool = False):
        """Starts the voice satellite perception loop."""
        ok, msg = self.initialize_hardware()
        if not ok:
            print(f"{RED}[ERROR] {msg}{RESET}", file=sys.stderr)
            return 1

        self.is_running = True

        if not headless:
            self.print_satellite_card()

        # Start microphone stream if voice input is enabled
        if self.voice_in:
            self.voice_in.start_listening(callback=self.on_speech_detected)

        # Start background heartbeat loop
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"SatHeartbeat-{self.node_id}",
            daemon=True
        )
        self._heartbeat_thread.start()

        # Start background WebSocket listener for remote speech commands
        self._ws_thread = threading.Thread(
            target=self._mesh_ws_loop,
            name=f"SatWS-{self.node_id}",
            daemon=True
        )
        self._ws_thread.start()

        # Handle termination signals cleanly when executing on the main thread
        def handle_sig(sig, frame):
            print(f"\n{YELLOW}[*] Stopping Voice Satellite ({self.node_id})...{RESET}")
            self.stop()
            sys.exit(0)

        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGINT, handle_sig)
                if hasattr(signal, "SIGTERM"):
                    signal.signal(signal.SIGTERM, handle_sig)
            except (ValueError, AttributeError):
                pass

        try:
            while self.is_running:
                time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            self.stop()
        return 0

    def stop(self):
        """Gracefully halts microphone capture and audio playback."""
        self.is_running = False
        try:
            self.send_heartbeat(status="offline")
        except Exception:
            pass
        if self.voice_in:
            try:
                if hasattr(self.voice_in, "stop_listening"):
                    self.voice_in.stop_listening()
                elif hasattr(self.voice_in, "stop"):
                    self.voice_in.stop()
            except Exception:
                pass
        if self.voice_out:
            try:
                self.voice_out.stop()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Core AI Sovereign Voice Satellite")
    parser.add_argument("--server", type=str, help="Main Core AI server URL (e.g. http://192.168.2.203:8000)")
    parser.add_argument("--node-id", type=str, help="Unique node identifier for this machine")
    parser.add_argument("--zone", type=str, help="Spatial room/zone anchor (e.g. office, living_room, studio)")
    parser.add_argument("--mode", type=str, choices=["auto", "bidirectional", "speak_only", "listen_only"], default="auto", help="Operational mode")
    parser.add_argument("--speak-only", action="store_true", help="Run satellite as speaker-only audio output sink")
    parser.add_argument("--listen-only", action="store_true", help="Run satellite as listen-only microphone sensor")
    parser.add_argument("--mic", type=str, help="Microphone device index or substring name")
    parser.add_argument("--speaker", type=str, help="Speaker device index or substring name")
    parser.add_argument("--model-size", type=str, default="small", help="Whisper model size (tiny, base, small)")
    parser.add_argument("--headless", action="store_true", help="Run without terminal status card")

    args = parser.parse_args()

    # Parse device numbers if integer
    mic_dev = int(args.mic) if args.mic and args.mic.isdigit() else args.mic
    spk_dev = int(args.speaker) if args.speaker and args.speaker.isdigit() else args.speaker

    mode = "speak_only" if args.speak_only else ("listen_only" if args.listen_only else args.mode)

    satellite = VoiceSatellite(
        node_id=args.node_id,
        server_url=args.server,
        zone=args.zone,
        mode=mode,
        mic_device=mic_dev,
        speaker_device=spk_dev,
        model_size=args.model_size
    )

    sys.exit(satellite.run(headless=args.headless))


if __name__ == "__main__":
    main()
