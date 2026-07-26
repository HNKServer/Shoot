#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any


class Report:
    def __init__(self):
        self.results: list[dict[str, Any]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS" if ok else "FAIL") + ": " + name + (f" — {detail}" if detail else ""))

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r["ok"])

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r["ok"])


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def python_files(root: Path):
    yield from root.rglob("*.py")


def relative_hashes(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        out[p.relative_to(root).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def extract_function(path: Path, name: str, namespace: dict[str, Any]):
    tree = ast.parse(read(path), filename=str(path))
    fn = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    module = ast.Module(body=[fn], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[name]


class Field:
    def __init__(self, name: str):
        self.name = name

    def __gt__(self, other): return (">", self.name, other)
    def __lt__(self, other): return ("<", self.name, other)


class Query:
    def __init__(self, field):
        self.field = field
        self.where_args = ()

    def where(self, *args):
        self.where_args = args
        return self


class FakeSqlAlchemy:
    @staticmethod
    def select(field):
        return Query(field)


class FakeScalarResult:
    def __init__(self, values): self.values = list(values)
    def scalars(self): return list(self.values)


class FakeLookupDb:
    def __init__(self, values_by_field): self.values_by_field = values_by_field
    async def execute(self, query):
        return FakeScalarResult(self.values_by_field.get(query.field.name, []))


class FakeMainDb:
    def __init__(self): self.flushes = 0
    async def flush(self): self.flushes += 1


async def validate_serial_function(path: Path, report: Report):
    inventory = {
        "items": {10: 2},
        "recovery": {20: 1},
        "exchange": {30: 5},
        "sis": {40: 3},
        "supporters": {50: 4},
    }
    adds = {k: [] for k in inventory}

    async def get_item_count(ctx, user, item_id): return inventory["items"].get(item_id, 0)
    async def add_item(ctx, user, item_id, amount):
        inventory["items"][item_id] = inventory["items"].get(item_id, 0) + amount
        adds["items"].append((item_id, amount))
    async def get_recovery(ctx, user, item_id):
        amount = inventory["recovery"].get(item_id)
        return None if amount is None else SimpleNamespace(amount=amount)
    async def add_recovery(ctx, user, item_id, amount):
        inventory["recovery"][item_id] = inventory["recovery"].get(item_id, 0) + amount
        adds["recovery"].append((item_id, amount))
    async def get_exchange(ctx, user, item_id): return inventory["exchange"].get(item_id, 0)
    async def add_exchange(ctx, user, item_id, amount):
        inventory["exchange"][item_id] = inventory["exchange"].get(item_id, 0) + amount
        adds["exchange"].append((item_id, amount))
    async def get_sis(ctx, user, item_id):
        amount = inventory["sis"].get(item_id)
        return None if amount is None else SimpleNamespace(amount=amount)
    async def add_sis(ctx, user, item_id, amount):
        inventory["sis"][item_id] = inventory["sis"].get(item_id, 0) + amount
        adds["sis"].append((item_id, amount))
    async def get_supporter(ctx, user, item_id):
        amount = inventory["supporters"].get(item_id)
        return None if amount is None else SimpleNamespace(amount=amount)
    async def add_supporter(ctx, user, item_id, amount):
        inventory["supporters"][item_id] = inventory["supporters"].get(item_id, 0) + amount
        adds["supporters"].append((item_id, amount))

    def current_lp(user): return user._lp
    def add_lp(user, amount): user._lp += amount

    ns = {
        "sqlalchemy": FakeSqlAlchemy,
        "idol": SimpleNamespace(BasicSchoolIdolContext=object),
        "main": SimpleNamespace(User=object),
        "item_db": SimpleNamespace(KGItem=SimpleNamespace(item_id=Field("kg_item")), RecoveryItem=SimpleNamespace(recovery_item_id=Field("recovery_item"))),
        "exchange_db": SimpleNamespace(ExchangePoint=SimpleNamespace(exchange_point_id=Field("exchange_point"))),
        "unit_db": SimpleNamespace(RemovableSkill=SimpleNamespace(unit_removable_skill_id=Field("sis"))),
        "item": SimpleNamespace(get_item_count=get_item_count, add_item=add_item, get_recovery_item_data=get_recovery, add_recovery_item=add_recovery),
        "exchange": SimpleNamespace(get_exchange_point_amount=get_exchange, add_exchange_point=add_exchange),
        "unit": SimpleNamespace(
            unit=SimpleNamespace(Unit=SimpleNamespace(unit_id=Field("supporter"), disable_rank_up=Field("disable_rank_up"))),
            get_removable_skill_info=get_sis,
            add_unit_removable_skill=add_sis,
            get_supporter_unit=get_supporter,
            add_supporter_unit=add_supporter,
        ),
        "user_system": SimpleNamespace(get_current_energy=current_lp, add_energy=add_lp),
    }
    fn = extract_function(path, "give_comprehensive_test_resources", ns)
    user = SimpleNamespace(
        game_coin=1, social_point=2, free_sns_coin=3, paid_sns_coin=4,
        unit_max=320, waiting_unit_max=1000, friend_max=10,
        training_energy_max=3, training_energy=1, _lp=5,
    )
    context = SimpleNamespace(db=SimpleNamespace(
        item=FakeLookupDb({"kg_item": [1, 2, 3, 4, 10, 11], "recovery_item": [20, 21]}),
        exchange=FakeLookupDb({"exchange_point": [30, 31]}),
        unit=FakeLookupDb({"sis": [40, 41], "supporter": [50, 51]}),
        main=FakeMainDb(),
    ))

    message = await fn(context, user)
    report.check("LOVEARROWSHOOT sets game coin target", user.game_coin == 99_999_999)
    report.check("LOVEARROWSHOOT sets friend points target", user.social_point == 99_999_999)
    report.check("LOVEARROWSHOOT sets free and paid Loveca targets", user.free_sns_coin == 99_999 and user.paid_sns_coin == 99_999)
    report.check("LOVEARROWSHOOT expands card, waiting room and friend capacity", user.unit_max == 5000 and user.waiting_unit_max == 5000 and user.friend_max == 1000)
    report.check("LOVEARROWSHOOT restores training energy and LP", user.training_energy == 99 and user.training_energy_max == 99 and user._lp == 9999)
    report.check("LOVEARROWSHOOT tops up ordinary items and skips currency item IDs", inventory["items"] == {10: 9999, 11: 9999})
    report.check("LOVEARROWSHOOT tops up recovery items", inventory["recovery"] == {20: 9999, 21: 9999})
    report.check("LOVEARROWSHOOT tops up sticker/exchange currencies", inventory["exchange"] == {30: 9999, 31: 9999})
    report.check("LOVEARROWSHOOT tops up SIS", inventory["sis"] == {40: 99, 41: 99})
    report.check("LOVEARROWSHOOT tops up supporter members", inventory["supporters"] == {50: 100, 51: 100})
    first_add_counts = {k: len(v) for k, v in adds.items()}
    first_lp = user._lp
    second_message = await fn(context, user)
    report.check("LOVEARROWSHOOT is reusable and idempotent", {k: len(v) for k, v in adds.items()} == first_add_counts and user._lp == first_lp)
    report.check("LOVEARROWSHOOT returns a readable result", "LOVEARROWSHOOT" in message and "Warnings:" not in message and "Warnings:" not in second_message)


def validate_merge_function(path: Path, source_json: Path, report: Report):
    ns = {"Path": Path, "json": json}
    fn = extract_function(path, "_merge_required_builtin_serial_codes", ns)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = td / "bundled.json"
        dst = td / "workspace.json"
        shutil.copy2(source_json, src)
        custom = {
            "custom_key": {"keep": True},
            "serial_codes": [{"serial_code": "MYCUSTOM", "action": {"message_en": "keep"}}],
        }
        dst.write_text(json.dumps(custom), encoding="utf-8")
        fn(src, dst)
        once = json.loads(dst.read_text(encoding="utf-8"))
        fn(src, dst)
        twice = json.loads(dst.read_text(encoding="utf-8"))
        codes = [e.get("serial_code") for e in once["serial_codes"] if isinstance(e, dict)]
        report.check("Android workspace migration preserves user server_data fields", once.get("custom_key") == {"keep": True})
        report.check("Android workspace migration preserves custom serial codes", "MYCUSTOM" in codes)
        report.check("Android workspace migration appends LOVEARROWSHOOT", codes.count("LOVEARROWSHOOT") == 1)
        report.check("Android workspace migration does not duplicate built-in code", once == twice)


def run_compileall(pyroot: Path, report: Report, label: str):
    proc = subprocess.run([sys.executable, "-m", "compileall", "-q", str(pyroot)], capture_output=True, text=True)
    report.check(f"{label} Python compileall", proc.returncode == 0, (proc.stdout + proc.stderr).strip()[-1000:])


def validate_kotlin(android_root: Path, report: Report):
    java = android_root / "app/src/main/java/moe/honoka/npps4wrapper"
    main = read(java / "MainActivity.kt")
    service = read(java / "Npps4Service.kt")
    editor = read(java / "ConfigEditorActivity.kt")
    report.check("Wrapper default host remains localhost", 'DEFAULT_HOST = "127.0.0.1"' in service)
    report.check("Wrapper default port restored to 51376", "DEFAULT_PORT = 51376" in service and "DEFAULT_PORT = 8080" not in service)
    report.check("Endpoint is stored in SharedPreferences", "server_endpoint" in service and "putString(PREF_HOST" in service and "putInt(PREF_PORT" in service)
    report.check("Endpoint is restored on app launch", "Npps4Service.savedHost" in main and "Npps4Service.savedPort" in main)
    report.check("Endpoint edits persist while stopped", "attachEndpointPersistence()" in main and "saveEndpointPreferences()" in main and "TextWatcher" in main)
    report.check("Host and port controls lock while server is active", "hostEdit.isEnabled = !locked" in main and "portEdit.isEnabled = !locked" in main)
    report.check("Status indicator uses actual Python host and port", 's.optString("host"' in main and 's.optInt("port"' in main and 'append("监听：$actualHost:$actualPort' in main)
    report.check("Starting and restarting save and lock endpoint", main.count("Npps4Service.saveEndpoint") >= 2 and main.count("setEndpointLocked(true") >= 2)
    report.check("Every file editor/log viewer gets search controls", "搜索文本（输入后自动跳转）" in editor and "上一个" in editor and "下一个" in editor)
    report.check("Search selects and scrolls to matching line", "editor.setSelection" in editor and "layout.getLineForOffset" in editor and "editor.scrollTo" in editor)
    report.check("Search supports case-insensitive previous/next navigation", "ignoreCase = true" in editor and "findMatch(forward = false)" in editor and "findMatch(forward = true)" in editor)
    find_body = editor.split("private fun findMatch", 1)[1].split("private fun countMatches", 1)[0]
    report.check("Automatic search keeps keyboard focus in the search field", "editor.requestFocus()" not in find_body)
    lock_body = main.split("private fun setEndpointLocked", 1)[1].split("private fun input", 1)[0]
    report.check("Stopped status polling does not overwrite endpoint drafts", "if (locked)" in lock_body and "if (locked && actualHost" in lock_body)


def validate_source(android_root: Path, pc_root: Path, report: Report):
    apy = android_root / "app/src/main/python"
    ppy = pc_root / "app/src/main/python"
    run_compileall(apy, report, "Android")
    run_compileall(ppy, report, "PC")
    ah = relative_hashes(apy)
    ph = relative_hashes(ppy)
    report.check("Android and PC Python trees are byte-identical", ah == ph, f"Android={len(ah)}, PC={len(ph)}")

    server_data = json.loads(read(apy / "npps4/server_data.json"))
    entries = [e for e in server_data.get("serial_codes", []) if isinstance(e, dict) and e.get("serial_code") == "LOVEARROWSHOOT"]
    report.check("server_data contains exactly one LOVEARROWSHOOT code", len(entries) == 1)
    report.check("LOVEARROWSHOOT calls the comprehensive resource function", len(entries) == 1 and entries[0].get("action", {}).get("function") == "give_comprehensive_test_resources")
    registry = read(apy / "npps4/serialcode/__init__.py")
    report.check("serial-code function is registered", '"give_comprehensive_test_resources": func.give_comprehensive_test_resources' in registry)
    build = read(apy / "npps4/build_info.py")
    gradle = read(android_root / "app/build.gradle")
    report.check("Build ID is v5.10", 'BUILD_ID = "v5.10-wrapper-endpoint-search-test-resources"' in build)
    report.check("Android versionCode/versionName are 510/0.5.10", "versionCode 510" in gradle and "versionName '0.5.10'" in gradle)
    wrapper = read(apy / "android_wrapper.py")
    android_main = read(apy / "android_main.py")
    report.check("Android Python bridge defaults use 51376", wrapper.count("51376") >= 4 and "port: int = 51376" in android_main)
    report.check("Android bundled workspace migrates required serial code", "_merge_required_builtin_serial_codes(" in wrapper and 'required_codes = {"LOVEARROWSHOOT"}' in wrapper)

    for label, pyroot in (("Android", apy), ("PC", ppy)):
        try:
            for p in python_files(pyroot):
                ast.parse(read(p), filename=str(p))
            ok, detail = True, ""
        except Exception as e:
            ok, detail = False, repr(e)
        report.check(f"{label} Python AST parse", ok, detail)

    asyncio.run(validate_serial_function(apy / "npps4/serialcode/func.py", report))
    validate_merge_function(apy / "android_wrapper.py", apy / "npps4/server_data.json", report)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--android-root", type=Path, required=True)
    parser.add_argument("--pc-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    report = Report()
    validate_kotlin(args.android_root, report)
    validate_source(args.android_root, args.pc_root, report)
    payload = {
        "version": "v5.10",
        "passed": report.passed,
        "failed": report.failed,
        "results": report.results,
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SUMMARY: {report.passed} passed, {report.failed} failed")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
