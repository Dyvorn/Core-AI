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
                if plan and (plan.steps or plan.context.get("direct_response")):
                    if not plan.steps:
                        plan.status = "completed"
                    self.pipeline_logger.log_event("PLAN_GENERATED", {
                        "mode": "llm",
                        "model": active_model,
                        "step_count": len(plan.steps),
                        "steps": [s.model_dump() for s in plan.steps],
                        "has_direct_response": bool(plan.context.get("direct_response"))
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
        elif any(k in goal_lower for k in ["wie spät", "spät", "spaet", "uhrzeit", "uhr", "what time", "current time", "time is it", "wie sp"]):
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

        # Pattern: Verbal presence relocation
        # (e.g. "I'm in the office rn", "I'm at the desk", "I am in the kitchen", "moved to studio", "ich bin jetzt im büro")
        elif reloc_match_en := re.search(r"\b(?:i'?m\s+(?:in|at)|i am\s+(?:in|at)|moved to|relocate to|relocated to|now (?:in|at)|currently (?:in|at))\s+(?:the\s+)?([a-zA-Z0-9_\-]+)", goal_lower):
            raw_zone = reloc_match_en.group(1).strip().lower()
            raw_zone = re.sub(r"\b(rn|now|right|room|zimmer)\b", "", raw_zone).strip() or raw_zone
            steps.append(PipelineStep(
                id="relocate_step",
                name=f"Relocate Operator to {raw_zone.title()}",
                tool_name="relocate_operator",
                arguments={"target_zone": raw_zone},
                depends_on=[]
            ))
        elif reloc_match_de := re.search(r"\b(?:ich bin|bin|jetzt|ab jetzt|umgezogen|gewechselt|standort)\s+(?:jetzt\s+)?(?:in\s+der|im|in\s+den|in\s+das|ins)\s+(?:der\s+)?([a-zA-Z0-9äöüß_\-]+)", goal_lower):
            raw_zone = reloc_match_de.group(1).strip().lower()
            raw_zone = re.sub(r"\b(rn|now|right|room|zimmer)\b", "", raw_zone).strip() or raw_zone
            steps.append(PipelineStep(
                id="relocate_step",
                name=f"Relocate Operator to {raw_zone.title()}",
                tool_name="relocate_operator",
                arguments={"target_zone": raw_zone},
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
            context["offline_ai_notice"] = True

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
        Uses LiteLLM to decompose complex tasks into a structured DAG of steps,
        enriched with full contextual awareness of the operator, spatial zones, and device topology.
        """
        from litellm import completion  # type: ignore

        operator_name = "Operator"
        operator_zone = context.get("zone", "studio")
        try:
            profile = self.state_manager.get_user_profile()
            operator_name = profile.preferred_name
        except Exception:
            pass

        zones_summary = []
        try:
            zones = self.state_manager.list_zones()
            zones_summary = [{"id": z.zone_id, "name": z.display_name} for z in zones]
        except Exception:
            pass

        devices_summary = []
        try:
            devs = self.state_manager.list_all_devices()
            devices_summary = [{"id": d.device_id, "type": d.device_type, "zone": d.current_zone, "status": d.status} for d in devs]
        except Exception:
            pass

        system_prompt = f"""You are the Brain and DAG Orchestrator of Core AI, an autonomous sovereign life OS with Jarvis-level situational awareness.
Operator: {operator_name}
Current Spatial Zone: {operator_zone}

Physical & Mesh Topology:
- Registered Zones: {json.dumps(zones_summary)}
- Registered Devices & Edge Nodes: {json.dumps(devices_summary)}

Available Tools Catalog:
{json.dumps(catalog, indent=2)}

Guidelines:
1. Deep Contextual Reasoning:
   - If the user asks about an appliance or device state (e.g. 'what is in my fridge?'), first consider if that device is registered in Core AI. If not, use local network discovery tools ('scan_local_network', 'inspect_lan_device') or home assistant tools to find and inspect it.
2. If solving the goal requires system actions or inspections, output structured DAG 'steps'.
   - Independent steps MUST have empty `depends_on` so they execute in parallel!
   - If a step needs output from an earlier step, use `{{{{steps.earlier_step_id.output.fieldName}}}}` in arguments.
3. If the user asks an open-ended conversational question, knowledge query, or reasoning task that requires NO external tool actions, provide a direct answer in 'direct_response' with an empty 'steps' array.

Output ONLY a JSON object matching this schema:
{{
  "goal": "{goal}",
  "direct_response": null,
  "steps": [
    {{
      "id": "unique_step_id",
      "name": "Human-readable description of step",
      "tool_name": "exact_tool_name_from_catalog",
      "arguments": {{ "param1": "val1" }},
      "depends_on": []
    }}
  ]
}}
Do NOT output any markdown formatting or commentary outside the JSON.
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
        if data.get("direct_response"):
            context["direct_response"] = data["direct_response"]
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

        # Direct response from LLM (general reasoning / questions)
        if plan.context.get("direct_response"):
            return str(plan.context["direct_response"])

        # Offline AI Notice handling (when no model is connected)
        if plan.context.get("offline_ai_notice"):
            if language == "de":
                return (
                    f"Entschuldige bitte {name}, aktuell ist kein KI-Modell (wie Gemini, OpenAI oder lokales Ollama) verbunden oder online, "
                    f"um die Frage '{plan.goal}' auszuwerten. Du kannst jederzeit einen API-Schlüssel konfigurieren "
                    f"(z. B. mit 'api-key set gemini <KEY>') oder eine lokale Ollama-Instanz starten."
                )
            else:
                return (
                    f"Pardon me {name}, but there is currently no AI reasoning model (such as Gemini, OpenAI, or local Ollama) connected or online "
                    f"to analyze '{plan.goal}'. You can connect one anytime with 'api-key set gemini <KEY>' or by running a local Ollama instance."
                )

        # Failure handling
        if plan.status != "completed":
            err = plan.error_summary or "Unbekannter Fehler"
            if language == "de":
                return f"Hey {name}, die Aktion konnte leider nicht vollständig ausgeführt werden: {err}"
            else:
                return f"Hey {name}, the action could not be completed: {err}"

        # Success handling - inspect step outputs
        step_outputs = {s.tool_name: s.output for s in plan.steps if s.status == "completed"}

        # Dynamic LLM Spoken Synthesis: If an active model is available and tools produced outputs,
        # have the neural model synthesize a natural, conversational spoken summary
        active_model = self.get_active_model()
        if active_model and step_outputs:
            try:
                from litellm import completion  # type: ignore
                synth_prompt = (
                    f"You are Core AI, a helpful, conversational OS speaking to {name}. "
                    f"The user asked: '{plan.goal}'. "
                    f"Tool execution results: {json.dumps(step_outputs, default=str)}. "
                    f"Formulate a concise, natural, spoken response (1 to 2 sentences max) in {language}. "
                    f"Provide clear, direct insight based on the tool results. Do not include markdown formatting, bullet points, or JSON."
                )
                resp = completion(
                    model=active_model,
                    messages=[{"role": "system", "content": synth_prompt}],
                    max_tokens=150,
                    timeout=6.0
                )
                spoken_text = resp.choices[0].message.content.strip()
                if spoken_text:
                    return spoken_text
            except Exception as e:
                logger.debug(f"LLM speech synthesis fallback to deterministic formatting: {e}")

        # Deterministic formatting fallbacks

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

        # 4. Network Discovery & Device Inspection
        if "scan_local_network" in step_outputs or "inspect_lan_device" in step_outputs:
            scan_res = step_outputs.get("scan_local_network") or {}
            insp_res = step_outputs.get("inspect_lan_device") or {}
            dev_count = scan_res.get("device_count", 0)
            if insp_res and not insp_res.get("core_installed", False):
                hint = insp_res.get("device_hint", "Gerät")
                host = insp_res.get("host", "LAN")
                if language == "de":
                    return f"Ich habe ein {hint} auf {host} im Netzwerk gefunden, allerdings ist dort noch kein Core AI Knoten installiert."
                else:
                    return f"I found a {hint} at {host} on your local network, but the Core AI edge node is not installed on it yet."
            if language == "de":
                return f"Der Netzwerkscan wurde abgeschlossen. Es wurden {dev_count} aktive Geräte im lokalen Netz gefunden, {name}."
            else:
                return f"Network scan completed. Found {dev_count} active devices on your local network, {name}."

        # 5. Home Assistant service call
        if "home_assistant_call" in step_outputs:
            if language == "de":
                return f"Befehl ausgeführt, {name}. Das Smart-Home-Gerät wurde aktualisiert."
            else:
                return f"Smart home action completed, {name}."

        # 6. File / Dir operations
        if "list_dir_contents" in step_outputs:
            contents = step_outputs["list_dir_contents"]
            count = len(contents) if isinstance(contents, list) else "mehrere"
            if language == "de":
                return f"Ich habe das Verzeichnis geprüft. Es enthält {count} Einträge, {name}."
            else:
                return f"Directory contains {count} items, {name}."

        # 7. Relocate Operator / Spatial Handoff
        if "relocate_operator" in step_outputs:
            reloc_info = step_outputs["relocate_operator"]
            target_name = (reloc_info.get("display_name") or reloc_info.get("zone", "room")).title() if isinstance(reloc_info, dict) else "room"
            if language == "de":
                return f"Alles klar {name}, Standort auf {target_name} aktualisiert. Audio und Anzeigen wurden umgestellt."
            else:
                return f"Understood {name}. Updated your location to the {target_name}. Audio and display context re-routed."

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
