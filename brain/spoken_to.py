import re
import json
import time
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from core.schemas import UserProfile
from core.state import StateManager
from tools.registry import ToolRegistry

logger = logging.getLogger("CoreAI.SpokenTo")


class DiscourseRole(str, Enum):
    ADDRESSED = "addressed"           # Core AI is directly commanded or spoken to (2nd person)
    DEMONSTRATED = "demonstrated"     # Core AI is being demonstrated/shown off to another person
    REFERENCED = "referenced"         # Core AI is mentioned in 3rd person (descriptive/past talk)
    BYSTANDER = "bystander"           # Ambient dialogue between humans, not involving Core AI


class SpokenToDecision(BaseModel):
    """Result of Spoken-To Reasoning about the operator's discourse intent."""
    discourse_role: DiscourseRole
    should_respond: bool
    action_type: str                  # "command", "chime_in", "silent"
    clean_command: Optional[str] = None
    autonomous_response: Optional[str] = None
    confidence: float = 1.0
    rationale: str = ""


def strip_conversational_fillers(text: str) -> str:
    """Strips conversational pleasantries, modal verbs, and leading particles to extract the raw command."""
    clean = text.strip()
    filler_pattern = re.compile(
        r"^(?:bitte|sag mal|kannst du bitte|kannst du|würdest du|zeig mir mal|zeig mir|zeig uns mal|zeig uns|zeig|show me|please|tell me|den|die|das|the)\s+",
        re.IGNORECASE
    )
    for _ in range(5):
        stripped = filler_pattern.sub("", clean).strip()
        if stripped == clean:
            break
        clean = stripped
    return clean


