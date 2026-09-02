import datetime
import platform
import os
import sys

def get_time() -> str:
    """Returns the current system time."""
    return datetime.datetime.now().strftime("%H:%M")

def get_system_status() -> dict:
    """
    Returns cross-platform system diagnostics:
    Works identically across Linux, Android/Termux, macOS, and Windows.
    """
    status = {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "time": datetime.datetime.now().isoformat()
    }
    
    # Enrich with Linux distribution details if running on Linux
    if platform.system() == "Linux":
        try:
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            status["linux_distro"] = line.split("=")[1].strip('"\n')
        except Exception:
            pass

    return status

time_schema = {
    "name": "get_time",
    "description": "Get the current time",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

system_status_schema = {
    "name": "get_system_status",
    "description": "Fetch current operating system, distribution, and hardware architecture status",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}
