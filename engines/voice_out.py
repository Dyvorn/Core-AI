import logging
import sounddevice as sd
import soundfile as sf
import os
# from kokoro_onnx import Kokoro # Uncomment when kokoro-onnx is installed

logger = logging.getLogger(__name__)

class VoiceOutEngine:
    """Handles Text-to-Speech (TTS) and audio playback"""
    
    def __init__(self, use_kokoro=False):
        self.use_kokoro = use_kokoro
        self.model = None
        if use_kokoro:
            try:
                # Placeholder for Kokoro initialization
                # self.model = Kokoro("path/to/kokoro-v0_19.onnx", "path/to/voices.bin")
                logger.info("Kokoro TTS initialized (Mocked)")
            except Exception as e:
                logger.error(f"Failed to load Kokoro: {e}")
        
    def synthesize_and_play(self, text: str, voice: str = "default"):
        """Synthesize text and play it immediately"""
        logger.info(f"Synthesizing text: '{text}' with voice '{voice}'")
        
        if self.use_kokoro and self.model:
            # samples, sample_rate = self.model.create(text, voice=voice, speed=1.0, lang="en-us")
            # sd.play(samples, sample_rate)
            # sd.wait()
            pass
        else:
            # For the structural prototype without a 1GB model download, 
            # we use a very basic mock or system TTS.
            # Using pyttsx3 as a fallback if installed, otherwise just log.
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
            except ImportError:
                logger.warning("pyttsx3 not installed, cannot play system audio. Please install it or configure Kokoro.")
                logger.info(f"[SPEAKER OUT]: {text}")

    def play_audio_file(self, file_path: str):
        """Play a pre-recorded audio file"""
        try:
            data, fs = sf.read(file_path, dtype='float32')
            sd.play(data, fs)
            sd.wait()
        except Exception as e:
            logger.error(f"Error playing audio file {file_path}: {e}")
