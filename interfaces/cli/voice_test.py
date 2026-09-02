print("\n[1/4] ⏳ Initialisiere Python & Umgebung...", flush=True)
import logging
import os
import sys

# Add parent dir to path so we can import core/engines
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

print("[2/4] 📦 Lade Module (faster-whisper, LiteLLM, PyTorch)...", flush=True)
from engines.voice_in import VoiceInEngine
from engines.voice_out import VoiceOutEngine
from brain.planner import Planner
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema
from tools.native.home_assistant import HomeAssistantMock, ha_call_schema
from dotenv import load_dotenv

print("[3/4] ⚙️ Initialisiere Tools & Einstellungen...", flush=True)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VoiceTest")

def main():
    logger.info("Starting Interactive Voice Pipeline Test")
    load_dotenv("config/.env")
    
    # Setup offline components (without Redis for simple local test)
    voice_in = VoiceInEngine(model_size="distil-large-v3", device="cpu", compute_type="int8")
    voice_out = VoiceOutEngine(use_kokoro=False) # Fallback to pyttsx3 or mock
    
    planner = Planner(model_name="ollama/qwen3.5:2b")
    
    registry = ToolRegistry()
    registry.register_tool("get_time", get_time, time_schema)
    ha = HomeAssistantMock("mock", "mock")
    registry.register_tool("home_assistant_call", ha.call_service, ha_call_schema)
    
    room_context = {"room_id": "room_office"}
    
    def on_speech_transcribed(text: str):
        print(f"\n{'='*50}")
        print(f"👤 USER: \"{text}\"")
        print(f"{'='*50}")
        
        # 1. Brain processes intent
        print(f"🧠 BRAIN: Querying Ollama (model: {planner.model_name})...")
        response = planner.process_intent(text, room_context, registry.get_all_schemas())
        
        # 2. Handle Action or Response
        if response["action"] == "tool_call":
            print(f"⚡ TOOL CALLED: {response['tool_name']} with args {response['arguments']}")
            tool_res = registry.execute_tool(response["tool_name"], response["arguments"])
            print(f"📋 TOOL RESULT: {tool_res}")
            out_text = "Die Aktion wurde erfolgreich durchgeführt."
        else:
            out_text = response["text"]
            
        print(f"🤖 CORE AI: \"{out_text}\"")
        
        # 3. TTS Playback
        print(f"🔊 SPEAKER: Playing response via TTS...")
        voice_out.synthesize_and_play(out_text)
        print(f"{'='*50}\n")

    print("\n" + "="*50)
    print("🚀 CORE AI - LOCAL VOICE PIPELINE READY")
    print(f"• STT Engine: faster-whisper (distil-large-v3, CPU int8)")
    print(f"• Reasoning Engine: {planner.model_name}")
    print(f"• TTS Engine: pyttsx3")
    print("="*50 + "\n")
    
    if voice_in.model is None:
        logger.error("Whisper model failed to load. Are dependencies installed?")
        return

    voice_in.start_listening(callback=on_speech_transcribed)
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping Voice Pipeline...")
        voice_in.stop_listening()

if __name__ == "__main__":
    main()
