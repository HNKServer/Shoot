# Android Wrapper v4.18

This version continues from v4.17 and adds operator-facing download profile shortcuts.

## Added

- Main screen card: **下载后端 / 区服快捷配置**.
- One-click CN local archive profile:
  - `download.backend = "cn_archive"`
  - `compat.region = "cn"`
  - `cn_wrappers = true`
  - `cn_optional_stubs = true`
- One-click GL online DLAPI/CDN profile:
  - `download.backend = "n4dlapi"`
  - `download.n4dlapi.server = "https://ll.sif.moe/npps4_dlapi/"`
  - `compat.region = "global"`
  - `cn_wrappers = false`
  - `cn_optional_stubs = false`
- The Android Python bootstrap no longer overwrites a valid `n4dlapi` profile back to `cn_archive`.
- The generated Android config always includes both `[download.cn_archive]` and `[download.n4dlapi]` sections so switching does not require hand-editing TOML.
- Included DLAPI mirror tools under `app/src/main/python/tools/dlapi_mirror/`.

## Important limitation

This is a profile switch, not yet a true simultaneous per-session CN/GL router. A single running server process still has one active master-data/download backend at import time. CN/GL friend-linking should share the same user/friend database layer, but true concurrent CN and GL clients require a later per-session region/download/master-data adapter.
