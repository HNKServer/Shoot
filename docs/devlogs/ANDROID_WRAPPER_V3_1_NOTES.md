# NPPS4 Android Wrapper v3.1

This version corrects the master-data assumption:

- Server account/progress DB is still created and managed by NPPS4 (`data/main.sqlite3`).
- Client CDN ZIPs remain read-only and are not edited or scanned as the required default master DB source.
- `99_0_115.zip` is read as part of the CDN mirror only; edit it externally and place it in `list_CN_Android`.
- A bundled honoka-chan `assets/main.db` is included as `npps4/assets/honoka_main.db`.
- The wrapper can generate NPPS4-readable split master DBs under `data/db_cn_honoka` from that bundled honoka database.
- All-files access is back to targetSdk 35 + MANAGE_EXTERNAL_STORAGE.

The generated split DBs are a conservative runnable CN baseline: NPPS4 schema is created, matching honoka rows are copied, missing NPPS4-only tables remain empty. This is not a perfect official global DB replacement, but it removes the incorrect requirement to manually provide split master DBs or search thousands of CDN ZIPs before the service can start.
