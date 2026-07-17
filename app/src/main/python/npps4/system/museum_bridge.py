"""Optional account-side access policy for a generated CN Museum bridge.

The default policy is deliberately ``normal``: importing the complete catalog
must not silently replace NPPS4's ordinary achievement/gameplay unlocks.  The
``archive`` policy grants every merged row for which no route exists in the
preserved upstream NPPS4 source plus bundled server_data.  ``all`` grants the
entire merged catalog.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import sqlalchemy

from .. import idol
from .. import util
from ..config import config
from ..db import main
from ..db import museum as museum_db


@dataclass(kw_only=True)
class MuseumBridgeSyncResult:
    policy: str = "normal"
    requested: int = 0
    inserted: int = 0
    applied: bool = False


def _absolute(path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(config.ROOT_DIR, path))


def _load_manifest() -> dict | None:
    path = _absolute(config.CONFIG_DATA.download.cn_archive.museum_bridge_manifest)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            value = json.load(fh)
        return value if isinstance(value, dict) else None
    except Exception as exc:
        util.log(
            "CN Museum bridge",
            f"Cannot read manifest {path}: {type(exc).__name__}: {exc}",
            severity=util.logging.WARNING,
        )
        return None


def _ids_for_policy(manifest: dict, policy: str) -> set[int]:
    if policy == "archive":
        # v4.45 manifest: all merged rows without a preserved route.  Keep the
        # v4.44 imported-only key as a compatibility fallback for custom builds.
        source = manifest.get(
            "statically_unreachable_ids",
            manifest.get("estimated_unreachable_imported_ids", []),
        )
    elif policy == "all":
        source = manifest.get("imported_museum_content_ids", [])
        # Include original CN rows too when the operator explicitly requested all.
        source = list(source) + list(manifest.get("cn_original_museum_content_ids", []))
    else:
        return set()
    result: set[int] = set()
    for value in source:
        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue
    return result


async def sync_once(context: idol.BasicSchoolIdolContext, user: main.User) -> MuseumBridgeSyncResult:
    policy = str(config.CONFIG_DATA.download.cn_archive.museum_bridge_unlock_policy or "normal").strip().lower()
    result = MuseumBridgeSyncResult(policy=policy)
    if not config.is_cn_compat() or policy == "normal" or user.tutorial_state != -1:
        return result
    if policy not in {"archive", "all"}:
        util.log("CN Museum bridge", f"Unknown unlock policy {policy!r}; using normal", severity=util.logging.WARNING)
        return result

    manifest = _load_manifest()
    if manifest is None:
        return result
    requested = _ids_for_policy(manifest, policy)
    result.requested = len(requested)
    if not requested:
        return result

    digest = str(manifest.get("merged_encrypted_sha256") or manifest.get("merged_plain_sha256") or "unknown")[:16]
    semantics = int(manifest.get("format_version") or 1)
    grant_key = f"cn_museum_bridge:v{semantics}:{policy}:{digest}"
    grant_q = sqlalchemy.select(main.ContentAccessGrant).where(
        main.ContentAccessGrant.user_id == user.id,
        main.ContentAccessGrant.grant_key == grant_key,
    )
    if (await context.db.main.execute(grant_q)).scalar() is not None:
        return result

    valid = set(
        (
            await context.db.museum.execute(
                sqlalchemy.select(museum_db.MuseumContents.museum_contents_id).where(
                    museum_db.MuseumContents.museum_contents_id.in_(requested)
                )
            )
        ).scalars()
    )
    existing = set(
        (
            await context.db.main.execute(
                sqlalchemy.select(main.MuseumUnlock.museum_contents_id).where(
                    main.MuseumUnlock.user_id == user.id,
                    main.MuseumUnlock.museum_contents_id.in_(valid),
                )
            )
        ).scalars()
    )
    for item_id in sorted(valid - existing):
        context.db.main.add(main.MuseumUnlock(user_id=user.id, museum_contents_id=item_id))
        result.inserted += 1

    context.db.main.add(
        main.ContentAccessGrant(user_id=user.id, grant_key=grant_key, grant_version=1)
    )
    await context.db.main.flush()
    result.applied = True
    util.log(
        "CN Museum bridge access sync",
        f"user_id={user.id}",
        f"policy={policy}",
        f"requested={result.requested}",
        f"valid={len(valid)}",
        f"inserted={result.inserted}",
        severity=util.logging.WARNING,
    )
    return result
