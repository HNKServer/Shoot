# Android Wrapper v4.5 - restart-safe NPPS4 import reset

This patch fixes the restart path after changing the listen host/port in the Android UI.

Symptom fixed:

```text
ValueError: Endpoint achievement/unaccomplishList is already registered!
```

Cause:

NPPS4 registers gameplay endpoints at Python import time through `npps4.idol.core.API_ROUTER_MAP` and FastAPI routers.  The Android wrapper keeps one Chaquopy Python interpreter alive across Start/Stop/Start.  v4.4 reset config/run/game modules before each start, but it did not reset `npps4.idol` and `npps4.app`, so the second import attempted to register the same endpoints into the old in-memory registry.

Fix:

`android_wrapper._reset_runtime_modules()` now also clears import-time registries and router modules before every real server start:

- `npps4.app`
- `npps4.idol`
- `npps4.webview`
- `npps4.ghome`
- `npps4.sif2export`
- related config/download/db/system helper modules

The mutable SQLite user database is not deleted. This only rebuilds Python module-level objects in memory.
