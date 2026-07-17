# NPPS4 Android Wrapper v2.1

- Removed automatic periodic status polling from app startup.
- Removed automatic notification permission request on app startup; it now runs only when starting the server.
- Fixed background status checks so view text is read on the UI thread before launching background work.
- Added fallback crash UI if MainActivity initialization itself fails.
- Fixed the accidental duplicate `Thread {` block in `updateStatus`.

This version is intended to make the main UI stay visible even when Python/NPPS4 or device-specific UI behavior fails.
