import pytest
from brain.safety import SafetyGate
from brain.planner import Planner
from tools.registry import ToolRegistry

def test_safety_gate_catastrophic_rejection():
    gate = SafetyGate()
    
    # Destructive commands rejected
    is_harmful, reason = gate.is_harmful_action("rm -rf /")
    assert is_harmful is True
    assert "Catastrophic" in reason

    is_harmful_win, _ = gate.is_harmful_action("format c:")
    assert is_harmful_win is True

    # Constructive everyday commands approved
    is_harmful_safe, _ = gate.is_harmful_action("whats the temp in Halle (Saale)")
    assert is_harmful_safe is False

    is_harmful_calc, _ = gate.is_harmful_action("calculate 42 * 100")
    assert is_harmful_calc is False

def test_planner_safety_gate_integration(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    gate = SafetyGate()
    planner = Planner(registry=registry, safety_gate=gate)

    plan = planner.plan_problem("rm -rf /")
    assert plan.status == "failed"
    assert "Catastrophic" in plan.error_summary
    assert len(plan.steps) == 0
