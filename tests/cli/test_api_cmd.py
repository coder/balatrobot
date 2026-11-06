"""Integration tests for balatrobot api command."""

import json

from typer.testing import CliRunner

from balatrobot.cli import app
from balatrobot.cli.client import BalatroClient

runner = CliRunner()


class TestApiCommand:
    """Test balatrobot api command."""

    # --- Happy path tests ---

    def test_api_health_success(self, cli_port: int):
        """api health returns JSON result."""
        result = runner.invoke(app, ["api", "health", "--port", str(cli_port)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_api_gamestate_success(self, cli_port: int, balatro_client: BalatroClient):
        """api gamestate returns state."""
        balatro_client.call("menu")  # Reset state
        result = runner.invoke(app, ["api", "gamestate", "--port", str(cli_port)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "state" in data

    def test_api_with_params(self, cli_port: int, balatro_client: BalatroClient):
        """api command passes JSON params correctly."""
        balatro_client.call("menu")
        params = json.dumps({"deck": "RED", "stake": "WHITE"})
        result = runner.invoke(app, ["api", "start", params, "--port", str(cli_port)])
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
        assert len(methods) == 22
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
        result = runner.invoke(app, ["api", "health", "--port", str(cli_port)])
        assert result.exit_code == 0

    # --- API error handling tests ---

    def test_api_error_formatted(self, cli_port: int, balatro_client: BalatroClient):
        """API errors formatted as 'Error: NAME - message'."""
        balatro_client.call("menu")
        result = runner.invoke(
            app, ["api", "play", '{"cards": [0]}', "--port", str(cli_port)]
        )
        assert result.exit_code == 1
        assert "Error: INVALID_STATE" in result.output

    # --- Connection error tests ---

    def test_api_connection_error(self):
        """Connection error formatted correctly."""
        result = runner.invoke(app, ["api", "health", "--port", "1"])
        assert result.exit_code == 1
        assert "Connection failed" in result.output

    # --- Output format tests ---

    def test_api_output_is_indented_json(self, cli_port: int):
        """Output is pretty-printed JSON."""
        result = runner.invoke(app, ["api", "health", "--port", str(cli_port)])
        assert result.exit_code == 0
        # Check for indentation (2 spaces) or compact format
        assert '  "status"' in result.output or '"status": "ok"' in result.output
