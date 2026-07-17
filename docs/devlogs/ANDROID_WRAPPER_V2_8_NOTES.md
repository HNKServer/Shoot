# NPPS4 Android Wrapper v2.8

## Changes

- Treat public CN archive ZIPs as read-only. The wrapper no longer writes README/marker files into the selected public CDN directory.
- Avoid startup crashes caused by trying to create or write under `/storage/emulated/0/...` without `MANAGE_EXTERNAL_STORAGE`.
- Python workspace preparation no longer creates or modifies the public archive directory.
- Added an app-specific direct-read data directory option:
  `/storage/emulated/0/Android/data/moe.honoka.npps4wrapper/files/public_cdn/`.
  Use this if the ROM hides or disables the "All files access" switch.
- `startForeground` is now caught and logged so notification/foreground-service permission issues do not kill the whole app.
- UI copy now explicitly states that normal CDN ZIPs, including `99_0_115.zip`, are not edited by the wrapper.

## Important storage note

Directly serving a public path such as `/storage/emulated/0/LoveLive/list_CN_Android` requires ordinary Linux filesystem access. On Android 11+, this usually requires `MANAGE_EXTERNAL_STORAGE`; SAF directory selection does not automatically make that path readable to Chaquopy/Python as a normal file path.

If the ROM hides or greys out the all-files access switch, use either:

```bash
adb shell appops set moe.honoka.npps4wrapper MANAGE_EXTERNAL_STORAGE allow
```

or move the CDN directory to the app-specific direct-read directory created by the wrapper.
