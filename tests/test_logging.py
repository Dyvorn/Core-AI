import os
import json
import pytest
from core.logging_setup import setup_logging, get_pipeline_logger

def test_jsonl_pipeline_logger(tmp_path):
    test_jsonl = os.path.join(tmp_path, "test_pipelines.jsonl")
    from core.logging_setup import JsonlPipelineLogger
    logger = JsonlPipelineLogger(log_path=test_jsonl)
    
    logger.log_event("TEST_EVENT", {"key": "value"}, pipeline_id="pipe-123", step_id="step-1")
    
    assert os.path.exists(test_jsonl)
    with open(test_jsonl, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == "TEST_EVENT"
        assert data["pipeline_id"] == "pipe-123"
        assert data["step_id"] == "step-1"
        assert data["payload"]["key"] == "value"

def test_setup_logging():
    logger = setup_logging(log_file="logs/test_core_ai.log")
    assert logger is not None
