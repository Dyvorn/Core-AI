import os
import json
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
    """

    def __init__(self, host_score_override: Optional[float] = None):
        self.host_score_override = host_score_override
        self._connected_clients: Dict[str, ClientComputeSignature] = {}
        self._active_compute_node: str = "host"
        self._delegated_endpoint: Optional[str] = None
        self._delegated_model: Optional[str] = None
        self._last_notice: Optional[str] = None

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

    def get_status(self) -> Dict[str, Any]:
        """Returns the complete MHAC runtime status matrix."""
        host_sig = self.get_host_compute_signature()
        clients = [c.model_dump() for c in self._connected_clients.values()]
        return {
            "mode": "accelerated" if self._delegated_endpoint else "standalone",
            "active_compute_node": self._active_compute_node,
            "host": host_sig.model_dump(),
            "delegated_endpoint": self._delegated_endpoint,
            "delegated_model": self._delegated_model,
            "connected_clients_count": len(self._connected_clients),
            "connected_clients": clients,
            "last_notice": self._last_notice
        }


# Global MHAC broker instance
_global_mhac_broker: Optional[MHACBroker] = None

def get_mhac_broker() -> MHACBroker:
    global _global_mhac_broker
    if _global_mhac_broker is None:
        _global_mhac_broker = MHACBroker()
    return _global_mhac_broker
