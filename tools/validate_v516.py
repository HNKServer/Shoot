#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
import json
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYROOT = ROOT / "app" / "src" / "main" / "python"
N = PYROOT / "npps4"
checks: list[dict[str, object]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "passed": bool(ok), "detail": detail})


def text(rel: str) -> str:
    return (N / rel).read_text(encoding="utf-8")


def java_hash(value: str) -> int:
    result = 0
    for char in value:
        result = (31 * result + ord(char)) & 0xFFFFFFFF
    return result


bad: list[str] = []
for path in PYROOT.rglob("*.py"):
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:
        bad.append(f"{path.relative_to(ROOT)}: {exc}")
check("all embedded Python files parse", not bad, "; ".join(bad[:5]))

build = text("build_info.py")
exchange_src = text("system/exchange.py")
secretbox_src = text("system/secretbox.py")
banner_src = text("game/banner.py")
serial_src = text("serialcode/func.py")
accessory_src = text("system/accessory.py")
item_src = text("system/item.py")
schema_src = text("data/schema.py")
server = json.loads((N / "server_data.json").read_text(encoding="utf-8"))
boxes = {row["id_string"]: row for row in server["secretbox_data"]}

check(
    "v5.16 verified build marker",
    'BUILD_ID = "v5.16-verified-sticker-gacha-special-accessory-fix"' in build,
)
check("v5.15 friend fallback policy retained", "navigation-partner appearance" in build)
check("no process-global per-user cache retained", "process-global per-user cache" in build)

# Original NPPS4 deliberately has separate single and 10x blue-coupon pages.
for group in ("myus", "aqua"):
    single = boxes.get(f"bt-{group}")
    multi = boxes.get(f"bt-{group}-10x")
    check(f"{group} blue-coupon single page retained", single is not None)
    check(f"{group} blue-coupon 10x page retained", multi is not None)
    if single and multi:
        check(
            f"{group} duplicate art is intentional but IDs differ",
            single["menu_asset"] == multi["menu_asset"]
            and java_hash(single["id_string"]) != java_hash(multi["id_string"]),
        )
        check(
            f"{group} single/10x unit counts differ",
            {button["unit_count"] for button in single["buttons"]} == {1}
            and {button["unit_count"] for button in multi["buttons"]} == {10},
        )
check("home banner deduplicates art only", "seen_assets" in banner_src)
check("home banner prefers canonical higher-order page", "-int(item.order)" in banner_src)
check("scouting list does not deduplicate pages", "seen_assets" not in secretbox_src)

# honoka CN final-service pages: the id strings intentionally hash to official IDs.
for key, official_id, category in (("5K", 1718, 1), ("5L", 1719, 2), ("5M", 1720, 3), ("5N", 1721, 4)):
    page = boxes.get(key)
    check(f"CN thanks-festival page {official_id} present", page is not None)
    if page:
        check(f"{key} hashes to official ID", java_hash(key) == official_id)
        check(
            f"{key} uses profile-local SSR/UR pool",
            page.get("profiles") == ["cn"]
            and page.get("pool_mode") == "thanks_festival"
            and page["member_category"] == category
            and page["rarity_names"] == ["SSR", "UR"]
            and page["rarity_rates"] == [70, 30],
        )
        ticket_costs = [
            cost.get("cost_item_id")
            for button in page["buttons"]
            for cost in button["costs"]
            if cost["cost_type"] == 1000
        ]
        check(f"{key} special 11-pull ticket uses item 8", ticket_costs == [8])
check("Nijigasaki honor page remains GL-only", boxes["honor-niji"].get("profiles") == ["gl"])
check("Liella honor page remains GL-only", boxes["honor-lila"].get("profiles") == ["gl"])
check("configured pools are projected to active profile unit IDs", "secretbox_supported_unit_ids" in secretbox_src)
check("thanks pools use request profile master", "secretbox_thanks_pools" in secretbox_src)
check("empty positive-rate pages are hidden", "empty profile pool" in secretbox_src)
check("detail and draw use the same projected page", "async def get_secretbox_data" in secretbox_src)

# Sticker shop: one request-local catalogue and the exact same guard for list/buy.
check("sticker catalogue uses NPPS4 request cache", '@common.context_cacheable("exchange_profile_catalogue")' in exchange_src)
check("sticker list filters unsupported rows", "await _shop_row_supported(context, raw_info)" in exchange_src)
check("sticker purchase reuses the same filter", exchange_src.count("await _shop_row_supported(context, raw_info)") >= 2)
check("empty CN item master has configured-ticket fallback", "if item_ids is not None and not item_ids" in exchange_src)
check("shop filtering logs excluded row diagnostics", "Sticker-shop profile projection" in exchange_src)

