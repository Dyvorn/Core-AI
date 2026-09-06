import pytest
from unittest.mock import patch, MagicMock

from tools.native.web_tools import open_url, search_web_query, open_youtube
from tools.native.desktop_tools import launch_application, open_path_in_explorer, get_clipboard_text, set_clipboard_text
from tools.native.media_tools import media_control
from tools.native.process_tools import list_running_processes, kill_process, get_hardware_metrics, lock_workstation
from tools.native.shell_tools import run_shell_command
from tools.registry import ToolRegistry


def test_open_url_and_youtube():
    with patch("webbrowser.open") as mock_open:
        res = open_url("google.com")
        assert res["status"] == "success"
        assert res["url"] == "https://google.com"
        mock_open.assert_called_with("https://google.com")

        yt_res = open_youtube(search_query="lofi hip hop")
        assert yt_res["status"] == "success"
        assert "youtube.com/results" in yt_res["url"]

        search_res = search_web_query("python asyncio", engine="google")
        assert search_res["status"] == "success"
        assert "google.com/search" in search_res["url"]


def test_launch_application():
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.return_value = MagicMock()
        res = launch_application("calc")
        assert res["status"] == "success"
        assert res["app_name"] == "calc"
        assert mock_popen.called


def test_media_control():
    # Test valid action execution
    res = media_control("volume_up")
    assert res["status"] in ("success", "error")
    # Test invalid action error
    bad = media_control("do_backflip")
    assert bad["status"] == "error"


def test_process_tools_and_safety():
    # Process listing
    proc_res = list_running_processes(limit=5)
    assert proc_res["status"] == "success"
    assert isinstance(proc_res["processes"], list)

    # Protection against terminating vital OS processes
    prot_res = kill_process("explorer.exe")
    assert prot_res["status"] == "rejected"
    assert "Safety Protection" in prot_res["reason"]

    # Protection against self-termination
    import os
    self_res = kill_process(str(os.getpid()))
    assert self_res["status"] == "rejected"

    # Hardware metrics
    hw = get_hardware_metrics()
    assert hw["status"] == "success"
    assert "metrics" in hw
    assert "disk" in hw["metrics"]


def test_run_shell_command():
    # 1. Safe command execution
    res = run_shell_command("echo hello_core_ai")
    assert res["status"] == "success"
    assert "hello_core_ai" in res["stdout"]

    # 2. Catastrophic command rejection by SafetyGate
    bad_res = run_shell_command("rm -rf /")
    assert bad_res["status"] == "rejected"
    assert "SafetyGate" in bad_res["reason"] or "Catastrophic" in bad_res["reason"]


def test_tool_registry_integration():
    import main
    reg = main.setup_tools()
    assert reg.has_tool("open_url")
    assert reg.has_tool("open_youtube")
    assert reg.has_tool("search_web_query")
    assert reg.has_tool("launch_application")
    assert reg.has_tool("media_control")
    assert reg.has_tool("take_screenshot")
    assert reg.has_tool("get_clipboard_text")
    assert reg.has_tool("set_clipboard_text")
    assert reg.has_tool("list_running_processes")
    assert reg.has_tool("kill_process")
    assert reg.has_tool("get_hardware_metrics")
    assert reg.has_tool("lock_workstation")
    assert reg.has_tool("run_shell_command")
    assert reg.has_tool("update_operator_profile")
    assert len(reg.tools) >= 25
