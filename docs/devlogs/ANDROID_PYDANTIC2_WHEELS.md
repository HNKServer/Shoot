# NPPS4 Android Wrapper v4.3: native Pydantic v2 dependency plan

This version intentionally stays on NPPS4's native Pydantic v2 stack. It does not
contain the older Pydantic v1 compatibility shim.

The only missing dependency on stock Chaquopy is usually `pydantic-core`, because
it is a Rust/native extension and must be supplied as an Android wheel.

## One-time steps

1. Build `pydantic-core` Android wheel:

```bash
bash tools/pydantic_core_android/build_pydantic_core_android.sh --archs "aarch64"
```

For emulator support:

```bash
bash tools/pydantic_core_android/build_pydantic_core_android.sh --archs "aarch64 x86_64"
```

2. Build the APK:

```bash
bash scripts/build_apk_pydantic2.sh
```

## Generated files

The wheel builder writes:

```text
app/src/main/python/wheels/pydantic_core-*.whl
app/src/main/python/constraints-android.txt
```

`constraints-android.txt` pins the exact `pydantic` and `pydantic-core` versions
resolved during wheel creation, preventing Gradle/Chaquopy from resolving a newer
Pydantic version that requires a different core wheel.

## Version constraints

- Python runtime: Chaquopy Python 3.13 (`cp313` wheels).
- Android ABIs: `arm64-v8a` and `x86_64` only.
- Pydantic: v2, no v1 fallback.
- If the wheel is missing, build fails intentionally instead of falling back to a
  broken compatibility layer.
