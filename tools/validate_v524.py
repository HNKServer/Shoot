#!/usr/bin/env python3
from __future__ import annotations

import ast
import asyncio
import base64
import compileall
import io
import sqlite3
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pydantic

ROOT = Path(__file__).resolve().parents[1]
PYROOT = ROOT / "app/src/main/python"
PKG = PYROOT / "npps4"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[OK] {message}")


def class_block(source: str, name: str) -> str:
    start = source.index(f"class {name}(")
    next_class = source.find("\nclass ", start + 1)
    return source[start:] if next_class < 0 else source[start:next_class]


# Build marker and configuration.
build = (PKG / "build_info.py").read_text(encoding="utf-8")
require("v5.24-ranking-schema-rollback-museum-visual-only" in build, "v5.24 build marker is present")
config_source = (PKG / "config/data.py").read_text(encoding="utf-8")
require("museum_stat_bonus_enabled" in config_source and "] = False" in config_source,
        "Museum stat bonus defaults to disabled")
for sample in ("config.sample.toml", "config.dual.sample.toml", "config.cn-local.sample.toml", "config.gl-online.sample.toml"):
    require("museum_stat_bonus_enabled = false" in (PYROOT / sample).read_text(encoding="utf-8"),
            f"{sample} keeps Museum visual-only default")

# Exact Unit Master is a server resource, not a local-client dependency.
profile_master = (PKG / "system/profile_unit_master.py").read_text(encoding="utf-8")
require('resources.files("npps4.assets")' in profile_master, "Unit Master is resolved from bundled server assets")
require("mode=ro" in profile_master, "Bundled Unit Master is opened read-only")
for profile, filename, minimum in (("CN", "cn_unit_master.db", 3600), ("GL", "gl_client_master.db", 3900)):
    path = PKG / "assets" / filename
    require(path.is_file(), f"{profile} Unit Master is packaged")
    with sqlite3.connect(path) as db:
        count = int(db.execute("SELECT COUNT(*) FROM unit_m").fetchone()[0])
    require(count >= minimum, f"{profile} Unit Master contains {count} units")

# Museum unlock visibility and stat suppression are independent.
museum_path = PKG / "system/museum.py"
tree = ast.parse(museum_path.read_text(encoding="utf-8"), filename=str(museum_path))
selected = []
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name in {"MuseumParameterData", "MuseumInfoData"}:
        selected.append(node)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "get_museum_info_data":
        node.returns = None
        for arg in list(node.args.args) + list(node.args.kwonlyargs):
            arg.annotation = None
        selected.append(node)
module = ast.Module(body=selected, type_ignores=[])
ast.fix_missing_locations(module)

class _Gameplay:
    museum_stat_bonus_enabled = False
class _ConfigData:
    gameplay = _Gameplay()
class _Config:
    CONFIG_DATA = _ConfigData()
async def _cleanup(_context, _user):
    return None
async def _rows(_context):
    return [(101, 10, 20, 30), (102, 1, 2, 3)]
namespace = {
    "pydantic": pydantic,
    "config": _Config,
    "_cleanup_legacy_museum_transplant": _cleanup,
    "_native_rows": _rows,
    "_native_unlock_policy": lambda _context: "all",
}
exec(compile(module, str(museum_path), "exec", dont_inherit=True), namespace)
namespace["MuseumInfoData"].model_rebuild(_types_namespace=namespace)
async def check_museum() -> None:
    info = await namespace["get_museum_info_data"](SimpleNamespace(), SimpleNamespace(id=1))
    require(info.contents_id_list == [101, 102], "Museum gallery unlocks remain visible")
    require(info.parameter.model_dump() == {"smile": 0, "pure": 0, "cool": 0},
            "Museum team stats are zero by default")
    _Config.CONFIG_DATA.gameplay.museum_stat_bonus_enabled = True
    enabled = await namespace["get_museum_info_data"](SimpleNamespace(), SimpleNamespace(id=1))
    require(enabled.parameter.model_dump() == {"smile": 11, "pure": 22, "cool": 33},
            "Optional original Museum stats can still be enabled")
asyncio.run(check_museum())
require("get_cross_profile_common_parameter" not in museum_path.read_text(encoding="utf-8"),
        "Museum cross-profile score-normalization helper is removed")

