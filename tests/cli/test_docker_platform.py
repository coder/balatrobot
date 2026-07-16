"""Tests for the docker platform launcher (DockerLauncher).

These are pure unit tests: ``shutil.which`` and ``subprocess.run`` are mocked
so no docker daemon or balatrobox image is required.
"""

from unittest.mock import MagicMock

import pytest

from balatrobot.config import Config
from balatrobot.platforms.docker import DockerLauncher


def _ok_run(*args, **kwargs):
    """A subprocess.run mock that always succeeds (rc=0)."""
    result = MagicMock()
    result.returncode = 0
    return result


class TestDockerValidatePaths:
    """validate_paths: docker CLI presence + balatrobox image presence."""

    def test_missing_docker_cli_raises(self, monkeypatch):
        """Raises RuntimeError when `docker` is not on PATH."""
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        launcher = DockerLauncher()

        with pytest.raises(RuntimeError, match="docker CLI not found"):
            launcher.validate_paths(Config())

    @pytest.mark.parametrize("returncode", [1, 125, 127])
    def test_missing_image_raises_with_build_hint(self, monkeypatch, returncode):
        """Raises RuntimeError mentioning `docker build` when image absent."""
        monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}")
        fail = MagicMock()
        fail.returncode = returncode
        monkeypatch.setattr("subprocess.run", lambda *a, **kw: fail)

        launcher = DockerLauncher()
        with pytest.raises(RuntimeError, match=r"docker build -t balatrobox"):
            launcher.validate_paths(Config())

    def test_image_present_succeeds(self, monkeypatch):
        """No exception when docker CLI + image are both present."""
        monkeypatch.setattr("shutil.which", lambda cmd: f"/usr/bin/{cmd}")
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            r = MagicMock()
            r.returncode = 0
            return r

        monkeypatch.setattr("subprocess.run", fake_run)
        launcher = DockerLauncher()
        launcher.validate_paths(Config())  # should not raise

        assert "docker" in seen["cmd"]
        assert "balatrobox:latest" in seen["cmd"]


class TestDockerBuildEnv:
    """build_env returns the host env for the docker CLI itself."""

    def test_returns_host_environ_copy(self, monkeypatch):
        """build_env is os.environ.copy() — the container env is via -e flags."""
        monkeypatch.setattr("os.environ", {"PATH": "/usr/bin", "HOME": "/h"})
        launcher = DockerLauncher()
        env = launcher.build_env(Config())

        assert env == {"PATH": "/usr/bin", "HOME": "/h"}


