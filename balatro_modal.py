"""Package Balatro + BalatroBot into a Modal image.

The Balatro game itself is *not* redistributable, so it is never baked into a
public layer: the ``.love`` archive is read from your local Steam install at
build time and copied into your own private Modal image.

The image runs the game headless on Linux via the native LOVE launcher
(``love <game-dir>`` with ``liblovely.so`` LD_PRELOADed), which is the
combination BalatroBot's ``NativeLauncher`` expects.

Usage::

    modal run balatro_modal.py                  # build + smoke test
    modal run balatro_modal.py::demo_run        # start a run, print gamestate

From training-gym (or any other Modal app)::

    from balatro_modal import balatro_image, BalatroEnv
"""

from __future__ import annotations

import os
from pathlib import Path

import modal

# --- Pinned dependency versions -------------------------------------------

LOVE_VERSION = "11.5"  # the LOVE version Balatro is built against
LOVELY_VERSION = "0.9.0"  # >= 0.8.0 required by BalatroBot
SMODS_VERSION = "1.0.0-beta-1814a"  # >= 1.0.0-beta-1221a required by BalatroBot

# --- Paths inside the image -----------------------------------------------

GAME_DIR = "/opt/balatro/game"  # unpacked Balatro.love
MODS_DIR = "/opt/balatro/Mods"  # smods + balatrobot
LOVELY_SO = "/usr/local/lib/liblovely.so"
LOVE_APPIMAGE_DIR = "/opt/love"  # extracted upstream AppImage
# Lovely derives its Mods directory from the *name* of the running executable
# (`/root/.local/share/<exe-name>/Mods`).
LOVE_BIN = "/opt/balatro/bin/love"
LOVE_BIN_NAME = "love"
LOVE_WRAPPER = "/usr/local/bin/balatro-love"  # love + on-demand Xvfb
LOGS_DIR = "/tmp/balatrobot-logs"
# LOVE derives its save directory from the game's identity, which Balatro's
# conf.lua leaves unset - it relies on being a fused build. `conf.lua` is
# patched below so the location is the same one a real install uses.
SAVE_IDENTITY = "Balatro"
SAVE_DIR = f"/root/.local/share/love/{SAVE_IDENTITY}"

REPO = Path(__file__).parent

# --- Locating the local Balatro.love --------------------------------------

# `Balatro.love` is a plain zip of Lua + assets and is platform independent, so
# the macOS copy runs fine in the Linux image.
LOVE_ARCHIVE_CANDIDATES = (
    Path.home()
    / "Library/Application Support/Steam/steamapps/common/Balatro"
    / "Balatro.app/Contents/Resources/Balatro.love",
    Path.home() / ".local/share/Steam/steamapps/common/Balatro/Balatro.love",
    Path.home() / ".steam/steam/steamapps/common/Balatro/Balatro.love",
)


def find_balatro_love() -> Path:
    """Locate the local Balatro.love archive.

    Override with ``BALATRO_LOVE_ARCHIVE=/path/to/Balatro.love``.
    """
    if override := os.environ.get("BALATRO_LOVE_ARCHIVE"):
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"BALATRO_LOVE_ARCHIVE does not exist: {path}")
        return path

    for candidate in LOVE_ARCHIVE_CANDIDATES:
        if candidate.is_file():
            return candidate

    searched = "\n  ".join(str(c) for c in LOVE_ARCHIVE_CANDIDATES)
    raise FileNotFoundError(
        "Could not find Balatro.love. Install Balatro via Steam, or set "
        f"BALATRO_LOVE_ARCHIVE.\nSearched:\n  {searched}"
    )


SAVE_DIR_CANDIDATES = (
    Path.home() / "Library/Application Support/Balatro",  # macOS
    Path.home() / ".local/share/love/Balatro",  # Linux
)


