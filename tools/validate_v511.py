#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


class Report:
    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS" if ok else "FAIL") + ": " + name + (f" — {detail}" if detail else ""))

    @property
    def passed(self) -> int:
        return sum(1 for row in self.results if row["ok"])

    @property
    def failed(self) -> int:
        return sum(1 for row in self.results if not row["ok"])


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def relative_hashes(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def run_compileall(root: Path, report: Report, label: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(root)],
        text=True,
        capture_output=True,
    )
    report.check(
        f"{label} Python compileall",
        proc.returncode == 0,
        (proc.stdout + proc.stderr).strip()[-1200:],
    )


def validate_workspace_authority(android_root: Path, report: Report) -> None:
    pyroot = android_root / "app/src/main/python"
    script = r'''
from pathlib import Path
import json
import tempfile
import android_wrapper

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "npps4").mkdir()
    (root / "external").mkdir()
    server_data = '{"serial_codes": [], "custom": {"keep": true}}\n'
    config = 'THIS IS AN INTENTIONALLY CUSTOM CONFIG\n'
    login_bonus = 'def get_rewards(*args, **kwargs):\n    return ["custom"]\n'
    (root / "npps4/server_data.json").write_text(server_data, encoding="utf-8")
    (root / "config.toml").write_text(config, encoding="utf-8")
    (root / "external/login_bonus.py").write_text(login_bonus, encoding="utf-8")
    android_wrapper.prepare_workspace(str(root))
    android_wrapper.prepare_workspace(str(root))
    assert (root / "npps4/server_data.json").read_text(encoding="utf-8") == server_data
    assert (root / "config.toml").read_text(encoding="utf-8") == config
    assert (root / "external/login_bonus.py").read_text(encoding="utf-8") == login_bonus

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    android_wrapper.prepare_workspace(str(root))
    data = json.loads((root / "npps4/server_data.json").read_text(encoding="utf-8"))
    codes = [entry.get("serial_code") for entry in data.get("serial_codes", []) if isinstance(entry, dict)]
    assert codes.count("LOVEARROWSHOOT") == 1
    assert (root / "config.toml").exists()
print("workspace-authority-ok")
'''
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(pyroot),
        env={**__import__("os").environ, "PYTHONPATH": str(pyroot)},
        text=True,
        capture_output=True,
    )
    report.check(
        "Existing server_data/config/external files survive repeated startup byte-for-byte",
        proc.returncode == 0 and "workspace-authority-ok" in proc.stdout,
        (proc.stdout + proc.stderr).strip()[-1600:],
    )


def validate_kotlin(android_root: Path, report: Report) -> None:
    java = android_root / "app/src/main/java/moe/honoka/npps4wrapper"
    editor = read(java / "ConfigEditorActivity.kt")
    file_ops = read(java / "FileOps.kt")
    service = read(java / "Npps4Service.kt")
    main = read(java / "MainActivity.kt")

    report.check(
        "Search TextWatcher uses the EditText receiver explicitly",
        "searchInput.text.isNotBlank()" in editor and "this.text.isNotBlank()" not in editor,
    )
    ensure_body = file_ops.split("fun ensureTemplate", 1)[1].split("fun rewriteDefaultConfig", 1)[0]
    report.check(
        "ensureTemplate creates config only when absent",
        "if (!cfg.exists())" in ensure_body and "currentConfig.isBlank()" not in ensure_body,
    )
    report.check(
        "ensureTemplate never writes an empty server_data placeholder",
        'serverData.writeText("{}\\n"' not in ensure_body and "PythonBridge.serverDataFile" not in ensure_body,
    )
    report.check(
        "ensureTemplate never repairs an existing login-bonus hook",
        "if (!loginBonus.exists())" in ensure_body and "placeholder.bak" not in ensure_body,
    )
    report.check(
        "Service startup does not rewrite config.toml",
        "FileOps.rewriteDefaultConfig(this)" not in service,
    )
    start_area = main.split('addView(button("启动服务器")', 1)[1].split('addView(button("停止服务器")', 1)[0]
    report.check(
        "Start/restart buttons do not rewrite config.toml",
        "rewriteDefaultConfig" not in start_area,
    )
    report.check(
        "Explicit GUI profile/path changes can still write their requested values",
        file_ops.count("rewriteDefaultConfig(context)") >= 4,
    )


