#!/usr/bin/env python3
from pathlib import Path
import ast, sqlite3, sys

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
pyroot = root / "app/src/main/python"
npps4 = pyroot / "npps4"
errors: list[str] = []

def req(value: bool, message: str) -> None:
    if not value:
        errors.append(message)

for path in pyroot.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

# The forced GL-to-CN Museum implementation must no longer exist as code/assets.
for rel in (
    "npps4/system/museum_bridge.py",
    "npps4/tools/cn_museum_bridge.py",
    "npps4/assets/cn_museum_bridge",
):
    req(not (pyroot / rel).exists(), f"obsolete Museum transplant path remains: {rel}")
for rel in ("tools/cn_museum_bridge_toolkit",):
    req(not (root / rel).exists(), f"obsolete Museum toolkit remains: {rel}")

for rel in ("config.sample.toml", "config.cn-local.sample.toml"):
    text = (pyroot / rel).read_text(encoding="utf-8")
    for token in ("museum_bridge_unlock_policy", "museum_bridge_manifest", "museum_server_db"):
        req(token not in text, f"{rel} still exposes obsolete option {token}")
    req("android_extra_update_packages = []" in text, f"{rel} does not keep extra CN update packages empty")

cn = (npps4 / "download/cn_archive.py").read_text(encoding="utf-8")
req("_bundled_banner_alias" in cn and ".imag" in cn, "banner .imag alias missing")
req("sizes[file] = os.path.getsize(bundled)" in cn, "download/getUrl does not report bundled banner size")
req("npps4.assets.cn_home_banner" in cn, "dedicated banner asset package missing")
req("_materialize_content_overlay_package" not in cn, "normal content-package mutation remains active")
req("_CLIENT_CONTENT_READY_MARKER" not in cn, "Museum readiness gate remains active")
req("_cleanup_obsolete_museum_transplant_artifacts" in cn, "old generated Museum files are not cleaned on upgrade")
req("build_update_zip" not in cn, "synthetic Museum update-package generator remains active")

banner = (npps4 / "game/banner.py").read_text(encoding="utf-8")
req("npps4_data_transfer.png" in banner and "npps4_manga.png" in banner, "home WebView banners missing")
req("back_side=True" in banner, "manga back-side banner missing")
req("_cn_secretbox_banners" in banner, "front scouting carousel missing")

museum = (npps4 / "system/museum.py").read_text(encoding="utf-8")
req("museum_bridge:%" in museum and "row_by_id" in museum, "legacy grants are not pruned to native IDs")
req("museum_bridge_unlock_policy" not in museum, "runtime still reads the abandoned all/archive Museum policy")

# The CN generated master is the native 16-entry catalogue, not a merged 1360-row DB.
db = npps4 / "assets/honoka_main.db"
req(db.is_file(), "native CN master DB missing")
if db.is_file():
    with sqlite3.connect(db) as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM museum_contents_m").fetchone()[0])
    req(count == 16, f"native CN Museum count is {count}, expected 16")

for name in ("npps4_data_transfer.png", "npps4_manga.png"):
    req((npps4 / "assets/cn_home_banner" / name).is_file(), f"banner asset missing: {name}")

if errors:
    print("v4.55 validation FAILED")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)
print("v4.55 validation OK")
