import os
import asyncio
import pytest
from tools.registry import ToolRegistry
from core.state import StateManager
from core.schemas import PipelinePlan, PipelineStep
from brain.pipeline_engine import PipelineEngine
from tools.native.system_tools import get_time, time_schema
from tools.native.math_tools import calculate_math, calculate_math_schema

@pytest.mark.anyio
async def test_concurrent_pipeline_execution(tmp_path):
    state_file = os.path.join(tmp_path, "test_engine.db")
    state = StateManager(db_path=state_file)
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("calculate_math", calculate_math, calculate_math_schema)

    engine = PipelineEngine(registry=registry, state_manager=state)

    # 2 independent steps should execute in parallel, followed by dependent step 3
    plan = PipelinePlan(
        goal="Calculate and check time",
        steps=[
            PipelineStep(
                id="step_calc",
                name="Math Calculation",
                tool_name="calculate_math",
                arguments={"expression": "100 * 5"},
                depends_on=[]
            ),
            PipelineStep(
                id="step_time",
                name="Fetch Time",
                tool_name="get_time",
                arguments={},
                depends_on=[]
            ),
            PipelineStep(
                id="step_calc2",
                name="Dependent Calculation",
                tool_name="calculate_math",
                arguments={"expression": "{{steps.step_calc.output.result}} + 50"},
                depends_on=["step_calc"]
            )
        ]
    )

    result_plan = await engine.execute_pipeline(plan)
    assert result_plan.status == "completed"
    assert len(result_plan.steps) == 3
    assert result_plan.steps[0].output["result"] == 500
    assert result_plan.steps[2].output["result"] == 550

@pytest.mark.anyio
async def test_pipeline_failure_and_diagnosis(tmp_path):
    state_file = os.path.join(tmp_path, "test_fail.db")
    state = StateManager(db_path=state_file)
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    engine = PipelineEngine(registry=registry, state_manager=state)

    # Pipeline with nonexistent tool
    plan = PipelinePlan(
        goal="Run bad tool",
        steps=[
            PipelineStep(
                id="bad_step",
                name="Call Missing Tool",
                tool_name="unknown_tool_xyz",
                arguments={},
                max_retries=1
            )
        ]
    )

    result_plan = await engine.execute_pipeline(plan)
    assert result_plan.status == "failed"
    assert "unknown_tool_xyz" in result_plan.error_summary
