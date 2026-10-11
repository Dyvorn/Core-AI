import datetime
import platform
import os
import sys

def get_time(**kwargs) -> str:
    """Returns the current system time."""
    return datetime.datetime.now().strftime("%H:%M")

def get_system_status(**kwargs) -> dict:
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

def factory_reset(confirm: bool = False, keep_env: bool = False, **kwargs) -> dict:
    """
    Executes a zero-residue clean slate reset:
    Deletes runtime database, logs, backups, and dynamic tools while preserving
    all code files and the Python virtual environment for a clean new server setup.
    Requires explicit confirm=True.
    """
    if not confirm:
        return {
            "status": "confirmation_required",
            "message": "Factory reset requires explicit confirmation (confirm=True). This wipes runtime database, logs, and credentials while keeping all code files and virtualenv installed."
        }
    from interfaces.install.clean_setup import clean_system_state
    res = clean_system_state(wipe_env=not keep_env, stop_services=False)
    return {
        "status": "success",
        "message": "System wiped to clean Day-Zero state. All code files, dependencies, and venv preserved for fresh setup.",
        "details": {
            "removed_db_files": len(res.get("removed_db_files", [])),
            "cleared_logs": len(res.get("cleared_log_files", [])),
            "cleared_backups": len(res.get("cleared_backup_files", [])),
            "cleared_dynamic_tools": len(res.get("cleared_dynamic_tools", []))
        }
    }

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

def inspect_system_resources(**kwargs) -> dict:
    """
    Returns real-time hardware vitals, memory consumption, CPU load, and disk capacity.
    Cross-platform support for Windows, Linux, and macOS.
    """
    import shutil
    res = {
        "os": platform.system(),
        "hostname": platform.node(),
        "cpu_count": os.cpu_count() or 1,
    }

    # Load Averages (Unix)
    if hasattr(os, "getloadavg"):
        try:
            load1, load5, load15 = os.getloadavg()
            res["load_avg"] = {"1m": round(load1, 2), "5m": round(load5, 2), "15m": round(load15, 2)}
        except Exception:
            pass

    # Disk usage
    try:
        path = "C:\\" if os.name == "nt" else "/"
        total, used, free = shutil.disk_usage(path)
        res["disk"] = {
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "used_percent": round((used / total) * 100, 1)
        }
    except Exception:
        pass

    # Memory usage via psutil if present
    try:
        import psutil
        vmem = psutil.virtual_memory()
        res["memory"] = {
            "total_gb": round(vmem.total / (1024**3), 2),
            "available_gb": round(vmem.available / (1024**3), 2),
            "used_percent": round(vmem.percent, 1)
        }
        res["cpu_percent"] = round(psutil.cpu_percent(interval=0.05), 1)
    except Exception:
        pass

    return res

system_resources_schema = {
    "name": "inspect_system_resources",
    "description": "Inspect CPU utilization, RAM usage, load average, and disk storage capacity",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

factory_reset_schema = {
    "name": "factory_reset",
    "description": "Clean-wipe all runtime database state, logs, credentials, and dynamic tools for a fresh Day-Zero server setup, preserving all installed code files and virtual environment",
    "parameters": {
        "type": "object",
        "properties": {
            "confirm": {
                "type": "boolean",
                "description": "Must be set to True to confirm execution"
            },
            "keep_env": {
                "type": "boolean",
                "description": "Optionally preserve config/.env without deleting API keys",
                "default": False
            }
        },
        "required": ["confirm"]
    }
}
