import os
import sys
import socket
import subprocess
import logging
from typing import Dict, Any, List, Optional

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
                    # Fast local device hint without blocking DNS
                    hint = "network_router" if candidate_ip.endswith(".1") else "smart_device"

                    devices.append({
                        "ip": candidate_ip,
                        "mac": mac or "unknown",
                        "hostname": None,
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


def inspect_lan_device(
    host_or_ip: Optional[str] = None,
    port: int = 80,
    timeout_sec: float = 1.0,
    **kwargs
) -> Dict[str, Any]:
    """
    Inspects a specific LAN device over HTTP/TCP to detect service banners,
    smart device identities, and whether Core AI edge client is installed.
    """
    # Resilient target extraction supporting various parameter names from LLMs
    raw_target = (
        host_or_ip or
        kwargs.get("target_ip_address") or
        kwargs.get("target_ip") or
        kwargs.get("ip_address") or
        kwargs.get("ip") or
        kwargs.get("host") or
        kwargs.get("address") or
        kwargs.get("target_host") or
        kwargs.get("device_ip") or
        "127.0.0.1"
    )

    # Handle list or dict passed instead of string
    if isinstance(raw_target, list) and raw_target:
        first = raw_target[0]
        raw_target = (first.get("ip") or first.get("host")) if isinstance(first, dict) else str(first)
    elif isinstance(raw_target, dict):
        raw_target = raw_target.get("ip") or raw_target.get("host") or str(raw_target)

    # Clean unresolvable template strings
    clean_host = str(raw_target).strip()
    if clean_host.startswith("{{") or clean_host.startswith("$") or not clean_host:
        clean_host = "127.0.0.1"

    is_reachable = False
    banner = None
    device_hint = "unknown_device"
    core_installed = False

    try:
        with socket.create_connection((clean_host, port), timeout=timeout_sec) as s:
            is_reachable = True
            # Send lightweight HTTP GET to check headers
            req = f"GET / HTTP/1.1\r\nHost: {clean_host}\r\nUser-Agent: CoreAI-Scanner/1.0\r\nConnection: close\r\n\r\n"
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
        logger.debug(f"Device inspection on {clean_host}:{port} failed: {e}")

    return {
        "status": "success",
        "host": clean_host,
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
            "host_or_ip": {"type": "string", "description": "Target IP or hostname on the LAN (e.g. '192.168.1.1')"},
            "target_ip_address": {"type": "string", "description": "Alias for host_or_ip"},
            "port": {"type": "integer", "description": "Port to inspect (default: 80, 8123, 8000, 8080)"},
            "timeout_sec": {"type": "number", "description": "Timeout in seconds (default: 1.0)"}
        }
    }
}
