"""Docker platform launcher — runs the balatrobox:latest image.
GitHub repo: https://github.com/S1M0N38/balatrobox
"""

import os
import shutil
import subprocess

from balatrobot.config import Config
from balatrobot.platforms.base import BaseLauncher

IMAGE = "balatrobox:latest"

STREAM_CONTAINER_PORT = 8080

LOCAL_REPO_MOUNTS: dict[str, str] = {
    "BALATROSRC_LOCAL_REPO": "/app/balatro",
    "BALATROBOT_LOCAL_REPO": "/mods/balatrobot",
    "DEBUGPLUS_LOCAL_REPO": "/mods/DebugPlus",
}

PASSTHROUGH_ENV: tuple[str, ...] = (
    "BALATROSRC_GITHUB_REPO",
    "BALATROSRC_GITHUB_BRANCH",
    "BALATROSRC_GITHUB_TOKEN",
    "BALATROBOT_GITHUB_REPO",
    "BALATROBOT_GITHUB_BRANCH",
    "BALATROBOX_DISPLAY",
    "BALATROBOX_STREAM",
)


class DockerLauncher(BaseLauncher):
    """Launcher that runs a fresh ``balatrobox:latest`` container per instance."""

    def validate_paths(self, config: Config) -> None:
        """Fail fast if the docker CLI or the image is unavailable."""
        if shutil.which("docker") is None:
            raise RuntimeError(
                "docker CLI not found on PATH. Install Docker and retry."
            )
        # `docker image inspect` exits non-zero when the image is missing.
        result = subprocess.run(
            ["docker", "image", "inspect", IMAGE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Image {IMAGE} not found. Build it with: docker build -t {IMAGE} "
                f"(run this from the balatrobox repo)."
            )

    def build_env(self, config: Config) -> dict[str, str]:
        """Host environment for the ``docker`` CLI itself.

        The *container* env is built explicitly via ``-e`` flags in
        :meth:`build_cmd`; we never blanket-forward the host env inside.
        """
        return os.environ.copy()

    def build_cmd(self, config: Config) -> list[str]:
        """Assemble the foreground ``docker run`` argv.

        Foreground + ``--rm`` + ``-i`` is the linchpin: it keeps the
        unmodified Popen lifecycle (``poll()`` / ``terminate()``) working,
        and ``--rm`` cleans the container on exit.
        """
        cmd: list[str] = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--name",
            f"balatrobot-{config.port}",
            "--label",
            "balatrobot=true",
            "-p",
            f"{config.port}:{config.port}",
        ]

        # Optional HLS stream port → container's internal :8080.
        if config.stream_port is not None:
            cmd += ["-p", f"{config.stream_port}:{STREAM_CONTAINER_PORT}"]

        # Local-checkout mounts (read-only). Skipped when the var is unset.
        for env_var, target in LOCAL_REPO_MOUNTS.items():
            path = os.environ.get(env_var)
            if path:
                cmd += ["-v", f"{path}:{target}:ro"]

        # Mount extra paths
        extra = os.environ.get("BALATROBOT_DOCKER_MOUNTS")
        if extra:
            for path in extra.split(os.pathsep):
                path = path.strip()
                if path:
                    cmd += ["-v", f"{path}:{path}:rw"]

        # Force 0.0.0.0 host
        driving = config.to_env()
        driving["BALATROBOT_HOST"] = "0.0.0.0"
        for name, value in driving.items():
            cmd += ["-e", f"{name}={value}"]

        # Pass env vars
        for env_var in PASSTHROUGH_ENV:
            value = os.environ.get(env_var)
            if value is not None:
                cmd += ["-e", f"{env_var}={value}"]

        # Per-instance log directory
        instance_dir = getattr(self, "instance_dir", None)
        if instance_dir is not None:
            cmd += [
                "-v",
                f"{instance_dir}:{instance_dir}:rw",
                "-e",
                f"BALATROBOT_LOG_DIR={instance_dir}",
            ]

        cmd.append(IMAGE)
        return cmd
