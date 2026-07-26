#!/usr/bin/env python3
from __future__ import annotations

import ast
import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYROOT = ROOT / "app" / "src" / "main" / "python"
checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))


def text(rel: str) -> str:
    return (PYROOT / "npps4" / rel).read_text(encoding="utf-8")


# Syntax audit for the entire embedded server.
bad_syntax: list[str] = []
for path in PYROOT.rglob("*.py"):
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        bad_syntax.append(f"{path.relative_to(ROOT)}: {exc}")
check("all embedded Python files parse", not bad_syntax, "; ".join(bad_syntax[:5]))

build = text("build_info.py")
costume_src = text("system/costume.py")
projection_src = text("system/profile_projection.py")
unit_src = text("system/unit.py")
friend_src = text("game/friend.py")
profile_game_src = text("game/profile.py")
profile_system_src = text("system/profile.py")
advanced_src = text("system/advanced.py")
live_src = text("game/live.py")
ranking_src = text("game/ranking.py")
notice_src = text("game/notice.py")
unit_model_src = text("system/unit_model.py")

check(
    "build id is v5.15 social fallback fix",
    'BUILD_ID = "v5.15-friend-costume-cross-profile-fallback"' in build,
)
check("policy forbids wardrobe preload", "no wardrobe preload" in build)
check("policy forbids process-global per-user cache", "process-global per-user cache" in build)
check("policy forbids synthetic card ownership", "synthetic card ownership" in build)

# DB strategy: one rendered navigation card, current profile first, then other profile.
check("social lookup is targeted to one owned-card id", "main.UserCostumeDress.unit_owning_user_id == owned.id" in costume_src)
check("receiver profile binding is queried first", "main.UserCostumeDress.profile == current_profile" in costume_src)
check("other-profile binding is fallback-only", "main.UserCostumeDress.profile != current_profile" in costume_src)
check("source-profile registration is validated", "row.profile," in costume_src and "_registered_row_for_profile" in costume_src)
check("receiver Master support is validated", "costume_master = await _master(context, row.costume_unit_id)" in costume_src)
check("signed receiver asset is validated", "has_signed_variant" in costume_src)
check("social projection ignores target local display toggle", "async def social_appearance_for_owned_unit" in costume_src and "is_enabled(context" not in costume_src.split("async def social_appearance_for_owned_unit", 1)[1])
check(
    "no wardrobe-table preload helper was added",
    all(token not in costume_src for token in ("_load_appearance_state", "costume_appearance_state", "dresses: dict", "registered: set")),
)
check("no context/global costume cache decorator", "@common.context_cacheable" not in costume_src)

# Social contract and fallback routing.
check("owned unit supports explicit social projection", "social_costume_projection: bool = False" in unit_src)
check("social base projection uses native fallback", "social_costume_projection=True" in projection_src and "native_costume_fallback=True" in projection_src)
check("main-deck center is preferred before navigation partner", "Return main-deck center first" in projection_src and "ids.append(int(target_user.center_unit_owning_user_id" in projection_src)
check("social appearance comes from navigation partner", "partner_id = int(target_user.center_unit_owning_user_id" in projection_src)
check("unsupported owned cards are skipped, never invented", "No synthetic card or unknown Master ID" in projection_src)
check("Live guest validates leader-skill support", "_live_leader_supported" in projection_src and "LeaderSkill" in projection_src)
check("partyList and live/play share one guest selector", "profile_projection.live_guest_center_unit" in advanced_src and "profile_projection.live_guest_center_unit" in live_src)
check("partyList rejects an empty unsafe payload", "if not party_list:" in live_src and "ERROR_CODE_LIVE_INVALID_PARTY_USER" in live_src)

for rel, src in (
    ("friend", friend_src),
    ("profile", profile_game_src),
    ("ranking", ranking_src),
    ("greeting", notice_src),
    ("Live party", advanced_src),
):
    check(f"{rel} uses social costume projection", "profile_projection.social_costume" in src)

check("profile center receives partner display costume", "display_costume=display_costume" in profile_game_src)
check(
    "profile navigation row also receives safe partner display costume",
    profile_game_src.count("display_costume=display_costume") >= 2,
)
check("friend list omits unrepresentable rows instead of null center", "if center is None:" in friend_src and "return None" in friend_src)
check("friend search fails safely for no representable card", "ERROR_CODE_FRIEND_USER_NOT_EXISTS" in friend_src)
check("profile fails safely for no representable card", "center_projection is None or partner_projection is None" in profile_game_src)

