import io
import os
import re
import sys
import logging
import queue
import threading
import asyncio
from typing import Optional, Any, Dict, List, Tuple
import numpy as np
import sounddevice as sd
import soundfile as sf

from core.schemas import BaseEvent, TextEvent, TTSRequestEvent
from core.bus import EventBus

logger = logging.getLogger("CoreAI.VoiceOut")

# Default Neural Voices
DEFAULT_DE_VOICE = "de-DE-FlorianMultilingualNeural"
DEFAULT_EN_VOICE = "en-US-ChristopherNeural"

GERMAN_INDICATORS = {
    "der", "die", "das", "ein", "eine", "einer", "und", "ist", "sind",
    "nicht", "hallo", "guten", "morgen", "tag", "abend", "uhr",
    "aktion", "abgeschlossen", "fehler", "ergebnis", "zeit", "bitte", "danke",
    "wie", "spät", "zeige", "wer", "was"
}

ENGLISH_INDICATORS = {
    "the", "a", "an", "is", "are", "and", "not", "hello", "hi", "good",
    "morning", "what", "time", "action", "completed", "error", "result",
    "please", "thanks", "who", "show", "current", "status", "how"
}

class VoiceOutEngine:
    """
    High-Fidelity Text-to-Speech (TTS) & Audio Playback Engine:
    - Primary: Microsoft Edge Neural TTS (`edge-tts`) with 300+ ultra-realistic voices
    - Automatic offline fallback to local system TTS (`pyttsx3`)
    - In-memory audio decoding without disk clutter
    - Non-blocking sequential speech queue (prevents voice overlap)
    - Direct subscription to Core AI EventBus 'tts_events'
    """

    def __init__(
        self,
        default_voice: str = "auto",
        output_device: Optional[Any] = None,
        rate: str = "+0%",
        volume: str = "+0%"
    ):
        self.default_voice = default_voice
        self.output_device = output_device
        self.rate = rate
        self.volume = volume

        # Sequential playback worker thread
        self.speech_queue = queue.Queue()
        self._is_running = True
        self.is_speaking = False
        self.playback_thread = threading.Thread(target=self._playback_worker, daemon=True)
        self.playback_thread.start()

        # Optional bus reference for speech lifecycle events
        self.bus: Optional[EventBus] = None

    def list_output_devices(self) -> List[Dict[str, Any]]:
        """Lists all audio output devices available on the host system."""
        devices = []
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_output_channels", 0) > 0:
                    devices.append({
                        "index": idx,
                        "name": dev.get("name"),
                        "channels": dev.get("max_output_channels"),
                        "default_samplerate": dev.get("default_samplerate")
                    })
        except Exception as e:
            logger.error(f"Failed to query output devices: {e}")
        return devices

    def detect_language(self, text: str) -> str:
        """Heuristic language detection between German (de) and English (en)."""
        # Look for German umlauts
        if any(c in text for c in ["ä", "ö", "ü", "Ä", "Ö", "Ü", "ß"]):
            return "de"

        words = set(re.findall(r"\b\w+\b", text.lower()))
        score_de = len(words.intersection(GERMAN_INDICATORS))
        score_en = len(words.intersection(ENGLISH_INDICATORS))

        if score_de > score_en:
            return "de"
        if score_en > score_de:
            return "en"
        return "de" if score_de > 0 else "en"

    def select_voice(self, text: str, voice_override: Optional[str] = None) -> str:
        """Determines the neural voice based on override or detected language."""
        if voice_override and voice_override != "default" and voice_override != "auto":
            return voice_override

        if self.default_voice not in ("auto", "default", None):
            return self.default_voice

        lang = self.detect_language(text)
        return DEFAULT_DE_VOICE if lang == "de" else DEFAULT_EN_VOICE

    async def _synthesize_edge_tts(self, text: str, voice: str) -> Tuple[np.ndarray, int]:
        """Synthesizes text using edge-tts directly into an in-memory audio array."""
        import edge_tts
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=self.rate, volume=self.volume)
        audio_buffer = bytearray()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])

        if not audio_buffer:
            raise RuntimeError("Edge-TTS returned empty audio stream")

        # Decode MP3 bytes in-memory using soundfile
        audio_data, sample_rate = sf.read(io.BytesIO(audio_buffer), dtype="float32")
        return audio_data, sample_rate

    def _fallback_pyttsx3(self, text: str):
        """Offline fallback playback using local system TTS."""
        logger.info(f"[pyttsx3 Offline TTS] Speaking: '{text}'")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.error(f"pyttsx3 playback failed: {e}")
            print(f"\n[🔊 SPEAKER OUT (MUTE FALLBACK)]: {text}\n")

    def synthesize_and_play(
        self,
        text: str,
        voice: Optional[str] = None,
        device: Optional[Any] = None,
        blocking: bool = True
    ):
        """
        Enqueues text for synthesis and playback.
        If blocking=True (default for direct calls), waits until this specific sentence finishes playing.
        """
        if not text or not text.strip():
            return

        done_event = threading.Event() if blocking else None
        item = {
            "text": text.strip(),
            "voice": voice,
            "device": device or self.output_device,
            "done_event": done_event
        }
        self.speech_queue.put(item)

        if blocking and done_event:
            done_event.wait()

    def _playback_worker(self):
        """Worker thread processing speech items sequentially."""
        while self._is_running:
            try:
                item = self.speech_queue.get(timeout=0.2)
                if item is None:
                    break

                text = item["text"]
                voice = self.select_voice(text, item["voice"])
                target_device = item["device"]
                done_event = item["done_event"]

                self.is_speaking = True
                self._notify_speech_state(True, text)
                logger.info(f"Synthesizing speech with voice '{voice}': '{text[:60]}...'")

                played_successfully = False

                # 1. Primary: Edge Neural TTS
                try:
                    # Run async synthesis
                    audio_data, sample_rate = asyncio.run(self._synthesize_edge_tts(text, voice))
                    
                    # Play through sounddevice
                    sd.play(audio_data, samplerate=sample_rate, device=target_device)
                    sd.wait()
                    played_successfully = True
                except Exception as e:
                    logger.warning(f"Edge-TTS synthesis or playback failed ({e}). Falling back to pyttsx3...")

                # 2. Offline Fallback: pyttsx3
                if not played_successfully:
                    try:
                        self._fallback_pyttsx3(text)
                        played_successfully = True
                    except Exception as e2:
                        logger.error(f"Offline fallback also failed: {e2}")

                self.is_speaking = False
                self._notify_speech_state(False, text)

                if done_event:
                    done_event.set()

                self.speech_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Unexpected error in TTS playback worker: {e}", exc_info=True)
                self.is_speaking = False

    def _notify_speech_state(self, is_speaking: bool, text: str):
        """Optionally publishes speech lifecycle events onto the EventBus."""
        if not self.bus:
            return
        try:
            state_label = "speaking_started" if is_speaking else "speaking_finished"
            event = BaseEvent(
                source_node="voice_out",
                room_id="local_audio"
            )
            # Publish event to 'voice_state'
            self.bus.publish("voice_state", event)
        except Exception as e:
            logger.debug(f"Could not publish voice_state event: {e}")

    def attach_to_bus(self, bus: EventBus, channel: str = "tts_events"):
        """Subscribes this engine to the central EventBus for incoming speech events."""
        self.bus = bus

        def on_tts_event(data: dict):
            try:
                # Handle either TextEvent or TTSRequestEvent payloads
                text = data.get("text")
                voice = data.get("voice")
                target_device = data.get("target_device")

                if text:
                    logger.info(f"Received TTS event from bus: '{text[:50]}...'")
                    self.synthesize_and_play(text=text, voice=voice, device=target_device, blocking=False)
            except Exception as e:
                logger.error(f"Error handling TTS event from bus: {e}", exc_info=True)

        bus.subscribe(channel, on_tts_event)
        logger.info(f"VoiceOutEngine attached to EventBus channel '{channel}'")

    def play_audio_file(self, file_path: str, device: Optional[Any] = None):
        """Plays a pre-recorded audio file directly through sounddevice."""
        try:
            data, fs = sf.read(file_path, dtype="float32")
            sd.play(data, fs, device=device or self.output_device)
            sd.wait()
        except Exception as e:
            logger.error(f"Error playing audio file {file_path}: {e}")

    def stop(self):
        """Shuts down the speech worker thread and stops playback."""
        self._is_running = False
        self.speech_queue.put(None)
        try:
            sd.stop()
        except Exception:
            pass
        if self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1.0)
        logger.info("VoiceOutEngine stopped.")
