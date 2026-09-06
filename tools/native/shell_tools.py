import subprocess
import logging
from typing import Dict, Any
from brain.safety import SafetyGate

logger = logging.getLogger("CoreAI.ShellTools")

def run_shell_command(command: str, timeout_seconds: int = 15) -> Dict[str, Any]:
    """
    Executes a shell command on the host operating system.
    Strictly audited by SafetyGate to prevent catastrophic system destruction.
    Captures stdout and stderr without blocking indefinitely.
    """
    clean_cmd = command.strip()
    if not clean_cmd:
        return {"status": "error", "error": "Empty command provided"}

    # 1. Safety Gate Audit
    safety = SafetyGate()
    is_harmful, reason = safety.is_harmful_action(clean_cmd)
    if is_harmful:
        logger.warning(f"Shell command rejected by SafetyGate: '{clean_cmd}' - Reason: {reason}")
        return {
            "status": "rejected",
            "command": clean_cmd,
            "reason": reason
        }

    # 2. Command Execution
    try:
        logger.info(f"Executing audited shell command: {clean_cmd}")
        res = subprocess.run(
            clean_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=max(1, min(timeout_seconds, 60))
        )
        return {
            "status": "success" if res.returncode == 0 else "failed",
            "command": clean_cmd,
            "returncode": res.returncode,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "command": clean_cmd,
            "error": f"Command timed out after {timeout_seconds} seconds"
        }
    except Exception as e:
        logger.error(f"Error executing shell command '{clean_cmd}': {e}")
        return {
            "status": "error",
            "command": clean_cmd,
            "error": str(e)
        }


run_shell_command_schema = {
    "name": "run_shell_command",
    "description": "Executes a safe terminal/shell command on the host machine (audited by SafetyGate to block destructive attacks).",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact shell command line to run (e.g. 'dir', 'git status', 'python --version', 'ipconfig')"
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum execution time in seconds before timeout (default: 15, max: 60)"
            }
        },
        "required": ["command"]
    }
}
