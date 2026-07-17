#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
PYROOT = ROOT / "app/src/main/python"
sys.path.insert(0, str(PYROOT))

errors: list[str] = []
notes: list[str] = []


def require(value: bool, message: str) -> None:
    if not value:
        errors.append(message)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


banner = read("app/src/main/python/npps4/game/banner.py")
for asset in ("npps4_data_transfer.png", "npps4_manga.png"):
    require(asset in banner, f"missing CN banner asset reference: {asset}")
require(banner.count("banner_type=2") >= 3, "CN does not expose two type-2 WebView cards")
require(banner.count("back_side=False") >= 3, "CN banner still uses the crashing flip path")
require("/transfer?token=" in banner and '/manga"' in banner, "transfer/manga WebView URLs are missing")
require("banner_type=18" in banner, "global type-18 path was accidentally removed")

transfer = read("app/src/main/python/npps4/webview/transfer.py")
require('@app.core.get("/transfer"' in transfer, "GET /transfer route missing")
require('@app.core.post("/transfer"' in transfer, "POST /transfer route missing")
require("generate_passcode_sha1" in transfer and "transfer_sha1 = None" in transfer, "transfer page is not tied to real NPPS4 handover state")
require("from . import transfer" in read("app/src/main/python/npps4/webview/__init__.py"), "transfer route is not imported")
require((PYROOT / "templates/transfer.html").is_file(), "transfer template missing")
manga_template = read("app/src/main/python/templates/manga.html")
require('{{ define "common/manga.html" }}' not in manga_template and "{{ end }}" not in manga_template, "manga template still contains incompatible Go-template markers")

fileops = read("app/src/main/java/moe/honoka/npps4wrapper/FileOps.kt")
config_py = read("app/src/main/python/android_wrapper.py")
config_data = read("app/src/main/python/npps4/config/data.py")
for source, name in ((fileops, "FileOps"), (config_py, "android_wrapper"), (config_data, "config/data")):
    require("97.4.7" in source, f"{name} does not advertise 97.4.7")
    require("99_0_117.zip" in source, f"{name} does not configure 99_0_117.zip")
require('museum_bridge_unlock_policy = "all"' in fileops, "new CN config does not default Museum policy to all")
require('"museum_bridge_unlock_policy" to tomlString("all")' in fileops, "Wrapper profile sync does not preserve/add all policy")
require("pre-v450-cn-content.bak" in config_py, "existing CN config migration/backup missing")

cn_archive_source = read("app/src/main/python/npps4/download/cn_archive.py")
require('minimum_order = 117 if _same_cn_version(external_version, "97.4.6")' in cn_archive_source, "incremental 97.4.6 -> 97.4.7 filter missing")
museum_bridge_source = read("app/src/main/python/npps4/system/museum_bridge.py")
museum_source = read("app/src/main/python/npps4/system/museum.py")
require("in_(requested)" not in museum_bridge_source and "in_(valid)" not in museum_bridge_source, "Museum all-policy still risks SQLite's 999-bind limit")
require("in_(contents_id_list)" not in museum_source, "museum/info still risks SQLite's 999-bind limit")
for entry in (
    "assets/image/webview/npps4_data_transfer.png",
    "assets/image/webview/npps4_manga.png",
):
    require(entry in cn_archive_source, f"99_0_117 generator missing {entry}")

# Verify the actual bundled payload can be wrapped and decrypted as a 1360-row CN Museum DB.
from npps4.tools.cn_museum_bridge import build_update_zip
from npps4.tools import honky_file

