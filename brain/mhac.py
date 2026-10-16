import os
import json
import time
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from core.schemas import ClientComputeSignature, MHACHandshakeRequest, MHACHandshakeResponse

logger = logging.getLogger(__name__)

class MHACBroker:
    """
    Multiple Hardware-Aware Computing (MHAC) Capability & Context Broker:
    - Opportunistically offloads heavy AI inference to client workstations/PCs.
    - Decoupled intelligence: orchestrator state, memory, and proactive hooks stay centralized on core.
    - Evaluates compute score: ComputeScore = (CPU * 1.0) + (RAM * 0.5) + (GPU * 50.0) + (VRAM * 5.0).
    - Probes client Ollama model inventory and negotiates placement.
    - Automatic liveness monitoring, graceful zero-downtime failover to host, and auto-recovery.
    """

    def __init__(self, host_score_override: Optional[float] = None, bus: Optional[Any] = None):
        self.host_score_override = host_score_override
        self.bus = bus
        self._connected_clients: Dict[str, ClientComputeSignature] = {}
        self._dormant_clients: Dict[str, ClientComputeSignature] = {}
        self._active_compute_node: str = "host"
        self._delegated_endpoint: Optional[str] = None
        self._delegated_model: Optional[str] = None
        self._last_notice: Optional[str] = None
        self._transitions_history: List[Dict[str, Any]] = []

    def get_host_compute_signature(self) -> ClientComputeSignature:
        """Inspects local host vitals and computes host compute signature."""
        try:
            from core.service import get_host_vitals
            vitals = get_host_vitals()
            cpu_cores = int(vitals.get("cpu_count", 2))
            ram_gb = float(vitals.get("total_ram_gb", 16.0))
            gpu_hw = str(vitals.get("gpu_hardware", "None"))
            has_gpu = bool(gpu_hw and gpu_hw.lower() not in ["none", "integrated", "unknown", ""])
            
            sig = ClientComputeSignature(
                node_id="host",
                device_name="Central Host (core)",
                device_type="server",
                cpu_cores=cpu_cores,
                ram_total_gb=ram_gb,
                has_gpu=has_gpu,
                gpu_name=gpu_hw if has_gpu else None,
                vram_gb=8.0 if has_gpu else 0.0,
                ollama_endpoint=os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434")
            )
            sig.calculate_score()
            if self.host_score_override is not None:
                sig.compute_score = self.host_score_override
            return sig
        except Exception as e:
            logger.warning(f"Could not inspect host vitals for MHAC: {e}")
            # Fallback for weak host laptop (2 cores, 16GB RAM, no GPU = score 10.0)
            fallback_score = self.host_score_override if self.host_score_override is not None else 10.0
            sig = ClientComputeSignature(
                node_id="host",
                device_name="Central Host (core)",
                device_type="server",
                cpu_cores=2,
                ram_total_gb=16.0,
                has_gpu=False,
                compute_score=fallback_score
            )
            return sig

    def get_host_score(self) -> float:
        """Returns the current host compute score."""
        return self.get_host_compute_signature().compute_score

    def probe_client_models(self, ollama_endpoint: str, timeout: float = 1.0) -> List[str]:
        """Probes a remote or local Ollama endpoint for installed models."""
        if not ollama_endpoint:
            return []
        clean_ep = ollama_endpoint.rstrip("/")
        url = f"{clean_ep}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CoreAI-MHAC/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "").lower() for m in data.get("models", [])]
                    return models
        except Exception as e:
            logger.debug(f"MHAC probe to {url} failed: {e}")
        return []

    def evaluate_handshake(
        self,
        client_sig: ClientComputeSignature,
        preferred_models: Optional[List[str]] = None
    ) -> MHACHandshakeResponse:
        """
        Evaluates a client device handshake:
        1. Compares ComputeScore_client > ComputeScore_host.
        2. If client out-competes, probes client Ollama model inventory.
        3. Negotiates model placement or fallback.
        """
        host_sig = self.get_host_compute_signature()
        host_score = host_sig.compute_score
        client_score = client_sig.calculate_score()

        # Register client signature
        self._connected_clients[client_sig.node_id] = client_sig

        prefs = preferred_models or ["llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "llama3:latest", "qwen3.5:2b"]
        
        # Check if client out-competes host
        if client_score > host_score:
            endpoint = client_sig.ollama_endpoint or "http://127.0.0.1:11434"
            installed = self.probe_client_models(endpoint)
            client_sig.installed_models = installed

            # Look for a match among preferred models
            matched_model = None
            for pref in prefs:
                pref_clean = pref.lower().strip()
                if any(pref_clean == m or m.startswith(f"{pref_clean}:") for m in installed):
                    matched_model = pref
                    break

            if matched_model:
                # Accelerated Workstation Mode
                self._active_compute_node = client_sig.node_id
                self._delegated_endpoint = endpoint
                self._delegated_model = matched_model
                gpu_desc = f"{client_sig.gpu_name} ({client_sig.vram_gb or '?'}GB VRAM)" if client_sig.has_gpu else f"{client_sig.cpu_cores}-Core CPU"
                notice = (
                    f"Higher-tier compute detected on {client_sig.device_name} [{gpu_desc}]. "
                    f"Offloading execution layer to local GPU using '{matched_model}'."
                )
                self._last_notice = notice
                logger.info(f"[MHAC] Accelerated Delegation active: {notice}")

                return MHACHandshakeResponse(
                    status="accelerated_workstation",
                    active_compute_node=client_sig.node_id,
                    host_score=host_score,
                    client_score=client_score,
                    delegated_endpoint=endpoint,
                    target_model=matched_model,
                    notice_message=notice,
                    installed_on_client=installed,
                    missing_models=[]
                )
            else:
                # Missing Model Handshake Mode
                target = prefs[0]
                missing = [p for p in prefs if not any(p == m or m.startswith(f"{p}:") for m in installed)]
                notice = (
                    f"I can run this significantly faster on your machine ({client_sig.device_name}), "
                    f"but '{target}' is not installed on this device. "
                    f"Would you like me to pull it, or should I fallback to my internal processor?"
                )
                self._last_notice = notice
                logger.info(f"[MHAC] Missing Model Handshake: {notice}")

                # Safe fallback to host
                self._active_compute_node = "host"
                self._delegated_endpoint = None
                self._delegated_model = None

                return MHACHandshakeResponse(
                    status="missing_model_handshake",
                    active_compute_node="host",
                    host_score=host_score,
                    client_score=client_score,
                    delegated_endpoint=None,
                    target_model=target,
                    notice_message=notice,
                    installed_on_client=installed,
                    missing_models=missing
                )
        else:
            # Standalone / Idle Mode (host is faster or client is low-spec)
            self._active_compute_node = "host"
            self._delegated_endpoint = None
            self._delegated_model = None
            notice = f"Client compute ({client_score}) does not exceed host ({host_score}). Running self-contained on host internal processor."
            self._last_notice = notice
            logger.info(f"[MHAC] Standalone mode: {notice}")

            return MHACHandshakeResponse(
                status="standalone",
                active_compute_node="host",
                host_score=host_score,
                client_score=client_score,
                delegated_endpoint=None,
                target_model=None,
                notice_message=notice,
                installed_on_client=[],
                missing_models=[]
            )

    def trigger_client_model_pull(self, ollama_endpoint: str, model_name: str) -> Dict[str, Any]:
        """Instructs the client Ollama instance to pull a missing model."""
        clean_ep = ollama_endpoint.rstrip("/")
        url = f"{clean_ep}/api/pull"
        payload = json.dumps({"name": model_name, "stream": False}).encode("utf-8")
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json", "User-Agent": "CoreAI-MHAC/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {"status": "success", "result": data, "message": f"Pulled '{model_name}' on client."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to pull model on client: {e}"}

    def reset_delegation(self):
        """Resets delegation back to host."""
        self._active_compute_node = "host"
        self._delegated_endpoint = None
        self._delegated_model = None
        self._last_notice = "Compute delegation reset to central host."

    def get_delegated_endpoint(self) -> Optional[str]:
        """Returns the active delegated endpoint or None if running on host."""
        return self._delegated_endpoint

    def get_delegated_model(self) -> Optional[str]:
        """Returns the active delegated model or None."""
        return self._delegated_model

    @property
    def delegated_routes(self) -> Dict[str, Any]:
        """Returns active delegated routing targets."""
        if self._delegated_endpoint and self._delegated_model:
            return {
                "planner": self._delegated_endpoint,
                "model": self._delegated_model,
                "endpoint": self._delegated_endpoint
            }
        return {}

    def get_active_devices_count(self) -> int:
        """Returns count of active compute clients."""
        return len(self._connected_clients)

    def check_client_liveness(self, endpoint: Optional[str] = None, timeout: float = 0.5) -> bool:
        """
        Fast non-blocking probe to verify if a client workstation is reachable and awake.
        Returns True if endpoint responds with 200, False if unreachable or asleep.
        """
        target = endpoint or self._delegated_endpoint
        if not target:
            return False
        clean_ep = target.rstrip("/")
        url = f"{clean_ep}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CoreAI-MHAC-Liveness/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status == 200
        except Exception:
            return False

    def failover_to_host(self, reason: str = "Client workstation unreachable or asleep") -> Dict[str, Any]:
        """
        Seamless zero-downtime failover to host compute:
        Preserves client metadata in _dormant_clients for auto-recovery when the PC wakes up,
        and switches active compute node back to host immediately.
        """
        prev_node = self._active_compute_node
        prev_endpoint = self._delegated_endpoint
        prev_model = self._delegated_model

        if prev_node != "host" and prev_node in self._connected_clients:
            self._dormant_clients[prev_node] = self._connected_clients.pop(prev_node)

        self._active_compute_node = "host"
        self._delegated_endpoint = None
        self._delegated_model = None
        notice = f"Compute failover to central host: {reason}. Running on host internal processor."
        self._last_notice = notice
        logger.warning(f"[MHAC Failover] {notice}")

        transition_record = {
            "event": "failover_to_host",
            "previous_node": prev_node,
            "previous_endpoint": prev_endpoint,
            "previous_model": prev_model,
            "reason": reason,
            "timestamp": time.time()
        }
        self._transitions_history.append(transition_record)

        if self.bus:
            try:
                self.bus.publish("mhac_events", {
                    "event_type": "mhac_transition",
                    "mode": "standalone",
                    "active_compute_node": "host",
                    "reason": reason,
                    "notice": notice
                })
            except Exception:
                pass

        return {
            "status": "failed_over",
            "active_compute_node": "host",
            "reason": reason,
            "notice": notice
        }

    def recover_delegation(self, node_id: Optional[str] = None) -> bool:
        """
        Checks if a dormant workstation has awakened or reconnected, and seamlessly
        restores accelerated compute delegation.
        """
        candidates = [node_id] if node_id else list(self._dormant_clients.keys())
        for cid in candidates:
            sig = self._dormant_clients.get(cid)
            if sig and sig.ollama_endpoint:
                if self.check_client_liveness(sig.ollama_endpoint, timeout=0.8):
                    logger.info(f"[MHAC Recovery] Dormant workstation '{sig.device_name}' is reachable again. Re-negotiating...")
                    self._dormant_clients.pop(cid, None)
                    res = self.evaluate_handshake(sig)
                    if res.status == "accelerated_workstation":
                        logger.info(f"[MHAC Recovery] Accelerated compute restored to '{sig.device_name}'.")
                        record = {
                            "event": "recovered_delegation",
                            "node_id": sig.node_id,
                            "endpoint": sig.ollama_endpoint,
                            "model": res.target_model,
                            "timestamp": time.time()
                        }
                        self._transitions_history.append(record)
                        return True
        return False

    def heartbeat_step(self) -> Dict[str, Any]:
        """
        Periodic heartbeat evaluation (executed in Track 3 Daemons):
        - If accelerated: checks liveness of delegated client. If unreachable, triggers seamless failover.
        - If standalone: checks dormant clients for recovery.
        """
        if self._delegated_endpoint:
            is_alive = self.check_client_liveness(self._delegated_endpoint, timeout=0.6)
            if not is_alive:
                return self.failover_to_host(reason="Heartbeat probe timed out (workstation asleep or disconnected)")
            return {"status": "healthy", "mode": "accelerated", "node": self._active_compute_node}
        else:
            if self._dormant_clients:
                recovered = self.recover_delegation()
                if recovered:
                    return {"status": "recovered", "mode": "accelerated", "node": self._active_compute_node}
            return {"status": "healthy", "mode": "standalone", "node": "host"}

    def get_workload_matrix(self) -> Dict[str, Any]:
        """
        Returns asymmetric workload distribution between Central Host and Operator PC:
        - Server: Handles background, slow, and persistent workloads.
        - PC: Handles fast, low-latency foreground and interactive LLM workloads.
        """
        is_acc = bool(self._delegated_endpoint)
        return {
            "mode": "accelerated" if is_acc else "standalone",
            "active_compute_node": self._active_compute_node,
            "server_node": {
                "id": "host",
                "role": "Sovereign Central Host (core)",
                "workloads": [
                    "proactive_watcher_daemon",
                    "context_sentinel_track2",
                    "sqlite_state_persistence",
                    "track_3_background_daemons",
                    "memory_consolidation_and_indexing",
                    "offline_heuristic_dag_fallback"
                ]
            },
            "pc_node": {
                "id": self._active_compute_node if is_acc else None,
                "role": "High-Compute Operator Workstation / GPU",
                "endpoint": self._delegated_endpoint,
                "target_model": self._delegated_model,
                "workloads": [
                    "interactive_llm_reasoning",
                    "foreground_spoken_to_track1",
                    "heavy_dag_planning",
                    "fastpath_code_synthesis"
                ] if is_acc else []
            },
            "transitions_count": len(self._transitions_history),
            "last_notice": self._last_notice
        }

    def connect_workstation_by_endpoint(
        self,
        endpoint: str,
        device_name: str = "Operator Workstation",
        gpu_name: str = "NVIDIA RTX",
        vram_gb: float = 16.0,
        cpu_cores: int = 16,
        ram_gb: float = 32.0,
        preferred_models: Optional[List[str]] = None
    ) -> MHACHandshakeResponse:
        """
        Convenience helper to connect and evaluate a remote workstation by its endpoint.
        """
        clean_ep = endpoint.strip()
        if not clean_ep.startswith("http"):
            clean_ep = f"http://{clean_ep}"
        if ":" not in clean_ep.split("//", 1)[-1]:
            clean_ep = f"{clean_ep}:11434"

        sig = ClientComputeSignature(
            node_id=f"workstation-{abs(hash(clean_ep)) % 10000}",
            device_name=device_name,
            device_type="workstation",
            cpu_cores=cpu_cores,
            ram_total_gb=ram_gb,
            has_gpu=True,
            gpu_name=gpu_name,
            vram_gb=vram_gb,
            ollama_endpoint=clean_ep
        )
        sig.calculate_score()
        return self.evaluate_handshake(sig, preferred_models=preferred_models)

    def get_status(self) -> Dict[str, Any]:
        """Returns the complete MHAC runtime status matrix."""
        host_sig = self.get_host_compute_signature()
        clients = [c.model_dump() for c in self._connected_clients.values()]
        dormant = [c.model_dump() for c in self._dormant_clients.values()]
        return {
            "mode": "accelerated" if self._delegated_endpoint else "standalone",
            "active_compute_node": self._active_compute_node,
            "host": host_sig.model_dump(),
            "delegated_endpoint": self._delegated_endpoint,
            "delegated_model": self._delegated_model,
            "connected_clients_count": len(self._connected_clients),
            "connected_clients": clients,
            "dormant_clients_count": len(self._dormant_clients),
            "dormant_clients": dormant,
            "workload_distribution": self.get_workload_matrix(),
            "transitions_history": self._transitions_history[-5:],
            "last_notice": self._last_notice
        }


# Global MHAC broker instance
_global_mhac_broker: Optional[MHACBroker] = None

def get_mhac_broker() -> MHACBroker:
    global _global_mhac_broker
    if _global_mhac_broker is None:
        _global_mhac_broker = MHACBroker()
    return _global_mhac_broker
