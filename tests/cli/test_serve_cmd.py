"""Integration tests for balatrobot serve command."""

import pytest
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

    # --- Num instances validation tests ---

    def test_serve_num_instances_zero(self):
        """--num 0 rejected with error message."""
        result = runner.invoke(app, ["serve", "--num", "0"])
        assert result.exit_code == 1
        assert "--num must be >= 1" in result.output

    def test_serve_num_instances_negative(self):
        """Negative --num rejected."""
        result = runner.invoke(app, ["serve", "--num", "-1"])
        assert result.exit_code == 1
        assert "--num must be >= 1" in result.output

    # --- Render mode validation tests ---

    def test_serve_invalid_render_mode(self):
        """Invalid render mode rejected with error message."""
        result = runner.invoke(app, ["serve", "--render", "invalid"])
        assert result.exit_code == 1
        assert "Invalid render mode 'invalid'" in result.output

    # --- Help text tests ---

    def test_serve_help(self):
        """serve --help shows all options."""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--settings" in result.output
        assert "--render" in result.output
        assert "--platform" in result.output
        assert "--num" in result.output
        assert "--debug" in result.output
        assert "--path-balatro" in result.output
        assert "--path-lovely" in result.output
        assert "--path-love" in result.output
        assert "--path-logs" in result.output
        # Old flags should NOT be present
        assert "--fast" not in result.output
        assert "--headless" not in result.output
        assert "--render-on-api" not in result.output
        assert "--audio" not in result.output
        assert "--no-shaders" not in result.output
        assert "--gamespeed" not in result.output
        assert "--fps-cap" not in result.output
        assert "--animation-fps" not in result.output
        assert "--no-reduced-motion" not in result.output
        assert "--pixel-art-smoothing" not in result.output

    def test_serve_settings_help_text(self):
        """--settings help shows profile name description."""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert (
            "profile name" in result.output.lower()
            or "Settings profile" in result.output
        )

    # --- Settings callback validation tests ---

    def test_serve_settings_valid_name(self):
        """Valid profile names accepted by --settings."""
        from balatrobot.cli.serve import settings_callback

        assert settings_callback(None) is None
        assert settings_callback("fast") == "fast"
        assert settings_callback("headless") == "headless"
        assert settings_callback("my-profile") == "my-profile"
        assert settings_callback("my_profile") == "my_profile"
        assert settings_callback("Profile123") == "Profile123"

    def test_serve_settings_rejects_path(self):
        """--settings rejects paths with slashes."""
        result = runner.invoke(app, ["serve", "--settings", "/path/to/profile"])
        assert result.exit_code != 0

    def test_serve_settings_rejects_dotdot(self):
        """--settings rejects '..' traversal."""
        result = runner.invoke(app, ["serve", "--settings", "../etc/passwd"])
        assert result.exit_code != 0

    def test_serve_settings_rejects_empty(self):
        """--settings rejects empty-ish names."""
        import typer

        from balatrobot.cli.serve import settings_callback

        with pytest.raises(typer.BadParameter):
            settings_callback("")

    def test_serve_settings_rejects_leading_hyphen(self):
        """--settings rejects names starting with hyphen."""
        import typer

        from balatrobot.cli.serve import settings_callback

        with pytest.raises(typer.BadParameter):
            settings_callback("-bad")

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

        monkeypatch.setenv("BALATROBOT_DEBUG", "1")
        monkeypatch.setenv("BALATROBOT_PORT", "8888")

        config = Config.from_kwargs(debug=None, port=None)
        assert config.debug is True
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
        assert "stop" in result.output

    def test_no_args_shows_help(self):
        """Running without args shows help (exit code 2 for multi-command apps)."""
        result = runner.invoke(app, [])
        # Typer no_args_is_help exits with code 2 for multi-command apps
        assert result.exit_code == 2
        assert "serve" in result.output
        assert "api" in result.output