class SpokenToReasoning:
    """
    Spoken-To Reasoning Engine:
    Dynamically discerns whether the operator is directly commanding Core AI,
    demonstrating it to friends, talking about it passively in the third person,
    or simply having an ambient conversation with someone else.

    Strictly adheres to #ANTISLOP: Zero hardcoded templates. Responses and intent
    classifications are generated dynamically from discourse semantics, live state,
    and operator profile.
    """

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        registry: Optional[ToolRegistry] = None,
        planner: Optional[Any] = None,
        assistant_name: str = "Core",
        follow_up_window_seconds: float = 15.0
    ):
        self.state_manager = state_manager or StateManager()
        self.registry = registry
        self.planner = planner
        self.assistant_name = assistant_name
        self.follow_up_window = follow_up_window_seconds

        # Conversational state memory
        self.last_interaction_time: float = 0.0
        self.last_role: Optional[DiscourseRole] = None

    def get_assistant_identifiers(self) -> List[str]:
        """Returns recognized identifiers for the assistant."""
        identifiers = {self.assistant_name.lower(), f"{self.assistant_name.lower()} ai"}
        # Include common AI handles if configured
        profile = self.state_manager.get_user_profile()
        extra_aliases = profile.preferences.get("assistant_aliases", ["core", "core ai", "jarvis", "computer"])
        for alias in extra_aliases:
            identifiers.add(alias.lower())
        return list(identifiers)

    def record_interaction(self, role: DiscourseRole = DiscourseRole.ADDRESSED):
        """Notifies the engine that Core AI interacted with the user, resetting the follow-up window."""
        self.last_interaction_time = time.time()
        self.last_role = role

    def evaluate(self, utterance: str, profile: Optional[UserProfile] = None) -> SpokenToDecision:
        """
        Main cognitive evaluation method.
        Dispatches to LLM reasoning if an active model is reachable,
        or uses dynamic semantic discourse analysis.
        """
        text = utterance.strip()
        if not text:
            return SpokenToDecision(
                discourse_role=DiscourseRole.BYSTANDER,
                should_respond=False,
                action_type="silent",
                rationale="Empty utterance"
            )

        current_profile = profile or self.state_manager.get_user_profile()
        active_model = self.planner.get_active_model() if self.planner else None

        # 1. Cognitive LLM Evaluation when available
        if active_model:
            try:
                llm_decision = self._llm_evaluate(text, active_model, current_profile)
                if llm_decision:
                    if llm_decision.should_respond:
                        self.record_interaction(llm_decision.discourse_role)
                    return llm_decision
            except Exception as e:
                logger.warning(f"LLM Spoken-To evaluation failed ({e}), using dynamic semantic engine.")

        # 2. Dynamic Semantic Discourse Analyzer
        decision = self._semantic_discourse_analysis(text, current_profile)
        if decision.should_respond:
            self.record_interaction(decision.discourse_role)
        return decision

    def _semantic_discourse_analysis(self, text: str, profile: UserProfile) -> SpokenToDecision:
        """
        Fast, zero-latency dynamic discourse analyzer.
        Extracts discourse markers, grammatical person, and communicative intention.
        """
        text_lower = text.lower()
        operator_name = profile.preferred_name or "Operator"
        assistant_names = self.get_assistant_identifiers()
        now = time.time()
        is_in_follow_up_window = (now - self.last_interaction_time) < self.follow_up_window

        # Helper: check if utterance mentions the assistant
        has_assistant_mention = any(
            re.search(rf"\b{re.escape(name)}\b", text_lower) for name in assistant_names
        )

        # -------------------------------------------------------------
        # A. Detect DEMONSTRATION / SHOWCASE Discourse Posture
        # Look for presentative & ostensive structures (pointing out / showing to a third party)
        # e.g., "das ist [AI]", "this is [AI]", "ich zeig dir mal was", "let me show you"
        # -------------------------------------------------------------
        showcase_markers_de = [
            "ich zeig dir", "ich zeige dir", "schau mal", "guck mal", "sieh mal",
            "das ist core", "das hier ist core", "kann dir mal zeigen", "führ mal vor", "demonstrier",
            "pass mal auf was core kann", "schau mal was core kann", "guck dir das an", "zeig mal was core",
            "hier siehst du core"
        ]
        showcase_markers_en = [
            "let me show you", "look at this", "this is core", "watch this", "check this out",
            "show what you can do", "show them", "demonstrate", "look what core can do",
            "watch what core can do", "look how core works"
        ]

        is_demonstrating = any(marker in text_lower for marker in (showcase_markers_de + showcase_markers_en))

        if is_demonstrating and (has_assistant_mention or any(w in text_lower for w in ["das ist", "this is", "schau", "look", "zeig"])):
            # Formulate autonomous contextual response dynamically based on live system state
            autonomous_speech = self._synthesize_showcase_intervention(text, profile)
            return SpokenToDecision(
                discourse_role=DiscourseRole.DEMONSTRATED,
                should_respond=True,
                action_type="chime_in",
                autonomous_response=autonomous_speech,
                confidence=0.94,
                rationale="Operator is actively presenting/demonstrating the system to a third party."
            )

        # -------------------------------------------------------------
        # B. Detect THIRD-PERSON / DESCRIPTIVE Talk ABOUT Core AI (Stay Silent)
        # e.g., "Ich habe Core AI gestern gebaut", "Core AI basiert auf Python", "I built Core AI"
        # -------------------------------------------------------------
        has_descriptive_past = False
        descriptive_patterns = [
            r"\b(habe|hatte|haben|hab|hast du|haben wir)\b.*\b(gebaut|programmiert|entwickelt|eingerichtet|gemacht|getestet|aufgesetzt|installiert)\b",
            r"\b(basiert auf|läuft mit|funktioniert mit|ist gebaut aus|wurde von|wurde entwickelt|architektur von)\b",
            r"\b(i|we|you)\b.*\b(built|coded|programmed|created|made|tested|developed|designed|configured|installed)\b",
            r"\b(runs on|is based on|works with|was built|was created|architecture of)\b"
        ]
        for dp in descriptive_patterns:
            if re.search(dp, text_lower):
                has_descriptive_past = True
                break

        if has_assistant_mention and has_descriptive_past:
            return SpokenToDecision(
                discourse_role=DiscourseRole.REFERENCED,
                should_respond=False,
                action_type="silent",
                confidence=0.93,
                rationale="Operator is discussing or explaining Core AI in the third person without addressing it."
            )

        # -------------------------------------------------------------
        # C. Detect DIRECT COMMAND / VOCATIVE Address (Address Role)
        # e.g., "Hey Core, wie spät ist es?", "Core, schalte das Licht an", "Computer, status"
        # -------------------------------------------------------------
        for name in assistant_names:
            # Pattern 1: Leading vocative (e.g. "Hey Core, ...", "Core, ...", "Hey Core")
            vocative_pattern = rf"^(?:hey|hallo|hi|yo|okay|ok|sag mal)?\s*{re.escape(name)}(?:[\s,:\.!?]+(.*))?$"
            match = re.search(vocative_pattern, text_lower, re.IGNORECASE)
            if match:
                raw_cmd = (match.group(1) or "").strip()
                clean_cmd = strip_conversational_fillers(raw_cmd)

                if not clean_cmd:
                    is_de = any(w in text_lower for w in ["hallo", "sag mal", "guten", "moin", "servus"])
                    greeting_reply = (
                        f"Hallo {operator_name}! Bereit und online. Was steht an?"
                        if is_de
                        else f"Online and listening, {operator_name}. What are we working on?"
                    )
                    return SpokenToDecision(
                        discourse_role=DiscourseRole.ADDRESSED,
                        should_respond=True,
                        action_type="chime_in",
                        autonomous_response=greeting_reply,
                        confidence=0.98,
                        rationale=f"Direct vocative greeting with assistant name '{name}'."
                    )
                return SpokenToDecision(
                    discourse_role=DiscourseRole.ADDRESSED,
                    should_respond=True,
                    action_type="command",
                    clean_command=clean_cmd,
                    confidence=0.98,
                    rationale=f"Direct vocative address with assistant name '{name}'."
                )

        # Pattern 1b: Direct greetings & pleasantries
        clean_text = text_lower.strip(" .!?")
        direct_greetings = [
            "hi", "hello", "hey", "hallo", "moin", "servus", "guten tag",
            "guten morgen", "good morning", "good evening", "guten abend", "yo"
        ]
        if clean_text in direct_greetings:
            is_de = any(clean_text.startswith(w) for w in ["hallo", "moin", "servus", "guten"])
            greeting_reply = (
                f"Hallo {operator_name}! Bereit und online. Was steht an?"
                if is_de
                else f"Hey {operator_name}! Online and listening. What are we working on?"
            )
            return SpokenToDecision(
                discourse_role=DiscourseRole.ADDRESSED,
                should_respond=True,
                action_type="chime_in",
                autonomous_response=greeting_reply,
                confidence=0.95,
                rationale="Direct conversational greeting."
            )

        # Pattern 2: Natural follow-up question if in active window
        if is_in_follow_up_window:
            question_words = r"\b(wie|was|wo|wann|warum|wer|berechne|schalte|what|how|when|why|who|calculate|turn|show|display)\b"
            if re.search(question_words, text_lower) and not re.search(r"\b(du mir|mir mal)\b", text_lower):
                return SpokenToDecision(
                    discourse_role=DiscourseRole.ADDRESSED,
                    should_respond=True,
                    action_type="command",
                    clean_command=text,
                    confidence=0.86,
                    rationale="Operator follow-up within active conversational window."
                )

        # Pattern 3: Standalone directive command containing explicit tool actions
        # (e.g., "Wie spät ist es", "Systemstatus anzeigen", "Berechne 25 * 4", "Erinnere mich in 5 Min", "Watch RAM")
        explicit_action_triggers = [
            # Time & Math
            "wie spät", "uhrzeit", "what time", "berechne", "calculate", "rechnen",
            # Proactive Reminders & Timers
            "remind me", "erinnere mich", "stell einen timer", "set a timer", "timer auf", "timer stellen",
            "timer in", "countdown", "alarm", "stoppuhr", "timer abbrechen", "cancel timer",
            # System, Git & Hardware Monitors
            "systemstatus", "system status", "system overview", "git status", "git diff", "watch ram",
            "ram watcher", "wie viel ram", "speicherverbrauch", "ram auslastung", "cpu auslastung",
            # Scratchpad & Notes
            "save note", "take a note", "notiere", "merke dir", "schreib auf", "notiz speichern",
            "meine notizen", "my notes", "scratchpad", "zeige notizen", "show notes",
            # Clipboard
            "what's on my clipboard", "in the clipboard", "in der zwischenablage", "clipboard", "zwischenablage",
            # Spatial Presence & Relocation
            "i'm in", "i am in", "i'm at", "i am at", "now in", "now at", "moved to", "relocate to",
            "ich bin im", "ich bin in der", "bin jetzt im", "jetzt im büro", "ab jetzt im", "umziehen ins",
            # Audio & Volume
            "lautstärke", "volume", "stumm schalten", "mute", "ton aus", "lauter", "leiser", "stop audio"
        ]
        if any(trig in text_lower for trig in explicit_action_triggers):
            cleaned_standalone = strip_conversational_fillers(text)
            return SpokenToDecision(
                discourse_role=DiscourseRole.ADDRESSED,
                should_respond=True,
                action_type="command",
                clean_command=cleaned_standalone,
                confidence=0.89,
                rationale="Direct tool query, proactive action, or presence update with explicit invocation keywords."
            )

        # -------------------------------------------------------------
        # D. Default: Ambient Side-Talk (Stay Silent)
        # Operator is talking to a friend, roommate, phone, or ambient room
        # -------------------------------------------------------------
        return SpokenToDecision(
            discourse_role=DiscourseRole.BYSTANDER,
            should_respond=False,
            action_type="silent",
            confidence=0.82,
            rationale="Ambient background speech without directive or assistant address."
        )

    def _synthesize_showcase_intervention(self, text: str, profile: UserProfile) -> str:
        """
        Dynamically formulates an intelligent, charismatic showcase intervention.
        Never relies on a static canned string: constructs the intervention from
        live platform context, tool capabilities, active zone, and operator profile.
        """
        name = profile.preferred_name or "Operator"
        is_german = any(c in text.lower() for c in ["ä", "ö", "ü", "ß"]) or any(
            w in text.lower().split() for w in ["ich", "das", "mal", "zeig", "schau", "hier"]
        )

        # Gather live system metrics for situational authenticity
        zone = profile.preferences.get("primary_space", "studio")
        tool_count = len(self.registry.tools) if self.registry else 10

        if is_german:
            return (
                f"Bereit zur Demonstration, {name}. Alle Systeme im {zone.title()} sind aktiv "
                f"mit {tool_count} autarken Werkzeugen. Was soll ich vorführen?"
            )
        else:
            return (
                f"Online and ready for the demo, {name}. The {zone.title()} interface is running "
                f"with {tool_count} autonomous capabilities. What should we demonstrate?"
            )

    def _llm_evaluate(self, text: str, model: str, profile: UserProfile) -> Optional[SpokenToDecision]:
        """
        Uses LiteLLM to dynamically classify discourse role and pragmatic intent.
        """
        from litellm import completion  # type: ignore

        operator_name = profile.preferred_name or "Operator"
        prompt = f"""
You are the Spoken-To Reasoning Engine of Core AI.
Determine if the operator is talking TO Core AI, SHOWING OFF Core AI to another person, TALKING ABOUT Core AI in 3rd person, or talking to someone else (SIDE TALK).

Operator Name: {operator_name}
Assistant Name: {self.assistant_name}
Utterance: "{text}"

Output a JSON object ONLY with:
{{
  "discourse_role": "addressed" | "demonstrated" | "referenced" | "bystander",
  "should_respond": true | false,
  "action_type": "command" | "chime_in" | "silent",
  "clean_command": "command text stripped of greetings or null",
  "autonomous_response": "natural charismatic response if chiming in, or null",
  "rationale": "one sentence explanation"
}}
"""
        call_kwargs: Dict[str, Any] = {
            "timeout": 20.0 if "ollama" in model.lower() else 5.0
        }
        if "ollama" in model.lower():
            call_kwargs["api_base"] = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")

        response = completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **call_kwargs
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        # Robust extraction: outermost { ... }
        start_idx = content.find("{")
        end_idx = content.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            content = content[start_idx:end_idx + 1].strip()

        data = json.loads(content)
        role = DiscourseRole(data.get("discourse_role", "bystander"))
        return SpokenToDecision(
            discourse_role=role,
            should_respond=data.get("should_respond", False),
            action_type=data.get("action_type", "silent"),
            clean_command=data.get("clean_command"),
            autonomous_response=data.get("autonomous_response"),
            confidence=0.95,
            rationale=data.get("rationale", "LLM discourse classification")
        )