def find_balatro_save() -> Path:
    """Locate the local Balatro save directory.

    Balatro crashes on a profile that has never been through its first-run
    setup (`game.lua`: `G.SETTINGS.tutorial_progress` is nil at the main menu),
    so the container starts from the same `settings.jkr` and profile a real
    install has. Override with ``BALATRO_SAVE_DIR``.
    """
    if override := os.environ.get("BALATRO_SAVE_DIR"):
        path = Path(override).expanduser()
    else:
        path = next(
            (c for c in SAVE_DIR_CANDIDATES if (c / "settings.jkr").is_file()),
            None,
        )

    if path is None or not (path / "settings.jkr").is_file():
        searched = "\n  ".join(str(c) for c in SAVE_DIR_CANDIDATES)
        raise FileNotFoundError(
            "No Balatro save data found. Launch Balatro once so it creates a "
            f"profile, or set BALATRO_SAVE_DIR.\nSearched:\n  {searched}"
        )
    return path


# --- Image ----------------------------------------------------------------

# Lovely resolves the Mods directory from LOVE's save/config directories, which
# vary with the game's identity; symlink every candidate at the one real dir.
_MOD_DIR_LINKS = (
    f"/root/.local/share/{LOVE_BIN_NAME}/Mods",  # what Lovely actually uses
    "/root/.config/love/Mods",
    f"{GAME_DIR}/Mods",
)

# LOVE needs a GL context even when BalatroBot hides the window, so bring up a
# throwaway X server (software rendering) on first launch. Xvfb itself must not
# inherit LD_PRELOAD=liblovely.so - Lovely only belongs in the game process.
_LOVE_WRAPPER_SCRIPT = f"""#!/bin/sh
set -e

# Lovely belongs in the game process only - not in this shell, Xvfb, or any
# helper it spawns.
LOVELY_PRELOAD="$LD_PRELOAD"
unset LD_PRELOAD

DISPLAY_NUM="${{BALATRO_DISPLAY:-99}}"
if ! xdpyinfo -display ":$DISPLAY_NUM" >/dev/null 2>&1; then
    Xvfb ":$DISPLAY_NUM" -screen 0 1280x720x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
    i=0
    while [ "$i" -lt 100 ]; do
        xdpyinfo -display ":$DISPLAY_NUM" >/dev/null 2>&1 && break
        i=$((i + 1))
        sleep 0.1
    done
fi

export DISPLAY=":$DISPLAY_NUM"
export LD_LIBRARY_PATH="{LOVE_APPIMAGE_DIR}/lib:${{LD_LIBRARY_PATH:-}}"
export LD_PRELOAD="$LOVELY_PRELOAD"
exec {LOVE_BIN} "$@"
"""

_base_image = (
    # Debian trixie ships LOVE 11.5, the version Balatro is built against.
    modal.Image.from_registry("debian:trixie-slim", add_python="3.12")
    # `debian:*-slim` drops man pages via a dpkg path-exclude, but LOVE's
    # postinst registers `love-11.5.6.gz` with update-alternatives and fails
    # when it is missing. Keep man pages for packages installed here.
    .run_commands(
        "sed -i '/path-exclude.*man/d' /etc/dpkg/dpkg.cfg.d/* 2>/dev/null || true",
        "rm -f /etc/dpkg/dpkg.cfg.d/docker",
    )
    .apt_install(
        "love",  # not used directly - pulls in LOVE's runtime dependencies
        "xvfb",  # virtual display
        "x11-utils",  # xdpyinfo, used to wait for Xvfb
        "libgl1-mesa-dri",  # llvmpipe software GL
        "ca-certificates",
        "curl",
        "git",
        "unzip",
        "procps",
    )
    # Upstream LOVE build. Debian's `love` statically links PhysFS without
    # exporting its symbols, and Steamodded's nativefs resolves PHYSFS_* through
    # LuaJIT's FFI at runtime - it only works against the upstream build.
    .run_commands(
        "curl -fsSL -o /tmp/love.AppImage https://github.com/love2d/love/releases"
        f"/download/{LOVE_VERSION}/love-{LOVE_VERSION}-x86_64.AppImage",
        "chmod +x /tmp/love.AppImage",
        "cd /tmp && ./love.AppImage --appimage-extract >/dev/null",
        f"mv /tmp/squashfs-root {LOVE_APPIMAGE_DIR}",
        "rm -f /tmp/love.AppImage",
    )
    # Lovely Injector
    .run_commands(
        "curl -fsSL -o /tmp/lovely.tar.gz "
        "https://github.com/ethangreen-dev/lovely-injector/releases/download/"
        f"v{LOVELY_VERSION}/lovely-x86_64-unknown-linux-gnu.tar.gz",
        "tar xzf /tmp/lovely.tar.gz -C /tmp",
        f"install -m 755 /tmp/liblovely.so {LOVELY_SO}",
        "rm -rf /tmp/lovely.tar.gz /tmp/liblovely.so",
    )
    # Steamodded + Mods directory layout
    .run_commands(
        f"mkdir -p {MODS_DIR} {GAME_DIR} /opt/balatro/bin "
        f"/root/.config/love /root/.local/share/{LOVE_BIN_NAME}",
        # The AppImage's own layout varies by release; pin a stable path to it.
        f"ln -sfn $(find {LOVE_APPIMAGE_DIR} -type f -name love -perm -u+x | head -1)"
        f" {LOVE_BIN}",
        "git clone --depth 1 --branch "
        f"{SMODS_VERSION} https://github.com/Steamodded/smods.git {MODS_DIR}/smods",
        *(f"ln -sfn {MODS_DIR} {link}" for link in _MOD_DIR_LINKS),
    )
)


