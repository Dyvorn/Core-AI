import os
import sys
import json
import argparse
import socket
import asyncio
import urllib.request
import urllib.error

def enroll_device(
    server_url: str,
    device_name: str,
    device_type: str,
    target_zone: str,
    auth_secret: str,
    request_owner: bool = True
):
    hostname = socket.gethostname()
    device_id = f"{device_type}_{hostname.lower().replace(' ', '_')}"
    
    print(f"[*] Core AI Zero-Friction Device Onboarding")
    print(f"[*] Target Gateway: {server_url}")
    print(f"[*] Enrolling Device: '{device_name}' (ID: {device_id}, Type: {device_type}, Zone: {target_zone})")

    payload = {
        "device_id": device_id,
        "device_name": device_name,
        "device_type": device_type,
        "target_zone": target_zone,
        "requested_trust_tier": "owner" if request_owner else "guest",
        "capabilities": ["mic", "speaker", "notifications", "local_commands"],
        "auth_secret": auth_secret
    }

    req = urllib.request.Request(
        f"{server_url.rstrip('/')}/api/v1/devices/enroll",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            print(f"\n[+] Enrollment Result: {result.get('status').upper()}")
            print(f"[+] Assigned Trust Tier: {result.get('assigned_trust_tier').upper()}")
            print(f"[+] Session Token: {result.get('session_token')[:8]}...")
            print(f"[+] WebSocket Node Gateway: {result.get('gateway_ws_url')}")
            print(f"\n[OK] {result.get('message')}")
            print(f"[OK] This device is now integrated into Core AI's ubiquitous mesh!")
            return result
    except urllib.error.HTTPError as e:
        print(f"[-] HTTP Error {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        print(f"[-] Ensure Core AI Gateway is running at {server_url}")
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Core AI Zero-Friction Device Onboarding")
    parser.add_argument("--server", default="http://localhost:8000", help="Core AI Gateway URL")
    parser.add_argument("--device-name", default=socket.gethostname(), help="Human-readable device name")
    parser.add_argument("--device-type", default="laptop", choices=["laptop", "phone", "raspberry_pi", "arduino_bridge", "vehicle_car", "smart_glasses"])
    parser.add_argument("--zone", default="home/indoor/studio", help="Initial spatial zone")
    parser.add_argument("--secret", default="core_sovereign_secret", help="Owner authentication secret")
    parser.add_argument("--guest", action="store_true", help="Enroll as guest device")

    args = parser.parse_args()
    enroll_device(
        server_url=args.server,
        device_name=args.device_name,
        device_type=args.device_type,
        target_zone=args.zone,
        auth_secret=args.secret,
        request_owner=not args.guest
    )
