# CN Museum bridge toolkit (v4.45)

Build a CN 9.7.1-compatible Museum DB from the supplied CN and community/GL
APKs. CN table layout and overlapping CN rows win; GL-only content rows are
added and re-encrypted with the original CN Honky metadata.

```bash
python cn_museum_bridge.py \
  --cn-apk LoveLive_9.7.1.apk \
  --gl-apk lovelive-community.apk \
  --output-dir museum-build \
  --archive-dir list_CN_Android \
  --server-data npps4/server_data.json
```

v4.45 recursively scans every reward section in `server_data.json`. The
supplied data contains 78 real Museum routes: 77 achievement rewards and
Museum ID 1698 in `sticker_shop`. `archive` therefore grants the 1282 merged
rows with no route in the preserved source/data; it no longer uses v4.44's
achievement-only/imported-only estimate.

Install or configure:

```toml
[download.cn_archive]
android_extra_update_packages = ["data/cn_update_overlays/99_0_116.zip"]
museum_server_db = "data/cn_update_overlays/museum.server.db"
museum_bridge_manifest = "data/cn_update_overlays/museum_bridge_manifest.json"
museum_bridge_unlock_policy = "normal" # normal | archive | all
archive_access_manifest = "data/cn_update_overlays/archive_access_manifest.json"
```

`archive_access_audit.py` in the parent `tools` directory produces the static
route manifest used for story, Live and Album catalog policies.
