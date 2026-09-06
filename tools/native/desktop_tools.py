import os
import re
import sys
import time
import shutil
import platform
import subprocess
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("CoreAI.DesktopTools")


class AppResolver:
    """
    Universal Desktop Application Discovery & Fuzzy Matcher:
    - Scans Windows Start Menu, Desktops, and App Paths (.lnk shortcuts & executables).
    - Scans macOS /Applications (.app) and Linux /usr/share/applications (.desktop).
    - Employs ranked token & substring matching to resolve conversational names
      (e.g. 'davinci', 'davinci resolve', 'obs', 'discord', 'blender', 'spotify').
    """

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._last_scan_time: float = 0
        self._scan_ttl: float = 300.0  # 5 minutes cache

    def scan_installed_apps(self, force: bool = False) -> Dict[str, str]:
        now = time.time()
        if self._cache and not force and (now - self._last_scan_time) < self._scan_ttl:
            return self._cache

        system = platform.system()
        apps: Dict[str, str] = {}

        if system == "Windows":
            # 1. Start Menu Shortcuts & Desktops
            scan_dirs = [
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
                os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
                os.path.expandvars(r"%USERPROFILE%\Desktop"),
                r"C:\Users\Public\Desktop"
            ]
            for s_dir in scan_dirs:
                if os.path.exists(s_dir):
                    for root, _, files in os.walk(s_dir):
                        for f in files:
                            if f.lower().endswith(".lnk"):
                                base = os.path.splitext(f)[0].lower().strip()
                                apps[base] = os.path.join(root, f)

            # 2. Registry App Paths
            try:
                import winreg
                for hkey in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                    try:
                        with winreg.OpenKey(hkey, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths") as key:
                            num_subkeys, _, _ = winreg.QueryInfoKey(key)
                            for i in range(num_subkeys):
                                try:
                                    subkey_name = winreg.EnumKey(key, i)
                                    with winreg.OpenKey(key, subkey_name) as subkey:
                                        val, _ = winreg.QueryValueEx(subkey, "")
                                        if val and os.path.exists(val):
                                            base = os.path.splitext(subkey_name)[0].lower()
                                            if base not in apps:
                                                apps[base] = val
                                except Exception:
                                    continue
                    except Exception:
                        pass
            except Exception:
                pass

        elif system == "Darwin":
            for d in ["/Applications", os.path.expanduser("~/Applications")]:
                if os.path.exists(d):
                    for item in os.listdir(d):
                        if item.endswith(".app"):
                            base = os.path.splitext(item)[0].lower()
                            apps[base] = os.path.join(d, item)

        else:  # Linux
            for d in ["/usr/share/applications", os.path.expanduser("~/.local/share/applications")]:
                if os.path.exists(d):
                    for f in os.listdir(d):
                        if f.endswith(".desktop"):
                            base = os.path.splitext(f)[0].lower()
                            apps[base] = os.path.join(d, f)

        self._cache = apps
        self._last_scan_time = now
        logger.info(f"Indexed {len(apps)} installed desktop applications.")
        return apps

    def find_app(self, query: str) -> Optional[str]:
        q = query.lower().strip()
        apps = self.scan_installed_apps()

        if q in apps:
            return apps[q]

        candidates = []
        q_words = set(re.findall(r'\w+', q))

        for name, path in apps.items():
            name_words = set(re.findall(r'\w+', name))
            if name == q:
                candidates.append((100, -len(name), path))
            elif name.startswith(q):
                candidates.append((85, -len(name), path))
            elif q_words and q_words.issubset(name_words):
                score = 80 if len(q_words) == len(name_words) else 70
                candidates.append((score, -len(name), path))
            elif q in name:
                candidates.append((60, -len(name), path))
            elif name in q:
                candidates.append((50, len(name), path))
            elif q_words and (q_words & name_words):
                overlap = len(q_words & name_words)
                candidates.append((30 + overlap * 5, -len(name), path))

        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][2]

        return None


_app_resolver = AppResolver()