def _add_local_content(image: modal.Image) -> modal.Image:
    """Layers built from files on this machine: the game and this repo.

    Guarded by `modal.is_local()` below - containers re-import this module with
    the image already built, and neither the Steam install nor the repo is
    present there.
    """
    return (
        image
        # The game itself, from the local Steam install. NativeLauncher runs
        # `love <dir>`, so the archive is expanded rather than passed as .love.
        .add_local_file(find_balatro_love(), "/opt/balatro/Balatro.love", copy=True)
        .run_commands(
            f"unzip -q /opt/balatro/Balatro.love -d {GAME_DIR}",
            # A packaged Balatro binary is "fused", which implicitly gives it
            # the Balatro save identity. Running the portable .love directory
            # does not, so set the same identity explicitly or settings.jkr is
            # never found and the main menu crashes on tutorial_progress.
            f"sed -i \"/t.title = 'Balatro'/a\\\\\\tt.identity = '{SAVE_IDENTITY}'\" "
            f"{GAME_DIR}/conf.lua",
            "rm /opt/balatro/Balatro.love",
        )
        # A real install's settings + profile, so the game boots past its
        # first-run tutorial state.
        .add_local_file(
            find_balatro_save() / "settings.jkr", f"{SAVE_DIR}/settings.jkr", copy=True
        )
        .add_local_file(
            find_balatro_save() / "1/profile.jkr",
            f"{SAVE_DIR}/1/profile.jkr",
            copy=True,
        )
        .add_local_file(
            find_balatro_save() / "1/meta.jkr", f"{SAVE_DIR}/1/meta.jkr", copy=True
        )
        # BalatroBot: the Lua mod...
        .add_local_file(
            REPO / "balatrobot.json",
            f"{MODS_DIR}/balatrobot/balatrobot.json",
            copy=True,
        )
        .add_local_file(
            REPO / "balatrobot.lua",
            f"{MODS_DIR}/balatrobot/balatrobot.lua",
            copy=True,
        )
        .add_local_dir(REPO / "src/lua", f"{MODS_DIR}/balatrobot/src/lua", copy=True)
        # ...and the Python package that launches and drives the game
        .add_local_dir(REPO / "src/balatrobot", "/opt/balatrobot/balatrobot", copy=True)
    )


balatro_image = _base_image
if modal.is_local():
    balatro_image = _add_local_content(balatro_image)

