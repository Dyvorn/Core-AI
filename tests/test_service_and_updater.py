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
    # Running update check should inspect commits cleanly
    has_updates, cur_commit, remote_commit = updater.check_for_updates()
    assert cur_commit is not None

def test_updater_apply_update_force(monkeypatch):
    updater = CoreUpdater()
    # Mock check_for_updates to simulate available update
    monkeypatch.setattr(updater, "check_for_updates", lambda: (True, "abcdef", "123456"))
    # Mock _run_git pull to succeed
    monkeypatch.setattr(updater, "_run_git", lambda args: (0, "Already up to date.", ""))
    # Mock create_state_snapshot
    monkeypatch.setattr(updater, "create_state_snapshot", lambda: (None, None))
    # Mock get_current_commit
    monkeypatch.setattr(updater, "get_current_commit", lambda: "123456")

    ok, msg = updater.apply_update(force=True)
    assert ok is True
    assert "--force override applied" in msg

def test_updater_test_guard_diagnostics(monkeypatch, capsys):
    updater = CoreUpdater()
    monkeypatch.setattr(updater, "check_for_updates", lambda: (True, "abcdef", "123456"))
    monkeypatch.setattr(updater, "_run_git", lambda args: (0, "", ""))
    monkeypatch.setattr(updater, "create_state_snapshot", lambda: (None, None))
    # Simulate test failure
    monkeypatch.setattr(updater, "run_tests", lambda timeout=300.0: (False, "FAILED tests/test_dummy.py::test_fail - AssertionError"))

    ok, msg = updater.apply_update(force=False)
    assert ok is False
    assert "test guard detected test failures" in msg
    captured = capsys.readouterr()
    assert "CORE AI :: TEST GUARD FAILURE DIAGNOSTICS" in captured.out
    assert "FAILED tests/test_dummy.py::test_fail" in captured.out

def test_updater_missing_pytest_graceful(monkeypatch):
    updater = CoreUpdater()
    import subprocess
    # Simulate pytest missing (exit code 1 on import pytest)
    orig_run = subprocess.run
    def mock_run(args, **kwargs):
        if "-c" in args and "import pytest" in args:
            return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="No module named pytest")
        return orig_run(args, **kwargs)
    monkeypatch.setattr(subprocess, "run", mock_run)

    passed, out = updater.run_tests()
    assert passed is True
    assert "pytest' is not installed" in out

def test_desktop_launcher_creation(tmp_path, monkeypatch):
    from interfaces.install.setup_service import create_desktop_launcher
    fake_desktop = tmp_path / "Desktop"
    fake_desktop.mkdir()
    if os.name == "nt":
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
    else:
        monkeypatch.setenv("HOME", str(tmp_path))
    res = create_desktop_launcher(root_dir=str(tmp_path))
    assert res is not None
    assert os.path.isfile(res)

def test_watchdog_pid_lifecycle(tmp_path):
    svc = ServiceManager(root_dir=str(tmp_path))
    assert svc.get_watchdog_pid() is None

    # Simulate saving a stale watchdog PID
    w_pid_file = tmp_path / ".core_watchdog.pid"
    w_pid_file.write_text("999999", encoding="utf-8")
    assert svc.get_watchdog_pid() is None
    assert not w_pid_file.exists()

def test_autostart_enable_disable(tmp_path, monkeypatch):
    svc = ServiceManager(root_dir=str(tmp_path))
    fake_appdata = tmp_path / "AppData" / "Roaming"
    fake_home = tmp_path / "home"

    if os.name == "nt":
        monkeypatch.setenv("APPDATA", str(fake_appdata))
    else:
        monkeypatch.setenv("HOME", str(fake_home))

    assert not svc.is_autostart_enabled()

    # Enable autostart with 24/7 watchdog
    ok, msg = svc.enable_autostart(in_terminal=False, use_watchdog=True)
    assert ok is True
    assert svc.is_autostart_enabled() is True

    auto_path = svc.get_autostart_path()
    assert os.path.isfile(auto_path)
    with open(auto_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "watchdog" in content

    # Disable autostart
    ok_dis, msg_dis = svc.disable_autostart()
    assert ok_dis is True
    assert svc.is_autostart_enabled() is False
    assert not os.path.exists(auto_path)

def test_autostart_visible_terminal(tmp_path, monkeypatch):
    svc = ServiceManager(root_dir=str(tmp_path))
    fake_appdata = tmp_path / "AppData" / "Roaming"
    fake_home = tmp_path / "home"

    if os.name == "nt":
        monkeypatch.setenv("APPDATA", str(fake_appdata))
    else:
        monkeypatch.setenv("HOME", str(fake_home))

    ok, msg = svc.enable_autostart(in_terminal=True, use_watchdog=False)
    assert ok is True
    assert svc.is_autostart_enabled() is True

    auto_path = svc.get_autostart_path()
    with open(auto_path, "r", encoding="utf-8") as f:
        content = f.read()
    if os.name == "nt":
        assert "call core.bat run" in content
    else:
        assert "Terminal=true" in content

    svc.disable_autostart()

def test_watchdog_daemon_init(tmp_path):
    from core.watchdog import WatchdogDaemon, is_watchdog_running
    daemon = WatchdogDaemon(root_dir=str(tmp_path), port=8001)
    assert daemon.port == 8001
    assert daemon.max_consecutive_crashes == 5
    assert not is_watchdog_running(str(tmp_path))

def test_service_cards_output(capsys, tmp_path):
    svc = ServiceManager(root_dir=str(tmp_path))
    svc.print_status_card()
    out = capsys.readouterr().out
    assert "DAEMON & GATEWAY STATUS CARD" in out

    svc.print_autostart_card()
    out_auto = capsys.readouterr().out
    assert "24/7 ALWAYS-ON AUTOSTART STATUS" in out_auto