# Generate the exact bundled CN split master, then validate every configured row.
try:
    tool_path = N / "tools" / "cn_honoka_master.py"
    spec = importlib.util.spec_from_file_location("v516_cn_master", tool_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="npps4-v516-cn-") as tmp:
        module.generate_split_db(str(N / "assets" / "honoka_main.db"), tmp, overwrite=True)

        def master_ids(db_name: str, table: str, column: str) -> set[int]:
            with sqlite3.connect(Path(tmp) / f"{db_name}.db_") as conn:
                return {int(row[0]) for row in conn.execute(f"SELECT {column} FROM `{table}`")}

        exchange_ids = master_ids("exchange", "exchange_point_m", "exchange_point_id")
        item_ids = master_ids("item", "kg_item_m", "item_id")
        if not item_ids:
            item_ids = {
                int(cost["cost_item_id"])
                for page in server["secretbox_data"]
                if not page.get("profiles") or "cn" in page["profiles"]
                for button in page["buttons"]
                for cost in button["costs"]
                if cost["cost_type"] == 1000 and cost.get("cost_item_id") is not None
            }
        catalogues = {
            1000: item_ids,
            5100: master_ids("item", "award_m", "award_id"),
            5200: master_ids("item", "background_m", "background_id"),
            3006: exchange_ids,
            14000: master_ids("museum", "museum_contents_m", "museum_contents_id"),
        }
        excluded: list[str] = []
        for row in server["sticker_shop"]:
            ids = catalogues.get(int(row["add_type"]))
            if ids is not None and int(row["item_id"]) not in ids:
                excluded.append(row["id_string"])
                continue
            if any(int(cost["rarity"]) not in exchange_ids for cost in row.get("costs", [])):
                excluded.append(row["id_string"])
        expected = {
            "background_217", "background_224", "background_225", "background_227", "background_228",
            *{f"award_{value}" for value in range(534, 573)},
            "cg?",
        }
        check("CN blue-coupon shop row remains visible", "blue_ticket" not in excluded)
        check("CN invalid sticker rows identified exactly", set(excluded) == expected, json.dumps(excluded, ensure_ascii=False))
        check("CN visible sticker rows count is 804", len(server["sticker_shop"]) - len(excluded) == 804)

        with sqlite3.connect(Path(tmp) / "unit.db_") as conn:
            mappings = [(int(a), int(u)) for a, u in conn.execute("SELECT accessory_id, unit_id FROM accessory_special_m")]
            unit_rows = {
                int(unit_id): int(disable)
                for unit_id, disable in conn.execute("SELECT unit_id, disable_rank_up FROM unit_m")
            }
        check("CN special accessory mappings are present", len(mappings) == 258)
        check("every CN special mapping targets a real normal card", all(unit_rows.get(unit_id) == 0 for _, unit_id in mappings))
except Exception as exc:
    check("bundled CN master validation completed", False, f"{type(exc).__name__}: {exc}")

# Correct item semantics and comprehensive test-code stock.
check("item 2 is social points", "case 2:" in item_src and "user.social_point" in item_src)
check("item 3 is game coin", "case 3:" in item_src and "user.game_coin" in item_src)
check("item 4 is free Loveca", "case 4:" in item_src and "user.free_sns_coin" in item_src)
check("LOVEARROWSHOOT explicitly stocks item 1 and 5", "item_ids: set[int] = {1, 5}" in serial_src)
check("LOVEARROWSHOOT stocks every configured scouting ticket", "SECRETBOX_COST_TYPE.ITEM_TICKET" in serial_src and "item_ids.add(int(cost.cost_item_id))" in serial_src)
check("pseudo items 2/3/4 are balances, not inventory rows", "item_ids - {2, 3, 4}" in serial_src)
check("LOVEARROWSHOOT creates three eligible special-card copies", "target_count=3" in serial_src and "special_test_cards" in serial_src)

# Keep the previously reverse-engineered official special-create contract.
check("special accessory still uses one mapped card", "if len(units) == 1:" in accessory_src)
check("no speculative two-card special rule added", "units[0].unit_id == units[1].unit_id" not in accessory_src)
check("no speculative special wear restriction added", "special accessory requires" not in accessory_src)
check("special mapping still comes from active profile master", "accessory_special_m WHERE unit_id=:unit_id" in accessory_src)

check("schema supports profile and dynamic-pool metadata", "profiles: list[Literal" in schema_src and "pool_mode:" in schema_src)

passed = sum(1 for row in checks if row["passed"])
failed = len(checks) - passed
report = {
    "build_id": "v5.16-verified-sticker-gacha-special-accessory-fix",
    "passed": passed,
    "failed": failed,
    "checks": checks,
}
(ROOT / "NPPS4_V5_16_FINAL_VALIDATION.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
lines = [
    "# NPPS4 v5.16 重新验证报告",
    "",
    f"- 通过：**{passed}**",
    f"- 失败：**{failed}**",
    "",
]
for row in checks:
    mark = "PASS" if row["passed"] else "FAIL"
    detail = f" — {row['detail']}" if row["detail"] else ""
    lines.append(f"- **{mark}** — {row['name']}{detail}")
(ROOT / "NPPS4_V5_16_FINAL_VALIDATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"passed": passed, "failed": failed}, ensure_ascii=False))
if failed:
    raise SystemExit(1)
