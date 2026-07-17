# NPPS4 Android Wrapper v2.3

This version removes runtime dependency on Material Components widgets from the programmatic UI.

Why:
- Some builds/devices still reported `ThemeEnforcement.checkMaterialTheme` when creating `MaterialCardView` even after switching the app theme.
- The wrapper now uses standard Android `Button`, `EditText`, `LinearLayout`, `TextView` and programmatic rounded backgrounds.
- Visual style remains card-based with fixed `#1769FF` blue, but no MaterialComponents theme enforcement can crash the main screen.

Unchanged:
- Python / Chaquopy settings.
- NPPS4 server code.
- Public path mapping (`/storage/emulated/0/NPPS4/list_CN_Android`).
- Backup policy: server state/config only, no CDN archives or master DB.
