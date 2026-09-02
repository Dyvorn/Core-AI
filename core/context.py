import yaml
from typing import List, Dict, Optional
from .schemas import NodeInfo, SpatialContext
import logging

logger = logging.getLogger(__name__)

class ContextManager:
    """
    Manages ubiquitous device topology and spatial zones:
    - Indoor rooms
    - Outdoor ground and property
    - Vehicles (car, bike)
    - Wearables (smart glasses, phone, smartwatch)
    """
    
    def __init__(self, config_path: str = "config/nodes.yaml", state_manager=None):
        self.nodes: Dict[str, NodeInfo] = {}
        self.state_manager = state_manager
        self.load_nodes(config_path)

    def load_nodes(self, config_path: str):
        try:
            import os
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and 'nodes' in data and data['nodes']:
                        for node_data in data['nodes']:
                            node = NodeInfo(**node_data)
                            self.nodes[node.id] = node
                logger.info(f"Loaded {len(self.nodes)} nodes from config")
        except Exception as e:
            logger.warning(f"Could not load static nodes from {config_path} (will use dynamic state discovery): {e}")

    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        if node_id in self.nodes:
            return self.nodes[node_id]
        
        # Dynamic fallback to StateManager database
        if self.state_manager:
            device = self.state_manager.get_device_record(node_id)
            if device:
                return NodeInfo(
                    id=device.device_id,
                    name=device.name,
                    type=device.device_type,
                    capabilities=device.capabilities,
                    zone=device.current_zone,
                    connectivity="local"
                )
        return None

    def get_zone_for_node(self, node_id: str) -> str:
        """Returns the hierarchical zone of the node, dynamically resolving if needed."""
        node = self.get_node(node_id)
        if node and node.zone:
            return node.zone
        return "default"


    def get_room_for_node(self, node_id: str) -> str:
        """Backward-compatible helper for room-based workflows."""
        node = self.get_node(node_id)
        if node:
            if node.zone:
                return node.zone
            return node.id
        return "default_room"

    def get_nodes_by_type(self, node_type: str) -> List[NodeInfo]:
        """Returns all nodes matching a device category (e.g. 'smart_glasses', 'vehicle_car', 'phone')."""
        return [node for node in self.nodes.values() if node.type == node_type]

    def get_node_capabilities(self, node_id: str) -> List[str]:
        """Returns the list of modalities the node can handle (e.g. ['hud_display', 'camera', 'speaker'])."""
        node = self.get_node(node_id)
        return node.capabilities if node else []
