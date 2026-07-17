#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import os
import sqlite3
import sys
import tempfile
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYROOT = ROOT / "app/src/main/python"
errors: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# Exact banner contract established by the supplied CN client/honoka source and
# the user's old screenshots.
banner = read("app/src/main/python/npps4/game/banner.py")
require('"assets/image/webview/wv_ba_01.png"\n                if capabilities.profile == "cn"' in banner,
        "CN type-2 banner does not use exact unprefixed wv_ba_01")
require('"assets/image/secretbox/icon/s_ba_1718_1.png"\n                if capabilities.profile == "cn"' not in banner,
        "type-1 scouting asset is still misused as CN type-2 WebView banner")
require('webview_url=("/manga" if capabilities.profile == "cn" else "/")' in banner,
        "CN manga WebView route is not connected to the home card")

# CN resource namespace must override UI language.
secretbox_source = read("app/src/main/python/npps4/system/secretbox.py")
secretbox_tree = ast.parse(secretbox_source)
secretbox_func = next(n for n in secretbox_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_determine_en_path")
ns = {"idol": types.SimpleNamespace(BasicSchoolIdolContext=object), "config": types.SimpleNamespace(is_cn_compat=lambda: True)}
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias("annotations")], level=0), secretbox_func], type_ignores=[])), "secretbox-test", "exec"), ns)
ctx = types.SimpleNamespace(is_lang_jp=lambda: False)
require(ns["_determine_en_path"](ctx, "assets/image/secretbox/title/title_1.png", "") == "assets/image/secretbox/title/title_1.png",
        "CN English UI still gets en/ secretbox paths")
ns["config"].is_cn_compat = lambda: False
require(ns["_determine_en_path"](ctx, "assets/x.png", "") == "en/assets/x.png",
        "standard English path behavior was broken")

# Execute the actual raw ZIP resolver definitions with lightweight dependency
# stubs, then prove exact CN bytes and update precedence.
cn_source = read("app/src/main/python/npps4/download/cn_archive.py")
cn_tree = ast.parse(cn_source)
selected = [ast.ImportFrom(module="__future__", names=[ast.alias("annotations")], level=0)]
want_classes = {"_Package", "_RawArchiveMember"}
want_funcs = {
    "_normalize_raw_path", "_cn_native_only", "_raw_package_priority",
    "_lookup_cn_raw_many_sync", "_raw_cache_path", "_materialize_cn_raw_sync",
}
want_assigns = {"_CN_NATIVE_ONLY_PREFIXES", "_RAW_LOOKUP_CACHE", "_RAW_LOOKUP_LOCK", "_RAW_STATS"}
for node in cn_tree.body:
    if isinstance(node, ast.ClassDef) and node.name in want_classes:
        selected.append(node)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in want_funcs:
        selected.append(node)
    elif isinstance(node, (ast.Assign, ast.AnnAssign)):
        names: set[str] = set()
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
        if names & want_assigns:
            selected.append(node)

with tempfile.TemporaryDirectory() as td:
    troot = Path(td)
    base_zip = troot / "1_1_1.zip"
    update_zip = troot / "99_0_2.zip"
    target = "assets/image/secretbox/title/tx_title_1.texb"
    wrapped = "assets/image/secretbox/appeal/tx_appeal_2_2.texb"
    with zipfile.ZipFile(base_zip, "w") as zf:
        zf.writestr(target, b"old-cn")
    with zipfile.ZipFile(update_zip, "w") as zf:
        zf.writestr(target, b"new-cn")
        zf.writestr("top/" + wrapped, b"wrapped-cn")

    class Logging:
        WARNING = 30
        INFO = 20

    fake_platform = object()
    exec_ns = {
        "asyncio": __import__("asyncio"),
        "os": os,
        "shutil": __import__("shutil"),
        "threading": __import__("threading"),
        "zipfile": zipfile,
        "dataclass": __import__("dataclasses").dataclass,
        "idoltype": types.SimpleNamespace(PlatformType=object),
        "util": types.SimpleNamespace(logging=Logging, log=lambda *a, **k: None),
        "config": types.SimpleNamespace(get_data_directory=lambda: str(troot / "data")),
        "_config": types.SimpleNamespace(update_package_type=99),
        "_PLATFORM_MAP": {fake_platform: "Android"},
        "_PACKAGES": {},
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), "cn-raw-test", "exec"), exec_ns)
    Package = exec_ns["_Package"]
    exec_ns["_PACKAGES"][fake_platform] = [
        Package(fake_platform, 1, 1, 1, base_zip.name, str(base_zip), base_zip.stat().st_size),
        Package(fake_platform, 99, 0, 2, update_zip.name, str(update_zip), update_zip.stat().st_size),
    ]
    members = exec_ns["_lookup_cn_raw_many_sync"](fake_platform, [target, wrapped, "missing.bin"])
    require(members[target] is not None and Path(members[target].zip_path) == update_zip,
            "raw resolver did not prefer latest CN update ZIP")
    require(members[wrapped] is not None and members[wrapped].member_name == "top/" + wrapped,
            "unique top-level wrapper suffix was not resolved")
    out = exec_ns["_materialize_cn_raw_sync"](fake_platform, target)
    require(out is not None and Path(out).read_bytes() == b"new-cn",
            "raw resolver did not materialize exact CN bytes")
    require(exec_ns["_cn_native_only"](target), "secretbox namespace is not protected from GL fallback")
    require(exec_ns["_cn_native_only"]("assets/image/webview/wv_ba_01.png"), "WebView banner namespace is not protected")
    require(not exec_ns["_cn_native_only"]("assets/sound/optional/foo.acb"), "GL fallback was disabled globally instead of narrowly")

