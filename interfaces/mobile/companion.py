"""
Core AI :: Mobile Companion & Nothing OS Glyph Protocol
Phase 4 Mobile Integration:
- Zero-friction token enrollment with sovereign authentication
- Real-time lock-screen glanceable telemetry (reminders, hardware vitals, active satellites)
- Nothing OS rear Glyph Matrix LED driver patterns (reasoning_pulse, success_flash, alert_burst)
"""

import os
import sys
import re
import json
import time
import socket
import argparse
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from core.schemas import GlyphPattern
from core.terminal import render_box, CYAN, GREEN, YELLOW, RED, MAGENTA, BOLD, RESET

logger = logging.getLogger("CoreAI.MobileCompanion")
DIM = "\033[90m"


def render_glyph_matrix(pattern: str = "reasoning_pulse", brightness: int = 255) -> str:
    """
    Renders high-contrast ANSI visualization of Nothing Phone (2) physical Glyph Interface backplate.
    Visualizes addressable LED segments:
    - Upper-left dual camera circle
    - Top-right diagonal slash
    - Central charging coil / reasoning ring (multi-segment)
    - Bottom exclamation mark (battery / alert bar)
    """
    pat = pattern.lower()

    if pat == "reasoning_pulse":
        cam_col = DIM
        slash_col = YELLOW
        coil_col = f"\033[38;5;220;1m"  # Glowing Amber/Gold
        bar_col = DIM
        tag = f"{YELLOW}REASONING PULSE (Coil Segmented Progress){RESET}"
    elif pat == "success_flash":
        cam_col = GREEN
        slash_col = GREEN
        coil_col = GREEN
        bar_col = GREEN
        tag = f"{GREEN}SUCCESS FLASH (All Zones High Strobe){RESET}"
    elif pat == "alert_burst":
        cam_col = RED
        slash_col = RED
        coil_col = RED
        bar_col = f"\033[91;1m"
        tag = f"{RED}ALERT BURST (Critical Priority Hazard){RESET}"
    elif pat == "listening":
        cam_col = CYAN
        slash_col = CYAN
        coil_col = CYAN
        bar_col = CYAN
        tag = f"{CYAN}LISTENING (Sensor Intake Active){RESET}"
    else:  # idle or other
        cam_col = DIM
        slash_col = DIM
        coil_col = DIM
        bar_col = DIM
        tag = f"{DIM}IDLE (Ambient Standby){RESET}"

    pct = int((brightness / 255.0) * 100)

    # Detect if console encoding natively supports Unicode box-drawing characters
    encoding = (getattr(sys.stdout, "encoding", "") or "").lower()
    use_unicode = encoding.startswith("utf") or sys.platform != "win32"

    if use_unicode:
        c_tl, c_tr, c_bl, c_br = "╭", "╮", "╰", "╯"
        b_tl, b_tr, b_bl, b_br = "┌", "┐", "└", "┘"
        b_h, b_v = "─", "│"
        dot = "◉"
        slash = "╲"
        bar = "█"
        pip = "●"
    else:
        c_tl, c_tr, c_bl, c_br = "+", "+", "+", "+"
        b_tl, b_tr, b_bl, b_br = "+", "+", "+", "+"
        b_h, b_v = "-", "|"
        dot = "o"
        slash = "\\"
        bar = "#"
        pip = "*"

    lines = [
        f"{DIM}{b_tl}{b_h * 42}{b_tr}{RESET}",
        f"{DIM}{b_v}{RESET}  {cam_col}{c_tl}────{c_tr}{RESET}               {slash_col}{slash}{slash}{RESET}                 {DIM}{b_v}{RESET}  Nothing Phone (2) Glyph Backplate",
        f"{DIM}{b_v}{RESET}  {cam_col}{b_v} {dot}  {b_v}{RESET}                {slash_col}{slash}{slash}{RESET}                {DIM}{b_v}{RESET}  Zone: Rear Glass Transparency",
        f"{DIM}{b_v}{RESET}  {cam_col}{b_v} {dot}  {b_v}{RESET}                                  {DIM}{b_v}{RESET}  Pattern: {tag}",
        f"{DIM}{b_v}{RESET}  {cam_col}{c_bl}────{c_br}{RESET}       {coil_col}{c_tl}───────────{c_tr}{RESET}              {DIM}{b_v}{RESET}  Intensity: {BOLD}{pct}%{RESET} ({brightness}/255)",
        f"{DIM}{b_v}{RESET}              {coil_col}{b_v}  {c_tl}─────{c_tr}  {b_v}{RESET}              {DIM}{b_v}{RESET}",
        f"{DIM}{b_v}{RESET}              {coil_col}{b_v}  {b_v} (G) {b_v}  {b_v}{RESET}              {DIM}{b_v}{RESET}  [Zone Matrix]:",
        f"{DIM}{b_v}{RESET}              {coil_col}{b_v}  {c_bl}─────{c_br}  {b_v}{RESET}              {DIM}{b_v}{RESET}  • Camera Ring:    {'[ON]' if cam_col != DIM else '[--]'}",
        f"{DIM}{b_v}{RESET}               {coil_col}{c_bl}───────────{c_br}{RESET}              {DIM}{b_v}{RESET}  • Diagonal Slash: {'[ON]' if slash_col != DIM else '[--]'}",
        f"{DIM}{b_v}{RESET}                                          {DIM}{b_v}{RESET}  • Central Arc:    {'[ACTIVE]' if coil_col != DIM else '[--]'}",
        f"{DIM}{b_v}{RESET}                    {bar_col}{bar}|{bar}{RESET}                   {DIM}{b_v}{RESET}  • Exclamation:    {'[LIT]' if bar_col != DIM else '[--]'}",
        f"{DIM}{b_v}{RESET}                    {bar_col} {pip} {RESET}                   {DIM}{b_v}{RESET}",
        f"{DIM}{b_bl}{b_h * 42}{b_br}{RESET}"
    ]
    return "\n".join(lines)


