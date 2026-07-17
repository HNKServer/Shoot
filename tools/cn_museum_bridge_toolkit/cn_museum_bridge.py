"""Build a CN-compatible Museum master overlay from CN and community APKs.

The tool never replaces the CN schema with the newer community schema.  It
copies the CN database, preserves every CN row on primary-key conflicts, adds
only community rows whose category is known to the CN client, strips columns
which do not exist in CN 9.7.1, re-encrypts with the original CN Honky v4
metadata, and can wrap the result in a real CN 99 update-package template.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

try:
    from . import honky_file
except ImportError:  # standalone execution from copied toolkit
    import honky_file  # type: ignore

MUSEUM_ENTRY = "db/museum/museum.db_"
DANGEROUS_UPDATE_ENTRIES = {
    "server_info.json",
    "config/server_info.json",
    "client_info.json",
    "config/client_info.json",
}
TABLES = (
    "museum_contents_m",
    "museum_menu_m",
    "museum_setting_m",
    "museum_tab_category_m",
    "museum_tab_m",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize(name: str) -> str:
    return name.replace("\\", "/").lstrip("/")


def _appassets_bytes(apk_path: Path) -> bytes:
    with zipfile.ZipFile(apk_path) as apk:
        names = apk.namelist()
        candidates = [n for n in names if _normalize(n).lower().endswith("assets/appassets.zip")]
        if not candidates:
            candidates = [n for n in names if _normalize(n).lower().endswith("appassets.zip")]
        if not candidates:
            raise RuntimeError(f"AppAssets.zip not found in APK: {apk_path}")
        return apk.read(sorted(candidates, key=len)[0])


def encrypted_museum_from_apk(apk_path: str | os.PathLike[str]) -> bytes:
    apk = Path(apk_path).resolve()
    with zipfile.ZipFile(io.BytesIO(_appassets_bytes(apk))) as assets:
        by_normalized = {_normalize(n): n for n in assets.namelist()}
        actual = by_normalized.get(MUSEUM_ENTRY)
        if actual is None:
            raise RuntimeError(f"{MUSEUM_ENTRY} not found in {apk.name}/AppAssets.zip")
        return assets.read(actual)


def _decrypt_sqlite(data: bytes, region: str) -> tuple[bytes, honky_file.HonkyV4Meta]:
    plain, meta = honky_file.decrypt_v4(data, "museum.db_", region)
    if not plain.startswith(b"SQLite format 3\x00"):
        raise RuntimeError(f"decrypted {region} museum file is not SQLite")
    return plain, meta


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _table_schema(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    return [
        {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "pk": int(row[5]),
        }
        for row in conn.execute(f'PRAGMA table_info("{table}")')
    ]


def _rows(conn: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(f'SELECT * FROM "{table}"')]


def _db_report(path: Path) -> dict[str, Any]:
    with sqlite3.connect(path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables: dict[str, Any] = {}
        for table in TABLES:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if exists:
                tables[table] = {
                    "rows": conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0],
                    "columns": _table_schema(conn, table),
                }
        return {"path": str(path), "integrity": integrity, "tables": tables}


def _museum_unlock_routes(server_data: Path | None) -> list[dict[str, Any]]:
    """Find every bundled reward which actually grants ADD_TYPE.MUSEUM.

    v4.44 only inspected achievement_reward and therefore missed the sticker
    shop route for Museum ID 1698.  Walk the entire server_data tree so future
    serial-code, shop or event reward sections are classified automatically.
    """
    if server_data is None or not server_data.is_file():
        return []
    obj = json.loads(server_data.read_text(encoding="utf-8"))
    result: list[dict[str, Any]] = []

    def walk(value: Any, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            if value.get("add_type") == 14000 and "item_id" in value:
                try:
                    item_id = int(value["item_id"])
                except (TypeError, ValueError):
                    pass
                else:
                    route: dict[str, Any] = {
                        "museum_contents_id": item_id,
                        "source": path[0] if path else "unknown",
                        "path": list(path),
                    }
                    if route["source"] == "achievement_reward" and len(path) > 1:
                        try:
                            index = int(path[1])
                            route["achievement_id"] = int(obj["achievement_reward"][index]["achievement_id"])
                        except (KeyError, IndexError, TypeError, ValueError):
                            pass
                    result.append(route)
            for key, child in value.items():
                walk(child, path + (str(key),))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, path + (str(index),))

    walk(obj)
    return result


def _known_normal_unlock_ids(server_data: Path | None) -> set[int]:
    return {int(route["museum_contents_id"]) for route in _museum_unlock_routes(server_data)}


def _json_dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def merge_databases(
    cn_plain: Path,
    gl_plain: Path,
    output_plain: Path,
    report_dir: Path,
    server_data: Path | None = None,
) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cn_plain, output_plain)

    with sqlite3.connect(cn_plain) as cn, sqlite3.connect(gl_plain) as gl:
        cn.row_factory = sqlite3.Row
        gl.row_factory = sqlite3.Row
        cn_schema = {t: _table_schema(cn, t) for t in TABLES}
        gl_schema = {t: _table_schema(gl, t) for t in TABLES}
        cn_categories = {
            int(r["museum_tab_category_id"]): dict(r)
            for r in cn.execute("SELECT * FROM museum_tab_category_m")
        }
        gl_rows = [dict(r) for r in gl.execute("SELECT * FROM museum_contents_m")]
        cn_rows = {
            int(r["museum_contents_id"]): dict(r)
            for r in cn.execute("SELECT * FROM museum_contents_m")
        }

    cn_columns = [c["name"] for c in cn_schema["museum_contents_m"]]
    cn_ids = set(cn_rows)
    gl_ids = {int(r["museum_contents_id"]) for r in gl_rows}
    conflicts: list[dict[str, Any]] = []
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for row in gl_rows:
        item_id = int(row["museum_contents_id"])
        if item_id in cn_rows:
            diff = {
                column: {"cn": cn_rows[item_id].get(column), "gl": row.get(column)}
                for column in cn_columns
                if cn_rows[item_id].get(column) != row.get(column)
            }
            conflicts.append({"museum_contents_id": item_id, "differences": diff, "decision": "keep_cn"})
            continue
        category_id = int(row["museum_tab_category_id"])
        if category_id not in cn_categories:
            skipped.append(
                {
                    "museum_contents_id": item_id,
                    "reason": "category_not_supported_by_cn_client",
                    "museum_tab_category_id": category_id,
                }
            )
            continue
        imported.append({column: row.get(column) for column in cn_columns})

    with sqlite3.connect(output_plain) as out:
        placeholders = ",".join("?" for _ in cn_columns)
        quoted = ",".join(f'"{c}"' for c in cn_columns)
        out.executemany(
            f'INSERT INTO "museum_contents_m" ({quoted}) VALUES ({placeholders})',
            [[row.get(c) for c in cn_columns] for row in imported],
        )
        out.commit()
        integrity = out.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"merged museum SQLite integrity check failed: {integrity}")
        out.execute("VACUUM")

    routes = _museum_unlock_routes(server_data)
    normal_ids = {int(route["museum_contents_id"]) for route in routes}
    imported_ids = {int(r["museum_contents_id"]) for r in imported}
    all_merged_ids = cn_ids | imported_ids
    known_normal = all_merged_ids & normal_ids
    known_normal_imported = imported_ids & normal_ids
    estimated_unreachable = imported_ids - normal_ids
    statically_unreachable = all_merged_ids - normal_ids
    achievement_ids = {
        int(route["museum_contents_id"])
        for route in routes
        if route.get("source") == "achievement_reward"
    } & all_merged_ids
    sticker_shop_ids = {
        int(route["museum_contents_id"])
        for route in routes
        if route.get("source") == "sticker_shop"
    } & all_merged_ids

    resource_paths: set[str] = set()
    for row in imported:
        for key in ("thumbnail_asset", "thumbnail_asset_en"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                resource_paths.add(_normalize(value.strip()))
    with sqlite3.connect(cn_plain) as cn:
        cn.row_factory = sqlite3.Row
        for row in cn.execute("SELECT * FROM museum_menu_m"):
            for key in ("menu_asset", "menu_asset_en"):
                value = row[key]
                if isinstance(value, str) and value.strip():
                    resource_paths.add(_normalize(value.strip()))

    schema_diff: dict[str, Any] = {}
    for table in TABLES:
        cn_names = [c["name"] for c in cn_schema[table]]
        gl_names = [c["name"] for c in gl_schema[table]]
        schema_diff[table] = {
            "cn_only_columns": [x for x in cn_names if x not in gl_names],
            "gl_only_columns": [x for x in gl_names if x not in cn_names],
            "common_columns": [x for x in cn_names if x in gl_names],
        }

    manifest = {
        "format_version": 2,
        "client_region": "cn",
        "client_application_version": "9.7.1",
        "content_version_preserved": "97.4.6",
        "museum_entry": MUSEUM_ENTRY,
        "cn_original_count": len(cn_ids),
        "gl_original_count": len(gl_ids),
        "merged_count": len(cn_ids | gl_ids) - len(skipped),
        "conflict_count": len(conflicts),
        "imported_count": len(imported_ids),
        "skipped_count": len(skipped),
        "cn_original_museum_content_ids": sorted(cn_ids),
        "imported_museum_content_ids": sorted(imported_ids),
        # New exact names. Legacy imported-only fields remain for readers of
        # v4.44 manifests, but archive policy uses the full merged catalog.
        "known_gameplay_unlock_ids": sorted(known_normal),
        "known_achievement_unlock_ids": sorted(achievement_ids),
        "known_sticker_shop_unlock_ids": sorted(sticker_shop_ids),
        "statically_unreachable_ids": sorted(statically_unreachable),
        "museum_unlock_route_details": routes,
        "known_normal_unlock_ids": sorted(known_normal),
        "known_normal_imported_ids": sorted(known_normal_imported),
        "estimated_unreachable_imported_ids": sorted(estimated_unreachable),
        "unlock_policy_default": "normal",
        "notes": [
            "CN rows win on all ID conflicts.",
            "CN lookup/category tables are preserved unchanged.",
            "GL-only _encryption_release_id columns are stripped.",
            "Known normal unlock coverage is recursively derived from all NPPS4 server_data reward sections.",
            "77 entries are achievement rewards and Museum ID 1698 is available from sticker_shop in the bundled data.",
            "statically_unreachable_ids means no route is preserved in upstream NPPS4 source + bundled server_data; historical live-service routes may have existed.",
        ],
    }

    _json_dump(report_dir / "cn_museum_schema.json", cn_schema)
    _json_dump(report_dir / "gl_museum_schema.json", gl_schema)
    _json_dump(report_dir / "museum_schema_diff.json", schema_diff)
    _json_dump(report_dir / "museum_id_conflicts.json", conflicts)
    _json_dump(report_dir / "museum_compatible_rows.json", imported)
    _json_dump(report_dir / "museum_skipped_rows.json", skipped)
    _json_dump(report_dir / "museum_bridge_manifest.json", manifest)
    (report_dir / "museum_resource_manifest.txt").write_text(
        "\n".join(sorted(resource_paths)) + ("\n" if resource_paths else ""), encoding="utf-8"
    )

    summary = f"""NPPS4 CN Museum bridge build summary

