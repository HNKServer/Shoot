#!/usr/bin/env python3
from __future__ import annotations

import ast
import asyncio
import hashlib
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
pyroot = root / "app/src/main/python"
npps4 = pyroot / "npps4"
errors: list[str] = []


def req(value: bool, message: str) -> None:
    if not value:
        errors.append(message)


for path in pyroot.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

banner = (npps4 / "game/banner.py").read_text(encoding="utf-8")
archive = (npps4 / "download/cn_archive.py").read_text(encoding="utf-8")
config_data = (npps4 / "config/data.py").read_text(encoding="utf-8")
museum = (npps4 / "system/museum.py").read_text(encoding="utf-8")

# Front uses a CN-known catalogue key. Back matches honoka-chan exactly.
for token in (
    'asset_path="assets/image/secretbox/icon/s_ba_1718_1.png"',
    'asset_path="assets/image/webview/wv_ba_01.png"',
    'webview_url=f"/transfer?t={token}"',
    'webview_url="/manga"',
    'banner_id=200001',
    'back_side=True',
):
    req(token in banner, f"banner contract missing {token}")
req('"assets/image/secretbox/icon/s_ba_1718_1.png": "npps4_data_transfer.png"' in archive,
    "transfer thumbnail is not mapped to a CN-known identifier")
req('"assets/image/webview/wv_ba_01.png": "npps4_manga.png"' in archive,
    "manga thumbnail does not use the exact honoka path")
req('path.endswith(".imag")' in archive, "CN .imag alias handling missing")
req('npps4_data_transfer.png' not in banner and 'npps4_manga.png' not in banner,
    "banner response still exposes arbitrary asset identifiers")

# Native Museum unlock switch exists, but no GL catalogue transplant returns.
req('museum_unlock_policy' in config_data, "native Museum unlock config missing")
req('museum_bridge_unlock_policy' in config_data, "old config-name migration alias missing")
req('_native_unlock_policy' in museum and 'sorted(row_by_id)' in museum,
    "native all-unlock logic missing")
for rel in (
    "npps4/system/museum_bridge.py",
    "npps4/tools/cn_museum_bridge.py",
    "npps4/assets/cn_museum_bridge",
):
    req(not (pyroot / rel).exists(), f"obsolete GL Museum transplant remains: {rel}")

native_db = npps4 / "assets/honoka_main.db"
req(native_db.is_file(), "native CN master missing")
if native_db.is_file():
    with sqlite3.connect(native_db) as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM museum_contents_m").fetchone()[0])
    req(count == 16, f"native Museum has {count} rows, expected 16")

# Bundled source images are valid and distinct.
images = []
for name in ("npps4_data_transfer.png", "npps4_manga.png"):
    file = npps4 / "assets/cn_home_banner" / name
    req(file.is_file() and file.stat().st_size > 1000, f"missing/truncated banner image {name}")
    if file.is_file():
        data = file.read_bytes()
        req(data.startswith(b"\x89PNG\r\n\x1a\n"), f"{name} is not PNG")
        images.append(hashlib.sha256(data).hexdigest())
req(len(images) == 2 and images[0] != images[1], "banner images are unexpectedly identical")

# Android version/build identity.
gradle = (root / "app/build.gradle").read_text(encoding="utf-8")
build = (npps4 / "build_info.py").read_text(encoding="utf-8")
req("versionCode 438" in gradle and "versionName '0.4.36'" in gradle, "Android version not bumped")
req("v4.56-cn-known-banner-assets-native-museum-unlock" in build, "build ID not updated")

if errors:
    print("v4.56 validation FAILED")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)
print("v4.56 validation OK")
