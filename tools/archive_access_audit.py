#!/usr/bin/env python3
"""Audit preserved NPPS4 access routes for Museum, stories, Live and Album.

"No route" means that no route was found in the supplied original NPPS4
source, bundled server_data.json and client master files. It does not claim
that KLab's historical live-service/event backend never distributed it.
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import sqlite3
from pathlib import Path
from typing import Any

ADD_UNIT = 1001
ADD_LIVE = 5000
ADD_SCENARIO = 5300
ADD_MUSEUM = 14000


def _rows(conn: sqlite3.Connection, sql: str, args=()):
    conn.row_factory = sqlite3.Row
    return [dict(r) for r in conn.execute(sql, args)]


def _walk(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, dict):
        if "add_type" in value and "item_id" in value:
            try:
                yield int(value["add_type"]), int(value["item_id"]), path, value
            except (TypeError, ValueError):
                pass
        for key, child in value.items():
            yield from _walk(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, path + (str(index),))


def _initial_units(login_py: Path) -> set[int]:
    tree = ast.parse(login_py.read_text(encoding="utf-8"))
    template: list[int] = []
    centers: list[int] = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "TEMPLATE_DECK":
                template = ast.literal_eval(node.value)
            elif target.id == "INITIAL_UNIT_IDS":
                centers = [value for group in ast.literal_eval(node.value) for value in group]
    return {int(value) for value in template if int(value)} | {int(value) for value in centers}


def _source_call_sites(source_root: Path) -> dict[str, list[dict[str, Any]]]:
    needles = {
        "museum": "museum.unlock",
        "main_scenario": "scenario.unlock",
        "side_story": "subscenario.unlock",
        "normal_live": "unlock_normal_live",
        "album": "album.update",
    }
    result: dict[str, list[dict[str, Any]]] = {}
    for name, needle in needles.items():
        hits: list[dict[str, Any]] = []
        for path in (source_root / "npps4").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                if needle in line:
                    hits.append(
                        {
                            "file": str(path.relative_to(source_root)),
                            "line": number,
                            "text": line.strip(),
                        }
                    )
        result[name] = hits
    return result


def build(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.source_root)
    server = json.loads(Path(args.server_data).read_text(encoding="utf-8"))
    rewards = list(_walk(server))
    by_add: dict[int, list[tuple[int, tuple[str, ...], dict[str, Any]]]] = collections.defaultdict(list)
    for add_type, item_id, path, row in rewards:
        by_add[add_type].append((item_id, path, row))

    with sqlite3.connect(args.museum_db) as db:
        museum = {int(r["museum_contents_id"]): r for r in _rows(db, "SELECT * FROM museum_contents_m")}
    with sqlite3.connect(args.client_master) as db:
        scenarios = {int(r["scenario_id"]) for r in _rows(db, "SELECT scenario_id FROM scenario_m")}
        tracks = {int(r["live_track_id"]) for r in _rows(db, "SELECT live_track_id FROM live_track_m")}
        setting = {
            int(r["live_setting_id"]): int(r["live_track_id"])
            for r in _rows(db, "SELECT live_setting_id, live_track_id FROM live_setting_m")
        }
        default_live = {
            setting[int(r["live_setting_id"])]
            for r in _rows(db, "SELECT live_setting_id FROM normal_live_m WHERE default_unlocked_flag=1")
            if int(r["live_setting_id"]) in setting
        }
    with sqlite3.connect(args.game_master) as db:
        units = {int(r["unit_id"]) for r in _rows(db, "SELECT unit_id FROM unit_m")}
        subs = {
            int(r["subscenario_id"]): int(r["unit_id"])
            for r in _rows(db, "SELECT subscenario_id, unit_id FROM subscenario_m")
        }

    museum_route_details: list[dict[str, Any]] = []
    for item_id, path, _row in by_add[ADD_MUSEUM]:
        source_name = path[0] if path else "unknown"
        detail: dict[str, Any] = {
            "museum_contents_id": item_id,
            "source": source_name,
            "path": list(path),
        }
        if source_name == "achievement_reward" and len(path) > 1:
            try:
                index = int(path[1])
                detail["achievement_reward_index"] = index
                detail["achievement_id"] = int(server["achievement_reward"][index]["achievement_id"])
            except (KeyError, IndexError, TypeError, ValueError):
                pass
        museum_route_details.append(detail)
    museum_routes = {row["museum_contents_id"] for row in museum_route_details} & set(museum)
    museum_achievement = {
        row["museum_contents_id"]
        for row in museum_route_details
        if row["source"] == "achievement_reward"
    } & set(museum)
    museum_sticker = {
        row["museum_contents_id"]
        for row in museum_route_details
        if row["source"] == "sticker_shop"
    } & set(museum)

    initial_scenarios = {1, 2, 3, 184, 185, 186, 187, 188} & scenarios
    scenario_rewards = {item_id for item_id, _path, _row in by_add[ADD_SCENARIO]} & scenarios
    scenario_routes = initial_scenarios | scenario_rewards

    default_ids = ({1} | default_live) & tracks
    live_rewards = {item_id for item_id, _path, _row in by_add[ADD_LIVE]} & tracks
    live_routes = default_ids | live_rewards

    secretbox_units: set[int] = set()
    for box in server.get("secretbox_data", []):
        for pool in box.get("rarity_pools", []):
            for value in pool:
                try:
                    secretbox_units.add(int(value))
                except (TypeError, ValueError):
                    pass
    reward_units = {item_id for item_id, _path, _row in by_add[ADD_UNIT]} & units
    initial_unit_ids = _initial_units(source / "npps4/game/login.py") & units
    secretbox_units &= units
    unit_routes = secretbox_units | reward_units | initial_unit_ids
    sub_routes = {sub_id for sub_id, unit_id in subs.items() if unit_id in unit_routes}

    result = {
        "format_version": 2,
        "scope": "preserved upstream NPPS4 source + bundled server_data + supplied final GL/CN client masters",
        "museum": {
            "all_ids": sorted(museum),
            "known_gameplay_unlock_ids": sorted(museum_routes),
            "known_achievement_unlock_ids": sorted(museum_achievement),
            "known_sticker_shop_unlock_ids": sorted(museum_sticker),
            "statically_unreachable_ids": sorted(set(museum) - museum_routes),
            "route_details": museum_route_details,
        },
        "main_scenario": {
            "all_ids": sorted(scenarios),
            "initial_ids": sorted(initial_scenarios),
            "reward_ids": sorted(scenario_rewards),
            "known_gameplay_unlock_ids": sorted(scenario_routes),
            "statically_unreachable_ids": sorted(scenarios - scenario_routes),
        },
        "side_story": {
            "all_ids": sorted(subs),
            "known_gameplay_unlock_ids": sorted(sub_routes),
            "statically_unreachable_ids": sorted(set(subs) - sub_routes),
            "unreachable_unit_map": {str(key): subs[key] for key in sorted(set(subs) - sub_routes)},
        },
        "live": {
            "all_ids": sorted(tracks),
            "default_ids": sorted(default_ids),
            "reward_ids": sorted(live_rewards),
            "known_gameplay_unlock_ids": sorted(live_routes),
            "statically_unreachable_ids": sorted(tracks - live_routes),
        },
        "album": {
            "all_unit_ids": sorted(units),
            "secretbox_unit_ids": sorted(secretbox_units),
            "reward_unit_ids": sorted(reward_units),
            "initial_unit_ids": sorted(initial_unit_ids),
            "known_gameplay_obtainable_unit_ids": sorted(unit_routes),
            "statically_unobtainable_unit_ids": sorted(units - unit_routes),
        },
        "source_unlock_call_sites": _source_call_sites(source),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--server-data", required=True)
    parser.add_argument("--client-master", required=True)
    parser.add_argument("--game-master", required=True)
    parser.add_argument("--museum-db", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build(args)
    for key in ("museum", "main_scenario", "side_story", "live"):
        section = result[key]
        print(
            f"{key}: all={len(section['all_ids'])} "
            f"route={len(section['known_gameplay_unlock_ids'])} "
            f"archive={len(section['statically_unreachable_ids'])}"
        )
    album = result["album"]
    print(
        f"album: all={len(album['all_unit_ids'])} "
        f"obtainable={len(album['known_gameplay_obtainable_unit_ids'])} "
        f"archive={len(album['statically_unobtainable_unit_ids'])}"
    )


if __name__ == "__main__":
    main()
