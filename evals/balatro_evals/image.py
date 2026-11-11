"""The Image every Harbor evaluation's trials run in: Harbor and its Modal environment, which starts each task's
Sandboxes. Task Images are Harbor's, pulled or built in the job's environment."""

import modal

HARBOR_VERSION = "0.24.0"

# Harbor needs Python 3.12.
image = modal.Image.debian_slim(python_version="3.12").uv_pip_install(  # pyright: ignore[reportAttributeAccessIssue]
    f"harbor[modal]=={HARBOR_VERSION}"
)
