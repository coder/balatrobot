"""Tests for balatrobot cli list command."""

import json
import os

from typer.testing import CliRunner

from balatrobot.cli import app

runner = CliRunner()


class TestListCommand:
    """Test balatrobot list command."""

    def test_list_no_state_file(self, tmp_path, monkeypatch):
        """List shows message when no state file exists."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No running instances" in result.output

    def test_list_with_instances(self, tmp_path, monkeypatch):
        """List shows running instances."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        # Write a valid state file
        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {"host": "127.0.0.1", "port": 14001},
                {"host": "127.0.0.1", "port": 14002},
            ],
        }
        state_path.write_text(json.dumps(state_data))

        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "14001" in result.output
        assert "14002" in result.output

    def test_list_json_output(self, tmp_path, monkeypatch):
        """List --json outputs structured JSON."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))

        state_path = tmp_path / "state.json"
        state_data = {
            "pid": os.getpid(),
            "started_at": "2026-05-28T12:00:00Z",
            "instances": [
                {"host": "127.0.0.1", "port": 14001},
            ],
        }
        state_path.write_text(json.dumps(state_data))

        result = runner.invoke(app, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["instances"]) == 1
        assert data["instances"][0]["port"] == 14001

    def test_list_help(self):
        """List --help shows options."""
        result = runner.invoke(app, ["list", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.output
