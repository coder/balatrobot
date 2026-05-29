"""Tests for balatrobot stop command."""

import json
import os
import signal
from unittest.mock import patch

from typer.testing import CliRunner

from balatrobot.cli import app

runner = CliRunner()


class TestStopCommand:
    """Test balatrobot stop command."""

    def test_stop_help(self):
        """Stop --help shows usage."""
        result = runner.invoke(app, ["stop", "--help"])
        assert result.exit_code == 0
        assert "stop" in result.output.lower()

    def test_stop_no_state_file(self, tmp_path, monkeypatch):
        """Stop shows message when no state file exists."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["stop"])
        assert result.exit_code == 0
        assert "No running instances" in result.output

    def test_stop_dead_pid_in_state_file(self, tmp_path, monkeypatch):
        """Dead PID in state file is auto-deleted, shows no instances."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        # Write state file with a PID that definitely doesn't exist
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": 999999999,
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/14001.log",
                },
            ],
        }
        state_path.write_text(json.dumps(state_data))

        result = runner.invoke(app, ["stop"])
        assert result.exit_code == 0
        assert "No running instances" in result.output
        # State file should have been cleaned up by StateFile.read()
        assert not state_path.exists()

    def test_stop_live_pid_sigterm_succeeds(self, tmp_path, monkeypatch):
        """Stop sends SIGTERM and reports success when process dies."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/14001.log",
                },
            ],
        }
        state_path.write_text(json.dumps(state_data))

        # First os.kill: StateFile.read() alive check (signal 0) → None
        # Second os.kill: stop() SIGTERM → ProcessLookupError (already dead)
        with patch("balatrobot.cli.stop.os.kill") as mock_kill:
            mock_kill.side_effect = [None, ProcessLookupError()]
            result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0
        assert f"Server stopped (PID {os.getpid()})" in result.output
        assert mock_kill.call_count == 2

    def test_stop_live_pid_timeout(self, tmp_path, monkeypatch):
        """Stop reports error when process won't die within timeout."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/14001.log",
                },
            ],
        }
        state_path.write_text(json.dumps(state_data))

        # os.kill always succeeds — process never dies
        # time.monotonic jumps forward to skip the 5s wait
        with (
            patch("balatrobot.cli.stop.os.kill", return_value=None),
            patch("balatrobot.cli.stop.time.monotonic") as mock_time,
            patch("balatrobot.cli.stop.time.sleep"),
        ):
            # deadline = monotonic() + 5.0 = 5.0
            # First poll: monotonic() returns 1.0 (< 5.0, enter loop)
            # After sleep, monotonic() returns 100.0 (> 5.0, exit loop → timeout)
            mock_time.side_effect = [0.0, 1.0, 100.0]
            result = runner.invoke(app, ["stop"])

        assert result.exit_code == 1
        assert "Timed out" in result.output

    def test_stop_permission_denied(self, tmp_path, monkeypatch):
        """Stop handles PermissionError from os.kill gracefully."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {
                    "host": "127.0.0.1",
                    "port": 14001,
                    "log_path": "/tmp/logs/14001.log",
                },
            ],
        }
        state_path.write_text(json.dumps(state_data))

        def kill_permission_denied(pid, sig):
            """Allow signal-0 alive checks, raise on SIGTERM."""
            if sig == signal.SIGTERM:
                raise PermissionError("Not allowed")
            return None

        with patch("balatrobot.cli.stop.os.kill", side_effect=kill_permission_denied):
            result = runner.invoke(app, ["stop"])

        assert result.exit_code == 1
        assert "Permission denied" in result.output