# v5.14 contract protections must remain.
check("optional costume serializer still removes JSON null", 'data.pop("costume", None)' in unit_model_src)
check("ordinary owned-card override still respects local toggle", "not await is_enabled(context, user)" in costume_src)
check("ordinary absent binding still returns None", "if row is None:\n        return None" in costume_src.split("async def appearance_for_owned_unit", 1)[1])
check("single-use wardrobe guard remains in dressUp", "already used by another card" in costume_src)
check("no wardrobe removal API invented", "unregister" not in text("game/costume.py").lower() and "deleteCostume" not in text("game/costume.py"))


async def dynamic_checks() -> None:
    sys.path.insert(0, str(PYROOT))
    unit_model = importlib.import_module("npps4.system.unit_model")

    def load_async_function(source: str, name: str, namespace: dict[str, Any]):
        tree = ast.parse(source)
        node = next(
            item
            for item in tree.body
            if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)) and item.name == name
        )
        module = ast.Module(
            body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node],
            type_ignores=[],
        )
        ast.fix_missing_locations(module)
        exec(compile(module, filename=f"<{name}>", mode="exec"), namespace)
        return namespace[name]

    # Real wire-format regression from v5.14.
    common: dict[str, Any] = dict(
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
    empty = unit_model.UnitInfoData(**common, costume=None).model_dump(exclude_none=False)
    dressed = unit_model.UnitInfoData(
        **common,
        costume=unit_model.CostumeInfo(unit_id=9, is_rank_max=True, is_signed=False),
    ).model_dump(exclude_none=False)
    check("wire format omits absent costume key", "costume" not in empty, json.dumps(empty)[:240])
    check("wire format preserves real costume object", dressed.get("costume", {}).get("unit_id") == 9)
    check("unrelated None fields retain v5.12 behavior", "unit_rarity_id" in empty and empty["unit_rarity_id"] is None)

    # Execute the exact social helper body with deterministic fake DB/master functions.
    owned = SimpleNamespace(id=44, user_id=7, unit_id=100, display_rank=1, is_signed=False, active=True)
    exact = SimpleNamespace(profile="cn", costume_unit_id=200, is_rank_max=False, is_signed=False)
    other = SimpleNamespace(profile="gl", costume_unit_id=300, is_rank_max=True, is_signed=False)
    rows = [exact, other]
    registered = {("cn", 200): object(), ("gl", 300): object()}
    masters = {
        100: SimpleNamespace(unit_type_id=5, rank_max=2),
        200: SimpleNamespace(unit_type_id=5, rank_max=2),
        300: SimpleNamespace(unit_type_id=5, rank_max=2),
    }

    async def fake_rows(context: Any, value: Any):
        return list(rows)

    async def fake_registered(context: Any, user_id: int, profile: str, unit_id: int, is_rank_max: bool, is_signed: bool):
        return registered.get((profile, unit_id))

    async def fake_master(context: Any, unit_id: int):
        return masters.get(unit_id)

    async def fake_signed(context: Any, unit_id: int):
        return unit_id != 999

    async def fake_native(context: Any, value: Any):
        return unit_model.CostumeInfo(unit_id=value.unit_id, is_rank_max=False, is_signed=False)

    social_fn = load_async_function(
        costume_src,
        "social_appearance_for_owned_unit",
        {
            "_social_dress_rows": fake_rows,
            "_registered_row_for_profile": fake_registered,
            "_master": fake_master,
            "unit_system": SimpleNamespace(has_signed_variant=fake_signed),
            "unit_model": unit_model,
            "default_appearance": fake_native,
        },
    )

    got = await social_fn(SimpleNamespace(), owned, native_fallback=True)
    check("dynamic: receiver-profile dress wins", got is not None and got.unit_id == 200)

    masters.pop(200)
    got = await social_fn(SimpleNamespace(), owned, native_fallback=True)
    check("dynamic: unsupported receiver dress falls to other profile", got is not None and got.unit_id == 300)

    rows[:] = [SimpleNamespace(profile="gl", costume_unit_id=999, is_rank_max=True, is_signed=True)]
    registered[("gl", 999)] = object()
    masters[999] = SimpleNamespace(unit_type_id=5, rank_max=2)
    got = await social_fn(SimpleNamespace(), owned, native_fallback=True)
    check("dynamic: unsupported signed asset falls to native", got is not None and got.unit_id == 100)

    masters.pop(100)
    got = await social_fn(SimpleNamespace(), owned, native_fallback=True)
    check("dynamic: unsupported native card is omitted", got is None)

    # Execute the exact partner-display helper: visual costume is independent from stats center.
    target = SimpleNamespace(id=7, center_unit_owning_user_id=55)
    partner = SimpleNamespace(id=55, user_id=7, active=True)

    class FakeMain:
        async def get(self, model: Any, key: int):
            return partner if key == 55 else None

    async def fake_partner_appearance(context: Any, owned_value: Any, *, native_fallback: bool):
        return unit_model.CostumeInfo(unit_id=777, is_rank_max=True, is_signed=False)

    async def unused_center(context: Any, target_user: Any):
        return None

    social_center_fn = load_async_function(
        projection_src,
        "social_costume",
        {
            "main": SimpleNamespace(Unit=object()),
            "costume": SimpleNamespace(social_appearance_for_owned_unit=fake_partner_appearance),
            "center_unit": unused_center,
        },
    )
    context = SimpleNamespace(db=SimpleNamespace(main=FakeMain()))
    fallback_full = SimpleNamespace(costume=unit_model.CostumeInfo(unit_id=111, is_rank_max=False, is_signed=False))
    result = await social_center_fn(context, target, (object(), object(), fallback_full, object()))
    check("dynamic: social center displays navigation-partner appearance", result is not None and result.unit_id == 777)

    # Execute the exact Live selector: skip a supported Unit whose leader row is absent.
    first = SimpleNamespace(id=1)
    second = SimpleNamespace(id=2)

    async def fake_preferred(context: Any, target_user: Any):
        return (1, 2)

    async def fake_candidates(context: Any, target_user: Any, preferred: Any):
        yield first
        yield second

    async def fake_owned(context: Any, candidate: Any):
        return (candidate, SimpleNamespace(default_leader_skill_id=candidate.id), object(), object())

    async def fake_leader(context: Any, info: Any):
        return info.default_leader_skill_id == 2

    live_selector = load_async_function(
        projection_src,
        "live_guest_center_unit",
        {
            "_preferred_center_owning_ids": fake_preferred,
            "_candidate_owned_units": fake_candidates,
            "owned_unit": fake_owned,
            "_live_leader_supported": fake_leader,
        },
    )
    result = await live_selector(SimpleNamespace(), SimpleNamespace())
    check("dynamic: Live skips invalid unique center and picks next safe card", result is not None and result[0].id == 2)


try:
    asyncio.run(dynamic_checks())
except Exception as exc:
    check("dynamic validation suite completes", False, repr(exc))

# Android-only metadata and long-standing Kotlin compile fix.
gradle = (ROOT / "app" / "build.gradle").read_text(encoding="utf-8")
if "Android-Wrapper" in ROOT.name:
    check("Android versionCode 515", "versionCode 515" in gradle)
    check("Android versionName 0.5.15", "versionName '0.5.15'" in gradle)
    kotlin = ROOT / "app" / "src" / "main" / "java" / "moe" / "honoka" / "npps4wrapper" / "ConfigEditorActivity.kt"
    if kotlin.exists():
        ks = kotlin.read_text(encoding="utf-8")
        check("Kotlin search TextWatcher fix preserved", "searchInput.text.isNotBlank()" in ks and "this.text.isNotBlank()" not in ks)

passed = sum(ok for _, ok, _ in checks)
failed = len(checks) - passed
print(f"v5.15 validation: {passed} passed, {failed} failed")
for name, ok, detail in checks:
    print(f"{'PASS' if ok else 'FAIL'} - {name}" + (f" :: {detail}" if detail else ""))

report = {
    "package": ROOT.name,
    "passed": passed,
    "failed": failed,
    "checks": [{"name": n, "ok": o, "detail": d} for n, o, d in checks],
}
(ROOT / "NPPS4_V5_15_FINAL_VALIDATION.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
raise SystemExit(1 if failed else 0)
