# NPPS4 Android Wrapper v2.6 notes

Fixes based on runtime screenshots:

- Swapped the fixed-header toggle symbols: hidden header now shows `▼`, visible header now shows `▲`.
- The `LoveArrowShoot!` fixed header and status bar now use the app surface background instead of pure white.
- The path resolver now accepts either a project root such as `/storage/emulated/0/NPPS4` or an archives folder such as `/storage/emulated/0/LoveLive/list_CN_Android`, without creating `list_CN_Android/list_CN_Android` paths.
- Starting the service rewrites `config.toml` from the current path mapping before launching Python, so stale bad paths are not reused.
- The log viewer is read-only, has scrollbars, font-size buttons, and avoids stealing scroll events from the parent view.
- The all-files-access button now opens the app-specific all-files-access page first, then falls back to the global page and app details. Some ROMs hide or gray out this permission for side-loaded/debug apps; use ADB appops if needed.

If the service still says master DB files are missing, place extracted NPPS4-readable SQLite master DB files under the resolved `db_root`, not raw CDN ZIPs.
