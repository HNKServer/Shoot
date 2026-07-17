# Android Wrapper v4.1 - native Pydantic v2 dependency profile

This version removes the Pydantic v1 compatibility shim and aligns Android with
NPPS4's native Pydantic v2 assumptions.

Changes:

- `requirements-android.txt` now uses `pydantic>=2.7,<3`,
  `pydantic-core>=2.18,<3`, and `pydantic-settings>=2,<3`.
- FastAPI is pinned to the modern Pydantic-v2 line: `fastapi>=0.128,<1`.
- The local shim files `sitecustomize.py`, `android_pydantic_compat.py`, and
  `pydantic_settings.py` are removed so they cannot shadow real packages.
- Gradle pip uses `--only-binary=:all:` and `--find-links src/main/python/wheels`.
  If an Android-compatible `pydantic-core` wheel is not available, the build
  fails at packaging time instead of shipping a broken runtime shim.
- Runtime Python remains Chaquopy Python 3.13, satisfying NPPS4's Python >= 3.12
  requirement.

If the build fails on `pydantic-core`, provide Android-compatible cp313 wheels in
`app/src/main/python/wheels/` or build them for the target ABIs before packaging.
