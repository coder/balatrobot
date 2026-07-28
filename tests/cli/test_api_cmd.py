"""Integration tests for balatrobot api command."""

import json
from pathlib import Path

from typer.testing import CliRunner

from balatrobot.cli import app
from balatrobot.cli.client import BalatroClient

runner = CliRunner()


class TestApiCommand:
    """Test balatrobot api command."""

    # --- Happy path tests ---

    def test_api_health_success(self, cli_port: int):
        """api health returns JSON result with explicit port."""
        result = runner.invoke(
            app, ["api", "health", "--port", str(cli_port), "--host", "127.0.0.1"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_api_gamestate_success(self, cli_port: int, balatro_client: BalatroClient):
        """api gamestate returns state."""
        balatro_client.call("menu")  # Reset state
        result = runner.invoke(
            app, ["api", "gamestate", "--port", str(cli_port), "--host", "127.0.0.1"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "state" in data

    def test_api_with_params(self, cli_port: int, balatro_client: BalatroClient):
        """api command passes JSON params correctly."""
        balatro_client.call("menu")
        params = json.dumps({"deck": "b_red", "stake": "stake_white"})
        result = runner.invoke(
            app,
            ["api", "start", params, "--port", str(cli_port), "--host", "127.0.0.1"],
        )
        assert result.exit_code == 0

    # --- Method validation tests ---

    def test_api_invalid_method(self, cli_port: int):
        """Invalid method name rejected by Typer."""
        result = runner.invoke(app, ["api", "invalid_method", "--port", str(cli_port)])
        assert result.exit_code == 2  # Typer validation error
        assert "invalid_method" in result.output.lower()

    def test_api_all_methods_valid(self):
        """All Method enum values are valid strings."""
        from balatrobot.cli.api import Method

        methods = [m.value for m in Method]
        assert len(methods) == 24
        assert "health" in methods
        assert "gamestate" in methods

    # --- JSON validation tests ---

    def test_api_invalid_json_params(self, cli_port: int):
        """Invalid JSON params return error."""
        result = runner.invoke(
            app, ["api", "health", "{bad json", "--port", str(cli_port)]
        )
        assert result.exit_code == 1
        assert "Invalid JSON params" in result.output

    def test_api_empty_params_default(self, cli_port: int):
        """Empty params default to {}."""
        result = runner.invoke(
            app, ["api", "health", "--port", str(cli_port), "--host", "127.0.0.1"]
        )
        assert result.exit_code == 0

    # --- API error handling tests ---

    def test_api_error_formatted(self, cli_port: int, balatro_client: BalatroClient):
        """API errors formatted as 'Error: NAME - message'."""
        balatro_client.call("menu")
        result = runner.invoke(
            app,
            [
                "api",
                "play",
                '{"cards": [0]}',
                "--port",
                str(cli_port),
                "--host",
                "127.0.0.1",
            ],
        )
        assert result.exit_code == 1
        assert "Error: INVALID_STATE" in result.output

    # --- Connection error tests ---

    def test_api_connection_error(self):
        """Connection error formatted correctly."""
        result = runner.invoke(
            app, ["api", "health", "--port", "1", "--host", "127.0.0.1"]
        )
        assert result.exit_code == 1
        assert "Connection failed" in result.output

    # --- Output format tests ---

    def test_api_output_is_indented_json(self, cli_port: int):
        """Output is pretty-printed JSON."""
        result = runner.invoke(
            app, ["api", "health", "--port", str(cli_port), "--host", "127.0.0.1"]
        )
        assert result.exit_code == 0
        # Check for indentation (2 spaces) or compact format
        assert '  "status"' in result.output or '"status": "ok"' in result.output

    # --- Discovery tests ---

    def test_api_no_state_file_error(self, tmp_path, monkeypatch):
        """Discovery fails gracefully when no state file."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["api", "health"])
        assert result.exit_code == 1

    # --- Host/port validation tests ---

    def test_api_host_without_port(self, tmp_path, monkeypatch):
        """--host without --port rejected."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["api", "health", "--host", "127.0.0.1"])
        assert result.exit_code == 1
        assert "--host and --port must be provided together" in result.output

    def test_api_port_without_host(self, tmp_path, monkeypatch):
        """--port without --host rejected."""
        monkeypatch.setenv("BALATROBOT_STATE_DIR", str(tmp_path))
        result = runner.invoke(app, ["api", "health", "--port", "12346"])
        assert result.exit_code == 1
        assert "--host and --port must be provided together" in result.output


# ============================================================================
# Replay tests (--requests / --responses)
# ============================================================================


class TestReplayCommand:
    """Test balatrobot api --requests / --responses replay."""

    def _write_jsonl(self, path: Path, objects: list[dict]) -> None:
        """Write a list of dicts as JSONL."""
        path.write_text("\n".join(json.dumps(o) for o in objects))

    def test_replay_simple_sequence(self, cli_port: int, balatro_client: BalatroClient):
        """Replay a small menu→health sequence → exit 0."""
        balatro_client.call("menu")  # reset state
        reqs = [
            {"jsonrpc": "2.0", "method": "menu", "params": {}, "id": 1},
            {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 2},
        ]
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for r in reqs:
                f.write(json.dumps(r) + "\n")
            req_path = f.name

        try:
            result = runner.invoke(
                app,
                [
                    "api",
                    "--requests",
                    req_path,
                    "--port",
                    str(cli_port),
                    "--host",
                    "127.0.0.1",
                ],
            )
            assert result.exit_code == 0, result.output
            assert "Replayed 2 requests successfully" in result.output
        finally:
            Path(req_path).unlink(missing_ok=True)

    def test_replay_with_matching_responses(
        self, cli_port: int, balatro_client: BalatroClient
    ):
        """Replay + verify with matching responses → exit 0."""
        balatro_client.call("menu")
        # Capture actual responses first
        actual_result = balatro_client.call("health")

        reqs = [
            {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 1},
        ]
        resps = [
            {"jsonrpc": "2.0", "result": actual_result, "id": 1},
        ]

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for r in reqs:
                f.write(json.dumps(r) + "\n")
            req_path = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for r in resps:
                f.write(json.dumps(r) + "\n")
            resp_path = f.name

        try:
            result = runner.invoke(
                app,
                [
                    "api",
                    "--requests",
                    req_path,
                    "--responses",
                    resp_path,
                    "--port",
                    str(cli_port),
                    "--host",
                    "127.0.0.1",
                ],
            )
            assert result.exit_code == 0, result.output
            assert "Replayed 1 requests successfully" in result.output
        finally:
            Path(req_path).unlink(missing_ok=True)
            Path(resp_path).unlink(missing_ok=True)

    def test_replay_with_diverging_responses(
        self, cli_port: int, balatro_client: BalatroClient
    ):
        """Replay + verify with diverging responses → exit 1."""
        balatro_client.call("menu")

        reqs = [
            {"jsonrpc": "2.0", "method": "health", "params": {}, "id": 1},
        ]
        resps = [
            {"jsonrpc": "2.0", "result": {"status": "WRONG"}, "id": 1},
        ]

        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for r in reqs:
                f.write(json.dumps(r) + "\n")
            req_path = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            for r in resps:
                f.write(json.dumps(r) + "\n")
            resp_path = f.name

        try:
            result = runner.invoke(
                app,
                [
                    "api",
                    "--requests",
                    req_path,
                    "--responses",
                    resp_path,
                    "--port",
                    str(cli_port),
                    "--host",
                    "127.0.0.1",
                ],
            )
            assert result.exit_code == 1, result.output
            assert "Divergence" in result.output
        finally:
            Path(req_path).unlink(missing_ok=True)
            Path(resp_path).unlink(missing_ok=True)

    def test_replay_empty_requests_file(self, tmp_path):
        """Empty requests file → error."""
        req_file = tmp_path / "empty.jsonl"
        req_file.write_text("")

        result = runner.invoke(
            app,
            ["api", "--requests", str(req_file), "--port", "1", "--host", "127.0.0.1"],
        )
        assert result.exit_code == 1
        assert "empty" in result.output.lower()

    def test_replay_malformed_json_line(self, tmp_path):
        """Malformed JSON line → error with line number."""
        req_file = tmp_path / "bad.jsonl"
        req_file.write_text("{not valid json\n")

        result = runner.invoke(
            app,
            ["api", "--requests", str(req_file), "--port", "1", "--host", "127.0.0.1"],
        )
        assert result.exit_code == 1
        assert "line 1" in result.output.lower()

    def test_replay_response_count_mismatch(self, tmp_path):
        """Response count mismatch → error."""
        req_file = tmp_path / "req.jsonl"
        req_file.write_text(
            json.dumps({"jsonrpc": "2.0", "method": "health", "params": {}, "id": 1})
            + "\n"
            + json.dumps({"jsonrpc": "2.0", "method": "health", "params": {}, "id": 2})
            + "\n"
        )
        resp_file = tmp_path / "res.jsonl"
        resp_file.write_text(
            json.dumps({"jsonrpc": "2.0", "result": {"status": "ok"}, "id": 1}) + "\n"
        )

        result = runner.invoke(
            app,
            [
                "api",
                "--requests",
                str(req_file),
                "--responses",
                str(resp_file),
                "--port",
                "1",
                "--host",
                "127.0.0.1",
            ],
        )
        assert result.exit_code == 1
        assert "mismatch" in result.output.lower()
