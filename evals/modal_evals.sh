#!/bin/sh
# Run the modal-evals CLI with this project's pinned SDK against prod Modal Evals, in the joy-dev environment.
set -eu
evals_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export MODAL_PROFILE="${MODAL_PROFILE:-modal-labs}"
export MODAL_ENVIRONMENT="${MODAL_ENVIRONMENT:-joy-dev}"
export MODAL_FLASH_EVAL_URL="${MODAL_FLASH_EVAL_URL:-https://flash-eval.us-east-1.modal.com}"
unset VIRTUAL_ENV
cd "$evals_dir" && exec uv run --project "$evals_dir" "$@"