asset_dir = PYROOT / "npps4/assets/cn_museum_bridge"
for name in ("museum.db_", "museum.server.db", "npps4_data_transfer.png", "npps4_manga.png"):
    require((asset_dir / name).is_file() and (asset_dir / name).stat().st_size > 0, f"bundled payload missing: {name}")

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    template = td / "99_0_113.zip"
    with zipfile.ZipFile(template, "w") as zf:
        zf.writestr("client_info.json", b"must be removed")
        zf.writestr("dummy.txt", b"template")
    output = td / "99_0_117.zip"
    extras = {
        "assets/image/webview/npps4_data_transfer.png": (asset_dir / "npps4_data_transfer.png").read_bytes(),
        "assets/image/webview/npps4_manga.png": (asset_dir / "npps4_manga.png").read_bytes(),
    }
    build_update_zip(template, (asset_dir / "museum.db_").read_bytes(), output, extra_entries=extras)
    with zipfile.ZipFile(output) as zf:
        names = {n.replace("\\", "/").lstrip("./") for n in zf.namelist()}
        require(zf.testzip() is None, "generated 99_0_117 failed ZIP CRC validation")
        require("client_info.json" not in names, "dangerous client_info survived 99_0_117 wrapping")
        required = {"db/museum/museum.db_", *extras}
        require(required.issubset(names), f"generated 99_0_117 missing entries: {sorted(required - names)}")
        encrypted_db = zf.read("db/museum/museum.db_")
    plain, _meta = honky_file.decrypt_v4(encrypted_db, "museum.db_", "cn")
    db = td / "museum.db"
    db.write_bytes(plain)
    with sqlite3.connect(db) as conn:
        rows = int(conn.execute("SELECT COUNT(*) FROM museum_contents_m").fetchone()[0])
    require(rows == 1360, f"bundled merged Museum row count is {rows}, expected 1360")
    notes.append(f"synthetic 99_0_117 size={output.stat().st_size} rows={rows}")

# Verify migration transforms the exact v4.49 diagnostic state.
import android_wrapper
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    cfg = td / "config.toml"
    cfg.write_text(
        '[download]\nbackend = "cn_archive"\n\n[download.cn_archive]\n'
        'client_version = "97.4.6"\n'
        'android_extra_update_packages = ["data/cn_update_overlays/99_0_116.zip"]\n'
        'museum_bridge_unlock_policy = "normal"\n\n[compat]\nregion = "cn"\n',
        encoding="utf-8",
    )
    android_wrapper.prepare_workspace(str(td), str(cfg), str(td / "archives"), str(td / "db"))
    migrated = cfg.read_text(encoding="utf-8")
    require('client_version = "97.4.7"' in migrated, "existing config was not migrated to 97.4.7")
    require("99_0_117.zip" in migrated and "99_0_116.zip" not in migrated, "existing config still points at 116")
    require('museum_bridge_unlock_policy = "all"' in migrated, "existing normal policy was not migrated to all")
    require((td / "config.toml.pre-v450-cn-content.bak").is_file(), "v4.50 config backup was not created")

# The runtime token helper uses NPPS4's existing itsdangerous serializer and
# project secret; this environment lacks the Android Cryptodome wheel, so keep
# this validation structural rather than pretending to import the full app.
token_source = read("app/src/main/python/npps4/system/webview_token.py")
for term in ("URLSafeTimedSerializer", "max_age", 'payload.get("purpose") != purpose', 'int(payload["user_id"])'):
    require(term in token_source, f"WebView token validation is incomplete: {term}")

# Version/build markers.
gradle = read("app/build.gradle")
require("versionCode 433" in gradle and "versionName '0.4.32'" in gradle, "Android version marker is not 433 / 0.4.32")
require('BUILD_ID = "v4.50-cn-banner-museum-fix"' in read("app/src/main/python/npps4/build_info.py"), "v4.50 build ID missing")

if errors:
    print("v4.50 validation FAILED")
    for item in errors:
        print("-", item)
    raise SystemExit(1)

print("v4.50 validation PASSED")
for item in notes:
    print("-", item)
print("- two CN non-flipping type-2 WebView cards")
print("- transfer page writes real handover state")
print("- 97.4.6 clients receive the 117 incremental stage")
print("- Museum payload decrypts to 1360 rows")
