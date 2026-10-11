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
from typing import Optional, Dict, Any, Tuple

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
        state_manager: Optional[StateManager] = None
    ):
        self.state_manager = state_manager or StateManager()
        profile = self.state_manager.get_user_profile()
        prefs = profile.preferences

        default_node = f"{platform.node().lower() or 'satellite'}_node"
        self.node_id = node_id or prefs.get("mesh", {}).get("node_id") or default_node
        self.server_url = (server_url or prefs.get("mesh", {}).get("main_server_url") or "http://localhost:8000").rstrip("/")
        self.zone = zone or prefs.get("primary_space") or "office"
        self.operator_name = profile.preferred_name or "Operator"

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

        # Perception engines
        self.spoken_to = SpokenToReasoning()
        self.voice_out: Optional[VoiceOutEngine] = None
        self.voice_in: Optional[VoiceInEngine] = None
        self.is_running = False

    def initialize_hardware(self) -> Tuple[bool, str]:
        """Initializes voice in/out hardware with fallback detection."""
        try:
            self.voice_out = VoiceOutEngine(
                output_device=self.speaker_device,
                default_voice="auto"
            )
        except Exception as out_err:
            logger.warning(f"VoiceOut initialization warning ({out_err}). Speech playback may be silent.")
            self.voice_out = None

        try:
            self.voice_in = VoiceInEngine(
                model_size=self.model_size,
                input_device=self.mic_device,
                voice_out=self.voice_out
            )
            if self.voice_out and self.voice_in:
                self.voice_in.register_voice_out(self.voice_out)
            return True, "Audio hardware initialized successfully."
        except Exception as in_err:
            msg = f"Failed to initialize VoiceIn microphone: {in_err}"
            logger.error(msg)
            return False, msg

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

        command = decision.clean_command or text
        print(f"  {CYAN}[Dispatching to Mesh]{RESET} '{command}' -> {self.server_url}", flush=True)

        # 4. Dispatch over mesh to central main server
        context = {
            "zone": self.zone,
            "operator": self.operator_name,
            "source_node": self.node_id,
            "client_type": "voice_satellite"
        }

        start_time = time.time()
        mesh_res = self.mesh_client.execute_over_mesh(goal=command, context=context)
        elapsed = time.time() - start_time

        if mesh_res.get("execution_mode") == "remote_main_server":
            res_data = mesh_res.get("result", {})
            spoken = res_data.get("spoken_response") or res_data.get("final_output") or "Done."
            if isinstance(spoken, dict):
                spoken = spoken.get("message") or spoken.get("status") or str(spoken)

            print(f"{GREEN}[OK] Received Central Response in {elapsed:.2f}s:{RESET} {BOLD}{spoken}{RESET}\n", flush=True)
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
        status_lbl = f"{GREEN}ONLINE ({latency}ms){RESET}" if is_online else f"{YELLOW}OFFLINE (Autonomous Fallback){RESET}"

        mic_name = f"Device #{self.mic_device}" if self.mic_device is not None else "Default System Microphone"
        spk_name = f"Device #{self.speaker_device}" if self.speaker_device is not None else "Default System Speaker"

        card = render_box(
            title="C.O.R.E. AI :: SOVEREIGN VOICE SATELLITE",
            rows=[
                ("Satellite Node ID:", f"{CYAN}{self.node_id}{RESET}"),
                ("Spatial Zone:", f"{YELLOW}{self.zone}{RESET}"),
                ("Main Server URL:", f"{self.server_url} [{status_lbl}]"),
                ("Microphone Input:", mic_name),
                ("Speaker Playback:", spk_name),
                ("Voice Perception:", f"{GREEN}ALWAYS-ON (Silero Neural VAD){RESET}"),
                ("Status:", f"{GREEN}LISTENING FOR COMMANDS{RESET}")
            ],
            width=71
        )
        print(f"\n{card}\n", flush=True)
        print(f"{MAGENTA}Speak naturally at any time. Say 'Stop' to interrupt speech output.{RESET}\n", flush=True)

    def run(self, headless: bool = False):
        """Starts the voice satellite perception loop."""
        ok, msg = self.initialize_hardware()
        if not ok:
            print(f"{RED}[ERROR] {msg}{RESET}", file=sys.stderr)
            return 1

        self.is_running = True

        if not headless:
            self.print_satellite_card()

        # Start microphone stream
        self.voice_in.start_listening(callback=self.on_speech_detected)

        # Handle termination signals cleanly
        def handle_sig(sig, frame):
            print(f"\n{YELLOW}[*] Stopping Voice Satellite ({self.node_id})...{RESET}")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, handle_sig)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handle_sig)

        try:
            while self.is_running:
                time.sleep(0.5)
        except (KeyboardInterrupt, SystemExit):
            self.stop()
        return 0

    def stop(self):
        """Gracefully halts microphone capture and audio playback."""
        self.is_running = False
        if self.voice_in:
            try:
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
    parser.add_argument("--mic", type=str, help="Microphone device index or substring name")
    parser.add_argument("--speaker", type=str, help="Speaker device index or substring name")
    parser.add_argument("--model-size", type=str, default="small", help="Whisper model size (tiny, base, small)")
    parser.add_argument("--headless", action="store_true", help="Run without terminal status card")

    args = parser.parse_args()

    # Parse device numbers if integer
    mic_dev = int(args.mic) if args.mic and args.mic.isdigit() else args.mic
    spk_dev = int(args.speaker) if args.speaker and args.speaker.isdigit() else args.speaker

    satellite = VoiceSatellite(
        node_id=args.node_id,
        server_url=args.server,
        zone=args.zone,
        mic_device=mic_dev,
        speaker_device=spk_dev,
        model_size=args.model_size
    )

    sys.exit(satellite.run(headless=args.headless))


if __name__ == "__main__":
    main()
