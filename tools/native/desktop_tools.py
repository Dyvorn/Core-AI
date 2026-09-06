import os
import sys
import platform
import subprocess
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("CoreAI.DesktopTools")

def launch_application(app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Launches a desktop application on the host machine.
    Resolves common aliases across Windows, Linux, and macOS.
    Executes in detached mode so Core AI never blocks or hangs.
    """
    name_clean = app_name.lower().strip()
    system = platform.system()
    extra_args = args or []

    # Common cross-platform application aliases
    app_map_windows = {
        "youtube": ["cmd.exe", "/c", "start", "https://youtube.com"],
        "spotify": ["cmd.exe", "/c", "start", "spotify:"],
        "vscode": ["code"],
        "code": ["code"],
        "browser": ["cmd.exe", "/c", "start", "https://google.com"],
        "chrome": ["chrome"],
        "firefox": ["firefox"],
        "edge": ["msedge"],
        "calculator": ["calc.exe"],
        "calc": ["calc.exe"],
        "notepad": ["notepad.exe"],
        "terminal": ["wt.exe"],
        "powershell": ["powershell.exe"],
        "cmd": ["cmd.exe"],
        "explorer": ["explorer.exe"],
        "taskmgr": ["taskmgr.exe"],
        "task manager": ["taskmgr.exe"],
        "settings": ["cmd.exe", "/c", "start", "ms-settings:"]
    }

    app_map_linux = {
        "youtube": ["xdg-open", "https://youtube.com"],
        "spotify": ["spotify"],
        "vscode": ["code"],
        "code": ["code"],
        "browser": ["x-www-browser"],
        "chrome": ["google-chrome"],
        "firefox": ["firefox"],
        "terminal": ["x-terminal-emulator"],
        "calculator": ["gnome-calculator"],
        "calc": ["gnome-calculator"],
        "notepad": ["gedit"],
        "explorer": ["xdg-open", "."]
    }

    app_map_darwin = {
        "youtube": ["open", "https://youtube.com"],
        "spotify": ["open", "-a", "Spotify"],
        "vscode": ["code"],
        "code": ["code"],
        "browser": ["open", "https://google.com"],
        "chrome": ["open", "-a", "Google Chrome"],
        "firefox": ["open", "-a", "Firefox"],
        "terminal": ["open", "-a", "Terminal"],
        "calculator": ["open", "-a", "Calculator"],
        "notepad": ["open", "-a", "TextEdit"],
        "explorer": ["open", "."]
    }

    if system == "Windows":
        cmd_list = app_map_windows.get(name_clean, [name_clean])
    elif system == "Darwin":
        cmd_list = app_map_darwin.get(name_clean, ["open", "-a", name_clean])
    else:
        cmd_list = app_map_linux.get(name_clean, [name_clean])

    full_cmd = list(cmd_list) + extra_args

    try:
        # Launch detached/non-blocking
        if system == "Windows":
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(full_cmd, shell=False, creationflags=creationflags)
        else:
            subprocess.Popen(full_cmd, shell=False, start_new_session=True)

        logger.info(f"Launched application '{app_name}' with command: {full_cmd}")
        return {
            "status": "success",
            "app_name": app_name,
            "resolved_command": " ".join(full_cmd),
            "message": f"Successfully launched {app_name} on your workstation"
        }
    except Exception as e:
        # Fallback to shell start
        try:
            subprocess.Popen(f"start {app_name}" if system == "Windows" else f"xdg-open {app_name}", shell=True)
            return {
                "status": "success",
                "app_name": app_name,
                "message": f"Invoked launch for '{app_name}' via OS shell launcher"
            }
        except Exception as e2:
            logger.error(f"Failed to launch application '{app_name}': {e2}")
            return {
                "status": "error",
                "app_name": app_name,
                "error": str(e2)
            }

def open_path_in_explorer(path: str) -> Dict[str, Any]:
    """
    Opens a directory in the host OS file explorer, or highlights a file.
    """
    norm_path = os.path.abspath(path.strip())
    system = platform.system()

    try:
        if system == "Windows":
            if os.path.isfile(norm_path):
                subprocess.Popen(f'explorer.exe /select,"{norm_path}"', shell=True)
            else:
                os.startfile(norm_path)
        elif system == "Darwin":
            subprocess.Popen(["open", "-R", norm_path] if os.path.isfile(norm_path) else ["open", norm_path])
        else:
            target_dir = os.path.dirname(norm_path) if os.path.isfile(norm_path) else norm_path
            subprocess.Popen(["xdg-open", target_dir])

        logger.info(f"Opened path in explorer: {norm_path}")
        return {
            "status": "success",
            "path": norm_path,
            "message": f"Opened {norm_path} in file explorer"
        }
    except Exception as e:
        logger.error(f"Failed to open path in explorer '{path}': {e}")
        return {
            "status": "error",
            "path": path,
            "error": str(e)
        }

def take_screenshot(output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Captures the primary display and saves to an image file.
    Uses native Windows PowerShell .NET graphics with zero pip dependencies.
    """
    target_dir = "screenshots"
    os.makedirs(target_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_path = output_path or os.path.join(target_dir, f"screen_{timestamp}.png")
    abs_path = os.path.abspath(final_path)

    system = platform.system()
    try:
        if system == "Windows":
            # Native PowerShell .NET System.Drawing screen capture script
            ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
$screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
$bitmap.Save('{abs_path.replace(chr(92), "/")}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
"""
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True, timeout=10)
            if res.returncode != 0:
                raise RuntimeError(f"PowerShell capture failed: {res.stderr.strip()}")
        elif system == "Darwin":
            subprocess.run(["screencapture", "-x", abs_path], check=True, timeout=10)
        else:
            # Linux: try scrot, gnome-screenshot, or import
            subprocess.run(["scrot", abs_path], check=True, timeout=10)

        logger.info(f"Screenshot successfully captured: {abs_path}")
        return {
            "status": "success",
            "file_path": abs_path,
            "size_bytes": os.path.getsize(abs_path) if os.path.exists(abs_path) else 0,
            "message": f"Captured screenshot to {abs_path}"
        }
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

def get_clipboard_text() -> Dict[str, Any]:
    """
    Reads text content currently stored in the system clipboard.
    """
    system = platform.system()
    try:
        if system == "Windows":
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=5
            )
            text = res.stdout.rstrip("\r\n")
            return {"status": "success", "clipboard_text": text}
        elif system == "Darwin":
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return {"status": "success", "clipboard_text": res.stdout}
        else:
            res = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=5)
            return {"status": "success", "clipboard_text": res.stdout}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def set_clipboard_text(text: str) -> Dict[str, Any]:
    """
    Copies specified text to the system clipboard.
    """
    system = platform.system()
    try:
        if system == "Windows":
            # Encode to avoid escaping issues
            escaped = text.replace("'", "''")
            cmd = f"Set-Clipboard -Value '{escaped}'"
            subprocess.run(["powershell", "-NoProfile", "-Command", cmd], check=True, timeout=5)
            return {"status": "success", "message": "Text copied to clipboard"}
        elif system == "Darwin":
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text, timeout=5)
            return {"status": "success", "message": "Text copied to clipboard"}
        else:
            proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text, timeout=5)
            return {"status": "success", "message": "Text copied to clipboard"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# --- JSON Schemas for Tool Catalog ---

launch_application_schema = {
    "name": "launch_application",
    "description": "Launches a desktop application on the host OS (e.g. 'youtube', 'spotify', 'vscode', 'chrome', 'calculator', 'notepad', 'terminal', 'explorer', 'settings').",
    "parameters": {
        "type": "object",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Application name or common alias (e.g. 'youtube', 'spotify', 'code', 'calc', 'notepad', 'chrome')"
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional command-line arguments to pass to the application"
            }
        },
        "required": ["app_name"]
    }
}

open_path_in_explorer_schema = {
    "name": "open_path_in_explorer",
    "description": "Opens a folder in File Explorer / Finder, or reveals a specific file.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File or directory path to open"
            }
        },
        "required": ["path"]
    }
}

take_screenshot_schema = {
    "name": "take_screenshot",
    "description": "Takes a screenshot of the operator's desktop display and saves it to a PNG file.",
    "parameters": {
        "type": "object",
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Optional file path where the screenshot PNG will be saved"
            }
        }
    }
}

get_clipboard_text_schema = {
    "name": "get_clipboard_text",
    "description": "Reads text content currently on the system clipboard.",
    "parameters": {"type": "object", "properties": {}}
}

set_clipboard_text_schema = {
    "name": "set_clipboard_text",
    "description": "Sets or copies text into the system clipboard.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text string to copy to clipboard"
            }
        },
        "required": ["text"]
    }
}
