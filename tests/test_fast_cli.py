import pytest
from unittest.mock import patch, MagicMock
from interfaces.cli.client import execute_via_daemon, fallback_in_process, main

def test_fast_cli_execute_via_daemon():
    mock_cm = MagicMock()
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"status": "completed", "spoken_response": "Test success", "final_output": "done"}'
    mock_cm.__enter__.return_value = mock_response
    mock_cm.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_cm):
        res = execute_via_daemon("test goal", host="127.0.0.1", port=8000)
        assert res["status"] == "completed"
        assert res["spoken_response"] == "Test success"

def test_fast_cli_main_success(capsys):
    mock_cm = MagicMock()
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"status": "completed", "spoken_response": "All good, Dyvorn."}'
    mock_cm.__enter__.return_value = mock_response
    mock_cm.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_cm):
        test_args = ["core", "what time is it"]
        with patch("sys.argv", test_args):
            exit_code = main()
            assert exit_code == 0
            captured = capsys.readouterr()
            assert "All good, Dyvorn." in captured.out

def test_fast_cli_fallback_when_offline():
    import urllib.error
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        with patch("interfaces.cli.client.fallback_in_process", return_value=0) as mock_fallback:
            test_args = ["core", "what time is it"]
            with patch("sys.argv", test_args):
                exit_code = main()
                assert exit_code == 0
                mock_fallback.assert_called_once()
