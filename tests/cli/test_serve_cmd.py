"""Integration tests for balatrobot serve command."""

from typer.testing import CliRunner

from balatrobot.cli import app
from balatrobot.cli.serve import PLATFORM_CHOICES

runner = CliRunner()


class TestServeCommand:
    """Test balatrobot serve command options."""

    # --- Platform validation tests ---

    def test_serve_invalid_platform_error(self):
        """Invalid platform rejected with error message."""
        result = runner.invoke(app, ["serve", "--platform", "invalid"])
        assert result.exit_code == 1
        assert "Invalid platform 'invalid'" in result.output
        assert "darwin" in result.output  # Shows valid choices

    def test_serve_valid_platforms(self):
        """All valid platforms in list."""
        assert PLATFORM_CHOICES == ["darwin", "linux", "windows", "native"]

    # --- Help text tests ---

    def test_serve_help(self):
        """serve --help shows all options."""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--fast" in result.output
        assert "--headless" in result.output
        assert "--platform" in result.output
        assert "--num-instances" in result.output or "-n" in result.output

    # --- Config.from_kwargs tests ---

    def test_config_from_kwargs_explicit_overrides_env(self, clean_env, monkeypatch):
        """Explicit kwarg overrides environment variable."""
        from balatrobot.config import Config

        monkeypatch.setenv("BALATROBOT_HOST", "env-host")

        config = Config.from_kwargs(host="cli-host", port=None)
        assert config.host == "cli-host"

    def test_config_from_kwargs_falls_back_to_env(self, clean_env, monkeypatch):
        """None kwarg falls back to environment variable."""
        from balatrobot.config import Config

        monkeypatch.setenv("BALATROBOT_HOST", "env-host")

        config = Config.from_kwargs(host=None, port=9999)
        assert config.host == "env-host"
        assert config.port == 9999

    def test_config_from_kwargs_env_var_fallback(self, clean_env, monkeypatch):
        """Env vars used when options not provided."""
        from balatrobot.config import Config

        monkeypatch.setenv("BALATROBOT_FAST", "1")
        monkeypatch.setenv("BALATROBOT_PORT", "8888")

        config = Config.from_kwargs(fast=None, port=None)
        assert config.fast is True
        assert config.port == 8888


class TestMainApp:
    """Test main app help and structure."""

    def test_main_help(self):
        """Main app --help shows subcommands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "serve" in result.output
        assert "api" in result.output
        assert "list" in result.output

    def test_no_args_shows_help(self):
        """Running without args shows help (exit code 2 for multi-command apps)."""
        result = runner.invoke(app, [])
        # Typer no_args_is_help exits with code 2 for multi-command apps
        assert result.exit_code == 2
        assert "serve" in result.output
        assert "api" in result.output
