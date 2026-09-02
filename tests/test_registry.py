import os
import pytest
from tools.registry import ToolRegistry
from tools.native.system_tools import get_time, time_schema
from tools.native.math_tools import calculate_math, calculate_math_schema

def test_tool_registration_and_execution():
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    registry.register_tool("get_time", get_time, time_schema)
    registry.register_tool("calculate_math", calculate_math, calculate_math_schema)

    assert registry.has_tool("get_time")
    assert registry.has_tool("calculate_math")
    assert not registry.has_tool("non_existent_tool")

    # Catalog
    catalog = registry.get_tool_catalog()
    assert len(catalog) == 2
    tool_names = [t["name"] for t in catalog]
    assert "get_time" in tool_names
    assert "calculate_math" in tool_names

    # Execution success
    res = registry.execute_tool("calculate_math", {"expression": "25 * 4"})
    assert res.success is True
    assert res.output["result"] == 100
    assert res.duration_ms >= 0.0

def test_tool_execution_error_handling():
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    
    # Non existent tool
    res = registry.execute_tool("missing_tool", {})
    assert res.success is False
    assert "not found in the registry" in res.error

    # Function throwing exception
    def failing_tool(a: int):
        raise ValueError("Something went wrong inside tool")

    registry.register_tool("failing_tool", failing_tool, {"name": "failing_tool", "description": "Fails"})
    res2 = registry.execute_tool("failing_tool", {"a": 1})
    assert res2.success is False
    assert "Something went wrong inside tool" in res2.error
