import os
import re
import sys
import logging
import queue
import threading
import collections
from typing import Callable, Optional, Dict, Any, List
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from core.schemas import TextEvent, SpatialContext
from core.bus import EventBus

logger = logging.getLogger("CoreAI.VoiceIn")

# Known Whisper hallucinations on silence / ambient room noise / repetitive audio
HALLUCINATION_PATTERNS = [
    r"^\s*$",
    r"^[\.\,\!\?\:\;\-\–\—\s]+$",
    r"^(you|thank you|thank you for watching|thanks for watching|subscribe|subtitles|music|applause|silence|whispering)[\.\!\?]?$",
    r"^(danke|vielen dank fürs zuschauen|vielen dank|abonnieren|untertitel|musik|stille|geflüster)[\.\!\?]?$",
    r"^\[(music|applause|laughter|noise|silence|whispering|blank_audio|cheering)\]$",
    r"^\((music|applause|laughter|noise|silence|whispering|blank_audio|cheering)\)$",
    r"^(subtitles by|transcribed by|untertitel von|untertitelung durch).*",
    r"^(.)\1{4,}$",  # Single character repeated 5+ times
    r"^(\b\w+\b)(?:\s+\1){3,}[\.\!\?]?$",  # Word repeated 4+ times (e.g. "yeah yeah yeah yeah")
]


