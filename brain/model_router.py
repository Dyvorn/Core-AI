import os
import re
import logging
from typing import Dict, Any, Optional, Tuple, List
from core.state import StateManager

logger = logging.getLogger(__name__)

class ModelRouter:
    """
    Dynamic Model & AI Provider Customization Engine:
    - Zero hardcoded models: operator chooses their preferred models & providers.
    - Persistent memory of preferences in SQLite (user_profiles.preferences['models']).
    - Per-task / domain routing (e.g. complex DAG planning vs. fast local execution).
    - Natural language runtime overrides (e.g. 'using ollama/llama3' or 'with gemini/gemini-2.5-flash').
    - Fast health & availability checking with automatic offline fallback.
    - Dynamic API key management.
    """

    DEFAULT_ROLES = {
        "planner": "ollama/qwen3.5:2b",
        "fallback": "gemini/gemini-2.5-flash",
        "deep_reasoning": "gemini/gemini-2.5-pro",
        "fast_local": "ollama/qwen3.5:2b"
    }

    def __init__(self, state_manager: Optional[StateManager] = None):
        self.state_manager = state_manager or StateManager()
        self._status_cache: Dict[str, bool] = {}

    def get_model_preferences(self) -> Dict[str, Any]:
        """Retrieves operator model preferences from SQLite with safe defaults."""
        try:
            profile = self.state_manager.get_user_profile()
            prefs = profile.preferences.get("models", {})
            return {**self.DEFAULT_ROLES, **prefs}
        except Exception as e:
            logger.warning(f"Could not load model preferences from state: {e}")
            return dict(self.DEFAULT_ROLES)

    def set_model_preference(self, role: str, model_name: str) -> Dict[str, Any]:
        """Saves a model assignment for a given role (e.g. 'planner', 'fallback', 'deep_reasoning')."""
        profile = self.state_manager.get_user_profile()
        if "models" not in profile.preferences:
            profile.preferences["models"] = {}
        profile.preferences["models"][role] = model_name.strip()
        self.state_manager.save_user_profile(profile)
        logger.info(f"Updated model preference for role '{role}' -> '{model_name}'")
        return profile.preferences["models"]

    def set_api_key(self, provider: str, api_key: str, persist_to_env: bool = True) -> str:
        """Sets an API key for a provider in memory and optionally appends/updates config/.env."""
        provider_clean = provider.strip().upper()
        env_var = f"{provider_clean}_API_KEY"
        if provider_clean == "GEMINI":
            env_var = "GEMINI_API_KEY"
        elif provider_clean == "GOOGLE":
            env_var = "GOOGLE_API_KEY"
        elif provider_clean == "OPENAI":
            env_var = "OPENAI_API_KEY"
        elif provider_clean == "ANTHROPIC":
            env_var = "ANTHROPIC_API_KEY"

        os.environ[env_var] = api_key.strip()
        # Invalidate status cache
        self._status_cache.clear()

        if persist_to_env:
            self._update_env_file(env_var, api_key.strip())

        logger.info(f"Configured API key for provider '{provider_clean}' (saved to {env_var})")
        return env_var

    def _update_env_file(self, env_var: str, value: str):
        """Updates or appends a key in config/.env or .env."""
        target_path = "config/.env" if os.path.exists("config") else ".env"
        lines: List[str] = []
        found = False

        if os.path.exists(target_path):
            with open(target_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{env_var}="):
                new_lines.append(f"{env_var}={value}\n")
                found = True
            else:
                new_lines.append(line)

        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{env_var}={value}\n")

        with open(target_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    def extract_model_override(self, goal: str) -> Tuple[str, Optional[str]]:
        """
        Detects if the user specified a specific model in their prompt.
        Examples:
          'solve compute sha256 with ollama/llama3' -> ('solve compute sha256', 'ollama/llama3')
          'plan trip using gemini/gemini-2.5-flash' -> ('plan trip', 'gemini/gemini-2.5-flash')
          'calculate math with model ollama/qwen3.5:2b' -> ('calculate math', 'ollama/qwen3.5:2b')
        """
        pattern = r'\b(?:with|using|on)\s+(?:model\s+)?([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.:]+)\b'
        match = re.search(pattern, goal, re.IGNORECASE)
        if match:
            model_override = match.group(1).strip()
            # Clean goal by removing the model phrase
            clean_goal = re.sub(pattern, "", goal, flags=re.IGNORECASE).strip()
            # Clean any trailing punctuation or extra spaces
            clean_goal = re.sub(r'\s+', ' ', clean_goal).strip()
            return clean_goal, model_override

        return goal, None

    def check_model_availability(self, model: str) -> bool:
        """Verifies if the model's provider and endpoint are reachable."""
        if model in self._status_cache:
            return self._status_cache[model]

        model_lower = model.lower()

        # Fast pre-check for Ollama
        if "ollama" in model_lower:
            try:
                import urllib.request
                api_base = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
                with urllib.request.urlopen(f"{api_base}/api/tags", timeout=0.3) as resp:
                    available = resp.status == 200
                    self._status_cache[model] = available
                    return available
            except Exception:
                self._status_cache[model] = False
                return False

        # Fast pre-check for Gemini
        elif "gemini" in model_lower:
            has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
            self._status_cache[model] = has_key
            return has_key

        # Fast pre-check for OpenAI
        elif "openai" in model_lower or "gpt" in model_lower:
            has_key = bool(os.getenv("OPENAI_API_KEY"))
            self._status_cache[model] = has_key
            return has_key

        # Fast pre-check for Anthropic
        elif "anthropic" in model_lower or "claude" in model_lower:
            has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
            self._status_cache[model] = has_key
            return has_key

        # Generic / Unknown model: check via litellm if installed
        try:
            from litellm import completion
            response = completion(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=2,
                timeout=2.0
            )
            available = bool(response and response.choices)
            self._status_cache[model] = available
            return available
        except Exception:
            self._status_cache[model] = False
            return False

    def resolve_model(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        role: str = "planner"
    ) -> Tuple[str, Optional[str]]:
        """
        Resolves the exact model to use for a given goal and context.
        Order of precedence:
          1. Context override ('model' in context)
          2. Natural language override in goal ('with ollama/llama3')
          3. Operator preference for the requested role ('planner', 'deep_reasoning')
          4. Configured fallback model
          5. None (falls back to local heuristic DAG decomposition)
        Returns: (clean_goal, resolved_model_name)
        """
        ctx = context or {}

        # 1. Context explicit override
        if ctx.get("model"):
            candidate = ctx["model"]
            if self.check_model_availability(candidate):
                return goal, candidate
            logger.warning(f"Context model override '{candidate}' unavailable. Evaluating next option.")

        # 2. Natural language prompt override
        clean_goal, prompt_override = self.extract_model_override(goal)
        if prompt_override:
            if self.check_model_availability(prompt_override):
                logger.info(f"Using runtime model override from prompt: '{prompt_override}'")
                return clean_goal, prompt_override
            else:
                logger.warning(f"Runtime model override '{prompt_override}' from prompt is offline. Falling back to defaults.")

        # 3. User preference for specified role
        prefs = self.get_model_preferences()
        preferred_model = prefs.get(role, self.DEFAULT_ROLES.get(role))
        if preferred_model and self.check_model_availability(preferred_model):
            return clean_goal, preferred_model

        # 4. Fallback model
        fallback_model = prefs.get("fallback", self.DEFAULT_ROLES.get("fallback"))
        if fallback_model and self.check_model_availability(fallback_model):
            return clean_goal, fallback_model

        # 5. Offline heuristic
        return clean_goal, None

    def get_status_summary(self) -> Dict[str, Any]:
        """Provides a complete summary of configured providers, active models, and connectivity."""
        prefs = self.get_model_preferences()
        providers = {
            "gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "ollama_local": self.check_model_availability("ollama/test")
        }

        active_roles = {}
        for role, model in prefs.items():
            active_roles[role] = {
                "model": model,
                "online": self.check_model_availability(model)
            }

        return {
            "configured_providers": providers,
            "roles": active_roles,
            "offline_heuristic_available": True
        }
