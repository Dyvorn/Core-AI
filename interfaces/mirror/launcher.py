import os
import sys
import time
import shutil
import logging
import argparse
import subprocess
from typing import Optional, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [CoreAI.MirrorLauncher] %(message)s")
logger = logging.getLogger("CoreAI.MirrorLauncher")


def find_browser_executable(custom_path: Optional[str] = None) -> Optional[str]:
    """Finds an installed Chromium-compatible browser binary across Windows, Linux, and macOS."""
    if custom_path and os.path.isfile(custom_path):
        return custom_path

    # Check environment variable
    env_browser = os.getenv("CORE_MIRROR_BROWSER")
    if env_browser and os.path.isfile(env_browser):
        return env_browser

    candidates: List[str] = []

    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")

        candidates = [
            os.path.join(program_files, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files_x86, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(program_files_x86, "Microsoft\\Edge\\Application\\msedge.exe"),
            os.path.join(local_app_data, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(program_files, "BraveSoftware\\Brave-Browser\\Application\\brave.exe"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    else:
        # Linux / Raspberry Pi OS
        candidates = [
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/microsoft-edge",
            "/snap/bin/chromium",
        ]

    for path in candidates:
        if os.path.isfile(path):
            return path

    # Check PATH
    for name in ["chromium-browser", "chromium", "google-chrome", "chrome", "msedge"]:
        found = shutil.which(name)
        if found:
            return found

    return None


def run_kiosk(url: str, browser_path: Optional[str] = None, kiosk_mode: bool = True, watchdog: bool = True):
    """Launches the Ambient HUD in kiosk mode with an optional process watchdog."""
    executable = find_browser_executable(browser_path)
    if not executable:
        logger.error("No compatible Chromium browser found on this system.")
        logger.info(f"Please open your browser manually to: {url}")
        return

    logger.info(f"Found browser executable: {executable}")
    logger.info(f"Launching Ambient HUD Kiosk pointing to: {url}")

    flags = [
        executable,
        "--noerrdialogs",
        "--disable-infobars",
        "--disable-features=Translate",
        "--no-first-run",
        "--check-for-update-interval=31536000",
        "--autoplay-policy=no-user-gesture-required"
    ]

    if kiosk_mode:
        flags.append("--kiosk")
    else:
        flags.append("--start-maximized")

    flags.append(url)

    while True:
        try:
            logger.info("Starting browser process...")
            proc = subprocess.Popen(flags)
            returncode = proc.wait()
            logger.warning(f"Browser exited with returncode {returncode}")

            if not watchdog:
                break

            logger.info("Watchdog active: restarting browser in 3 seconds (Press Ctrl+C to abort)...")
            time.sleep(3)
        except KeyboardInterrupt:
            logger.info("Launcher stopped by operator.")
            if 'proc' in locals() and proc.poll() is None:
                proc.terminate()
            break
        except Exception as e:
            logger.error(f"Error launching kiosk: {e}")
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Core AI Ambient Smart Mirror & Wall Projection Kiosk Launcher")
    parser.add_argument("--url", default="http://localhost:8000/mirror", help="Target URL for Ambient HUD")
    parser.add_argument("--browser", default=None, help="Explicit path to browser executable")
    parser.add_argument("--no-kiosk", action="store_true", help="Launch maximized without locking into kiosk mode")
    parser.add_argument("--no-watchdog", action="store_true", help="Disable automatic restart upon browser exit")

    args = parser.parse_args()
    run_kiosk(
        url=args.url,
        browser_path=args.browser,
        kiosk_mode=not args.no_kiosk,
        watchdog=not args.no_watchdog
    )
