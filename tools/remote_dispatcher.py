import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Set, List

from core.schemas import ToolCallRequest, StepResult
from tools.registry import ToolRegistry
from core.gateway import connection_manager

logger = logging.getLogger(__name__)

class RemoteToolDispatcher:
    """
    Bridges the local ToolRegistry with remote physical edge nodes (Car, Phone, Glasses).
    Allows the AI to execute tools that live on external edge hardware across the network.
    Automatically manages dynamic proxy registration and clean deregistration when nodes disconnect.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.node_tools: Dict[str, Set[str]] = {}

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

            # Resolve loop: prefer connection manager's main async loop if available
            loop = getattr(connection_manager, "loop", None)
            if not loop or loop.is_closed():
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

            # Execute future in the target loop
            try:
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

        if node_id not in self.node_tools:
            self.node_tools[node_id] = set()
        self.node_tools[node_id].add(tool_name)

        logger.info(f"Registered remote edge tool '{tool_name}' targeted to node '{node_id}'")

    def unregister_tools_for_node(self, node_id: str) -> List[str]:
        """
        Removes all dynamic proxy tools associated with an edge node that disconnected.
        Prevents ghost tools from lingering in the active catalog.
        """
        removed = []
        if node_id in self.node_tools:
            for tool_name in list(self.node_tools[node_id]):
                if self.registry.unregister_tool(tool_name):
                    removed.append(tool_name)
            del self.node_tools[node_id]
        if removed:
            logger.info(f"Cleaned up {len(removed)} remote tools for disconnected edge node '{node_id}': {removed}")
        return removed
