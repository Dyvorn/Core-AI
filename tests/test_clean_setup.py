import os
import shutil
import pytest
from interfaces.install.clean_setup import clean_system_state, print_clean_summary_card
from tools.native.system_tools import factory_reset
from tools.registry import ToolRegistry
from brain.planner import Planner

def setup_fake_environment(tmp_path):
    """Sets up a realistic Core AI directory structure with runtime files and code files."""
    root = tmp_path

    # Virtualenv and Git (must NEVER be deleted)
    venv_dir = root / ".venv" / "Scripts"
    venv_dir.mkdir(parents=True)
    (venv_dir / "python.exe").write_text("fake_python", encoding="utf-8")

    git_dir = root / ".git"
    git_dir.mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/master", encoding="utf-8")

    # Source code files (must NEVER be deleted)
    core_dir = root / "core"
    core_dir.mkdir(parents=True)
    (core_dir / "service.py").write_text("# service code", encoding="utf-8")

    (root / "main.py").write_text("# main entrypoint", encoding="utf-8")
    (root / "core.bat").write_text("@echo off", encoding="utf-8")
    (root / "core.sh").write_text("#!/bin/bash", encoding="utf-8")

    # Config directory
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / ".env.example").write_text("CORE_PORT=8000\n", encoding="utf-8")
    (config_dir / ".env").write_text("CORE_AUTH_SECRET=my_custom_secret\nOPENAI_API_KEY=sk-test\n", encoding="utf-8")

    # SQLite Database files (must be wiped)
    (root / "core_ai.db").write_text("fake_db_data", encoding="utf-8")
    (root / "core_ai.db-wal").write_text("fake_wal_data", encoding="utf-8")
    (root / "core_ai.db-shm").write_text("fake_shm_data", encoding="utf-8")
    (root / "test_core_ai.db").write_text("fake_test_db", encoding="utf-8")

    # Logs directory (must be cleared, folder kept)
    logs_dir = root / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "core_ai.log").write_text("log line 1\n", encoding="utf-8")
    (logs_dir / "pipelines.jsonl").write_text("{}\n", encoding="utf-8")

    # Backups directory (must be cleared, folder kept)
    backups_dir = root / "backups"
    backups_dir.mkdir(parents=True)
    (backups_dir / "state_backup_2026.db").write_text("backup_db", encoding="utf-8")
    (backups_dir / "env_backup_2026.env").write_text("backup_env", encoding="utf-8")

    # Dynamic tools (generated tools must be cleared, __init__.py kept)
    dyn_dir = root / "tools" / "dynamic"
    dyn_dir.mkdir(parents=True)
    (dyn_dir / "__init__.py").write_text("# dynamic tools init", encoding="utf-8")
    (dyn_dir / "custom_generated_tool.py").write_text("# dynamic tool code", encoding="utf-8")

    # Bytecode caches (must be cleared)
    pycache_dir = core_dir / "__pycache__"
    pycache_dir.mkdir(parents=True)
    (pycache_dir / "service.cpython-313.pyc").write_text("bytecode", encoding="utf-8")

    return root

def test_clean_system_state_dry_run(tmp_path):
    root = setup_fake_environment(tmp_path)

    res = clean_system_state(
        root_dir=str(root),
        wipe_db=True,
        wipe_env=True,
        wipe_logs=True,
        wipe_backups=True,
        wipe_dynamic_tools=True,
        wipe_pycache=True,
        stop_services=False,
        dry_run=True
    )

    assert res["dry_run"] is True
    assert "core_ai.db" in res["removed_db_files"]
    assert len(res["cleared_log_files"]) == 2
    assert len(res["cleared_backup_files"]) == 2
    assert "custom_generated_tool.py" in res["cleared_dynamic_tools"]

    # In dry-run mode, all files must STILL exist
    assert (root / "core_ai.db").exists()
    assert (root / "config" / ".env").exists()
    assert (root / "logs" / "core_ai.log").exists()
    assert (root / "backups" / "state_backup_2026.db").exists()
    assert (root / "tools" / "dynamic" / "custom_generated_tool.py").exists()