# Database model is exactly the pre-v5.21 shared ranking shape.
main_source = (PKG / "db/main.py").read_text(encoding="utf-8")
for model in ("LiveClear", "LiveReplay", "PlayerRanking"):
    block = class_block(main_source, model)
    require("profile:" not in block, f"{model} has no CN/GL profile column")
require("normalized_hi_score" not in class_block(main_source, "LiveClear"),
        "LiveClear has no normalized score column")
require("UniqueConstraint(user_id, live_difficulty_id)" in class_block(main_source, "LiveClear"),
        "LiveClear is shared per account and song")
require("UniqueConstraint(user_id, live_difficulty_id, use_skill)" in class_block(main_source, "LiveReplay"),
        "LiveReplay is shared per account and song")
require("UniqueConstraint(user_id, day)" in class_block(main_source, "PlayerRanking"),
        "Daily ranking is one shared account row")

# Runtime ranking uses raw client score with no weighting or hidden payload.
game_live = (PKG / "game/live.py").read_text(encoding="utf-8")
system_live = (PKG / "system/live.py").read_text(encoding="utf-8")
ranking = (PKG / "system/ranking.py").read_text(encoding="utf-8")
advanced = (PKG / "system/advanced.py").read_text(encoding="utf-8")
unit_source = (PKG / "system/unit.py").read_text(encoding="utf-8")
for forbidden in ("normalized_score", "ranking_normalization", "canonical_attribute", "native_attribute"):
    require(forbidden not in game_live, f"game/live has no {forbidden} weighting path")
require("ranking.increment_daily_score(context, current_user, score)" in game_live,
        "Daily ranking receives the raw submitted score")
require("stats.model_dump_json().encode(\"utf-8\")" in game_live,
        "Live in-progress payload is the original deck JSON")
require("LiveClear.profile" not in system_live and "LiveReplay.profile" not in system_live,
        "Live clear and replay queries are not split by profile")
require("SHARED_PROFILE" not in ranking and "normalized_hi_score" not in ranking,
        "Ranking module has no virtual shared profile or normalized scores")
require("main.LiveClear.hi_score" in ranking, "Song ranking uses raw high score")
require("level_limit_profile" not in advanced and "get_unit_stats_from_unit_data_for_profile" not in unit_source,
        "CN level-curve ranking compensation is removed")

# No experimental ranking migrations or Android hand-written equivalents remain.
versions = PKG / "alembic/versions"
for name in (
    "2026_07_25_0010-profile_ranking_state.py",
    "2026_07_25_0011-shared_normalized_ranking.py",
    "2026_07_25_0012-museum_visual_only_score_reset.py",
):
    require(not (versions / name).exists(), f"{name} is absent")
android_schema = (PKG / "android_schema.py").read_text(encoding="utf-8")
require('ALEMBIC_HEAD = "costume_full_cycle"' in android_schema,
        "Android schema head is restored to costume_full_cycle")
require("_rebuild_profile_scoring_table" not in android_schema,
        "Android profile-ranking table rebuild is removed")
require(not (PKG / "assets/profile_score_contract.json").exists(),
        "Obsolete profile score contract is removed")

# Embedded Alembic payload must match the reverted source tree.
payload_source = (PKG / "tools/android_alembic_payload.py").read_text(encoding="utf-8")
payload_tree = ast.parse(payload_source)
assign = next(node for node in payload_tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PAYLOAD_B64" for t in node.targets))
encoded = ast.literal_eval(assign.value)
with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as zf:
    names = set(zf.namelist())
    require("versions/2026_07_23_0009-costume_full_cycle.py" in names,
            "Embedded Alembic payload contains costume_full_cycle")
    require(not any("2026_07_25_001" in name for name in names),
            "Embedded Alembic payload contains no reverted ranking migration")

# Exact special-accessory card generation remains present.
serial = (PKG / "serialcode/func.py").read_text(encoding="utf-8")
require("profile_unit_master" in serial and "_grant_special_accessory_test_units" in serial,
        "Exact special-accessory target-card grant is preserved")

require(compileall.compile_dir(PYROOT, quiet=1), "All embedded Python compiles")
print("v5.24 validation complete")
