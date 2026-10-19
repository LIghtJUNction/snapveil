#!/usr/bin/env bash
set -euo pipefail
cd "${KAM_PROJECT_ROOT:?}"
python3 tools/verify.py
