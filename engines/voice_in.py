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

INTERRUPT_PATTERN = re.compile(
    r"^(?:no[,\s]+|nein[,\s]+|hey[,\s]+|warte[,\s]+)*(?:stop|stopp|halt|cancel|abbrechen|warte|wait|quiet|leise|ruhe|hör auf|shut up|pause)\b",
    re.IGNORECASE
)


def resample_audio(chunk: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
    """
    Fast linear interpolation resampling from native hardware rate to 16kHz for Whisper.
    Pure NumPy implementation without heavy external dependencies.
    """
    if orig_sr == target_sr or len(chunk) == 0:
        return chunk.astype(np.float32)

    duration = len(chunk) / float(orig_sr)
    target_length = round(duration * target_sr)
    if target_length <= 0:
        return np.array([], dtype=np.float32)

    orig_indices = np.linspace(0, len(chunk) - 1, num=len(chunk))
    target_indices = np.linspace(0, len(chunk) - 1, num=target_length)
    return np.interp(target_indices, orig_indices, chunk).astype(np.float32)


class VoiceInEngine:
    """
    High-Performance Voice Capture, Silero VAD, and Speech-to-Text (STT) Engine:
    - Neural Silero VAD (ONNX) for sub-400ms speech offset detection and noise rejection
    - Auto-detects native hardware sample rate (WASAPI / DirectSound 44.1/48kHz) with fast resampling
    - Ultra-low latency Faster-Whisper decoding (beam_size=1 greedy mode)
    - Full speech barge-in and verbal interruption support ("Stop", "No no stop", "Stopp")
    - Whisper hallucination and ambient noise suppression
    - Decoupled asynchronous callback dispatch preserving non-blocking mic capture
    """

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: str = "auto",
        compute_type: str = "default",
        input_device: Optional[Any] = None,
        sample_rate: int = 16000,
        silence_threshold: float = 0.015,
        silence_duration_chunks: int = 5,
        language: Optional[str] = None,
        show_meter: bool = False,
        voice_out: Optional[Any] = None
    ):
        # Allow environment override for model and language
        env_model = os.getenv("CORE_STT_MODEL")
        env_lang = os.getenv("CORE_STT_LANGUAGE")

        # Default model size (configurable, default small/base)
        self.model_size = model_size or env_model or "small"
        self.language = language or env_lang or None
        self.requested_device = device
        self.requested_compute = compute_type
        self.input_device = input_device if input_device is not None else os.getenv("CORE_MIC_DEVICE")
        self.sample_rate = sample_rate  # Target Whisper rate (16000 Hz)
        self.hw_samplerate = sample_rate  # Will be set to actual hardware rate upon opening stream
        self.show_meter = show_meter or (os.getenv("CORE_VOICE_METER", "0").lower() in ("1", "true"))

        # Interruption and voice output linkage
        self.voice_out = voice_out
        self.on_interrupt: Optional[Callable[[str], None]] = None

        # VAD & Energy parameters
        self.silence_threshold = silence_threshold
        self.min_speech_threshold = 0.008
        self.ambient_noise_floor = 0.005  # Adaptive baseline, updated during quiet intervals
        self.silence_duration_chunks = silence_duration_chunks  # Trailing silence frames (~350ms)
        self.max_speech_chunks = 200  # Safety cutoff (~6.5s) to prevent infinite accumulation
        self.pre_roll_chunks = 10  # Pre-roll ~320ms to capture opening syllables cleanly

        # State tracking
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.callback: Optional[Callable[[str], None]] = None
        self.state_callback: Optional[Callable[[str], None]] = None
        self.current_state = "idle"  # idle, listening, recording, transcribing

        # Neural Silero VAD initialization
        self.vad_model = None
        try:
            from faster_whisper.vad import get_vad_model
            self.vad_model = get_vad_model()
            logger.info("Silero VAD model loaded for neural voice activity detection.")
        except Exception as vad_err:
            logger.warning(f"Silero VAD model unavailable ({vad_err}). Falling back to adaptive energy VAD.")
            self.vad_model = None

        # Auto-configure optimal device and compute
        self.device, self.compute_type = self._determine_hardware(device, compute_type)
        self.model = self._load_model_with_fallback(self.model_size, self.device, self.compute_type)

    def register_voice_out(self, voice_out: Any, on_interrupt: Optional[Callable[[str], None]] = None):
        """Wires VoiceOutEngine to enable instant speech interruption and barge-in."""
        self.voice_out = voice_out
        self.on_interrupt = on_interrupt

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
        # distil-large-v3 and distil models are strictly English-only.
        # If language is not explicitly set to 'en', upgrade to multilingual 'small'
        if ("distil" in requested_model.lower()) and self.language != "en":
            logger.info("Notice: 'distil-large-v3' is English-only. Upgrading to multilingual 'small' model for fluent German and English speech.")
            requested_model = "small"

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

    def _dispatch_callback(self, text: str):
        """Dispatches speech callback asynchronously so audio capture loop never blocks."""
        if self.callback:
            threading.Thread(target=self._run_callback_safe, args=(text,), daemon=True).start()

    def _run_callback_safe(self, text: str):
        try:
            if self.callback:
                self.callback(text)
        except Exception as cb_err:
            logger.error(f"Error in speech callback: {cb_err}", exc_info=True)

    def _process_audio(self):
        pre_roll = collections.deque(maxlen=self.pre_roll_chunks)
        buffer = []
        silence_frames = 0
        is_speech_active = False
        frame_accumulator = []
        FRAME_SIZE = 512  # 32ms at 16kHz for Silero VAD and fast energy checks

        while self.is_recording:
            try:
                raw_chunk = self.audio_queue.get(timeout=0.1)
                if len(raw_chunk) == 0:
                    continue

                frame_accumulator.extend(raw_chunk)

                # Process in 512-sample (32ms) frames
                while len(frame_accumulator) >= FRAME_SIZE and self.is_recording:
                    frame = np.array(frame_accumulator[:FRAME_SIZE], dtype=np.float32)
                    frame_accumulator = frame_accumulator[FRAME_SIZE:]

                    rms = float(np.sqrt(np.mean(frame**2))) if len(frame) > 0 else 0.0
                    peak = float(np.max(np.abs(frame))) if len(frame) > 0 else 0.0

                    # Dynamic thresholds for fallback energy VAD
                    start_threshold = max(self.min_speech_threshold, self.ambient_noise_floor * 2.2)
                    sustain_threshold = max(self.min_speech_threshold * 0.75, self.ambient_noise_floor * 1.35)

                    is_bot_speaking = bool(self.voice_out and getattr(self.voice_out, "is_speaking", False))

                    # 1. Neural Silero VAD speech probability evaluation
                    is_speech = False
                    is_sustain = False
                    if self.vad_model is not None:
                        try:
                            speech_prob = float(self.vad_model(frame)[0])
                            # During bot speech, require slightly higher confidence to reject acoustic bleed
                            speech_gate = 0.55 if is_bot_speaking else 0.45
                            sustain_gate = 0.35 if is_bot_speaking else 0.25
                            is_speech = (speech_prob >= speech_gate)
                            is_sustain = (speech_prob >= sustain_gate)
                        except Exception as vad_e:
                            logger.debug(f"Silero VAD inference exception ({vad_e}), using RMS")
                            is_speech = (rms >= start_threshold or (rms >= self.min_speech_threshold and peak >= self.silence_threshold * 1.6))
                            is_sustain = (rms >= sustain_threshold)
                    else:
                        is_speech = (rms >= start_threshold or (rms >= self.min_speech_threshold and peak >= self.silence_threshold * 1.6))
                        is_sustain = (rms >= sustain_threshold)

                    if not is_speech_active:
                        pre_roll.append(frame)
                        self.ambient_noise_floor = 0.95 * self.ambient_noise_floor + 0.05 * rms
                        self.ambient_noise_floor = max(0.001, min(self.ambient_noise_floor, 0.03))

                        if is_speech:
                            is_speech_active = True
                            self._set_state("recording")
                            buffer = list(pre_roll)
                            buffer.append(frame)
                            silence_frames = 0
                    else:
                        buffer.append(frame)
                        if is_sustain:
                            silence_frames = 0
                        else:
                            silence_frames += 1

                    # Dynamic terminal meter display (only if show_meter is enabled)
                    if self.show_meter:
                        bars = int(min(rms / 0.05, 1.0) * 10)
                        meter = "█" * bars + "░" * (10 - bars)
                        status_text = f"🗣️ RECORDING ({len(buffer)})" if is_speech_active else "👂 LISTENING..."
                        sys.stdout.write(f"\r[🎙️ MIC] [{meter}] rms: {rms:.4f} (noise: {self.ambient_noise_floor:.4f}) | {status_text:<30}")
                        sys.stdout.flush()

                    # Trigger transcription: ~350ms of trailing silence (11 frames * 32ms) OR max speech frames (~6.4s)
                    silence_cutoff_frames = 11 if self.vad_model is not None else max(5, self.silence_duration_chunks * 2)
                    speech_cutoff = (silence_frames >= silence_cutoff_frames) or (len(buffer) >= self.max_speech_chunks)

                    if is_speech_active and speech_cutoff and len(buffer) >= 8:
                        if self.show_meter:
                            sys.stdout.write("\r" + " " * 80 + "\r")
                            sys.stdout.flush()

                        audio_data = np.concatenate(buffer).flatten()
                        duration_sec = len(audio_data) / float(self.sample_rate)
                        buffer = []
                        silence_frames = 0
                        is_speech_active = False
                        pre_roll.clear()
                        self._set_state("transcribing")

                        # Transcribe with Whisper (beam_size=1 greedy decoding)
                        if self.model and len(audio_data) >= int(self.sample_rate * 0.25):
                            print(f"\n[⏳ VAD] Speech ended ({duration_sec:.1f}s). Transcribing with faster-whisper ({self.model_size})...")
                            text = self.transcribe_audio_array(audio_data, language=self.language, beam_size=1)
                            clean_text = text.strip()

                            if clean_text and not self.is_hallucination(clean_text):
                                is_interrupt = bool(INTERRUPT_PATTERN.search(clean_text.lower()))
                                is_currently_speaking = bool(self.voice_out and getattr(self.voice_out, "is_speaking", False))

                                if is_interrupt:
                                    if self.voice_out:
                                        self.voice_out.interrupt()
                                    if self.on_interrupt:
                                        try:
                                            self.on_interrupt(clean_text)
                                        except Exception as ie:
                                            logger.debug(f"Error in on_interrupt: {ie}")
                                    print(f"\n[🛑 INTERRUPTED] Playback halted by operator: \"{clean_text}\"")

                                    # Check for trailing directive after interrupt phrase (e.g. "Stop, wie spät ist es?")
                                    trailing_cmd = INTERRUPT_PATTERN.sub("", clean_text).strip(" ,.!?")
                                    if trailing_cmd and len(trailing_cmd) > 2:
                                        self._dispatch_callback(trailing_cmd)
                                else:
                                    if is_currently_speaking:
                                        if self.voice_out:
                                            self.voice_out.interrupt()
                                        print(f"\n[🛑 BARGE-IN] Interrupted playback for new command: \"{clean_text}\"")

                                    print(f"[📝 STT] Result: \"{clean_text}\"")
                                    self._dispatch_callback(clean_text)
                            else:
                                if clean_text:
                                    print(f"[📝 STT] (Filtered ambient noise/hallucination: '{clean_text}')")

                        # Drain pending raw chunks accumulated during transcription
                        with self.audio_queue.mutex:
                            self.audio_queue.queue.clear()
                        frame_accumulator.clear()

                        self._set_state("listening")

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error during audio processing: {e}", exc_info=True)

    def transcribe_audio_array(self, audio_data: np.ndarray, language: Optional[str] = None, beam_size: int = 1) -> str:
        """Direct transcription of float32 16kHz audio array using Faster-Whisper."""
        if not self.model or len(audio_data) == 0:
            return ""
        try:
            target_lang = language or self.language
            initial_prompt = (
                "Core AI, Gemini, Hey Core, Dyvorn, Studio, Office, Kitchen, Living Room. "
                "Deutsch und Englisch: Wie spät ist es, Uhrzeit, stop, halt, abbrechen, Wetter, Systemstatus, Erinnerung, Notizen, Licht, Lautstärke."
            )
            segments, info = self.model.transcribe(
                audio_data,
                beam_size=beam_size,
                temperature=0.0,
                best_of=1,
                language=target_lang,
                vad_filter=False,  # High-precision Silero VAD was already applied in capture loop
                initial_prompt=initial_prompt
            )
            detected_lang = getattr(info, "language", "unknown")
            lang_prob = getattr(info, "language_probability", 1.0)
            logger.debug(f"Detected speech language '{detected_lang}' (probability: {lang_prob:.2f})")
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

