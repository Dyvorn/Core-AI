import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import logging
import queue
import threading

logger = logging.getLogger(__name__)

class VoiceInEngine:
    """Handles VAD and STT (faster-whisper)"""
    
    def __init__(self, model_size="distil-large-v3", device="auto", compute_type="default"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = self._load_model(device, compute_type)
            
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.sample_rate = 16000

    def _load_model(self, device, compute_type):
        print(f"[4/4] 🤖 Lade faster-whisper STT ('{self.model_size}', device={device}, compute={compute_type})...", flush=True)
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

    def start_listening(self, callback):
        """Starts a background thread to listen to the mic and process audio."""
        if self.is_recording:
            return
            
        self.is_recording = True
        self.callback = callback
        
        def audio_callback(indata, frames, time, status):
            if status:
                logger.warning(status)
            self.audio_queue.put(indata.copy())

        self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=audio_callback, dtype='float32')
        self.stream.start()
        
        self.process_thread = threading.Thread(target=self._process_audio)
        self.process_thread.start()
        logger.info("Voice input started listening")

    def stop_listening(self):
        self.is_recording = False
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        if hasattr(self, 'process_thread'):
            self.process_thread.join()
        logger.info("Voice input stopped")

    def _process_audio(self):
        buffer = []
        silence_threshold = 0.02  # Threshold for speech vs background noise
        silence_chunks = 0
        is_speech_active = False
        
        while self.is_recording:
            try:
                # Get audio chunks
                chunk = self.audio_queue.get(timeout=0.1)
                buffer.append(chunk)
                
                # Calculate audio level
                peak = np.max(np.abs(chunk))
                # Visual VU Meter bar (10 characters)
                bars = int(min(peak / 0.1, 1.0) * 10)
                meter = "█" * bars + "░" * (10 - bars)
                
                if peak >= silence_threshold:
                    if not is_speech_active and len(buffer) > 2:
                        is_speech_active = True
                    silence_chunks = 0
                else:
                    silence_chunks += 1
                
                # Live dynamic terminal output on the same line
                if is_speech_active:
                    status_text = f"🗣️ RECORDING SPEECH (chunks: {len(buffer)})"
                else:
                    status_text = "👂 LISTENING..."
                
                import sys
                sys.stdout.write(f"\r[🎙️ MIC] [{meter}] peak: {peak:.3f} | {status_text:<35}")
                sys.stdout.flush()
                    
                # If we were speaking and now detected silence for enough chunks, transcribe
                if is_speech_active and silence_chunks > 12 and len(buffer) > 15:
                    import sys
                    sys.stdout.write("\r" + " " * 75 + "\r") # Clear the line
                    sys.stdout.flush()
                    
                    audio_data = np.concatenate(buffer).flatten()
                    duration_sec = len(audio_data) / self.sample_rate
                    buffer = []
                    silence_chunks = 0
                    is_speech_active = False
                    
                    if self.model:
                        print(f"\n[⏳ VAD] Speech ended. Transcribing {duration_sec:.1f}s audio with faster-whisper...")
                        try:
                            segments, info = self.model.transcribe(audio_data, beam_size=5, language=None, vad_filter=True)
                            text = " ".join([segment.text for segment in segments]).strip()
                        except Exception as transcribe_err:
                            if "cublas" in str(transcribe_err).lower() or "cuda" in str(transcribe_err).lower():
                                logger.warning(f"CUDA execution failed ({transcribe_err}). Switching to CPU (int8)...")
                                self.device = "cpu"
                                self.compute_type = "int8"
                                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                                segments, info = self.model.transcribe(audio_data, beam_size=5, language=None, vad_filter=True)
                                text = " ".join([segment.text for segment in segments]).strip()
                            else:
                                raise transcribe_err

                        if text:
                            print(f"[📝 STT] Result (lang={info.language}): \"{text}\"")
                            if hasattr(self, 'callback'):
                                self.callback(text)
                        else:
                            print("[📝 STT] (No distinct speech detected / filtered as noise)")
                                
                        # Clear old audio queue accumulated during transcribe time
                        with self.audio_queue.mutex:
                            self.audio_queue.queue.clear()
                                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"\nError in audio processing: {e}")
                
    def transcribe_file(self, file_path: str) -> str:
        """Helper for testing without mic"""
        if not self.model:
            return ""
        segments, info = self.model.transcribe(file_path, beam_size=5)
        return " ".join([segment.text for segment in segments]).strip()
