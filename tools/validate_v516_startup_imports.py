from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app" / "src" / "main" / "python"
CHANGED = [
    "npps4/system/secretbox.py",
    "npps4/system/exchange.py",
    "npps4/system/accessory.py",
    "npps4/serialcode/func.py",
    "npps4/game/banner.py",
    "npps4/game/secretbox.py",
    "npps4/webview/secretbox.py",
    "npps4/data/schema.py",
]

for relative in CHANGED:
    path = ROOT / relative
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

path = ROOT / "npps4/system/secretbox.py"
tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
imports: set[str] = set()
for node in tree.body:
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.add(alias.asname or alias.name.split(".", 1)[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            imports.add(alias.asname or alias.name)

required = {"common", "sqlalchemy", "unit_db", "client_catalogue"}
missing = sorted(required - imports)
if missing:
    raise SystemExit(f"secretbox.py missing import-time dependencies: {missing}")

source = path.read_text(encoding="utf-8")
for marker in (
    '@common.context_cacheable("secretbox_thanks_pools")',
    'sqlalchemy.select(unit_db.Unit.unit_id',
    'client_catalogue.current(context)',
):
    if marker not in source:
        raise SystemExit(f"secretbox.py startup-contract marker missing: {marker}")

print("v5.16 startup import contract: PASS")
