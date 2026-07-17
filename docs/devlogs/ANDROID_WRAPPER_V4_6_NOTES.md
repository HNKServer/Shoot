# Android Wrapper v4.6 - CN/Honoka master DB schema repair

This version fixes a login-time crash seen after the Android Python server was
already able to start successfully:

```text
(sqlite3.OperationalError) no such column: live_setting_m.release_tag
```

Root cause:

- The CN/Honoka split master DB files in `data/db_cn_honoka` persist across APK
  upgrades.
- Earlier Android wrapper builds could generate or accept split master DBs whose
  physical SQLite tables did not include NPPS4's `MaybeEncrypted` columns:
  `release_tag` and `_encryption_release_id`.
- Newer NPPS4 ORM models still select those columns, so `/v1/account/login`
  returned a server-side code 31 error even though the server socket was up.

Fix:

- `android_wrapper.py` now repairs existing split master DB schemas during
  startup, before preflight and before the FastAPI server handles requests.
- Missing tables and safe missing columns are reconciled from the embedded
  schema.
- Nullable `release_tag` and `_encryption_release_id` columns are added to
  persisted master tables when absent.

This does not delete user progress and does not require clearing
`data/main.sqlite3`. If an old `data/db_cn_honoka` directory already exists, it
will be repaired in place on the next server start.
