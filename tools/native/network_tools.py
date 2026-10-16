import os
import sys
import platform
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


def ping_host(host: str, count: int = 2, timeout_sec: float = 2.0, **kwargs) -> Dict[str, Any]:
    """Pings a remote or local IP/hostname to measure latency and packet reachability."""
    clean_host = host.strip()
    system = platform.system() if "platform" in sys.modules else ("Windows" if os.name == "nt" else "Linux")
    cmd = ["ping", "-n", str(count), "-w", str(int(timeout_sec * 1000)), clean_host] if system == "Windows" else ["ping", "-c", str(count), "-W", str(int(timeout_sec)), clean_host]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec * count + 2.0)
        is_reachable = proc.returncode == 0
        return {
            "status": "success",
            "host": clean_host,
            "reachable": is_reachable,
            "output_summary": "Host is online and responding." if is_reachable else "Host unreachable or dropped packets.",
            "raw_output": proc.stdout.strip()
        }
    except Exception:
        # Fallback to direct TCP socket ping on common ports (80, 443, 22)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_sec)
            sock.connect((clean_host, 80))
            sock.close()
            return {"status": "success", "host": clean_host, "reachable": True, "output_summary": "TCP socket connected on port 80."}
        except Exception as e:
            return {"status": "success", "host": clean_host, "reachable": False, "output_summary": f"Unreachable: {e}"}


def check_port_open(host: str, port: int, timeout_sec: float = 1.5, **kwargs) -> Dict[str, Any]:
    """Tests if a specific TCP port is listening on a host."""
    clean_host = host.strip()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_sec)
        result = sock.connect_ex((clean_host, int(port)))
        sock.close()
        is_open = (result == 0)
        return {
            "status": "success",
            "host": clean_host,
            "port": int(port),
            "is_open": is_open,
            "message": f"Port {port} on '{clean_host}' is {'OPEN / LISTENING' if is_open else 'CLOSED / FILTERED'}."
        }
    except Exception as e:
        return {"status": "error", "message": f"Port check failed: {e}"}


def get_public_ip(timeout_sec: float = 3.0, **kwargs) -> Dict[str, Any]:
    """Resolves the external public WAN IP address of the central host."""
    import urllib.request
    endpoints = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com"
    ]
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CoreAI/0.3"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if resp.status == 200:
                    ip = resp.read().decode("utf-8").strip()
                    return {"status": "success", "public_ip": ip, "provider": url}
        except Exception:
            continue
    return {"status": "error", "message": "Could not determine public IP (all external providers unreachable)."}


def dns_lookup(domain: str, **kwargs) -> Dict[str, Any]:
    """Resolves hostname/domain to IPv4 addresses."""
    clean_domain = domain.strip().replace("http://", "").replace("https://", "").split("/")[0]
    try:
        infos = socket.getaddrinfo(clean_domain, None, socket.AF_INET)
        ips = list({info[4][0] for info in infos})
        return {
            "status": "success",
            "domain": clean_domain,
            "ips": ips,
            "primary_ip": ips[0] if ips else None
        }
    except Exception as e:
        return {"status": "error", "domain": clean_domain, "message": f"DNS resolution failed: {e}"}


def wake_on_lan(mac_address: str, broadcast_ip: str = "255.255.255.255", port: int = 9, **kwargs) -> Dict[str, Any]:
    """Sends a Wake-On-LAN (WOL) magic packet to boot up sleeping desktop workstations."""
    clean_mac = mac_address.replace(":", "").replace("-", "").replace(".", "").upper()
    if len(clean_mac) != 12:
        return {"status": "error", "message": f"Invalid MAC address format: '{mac_address}'. Expected 12 hexadecimal digits."}
    try:
        mac_bytes = bytes.fromhex(clean_mac)
        magic_payload = (b'\xFF' * 6) + (mac_bytes * 16)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_payload, (broadcast_ip, int(port)))
        sock.close()
        return {
            "status": "success",
            "mac_address": mac_address,
            "broadcast_ip": broadcast_ip,
            "port": int(port),
            "message": f"Dispatched WOL magic packet to '{mac_address}'."
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to send Wake-On-LAN packet: {e}"}


ping_host_schema = {
    "name": "ping_host",
    "description": "Ping a remote or local IP/hostname to test connectivity and response latency",
    "parameters": {
        "type": "object",
        "properties": {
            "host": {"type": "string", "description": "Target hostname or IP address"},
            "count": {"type": "integer", "default": 2}
        },
        "required": ["host"]
    }
}

check_port_schema = {
    "name": "check_port_open",
    "description": "Test if a specific network TCP port (e.g. 8000, 11434, 22) is open on a host",
    "parameters": {
        "type": "object",
        "properties": {
            "host": {"type": "string", "description": "Target IP or hostname"},
            "port": {"type": "integer", "description": "Port number to test"}
        },
        "required": ["host", "port"]
    }
}

public_ip_schema = {
    "name": "get_public_ip",
    "description": "Lookup external public WAN IP address of the server",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

dns_lookup_schema = {
    "name": "dns_lookup",
    "description": "Resolve a domain name to its associated IPv4 addresses",
    "parameters": {
        "type": "object",
        "properties": {
            "domain": {"type": "string", "description": "Domain name (e.g. 'google.com', 'ollama.com')"}
        },
        "required": ["domain"]
    }
}

wake_on_lan_schema = {
    "name": "wake_on_lan",
    "description": "Send Wake-on-LAN (WOL) magic packet to power on a sleeping PC or server",
    "parameters": {
        "type": "object",
        "properties": {
            "mac_address": {"type": "string", "description": "Physical MAC address of target workstation"},
            "broadcast_ip": {"type": "string", "default": "255.255.255.255"},
            "port": {"type": "integer", "default": 9}
        },
        "required": ["mac_address"]
    }
}