balatro_image = (
    balatro_image.pip_install("httpx", "typer")
    # LOVE launcher wrapper
    .run_commands(
        f"cat > {LOVE_WRAPPER} <<'BALATRO_LOVE_EOF'\n{_LOVE_WRAPPER_SCRIPT}\nBALATRO_LOVE_EOF",
        f"chmod +x {LOVE_WRAPPER}",
    )
    .env(
        {
            "PYTHONPATH": "/opt/balatrobot",
            "BALATROBOT_PLATFORM": "native",
            "BALATROBOT_BALATRO_PATH": GAME_DIR,
            "BALATROBOT_LOVE_PATH": LOVE_WRAPPER,
            "BALATROBOT_LOVELY_PATH": LOVELY_SO,
            "BALATROBOT_LOGS_PATH": LOGS_DIR,
            "BALATROBOT_HEADLESS": "1",
            "BALATROBOT_FAST": "1",
            "BALATROBOT_AUDIO": "0",
            "BALATROBOT_NO_SHADERS": "1",
            "LIBGL_ALWAYS_SOFTWARE": "1",
            "SDL_AUDIODRIVER": "dummy",
            # LOVE plays audio through OpenAL Soft, which ignores
            # SDL_AUDIODRIVER and otherwise fails on a container's absent ALSA.
            "ALSOFT_DRIVERS": "null",
        }
    )
)


app = modal.App("balatro-env", image=balatro_image)


# --- Environment ----------------------------------------------------------


@app.cls(image=balatro_image, timeout=60 * 60, scaledown_window=60)
class BalatroEnv:
    """One long-lived Balatro process, driven over BalatroBot's JSON-RPC API.

    This is the unit a rollout worker holds: `call()` maps 1:1 onto the API's
    endpoints (`start`, `play`, `discard`, `gamestate`, ...).
    """

    @modal.enter()
    def start_game(self) -> None:
        import asyncio

        from balatrobot.manager import BalatroInstance

        self._loop = asyncio.new_event_loop()
        self._instance = BalatroInstance()
        self._loop.run_until_complete(self._instance.start())

    @modal.exit()
    def stop_game(self) -> None:
        self._loop.run_until_complete(self._instance.stop())
        self._loop.close()

    @modal.method()
    def call(self, method: str, params: dict | None = None) -> dict:
        """Call a BalatroBot endpoint and return its JSON-RPC `result`."""
        import httpx

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }
        response = httpx.post(
            f"http://127.0.0.1:{self._instance.port}", json=payload, timeout=60.0
        )
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"{method} failed: {data['error']}")
        return data["result"]

    @modal.method()
    def game_log(self, tail: int = 40) -> str:
        """Tail the game's log file - the first place to look when a call fails."""
        log_path = self._instance.log_path
        if log_path is None or not log_path.exists():
            return "(no log file)"
        return "\n".join(log_path.read_text().splitlines()[-tail:])


# --- Smoke tests ----------------------------------------------------------


@app.function(image=balatro_image, timeout=600)
def check_image() -> dict[str, str]:
    """Verify the image layout without launching the game."""
    import subprocess

    def sh(cmd: str) -> str:
        return subprocess.run(
            cmd, shell=True, capture_output=True, text=True
        ).stdout.strip()

    return {
        "love": sh(f"LD_LIBRARY_PATH={LOVE_APPIMAGE_DIR}/lib {LOVE_BIN} --version"),
        "lovely": sh(f"ls -la {LOVELY_SO}"),
        "game_files": sh(f"ls {GAME_DIR} | head -5 | tr '\\n' ' '"),
        "mods": sh(f"ls {MODS_DIR} | tr '\\n' ' '"),
        "mod_links": sh(f"ls -ld {' '.join(_MOD_DIR_LINKS)} | tr '\\n' ' '"),
        "love_bin": sh(
            f"ls -la {LOVE_BIN} && "
            f"LD_LIBRARY_PATH={LOVE_APPIMAGE_DIR}/lib ldd {LOVE_BIN} | grep liblove"
        ),
        "balatrobot": sh("python -c 'import balatrobot; print(balatrobot.__file__)'"),
    }


