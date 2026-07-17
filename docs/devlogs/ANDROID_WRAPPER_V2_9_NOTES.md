# v2.9 storage permission fix

This version changes Android `targetSdk` from 35 to 29 and keeps `requestLegacyExternalStorage=true` so the wrapper can directly read a user-managed public CDN folder on Android 11+ in the same way older wrapper apps do.

It also adds a runtime READ/WRITE external storage permission button. MANAGE_EXTERNAL_STORAGE remains declared as a fallback, but the app no longer depends on the greyed-out settings switch.

CDN ZIPs remain read-only. The wrapper only extracts small master DB files into the app workspace and stores mutable server account/progress data there.