CN original rows: {len(cn_ids)}
Community/GL rows: {len(gl_ids)}
ID conflicts kept from CN: {len(conflicts)}
GL-only rows imported: {len(imported_ids)}
Rows skipped as unsupported: {len(skipped)}
Merged rows: {manifest['merged_count']}
Known NPPS4 gameplay unlock IDs: {len(known_normal)}
  Achievement routes: {len(achievement_ids)}
  Sticker-shop routes: {len(sticker_shop_ids)}
Known normal unlock IDs among imported rows: {len(known_normal_imported)}
Merged rows without a preserved normal route: {len(statically_unreachable)}
Imported rows without a preserved normal route: {len(estimated_unreachable)}
Thumbnail/menu resource paths: {len(resource_paths)}

"No preserved route" is a source/data result, not proof that KLab's historical
live service never distributed the content. Runtime policy therefore defaults
to 'normal'. Operators may select 'archive' to grant all merged entries without
a route in the preserved NPPS4 source/data, or 'all' to grant the full catalog.
"""
    (report_dir / "build-summary.txt").write_text(summary, encoding="utf-8")
    return manifest


def _clone_info(src: zipfile.ZipInfo, filename: str | None = None) -> zipfile.ZipInfo:
    dst = zipfile.ZipInfo(filename or src.filename, src.date_time)
    for attr in (
        "compress_type", "comment", "extra", "create_system", "create_version",
        "extract_version", "flag_bits", "internal_attr", "external_attr", "volume",
    ):
        setattr(dst, attr, getattr(src, attr))
    return dst


def select_template(archive_dir: Path) -> Path:
    candidates: list[tuple[int, Path]] = []
    for path in archive_dir.glob("99_0_*.zip"):
        try:
            order = int(path.stem.split("_")[2])
        except (IndexError, ValueError):
            continue
        if order in (115, 116):
            continue
        candidates.append((order, path))
    if not candidates:
        raise RuntimeError(f"no real 99_0_*.zip template found in {archive_dir}")
    preferred = {113: 1000, 114: 900, 112: 800}
    candidates.sort(key=lambda x: (preferred.get(x[0], x[0]), x[0]), reverse=True)
    return candidates[0][1]


def build_update_zip(template: Path, encrypted_db: bytes, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_zip.with_suffix(output_zip.suffix + ".tmp")
    with zipfile.ZipFile(template, "r") as src, zipfile.ZipFile(tmp, "w") as dst:
        museum_info: zipfile.ZipInfo | None = None
        for info in src.infolist():
            normalized = _normalize(info.filename)
            if normalized == MUSEUM_ENTRY:
                museum_info = info
                continue
            if normalized in DANGEROUS_UPDATE_ENTRIES:
                continue
            if info.is_dir():
                dst.writestr(_clone_info(info), b"")
            else:
                dst.writestr(_clone_info(info), src.read(info.filename))
        if museum_info is None:
            museum_info = zipfile.ZipInfo(MUSEUM_ENTRY)
            museum_info.compress_type = zipfile.ZIP_DEFLATED
        dst.writestr(_clone_info(museum_info, MUSEUM_ENTRY), encrypted_db)
    os.replace(tmp, output_zip)
    with zipfile.ZipFile(output_zip) as check:
        if check.testzip() is not None or MUSEUM_ENTRY not in {_normalize(n) for n in check.namelist()}:
            raise RuntimeError("generated update ZIP failed validation")


def build_all(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.output_dir).resolve()
    report = out / "report"
    out.mkdir(parents=True, exist_ok=True)

    cn_enc = encrypted_museum_from_apk(args.cn_apk)
    gl_enc = encrypted_museum_from_apk(args.gl_apk)
    cn_plain, cn_meta = _decrypt_sqlite(cn_enc, "cn")
    # Community/WW final client uses the post-merge JP Honky prefix for this DB.
    try:
        gl_plain, gl_meta = _decrypt_sqlite(gl_enc, "jp")
    except Exception:
        gl_plain, gl_meta = _decrypt_sqlite(gl_enc, "ww")

    cn_plain_path = out / "cn.museum.original.db"
    gl_plain_path = out / "gl.museum.original.db"
    merged_plain_path = out / "museum.server.db"
    _write_bytes(cn_plain_path, cn_plain)
    _write_bytes(gl_plain_path, gl_plain)
    manifest = merge_databases(
        cn_plain_path,
        gl_plain_path,
        merged_plain_path,
        report,
        Path(args.server_data).resolve() if args.server_data else None,
    )

    merged_plain = merged_plain_path.read_bytes()
    encrypted_merged = honky_file.encrypt_v4(merged_plain, cn_meta, "museum.db_")
    verify, verify_meta = honky_file.decrypt_v4(encrypted_merged, "museum.db_", "cn")
    if verify != merged_plain:
        raise RuntimeError("CN Museum re-encryption round trip failed")
    encrypted_path = out / "museum.db_"
    _write_bytes(encrypted_path, encrypted_merged)

    manifest.update(
        {
            "cn_honky": asdict(cn_meta),
            "gl_honky": asdict(gl_meta),
            "cn_encrypted_sha256": _sha256(cn_enc),
            "gl_encrypted_sha256": _sha256(gl_enc),
            "merged_plain_sha256": _sha256(merged_plain),
            "merged_encrypted_sha256": _sha256(encrypted_merged),
            "server_db": "museum.server.db",
            "encrypted_db": "museum.db_",
        }
    )

    template: Path | None = None
    if args.template_zip:
        template = Path(args.template_zip).resolve()
    elif args.archive_dir:
        template = select_template(Path(args.archive_dir).resolve())
    if template is not None:
        update_zip = out / "99_0_116.zip"
        build_update_zip(template, encrypted_merged, update_zip)
        manifest["template_zip"] = str(template)
        manifest["update_zip"] = str(update_zip)
        manifest["update_zip_sha256"] = _sha256(update_zip.read_bytes())

    _json_dump(out / "museum_bridge_manifest.json", manifest)
    _json_dump(report / "museum_bridge_manifest.json", manifest)
    return manifest


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cn-apk", required=True, help="CN 9.7.1 APK")
    p.add_argument("--gl-apk", required=True, help="community/global APK containing the complete Museum DB")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--archive-dir", help="CN flat archive directory containing real 99_0_*.zip packages")
    p.add_argument("--template-zip", help="explicit real CN 99 package template")
    p.add_argument("--server-data", help="NPPS4 server_data.json used to estimate normal Museum unlock coverage")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    manifest = build_all(args)
    print(json.dumps({
        "ok": True,
        "merged_count": manifest["merged_count"],
        "imported_count": manifest["imported_count"],
        "skipped_count": manifest["skipped_count"],
        "output_dir": str(Path(args.output_dir).resolve()),
        "update_zip": manifest.get("update_zip"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