@app.function(image=balatro_image, timeout=900)
def smoke_test() -> str:
    """Boot the game, hit the API, and report what the mod loaded."""
    import asyncio

    import httpx

    from balatrobot.manager import BalatroInstance

    def read_log(instance) -> str:
        log = instance.log_path
        return log.read_text() if log and log.exists() else "(no log file)"

    async def main() -> str:
        instance = BalatroInstance()
        try:
            await instance.start()
        except Exception as exc:  # noqa: BLE001 - report, don't re-raise
            return f"FAILED to start: {exc!r}\n\n--- game log ---\n{read_log(instance)[-6000:]}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"http://127.0.0.1:{instance.port}",
                    json={"jsonrpc": "2.0", "method": "health", "id": 1},
                )
            health = str(response.json())
        except Exception as exc:  # noqa: BLE001
            health = f"health call failed: {exc!r}"
        finally:
            log_text = read_log(instance)
            await instance.stop()

        interesting = [
            line
            for line in log_text.splitlines()
            if any(
                marker in line
                for marker in ("BalatroBot", "Steamodded v", "Lovely", "ERROR", "Error")
            )
        ]
        return "health: {}\n{}".format(health, "\n".join(interesting[-25:]))

    return asyncio.run(main())


@app.function(image=balatro_image, timeout=1800)
def demo_run(steps: int = 60) -> dict:
    """Drive a scripted run for `steps` actions and report where it ended up.

    Not a policy - it always plays the first five cards in hand - but it
    exercises every phase transition a rollout has to survive: blind select,
    hands, cash out, shop, booster packs.
    """
    import asyncio

    import httpx

    from balatrobot.manager import BalatroInstance

    # Phases the game moves through on its own (animations); just wait them out.
    TRANSIENT = {"HAND_PLAYED", "DRAW_TO_HAND", "NEW_ROUND", "GAME_OVER"}

    async def main() -> dict:
        instance = BalatroInstance()
        await instance.start()
        url = f"http://127.0.0.1:{instance.port}"
        history: list[str] = []
        errors: list[str] = []

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:

                async def call(method: str, params: dict | None = None) -> dict:
                    response = await client.post(
                        url,
                        json={
                            "jsonrpc": "2.0",
                            "method": method,
                            "params": params or {},
                            "id": 1,
                        },
                    )
                    data = response.json()
                    if "error" in data:
                        raise RuntimeError(f"{method}: {data['error']}")
                    return data["result"]

                state = await call(
                    "start", {"deck": "RED", "stake": "WHITE", "seed": "BALATRO"}
                )

                for _ in range(steps):
                    phase = state.get("state")

                    try:
                        if phase == "BLIND_SELECT":
                            state = await call("select")
                        elif phase == "SELECTING_HAND":
                            hand = state.get("hand") or []
                            if not hand:
                                break
                            cards = list(range(min(5, len(hand))))
                            state = await call("play", {"cards": cards})
                        elif phase == "ROUND_EVAL":
                            state = await call("cash_out")
                        elif phase == "SHOP":
                            state = await call("next_round")
                        elif phase == "TAROT_PACK" or phase.endswith("_PACK"):
                            state = await call("pack", {"skip": True})
                        elif phase in TRANSIENT:
                            await asyncio.sleep(0.25)
                            state = await call("gamestate")
                            continue
                        else:
                            errors.append(f"unhandled phase {phase}")
                            break
                    except RuntimeError as exc:
                        errors.append(str(exc))
                        break

                    history.append(phase)
                    if state.get("won") or state.get("state") == "GAME_OVER":
                        break
        finally:
            await instance.stop()

        summary = {
            "final_state": state.get("state"),
            "ante": state.get("ante_num"),
            "round": state.get("round_num"),
            "money": state.get("money"),
            "actions": len(history),
            "phases_visited": sorted(set(history)),
            "errors": errors,
        }
        print(summary)
        return summary

    return asyncio.run(main())


@app.local_entrypoint()
def main() -> None:
    print("--- image layout ---")
    for key, value in check_image.remote().items():
        print(f"{key}: {value}")
    print("\n--- boot + health ---")
    print(smoke_test.remote())
