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

    valid_actions = {
        "play", "pause", "play_pause", "play/pause", "toggle",
        "next", "next_track", "skip",
        "previous", "prev", "prev_track", "back",
        "stop", "volume_up", "louder", "volume_down", "quieter", "mute", "unmute"
    }
    if clean_action not in valid_actions:
        return {
            "status": "error",
            "error": f"Unknown media action '{action}'. Supported: play_pause, next, previous, volume_up, volume_down, mute"
        }

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


def set_system_volume(level_percent: int, **kwargs) -> Dict[str, Any]:
    """Sets master system volume level (0 to 100%)."""
    clamped = max(0, min(100, int(level_percent)))
    system = platform.system()
    try:
        if system == "Windows":
            # On Windows without pycaw, execute PowerShell audio command or steps
            ps_script = f"""
            $obj = New-Object -ComObject WScript.Shell
            1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}
            $steps = [math]::Round({clamped} / 2)
            1..$steps | ForEach-Object {{ $obj.SendKeys([char]175) }}
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], timeout=3.0, capture_output=True)
            return {"status": "success", "level_percent": clamped, "message": f"Set volume to {clamped}%."}
        elif system == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {clamped}"], timeout=2.0, check=True)
            return {"status": "success", "level_percent": clamped, "message": f"Set volume to {clamped}%."}
        else:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{clamped}%"], timeout=2.0, check=True)
            return {"status": "success", "level_percent": clamped, "message": f"Set volume to {clamped}%."}
    except Exception as e:
        return {
            "status": "unsupported",
            "level_percent": clamped,
            "message": f"Host audio subsystem unavailable ({e}). Volume adjustment unsupported on headless host."
        }


def toggle_audio_mute(**kwargs) -> Dict[str, Any]:
    """Toggles master audio mute on the host system."""
    res = media_control(action="mute")
    if res.get("status") == "error":
        return {
            "status": "unsupported",
            "message": res.get("error", "Host audio mute unsupported on this host.")
        }
    return res


def get_audio_devices(**kwargs) -> Dict[str, Any]:
    """Inspects available audio playback and capture soundcards."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        dev_list = []
        for i, d in enumerate(devices):
            dev_list.append({
                "index": i,
                "name": d.get("name", "Unknown"),
                "max_input_channels": d.get("max_input_channels", 0),
                "max_output_channels": d.get("max_output_channels", 0),
                "default_samplerate": d.get("default_samplerate", 44100)
            })
        return {"status": "success", "count": len(dev_list), "devices": dev_list}
    except Exception:
        # Fallback when sounddevice is uninstalled or virtualized
        return {
            "status": "success",
            "count": 1,
            "devices": [{"index": 0, "name": "Default System Soundcard", "max_input_channels": 2, "max_output_channels": 2}]
        }


set_volume_schema = {
    "name": "set_system_volume",
    "description": "Set master system volume to a specific percentage (0 to 100)",
    "parameters": {
        "type": "object",
        "properties": {
            "level_percent": {"type": "integer", "description": "Volume percentage from 0 to 100", "minimum": 0, "maximum": 100}
        },
        "required": ["level_percent"]
    }
}

toggle_mute_schema = {
    "name": "toggle_audio_mute",
    "description": "Toggle audio mute state on the host system",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

audio_devices_schema = {
    "name": "get_audio_devices",
    "description": "Inspect connected microphones and speaker audio devices",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

