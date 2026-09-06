import os
import sys
import socket
import subprocess
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def scan_local_network(timeout_sec: float = 1.0) -> Dict[str, Any]:
    """
    Discovers active devices and hosts on the local network (LAN / Wi-Fi).
    Inspects system ARP table and queries hostnames without external heavy dependencies.
    """
    devices: List[Dict[str, Any]] = []
    seen_ips = set()

    # 1. Parse local ARP table (works on Windows, Linux, and macOS)
    try:
        cmd = ["arp", "-a"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec + 1.0)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                # On Windows: Internet Address / Physical Address / Type
                # On Linux: hostname (ip) at mac [ether] on iface
                candidate_ip = None
                mac = None
                for p in parts:
                    clean = p.strip("()")
                    octets = clean.split(".")
                    if len(octets) == 4 and all(o.isdigit() and 0 <= int(o) <= 255 for o in octets):
                        if clean not in ("255.255.255.255", "127.0.0.1", "0.0.0.0") and not clean.startswith("224."):
                            candidate_ip = clean
                    elif "-" in p or ":" in p:
                        if len(p.replace("-", "").replace(":", "")) == 12:
                            mac = p

                if candidate_ip and candidate_ip not in seen_ips:
                    seen_ips.add(candidate_ip)
                    # Attempt quick reverse hostname lookup
                    hostname = None
                    try:
                        hostname = socket.gethostbyaddr(candidate_ip)[0]
                    except Exception:
                        hostname = None

                    # Infer device hint
                    hint = "smart_device"
                    h_lower = (hostname or "").lower()
                    if "fridge" in h_lower or "refrigerator" in h_lower or "samsung" in h_lower:
                        hint = "smart_fridge"
                    elif "homeassistant" in h_lower or "hass" in h_lower:
                        hint = "home_assistant_server"
                    elif "tv" in h_lower or "roku" in h_lower or "bravia" in h_lower:
                        hint = "smart_tv"
                    elif "phone" in h_lower or "android" in h_lower or "iphone" in h_lower:
                        hint = "mobile_phone"
                    elif "router" in h_lower or "gateway" in h_lower:
                        hint = "network_router"

                    devices.append({
                        "ip": candidate_ip,
                        "mac": mac or "unknown",
                        "hostname": hostname,
                        "device_hint": hint
                    })
    except Exception as e:
        logger.warning(f"ARP table query encountered an issue: {e}")

    # Fallback to localhost if network isolation is active
    if not devices:
        devices.append({
            "ip": "127.0.0.1",
            "mac": "00:00:00:00:00:00",
            "hostname": "localhost",
            "device_hint": "local_core_host"
        })

    return {
        "status": "success",
        "device_count": len(devices),
        "devices": devices
    }


def inspect_lan_device(host_or_ip: str, port: int = 80, timeout_sec: float = 1.0) -> Dict[str, Any]:
    """
    Inspects a specific LAN device over HTTP/TCP to detect service banners,
    smart device identities, and whether Core AI edge client is installed.
    """
    is_reachable = False
    banner = None
    device_hint = "unknown_device"
    core_installed = False

    try:
        with socket.create_connection((host_or_ip, port), timeout=timeout_sec) as s:
            is_reachable = True
            # Send lightweight HTTP GET to check headers
            req = f"GET / HTTP/1.1\r\nHost: {host_or_ip}\r\nUser-Agent: CoreAI-Scanner/1.0\r\nConnection: close\r\n\r\n"
            s.sendall(req.encode("utf-8"))
            resp = s.recv(1024).decode("utf-8", errors="ignore")
            if resp:
                banner = resp[:200]
                resp_lower = resp.lower()
                if "core ai" in resp_lower or "core-ai" in resp_lower:
                    core_installed = True
                    device_hint = "core_ai_node"
                elif "home assistant" in resp_lower or "homeassistant" in resp_lower:
                    device_hint = "home_assistant_server"
                elif "smartthings" in resp_lower or "tizen" in resp_lower or "fridge" in resp_lower:
                    device_hint = "smart_fridge"
    except Exception as e:
        logger.debug(f"Device inspection on {host_or_ip}:{port} failed: {e}")

    return {
        "status": "success",
        "host": host_or_ip,
        "port": port,
        "is_reachable": is_reachable,
        "core_installed": core_installed,
        "device_hint": device_hint,
        "details": banner
    }


scan_local_network_schema = {
    "name": "scan_local_network",
    "description": "Scans the local LAN/Wi-Fi network to discover active smart devices, appliances (e.g. smart fridges, smart TVs), and edge nodes",
    "parameters": {
        "type": "object",
        "properties": {
            "timeout_sec": {"type": "number", "description": "Probe timeout in seconds (default: 1.0)"}
        }
    }
}

inspect_lan_device_schema = {
    "name": "inspect_lan_device",
    "description": "Inspects a specific LAN IP address or host to identify appliance type and check if Core AI edge node is installed",
    "parameters": {
        "type": "object",
        "properties": {
            "host_or_ip": {"type": "string", "description": "Target IP or hostname on the LAN"},
            "port": {"type": "integer", "description": "Port to inspect (default: 80, 8123, 8000, 8080)"},
            "timeout_sec": {"type": "number", "description": "Timeout in seconds (default: 1.0)"}
        },
        "required": ["host_or_ip"]
    }
}
