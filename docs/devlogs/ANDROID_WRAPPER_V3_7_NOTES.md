# NPPS4 Android Wrapper v3.7

This release replaces the v3.6 `create_all()` shortcut with an Android-safe schema initializer for the mutable server database.

## What changed

- Android still does **not** run Alembic script files at runtime, because Chaquopy/APK modules are not guaranteed to be normal filesystem files.
- Instead, `npps4/android_schema.py` now creates/reconciles the current NPPS4 mutable DB schema from SQLAlchemy metadata and stamps `alembic_version` with the current head revision (`cn_accessories`).
- Missing tables, indexes and safe missing columns are added on older Android databases.
- Unsafe upgrades, such as adding a required non-null column to a non-empty existing table without a default, now fail loudly instead of silently corrupting saved progress.
- The read-only honoka/CN master DB generation is unchanged.

## Database responsibility boundary

- `data/main.sqlite3`: mutable server account/progress DB, generated and managed by NPPS4/Wrapper.
- `data/db_cn_honoka/*.db_`: read-only master data generated from embedded `honoka_main.db`.
- CDN ZIP directory: read-only file source for clients; Wrapper does not edit ordinary ZIP files or `99_0_115.zip`.
