# NPPS4 Android Wrapper v1.7 notes

This release fixes issues reported during on-device testing:

- Explicitly imports the Pydantic v1 compatibility shim before NPPS4 modules are imported, fixing `module 'pydantic' has no attribute 'AliasChoices'` during startup.
- Switches the UI to a Material 3 / Material You style using Material Components and dynamic colors when available.
- Removes the default Android action bar and applies system-bar insets, fixing status/title bar overlap in the main screen and text editor screen.
- Health-check and startup errors are now written persistently into the main screen status/log card rather than being shown only in transient Toasts.
- CN archives are now read directly from a public path: `/storage/emulated/0/NPPS4/list_CN_Android`.
- `99_0_115.zip` is no longer imported separately; put it in the same `list_CN_Android` folder as the other CN archive zips.
- Adds a button to open Android's "All files access" settings, which may be required for direct public-path access on Android 11+.
- Full backup now includes both the app-private workspace and the public `/storage/emulated/0/NPPS4` mapping directory.
