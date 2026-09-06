import os
import sys
import platform
import shutil
import subprocess
import csv
import io
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("CoreAI.ProcessTools")

# Protected critical processes that must never be terminated by accident
PROTECTED_PROCESSES = {
    "system", "system idle process", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe",
    "dwm.exe", "explorer.exe", "kernel", "init", "systemd"
}

def list_running_processes(filter_name: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """
    Lists currently running OS processes, memory usage, and PIDs.
    Uses native tasklist on Windows or ps on Linux/macOS with zero pip dependencies.
    """
    system = platform.system()
    filter_clean = filter_name.lower().strip() if filter_name else None
    results = []

    try:
        if system == "Windows":
            # Run tasklist with CSV output
            cmd = ["tasklist", "/FO", "CSV", "/NH"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            reader = csv.reader(io.StringIO(res.stdout))
            for row in reader:
                if len(row) >= 5:
                    img_name, pid, session_name, session_num, mem_usage = row[0], row[1], row[2], row[3], row[4]
                    if filter_clean and filter_clean not in img_name.lower():
                        continue
                    results.append({
                        "name": img_name,
                        "pid": pid,
                        "memory": mem_usage
                    })
        else:
            cmd = ["ps", "-eo", "pid,comm,%mem,%cpu", "--sort=-%mem"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            lines = res.stdout.strip().split("\n")[1:]
            for line in lines:
                parts = line.split(maxsplit=3)
                if len(parts) >= 4:
                    pid, comm, pmem, pcpu = parts[0], parts[1], parts[2], parts[3]
                    if filter_clean and filter_clean not in comm.lower():
                        continue
                    results.append({
                        "name": comm,
                        "pid": pid,
                        "memory": f"{pmem}%",
                        "cpu": f"{pcpu}%"
                    })

        total_found = len(results)
        return {
            "status": "success",
            "count": total_found,
            "processes": results[:limit]
        }
    except Exception as e:
        logger.error(f"Error listing processes: {e}")
        return {"status": "error", "error": str(e)}

def kill_process(process_name_or_pid: str, force: bool = False) -> Dict[str, Any]:
    """
    Terminates a specific process by name or PID.
    Guarded against terminating critical OS processes or the Core AI process itself.
    """
    target = process_name_or_pid.strip()
    target_lower = target.lower()

    if target_lower in PROTECTED_PROCESSES:
        return {
            "status": "rejected",
            "reason": f"Safety Protection: '{target}' is a vital operating system process and cannot be terminated."
        }

    # Also protect current process
    current_pid = str(os.getpid())
    if target == current_pid:
        return {
            "status": "rejected",
            "reason": "Safety Protection: Core AI cannot terminate its own host process."
        }

    system = platform.system()
    try:
        if system == "Windows":
            cmd = ["taskkill"]
            if force:
                cmd.append("/F")
            if target.isdigit():
                cmd.extend(["/PID", target])
            else:
                img_name = target if target.endswith(".exe") else f"{target}.exe"
                cmd.extend(["/IM", img_name, "/T"])
            
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                logger.info(f"Terminated process: {target}")
                return {"status": "success", "target": target, "message": f"Successfully terminated process {target}"}
            else:
                return {"status": "error", "target": target, "error": res.stderr.strip()}
        else:
            cmd = ["pkill", "-9" if force else "-15", target] if not target.isdigit() else ["kill", "-9" if force else "-15", target]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return {"status": "success" if res.returncode == 0 else "error", "target": target}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def get_hardware_metrics() -> Dict[str, Any]:
    """
    Retrieves real-time CPU, RAM, and disk storage metrics.
    Zero external pip dependencies (uses shutil and native OS utilities).
    """
    metrics: Dict[str, Any] = {
        "platform": platform.system(),
        "processor": platform.processor(),
    }

    # 1. Disk Usage
    try:
        root_dir = "C:\\" if platform.system() == "Windows" else "/"
        total, used, free = shutil.disk_usage(root_dir)
        metrics["disk"] = {
            "drive": root_dir,
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free / (1024 ** 3), 2),
            "percent_used": round((used / total) * 100, 1)
        }
    except Exception as e:
        metrics["disk_error"] = str(e)

    # 2. Windows-specific Memory and CPU metrics via PowerShell
    if platform.system() == "Windows":
        try:
            ps_code = """
$os = Get-CimInstance Win32_OperatingSystem
$total_ram = [math]::Round($os.TotalVisibleMemorySize / 1024 / 1024, 2)
$free_ram = [math]::Round($os.FreePhysicalMemory / 1024 / 1024, 2)
$used_ram = [math]::Round($total_ram - $free_ram, 2)
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
Write-Output "$total_ram,$used_ram,$free_ram,$cpu"
"""
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], capture_output=True, text=True, timeout=8)
            if res.returncode == 0 and res.stdout.strip():
                parts = res.stdout.strip().split(",")
                if len(parts) >= 4:
                    metrics["memory"] = {
                        "total_gb": float(parts[0]),
                        "used_gb": float(parts[1]),
                        "free_gb": float(parts[2]),
                        "percent_used": round((float(parts[1]) / float(parts[0])) * 100, 1) if float(parts[0]) > 0 else 0
                    }
                    metrics["cpu_percent"] = float(parts[3]) if parts[3] else None
        except Exception as e:
            metrics["hardware_query_error"] = str(e)

    return {"status": "success", "metrics": metrics}

def lock_workstation() -> Dict[str, Any]:
    """
    Immediately locks the workstation display session.
    """
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
            return {"status": "success", "message": "Workstation session locked"}
        elif system == "Darwin":
            subprocess.run(["pmset", "displaysleepnow"], check=True)
            return {"status": "success", "message": "macOS display locked"}
        else:
            subprocess.run(["loginctl", "lock-session"], check=True)
            return {"status": "success", "message": "Linux session locked"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# --- JSON Schemas ---

list_running_processes_schema = {
    "name": "list_running_processes",
    "description": "Lists running applications and processes on the machine with memory usage and PIDs.",
    "parameters": {
        "type": "object",
        "properties": {
            "filter_name": {
                "type": "string",
                "description": "Optional name or substring to filter processes (e.g. 'chrome', 'python')"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of processes to return (default: 20)"
            }
        }
    }
}

kill_process_schema = {
    "name": "kill_process",
    "description": "Terminates a running application or process by name or PID (protected against vital OS processes).",
    "parameters": {
        "type": "object",
        "properties": {
            "process_name_or_pid": {
                "type": "string",
                "description": "Process image name (e.g. 'notepad', 'calc') or integer PID"
            },
            "force": {
                "type": "boolean",
                "description": "Force kill (/F)"
            }
        },
        "required": ["process_name_or_pid"]
    }
}

get_hardware_metrics_schema = {
    "name": "get_hardware_metrics",
    "description": "Retrieves real-time CPU utilization, RAM usage (total, used, free), and disk storage capacity.",
    "parameters": {"type": "object", "properties": {}}
}

lock_workstation_schema = {
    "name": "lock_workstation",
    "description": "Locks the current workstation display session for privacy and security.",
    "parameters": {"type": "object", "properties": {}}
}