def resample_audio(chunk: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
    """
    Fast linear interpolation resampling from native hardware rate to 16kHz for Whisper.
    Pure NumPy implementation without heavy external dependencies.
    """
    if orig_sr == target_sr or len(chunk) == 0:
        return chunk.astype(np.float32)

    duration = len(chunk) / float(orig_sr)
    target_length = int(round(duration * target_sr))
    if target_length <= 0:
        return np.array([], dtype=np.float32)

    orig_indices = np.linspace(0, len(chunk) - 1, num=len(chunk))
    target_indices = np.linspace(0, len(chunk) - 1, num=target_length)
    return np.interp(target_indices, orig_indices, chunk).astype(np.float32)


class VoiceInEngine:
    """
    High-Performance Voice Capture, Dynamic VAD, and Speech-to-Text (STT) Engine:
    - Auto-detects native hardware sample rate (WASAPI / DirectSound 44.1/48kHz) with fast resampling
    - Dynamic RMS energy calculation with adaptive ambient noise floor tracking
    - Pre-roll audio buffer preserving the onset of speech ('Hey Core...')
    - Resilient STT model loading with automatic cascade fallback (large -> small -> base -> tiny)
    - Whisper hallucination and ambient noise suppression
    - Direct integration with Core AI EventBus, Discourse Engine, and Gateway
    """

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: str = "auto",
        compute_type: str = "default",
        input_device: Optional[Any] = None,
        sample_rate: int = 16000,
        silence_threshold: float = 0.018,
        silence_duration_chunks: int = 8,
        language: Optional[str] = None
    ):
        # Allow environment override for model and language
        env_model = os.getenv("CORE_STT_MODEL")
        env_lang = os.getenv("CORE_STT_LANGUAGE")

        self.model_size = model_size or env_model or "distil-large-v3"
        self.language = language or env_lang or None
        self.requested_device = device
        self.requested_compute = compute_type
        self.input_device = input_device if input_device is not None else os.getenv("CORE_MIC_DEVICE")
        self.sample_rate = sample_rate  # Target Whisper rate (16000 Hz)
        self.hw_samplerate = sample_rate  # Will be set to actual hardware rate upon opening stream

        # VAD & Energy parameters
        self.silence_threshold = silence_threshold
        self.min_speech_threshold = 0.008
        self.ambient_noise_floor = 0.005  # Adaptive baseline, updated during quiet intervals
        self.silence_duration_chunks = silence_duration_chunks
        self.pre_roll_chunks = 4  # Keep ~400ms pre-speech audio to prevent clipping first syllable

        # State tracking
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.callback: Optional[Callable[[str], None]] = None
        self.state_callback: Optional[Callable[[str], None]] = None
        self.current_state = "idle"  # idle, listening, recording, transcribing

        # Auto-configure optimal device and compute
        self.device, self.compute_type = self._determine_hardware(device, compute_type)
        self.model = self._load_model_with_fallback(self.model_size, self.device, self.compute_type)

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

    def _load_model_with_fallback(self, requested_model: str, device: str, compute_type: str) -> Optional[WhisperModel]:
        """Attempts loading requested whisper model; falls back gracefully down the model tier if OOM/unavailable."""
        cascade = [requested_model]
        for fallback in ["small", "base", "tiny"]:
            if fallback not in cascade:
                cascade.append(fallback)

        for candidate in cascade:
            logger.info(f"Loading faster-whisper STT ('{candidate}', device={device}, compute={compute_type})...")
            try:
                model = WhisperModel(candidate, device=device, compute_type=compute_type)
                self.model_size = candidate
                return model
            except Exception as e:
                logger.warning(f"Failed to load whisper model '{candidate}' on {device}: {e}")
                if device != "cpu":
                    try:
                        logger.info(f"Retrying '{candidate}' on CPU (int8)...")
                        model = WhisperModel(candidate, device="cpu", compute_type="int8")
                        self.device = "cpu"
                        self.compute_type = "int8"
                        self.model_size = candidate
                        return model
                    except Exception as e_cpu:
                        logger.warning(f"CPU fallback for '{candidate}' also failed: {e_cpu}")

        logger.error("All whisper model loading attempts failed.")
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

    def _resample(self, chunk: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
        """Instance method wrapper for audio resampling."""
        return resample_audio(chunk, orig_sr, target_sr)

    def start_listening(self, callback: Callable[[str], None], state_callback: Optional[Callable[[str], None]] = None):
        """Starts a background thread capturing audio and transcribing speech."""
        if self.is_recording:
            logger.warning("VoiceInEngine is already recording.")
            return

        self.callback = callback
        self.state_callback = state_callback
        self.is_recording = True

        # Query hardware properties of selected device
        dev_info = None
        try:
            if self.input_device is not None:
                # Handle int or str name
                try:
                    dev_idx = int(self.input_device)
                    dev_info = sd.query_devices(dev_idx)
                except (ValueError, TypeError):
                    dev_info = sd.query_devices(self.input_device)
            else:
                dev_info = sd.query_devices(kind="input")
        except Exception as q_err:
            logger.debug(f"Device query notice: {q_err}")

        # Determine native hardware sample rate to prevent PaErrorCode -9997
        if dev_info and "default_samplerate" in dev_info and dev_info["default_samplerate"]:
            self.hw_samplerate = int(dev_info["default_samplerate"])
        else:
            self.hw_samplerate = 16000

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"Audio stream status: {status}")
            if self.is_recording:
                chunk = indata.copy()
                # Downmix multichannel to mono
                if chunk.ndim > 1 and chunk.shape[1] > 1:
                    mono = np.mean(chunk, axis=1)
                else:
                    mono = chunk.flatten()

                # Resample to 16kHz if hardware sample rate differs
                if self.hw_samplerate != self.sample_rate:
                    mono = self._resample(mono, self.hw_samplerate, self.sample_rate)

                self.audio_queue.put(mono)

        # Candidate configurations to attempt: native rate first, then standard rates
        sample_rate_candidates = [self.hw_samplerate]
        for fallback_rate in [48000, 44100, 16000]:
            if fallback_rate not in sample_rate_candidates:
                sample_rate_candidates.append(fallback_rate)

        stream_opened = False
        last_error = None

        for rate in sample_rate_candidates:
            try:
                block_size = int(rate * 0.1)  # 100ms frames
                self.stream = sd.InputStream(
                    device=self.input_device,
                    samplerate=rate,
                    channels=1,
                    callback=audio_callback,
                    dtype="float32",
                    blocksize=block_size
                )
                self.stream.start()
                self.hw_samplerate = rate
                stream_opened = True
                logger.info(f"Audio input stream successfully opened at {rate} Hz (target: {self.sample_rate} Hz).")
                break
            except Exception as e:
                last_error = e
                logger.debug(f"Could not open input stream at {rate} Hz: {e}")

        if not stream_opened:
            logger.warning(f"Failed to open audio stream on device {self.input_device} ({last_error}). Attempting device fallback...")
            try:
                valid_inputs = self.list_input_devices()
                if not valid_inputs:
                    raise RuntimeError("No audio input devices found on this system.")
                fallback_idx = valid_inputs[0]["index"]
                fallback_rate = int(valid_inputs[0].get("default_samplerate", 16000))
                logger.info(f"Falling back to input device {fallback_idx} ({valid_inputs[0]['name']} @ {fallback_rate} Hz)")
                self.input_device = fallback_idx
                self.hw_samplerate = fallback_rate

                self.stream = sd.InputStream(
                    device=fallback_idx,
                    samplerate=fallback_rate,
                    channels=1,
                    callback=audio_callback,
                    dtype="float32",
                    blocksize=int(fallback_rate * 0.1)
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
        pre_roll = collections.deque(maxlen=self.pre_roll_chunks)
        buffer = []
        silence_chunks = 0
        is_speech_active = False

        while self.is_recording:
            try:
                chunk = self.audio_queue.get(timeout=0.1)

                # Compute RMS and peak energy metrics
                rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0
                peak = float(np.max(np.abs(chunk))) if len(chunk) > 0 else 0.0

                # Adaptive threshold based on moving room noise floor
                adaptive_threshold = max(self.min_speech_threshold, self.ambient_noise_floor * 2.2)

                if not is_speech_active:
                    pre_roll.append(chunk)
                    # Smoothly update ambient noise floor during quiet intervals
                    self.ambient_noise_floor = 0.95 * self.ambient_noise_floor + 0.05 * rms

                bars = int(min(rms / 0.05, 1.0) * 10)
                meter = "█" * bars + "░" * (10 - bars)

                # Trigger speech activation if RMS exceeds adaptive threshold or peak is distinctly above silence threshold
                if rms >= adaptive_threshold or peak >= self.silence_threshold:
                    if not is_speech_active:
                        is_speech_active = True
                        self._set_state("recording")
                        # Prepend pre-roll buffer so onset syllables ("Hey", "Core") are fully captured
                        buffer = list(pre_roll)
                    buffer.append(chunk)
                    silence_chunks = 0
                else:
                    if is_speech_active:
                        buffer.append(chunk)
                        silence_chunks += 1

                # Dynamic terminal meter display
                status_text = f"🗣️ RECORDING ({len(buffer)})" if is_speech_active else "👂 LISTENING..."
                sys.stdout.write(f"\r[🎙️ MIC] [{meter}] rms: {rms:.4f} (noise: {self.ambient_noise_floor:.4f}) | {status_text:<30}")
                sys.stdout.flush()

                # Trigger transcription once silence threshold is reached after active speech
                if is_speech_active and silence_chunks >= self.silence_duration_chunks and len(buffer) >= 6:
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    sys.stdout.flush()

                    audio_data = np.concatenate(buffer).flatten()
                    duration_sec = len(audio_data) / self.sample_rate
                    buffer = []
                    silence_chunks = 0
                    is_speech_active = False
                    pre_roll.clear()
                    self._set_state("transcribing")

                    # Process audio if speech was at least ~250ms
                    if self.model and len(audio_data) >= int(self.sample_rate * 0.25):
                        print(f"\n[⏳ VAD] Speech ended ({duration_sec:.1f}s). Transcribing with faster-whisper...")
                        text = self.transcribe_audio_array(audio_data, language=self.language)

                        if text and not self.is_hallucination(text):
                            print(f"[📝 STT] Result: \"{text}\"")
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

    def transcribe_audio_array(self, audio_data: np.ndarray, language: Optional[str] = None) -> str:
        """Direct transcription of float32 16kHz audio array using Faster-Whisper."""
        if not self.model or len(audio_data) == 0:
            return ""
        try:
            segments, info = self.model.transcribe(
                audio_data,
                beam_size=5,
                language=language or self.language,
                vad_filter=True,
                initial_prompt="Core AI, Hey Core, Dyvorn, Studio, Office, Kitchen, Living Room"
            )
            return " ".join([seg.text for seg in segments]).strip()
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return ""

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
        segments, info = self.model.transcribe(file_path, beam_size=5, language=self.language)
        text = " ".join([segment.text for segment in segments]).strip()
        return text if not self.is_hallucination(text) else ""

