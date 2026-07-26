#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYROOT = ROOT / "app" / "src" / "main" / "python"
checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))


def text(rel: str) -> str:
    return (PYROOT / "npps4" / rel).read_text(encoding="utf-8")

# Source syntax
bad_syntax: list[str] = []
for path in PYROOT.rglob("*.py"):
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        bad_syntax.append(f"{path.relative_to(ROOT)}: {exc}")
check("all embedded Python files parse", not bad_syntax, "; ".join(bad_syntax[:5]))

build = text("build_info.py")
check("build id is v5.14 stability fix", 'BUILD_ID = "v5.14-costume-contract-stability-fix"' in build)
check("policy explicitly forbids wardrobe prefetch", "no wardrobe prefetch" in build)

costume = text("system/costume.py")
unit = text("system/unit.py")
game_unit = text("game/unit.py")
profile = text("system/profile.py")
projection = text("system/profile_projection.py")
unit_model = text("system/unit_model.py")

check("native appearance is not returned as an owned-unit override", "Return only a persisted costume override" in costume)
section = costume.split("async def appearance_for_owned_unit", 1)[1]
check("no binding returns None", "if row is None:\n        return None" in section)
check("invalid binding returns None", "if not valid:" in section and "return None" in section)
check("actual binding returns CostumeInfo", "unit_id=row.costume_unit_id" in section)
check("single-use guard is present only in dressUp path", "in_use_q = sqlalchemy.select(main.UserCostumeDress)" in costume and "already used by another card" in costume)
check("no costume prefetch state/cache added", all(token not in costume for token in ("costume_appearance_state", "@common.context_cacheable", "dresses: dict", "_load_appearance_state", "select(main.UserCostumeDress).where(main.UserCostumeDress.user_id == user_id")))
check("appearance query is targeted to one owned card", "main.UserCostumeDress.unit_owning_user_id == owned.id" in section)

check("full owned-unit payload defaults to override-only", "native_costume_fallback: bool = False" in unit)
check("unitAll explicitly disables native costume fallback", "native_costume_fallback=False" in game_unit)
check("profile projection explicitly retains display fallback", "native_costume_fallback=True" in projection)
check("profile info explicitly retains display fallback", "native_costume_fallback=True" in profile)
check("targeted OptionalCostumeModel serializer exists", "class OptionalCostumeModel" in unit_model and 'data.pop("costume", None)' in unit_model)

for rel, cls in (
    ("system/common.py", "CenterUnitInfo(unit_model.OptionalCostumeModel)"),
    ("system/advanced.py", "PartyCenterUnitInfo(unit_model.OptionalCostumeModel)"),
    ("system/profile.py", "ProfileUnitInfo(unit_model.OptionalCostumeModel)"),
    ("game/notice.py", "GreetingCenterUnitInfo(unit_model.OptionalCostumeModel)"),
):
    check(f"{rel} uses targeted costume serializer", cls in text(rel))

# Real Pydantic wire-format test.
sys.path.insert(0, str(PYROOT))
try:
    mod = importlib.import_module("npps4.system.unit_model")
    common = dict(
        unit_owning_user_id=1,
        unit_id=2,
        unit_rarity_id=None,
        exp=0,
        next_exp=1,
        level=1,
        level_limit_id=1,
        max_level=80,
        rank=1,
        max_rank=2,
        love=0,
        max_love=100,
        unit_skill_level=1,
        max_hp=3,
        favorite_flag=False,
        display_rank=1,
        unit_skill_exp=0,
        unit_removable_skill_capacity=0,
        is_love_max=False,
        is_level_max=False,
        is_rank_max=False,
        is_signed=False,
        is_skill_level_max=False,
        is_removable_skill_capacity_max=False,
        insert_date="",
    )
    empty = mod.UnitInfoData(**common, costume=None).model_dump(exclude_none=False)
    dressed = mod.UnitInfoData(
        **common,
        costume=mod.CostumeInfo(unit_id=9, is_rank_max=True, is_signed=False),
    ).model_dump(exclude_none=False)
    check("wire format omits absent costume key", "costume" not in empty, json.dumps(empty, ensure_ascii=False)[:300])
    check("wire format preserves real costume object", dressed.get("costume", {}).get("unit_id") == 9, json.dumps(dressed, ensure_ascii=False)[:300])
    check("other v5.12 None fields remain present", "unit_rarity_id" in empty and empty["unit_rarity_id"] is None)
except Exception as exc:
    check("Pydantic wire-format test imports", False, repr(exc))

# Existing routes and no invented unregister endpoint.
game_costume = text("game/costume.py")
for route in ("costumeList", "costumeStatus", "dressUp", "makeCostume"):
    check(f"route {route} preserved", f'@idol.register("costume", "{route}")' in game_costume)
check("no wardrobe removal API invented", "unregister" not in game_costume.lower() and "deleteCostume" not in game_costume)

# Android-only checks are harmless on the PC tree (PC intentionally retains its historical wrapper metadata).
gradle = (ROOT / "app" / "build.gradle").read_text(encoding="utf-8")
if "Android-Wrapper" in ROOT.name:
    check("Android versionCode 514", "versionCode 514" in gradle)
    check("Android versionName 0.5.14", "versionName '0.5.14'" in gradle)

kotlin = ROOT / "app" / "src" / "main" / "java" / "moe" / "honoka" / "npps4wrapper" / "ConfigEditorActivity.kt"
if "Android-Wrapper" in ROOT.name and kotlin.exists():
    ks = kotlin.read_text(encoding="utf-8")
    check("Kotlin search TextWatcher fix preserved", "searchInput.text.isNotBlank()" in ks and "this.text.isNotBlank()" not in ks)

passed = sum(ok for _, ok, _ in checks)
failed = len(checks) - passed
print(f"v5.14 validation: {passed} passed, {failed} failed")
for name, ok, detail in checks:
    print(f"{'PASS' if ok else 'FAIL'} - {name}" + (f" :: {detail}" if detail else ""))

report = {
    "package": ROOT.name,
    "passed": passed,
    "failed": failed,
    "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
}
(ROOT / "NPPS4_V5_14_FINAL_VALIDATION.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
raise SystemExit(1 if failed else 0)
