#!/usr/bin/env python3
"""Resolve the pydantic-core version required by the selected Pydantic v2 line.

This uses pip's resolver in dry-run mode so the Android build doesn't hard-code
an arbitrary pydantic-core version. The exact pydantic and pydantic-core pins are
written to app/src/main/python/constraints-android.txt by the shell wrapper.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def norm_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pydantic-spec", default="pydantic>=2.8,<3")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--json-out", required=True)
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="pydantic-resolve-") as td:
        report = Path(td) / "report.json"
        cmd = [
            args.python,
            "-m",
            "pip",
            "install",
            "--dry-run",
            "--ignore-installed",
            "--report",
            str(report),
            args.pydantic_spec,
        ]
        subprocess.run(cmd, check=True)
        data: dict[str, Any] = json.loads(report.read_text(encoding="utf-8"))

    found: dict[str, str] = {}
    for item in data.get("install", []):
        meta = item.get("metadata") or {}
        name = norm_name(meta.get("name", ""))
        version = meta.get("version")
        if name and version:
            found[name] = version

    pydantic_version = found.get("pydantic")
    core_version = found.get("pydantic-core")
    if not pydantic_version or not core_version:
        print("Could not resolve both pydantic and pydantic-core from pip report.", file=sys.stderr)
        print(json.dumps(found, indent=2), file=sys.stderr)
        return 2

    out = {
        "pydantic": pydantic_version,
        "pydantic_core": core_version,
        "pydantic_spec": args.pydantic_spec,
    }
    Path(args.json_out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