SESSION_FILE_PATH = os.path.expanduser("~/.core_ai_mobile_session.json")


class MobileCompanionClient:
    """
    Sovereign Mobile Companion Client:
    Communicates with Core AI Gateway over LAN or Tailscale WireGuard mesh.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        client_id: Optional[str] = None,
        token: Optional[str] = None,
        session_file: Optional[str] = None
    ):
        self.session_file = session_file or os.getenv("CORE_MOBILE_SESSION_FILE") or SESSION_FILE_PATH
        saved_session = self._load_session()

        target = (server_url or os.getenv("CORE_SERVER_URL") or saved_session.get("server_url") or "http://localhost:8000").rstrip("/")
        self.server_url = target
        raw_cid = client_id or saved_session.get("client_id") or f"phone_{socket.gethostname().lower()}"
        self.client_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(raw_cid))
        self.token: Optional[str] = token or saved_session.get("token")
        self.device_name: str = saved_session.get("device_name") or "Nothing Phone (2)"

        # If pointing to localhost and not overridden explicitly, attempt LAN auto-discovery if offline
        if not server_url and not os.getenv("CORE_SERVER_URL"):
            is_local_alive = False
            try:
                probe_req = urllib.request.Request(f"{self.server_url}/api/v1/health", headers={"User-Agent": "CoreAI-Probe"})
                with urllib.request.urlopen(probe_req, timeout=0.5) as resp:
                    if resp.status == 200:
                        is_local_alive = True
            except Exception as probe_err:
                logger.debug(f"Local gateway probe notice: {probe_err}")

            if not is_local_alive:
                try:
                    from core.discovery import discover_core_servers
                    found = discover_core_servers(timeout=1.0)
                    if found:
                        self.server_url = found[0]["url"]
                        logger.info(f"Auto-discovered Core AI Gateway at {self.server_url}")
                except Exception as disc_err:
                    logger.debug(f"LAN discovery notice: {disc_err}")

    def _load_session(self) -> Dict[str, Any]:
        """Loads cached session authentication credentials from disk if present."""
        if self.session_file and os.path.exists(self.session_file):
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"Failed to read mobile session file: {e}")
        return {}

    def _save_session(self, data: Dict[str, Any]):
        """Persists session authentication credentials to disk for seamless CLI usage."""
        if not self.session_file:
            return
        try:
            parent_dir = os.path.dirname(os.path.abspath(self.session_file))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if sys.platform != "win32":
                try:
                    os.chmod(self.session_file, 0o600)
                except OSError:
                    pass
        except Exception as e:
            logger.debug(f"Failed to write mobile session file: {e}")

    def clear_session(self):
        """Removes local cached session file."""
        self.token = None
        if self.session_file and os.path.exists(self.session_file):
            try:
                os.remove(self.session_file)
            except Exception as e:
                logger.debug(f"Failed to clear mobile session file: {e}")

    def enroll(
        self,
        device_name: str = "Mobile Companion",
        model: str = "Nothing Phone (2)",
        auth_secret: Optional[str] = None,
        pairing_code: Optional[str] = None,
        target_zone: str = "mobile/default"
    ) -> Dict[str, Any]:
        """Enrolls device with the central Core AI Gateway."""
        url = f"{self.server_url}/api/v1/mobile/enroll"
        payload = {
            "client_id": self.client_id,
            "device_name": device_name,
            "model": model,
            "target_zone": target_zone,
            "auth_secret": auth_secret or os.getenv("CORE_AUTH_SECRET", "core_sovereign_secret"),
            "pairing_code": pairing_code,
            "capabilities": ["glance_cards", "voice_stream", "glyph_matrix", "ble_gateway"]
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "CoreAI-MobileCompanion"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.token = data.get("token")
                self.device_name = device_name
                if data.get("status") == "enrolled":
                    self._save_session({
                        "token": self.token,
                        "client_id": self.client_id,
                        "server_url": self.server_url,
                        "device_name": self.device_name,
                        "assigned_tier": data.get("assigned_tier")
                    })
                return data
        except Exception as e:
            logger.error(f"Failed to enroll mobile device: {e}")
            return {"status": "error", "message": str(e)}

    def get_glance(self) -> Dict[str, Any]:
        """Fetches glanceable telemetry for lock screen cards and quick settings."""
        url = f"{self.server_url}/api/v1/mobile/glance"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CoreAI-MobileCompanion"}
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to fetch glance state: {e}")
            return {"status": "error", "message": str(e)}

    def trigger_glyph(
        self,
        pattern: str = "reasoning_pulse",
        brightness: int = 255,
        duration_ms: int = 500
    ) -> Dict[str, Any]:
        """Dispatches Nothing OS Glyph Matrix pattern to the gateway."""
        url = f"{self.server_url}/api/v1/mobile/glyph"
        payload = {
            "pattern": pattern,
            "brightness": brightness,
            "duration_ms": duration_ms
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "CoreAI-MobileCompanion"}
        )
        try:
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to trigger glyph: {e}")
            return {"status": "error", "message": str(e)}

    def send_command(self, goal: str) -> Dict[str, Any]:
        """
        Dispatches a task from the mobile companion to the gateway with Nothing OS Glyph Matrix reactive feedback:
        - Fires reasoning_pulse LED during planning
        - Fires success_flash LED on completion (or alert_burst on failure)
        """
        self.trigger_glyph("reasoning_pulse", duration_ms=400)
        url = f"{self.server_url}/api/v1/pipeline/solve_sync"
        payload = {
            "goal": goal,
            "context": {
                "source": "mobile_companion",
                "client_id": self.client_id,
                "token": self.token,
                "device_name": self.device_name
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "CoreAI-MobileCompanion"}
        )
        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "error":
                    self.trigger_glyph("alert_burst", duration_ms=300)
                else:
                    self.trigger_glyph("success_flash", duration_ms=250)
                return data
        except Exception as e:
            self.trigger_glyph("alert_burst", duration_ms=300)
            logger.error(f"Failed to dispatch mobile command: {e}")
            return {"status": "error", "message": str(e)}

    def print_glance_card(self):
        """Renders high-contrast lock screen glance card on terminal."""
        glance = self.get_glance()
        if glance.get("status") == "error":
            print(f"{RED}[ERROR] Could not connect to Core AI Gateway at {self.server_url}{RESET}")
            return

        vitals = glance.get("system_vitals", {})
        cpu = vitals.get("cpu_percent", "N/A")
        ram = vitals.get("memory", {}).get("percent", "N/A") if isinstance(vitals.get("memory"), dict) else "N/A"
        reminders = glance.get("unread_reminders", [])
        rem_str = f"{len(reminders)} Active" if reminders else "None"

        rows = [
            ("Operator:", f"{GREEN}{glance.get('operator_name', 'Operator')}{RESET}"),
            ("Primary Space:", f"{YELLOW}{glance.get('primary_space', 'office')}{RESET}"),
            ("Active AI Model:", f"{CYAN}{glance.get('active_model', 'N/A')}{RESET}"),
            ("System Hardware:", f"CPU: {cpu}% | RAM: {ram}%"),
            ("Active Reminders:", f"{MAGENTA}{rem_str}{RESET}"),
            ("Voice Satellites:", f"{GREEN}{glance.get('active_satellites_count', 0)} Online{RESET}"),
            ("Kernel Protocol:", f"{CYAN}v{glance.get('version', '0.2.2-alpha')}{RESET}")
        ]

        card = render_box(
            title="C.O.R.E. AI :: MOBILE GLANCE MATRIX",
            rows=rows,
            width=68
        )
        print(f"\n{card}\n")


def main():
    parser = argparse.ArgumentParser(description="Core AI Mobile Companion & Glyph Driver")
    parser.add_argument("action", nargs="?", default="glance", choices=["glance", "status", "enroll", "glyph", "ask", "logout", "reset-session"], help="Action to perform")
    parser.add_argument("extra", nargs="*", help="Extra arguments (e.g. prompt for ask)")
    parser.add_argument("--server", default="http://localhost:8000", help="Core AI Gateway URL")
    parser.add_argument("--client-id", default=None, help="Mobile device unique ID")
    parser.add_argument("--token", default=None, help="Explicit session token override")
    parser.add_argument("--pattern", default="reasoning_pulse", help="Glyph pattern (idle, listening, reasoning_pulse, success_flash, alert_burst)")
    parser.add_argument("--duration", type=int, default=500, help="Glyph pattern duration in milliseconds")
    parser.add_argument("--secret", default=None, help="Authentication secret")

    args = parser.parse_args()
    client = MobileCompanionClient(server_url=args.server, client_id=args.client_id, token=args.token)

    if args.action in ("glance", "status"):
        client.print_glance_card()

    elif args.action in ("logout", "reset-session"):
        client.clear_session()
        print(f"{GREEN}[OK] Mobile companion session cleared.{RESET}")

    elif args.action == "enroll":
        print(f"[*] Enrolling Mobile Companion with {args.server}...")
        res = client.enroll(auth_secret=args.secret)
        if res.get("status") == "enrolled":
            tier = str(res.get("assigned_tier") or "guest").upper()
            token = str(res.get("token") or "")
            tok_preview = f"{token[:12]}..." if token else "N/A"
            print(f"{GREEN}[OK] Successfully enrolled '{res.get('client_id')}' as {tier}!{RESET}")
            print(f"     Session Token: {tok_preview}")
            print(f"     WebSocket URL: {res.get('gateway_ws_url')}")
        else:
            print(f"{RED}[FAIL] Enrollment failed: {res.get('message')}{RESET}")

    elif args.action == "glyph":
        pattern = args.extra[0] if args.extra else args.pattern
        print(f"[*] Triggering Nothing OS Glyph pattern '{pattern}' ({args.duration}ms)...")
        print("\n" + render_glyph_matrix(pattern, brightness=255) + "\n")
        res = client.trigger_glyph(pattern=pattern, duration_ms=args.duration)
        if res.get("status") == "dispatched":
            print(f"{GREEN}[OK] Glyph matrix pattern '{pattern}' dispatched!{RESET}")
        else:
            print(f"{RED}[FAIL] Could not dispatch glyph: {res.get('message')}{RESET}")

    elif args.action == "ask":
        prompt = " ".join(args.extra).strip()
        if not prompt:
            print(f"{YELLOW}Usage: python -m interfaces.mobile.companion ask <prompt>{RESET}")
            sys.exit(1)
        print(f"[*] Dispatching prompt from mobile companion: '{prompt}'...")
        res = client.send_command(prompt)
        if res.get("status") == "error":
            print(f"{RED}[FAIL] {res.get('message')}{RESET}")
            sys.exit(1)
        spoken = res.get("spoken_response") or res.get("final_output") or "Done."
        print(f"\n{GREEN}[Core AI Spoken Response]{RESET} {BOLD}{spoken}{RESET}\n")


if __name__ == "__main__":
    main()
