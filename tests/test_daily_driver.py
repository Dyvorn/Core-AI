import os
import sys
import sqlite3
import subprocess
import pytest
from core.state import StateManager
from core.updater import CoreUpdater
from core.service import ServiceManager

def test_state_manager_schema_migration(tmp_path):
    db_file = str(tmp_path / "migration_test.db")
    state = StateManager(db_path=db_file)
    version = state.get_schema_version()
    assert version >= 2

    # Verify migration v2 indices exist
    conn = sqlite3.connect(db_file)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indices = [r[0] for r in cursor.fetchall()]
    conn.close()

    assert "idx_pipelines_status" in indices
    assert "idx_execution_logs_source" in indices

def test_state_manager_online_backup(tmp_path):
    db_file = str(tmp_path / "backup_source.db")
    state = StateManager(db_path=db_file)
    # Write a record
    state.set_room_state("studio", {"status": "ok"})

    backup_dir = str(tmp_path / "backups")
    backup_file = state.create_backup(backup_dir=backup_dir)
    assert backup_file is not None
    assert os.path.isfile(backup_file)

    # Verify backup contains the record
    restored_state = StateManager(db_path=backup_file)
    assert restored_state.get_room_state("studio") == {"status": "ok"}

def test_updater_state_snapshots_and_pruning(tmp_path):
    updater = CoreUpdater(repo_dir=str(tmp_path))
    # Create fake db and config/.env
    fake_db = tmp_path / "core_ai.db"
    init_state = StateManager(db_path=str(fake_db))
    init_state.set_room_state("lab", {"sensor": "active"})

    fake_config = tmp_path / "config"
    fake_config.mkdir()
    fake_env = fake_config / ".env"
    fake_env.write_text("FAKE_KEY=123", encoding="utf-8")

    backup_dir = str(tmp_path / "backups")
    db_snap, env_snap = updater.create_state_snapshot(backup_dir=backup_dir)
    assert db_snap is not None
    assert env_snap is not None
    assert os.path.isfile(db_snap)
    assert os.path.isfile(env_snap)

    # Test restore
    fake_db.write_text("corrupted content", encoding="utf-8")
    updater.restore_state_snapshot(db_snap, env_snap)
    restored = StateManager(db_path=str(fake_db))
    assert restored.get_room_state("lab") == {"sensor": "active"}

def test_service_manager_status_card(tmp_path, capsys):
    svc = ServiceManager(root_dir=str(tmp_path))
    svc.print_status_card(port=8000)
    captured = capsys.readouterr()
    assert "CORE AI :: DAEMON & GATEWAY STATUS CARD" in captured.out
    assert "Daemon Process:" in captured.out

def test_oneshot_cli_goal_execution():
    repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    test_env = dict(os.environ)
    test_env["GEMINI_API_KEY"] = ""
    test_env["GOOGLE_API_KEY"] = ""
    test_env["OPENAI_API_KEY"] = ""
    test_env["ANTHROPIC_API_KEY"] = ""
    test_env["CORE_FORCE_HEURISTIC"] = "1"

    res = subprocess.run(
        [sys.executable, "main.py", "--heuristic", "--no-anim", "--solve", "what time is it"],
        cwd=repo_dir,
        env=test_env,
        capture_output=True,
        text=True,
        timeout=15.0
    )
    assert res.returncode == 0
    assert "Core AI" in res.stdout
    assert "18" in res.stdout or ":" in res.stdout or "time" in res.stdout.lower()

