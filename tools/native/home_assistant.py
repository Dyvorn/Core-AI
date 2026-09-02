import logging

logger = logging.getLogger(__name__)

class HomeAssistantMock:
    """Mock for Home Assistant websocket/REST API"""
    
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        
    def call_service(self, entity_id: str, action: str) -> dict:
        logger.info(f"Mock HA Call: {action} on {entity_id}")
        return {"status": "success", "entity_id": entity_id, "state": "on" if action == "turn_on" else "off"}

ha_call_schema = {
    "name": "home_assistant_call",
    "description": "Call a Home Assistant service on an entity",
    "parameters": {
        "type": "object",
        "properties": {
            "entity_id": {"type": "string", "description": "The entity ID (e.g., light.living_room)"},
            "action": {"type": "string", "description": "The action (e.g., turn_on, turn_off)"}
        },
        "required": ["entity_id", "action"]
    }
}