def test_clean_system_state_execution(tmp_path):
    root = setup_fake_environment(tmp_path)

    res = clean_system_state(
        root_dir=str(root),
        wipe_db=True,
        wipe_env=True,
        wipe_logs=True,
        wipe_backups=True,
        wipe_dynamic_tools=True,
        wipe_pycache=True,
        stop_services=False,
        dry_run=False
    )

    assert res["status"] == "success"

    # 1. Database files must be deleted
    assert not (root / "core_ai.db").exists()
    assert not (root / "core_ai.db-wal").exists()
    assert not (root / "core_ai.db-shm").exists()
    assert not (root / "test_core_ai.db").exists()

    # 2. Config .env must be deleted, template .env.example must be preserved
    assert not (root / "config" / ".env").exists()
    assert (root / "config" / ".env.example").exists()

    # 3. Logs directory must exist but all files cleared
    assert (root / "logs").exists()
    assert len(list((root / "logs").iterdir())) == 0

    # 4. Backups directory must exist but all files cleared
    assert (root / "backups").exists()
    assert len(list((root / "backups").iterdir())) == 0

    # 5. Dynamic tools: __init__.py preserved, generated scripts deleted
    assert (root / "tools" / "dynamic" / "__init__.py").exists()
    assert not (root / "tools" / "dynamic" / "custom_generated_tool.py").exists()

    # 6. Pycache cleared
    assert not (root / "core" / "__pycache__").exists()

    # 7. CRITICAL: Virtual environment, Git, and source files must be 100% INTACT
    assert (root / ".venv" / "Scripts" / "python.exe").exists()
    assert (root / ".git" / "HEAD").exists()
    assert (root / "core" / "service.py").exists()
    assert (root / "main.py").exists()
    assert (root / "core.bat").exists()
    assert (root / "core.sh").exists()

def test_clean_system_state_keep_flags(tmp_path):
    root = setup_fake_environment(tmp_path)

    # Test preserving .env, logs, and backups via flags
    res = clean_system_state(
        root_dir=str(root),
        wipe_db=True,
        wipe_env=False,
        wipe_logs=False,
        wipe_backups=False,
        wipe_dynamic_tools=True,
        wipe_pycache=True,
        stop_services=False,
        dry_run=False
    )

    assert not (root / "core_ai.db").exists()
    assert (root / "config" / ".env").exists()
    assert (root / "logs" / "core_ai.log").exists()
    assert (root / "backups" / "state_backup_2026.db").exists()

def test_factory_reset_tool(tmp_path, monkeypatch):
    root = setup_fake_environment(tmp_path)

    # 1. Unconfirmed invocation requires confirmation
    unconfirmed = factory_reset(confirm=False)
    assert unconfirmed["status"] == "confirmation_required"

    # 2. Confirmed invocation
    import interfaces.install.clean_setup as cs_mod
    orig_clean = cs_mod.clean_system_state

    monkeypatch.setattr(
        cs_mod,
        "clean_system_state",
        lambda **kwargs: orig_clean(root_dir=str(root), stop_services=False)
    )

    confirmed = factory_reset(confirm=True)
    assert confirmed["status"] == "success"
    assert not (root / "core_ai.db").exists()

def test_planner_heuristic_routing_clean_setup():
    registry = ToolRegistry(dynamic_dir="tools/dynamic")
    planner = Planner(registry=registry, model_name="heuristic")

    test_queries = [
        "clean",
        "clean setup",
        "clean new setup",
        "delete everything but the files",
        "delete everything but files",
        "factory reset",
        "factory-reset",
        "clean server",
        "clean-slate"
    ]

    for q in test_queries:
        plan = planner.plan_problem(q)
        assert len(plan.steps) == 1, f"Failed for query '{q}'"
        assert plan.steps[0].tool_name == "factory_reset", f"Failed tool name for query '{q}'"
        assert plan.steps[0].arguments.get("confirm") is True
        # Verify offline notice is not set
        assert not plan.context.get("offline_ai_notice"), f"Offline notice set for '{q}'"

    # Test deterministic synthesis
    test_plan = planner.plan_problem("clean")
    test_plan.steps[0].status = "completed"
    test_plan.steps[0].output = {"status": "success", "message": "System wiped to clean Day-Zero state."}
    test_plan.status = "completed"
    spoken = planner.formulate_spoken_response(test_plan)
    assert "System wiped to clean Day-Zero state." in spoken

def test_print_clean_summary_card(capsys):
    fake_summary = {
        "stopped_processes": ["Core AI Microkernel (PID 1234)"],
        "removed_db_files": ["core_ai.db", "core_ai.db-wal"],
        "removed_env_files": ["config/.env"],
        "cleared_log_files": ["core_ai.log", "pipelines.jsonl"],
        "cleared_backup_files": ["state_backup_2026.db"],
        "cleared_dynamic_tools": ["custom_tool.py"],
        "cleared_pycache_dirs": ["core/__pycache__"],
        "dry_run": False
    }

    print_clean_summary_card(fake_summary)
    out = capsys.readouterr().out

    assert "ZERO-RESIDUE CLEAN SLATE MATRIX" in out
    assert "1 terminated" in out
    assert "core_ai.db" in out
    assert "PRESERVED COMPONENTS" in out
    assert ".venv" in out
