import logging
import re
from typing import Tuple, Dict, Any, List

logger = logging.getLogger(__name__)

class SafetyGate:
    """
    Harm-Free Unstoppable Agency & Human-in-the-Loop Safety Gate:
    - Fundamental Principle: As long as an action is helpful and does not cause real harm,
      Core AI will never refuse or preach. It will find a way to do it.
    - Zero Slop, Zero Bluff, Zero Corporate Nanny-Rails: We reject artificial moralizing refusal loops.
    - True Protection: Guards against catastrophic physical/system destruction and malicious exploits.
    """

    CRITICAL_CONFIRMATION_TOOLS = [
        "unlock_door",
        "purchase_item",
        "format_disk",
        "factory_reset"
    ]

    DESTRUCTIVE_PATTERNS = [
        r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(?:/|\*)",
        r"\bformat\s+[a-zA-Z]:",
        r"\b(dd\s+if=.*of=/dev/[a-z]+)",
        r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"  # Fork bomb
    ]

    def requires_confirmation(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Determines if an action requires explicit human-in-the-loop operator confirmation."""
        return tool_name in self.CRITICAL_CONFIRMATION_TOOLS

    def is_harmful_action(self, text: str) -> Tuple[bool, str]:
        """
        Validates whether an action is genuinely destructive or malicious.
        Returns: (is_harmful, reason)
        """
        for pat in self.DESTRUCTIVE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                logger.warning(f"Destructive safety violation caught: {text}")
                return True, "Action rejected: Catastrophic system destruction pattern detected."

        return False, "Action verified safe: Non-harming constructive execution approved."
