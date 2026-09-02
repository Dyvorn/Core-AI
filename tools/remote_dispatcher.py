import asyncio
import logging
import uuid
from typing import Dict, Any, Optional

from core.schemas import ToolCallRequest, StepResult
from tools.registry import ToolRegistry
from core.gateway import connection_manager

logger = logging.getLogger(__name__)

class RemoteToolDispatcher:
    """
    Bridges the local ToolRegistry with remote physical edge nodes (Car, Phone, Glasses).
    Allows the AI to execute tools that live on external edge hardware across the network.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def register_remote_edge_tool(
        self,
        node_id: str,
        tool_name: str,
        description: str,
        parameters_schema: dict,
        timeout: float = 15.0
    ):
        """
        Registers a proxy tool in the active ToolRegistry that transparently
        dispatches calls to `node_id` over its active WebSocket connection.
        """
        def remote_proxy_func(**kwargs) -> Dict[str, Any]:
            logger.info(f"Dispatching remote edge tool '{tool_name}' to physical node '{node_id}' with args: {kwargs}")
            
            # Check if event loop is running
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            request = ToolCallRequest(
                id=str(uuid.uuid4()),
                source_node="core_kernel",
                room_id="remote",
                tool_name=tool_name,
                arguments=kwargs,
                target_node=node_id
            )

            # If inside an async coroutine thread pool, run dispatch
            coro = connection_manager.dispatch_remote_tool_call(node_id=node_id, request=request, timeout=timeout)
            
            # Execute future in the current or active loop
            try:
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                result = future.result(timeout=timeout)
                return {"status": "success", "node_id": node_id, "result": result}
            except Exception as e:
                logger.error(f"Remote tool execution failed on node '{node_id}': {e}")
                return {"status": "error", "node_id": node_id, "error": str(e)}

        full_schema = {
            "name": tool_name,
            "description": f"[REMOTE EDGE: {node_id}] {description}",
            "parameters": parameters_schema,
            "target_node": node_id
        }

        self.registry.register_tool(
            name=tool_name,
            func=remote_proxy_func,
            schema=full_schema,
            is_dynamic=True
        )
        logger.info(f"Registered remote edge tool '{tool_name}' targeted to node '{node_id}'")
