#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! ls app/src/main/python/wheels/pydantic_core-*-cp313-*-android_*.whl >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Missing cp313 Android pydantic-core wheel.
Run first:
  bash tools/pydantic_core_android/build_pydantic_core_android.sh --archs "aarch64"
EOF
  exit 2
fi
if ! grep -q '^pydantic-core==' app/src/main/python/constraints-android.txt; then
  cat >&2 <<'EOF'
constraints-android.txt has no pydantic-core pin.
Run first:
  bash tools/pydantic_core_android/build_pydantic_core_android.sh --archs "aarch64"
EOF
  exit 2
fi
bash scripts/build_apk.sh
