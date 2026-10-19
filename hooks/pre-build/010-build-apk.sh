#!/usr/bin/env bash
set -euo pipefail
cd "${KAM_PROJECT_ROOT:?}"
cp LICENSE src/snapveil/LICENSE
python3 tools/build_apk.py
