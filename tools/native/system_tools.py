import datetime
import platform
import os
import sys
from typing import Dict, Any, Optional

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
    res: Dict[str, Any] = {
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
        import importlib
        psutil = importlib.import_module("psutil")
        vmem = psutil.virtual_memory()
        res["memory"] = {
            "total_gb": round(vmem.total / (1024**3), 2),
            "available_gb": round(vmem.available / (1024**3), 2),
            "used_percent": round(vmem.percent, 1)
        }
        res["cpu_percent"] = round(psutil.cpu_percent(interval=0.05), 1)
    except Exception:
        pass

    # Guaranteed fallbacks when psutil is not installed or virtualized
    if "cpu_percent" not in res:
        if "load_avg" in res and res.get("cpu_count"):
            res["cpu_percent"] = round(min((res["load_avg"]["1m"] / res["cpu_count"]) * 100.0, 100.0), 1)
        else:
            res["cpu_percent"] = 0.0

    if "memory" not in res:
        res["memory"] = {"total_gb": 0.0, "available_gb": 0.0, "used_percent": 0.0}
        if os.path.exists("/proc/meminfo"):
            try:
                mem = {}
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            mem[parts[0].strip()] = parts[1].strip().split()[0]
                if "MemTotal" in mem and "MemAvailable" in mem:
                    total_gb = round(int(mem["MemTotal"]) / (1024 * 1024), 2)
                    avail_gb = round(int(mem["MemAvailable"]) / (1024 * 1024), 2)
                    used_pct = round(((total_gb - avail_gb) / total_gb) * 100, 1) if total_gb > 0 else 0.0
                    res["memory"] = {
                        "total_gb": total_gb,
                        "available_gb": avail_gb,
                        "used_percent": used_pct
                    }
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


def get_disk_usage(path: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """
    Returns storage metrics for the specified path or primary system drive.
    Includes total capacity, used gigabytes, free gigabytes, and usage percentage.
    """
    import shutil
    target_path = path or (os.path.abspath(os.sep) if os.name != "nt" else "C:\\")
    try:
        total, used, free = shutil.disk_usage(target_path)
        return {
            "status": "success",
            "path": target_path,
            "total_gb": round(total / (1024**3), 2),
            "used_gb": round(used / (1024**3), 2),
            "free_gb": round(free / (1024**3), 2),
            "used_percent": round((used / total) * 100, 1)
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to inspect disk usage for '{target_path}': {e}"}


def get_battery_status(**kwargs) -> Dict[str, Any]:
    """
    Returns hardware battery charge percentage, charging state, and remaining life.
    Useful for laptop-based homelab servers and mobile workstations.
    """
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return {
                "status": "success",
                "has_battery": False,
                "message": "No hardware battery detected (running on AC desktop or VM)."
            }
        return {
            "status": "success",
            "has_battery": True,
            "percent": round(battery.percent, 1),
            "power_plugged": battery.power_plugged,
            "seconds_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
            "status_text": "Charging / AC Connected" if battery.power_plugged else f"{battery.percent}% Battery Remaining"
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "has_battery": False,
            "message": f"Battery inspection unavailable ({e}). Running on AC desktop, VM, or server."
        }


def get_network_interfaces(**kwargs) -> Dict[str, Any]:
    """
    Lists physical and virtual network adapters, active IP addresses, and interface status.
    """
    try:
        import psutil
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        interfaces = []
        for iface_name, iface_addrs in addrs.items():
            ipv4_list = [a.address for a in iface_addrs if a.family.name in ("AF_INET", "address_family.AF_INET") or str(a.family) == "2"]
            stat = stats.get(iface_name)
            is_up = stat.isup if stat else True
            speed_mb = stat.speed if stat else 0
            if ipv4_list:
                interfaces.append({
                    "name": iface_name,
                    "is_up": is_up,
                    "speed_mb": speed_mb,
                    "ipv4": ipv4_list
                })
        return {
            "status": "success",
            "count": len(interfaces),
            "interfaces": interfaces
        }
    except Exception as e:
        import socket
        try:
            lan_ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            lan_ip = "127.0.0.1"
        return {
            "status": "success",
            "count": 1,
            "interfaces": [{"name": "primary", "is_up": True, "speed_mb": 0, "ipv4": [lan_ip]}],
            "message": f"Retrieved via standard library fallback: {e}"
        }


disk_usage_schema = {
    "name": "get_disk_usage",
    "description": "Get disk storage usage, total, used, and free capacity for a directory or drive",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Optional drive letter or directory path"}
        }
    }
}

battery_status_schema = {
    "name": "get_battery_status",
    "description": "Inspect battery percentage, charging status, and remaining power for laptops/portables",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

network_interfaces_schema = {
    "name": "get_network_interfaces",
    "description": "Inspect active network adapters, LAN IP addresses, and link status",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

