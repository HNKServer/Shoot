#!/usr/bin/env python3
"""Static regression guard for proven CN/NPPS4 compatibility contracts.

The guard deliberately distinguishes three evidence classes:
* upstream NPPS4 behaviour which must be preserved;
* facts established by the supplied CN/GL clients and device logs;
* v4.41 post-service features which must be real database-backed behaviour,
  not hard-coded successful responses.
"""
from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
py = root / "app/src/main/python/npps4"
errors: list[str] = []


def text(rel: str) -> str:
    return (py / rel).read_text(encoding="utf-8")


def require(cond: bool, message: str) -> None:
    if not cond:
        errors.append(message)


# Exact client request: tutorial/progress always carries required tutorial_state.
tutorial_source = text("game/tutorial.py")
tutorial_tree = ast.parse(tutorial_source)
progress_class = next(
    (n for n in tutorial_tree.body if isinstance(n, ast.ClassDef) and n.name == "TutorialProgressRequest"),
    None,
)
require(progress_class is not None, "TutorialProgressRequest missing")
if progress_class is not None:
    field = next(
        (
            n
            for n in progress_class.body
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "tutorial_state"
        ),
        None,
    )
    require(field is not None and field.value is None, "tutorial_state must be required, not inferred/defaulted")
require("model_validator" not in tutorial_source, "tutorial request must not accept invented wrapper/camelCase variants")
require("_resolve_requested_state" not in tutorial_source, "tutorial state must not be inferred from missing input")

# unitSelect may return success only after full roster/deck/album/center validation.
login_source = text("game/login.py")
onboarding_source = text("system/onboarding.py")
require("ensure_starter_roster_and_deck" in login_source, "unitSelect must perform real NPPS4 mutations")
require("require_starter_postconditions" in login_source, "unitSelect success lacks database postcondition check")
for term in ("album rows missing", "deck 1 is absent", "center member is absent", "tutorial_state="):
    require(term in onboarding_source, f"onboarding postcondition missing: {term}")

# v4.36 compatibility remains additive: CN fields plus NPPS4 reinforce fields.
item_source = text("game/item.py")
for term in ("use_button_flag", "general_item_type", "buff_type", "reinforce_item_list", "reinforce_info"):
    require(term in item_source, f"item/list lost required/additive field {term}")
multi_source = text("game/multiunit.py")
for term in ("multi_unit_scenario_status_list", "unlocked_multi_unit_scenario_ids"):
    require(term in multi_source, f"multiunit response lost field {term}")

# Both supplied clients have no handler for banner type 18. CN capability gates
# must use the explicit APK version instead of the 97.4.6 content version.
banner_source = text("game/banner.py")
capability_source = text("system/client_capabilities.py")
config_data_source = text("config/data.py")
require("client_capabilities.for_context(context)" in banner_source, "banner endpoint bypasses central client capabilities")
require("context.client_version > (9, 11)" not in banner_source, "banner endpoint mistakes CN content version for APK version")
require("supports_sif2_transfer_banner=False" in capability_source, "CN profile exposes unsupported banner type 18")
require("application_version" in config_data_source and '"9.7.1"' in config_data_source, "CN APK version is not modeled separately")

# The CN client resolves home WebView art through a native .imag + TEXB pair.
# Data transfer uses a stock catalogue slot replaced by a final type-4 package;
# manga keeps honoka-chan's wv_ba_01 back-side contract.
app_source = text("app/app.py")
announce_source = text("webview/announce.py")
cn_archive_source = text("download/cn_archive.py")
require('docs_url="/main.php/api"' in app_source, "upstream in-game Swagger announcement was not restored")
require('RedirectResponse("/main.php/api")' in app_source, "root does not lead to the NPPS4 announcement/API page")
require('RedirectResponse("/main.php/api", 302)' in announce_source, "announce WebView does not redirect to NPPS4 API docs")
for term in (
    '"assets/image/webview/wv_ba_117.png"',
    '"assets/image/webview/wv_ba_01.png"',
    'webview_url=f"/transfer?t={token}"',
    'webview_url="/manga"',
    'banner_id=200001',
    'back_side=True',
):
    require(term in banner_source, f"CN home WebView contract missing: {term}")
for term in (
    '"4_0_999.zip"',
    '"assets/image/webview/wv_ba_01.png": "npps4_manga.png"',
    'path.endswith(".imag")',
):
    require(term in cn_archive_source, f"CN banner package contract missing: {term}")
require('capabilities.profile == "cn"' in banner_source, "CN poster assets are not profile-gated")
require("暂无公告" not in app_source + announce_source, "the incorrect custom no-announcement page remains")

# CN /live/play was rejected before game logic by CROSS-XMC.  Keep the
# compatibility exception narrow: CN + CROSS + already-authenticated session.
core_source = text("idol/core.py")
for term in (
    "config.is_cn_compat()",
    "xmc_verify == idoltype.XMCVerifyMode.CROSS",
    "context.token is not None",
    "CN CROSS XMC compatibility",
):
    require(term in core_source, f"authenticated CN CROSS compatibility missing condition: {term}")
require("config.need_xmc_verify()" in core_source, "global NPPS4 XMC verification was removed")
require("XMCVerifyMode.SHARED" in core_source, "SHARED-XMC path was removed")
require("verify_xmc = false" not in core_source.lower(), "XMC was globally disabled in code")

