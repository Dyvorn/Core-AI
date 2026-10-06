import os
import json
import time
import socket
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple, Callable

logger = logging.getLogger("CoreAI.Discovery")

DISCOVERY_PORT = int(os.getenv("CORE_DISCOVERY_PORT", 8008))
DISCOVERY_MAGIC_REQ = "DISCOVER_CORE_AI"
DISCOVERY_MAGIC_RESP = "CORE_AI_BEACON"

class LANBeacon:
    """
    Lightweight, Zero-UI LAN UDP Auto-Discovery Beacon:
    - Broadcasts server presence over local network periodically.
    - Responds immediately to unicast and broadcast discovery requests from roaming clients.
    - Zero external dependencies: pure Python standard library sockets.
    """

    def __init__(
        self,
        service_port: int = 8000,
        discovery_port: int = DISCOVERY_PORT,
        broadcast_interval: float = 5.0,
        server_info_provider: Optional[Callable[[], Dict[str, Any]]] = None
    ):
        self.service_port = service_port
        self.discovery_port = discovery_port
        self.broadcast_interval = broadcast_interval
        self.server_info_provider = server_info_provider
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    @staticmethod
    def get_lan_ip() -> str:
        """Returns outbound LAN IPv4 address."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def _build_payload(self) -> Dict[str, Any]:
        info = {}
        if self.server_info_provider:
            try:
                info = self.server_info_provider()
            except Exception:
                pass

        lan_ip = self.get_lan_ip()
        return {
            "magic": DISCOVERY_MAGIC_RESP,
            "service": "core_ai_gateway",
            "version": "0.1.1-alpha",
            "hostname": socket.gethostname(),
            "lan_ip": lan_ip,
            "port": self.service_port,
            "url": f"http://{lan_ip}:{self.service_port}",
            "active_user": info.get("active_user", "Operator"),
            "active_model": info.get("active_model", "heuristic"),
            "timestamp": time.time()
        }

    def _listen_and_broadcast(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", self.discovery_port))
            sock.settimeout(1.0)
            self._sock = sock
        except Exception as e:
            logger.warning(f"Could not bind discovery socket on port {self.discovery_port}: {e}")
            return

        last_broadcast = 0.0
        while self.running:
            now = time.time()
            # 1. Periodic broadcast announcement
            if now - last_broadcast >= self.broadcast_interval:
                try:
                    payload = json.dumps(self._build_payload()).encode("utf-8")
                    sock.sendto(payload, ("<broadcast>", self.discovery_port))
                    last_broadcast = now
                except Exception as e:
                    logger.debug(f"Broadcast send error: {e}")

            # 2. Check for incoming discovery requests
            try:
                data, addr = sock.recvfrom(2048)
                msg = data.decode("utf-8", errors="ignore").strip()
                if DISCOVERY_MAGIC_REQ in msg:
                    # Direct response to requester
                    resp_payload = json.dumps(self._build_payload()).encode("utf-8")
                    sock.sendto(resp_payload, addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    logger.debug(f"Discovery socket recv error: {e}")

        try:
            sock.close()
        except Exception:
            pass

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._listen_and_broadcast, name="CoreLANBeaconThread", daemon=True)
        self._thread.start()
        logger.info(f"LAN Discovery Beacon active on UDP port {self.discovery_port}")

    def stop(self):
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=1.5)
        logger.info("LAN Discovery Beacon stopped.")


def discover_core_servers(timeout: float = 2.0, discovery_port: int = DISCOVERY_PORT) -> List[Dict[str, Any]]:
    """
    Scans local network via UDP broadcast to discover active Core AI Main Servers.
    Returns list of discovered server metadata dictionaries.
    """
    discovered: Dict[str, Dict[str, Any]] = {}
    sock: Optional[socket.socket] = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.3)

        # Broadcast probe packet
        probe = f"{DISCOVERY_MAGIC_REQ}:0.1.1".encode("utf-8")
        try:
            sock.sendto(probe, ("<broadcast>", discovery_port))
        except Exception as e:
            logger.debug(f"Failed to send broadcast probe: {e}")

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(2048)
                parsed = json.loads(data.decode("utf-8", errors="ignore"))
                if parsed.get("magic") == DISCOVERY_MAGIC_RESP:
                    srv_key = f"{parsed.get('lan_ip', addr[0])}:{parsed.get('port')}"
                    if srv_key not in discovered:
                        parsed["from_ip"] = addr[0]
                        discovered[srv_key] = parsed
            except socket.timeout:
                continue
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Error during LAN discovery scan: {e}")
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass

    return list(discovered.values())
