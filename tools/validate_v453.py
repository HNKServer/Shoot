#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYROOT = ROOT / "app/src/main/python"
BRIDGE = PYROOT / "npps4/assets/cn_museum_bridge"


def ok(message: str) -> None:
    print(f"[OK] {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    ok(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_honky():
    path = ROOT / "tools/cn_museum_bridge_toolkit/honky_file.py"
    spec = importlib.util.spec_from_file_location("v453_honky", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check_assets_and_museum() -> None:
    from PIL import Image

    transfer = BRIDGE / "npps4_data_transfer.png"
    manga = BRIDGE / "npps4_manga.png"
    require(sha256(transfer) == "b0e7b888d7723b368a2ee16cec99e3a0d9dfaafe63b9cf4213447a710bb9c8e3", "PS transfer image is preserved byte-for-byte")
    with Image.open(transfer) as image:
        require(image.mode == "RGBA" and image.size == (1914, 616), "transfer image is RGBA 1914x616")
        corners = [image.getpixel((0, 0))[3], image.getpixel((image.width - 1, 0))[3], image.getpixel((0, image.height - 1))[3], image.getpixel((image.width - 1, image.height - 1))[3]]
        require(max(corners) == 0, "transfer image has transparent outer corners")
    with Image.open(manga) as image:
        require(image.width / image.height > 2.4, "manga thumbnail has home-banner aspect ratio")

    honky = load_honky()
    encrypted_db = (BRIDGE / "museum.db_").read_bytes()
    plain_db, meta = honky.decrypt_v4(encrypted_db, "museum.db_", "cn")
    require(meta.region == "cn", "Museum client database uses CN Honky v4")
    with tempfile.NamedTemporaryFile(suffix=".sqlite3") as fh:
        fh.write(plain_db)
        fh.flush()
        conn = sqlite3.connect(fh.name)
        count = conn.execute("SELECT COUNT(*) FROM museum_contents_m").fetchone()[0]
        conn.close()
    require(count == 1360, "client Museum catalogue contains 1360 rows")

    conn = sqlite3.connect(BRIDGE / "museum.server.db")
    count = conn.execute("SELECT COUNT(*) FROM museum_contents_m").fetchone()[0]
    conn.close()
    require(count == 1360, "server Museum catalogue contains 1360 rows")

    museum_lua = (BRIDGE / "museum_base_gl_cn.lua").read_bytes()
    plain_lua, lua_meta = honky.decrypt_v4(museum_lua, "base.lua", "cn")
    require(lua_meta.region == "cn", "WW Museum Lua is re-encrypted for CN")
    for needle in (b"micro_download", b"downloadIfNotExist", b".flsh"):
        require(needle in plain_lua, f"Museum Lua contains {needle.decode()} support")


def check_source_contracts() -> None:
    banner = (PYROOT / "npps4/game/banner.py").read_text(encoding="utf-8")
    archive = (PYROOT / "npps4/download/cn_archive.py").read_text(encoding="utf-8")
    wrapper = (PYROOT / "android_wrapper.py").read_text(encoding="utf-8")
    fileops = (ROOT / "app/src/main/java/moe/honoka/npps4wrapper/FileOps.kt").read_text(encoding="utf-8")
    gradle = (ROOT / "app/build.gradle").read_text(encoding="utf-8")

    require("banner_type=1" in banner and "_cn_secretbox_banners" in banner, "front carousel derives type-1 pages from secretbox data")
    require('back_side=True' in banner and 'webview_url="/manga"' in banner, "manga is the back-side WebView item")
    require("BackgroundTask(_mark_content_package_served" in archive, "Museum readiness is marked after ZIP response streaming")
    require("_CLIENT_CONTENT_REPLACEMENTS" in archive and "_CLIENT_CONTENT_ADDITIONS" in archive, "normal content-package overlay is enabled")
    require('android_extra_update_packages = []' in wrapper and '99_0_116.zip' not in fileops, "default Wrapper config does not add 116/117")
    require("versionCode 435" in gradle and "versionName '0.4.33'" in gradle, "Android version is 0.4.33 (435)")

    data = json.loads((PYROOT / "npps4/server_data.json").read_text(encoding="utf-8"))
    assets: list[str] = []
    ids: list[int] = []
    for item in data["secretbox_data"]:
        asset = str(item.get("menu_asset") or "")
        if not asset or asset in assets:
            continue
        assets.append(asset)
        value = 0
        for ch in item["id_string"]:
            value = (31 * value + ord(ch)) & 0xFFFFFFFF
        ids.append(value - 0x100000000 if value & 0x80000000 else value)
    require(len(assets) >= 8 and len(ids) == len(assets), "server_data exposes at least 8 unique scouting home banners")


def install_crypto_stubs() -> None:
    class DummyKey:
        n = 1
        e = 65537
        def publickey(self):
            return self

    def module(name: str, **attrs):
        value = types.ModuleType(name)
        for key, item in attrs.items():
            setattr(value, key, item)
        sys.modules[name] = value
        return value

    crypto = module("Cryptodome")
    cipher = module("Cryptodome.Cipher")
    hashes = module("Cryptodome.Hash")
    util = module("Cryptodome.Util")
    signature = module("Cryptodome.Signature")
    public_key = module("Cryptodome.PublicKey")
    protocol = module("Cryptodome.Protocol")
    crypto.Cipher, crypto.Hash, crypto.Util = cipher, hashes, util
    crypto.Signature, crypto.PublicKey, crypto.Protocol = signature, public_key, protocol
    rsa = module("Cryptodome.PublicKey.RSA", import_key=lambda *_a, **_k: DummyKey(), RsaKey=DummyKey)
    public_key.RSA = rsa
    for name in ("AES", "PKCS1_v1_5", "DES3"):
        child = module(
            f"Cryptodome.Cipher.{name}",
            new=lambda *_a, **_k: types.SimpleNamespace(decrypt=lambda *_a, **_k: b"", encrypt=lambda value: value),
            MODE_CBC=2,
        )
        setattr(cipher, name, child)
    class DummyHash:
        def update(self, *_a):
            return None
    for name in ("SHA1", "SHA256"):
        child = module(f"Cryptodome.Hash.{name}", new=lambda *_a, **_k: DummyHash())
        setattr(hashes, name, child)
    util.Padding = module("Cryptodome.Util.Padding", pad=lambda value, *_a, **_k: value, unpad=lambda value, *_a, **_k: value)
    signature.pkcs1_15 = module("Cryptodome.Signature.pkcs1_15", new=lambda *_a, **_k: types.SimpleNamespace(sign=lambda _value: b"x", verify=lambda *_a: None))
    protocol.KDF = module("Cryptodome.Protocol.KDF", PBKDF2=lambda *_a, **_k: b"0" * 32)


def check_synthetic_package_overlay() -> None:
    with tempfile.TemporaryDirectory(prefix="npps4-v453-") as tmp_name:
        tmp = Path(tmp_name)
        archives = tmp / "archives"
        archives.mkdir()
        (tmp / "data").mkdir()
        shutil.copy2(PYROOT / "default_server_key.pem", tmp / "default_server_key.pem")
        shutil.copy2(PYROOT / "npps4/server_data.json", tmp / "server_data.json")
        shutil.copytree(PYROOT / "static", tmp / "static")
        shutil.copytree(PYROOT / "templates", tmp / "templates")
        with zipfile.ZipFile(archives / "0_0_1.zip", "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("db/museum/museum.db_", b"OLD_DB")
            archive.writestr("common/model/museum/base.lua", b"OLD_LUA")
        with zipfile.ZipFile(archives / "4_0_94.zip", "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("assets/image/secretbox/title/tx_title_1.texb", b"CARRIER")
        with zipfile.ZipFile(archives / "99_0_1.zip", "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("config/client_info.json", b"UNCHANGED")
            # Even if the same paths exist in a 99 package, the overlay must
            # attach to ordinary full-data packages so a later stage cannot
            # overwrite it.
            archive.writestr("db/museum/museum.db_", b"UPDATE_STAGE_DB")
            archive.writestr("common/model/museum/base.lua", b"UPDATE_STAGE_LUA")
        (tmp / "config.toml").write_text(
            f'''[main]\ndata_directory = "data"\nserver_private_key = "default_server_key.pem"\nserver_data = "server_data.json"\n[download]\nbackend = "cn_archive"\nsend_patched_server_info = false\n[download.cn_archive]\nandroid_archives = "{archives.as_posix()}"\napplication_version = "9.7.1"\nclient_version = "97.4.6"\nupdate_package_type = 99\nserver_info_override = ""\nandroid_server_info_override = ""\ngl_overlay_enabled = false\nandroid_extra_update_packages = []\nmuseum_server_db = "data/museum.server.db"\nmuseum_bridge_manifest = "data/museum_bridge_manifest.json"\narchive_access_manifest = "data/archive_access_manifest.json"\nmuseum_bridge_unlock_policy = "all"\n[compat]\nregion = "cn"\ncn_wrappers = true\n''',
            encoding="utf-8",
        )
        os.environ["NPPS4_ROOT_DIR"] = str(tmp)
        os.environ["NPPS4_CONFIG"] = str(tmp / "config.toml")
        sys.path.insert(0, str(PYROOT))
        install_crypto_stubs()
        from npps4.download import cn_archive
        from npps4 import idoltype
        cn_archive.initialize()
        packages = cn_archive._PACKAGES[idoltype.PlatformType.Android]
        by_name = {package.filename: package for package in packages}
        museum = cn_archive._materialize_content_overlay_package(by_name["0_0_1.zip"])
        banner = cn_archive._materialize_content_overlay_package(by_name["4_0_94.zip"])
        with zipfile.ZipFile(museum.local_path) as archive:
            require(archive.read("db/museum/museum.db_") == (BRIDGE / "museum.db_").read_bytes(), "normal package replaces Museum DB")
            require(archive.read("common/model/museum/base.lua") == (BRIDGE / "museum_base_gl_cn.lua").read_bytes(), "normal package replaces Museum Lua")
        with zipfile.ZipFile(banner.local_path) as archive:
            require(archive.read("assets/image/webview/npps4_data_transfer.png") == (BRIDGE / "npps4_data_transfer.png").read_bytes(), "normal package carries transfer thumbnail")
            require(archive.read("assets/image/webview/npps4_manga.png") == (BRIDGE / "npps4_manga.png").read_bytes(), "normal package carries manga thumbnail")
        with zipfile.ZipFile(archives / "99_0_1.zip") as archive:
            require(archive.read("config/client_info.json") == b"UNCHANGED", "existing 99 package remains untouched")
            require(archive.read("db/museum/museum.db_") == b"UPDATE_STAGE_DB", "Museum overlay is not attached to type-99 package")
        require(not cn_archive.client_museum_catalog_ready(), "1360 catalogue is gated before package response completes")
        cn_archive._mark_content_package_served(museum)
        require(cn_archive.client_museum_catalog_ready(), "1360 catalogue opens after Museum package response completes")


def main() -> int:
    check_assets_and_museum()
    check_source_contracts()
    check_synthetic_package_overlay()
    subprocess.run([sys.executable, "-m", "compileall", "-q", str(PYROOT)], check=True)
    ok("Python compileall")
    print("v4.53 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