def validate_source(android_root: Path, pc_root: Path, report: Report) -> None:
    apy = android_root / "app/src/main/python"
    ppy = pc_root / "app/src/main/python"
    run_compileall(apy, report, "Android")
    run_compileall(ppy, report, "PC")

    for label, root in (("Android", apy), ("PC", ppy)):
        try:
            for path in root.rglob("*.py"):
                if "__pycache__" not in path.parts:
                    ast.parse(read(path), filename=str(path))
            ok, detail = True, ""
        except Exception as exc:
            ok, detail = False, repr(exc)
        report.check(f"{label} Python AST parse", ok, detail)

    ah = relative_hashes(apy)
    ph = relative_hashes(ppy)
    report.check(
        "Android and PC shared Python trees are byte-identical",
        ah == ph,
        f"Android={len(ah)} PC={len(ph)}",
    )

    server_data = json.loads(read(apy / "npps4/server_data.json"))
    codes = [
        entry
        for entry in server_data.get("serial_codes", [])
        if isinstance(entry, dict) and entry.get("serial_code") == "LOVEARROWSHOOT"
    ]
    report.check("Bundled server_data contains exactly one LOVEARROWSHOOT", len(codes) == 1)
    report.check(
        "LOVEARROWSHOOT remains an editable server_data action",
        len(codes) == 1
        and codes[0].get("action", {}).get("function") == "give_comprehensive_test_resources",
    )

    wrapper = read(apy / "android_wrapper.py")
    report.check(
        "Startup injector/repair helpers were removed",
        "_merge_required_builtin_serial_codes" not in wrapper
        and "_repair_server_data_if_empty_or_legacy" not in wrapper
        and "_repair_external_hook_if_invalid" not in wrapper,
    )
    report.check(
        "Python workspace copies editable defaults only when missing",
        wrapper.count("_copy_if_missing(") >= 6
        and "never canonicalize, migrate, repair" in wrapper
        and "must not inject bundled entries" in wrapper,
    )

    serial = read(apy / "npps4/serialcode/func.py")
    tree = ast.parse(serial)
    fn_names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    report.check(
        "Complete test-code helpers exist",
        {"_grant_collectible_units", "_grant_accessory_catalogue", "_grant_profile_cosmetics", "give_comprehensive_test_resources"}.issubset(fn_names),
    )
    report.check(
        "Test code grants every current-profile normal/costume card",
        "UNIT_CATEGORY.NORMAL" in serial
        and "UNIT_CATEGORY.COSTUME" in serial
        and "main.Unit(" in serial
        and "cards_created" in serial,
    )
    report.check(
        "Test code grants and maxes accessories/materials",
        "_raw_accessory_rows" in serial
        and "UserAccessory(" in serial
        and "UserAccessoryMaterial(" in serial
        and "MAX_RANK_UP_COUNT" in serial,
    )
    report.check(
        "Test code unlocks profile titles/backgrounds",
        "item_db.Award.award_id" in serial
        and "item_db.Background.background_id" in serial
        and "main.Award(" in serial
        and "main.Background(" in serial,
    )
    report.check(
        "Test code is reusable/profile-aware instead of duplicating the whole catalogue",
        "owned_by_unit_id" in serial
        and "profile_value" in serial
        and "existing_costume_ids" in serial,
    )
    report.check(
        "Card/storage targets are large enough for the combined CN/GL catalogue",
        "user.unit_max = max(user.unit_max, 10_000)" in serial
        and "user.waiting_unit_max = max(user.waiting_unit_max, 10_000)" in serial,
    )

    build = read(apy / "npps4/build_info.py")
    gradle = read(android_root / "app/build.gradle")
    report.check(
        "Build/version markers are v5.11",
        'BUILD_ID = "v5.11-config-authority-complete-test-code"' in build
        and "versionCode 511" in gradle
        and "versionName '0.5.11'" in gradle,
    )

    validate_workspace_authority(android_root, report)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--android-root", type=Path, required=True)
    parser.add_argument("--pc-root", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    report = Report()
    validate_kotlin(args.android_root, report)
    validate_source(args.android_root, args.pc_root, report)
    payload = {
        "version": "v5.11",
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
