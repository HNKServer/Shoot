#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHON_TAG="cp313"
ARCHS="aarch64"
ANDROID_API_LEVEL="24"
PYDANTIC_SPEC="pydantic>=2.8,<3"
CLEAN=1

usage() {
  cat <<'EOF'
Build Android/Chaquopy pydantic-core wheels for the native Pydantic v2 profile.

Default target: Python 3.13, Android API 24, arm64-v8a/aarch64.

Usage:
  bash tools/pydantic_core_android/build_pydantic_core_android.sh [options]

Options:
  --python-bin PATH       Host Python used to run pip/cibuildwheel (default: python3)
  --python-tag cp313      CPython tag to build (default: cp313). Keep cp313 unless you also change Chaquopy Python.
  --archs "aarch64 x86_64" Android architectures to build (default: aarch64)
  --api 24               Android API level for wheel tag (default: 24)
  --pydantic-spec SPEC   Pydantic resolver spec (default: pydantic>=2.8,<3)
  --no-clean             Don't remove old pydantic_core wheels before building
  -h, --help             Show this help

Outputs:
  app/src/main/python/wheels/pydantic_core-*-<python-tag>-*-android_*.whl
  app/src/main/python/constraints-android.txt
  build/pydantic-core-android/resolve.json

Requirements:
  Linux or WSL2/macOS with curl, Java, Android SDK (ANDROID_HOME), Rust/Cargo,
  and Python with pip. For CI, use the included GitHub Actions workflow.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python-bin) PYTHON_BIN="$2"; shift 2 ;;
    --python-tag) PYTHON_TAG="$2"; shift 2 ;;
    --archs) ARCHS="$2"; shift 2 ;;
    --api) ANDROID_API_LEVEL="$2"; shift 2 ;;
    --pydantic-spec) PYDANTIC_SPEC="$2"; shift 2 ;;
    --no-clean) CLEAN=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN" >&2
  exit 2
fi
if ! command -v cargo >/dev/null 2>&1; then
  echo "Rust/Cargo not found. Install Rust first: https://rustup.rs/" >&2
  exit 2
fi
if [[ -z "${ANDROID_HOME:-}" ]]; then
  echo "ANDROID_HOME is not set. Install Android command-line tools / Android Studio and export ANDROID_HOME." >&2
  exit 2
fi
if ! command -v java >/dev/null 2>&1 && [[ -z "${JAVA_HOME:-}" ]]; then
  echo "Java not found. Install JDK 17+ or set JAVA_HOME." >&2
  exit 2
fi

BUILD_DIR="$ROOT_DIR/build/pydantic-core-android"
SRC_DIR="$BUILD_DIR/src"
SDIST_DIR="$BUILD_DIR/sdist"
WHEEL_DIR="$ROOT_DIR/app/src/main/python/wheels"
CONSTRAINTS="$ROOT_DIR/app/src/main/python/constraints-android.txt"
RESOLVE_JSON="$BUILD_DIR/resolve.json"
mkdir -p "$BUILD_DIR" "$SRC_DIR" "$SDIST_DIR" "$WHEEL_DIR"

"$PYTHON_BIN" -m pip install -U pip build cibuildwheel packaging
"$PYTHON_BIN" "$SCRIPT_DIR/resolve_pydantic_core.py" \
  --python "$PYTHON_BIN" \
  --pydantic-spec "$PYDANTIC_SPEC" \
  --json-out "$RESOLVE_JSON"

PYDANTIC_VERSION="$($PYTHON_BIN - <<PY
import json
print(json.load(open('$RESOLVE_JSON'))['pydantic'])
PY
)"
CORE_VERSION="$($PYTHON_BIN - <<PY
import json
print(json.load(open('$RESOLVE_JSON'))['pydantic_core'])
PY
)"

echo "Resolved pydantic==$PYDANTIC_VERSION, pydantic-core==$CORE_VERSION"

if [[ "$CLEAN" == "1" ]]; then
  rm -f "$WHEEL_DIR"/pydantic_core-*.whl "$WHEEL_DIR"/pydantic-core-*.whl || true
fi
rm -rf "$SRC_DIR" "$SDIST_DIR"
mkdir -p "$SRC_DIR" "$SDIST_DIR"

"$PYTHON_BIN" -m pip download --no-binary=:all: --no-deps \
  "pydantic-core==$CORE_VERSION" \
  -d "$SDIST_DIR"

"$PYTHON_BIN" - <<PY
import tarfile, zipfile
from pathlib import Path
sdist_dir = Path('$SDIST_DIR')
src_dir = Path('$SRC_DIR')
files = list(sdist_dir.glob('pydantic_core-*.tar.gz')) + list(sdist_dir.glob('pydantic_core-*.zip')) + list(sdist_dir.glob('pydantic-core-*.tar.gz')) + list(sdist_dir.glob('pydantic-core-*.zip'))
if not files:
    raise SystemExit('No pydantic-core sdist found in ' + str(sdist_dir))
archive = files[0]
if archive.suffix == '.zip':
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(src_dir)
else:
    with tarfile.open(archive) as tf:
        tf.extractall(src_dir)
children = [p for p in src_dir.iterdir() if p.is_dir()]
if len(children) != 1:
    raise SystemExit('Expected one extracted source directory, got: ' + ', '.join(map(str, children)))
print(children[0])
PY

PKG_DIR="$($PYTHON_BIN - <<PY
from pathlib import Path
src = Path('$SRC_DIR')
children = [p for p in src.iterdir() if p.is_dir()]
print(children[0])
PY
)"

export CIBW_PLATFORM=android
export CIBW_BUILD="${PYTHON_TAG}-*"
export CIBW_ARCHS_ANDROID="$ARCHS"
export CIBW_ANDROID_API_LEVEL="$ANDROID_API_LEVEL"
export CIBW_BUILD_FRONTEND="build"
# Running tests requires a device/emulator. We only need build-time importability inside the APK,
# so skip cibuildwheel's device tests here.
export CIBW_TEST_SKIP="*"
# More useful logs for native/Rust failures.
export CIBW_BUILD_VERBOSITY="1"

"$PYTHON_BIN" -m cibuildwheel "$PKG_DIR" --platform android --output-dir "$WHEEL_DIR"

cat > "$CONSTRAINTS" <<EOF
# Generated by tools/pydantic_core_android/build_pydantic_core_android.sh
# Keep these pins in sync with the pydantic-core wheel files in app/src/main/python/wheels/.
pydantic==$PYDANTIC_VERSION
pydantic-core==$CORE_VERSION
EOF

echo
echo "Built wheels:"
ls -lh "$WHEEL_DIR"/pydantic_core-*.whl
echo
echo "Updated constraints: $CONSTRAINTS"
cat "$CONSTRAINTS"
