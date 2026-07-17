# Android Wrapper v0.4.4 notes

This is a small native-runtime packaging fix on top of v0.4.3.

## Fixed

- Server startup could fail after the Pydantic v2 wheel issue was solved with:

  ```text
  ValueError: the greenlet library is required to use this function.
  dlopen failed: library "libc++_shared.so" not found
  ```

- The wrapper now packages the Android NDK C++ shared runtime used by the native
  `greenlet` wheel.
- `Npps4Application` preloads `c++_shared` before Chaquopy imports SQLAlchemy and
  greenlet.
- `greenlet==3.5.1` is pinned alongside the Flet Android wheel index.

## Local build requirement

Install Android SDK NDK or set `ANDROID_NDK_HOME` / `ANDROID_NDK_ROOT` / `ndk.dir`.
No emulator and no nested virtualization are required.
