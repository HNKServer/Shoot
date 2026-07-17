# Building `pydantic-core` for Chaquopy / Android

This wrapper keeps NPPS4 on its original Pydantic v2 line. The only hard problem
is `pydantic-core`: it is a Rust/native extension, so Chaquopy needs an Android
wheel matching the app's Python and ABI.

The project is configured for:

```text
Chaquopy Python: 3.13
Wheel Python tag: cp313
Default Android ABI: arm64-v8a / aarch64
Optional emulator ABI: x86_64
Android API level: 24
```


## Recommended shortcut: use Flet's prebuilt Android wheels

This source package is already configured to prefer local wheels and then fall
back to `https://pypi.flet.dev`, which currently publishes Android wheels for
`pydantic-core` 2.33.2 on the cp313 arm64-v8a and x86_64 tags used by this
wrapper.

To pre-fill the local wheel directory without compiling Rust/NDK code, run:

```bash
bash tools/pydantic_core_android/fetch_flet_pydantic_core_wheels.sh
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pydantic_core_android\fetch_flet_pydantic_core_wheels.ps1
```

This writes the expected wheel files into:

```text
app/src/main/python/wheels/
```

The slower local Rust/NDK build path below is kept as a fallback if you need to
move to another Pydantic/core version that has no prebuilt Android wheel.

## Local build on WSL2 / Linux / macOS

Install prerequisites:

```bash
# Required commands: python3, pip, Java 17+, Android SDK, Rust/Cargo.
# ANDROID_HOME must point at your SDK root.
export ANDROID_HOME="$HOME/Android/Sdk"   # adjust if needed
cargo --version
java -version
python3 --version
```

Build only arm64 wheels for a real phone:

```bash
bash tools/pydantic_core_android/build_pydantic_core_android.sh --archs "aarch64"
```

Build arm64 + x86_64 wheels:

```bash
bash tools/pydantic_core_android/build_pydantic_core_android.sh --archs "aarch64 x86_64"
```

The script writes:

```text
app/src/main/python/wheels/pydantic_core-*.whl
app/src/main/python/constraints-android.txt
```

Then build the APK:

```bash
bash scripts/build_apk_pydantic2.sh
```

## Windows

Use WSL2:

```powershell
powershell -ExecutionPolicy Bypass -File tools\pydantic_core_android\build_pydantic_core_android.ps1 --archs "aarch64"
powershell -ExecutionPolicy Bypass -File scripts\build_apk_pydantic2.ps1
```

## GitHub Actions

The repository includes:

```text
.github/workflows/build-pydantic-core-android.yml
```

Push this source tree to GitHub, run the workflow manually, download the artifact,
and copy the generated wheels and `constraints-android.txt` back into this project.

## Why this exists

Do not switch NPPS4 to Pydantic v1. NPPS4 is written for Pydantic v2, and the
Android build should match that. This folder only solves the native dependency
piece: building a Chaquopy-compatible Android wheel for `pydantic-core`.
