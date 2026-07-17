# Android Wrapper v3.8

Fix startup failure `Missing or unknown backend ''` caused by premature Android imports.

- Stop no longer imports `android_main` when the server was never started.
- `_bootstrap` now sets `NPPS4_ROOT_DIR` / `NPPS4_CONFIG` and clears import-time-configured NPPS4 runtime modules before starting.
- `npps4.config.config` explicitly reapplies `NPPS4_CONFIG` to `ConfigData.model_config` before constructing settings.
- This prevents stale default config (`download.backend = ""`) from being cached after status/stop operations.
