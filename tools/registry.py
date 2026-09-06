import os
import sys
import time
import importlib.util
import logging
import traceback
from typing import Dict, Any, Callable, List, Optional
from core.schemas import StepResult

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Manages all available native and dynamically synthesized tools in the system"""
    
    def __init__(self, dynamic_dir: str = "tools/dynamic"):
        self.dynamic_dir = dynamic_dir
        self.tools: Dict[str, Callable] = {}
        self.schemas: Dict[str, dict] = {}
        self.metadata: Dict[str, dict] = {}

    @property
    def dynamic_tools(self) -> Dict[str, Callable]:
        """Returns all dynamically synthesized tools currently registered."""
        return {
            name: func
            for name, func in self.tools.items()
            if self.metadata.get(name, {}).get("is_dynamic", False)
        }

    def register_tool(
        self, 
        name: str, 
        func: Callable, 
        schema: dict, 
        is_dynamic: bool = False,
        file_path: Optional[str] = None
    ):
        """Registers a tool function with its JSON schema."""
        self.tools[name] = func
        self.schemas[name] = schema
        self.metadata[name] = {
            "name": name,
            "is_dynamic": is_dynamic,
            "file_path": file_path,
            "description": schema.get("description", ""),
            "parameters": schema.get("parameters", {})
        }
        logger.info(f"Registered tool: '{name}' (dynamic={is_dynamic})")

    def unregister_tool(self, name: str) -> bool:
        """Removes a tool from the registry."""
        if name in self.tools:
            del self.tools[name]
            self.schemas.pop(name, None)
            self.metadata.pop(name, None)
            logger.info(f"Unregistered tool: '{name}'")
            return True
        return False

    def has_tool(self, name: str) -> bool:
        return name in self.tools

    def get_tool_schema(self, name: str) -> Optional[dict]:
        return self.schemas.get(name)

    def get_all_schemas(self) -> List[dict]:
        return list(self.schemas.values())

    def get_tool_catalog(self) -> List[dict]:
        """Returns rich tool descriptions and schemas for LLM inspection and planning."""
        catalog = []
        for name, meta in self.metadata.items():
            catalog.append({
                "name": name,
                "description": meta["description"],
                "parameters": meta["parameters"],
                "is_dynamic": meta["is_dynamic"]
            })
        return catalog

    def execute_tool(self, name: str, args: dict) -> StepResult:
        """
        Executes a tool by name with arguments.
        Returns a structured StepResult with success, output, error, and duration.
        """
        start_time = time.perf_counter()
        if name not in self.tools:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"Tool '{name}' is not found in the registry. Available: {list(self.tools.keys())}"
            logger.error(err_msg)
            return StepResult(
                step_id="direct",
                tool_name=name,
                success=False,
                error=err_msg,
                duration_ms=duration_ms
            )
        
        func = self.tools[name]
        try:
            logger.info(f"Executing tool '{name}' with arguments: {args}")
            # Ensure args is a dictionary
            call_args = args if isinstance(args, dict) else {}
            result = func(**call_args)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Check if result dictionary itself reported a failure status
            if isinstance(result, dict) and result.get("status") == "error":
                return StepResult(
                    step_id="direct",
                    tool_name=name,
                    success=False,
                    output=result,
                    error=result.get("error", "Tool returned status: error"),
                    duration_ms=duration_ms
                )
                
            return StepResult(
                step_id="direct",
                tool_name=name,
                success=True,
                output=result,
                duration_ms=duration_ms
            )
        except TypeError as te:
            duration_ms = (time.perf_counter() - start_time) * 1000
            error_details = f"Argument error calling '{name}': {te}. Provided args: {args}"
            logger.error(error_details)
            return StepResult(
                step_id="direct",
                tool_name=name,
                success=False,
                error=error_details,
                duration_ms=duration_ms
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            tb_str = traceback.format_exc()
            error_details = f"Execution error in tool '{name}': {e}\n{tb_str}"
            logger.error(f"Error executing tool '{name}': {e}")
            return StepResult(
                step_id="direct",
                tool_name=name,
                success=False,
                error=error_details,
                duration_ms=duration_ms
            )

    def discover_dynamic_tools(self, dynamic_dir: Optional[str] = None) -> List[str]:
        """
        Scans dynamic_dir for python modules and dynamically imports and registers valid tools.
        Each dynamic tool file should export the function and a corresponding schema dict.
        """
        target_dir = dynamic_dir or self.dynamic_dir
        os.makedirs(target_dir, exist_ok=True)
        discovered = []

        for filename in os.listdir(target_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                tool_name = filename[:-3]
                file_path = os.path.join(target_dir, filename)
                try:
                    spec = importlib.util.spec_from_file_location(f"dynamic_{tool_name}", file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[f"dynamic_{tool_name}"] = module
                        spec.loader.exec_module(module)
                        
                        # Look for tool function (matching tool_name or run_tool or entrypoint)
                        func = getattr(module, tool_name, None) or getattr(module, "run_tool", None)
                        schema = getattr(module, f"{tool_name}_schema", None) or getattr(module, "tool_schema", None)
                        
                        if func and schema:
                            self.register_tool(
                                name=tool_name,
                                func=func,
                                schema=schema,
                                is_dynamic=True,
                                file_path=file_path
                            )
                            discovered.append(tool_name)
                        else:
                            logger.warning(f"File {filename} in dynamic tools missing function '{tool_name}' or schema.")
                except Exception as e:
                    logger.error(f"Failed to load dynamic tool from {filename}: {e}")

        logger.info(f"Discovered {len(discovered)} dynamic tools in {target_dir}: {discovered}")
        return discovered

    def reload_dynamic_tools(self) -> List[str]:
        """Hot-reloads all dynamic tools from disk without restarting."""
        # Unregister existing dynamic tools
        dynamic_names = [name for name, meta in self.metadata.items() if meta.get("is_dynamic")]
        for name in dynamic_names:
            self.unregister_tool(name)
        return self.discover_dynamic_tools()
