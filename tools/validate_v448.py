#!/usr/bin/env python3
from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
py_root = root / "app/src/main/python"
museum_system = py_root / "npps4/system/museum.py"
editor_source = root / "app/src/main/java/moe/honoka/npps4wrapper/ConfigEditorActivity.kt"
museum_db = py_root / "npps4/assets/cn_museum_bridge/museum.server.db"

errors: list[str] = []

def require(value: bool, message: str) -> None:
    if not value:
        errors.append(message)

source = museum_system.read_text(encoding="utf-8")
ast.parse(source)
require("context.db.museum.get(museum.MuseumContents" not in source, "museum unlock still loads the full ORM entity")
require("sqlalchemy.select(museum.MuseumContents)" not in source, "museum info still selects the full ORM entity")
require("MuseumContents.smile_buff" in source and "MuseumContents.pure_buff" in source and "MuseumContents.cool_buff" in source,
        "museum info does not select the portable buff columns")
require("if not contents_id_list:" in source, "empty Museum unlock list is not short-circuited")

with sqlite3.connect(museum_db) as db:
    columns = {row[1] for row in db.execute("PRAGMA table_info(museum_contents_m)")}
    require("_encryption_release_id" not in columns, "bundled CN Museum DB unexpectedly contains the GL-only column")
    require({"museum_contents_id", "smile_buff", "pure_buff", "cool_buff"}.issubset(columns),
            "bundled CN Museum DB is missing portable Museum columns")
    ids = [row[0] for row in db.execute("SELECT museum_contents_id FROM museum_contents_m ORDER BY museum_contents_id LIMIT 3")]
    if ids:
        marks = ",".join("?" for _ in ids)
        rows = list(db.execute(
            f"SELECT smile_buff, pure_buff, cool_buff FROM museum_contents_m WHERE museum_contents_id IN ({marks})",
            ids,
        ))
        require(len(rows) == len(ids), "portable Museum buff query did not return the expected rows")

kotlin = editor_source.read_text(encoding="utf-8")
require("class DragScrollbarView" in kotlin, "custom draggable scrollbar view is missing")
require("override fun onTouchEvent" in kotlin, "scrollbar has no touch/drag handler")
require("onPositionChanged?.invoke" in kotlin, "scrollbar drag does not publish its position")
require("editor.scrollTo" in kotlin, "scrollbar position is not connected to EditText scrolling")
require("isVerticalScrollBarEnabled = false" in kotlin and "isHorizontalScrollBarEnabled = false" in kotlin,
        "non-draggable framework scrollbars are still enabled")
require("垂直滚动条，可上下拖动" in kotlin and "水平滚动条，可左右拖动" in kotlin,
        "draggable scrollbar accessibility descriptions are missing")

if errors:
    print("v4.48 validation FAILED")
    for error in errors:
        print("-", error)
    raise SystemExit(1)

print("v4.48 validation OK")
print(f"CN Museum rows checked: {len(ids)} sample rows; schema columns: {len(columns)}")
print("Draggable vertical/horizontal scrollbar wiring: present")
