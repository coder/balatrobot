#!/usr/bin/env bash
#
# demo_screenshots.sh — replay a short Balatro run so the screenshot-logging
# feature writes one PNG per successful API call (1.png, 2.png, ...).
#
# Prerequisite: balatrobot serve --render headfull --screenshots ... already
# running. Then run this script. Screenshots land under
# <logs>/<timestamp>/<port>/ (dirname of the instance log_path).
#
# Uses `balatrobot api --requests` (auto-discovers the ephemeral port via the
# state file). The CLI client assigns sequential JSON-RPC ids (1, 2, 3, ...),
# so each call produces a distinct <id>.png.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRACE="$HERE/demo_screenshots.req.jsonl"

balatrobot api --requests "$TRACE"

echo "=== Screenshots written ==="
balatrobot list --json | python3 -c '
import sys, json, os
i = json.load(sys.stdin)["instances"][0]
print(os.path.join(os.path.dirname(i["log_path"]), str(i["port"])))
' | xargs ls -la
