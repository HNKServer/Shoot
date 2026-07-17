# Android Wrapper v3.6

- Removes Android runtime Alembic migration.
- Initializes the mutable server/account database with SQLAlchemy `Base.metadata.create_all()` in `android_main.py`.
- Stops relying on real filesystem paths for `npps4/alembic/env.py` under Chaquopy/AssetFinder.
- Keeps honoka-derived split master DB generation unchanged.
- Keeps CDN ZIPs read-only and independent from server progress DB.
- Removes `alembic[tz]` from Android-only Python requirements.
