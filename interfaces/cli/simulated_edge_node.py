import asyncio
import json
import sys
import os

# Ensure root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import websockets

async def run_edge_client(node_id: str = "vehicle_car", gateway_url: str = "ws://localhost:8000/ws/nodes"):
    url = f"{gateway_url}/{node_id}"
    print(f"[*] Starting Simulated Edge Client for '{node_id}' connecting to {url}...")

    async with websockets.connect(url) as ws:
        # 1. Send Handshake Registration
        registration = {
            "type": "register",
            "data": {
                "node_id": node_id,
                "device_type": "vehicle_car",
                "capabilities": ["car_lock_doors", "car_preheat_cabin", "car_obd_telemetry"],
                "initial_zone": "mobile/vehicle/car",
                "is_fixed_anchor": False,
                "battery_level": 88.5,
                "network_type": "tailscale"
            }
        }
        await ws.send(json.dumps(registration))
        resp = await ws.recv()
        print(f"[OK] Registered with Gateway: {resp}")

        # 2. Listen for Remote Tool Executions
        print(f"[*] Listening for remote tool execution requests from Core AI...")
        while True:
            msg_raw = await ws.recv()
            data = json.loads(msg_raw)
            print(f"\n[>>] Received request: {data}")

            if data.get("type") == "tool_call_request":
                req_id = data.get("request_id")
                tool_name = data.get("tool_name")
                args = data.get("arguments", {})

                # Simulate vehicle action
                print(f"[+] Simulating physical action '{tool_name}' with args {args}...")
                await asyncio.sleep(0.5)

                result_payload = {
                    "status": "success",
                    "device": node_id,
                    "action": tool_name,
                    "state": "executed",
                    "timestamp": asyncio.get_event_loop().time()
                }

                # Send response back to Gateway
                response = {
                    "type": "tool_call_response",
                    "request_id": req_id,
                    "result": result_payload
                }
                await ws.send(json.dumps(response))
                print(f"[OK] Dispatched tool response back to Core AI for request '{req_id[:8]}'")

if __name__ == "__main__":
    node = sys.argv[1] if len(sys.argv) > 1 else "vehicle_car"
    try:
        asyncio.run(run_edge_client(node_id=node))
    except KeyboardInterrupt:
        print("\n[*] Edge client stopped.")
