import sys
import platform
import logging
import subprocess
from typing import Dict, Any

logger = logging.getLogger("CoreAI.MediaTools")

def media_control(action: str) -> Dict[str, Any]:
    """
    Simulates hardware media key presses for music/video playback and audio volume.
    Supported actions:
      - 'play_pause' / 'play' / 'pause': Toggle playback
      - 'next' / 'next_track': Skip to next track
      - 'previous' / 'prev_track': Return to previous track
      - 'volume_up': Increase master volume
      - 'volume_down': Decrease master volume
      - 'mute' / 'unmute': Toggle mute
    """
    clean_action = action.lower().strip()
    system = platform.system()

    if system == "Windows":
        try:
            import ctypes
            user32 = ctypes.windll.user32

            # Virtual Key Codes (VK) on Windows
            VK_MEDIA_NEXT_TRACK = 0xB0
            VK_MEDIA_PREV_TRACK = 0xB1
            VK_MEDIA_STOP = 0xB2
            VK_MEDIA_PLAY_PAUSE = 0xB3
            VK_VOLUME_MUTE = 0xAD
            VK_VOLUME_DOWN = 0xAE
            VK_VOLUME_UP = 0xAF

            action_key_map = {
                "play": VK_MEDIA_PLAY_PAUSE,
                "pause": VK_MEDIA_PLAY_PAUSE,
                "play_pause": VK_MEDIA_PLAY_PAUSE,
                "play/pause": VK_MEDIA_PLAY_PAUSE,
                "toggle": VK_MEDIA_PLAY_PAUSE,
                "next": VK_MEDIA_NEXT_TRACK,
                "next_track": VK_MEDIA_NEXT_TRACK,
                "skip": VK_MEDIA_NEXT_TRACK,
                "previous": VK_MEDIA_PREV_TRACK,
                "prev": VK_MEDIA_PREV_TRACK,
                "prev_track": VK_MEDIA_PREV_TRACK,
                "back": VK_MEDIA_PREV_TRACK,
                "stop": VK_MEDIA_STOP,
                "volume_up": VK_VOLUME_UP,
                "louder": VK_VOLUME_UP,
                "volume_down": VK_VOLUME_DOWN,
                "quieter": VK_VOLUME_DOWN,
                "mute": VK_VOLUME_MUTE,
                "unmute": VK_VOLUME_MUTE
            }

            vk_code = action_key_map.get(clean_action)
            if not vk_code:
                return {
                    "status": "error",
                    "error": f"Unknown media action '{action}'. Supported: play_pause, next, previous, volume_up, volume_down, mute"
                }

            # Emulate key down and key up
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, 2, 0)  # KEYEVENTF_KEYUP = 2

            logger.info(f"Emulated Windows media key for action: {clean_action}")
            return {
                "status": "success",
                "action": clean_action,
                "message": f"Successfully triggered media {clean_action}"
            }
        except Exception as e:
            logger.error(f"Windows media key error: {e}")
            return {"status": "error", "error": str(e)}

    elif system == "Darwin":
        try:
            # AppleScript media control
            apple_scripts = {
                "play_pause": 'tell application "System Events" to key code 16 using {command down}',
                "volume_up": "set volume output volume (output volume of (get volume settings) + 10)",
                "volume_down": "set volume output volume (output volume of (get volume settings) - 10)",
                "mute": "set volume output muted not (output muted of (get volume settings))"
            }
            script = apple_scripts.get(clean_action, "")
            if script:
                subprocess.run(["osascript", "-e", script], check=True, timeout=3)
            return {"status": "success", "action": clean_action, "message": f"Triggered macOS media {clean_action}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    else:
        # Linux via playerctl or pactl
        try:
            if clean_action in ("play", "pause", "play_pause"):
                subprocess.run(["playerctl", "play-pause"], check=True, timeout=2)
            elif clean_action in ("next", "next_track"):
                subprocess.run(["playerctl", "next"], check=True, timeout=2)
            elif clean_action in ("previous", "prev_track"):
                subprocess.run(["playerctl", "previous"], check=True, timeout=2)
            elif clean_action == "volume_up":
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+5%"], check=True, timeout=2)
            elif clean_action == "volume_down":
                subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%"], check=True, timeout=2)
            elif clean_action == "mute":
                subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], check=True, timeout=2)
            return {"status": "success", "action": clean_action, "message": f"Triggered Linux media {clean_action}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}


media_control_schema = {
    "name": "media_control",
    "description": "Controls audio and media playback on the host machine (play/pause, next track, previous track, volume up, volume down, mute).",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["play_pause", "next", "previous", "volume_up", "volume_down", "mute"],
                "description": "The media control action to perform: 'play_pause', 'next', 'previous', 'volume_up', 'volume_down', or 'mute'"
            }
        },
        "required": ["action"]
    }
}
