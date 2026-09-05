import os
import re
import sys
import logging
import queue
import threading
from typing import Callable, Optional, Dict, Any, List
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from core.schemas import TextEvent, SpatialContext
from core.bus import EventBus

logger = logging.getLogger("CoreAI.VoiceIn")

# Known Whisper hallucinations on silence / ambient room noise
HALLUCINATION_PATTERNS = [
    r"^\s*$",
    r"^[\.\,\!\?\:\;\-\–\—\s]+$",
    r"^(you|thank you|thank you for watching|thanks for watching|subscribe|subtitles|music|applause)[\.\!\?]?$",
    r"^(danke|vielen dank fürs zuschauen|vielen dank|abonnieren|untertitel|musik)[\.\!\?]?$",
    r"^\[(music|applause|laughter|noise|silence|whispering)\]$",
    r"^\((music|applause|laughter|noise|silence|whispering)\)$",
    r"^(.)\1{4,}$",  # Single character repeated 5+ times
]

class VoiceInEngine:
    """
    High-Performance Voice Capture, Dynamic VAD, and Speech-to-Text (STT) Engine:
    - Automatically detects CPU vs. CUDA hardware acceleration
    - Robust audio device selection with fallback
    - Real-time VAD with dynamic VU metering
    - Whisper hallucination and ambient noise suppression
    - Direct integration with Core AI EventBus and Gateway
    """

    def __init__(
        self,
        model_size: str = "distil-large-v3",
        device: str = "auto",
        compute_type: str = "default",
        input_device: Optional[Any] = None,
        sample_rate: int = 16000,
        silence_threshold: float = 0.02,
        silence_duration_chunks: int = 12
    ):
        self.model_size = model_size
        self.requested_device = device
        self.requested_compute = compute_type
        self.input_device = input_device
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_duration_chunks = silence_duration_chunks

        # State tracking
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.callback: Optional[Callable[[str], None]] = None
        self.state_callback: Optional[Callable[[str], None]] = None
        self.current_state = "idle"  # idle, listening, recording, transcribing

        # Auto-configure optimal device and compute
        self.device, self.compute_type = self._determine_hardware(device, compute_type)
        self.model = self._load_model(self.device, self.compute_type)

    def _determine_hardware(self, req_device: str, req_compute: str) -> tuple[str, str]:
        """Auto-detects whether CUDA is genuinely available to avoid runtime cuBLAS errors."""
        if req_device == "cpu":
            compute = "int8" if req_compute == "default" else req_compute
            return "cpu", compute

        has_cuda = False
        try:
            import torch
            has_cuda = torch.cuda.is_available() and torch.cuda.device_count() > 0
        except Exception:
            has_cuda = False

        if has_cuda:
            compute = "float16" if req_compute == "default" else req_compute
            return "cuda", compute
        else:
            compute = "int8" if req_compute == "default" else req_compute
            return "cpu", compute

    def _load_model(self, device: str, compute_type: str) -> Optional[WhisperModel]:
        logger.info(f"Loading faster-whisper STT ('{self.model_size}', device={device}, compute={compute_type})...")
        try:
            return WhisperModel(self.model_size, device=device, compute_type=compute_type)
        except Exception as e:
            if device != "cpu":
                logger.warning(f"Failed to load whisper on {device} ({e}), falling back to CPU (int8)...")
                try:
                    self.device = "cpu"
                    self.compute_type = "int8"
                    return WhisperModel(self.model_size, device="cpu", compute_type="int8")
                except Exception as e2:
                    logger.error(f"Failed to load whisper model on CPU: {e2}")
            else:
                logger.error(f"Failed to load whisper model: {e}")
            return None

    def _set_state(self, new_state: str):
        if self.current_state != new_state:
            self.current_state = new_state
            if self.state_callback:
                try:
                    self.state_callback(new_state)
                except Exception as e:
                    logger.error(f"Error in state callback: {e}")

    def is_hallucination(self, text: str) -> bool:
        """Filters out typical whisper artifacts on quiet background noise."""
        clean = text.strip().lower()
        if len(clean) < 2:
            return True
        for pattern in HALLUCINATION_PATTERNS:
            if re.match(pattern, clean, re.IGNORECASE):
                return True
        return False

    def list_input_devices(self) -> List[Dict[str, Any]]:
        """Returns all audio input devices available on the host system."""
        devices = []
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "index": idx,
                        "name": dev.get("name"),
                        "channels": dev.get("max_input_channels"),
                        "default_samplerate": dev.get("default_samplerate")
                    })
        except Exception as e:
            logger.error(f"Failed to query audio devices: {e}")
        return devices

    def start_listening(self, callback: Callable[[str], None], state_callback: Optional[Callable[[str], None]] = None):
        """Starts a background thread capturing audio and transcribing speech."""
        if self.is_recording:
            logger.warning("VoiceInEngine is already recording.")
            return

        self.callback = callback
        self.state_callback = state_callback
        self.is_recording = True

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"Audio stream status: {status}")
            if self.is_recording:
                self.audio_queue.put(indata.copy())

        # Attempt to open input stream with selected or fallback device
        try:
            self.stream = sd.InputStream(
                device=self.input_device,
                samplerate=self.sample_rate,
                channels=1,
                callback=audio_callback,
                dtype="float32"
            )
            self.stream.start()
        except Exception as e:
            logger.warning(f"Failed to open audio stream on device {self.input_device} ({e}). Attempting device fallback...")
            try:
                # Find first valid input device
                valid_inputs = self.list_input_devices()
                if not valid_inputs:
                    raise RuntimeError("No audio input devices found on this system.")
                fallback_idx = valid_inputs[0]["index"]
                logger.info(f"Falling back to input device {fallback_idx}: {valid_inputs[0]['name']}")
                self.input_device = fallback_idx
                self.stream = sd.InputStream(
                    device=fallback_idx,
                    samplerate=self.sample_rate,
                    channels=1,
                    callback=audio_callback,
                    dtype="float32"
                )
                self.stream.start()
            except Exception as e2:
                self.is_recording = False
                logger.error(f"Cannot initialize audio capture: {e2}")
                raise RuntimeError(f"Audio input initialization failed: {e2}")

        self._set_state("listening")
        self.process_thread = threading.Thread(target=self._process_audio, daemon=True)
        self.process_thread.start()
        logger.info("VoiceInEngine listening stream started.")

    def stop_listening(self):
        """Cleanly stops recording and processing threads."""
        self.is_recording = False
        self._set_state("idle")

        if hasattr(self, "stream"):
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.debug(f"Error closing audio stream: {e}")

        if hasattr(self, "process_thread") and self.process_thread.is_alive():
            self.process_thread.join(timeout=1.0)

        # Clear remaining buffer
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()

        logger.info("VoiceInEngine listening stream stopped.")

    def _process_audio(self):
        buffer = []
        silence_chunks = 0
        is_speech_active = False

        while self.is_recording:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                buffer.append(chunk)

                peak = float(np.max(np.abs(chunk)))
                bars = int(min(peak / 0.1, 1.0) * 10)
                meter = "█" * bars + "░" * (10 - bars)

                if peak >= self.silence_threshold:
                    if not is_speech_active and len(buffer) > 2:
                        is_speech_active = True
                        self._set_state("recording")
                    silence_chunks = 0
                else:
                    silence_chunks += 1

                # Dynamic terminal meter display
                status_text = f"🗣️ RECORDING ({len(buffer)})" if is_speech_active else "👂 LISTENING..."
                sys.stdout.write(f"\r[🎙️ MIC] [{meter}] peak: {peak:.3f} | {status_text:<30}")
                sys.stdout.flush()

                # Trigger transcription once silence threshold is reached after active speech
                if is_speech_active and silence_chunks > self.silence_duration_chunks and len(buffer) > 12:
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    sys.stdout.flush()

                    audio_data = np.concatenate(buffer).flatten()
                    duration_sec = len(audio_data) / self.sample_rate
                    buffer = []
                    silence_chunks = 0
                    is_speech_active = False
                    self._set_state("transcribing")

                    if self.model and len(audio_data) >= self.sample_rate * 0.4:
                        print(f"\n[⏳ VAD] Speech ended ({duration_sec:.1f}s). Transcribing with faster-whisper...")
                        try:
                            segments, info = self.model.transcribe(
                                audio_data,
                                beam_size=5,
                                language=None,
                                vad_filter=True
                            )
                            text = " ".join([seg.text for seg in segments]).strip()
                        except Exception as transcribe_err:
                            logger.error(f"Whisper transcription error: {transcribe_err}")
                            text = ""

                        if text and not self.is_hallucination(text):
                            print(f"[📝 STT] Result (lang={info.language}): \"{text}\"")
                            if self.callback:
                                try:
                                    self.callback(text)
                                except Exception as cb_err:
                                    logger.error(f"Error in speech callback: {cb_err}", exc_info=True)
                        else:
                            print(f"[📝 STT] (Filtered ambient noise/hallucination: '{text}')")

                    # Drain old queue items accumulated during transcription
                    with self.audio_queue.mutex:
                        self.audio_queue.queue.clear()

                    self._set_state("listening")

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error during audio processing: {e}", exc_info=True)

    def bridge_to_event_bus(
        self,
        bus: EventBus,
        zone: str = "studio",
        device_type: str = "mic",
        state_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Convenience method: connects microphone capture directly to the central EventBus.
        Every transcribed statement is published to 'text_events' with accurate spatial context.
        """
        def on_transcription(text: str):
            event = TextEvent(
                source_node="local_mic",
                room_id=zone,
                spatial_context=SpatialContext(zone=zone, device_type=device_type),
                text=text
            )
            bus.publish("text_events", event)
            logger.info(f"Published transcribed text event from zone '{zone}': '{text}'")

        self.start_listening(callback=on_transcription, state_callback=state_callback)

    def transcribe_file(self, file_path: str) -> str:
        """Helper for unit tests and offline transcription."""
        if not self.model or not os.path.exists(file_path):
            return ""
        segments, info = self.model.transcribe(file_path, beam_size=5)
        text = " ".join([segment.text for segment in segments]).strip()
        return text if not self.is_hallucination(text) else ""
