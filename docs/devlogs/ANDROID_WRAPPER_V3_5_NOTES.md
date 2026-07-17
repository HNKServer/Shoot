# Android Wrapper v3.5

Fixes Alembic path extraction under Chaquopy. v3.4 still assumed `npps4/alembic/env.py` could be copied by walking importlib resources, but Chaquopy does not always expose package trees as normal filesystem paths. v3.5 embeds the whole Alembic directory as a base64 zip payload and extracts it to the real workspace before migrations.

No changes to CDN archive policy: CDN ZIPs are read-only and not edited.
