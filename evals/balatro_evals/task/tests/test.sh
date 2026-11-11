#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
python3 /tests/score.py > /logs/verifier/reward.json
cat /logs/verifier/reward.json
