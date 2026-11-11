# Balatro, headless, with BalatroBot's JSON-RPC API, laid out as the RL harness's runtime Image is
# (coder/balatrobot, batro_modal_rl.py). The game and the mod come from `release/`, a copy of the harness's
# `balatro-rl-assets` Volume release: Balatro itself isn't redistributable, so it never leaves a private release.
FROM python:3.12-slim-trixie

# `debian:*-slim` excludes man pages, but LOVE's postinst registers one with update-alternatives and fails without it.
RUN sed -i '/path-exclude.*man/d' /etc/dpkg/dpkg.cfg.d/* 2>/dev/null || true \
    && rm -f /etc/dpkg/dpkg.cfg.d/docker \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        love xvfb x11-utils libgl1-mesa-dri ca-certificates curl git unzip procps tmux ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ARG LOVE_VERSION=11.5
ARG LOVELY_VERSION=0.9.0
ARG SMODS_VERSION=1.0.0-beta-1814a

# Upstream LOVE: Debian's links PhysFS statically without exporting it, which Steamodded's nativefs needs.
RUN curl -fsSL -o /tmp/love.AppImage \
        https://github.com/love2d/love/releases/download/${LOVE_VERSION}/love-${LOVE_VERSION}-x86_64.AppImage \
    && chmod +x /tmp/love.AppImage \
    && cd /tmp && ./love.AppImage --appimage-extract >/dev/null \
    && mv /tmp/squashfs-root /opt/love \
    && rm -f /tmp/love.AppImage \
    && curl -fsSL -o /tmp/lovely.tar.gz \
        https://github.com/ethangreen-dev/lovely-injector/releases/download/v${LOVELY_VERSION}/lovely-x86_64-unknown-linux-gnu.tar.gz \
    && tar xzf /tmp/lovely.tar.gz -C /tmp \
    && install -m 755 /tmp/liblovely.so /usr/local/lib/liblovely.so \
    && rm -f /tmp/lovely.tar.gz /tmp/liblovely.so \
    && mkdir -p /opt/balatro/bin /opt/balatro/Mods /root/.local/share/love /root/.config/love \
    && ln -sfn /opt/love/bin/love /opt/balatro/bin/love \
    && git clone --depth 1 --branch ${SMODS_VERSION} https://github.com/Steamodded/smods.git /opt/balatro/Mods/smods \
    && ln -sfn /opt/balatro/Mods /root/.local/share/love/Mods \
    && ln -sfn /opt/balatro/Mods /root/.config/love/Mods \
    && pip install --no-cache-dir httpx typer

COPY release /opt/balatro/release
RUN ln -sfn /opt/balatro/release/game /opt/balatro/game \
    && ln -sfn /opt/balatro/release/mods/balatrobot /opt/balatro/Mods/balatrobot

COPY balatro-love balatro-serve balatro balatro-replay /usr/local/bin/
RUN chmod +x /usr/local/bin/balatro-love /usr/local/bin/balatro-serve /usr/local/bin/balatro /usr/local/bin/balatro-replay

ENV PYTHONPATH=/opt/balatro/release/python \
    BALATROBOT_PLATFORM=native \
    BALATROBOT_BALATRO_PATH=/opt/balatro/game \
    BALATROBOT_LOVE_PATH=/usr/local/bin/balatro-love \
    BALATROBOT_LOVELY_PATH=/usr/local/lib/liblovely.so \
    BALATROBOT_LOGS_PATH=/tmp/balatrobot-logs \
    BALATROBOT_HEADLESS=1 \
    BALATROBOT_RENDER_ON_API=1 \
    BALATROBOT_FAST=1 \
    BALATROBOT_AUDIO=0 \
    BALATROBOT_NO_SHADERS=1 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    SDL_AUDIODRIVER=dummy \
    ALSOFT_DRIVERS=null

WORKDIR /app
