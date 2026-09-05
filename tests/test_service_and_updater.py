import os
import pytest
from core.service import ServiceManager
from core.updater import CoreUpdater

def test_service_manager_pid_lifecycle(tmp_path):
    svc = ServiceManager(root_dir=str(tmp_path))
    assert svc.get_running_pid() is None

    # Simulate saving a PID
    svc._save_pid(999999) # Non-existent PID
    # Should detect stale PID and clear
    assert svc.get_running_pid() is None

def test_service_manager_autostart_path(tmp_path):
    svc = ServiceManager(root_dir=str(tmp_path))
    auto_path = svc.get_autostart_path()
    assert auto_path is not None
    if os.name == "nt":
        assert "Startup" in auto_path
    else:
        assert "autostart" in auto_path

def test_updater_git_inspection():
    updater = CoreUpdater()
    assert updater.is_git_repository() is True
    commit = updater.get_current_commit()
    assert commit is not None
    assert len(commit) >= 6

def test_updater_test_runner():
    updater = CoreUpdater()
    # Running test suite through updater should execute without error
    code, cur_commit, remote_commit = updater.check_for_updates()
    assert cur_commit is not None
