#!/bin/sh
# Use Balatro's pinned Dojo package and project-local dashboard settings.
set -eu
training_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export MODAL_PROFILE="${MODAL_PROFILE:-modal-labs}"
export MODAL_ENVIRONMENT="${MODAL_ENVIRONMENT:-joy-dev}"
export MODAL_DOJO_CONFIG_PATH="${MODAL_DOJO_CONFIG_PATH:-$training_dir/.dojo-config.toml}"
unset VIRTUAL_ENV
exec uv run --project "$training_dir" "$@"
