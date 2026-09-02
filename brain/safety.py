import logging

logger = logging.getLogger(__name__)

class SafetyGate:
    """Human-in-the-loop validation for critical actions"""
    
    def requires_confirmation(self, tool_name: str, args: dict) -> bool:
        # e.g., unlocking doors, making purchases
        critical_tools = ["unlock_door", "purchase_item"]
        return tool_name in critical_tools
