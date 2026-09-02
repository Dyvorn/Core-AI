import os
import pytest
from tools.registry import ToolRegistry
from core.state import StateManager
from brain.dynamic_generator import DynamicGenerator

def test_ast_validation_security(tmp_path):
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    generator = DynamicGenerator(registry=registry, dynamic_dir=str(tmp_path))

    # Safe code
    safe_code = """
def test_tool(x: int) -> dict:
    return {"status": "success", "val": x * 2}
"""
    is_safe, err = generator.validate_ast(safe_code)
    assert is_safe is True
    assert err is None

    # Dangerous code with subprocess
    dangerous_code_1 = """
import subprocess
def malicious_tool():
    subprocess.run(["rm", "-rf", "/"])
"""
    is_safe, err = generator.validate_ast(dangerous_code_1)
    assert is_safe is False
    assert "Security Violation" in err
    assert "subprocess" in err

    # Dangerous code with shutil
    dangerous_code_2 = """
import shutil
def del_tool():
    shutil.rmtree(".")
"""
    is_safe, err = generator.validate_ast(dangerous_code_2)
    assert is_safe is False
    assert "shutil" in err

def test_dynamic_tool_synthesis_and_execution(tmp_path):
    state_file = os.path.join(tmp_path, "test_core.db")
    state = StateManager(db_path=state_file)
    registry = ToolRegistry(dynamic_dir=str(tmp_path))
    generator = DynamicGenerator(registry=registry, state_manager=state, dynamic_dir=str(tmp_path))

    # Synthesize a hash tool
    success, file_path, err = generator.synthesize_tool(
        tool_name="test_hasher",
        description="Hashes given text with sha256",
        parameters_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"}
            },
            "required": ["text"]
        },
        sample_args={"text": "hello"}
    )

    assert success is True
    assert file_path is not None
    assert os.path.exists(file_path)
    assert registry.has_tool("test_hasher")

    # Execute synthesized tool through registry
    exec_res = registry.execute_tool("test_hasher", {"text": "hello_world"})
    assert exec_res.success is True
    assert "hash" in exec_res.output
    assert exec_res.output["status"] == "success"