def launch_application(app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Launches a desktop application on the host machine.
    Dynamically discovers installed programs (.lnk, .exe, .desktop, .app) via AppResolver.
    Resolves common aliases and handles arbitrary application names.
    """
    name_clean = app_name.lower().strip()
    system = platform.system()
    extra_args = args or []

    # 1. Built-in Special Aliases & URI Schemes
    special_schemes = {
        "youtube": lambda: subprocess.Popen(["cmd.exe", "/c", "start", "https://youtube.com"] if system == "Windows" else ["xdg-open", "https://youtube.com"]),
        "spotify": lambda: os.startfile("spotify:") if system == "Windows" else subprocess.Popen(["spotify"]),
        "calculator": lambda: subprocess.Popen(["calc.exe"] if system == "Windows" else ["gnome-calculator"]),
        "calc": lambda: subprocess.Popen(["calc.exe"] if system == "Windows" else ["gnome-calculator"]),
        "notepad": lambda: subprocess.Popen(["notepad.exe"] if system == "Windows" else ["gedit"]),
        "terminal": lambda: subprocess.Popen(["wt.exe"] if system == "Windows" else ["x-terminal-emulator"]),
        "powershell": lambda: subprocess.Popen(["powershell.exe"]),
        "cmd": lambda: subprocess.Popen(["cmd.exe"]),
        "explorer": lambda: subprocess.Popen(["explorer.exe"] if system == "Windows" else ["xdg-open", "."]),
        "settings": lambda: os.startfile("ms-settings:") if system == "Windows" else None,
        "taskmgr": lambda: subprocess.Popen(["taskmgr.exe"]),
        "task manager": lambda: subprocess.Popen(["taskmgr.exe"]),
    }

    if name_clean in special_schemes:
        try:
            special_schemes[name_clean]()
            return {
                "status": "success",
                "app_name": app_name,
                "message": f"Successfully launched {app_name} on your workstation"
            }
        except Exception as e:
            logger.debug(f"Special alias launch failed for '{name_clean}': {e}. Falling through to AppResolver.")

    # 2. Universal Installed Application Search (Fuzzy Matcher)
    resolved_path = _app_resolver.find_app(name_clean)
    if resolved_path:
        try:
            if system == "Windows":
                # If it's a shortcut (.lnk), invoke via os.startfile (native Windows shell execution)
                if resolved_path.lower().endswith(".lnk"):
                    os.startfile(resolved_path)
                else:
                    creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                    subprocess.Popen([resolved_path] + extra_args, creationflags=creationflags)
            elif system == "Darwin":
                subprocess.Popen(["open", resolved_path] + extra_args)
            else:
                subprocess.Popen(["xdg-open", resolved_path] + extra_args)

            logger.info(f"Launched application '{app_name}' via resolved shortcut: {resolved_path}")
            return {
                "status": "success",
                "app_name": app_name,
                "resolved_path": resolved_path,
                "message": f"Successfully launched {app_name} ({os.path.basename(resolved_path)})"
            }
        except Exception as e:
            logger.warning(f"Error launching resolved path '{resolved_path}': {e}")

    # 3. System PATH Search (shutil.which)
    in_path = shutil.which(name_clean) or (shutil.which(f"{name_clean}.exe") if system == "Windows" else None)
    if in_path:
        try:
            if system == "Windows":
                creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                subprocess.Popen([in_path] + extra_args, creationflags=creationflags)
            else:
                subprocess.Popen([in_path] + extra_args, start_new_session=True)
            return {
                "status": "success",
                "app_name": app_name,
                "resolved_path": in_path,
                "message": f"Successfully launched {app_name} from system PATH"
            }
        except Exception as e:
            logger.warning(f"Error launching from PATH '{in_path}': {e}")

    # 4. Safe OS Shell Fallback
    try:
        if system == "Windows":
            # Note the empty title string "" so start doesn't treat target as window title
            subprocess.Popen(f'cmd.exe /c start "" "{name_clean}"', shell=True)
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", name_clean])
        else:
            subprocess.Popen(["xdg-open", name_clean])

        return {
            "status": "success",
            "app_name": app_name,
            "message": f"Dispatched launch for '{app_name}' to OS shell"
        }
    except Exception as e:
        logger.error(f"Failed to launch application '{app_name}': {e}")
        return {
            "status": "error",
            "app_name": app_name,
            "error": f"Could not find or launch application '{app_name}': {e}"
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
