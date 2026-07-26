from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYROOT = ROOT / "app" / "src" / "main" / "python" / "npps4"

def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")

contract_path = PYROOT / "assets" / "accessory" / "accessory_tab_list.json"
data = json.loads(contract_path.read_text(encoding="utf-8"))
require(len(data) == 4, "tab count")
expected_ids = [
    list(range(1, 10)),
    list(range(101, 110)),
    [201, 202, 203, 204, 205, 206, 207, 208, 209, 212, 213, 214],
    list(range(301, 310)),
]
expected_assets = [
    list(range(1, 10)),
    list(range(10, 19)),
    list(range(24, 36)),
    [19, 20, 21, 22, 23, 36, 37, 38, 39],
]
seen_ids: set[int] = set()
seen_assets: set[str] = set()
for index, tab in enumerate(data):
    ids = [entry["unit_type_id"] for entry in tab["asset_list"]]
    assets = [entry["asset_path"] for entry in tab["asset_list"]]
    require(ids == expected_ids[index], f"unit mapping {index}")
    require(assets == [f"assets/image/accessory/list/list_{n}.png" for n in expected_assets[index]], f"asset mapping {index}")
    require(not seen_ids.intersection(ids), f"duplicate units {index}")
    require(not seen_assets.intersection(assets), f"duplicate assets {index}")
    seen_ids.update(ids); seen_assets.update(assets)
require(not any(re.search(r"list_(4[0-9]|[5-9][0-9])\\.png$", path) for path in seen_assets), "nonexistent list_40+ advertised")

unit_source = (PYROOT / "game" / "unit.py").read_text(encoding="utf-8")
accessory_source = (PYROOT / "system" / "accessory.py").read_text(encoding="utf-8")
ast.parse(unit_source); ast.parse(accessory_source)
for token in (
    "list[int] | list[list[int]]",
    "create_from_unit_groups",
    "UnitCreatedAccessoryGL",
    'context.profile.value == "cn"',
    '"reward_box_flag": entry_reward_flag',
):
    require(token in unit_source + accessory_source, f"missing implementation token: {token}")
require("_FALLBACK_TABS" not in accessory_source, "arithmetic fallback remains")
require("resources.files(\"npps4.assets.accessory\")" in accessory_source, "package resource loader missing")

print("PASS: v5.08 accessory tab and GL auto-create contract guard")
