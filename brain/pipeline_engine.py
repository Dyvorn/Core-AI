import asyncio
import re
import json
import logging
import time
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from core.schemas import PipelinePlan, PipelineStep, StepResult, FailureDiagnosis
from core.state import StateManager
from core.bus import EventBus
from core.logging_setup import get_pipeline_logger
from tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

class PipelineExecutionError(Exception):
    """Raised when pipeline cannot proceed or unrecoverable error occurs."""
    pass


class PipelineEngine:
    """
    Executes multi-step problem solving pipelines with:
    - Parallel execution of independent steps ('multiple things at once')
    - Dynamic variable resolution between steps (e.g. {{steps.step_1.output.result}})
    - Failure awareness, error diagnosis, and self-healing retries
    - Full persistence to SQLite and structured JSONL audit logs
    """

    def __init__(
        self,
        registry: ToolRegistry,
        state_manager: Optional[StateManager] = None,
        bus: Optional[EventBus] = None,
        max_workers: int = 4
    ):
        self.registry = registry
        self.state_manager = state_manager or StateManager()
        self.bus = bus
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.pipeline_logger = get_pipeline_logger()

    async def execute_pipeline(self, plan: PipelinePlan) -> PipelinePlan:
        """
        Executes a pipeline plan asynchronously until completion or fatal failure.
        Runs independent steps concurrently.
        """
        plan.status = "running"
        self.state_manager.save_pipeline(plan)
        
        start_time = time.perf_counter()
        logger.info(f"Starting pipeline '{plan.id[:8]}': '{plan.goal}' with {len(plan.steps)} steps.")
        self.pipeline_logger.log_event("PIPELINE_STARTED", {
            "goal": plan.goal,
            "step_count": len(plan.steps),
            "step_ids": [s.id for s in plan.steps]
        }, pipeline_id=plan.id)

        step_map: Dict[str, PipelineStep] = {step.id: step for step in plan.steps}
        completed_step_ids: Set[str] = set()
        failed_step_ids: Set[str] = set()

        while len(completed_step_ids) + len(failed_step_ids) < len(plan.steps):
            # 1. Identify ready steps (all dependencies completed, status pending)
            ready_steps: List[PipelineStep] = []
            for step in plan.steps:
                if step.status == "pending":
                    # Check if all dependencies are satisfied
                    deps_satisfied = all(dep in completed_step_ids for dep in step.depends_on)
                    deps_failed = any(dep in failed_step_ids for dep in step.depends_on)
                    
                    if deps_failed:
                        # Dependency failed, skip this step
                        step.status = "skipped"
                        step.error = f"Skipped because dependency in {step.depends_on} failed."
                        self.state_manager.save_step(plan.id, step)
                        failed_step_ids.add(step.id)
                        logger.warning(f"Step '{step.id}' skipped due to failed dependency.")
                    elif deps_satisfied:
                        ready_steps.append(step)

            if not ready_steps:
                # No steps ready and not all completed -> deadlock or all remaining skipped
                if len(completed_step_ids) + len(failed_step_ids) < len(plan.steps):
                    for step in plan.steps:
                        if step.status == "pending":
                            step.status = "skipped"
                            step.error = "Unresolvable dependency or deadlock."
                            failed_step_ids.add(step.id)
                            self.state_manager.save_step(plan.id, step)
                break

            # 2. Execute ready steps concurrently ("multiple things at once")
            logger.info(f"Executing batch of {len(ready_steps)} concurrent steps: {[s.id for s in ready_steps]}")
            self.pipeline_logger.log_event("CONCURRENT_BATCH_STARTED", {
                "batch_step_ids": [s.id for s in ready_steps]
            }, pipeline_id=plan.id)

            tasks = [self._execute_single_step(plan.id, step, step_map) for step in ready_steps]
            results: List[StepResult] = await asyncio.gather(*tasks)

            # 3. Process results & update statuses
            for step, res in zip(ready_steps, results):
                if res.success:
                    completed_step_ids.add(step.id)
                else:
                    failed_step_ids.add(step.id)

        # 4. Finalize Pipeline
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        has_failures = len(failed_step_ids) > 0
        plan.status = "completed" if not has_failures else "failed"
        plan.completed_at = datetime.now(timezone.utc)

        # Collect final output (from last completed step or combined outputs)
        if not has_failures and plan.steps:
            last_step = plan.steps[-1]
            plan.final_output = last_step.output
        elif has_failures:
            failed_errors = [f"{s.id}: {s.error}" for s in plan.steps if s.status in ("failed", "skipped")]
            plan.error_summary = "; ".join(failed_errors)

        self.state_manager.update_pipeline_status(
            pipeline_id=plan.id,
            status=plan.status,
            final_output=plan.final_output,
            error_summary=plan.error_summary
        )

        self.pipeline_logger.log_event("PIPELINE_FINISHED", {
            "status": plan.status,
            "duration_ms": total_duration_ms,
            "final_output": plan.final_output,
            "error_summary": plan.error_summary
        }, pipeline_id=plan.id)

        logger.info(f"Pipeline '{plan.id[:8]}' finished with status '{plan.status}' in {total_duration_ms:.2f}ms")
        return plan

    async def _execute_single_step(
        self,
        pipeline_id: str,
        step: PipelineStep,
        step_map: Dict[str, PipelineStep]
    ) -> StepResult:
        """
        Resolves arguments from prior steps, executes the tool,
        handles retries and failure diagnosis.
        """
        step.status = "running"
        step.started_at = datetime.now(timezone.utc)
        self.state_manager.save_step(pipeline_id, step)

        self.pipeline_logger.log_event("STEP_STARTED", {
            "step_id": step.id,
            "tool_name": step.tool_name,
            "raw_args": step.arguments
        }, pipeline_id=pipeline_id, step_id=step.id)

        # 1. Resolve variable interpolation in arguments from earlier step outputs
        resolved_args = self._resolve_arguments(step.arguments, step_map)

        # 2. Execute with retry loop
        current_attempt = 0
        step_result: Optional[StepResult] = None

        while current_attempt <= step.max_retries:
            start_t = time.perf_counter()
            loop = asyncio.get_running_loop()

            # Execute tool in thread pool to prevent blocking the async loop
            step_result = await loop.run_in_executor(
                self.executor,
                self.registry.execute_tool,
                step.tool_name,
                resolved_args
            )

            if step_result.success:
                step.status = "completed"
                step.output = step_result.output
                step.duration_ms = step_result.duration_ms
                step.completed_at = datetime.now(timezone.utc)
                self.state_manager.save_step(pipeline_id, step)

                self.pipeline_logger.log_event("STEP_COMPLETED", {
                    "step_id": step.id,
                    "tool_name": step.tool_name,
                    "output": step.output,
                    "duration_ms": step.duration_ms
                }, pipeline_id=pipeline_id, step_id=step.id)
                return step_result

            # Failure occurred: analyze failure ("Jarvis-like awareness")
            current_attempt += 1
            step.retry_count = current_attempt
            diagnosis = self._diagnose_failure(step, resolved_args, step_result.error or "Unknown error")
            
            logger.warning(
                f"[Jarvis Awareness] Step '{step.id}' (tool: {step.tool_name}) attempt {current_attempt} failed. "
                f"Root cause: {diagnosis.root_cause_analysis}. Suggestion: {diagnosis.suggested_fix}"
            )
            
            self.pipeline_logger.log_event("STEP_ATTEMPT_FAILED", {
                "step_id": step.id,
                "tool_name": step.tool_name,
                "attempt": current_attempt,
                "error": step_result.error,
                "diagnosis": diagnosis.model_dump()
            }, pipeline_id=pipeline_id, step_id=step.id)

            if current_attempt <= step.max_retries and diagnosis.can_retry:
                # If revised arguments were suggested by diagnosis, use them
                if diagnosis.revised_arguments:
                    resolved_args.update(diagnosis.revised_arguments)
                await asyncio.sleep(0.5)  # Brief backoff before retry
            else:
                break

        # If retries exhausted and still failed:
        step.status = "failed"
        step.error = step_result.error if step_result else "Execution failed"
        step.duration_ms = step_result.duration_ms if step_result else 0.0
        step.completed_at = datetime.now(timezone.utc)
        self.state_manager.save_step(pipeline_id, step)

        self.pipeline_logger.log_event("STEP_FAILED", {
            "step_id": step.id,
            "tool_name": step.tool_name,
            "final_error": step.error,
            "retry_count": step.retry_count
        }, pipeline_id=pipeline_id, step_id=step.id)

        return step_result or StepResult(
            step_id=step.id,
            tool_name=step.tool_name,
            success=False,
            error=step.error
        )

    def _resolve_arguments(self, args: Dict[str, Any], step_map: Dict[str, PipelineStep]) -> Dict[str, Any]:
        """
        Recursively replaces placeholder expressions like '{{steps.step_1.output.result}}'
        or '$step_1.result' with evaluated values from previous step outputs.
        """
        def resolve_value(val: Any) -> Any:
            if isinstance(val, str):
                # Pattern 1: {{steps.<step_id>.output.<field>}}
                pattern = r"\{\{steps\.([a-zA-Z0-9_\-]+)\.output(?:\.([a-zA-Z0-9_\.]+))?\}\}"
                match = re.search(pattern, val)
                if match:
                    step_id = match.group(1)
                    field_path = match.group(2)
                    referenced_step = step_map.get(step_id)
                    if referenced_step and referenced_step.output is not None:
                        output = referenced_step.output
                        if not field_path:
                            return output
                        # Traverse nested field path
                        curr = output
                        for field in field_path.split("."):
                            if isinstance(curr, dict) and field in curr:
                                curr = curr[field]
                            else:
                                curr = None
                                break
                        # If string was exactly the placeholder, return actual typed object
                        if val == match.group(0):
                            return curr
                        return val.replace(match.group(0), str(curr))

                # Pattern 2: $step_<id>.<field>
                pattern_short = r"\$([a-zA-Z0-9_\-]+)\.([a-zA-Z0-9_\.]+)"
                match_short = re.search(pattern_short, val)
                if match_short:
                    step_id = match_short.group(1)
                    field_path = match_short.group(2)
                    referenced_step = step_map.get(step_id)
                    if referenced_step and referenced_step.output is not None:
                        output = referenced_step.output
                        curr = output
                        for field in field_path.split("."):
                            if isinstance(curr, dict) and field in curr:
                                curr = curr[field]
                            else:
                                curr = None
                                break
                        if val == match_short.group(0):
                            return curr
                        return val.replace(match_short.group(0), str(curr))

                return val
            elif isinstance(val, dict):
                return {k: resolve_value(v) for k, v in val.items()}
            elif isinstance(val, list):
                return [resolve_value(item) for item in val]
            return val

        return resolve_value(args)

    def _diagnose_failure(self, step: PipelineStep, args: dict, error_message: str) -> FailureDiagnosis:
        """
        Inspects failure to build high-awareness diagnosis (root cause & suggested fix).
        """
        err_lower = error_message.lower()
        if "not found in the registry" in err_lower:
            return FailureDiagnosis(
                failed_step_id=step.id,
                tool_name=step.tool_name,
                error_message=error_message,
                root_cause_analysis="The required tool is not loaded or missing from ToolRegistry.",
                suggested_fix="Dynamically synthesize and register the missing tool, or ask user for tool implementation.",
                can_retry=False
            )
        elif "argument error" in err_lower or "missing 1 required" in err_lower:
            return FailureDiagnosis(
                failed_step_id=step.id,
                tool_name=step.tool_name,
                error_message=error_message,
                root_cause_analysis="The tool was called with invalid or missing arguments.",
                suggested_fix="Inspect tool schema and align argument parameter names.",
                can_retry=True
            )
        elif "file not found" in err_lower:
            return FailureDiagnosis(
                failed_step_id=step.id,
                tool_name=step.tool_name,
                error_message=error_message,
                root_cause_analysis="Target file path does not exist on disk.",
                suggested_fix="Verify directory listing or create file before reading.",
                can_retry=False
            )
        else:
            return FailureDiagnosis(
                failed_step_id=step.id,
                tool_name=step.tool_name,
                error_message=error_message,
                root_cause_analysis=f"Runtime exception during tool execution: {error_message}",
                suggested_fix="Retry step or re-evaluate step logic.",
                can_retry=True
            )
