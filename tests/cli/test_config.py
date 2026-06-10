"""Tests for balatrobot.config module."""

import pytest

from balatrobot.config import RENDER_CHOICES, Config, _parse_env_value


class TestParseEnvValue:
    """Tests for _parse_env_value type conversion."""

    def test_bool_true_values(self):
        """Boolean fields convert '1' and 'true' to True."""
        assert _parse_env_value("debug", "1") is True
        assert _parse_env_value("debug", "true") is True

    def test_bool_false_values(self):
        """Boolean fields convert other values to False."""
        assert _parse_env_value("debug", "0") is False
        assert _parse_env_value("debug", "false") is False
        assert _parse_env_value("debug", "yes") is False

    def test_string_passthrough(self):
        """String fields pass through unchanged."""
        assert _parse_env_value("host", "localhost") == "localhost"
        assert _parse_env_value("render", "headless") == "headless"
        assert _parse_env_value("settings", "fast") == "fast"


class TestConfigDefaults:
    """Tests for Config default values."""

    def test_defaults(self, clean_env):
        """Config has correct default values."""
        config = Config()

        assert config.host == "127.0.0.1"
        assert config.port == 12346
        assert config.render == "headfull"
        assert config.debug is False
        assert config.settings is None
        assert config.path_logs is None
        assert config.path_balatro is None
        assert config.path_lovely is None
        assert config.path_love is None
        assert config.platform is None


class TestConfigRenderValidation:
    """Tests for render mode validation in Config."""

    def test_valid_render_modes_accepted(self):
        """All RENDER_CHOICES produce valid configs."""
        for mode in RENDER_CHOICES:
            config = Config(render=mode)
            assert config.render == mode

    def test_invalid_render_mode_rejected(self):
        """Invalid render mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid render mode"):
            Config(render="invalid")


class TestConfigFromEnv:
    """Tests for Config.from_env() method."""

    def test_loads_env_vars(self, clean_env, monkeypatch):
        """Loads configuration from environment variables."""
        monkeypatch.setenv("BALATROBOT_HOST", "0.0.0.0")
        monkeypatch.setenv("BALATROBOT_DEBUG", "1")

        config = Config.from_env()

        assert config.port == 12346
        assert config.host == "0.0.0.0"
        assert config.debug is True

    def test_defaults_when_no_env(self, clean_env):
        """Uses defaults when no env vars set."""
        config = Config.from_env()

        assert config.port == 12346
        assert config.host == "127.0.0.1"

    def test_render_from_env(self, clean_env, monkeypatch):
        """Render mode loaded from environment."""
        monkeypatch.setenv("BALATROBOT_RENDER", "headless")

        config = Config.from_env()

        assert config.render == "headless"

    def test_settings_from_env(self, clean_env, monkeypatch):
        """Settings profile name loaded from environment."""
        monkeypatch.setenv("BALATROBOT_SETTINGS", "headless")

        config = Config.from_env()

        assert config.settings == "headless"

    def test_path_fields_use_new_names(self, clean_env, monkeypatch):
        """New path field names work from environment."""
        monkeypatch.setenv("BALATROBOT_PATH_BALATRO", "/balatro")
        monkeypatch.setenv("BALATROBOT_PATH_LOVELY", "/lovely")
        monkeypatch.setenv("BALATROBOT_PATH_LOVE", "/love")
        monkeypatch.setenv("BALATROBOT_PATH_LOGS", "/logs")

        config = Config.from_env()

        assert config.path_balatro == "/balatro"
        assert config.path_lovely == "/lovely"
        assert config.path_love == "/love"
        assert config.path_logs == "/logs"


class TestConfigToEnv:
    """Tests for Config.to_env() method."""

    def test_serializes_values(self):
        """Serializes config to environment dict."""
        config = Config(port=9999, debug=True, host="0.0.0.0")
        env = config.to_env()

        assert env["BALATROBOT_PORT"] == "9999"
        assert env["BALATROBOT_DEBUG"] == "1"
        assert env["BALATROBOT_HOST"] == "0.0.0.0"

    def test_skips_none_values(self):
        """None values are not included."""
        config = Config(path_balatro=None)
        env = config.to_env()

        assert "BALATROBOT_PATH_BALATRO" not in env

    def test_skips_false_bools(self):
        """False boolean values are not included."""
        config = Config(debug=False)
        env = config.to_env()

        assert "BALATROBOT_DEBUG" not in env

    def test_includes_render(self):
        """Render mode is included in env output."""
        config = Config(render="headless")
        env = config.to_env()

        assert env["BALATROBOT_RENDER"] == "headless"

    def test_includes_settings(self):
        """Settings profile name is included in env output."""
        config = Config(settings="fast")
        env = config.to_env()

        assert env["BALATROBOT_SETTINGS"] == "fast"

    def test_uses_new_env_var_names(self):
        """Uses BALATROBOT_PATH_* naming convention."""
        config = Config(
            path_balatro="/balatro",
            path_lovely="/lovely",
            path_love="/love",
            path_logs="/logs",
        )
        env = config.to_env()

        assert env["BALATROBOT_PATH_BALATRO"] == "/balatro"
        assert env["BALATROBOT_PATH_LOVELY"] == "/lovely"
        assert env["BALATROBOT_PATH_LOVE"] == "/love"
        assert env["BALATROBOT_PATH_LOGS"] == "/logs"
