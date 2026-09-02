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
    
    def __init__(self, config_path: str = "config/nodes.yaml"):
        self.nodes: Dict[str, NodeInfo] = {}
        self.load_nodes(config_path)

    def load_nodes(self, config_path: str):
        try:
            with open(config_path, 'r', encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data and 'nodes' in data:
                    for node_data in data['nodes']:
                        node = NodeInfo(**node_data)
                        self.nodes[node.id] = node
            logger.info(f"Loaded {len(self.nodes)} ubiquitous nodes from config")
        except Exception as e:
            logger.error(f"Failed to load nodes from {config_path}: {e}")

    def get_node(self, node_id: str) -> Optional[NodeInfo]:
        return self.nodes.get(node_id)

    def get_zone_for_node(self, node_id: str) -> str:
        """Returns the hierarchical zone of the node (e.g. 'mobile/vehicle/car', 'home/indoor/office')."""
        node = self.get_node(node_id)
        if node and node.zone:
            return node.zone
        return "default_zone"

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