# Wrapper editability/config persistence/report wiring.
editor = read("app/src/main/java/moe/honoka/npps4wrapper/ConfigEditorActivity.kt")
fileops = read("app/src/main/java/moe/honoka/npps4wrapper/FileOps.kt")
main_activity = read("app/src/main/java/moe/honoka/npps4wrapper/MainActivity.kt")
bridge = read("app/src/main/java/moe/honoka/npps4wrapper/PythonBridge.kt")
require("requestFocusFromTouch()" in editor and "showSoftInput(this" in editor,
        "editor does not explicitly restore focus/IME")
require("while (ancestor != null)" in editor and "requestDisallowInterceptTouchEvent(true)" in editor,
        "editor gesture is not protected from all ancestor ScrollViews")
require("keyListener = TextKeyListener.getInstance()" in editor and "isCursorVisible = true" in editor,
        "editable subpages still lack a real key listener/cursor")
require("if (currentConfig.isBlank()" in fileops,
        "ensureTemplate still overwrites every existing config")
require('"museum_bridge_unlock_policy" to tomlString("normal")' in fileops and
        'upsertTomlValue(text, "download.cn_archive", key, value, false)' in fileops,
        "archive unlock policy is not preserved when Wrapper paths are synchronized")
require("生成并查看诊断报告" in main_activity and "generateDiagnosticReport" in bridge,
        "diagnostic report is not exposed in Wrapper UI")

# Bundled Museum bridge integrity.
bridge_root = PYROOT / "npps4/assets/cn_museum_bridge"
with sqlite3.connect(bridge_root / "museum.server.db") as conn:
    museum_count = int(conn.execute("SELECT COUNT(*) FROM museum_contents_m").fetchone()[0])
manifest = json.loads((bridge_root / "museum_bridge_manifest.json").read_text(encoding="utf-8"))
require(museum_count == 1360, f"merged Museum server DB has {museum_count}, expected 1360")
require(manifest.get("cn_original_count") == 16 and manifest.get("imported_count") == 1344 and manifest.get("merged_count") == 1360,
        "Museum bridge manifest counts are inconsistent")

# Run the actual user-visible report generator against a synthetic workspace.
sys.path.insert(0, str(PYROOT))
import android_wrapper  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    work = Path(td) / "work"
    archives = Path(td) / "archives"
    dbroot = work / "data/db_cn_honoka"
    archives.mkdir(parents=True)
    dbroot.mkdir(parents=True)
    with zipfile.ZipFile(archives / "99_0_1.zip", "w") as zf:
        zf.writestr("assets/image/webview/wv_ba_01.png", b"banner")
        zf.writestr("assets/image/secretbox/icon/s_ba_1_1.png", b"scout")
        zf.writestr("assets/image/secretbox/title/tx_title_1.texb", b"title")
        zf.writestr("assets/image/secretbox/appeal/tx_appeal_2_2.texb", b"appeal")
    work.mkdir(parents=True, exist_ok=True)
    cfg = work / "config.toml"
    cfg.write_text(android_wrapper.default_config(str(work), str(archives), str(dbroot)), encoding="utf-8")
    overlay = work / "data/cn_update_overlays"
    overlay.mkdir(parents=True)
    for name in ("museum.server.db", "museum_bridge_manifest.json", "archive_access_manifest.json"):
        (overlay / name).write_bytes((bridge_root / name).read_bytes())
    (overlay / "99_0_116.zip").write_bytes(b"test")
    main_db = work / "data/main.sqlite3"
    main_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(main_db) as conn:
        conn.execute("CREATE TABLE museum_unlock (id INTEGER PRIMARY KEY, user_id INTEGER, museum_contents_id INTEGER)")
        conn.executemany("INSERT INTO museum_unlock(user_id, museum_contents_id) VALUES(1, ?)", [(i,) for i in range(1, 17)])
    response = json.loads(android_wrapper.generate_diagnostic_report(str(work), str(cfg), str(archives), str(dbroot)))
    require(response.get("ok") is True and Path(response["path"]).is_file(), "diagnostic report file was not generated")
    report = Path(response["path"]).read_text(encoding="utf-8")
    require('"zip_count": 1' in report and '"unlock_policy": "normal"' in report,
            "diagnostic report basic JSON is malformed")
    require('"museum_unlock"' in report and '"1": 16' in report,
            "diagnostic report does not expose current per-user Museum unlock count")
    require('"assets/image/webview/wv_ba_01.png": {' in report,
            "diagnostic report does not find exact CN home banner asset")

# Version markers.
gradle = read("app/build.gradle")
build_info = read("app/src/main/python/npps4/build_info.py")
require("versionCode 431" in gradle and "versionName '0.4.31'" in gradle, "Android version was not advanced to 0.4.31")
require('BUILD_ID = "v4.49-cn-core-regression-fix"' in build_info, "v4.49 build marker missing")

if errors:
    print("v4.49 validation FAILED")
    for error in errors:
        print("-", error)
    raise SystemExit(1)
print("v4.49 validation OK")
print(f"Museum merged rows: {museum_count}")
print("CN banner/scouting raw ZIP resolver: exact bytes + update precedence PASS")
print("Wrapper editable config persistence + diagnostic report: PASS")
