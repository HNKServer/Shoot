# NPPS4 Android Wrapper v2.5 notes

This release focuses on the issues found during on-device testing:

- The fixed top bar is now the only in-app title bar and displays `LoveArrowShoot!` in #1769FF at a larger size.
- The app label/activity title is also changed to `LoveArrowShoot!` to avoid stale system action bar text on ROMs which ignore NoActionBar.
- The main status card now shows a concise server state instead of dumping long tracebacks into the page.
- Full errors are written to `npps4-wrapper-crash.log` and can be opened from the UI.
- Public path mapping is restored with an editable public root path and an Android folder picker. It records the path and rewrites config without copying CDN data.
- The all-files-access button opens global settings first, with app-specific settings as fallback.
- The Pydantic v1 compatibility shim is now imported as `android_pydantic_compat` instead of relying on `sitecustomize`, which Android/host Python may not load from the app bundle.
- Startup preflight now checks `effort.db_` and verifies key master DB tables, so wrong/empty DB folders fail with a clear message.