# Exact client master overlay must be bundled. It supplements NPPS4 schemas;
# honoka is only a fallback when the exact client lacks a table.
master_path = py / "assets/cn_client_master.db"
master_tool_source = text("tools/cn_honoka_master.py")
require(master_path.is_file() and master_path.stat().st_size > 1_000_000, "exact CN client master overlay is absent/truncated")
require(
    'GENERATOR_VERSION = "cn_honoka_master:v6_accessory_full_cycle"' in master_tool_source,
    "current exact CN/accessory master generator is not active",
)
require("bundled_cn_client_master_db" in master_tool_source, "generator does not use bundled exact CN master")
if master_path.is_file():
    try:
        with sqlite3.connect(master_path) as db:
            checks = {
                "achievement_m": 6000,
                "live_setting_m": 1800,
                "live_track_m": 300,
                "scenario_m": 400,
                "event_scenario_m": 700,
                "multi_unit_scenario_m": 40,
                "accessory_m": 330,
                "accessory_level_m": 4800,
                "accessory_special_m": 250,
            }
            for table, minimum in checks.items():
                count = int(db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                require(count >= minimum, f"exact CN master table {table} is unexpectedly incomplete: {count}")
            achievement_cols = {row[1] for row in db.execute('PRAGMA table_info("achievement_m")')}
            for col in ("achievement_type", "default_open_flag", "start_date", "end_date"):
                require(col in achievement_cols, f"achievement_m lost required exact column {col}")
    except Exception as exc:
        errors.append(f"cannot validate exact CN client master: {exc}")

# Post-service content access must be a one-time real-state migration. It may
# restore release/login achievements and archived event stories, but must not
# blindly mark every normal progression achievement completed.
post_source = text("system/post_service_content.py")
lbonus_source = text("game/lbonus.py")
db_source = text("db/main.py")
event_game_source = text("game/eventscenario.py")
for term in ("GRANT_KEY = \"cn_post_service_content\"", "GRANT_VERSION = 1", "ContentAccessGrant", "grant.grant_version >= GRANT_VERSION"):
    require(term in post_source, f"post-service idempotency contract missing: {term}")
require("achievement_type == 29" in post_source, "release/login achievement selection is not narrowly typed")
require("default_open_flag == 1" in post_source, "release achievements are not limited to default-open records")
require("AchievementUpdateLoginBonus" in lbonus_source, "content migration bypasses NPPS4's real achievement checker")
require("process_achievement_reward" in lbonus_source, "content migration bypasses NPPS4's real reward processor")
for model in ("class EventScenarioUnlock", "class MultiUnitScenarioUnlock", "class ContentAccessGrant"):
    require(model in db_source, f"database-backed content state missing: {model}")
for route in ('"status"', '"open"', '"startup"', '"reward"'):
    require(f'@idol.register("eventscenario", {route}' in event_game_source, f"eventscenario endpoint missing: {route}")
for route in ('"multiunitscenarioStatus"', '"scenarioStartup"', '"scenarioReward"'):
    require(f'@idol.register("multiunit", {route}' in multi_source, f"multiunit endpoint missing: {route}")


# v4.46 completes the accessory lifecycle. The endpoints must be backed by
# persistent state and active-profile unit master tables, not honoka's
# hardcoded level-8/favorite shell.
accessory_source = text("system/accessory.py")
unit_game_source = text("game/unit.py")
for route in ("accessoryAll", "accessoryMaterialAll", "accessoryTab", "wearAccessory", "favoriteAccessory", "createAccessory", "mergeAccessory", "saleAccessory"):
    require(f'@idol.register("unit", "{route}"' in unit_game_source, f"accessory endpoint missing: {route}")
for term in (
    "accessory_lottery_cost_m",
    "accessory_lottery_group_m",
    "accessory_lottery_list_m",
    "accessory_special_m",
    "accessory_level_limit_over_m",
    "rank_up_count",
    "context.db.unit",
):
    require(term in accessory_source, f"full accessory lifecycle lost master/state logic: {term}")
for forbidden in ("Level = 8", "MaxLevel = 8", "RankUpCount = 4", "FavoriteFlag = true"):
    require(forbidden not in accessory_source + unit_game_source, f"honoka hardcoded accessory shell leaked into NPPS4: {forbidden}")
require("class UserAccessory" in db_source and "rank_up_count" in db_source, "persistent accessory remake state is missing")

# Do not advertise completely absent route families, and do not change a
# historically preserved capability without client evidence.
require("open_arena=False" in login_source, "Arena is advertised although no arena endpoints exist")
require("costume_status=False" in login_source, "Costume is advertised although mutation/status endpoints are absent")
require("open_v98=True" in login_source, "open_v98 was changed without client evidence")

# Never print bearer tokens or decrypted login credentials.
session_source = text("idol/session.py")
require("util.log(authorize)" not in session_source, "raw Authorize header is logged")
require("Hello my key is" not in login_source and "And my passwd is" not in login_source, "decrypted credentials are logged")

if errors:
    print("CN contract guard FAILED:")
    for error in errors:
        print(" -", error)
    raise SystemExit(1)
print("CN contract guard OK")
