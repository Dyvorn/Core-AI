import logging
import json
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple

from core.schemas import PipelinePlan, PipelineStep, FailureDiagnosis
from core.state import StateManager
from core.logging_setup import get_pipeline_logger
from tools.registry import ToolRegistry
from brain.dynamic_generator import DynamicGenerator

logger = logging.getLogger(__name__)

class Planner:
    """
    Intelligent Autonomous Problem Solver and Pipeline Architect:
    - Inspects available tools (introspection)
    - Verifies LLM model availability with transparent fallbacks
    - Decomposes problems into executable DAG pipelines
    - Detects capability gaps and builds new tools dynamically
    - Possesses failure awareness and re-plans upon error
    """
    
    def __init__(
        self,
        registry: ToolRegistry,
        model_name: str = "ollama/qwen3.5:2b",
        fallback_model: str = "gemini/gemini-2.5-flash",
        state_manager: Optional[StateManager] = None,
        dynamic_generator: Optional[DynamicGenerator] = None,
        model_router: Optional[Any] = None
    ):
        self.registry = registry
        self.state_manager = state_manager or StateManager()
        from brain.model_router import ModelRouter
        self.model_router = model_router or ModelRouter(state_manager=self.state_manager)
        self.model_name = model_name
        self.fallback_model = fallback_model
        self.dynamic_generator = dynamic_generator or DynamicGenerator(registry=self.registry, state_manager=self.state_manager)
        self.pipeline_logger = get_pipeline_logger()
        self._model_status_cache: Dict[str, bool] = {}

    def check_model_availability(self, model: str) -> bool:
        """
        Verifies if the model's provider and service are actually available.
        Delegates to ModelRouter for fast pre-checks and cached responses.
        """
        return self.model_router.check_model_availability(model)

    def get_active_model(self, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Returns the primary model if online, then fallback model, or None if fully offline."""
        _, resolved = self.model_router.resolve_model(goal="", context=context, role="planner")
        return resolved

    def plan_problem(self, goal: str, context: Optional[Dict[str, Any]] = None) -> PipelinePlan:
        """
        Main entrypoint: analyzes problem against available tools, identifies missing capabilities,
        synthesizes dynamic tools if necessary, and produces an executable PipelinePlan DAG.
        """
        clean_goal, active_model = self.model_router.resolve_model(goal, context=context, role="planner")
        target_goal = clean_goal or goal

        logger.info(f"Planning solution for goal: '{target_goal}' (model: '{active_model or 'heuristic'}')")
        self.pipeline_logger.log_event("PLANNING_STARTED", {
            "goal": target_goal,
            "resolved_model": active_model,
            "available_tools": list(self.registry.tools.keys())
        })

        catalog = self.registry.get_tool_catalog()

        # 1. First, check if goal requires a missing capability and needs dynamic tool creation
        self._ensure_capabilities_for_goal(target_goal, catalog)

        # Re-fetch catalog in case dynamic tools were just added
        catalog = self.registry.get_tool_catalog()

        # 2. Decompose into PipelinePlan using LLM or Heuristic Engine
        if active_model:
            try:
                plan = self._llm_generate_plan(target_goal, catalog, active_model, context or {})
                if plan and plan.steps:
                    self.pipeline_logger.log_event("PLAN_GENERATED", {
                        "mode": "llm",
                        "model": active_model,
                        "step_count": len(plan.steps),
                        "steps": [s.model_dump() for s in plan.steps]
                    }, pipeline_id=plan.id)
                    return plan
            except Exception as e:
                logger.warning(f"LLM planning failed ({e}). Falling back to heuristic planning engine.")

        plan = self._heuristic_generate_plan(target_goal, catalog, context or {})
        if not plan.steps:
            plan.status = "completed"
        self.pipeline_logger.log_event("PLAN_GENERATED", {
            "mode": "heuristic_fallback",
            "step_count": len(plan.steps),
            "steps": [s.model_dump() for s in plan.steps]
        }, pipeline_id=plan.id)
        return plan

    def _ensure_capabilities_for_goal(self, goal: str, catalog: List[Dict[str, Any]]):
        """
        Identifies whether a tool is missing for the given goal and synthesizes it on the fly.
        """
        goal_lower = goal.lower()
        
        # Check for hashing requirement
        if ("hash" in goal_lower or "sha256" in goal_lower or "md5" in goal_lower) and not self.registry.has_tool("hash_string"):
            logger.info("Missing capability detected: 'hash_string'. Initiating dynamic tool synthesis.")
            self.dynamic_generator.synthesize_tool(
                tool_name="hash_string",
                description="Computes cryptographic hash (sha256, md5, sha1) of a given text",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "String to hash"},
                        "algorithm": {"type": "string", "description": "Hash algorithm (sha256, md5, sha1)", "default": "sha256"}
                    },
                    "required": ["text"]
                },
                sample_args={"text": "test_input", "algorithm": "sha256"}
            )

        # Check for word count / text statistics requirement
        if ("word count" in goal_lower or "count words" in goal_lower) and not self.registry.has_tool("count_words"):
            logger.info("Missing capability detected: 'count_words'. Initiating dynamic tool synthesis.")
            self.dynamic_generator.synthesize_tool(
                tool_name="count_words",
                description="Counts words and characters in a given text string",
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "The text to analyze"}
                    },
                    "required": ["text"]
                },
                sample_args={"text": "hello world test"}
            )

    def _heuristic_generate_plan(self, goal: str, catalog: List[Dict[str, Any]], context: Dict[str, Any]) -> PipelinePlan:
        """
        Robust heuristic planner that constructs valid execution pipelines with concurrency.
        Specially optimized for natural spoken voice commands and system operations.
        """
        goal_lower = goal.lower()
        pipeline_id = str(uuid.uuid4())
        steps: List[PipelineStep] = []

        # Pattern: System diagnostics (Parallel execution of time + system status)
        if any(k in goal_lower for k in ["status", "system", "overview", "diagnos", "gesundheit", "wie geht"]):
            steps.append(PipelineStep(
                id="get_time_step",
                name="Fetch Current Time",
                tool_name="get_time",
                arguments={},
                depends_on=[]
            ))
            steps.append(PipelineStep(
                id="get_status_step",
                name="Fetch System Status",
                tool_name="get_system_status",
                arguments={},
                depends_on=[]
            ))

        # Pattern: Pure Time query ("wie spät ist es", "what time is it")
        elif any(k in goal_lower for k in ["wie spät", "uhrzeit", "what time", "current time", "time is it"]):
            steps.append(PipelineStep(
                id="get_time_step",
                name="Fetch Current Time",
                tool_name="get_time",
                arguments={},
                depends_on=[]
            ))

        # Pattern: Math computation ("was ist 25 * 4", "berechne 12 + 8")
        elif any(char in goal for char in ["+", "*", "/", "sqrt", "math", "calculate"]) or any(k in goal_lower for k in ["berechne", "calculate", "wie viel ist", "was ist"]):
            # Extract possible math expression
            expr_match = re.search(r"([0-9\.\s\+\-\*\/\(\)\^]|sqrt|pow|sin|cos)+", goal)
            expr = expr_match.group(0).strip() if expr_match else "1 + 1"
            expr = expr.strip("?!. ")
            steps.append(PipelineStep(
                id="calc_step",
                name="Calculate Math Expression",
                tool_name="calculate_math",
                arguments={"expression": expr},
                depends_on=[]
            ))

        # Pattern: Directory / File listing
        elif any(k in goal_lower for k in ["dateien", "files", "list dir", "list files", "zeige ordner"]):
            steps.append(PipelineStep(
                id="list_dir_step",
                name="List Workspace Contents",
                tool_name="list_dir_contents",
                arguments={"path": "."},
                depends_on=[]
            ))

        # Pattern: Hashing
        elif "hash" in goal_lower or "sha256" in goal_lower or "md5" in goal_lower:
            target_str = goal.split("hash")[-1].strip(" '\"") or "default_text"
            steps.append(PipelineStep(
                id="hash_step",
                name="Generate Hash",
                tool_name="hash_string",
                arguments={"text": target_str, "algorithm": "sha256"},
                depends_on=[]
            ))

        # Pattern: Home assistant device control
        elif any(k in goal_lower for k in ["turn on", "turn off", "schalte", "licht", "light", "lampe"]):
            entity = "light.living_room"
            action = "turn_on" if any(k in goal_lower for k in ["on", "an", "ein"]) else "turn_off"
            steps.append(PipelineStep(
                id="ha_action_step",
                name="Home Assistant Service Call",
                tool_name="home_assistant_call",
                arguments={"entity_id": entity, "action": action},
                depends_on=[]
            ))

        # Pattern: File read / write
        elif "write file" in goal_lower or "save to" in goal_lower or "speichere" in goal_lower:
            steps.append(PipelineStep(
                id="write_step",
                name="Write File Content",
                tool_name="write_text_file",
                arguments={"file_path": "output.txt", "content": goal},
                depends_on=[]
            ))

        # Pattern: Conversational greetings / dialogue
        elif any(goal_lower == g or goal_lower.startswith(f"{g} ") for g in [
            "hi", "hello", "hey", "hallo", "moin", "servus", "guten tag", "guten morgen", "good morning", "yo"
        ]):
            # Conversational greetings require no tool steps
            pass

        # Generic default: do not fabricate unrelated tool steps for unrecognized goals
        else:
            pass

        return PipelinePlan(
            id=pipeline_id,
            goal=goal,
            steps=steps,
            context=context
        )

    def _llm_generate_plan(
        self,
        goal: str,
        catalog: List[Dict[str, Any]],
        model: str,
        context: Dict[str, Any]
    ) -> PipelinePlan:
        """
        Uses LiteLLM to decompose complex tasks into a structured DAG of steps.
        """
        from litellm import completion  # type: ignore
        
        system_prompt = f"""
You are the Brain of Core AI, an autonomous system solver.
Your job is to inspect available tools and generate a structured multi-step execution pipeline (DAG) to solve the user's problem.

Available Tools Catalog:
{json.dumps(catalog, indent=2)}

Output ONLY a JSON object matching this schema:
{{
  "goal": "{goal}",
  "steps": [
    {{
      "id": "unique_step_id",
      "name": "Human-readable description of step",
      "tool_name": "exact_tool_name_from_catalog",
      "arguments": {{ "param1": "val1" }},
      "depends_on": [] // IDs of steps that MUST finish before this step runs. Independent steps have empty depends_on!
    }}
  ]
}}

Guidelines:
- Independent steps MUST have empty `depends_on` so they run in parallel!
- If a step needs output from an earlier step, use `{{{{steps.earlier_step_id.output.fieldName}}}}` in arguments.
- Do NOT output any markdown formatting, preamble, or conversational comments. Output only valid JSON.
"""
        response = completion(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": goal}
            ],
            timeout=15.0
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        data = json.loads(content)
        steps = [PipelineStep(**s) for s in data.get("steps", [])]
        return PipelinePlan(
            goal=goal,
            steps=steps,
            context=context
        )

    def replan_on_failure(
        self,
        plan: PipelinePlan,
        failed_step_id: str,
        error_message: str
    ) -> PipelinePlan:
        """
        When a step fails, analyzes the failure and yields updated steps or alternative tools.
        """
        logger.warning(f"[Jarvis Awareness] Re-planning triggered for pipeline '{plan.id}' due to failure in '{failed_step_id}': {error_message}")
        self.pipeline_logger.log_event("REPLANNING_TRIGGERED", {
            "failed_step_id": failed_step_id,
            "error_message": error_message
        }, pipeline_id=plan.id, step_id=failed_step_id)

        # Mark subsequent dependent steps as pending retry or adjust args
        for step in plan.steps:
            if step.id == failed_step_id:
                step.retry_count += 1
                step.status = "pending"
                step.error = None

        return plan

    def formulate_spoken_response(
        self,
        plan: PipelinePlan,
        profile: Optional[Any] = None,
        language: Optional[str] = None
    ) -> str:
        """
        Formulates a natural, conversational spoken sentence from a finished PipelinePlan.
        Translates raw tool outputs and status codes into clear human speech.
        """
        name = profile.preferred_name if profile and hasattr(profile, "preferred_name") else "Operator"
        
        # Determine language
        goal_text = plan.goal.lower()
        if not language:
            is_german = any(c in goal_text for c in ["ä", "ö", "ü", "ß"]) or any(
                w in goal_text.split() for w in ["wie", "was", "ist", "uhrzeit", "spät", "system", "status", "hallo", "schalte", "licht", "berechne"]
            )
            language = "de" if is_german else "en"

        # Conversational greetings & pleasantries
        clean_goal = goal_text.strip(" .!?")
        greetings = ["hi", "hello", "hey", "hallo", "moin", "servus", "guten tag", "guten morgen", "good morning", "good evening", "guten abend", "yo"]
        if clean_goal in greetings or any(clean_goal.startswith(f"{g} ") for g in greetings) or any(clean_goal == f"hey {a}" for a in ["core", "core ai", "assistant"]):
            if language == "de":
                return f"Hallo {name}! Bereit und online. Was steht an?"
            else:
                return f"Hey {name}! Online and ready. What are we working on?"

        # Failure handling
        if plan.status != "completed":
            err = plan.error_summary or "Unbekannter Fehler"
            if language == "de":
                return f"Hey {name}, die Aktion konnte leider nicht vollständig ausgeführt werden: {err}"
            else:
                return f"Hey {name}, the action could not be completed: {err}"

        # Success handling - inspect step outputs
        step_outputs = {s.tool_name: s.output for s in plan.steps if s.status == "completed"}

        # 1. Time response
        if "get_time" in step_outputs and "get_system_status" not in step_outputs:
            time_val = step_outputs["get_time"]
            if language == "de":
                return f"Es ist {time_val} Uhr, {name}."
            else:
                return f"It is {time_val}, {name}."

        # 2. System Status & Diagnostics
        if "get_system_status" in step_outputs:
            sys_info = step_outputs["get_system_status"]
            os_name = sys_info.get("os", "System")
            arch = sys_info.get("architecture", "")
            py_ver = sys_info.get("python_version", "")
            time_val = step_outputs.get("get_time", "")
            time_str = f" um {time_val} Uhr" if time_val else ""
            if language == "de":
                return f"Das System läuft stabil auf {os_name} ({arch}) mit Python {py_ver}{time_str}, {name}."
            else:
                return f"Core AI is operational on {os_name} {arch} running Python {py_ver}, {name}."

        # 3. Math calculation
        if "calculate_math" in step_outputs:
            res_info = step_outputs["calculate_math"]
            if isinstance(res_info, dict) and res_info.get("status") == "success":
                expr = res_info.get("expression", "")
                result = res_info.get("result")
                if language == "de":
                    return f"Das Ergebnis von {expr} ist {result}, {name}."
                else:
                    return f"The result of {expr} is {result}, {name}."

        # 4. Home Assistant service call
        if "home_assistant_call" in step_outputs:
            if language == "de":
                return f"Befehl ausgeführt, {name}. Das Smart-Home-Gerät wurde aktualisiert."
            else:
                return f"Smart home action completed, {name}."

        # 5. File / Dir operations
        if "list_dir_contents" in step_outputs:
            contents = step_outputs["list_dir_contents"]
            count = len(contents) if isinstance(contents, list) else "mehrere"
            if language == "de":
                return f"Ich habe das Verzeichnis geprüft. Es enthält {count} Einträge, {name}."
            else:
                return f"Directory contains {count} items, {name}."

        # Fallback if no specific step outputs were generated (unregistered tool capability)
        if not step_outputs:
            if language == "de":
                return f"Ich habe die Absicht verstanden, {name}, aber aktuell ist dafür noch kein passendes Werkzeug registriert."
            else:
                return f"I hear you, {name}, but there is no specific tool registered for '{plan.goal}' yet."

        # Generic default success
        final_val = plan.final_output
        if isinstance(final_val, dict):
            final_str = json.dumps(final_val)
        else:
            final_str = str(final_val) if final_val is not None else "erfolgreich"

        if language == "de":
            return f"Hey {name}, Aktion abgeschlossen: {final_str}"
        else:
            return f"Hey {name}, action completed: {final_str}"
