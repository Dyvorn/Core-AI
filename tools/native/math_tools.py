import math
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

def calculate_math(expression: str) -> Dict[str, Any]:
    """Safely evaluates basic math expressions."""
    # Restricted safe math namespace
    safe_namespace = {
        "abs": abs, "round": round, "min": min, "max": max,
        "sum": sum, "pow": pow,
        "math": math, "sqrt": math.sqrt, "sin": math.sin,
        "cos": math.cos, "tan": math.tan, "log": math.log,
        "pi": math.pi, "e": math.e
    }
    try:
        # Check expression for illegal words
        disallowed = ["import", "exec", "eval", "compile", "open", "system", "__", "globals", "locals"]
        for word in disallowed:
            if word in expression:
                return {"status": "error", "error": f"Security restriction: '{word}' is not allowed in math expressions"}
        
        # Evaluate using safe namespace
        result = eval(expression, {"__builtins__": {}}, safe_namespace)
        return {"status": "success", "expression": expression, "result": result}
    except Exception as e:
        return {"status": "error", "expression": expression, "error": str(e)}

def summarize_numbers(numbers: List[float]) -> Dict[str, Any]:
    """Computes summary statistics (count, sum, mean, min, max) for a list of numbers."""
    try:
        if not numbers:
            return {"status": "error", "error": "Numbers list cannot be empty"}
        total = sum(numbers)
        count = len(numbers)
        mean = total / count
        return {
            "status": "success",
            "count": count,
            "sum": total,
            "mean": mean,
            "min": min(numbers),
            "max": max(numbers)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

calculate_math_schema = {
    "name": "calculate_math",
    "description": "Perform mathematical calculations (arithmetic, square root, powers, trig)",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Mathematical formula to evaluate (e.g. '12 * 45 + sqrt(144)')"}
        },
        "required": ["expression"]
    }
}

summarize_numbers_schema = {
    "name": "summarize_numbers",
    "description": "Calculate statistical summary (count, sum, mean, min, max) for a list of numbers",
    "parameters": {
        "type": "object",
        "properties": {
            "numbers": {"type": "array", "items": {"type": "number"}, "description": "List of numeric values"}
        },
        "required": ["numbers"]
    }
}
