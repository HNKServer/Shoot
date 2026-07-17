#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
WHEEL_DIR="$ROOT_DIR/app/src/main/python/wheels"
CONSTRAINTS="$ROOT_DIR/app/src/main/python/constraints-android.txt"

mkdir -p "$WHEEL_DIR"

"$PYTHON_BIN" - "$WHEEL_DIR" <<'PY'
from __future__ import annotations

import html
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

index_url = "https://pypi.flet.dev/pydantic-core"
filenames = [
    "pydantic_core-2.33.2-cp313-cp313-android_24_arm64_v8a.whl",
    "pydantic_core-2.33.2-cp313-cp313-android_24_x86_64.whl",
]
wheel_dir = Path(sys.argv[1])
wheel_dir.mkdir(parents=True, exist_ok=True)

print(f"Reading {index_url}")
with urllib.request.urlopen(index_url, timeout=60) as response:
    page = response.read().decode("utf-8", "replace")

base = index_url if index_url.endswith("/") else index_url + "/"
for filename in filenames:
    pattern = r'href=["\']([^"\']*' + re.escape(filename) + r'[^"\']*)["\']'
    match = re.search(pattern, page)
    if not match:
        raise SystemExit(f"Could not find {filename} in {index_url}")

    href = html.unescape(match.group(1))
    url = urljoin(base, href)
    output = wheel_dir / filename
    print(f"Downloading {filename}")
    urllib.request.urlretrieve(url, output)
    print(f"  -> {output}")
PY

cat > "$CONSTRAINTS" <<'EOF_CONSTRAINTS'
# Android/Chaquopy native Pydantic v2 pins.
# Generated/refreshed by tools/pydantic_core_android/fetch_flet_pydantic_core_wheels.sh.
#
# Target runtime:
#   Chaquopy Python: 3.13
#   Android wheel tags: cp313-cp313-android_24_arm64_v8a and
#                       cp313-cp313-android_24_x86_64
pydantic==2.11.10
pydantic-core==2.33.2
EOF_CONSTRAINTS

echo "Done. Wheels are in: $WHEEL_DIR"
echo "Constraints refreshed: $CONSTRAINTS"
