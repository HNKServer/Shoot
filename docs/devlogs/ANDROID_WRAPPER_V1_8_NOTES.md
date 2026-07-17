# NPPS4 Android Wrapper v1.8 notes

Changes from v1.7:

- Backups now include only server-side mutable state: config, account/progress database files, `server_data.json`, `external/` scripts and server key. They intentionally exclude `/storage/emulated/0/NPPS4/list_CN_Android`, `/storage/emulated/0/NPPS4/db`, ZIP archives, beatmaps and exports.
- App theme color is fixed to `#1769FF` while keeping the Material 3 / Material You component style. Dynamic color override is disabled so the requested blue remains stable.
- Text editor screens now have a top-left back button and still keep the bottom return button.