class TestDockerBuildCmd:
    """build_cmd assembles the `docker run` argv."""

    def test_minimal_shape(self, monkeypatch):
        """Minimal command maps the rpc port and tags the container."""
        monkeypatch.setattr("os.environ", {})
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001))

        assert cmd[:2] == ["docker", "run"]
        assert "--rm" in cmd
        assert "-i" in cmd
        assert cmd[-1] == "balatrobox:latest"
        # rpc port mapped both sides
        assert "-p" in cmd and "14001:14001" in cmd
        # named + labelled for recovery
        assert "balatrobot-14001" in cmd
        assert "balatrobot=true" in cmd

    def test_stream_port_mapped_to_8080(self, monkeypatch):
        """When stream_port is set, it is mapped to the container's :8080."""
        monkeypatch.setattr("os.environ", {})
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001, stream_port=8081))

        assert "8081:8080" in cmd

    def test_no_stream_mapping_when_unset(self, monkeypatch):
        """No :8080 mapping when stream_port is None."""
        monkeypatch.setattr("os.environ", {})
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001))

        assert not any(arg.endswith(":8080") for arg in cmd)

    def test_forces_host_zero(self, monkeypatch):
        """BALATROBOT_HOST is forced to 0.0.0.0 inside the container."""
        monkeypatch.setattr("os.environ", {})
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001, host="127.0.0.1"))

        assert "BALATROBOT_HOST=0.0.0.0" in cmd
        assert "BALATROBOT_HOST=127.0.0.1" not in cmd

    def test_driving_env_from_config(self, monkeypatch):
        """BALATROBOT_* driving vars come from config as -e flags."""
        monkeypatch.setattr("os.environ", {})
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(
            Config(port=14001, render="headless", debug=True, settings="turbo")
        )

        assert "BALATROBOT_RENDER=headless" in cmd
        assert "BALATROBOT_DEBUG=1" in cmd
        assert "BALATROBOT_SETTINGS=turbo" in cmd
        assert "BALATROBOT_PORT=14001" in cmd

    def test_local_repo_mounts(self, monkeypatch):
        """BALATROSRC/BALATROBOT/DEBUGPLUS local repos become read-only mounts."""
        monkeypatch.setattr(
            "os.environ",
            {
                "BALATROSRC_LOCAL_REPO": "/host/src",
                "BALATROBOT_LOCAL_REPO": "/host/bot",
                "DEBUGPLUS_LOCAL_REPO": "/host/dp",
            },
        )
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001))

        assert "-v" in cmd
        assert "/host/src:/app/balatro:ro" in cmd
        assert "/host/bot:/mods/balatrobot:ro" in cmd
        assert "/host/dp:/mods/DebugPlus:ro" in cmd

    def test_balatrobox_env_passthrough(self, monkeypatch):
        """BALATROBOX_* and GitHub fetch vars are forwarded only when set."""
        monkeypatch.setattr(
            "os.environ",
            {
                "BALATROBOX_STREAM": "1",
                "BALATROBOX_DISPLAY": "820x480",
                "BALATROSRC_GITHUB_REPO": "u/r",
                "BALATROSRC_GITHUB_BRANCH": "v1",
                "BALATROSRC_GITHUB_TOKEN": "tok",
                "BALATROBOT_GITHUB_REPO": "coder/balatrobot",
                "BALATROBOT_GITHUB_BRANCH": "dev",
            },
        )
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001))

        assert "BALATROBOX_STREAM=1" in cmd
        assert "BALATROBOX_DISPLAY=820x480" in cmd
        assert "BALATROSRC_GITHUB_REPO=u/r" in cmd
        assert "BALATROSRC_GITHUB_BRANCH=v1" in cmd
        assert "BALATROSRC_GITHUB_TOKEN=tok" in cmd
        assert "BALATROBOT_GITHUB_REPO=coder/balatrobot" in cmd
        assert "BALATROBOT_GITHUB_BRANCH=dev" in cmd

    def test_platform_env_ignored(self, monkeypatch):
        """BALATROBOX_PLATFORM is a build/run-arch concern — never forwarded."""
        monkeypatch.setattr("os.environ", {"BALATROBOX_PLATFORM": "linux/arm64"})
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001))

        assert not any(a.startswith("BALATROBOX_PLATFORM=") for a in cmd)

    def test_extra_identity_mounts(self, monkeypatch):
        """BALATROBOT_DOCKER_MOUNTS paths are bind-mounted read-write at the same path.

        The load/save endpoints receive host-absolute paths and open them
        verbatim, so extra mounts must be identity mounts (same path inside the
        container as on the host). Used by the test suite to expose its
        fixtures/temp dirs.
        """
        import os

        monkeypatch.setattr(
            "os.environ", {"BALATROBOT_DOCKER_MOUNTS": f"/host/a{os.pathsep}/host/b"}
        )
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001))

        assert "/host/a:/host/a:rw" in cmd
        assert "/host/b:/host/b:rw" in cmd

    def test_no_extra_mounts_when_unset(self, monkeypatch):
        """No identity mounts when BALATROBOT_DOCKER_MOUNTS is unset."""
        monkeypatch.setattr("os.environ", {})
        launcher = DockerLauncher()
        cmd = launcher.build_cmd(Config(port=14001))

        assert not any(a.endswith(":rw") for a in cmd)
