#!/usr/bin/env python3
"""Fetch missing SIF1 Android assets or databases from an NPPS4-DLAPI mirror.

No third-party Python modules are required.  The script is designed for a CN
NPPS4 setup: it never changes the CN archive/version.  It only downloads raw GL
assets into an extracted overlay directory, preserving their original paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SERVER = "https://ll.sif.moe/npps4_dlapi"
EMPTY_MD5 = hashlib.md5(b"").hexdigest()
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def api_url(base: str, endpoint: str) -> str:
    return urllib.parse.urljoin(base.rstrip("/") + "/", endpoint.lstrip("/"))


def request_json(base: str, endpoint: str, payload: dict[str, Any] | None = None, shared_key: str = ""):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"User-Agent": "NPPS4-GL-overlay-toolkit/1.0"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if shared_key:
        headers["DLAPI-Shared-Key"] = urllib.parse.quote(shared_key)
    req = urllib.request.Request(api_url(base, endpoint), data=data, headers=headers, method="GET" if data is None else "POST")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def read_text_auto(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-16", "utf-16le", "utf-8-sig", "utf-8"):
        try:
            text = raw.decode(enc)
            if "\x00" not in text[:1000]:
                return text
        except UnicodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def safe_rel(path: str) -> str:
    path = os.path.normpath(path.replace("\\", "/")).replace("\\", "/").lstrip("/")
    if path in ("", ".") or path.startswith("../") or "/../" in f"/{path}/":
        raise ValueError(f"unsafe path: {path!r}")
    return path


def candidates(path: str, language_fallback: bool) -> list[str]:
    path = safe_rel(path)
    out = [path]
    if language_fallback:
        if path.startswith("en/"):
            out.append(path[3:])
        elif path.startswith("assets/"):
            out.append("en/" + path)
    return list(dict.fromkeys(out))


def getfile_rows(base: str, files: list[str], platform: int, shared_key: str) -> list[dict[str, Any]]:
    rows = request_json(base, "api/v1/getfile", {"files": files, "platform": platform}, shared_key)
    if not isinstance(rows, list) or len(rows) != len(files):
        raise RuntimeError("getfile returned unexpected response shape")
    return rows


def valid_row(row: dict[str, Any]) -> bool:
    size = int(row.get("size", 0) or 0)
    sums = row.get("checksums") or {}
    return size > 0 and bool(row.get("url")) and not (
        str(sums.get("md5", "")).lower() == EMPTY_MD5 and str(sums.get("sha256", "")).lower() == EMPTY_SHA256
    )


def download_verified(url: str, target: Path, expected: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=target.name + ".", suffix=".part", dir=target.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    total = 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NPPS4-GL-overlay-toolkit/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                md5.update(chunk)
                sha256.update(chunk)
        expected_size = int(expected.get("size", 0) or 0)
        sums = expected.get("checksums") or {}
        if expected_size and total != expected_size:
            raise RuntimeError(f"size mismatch: expected {expected_size}, got {total}")
        if sums.get("md5") and md5.hexdigest().lower() != str(sums["md5"]).lower():
            raise RuntimeError("MD5 mismatch")
        if sums.get("sha256") and sha256.hexdigest().lower() != str(sums["sha256"]).lower():
            raise RuntimeError("SHA256 mismatch")
        os.replace(tmp, target)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def chunked(seq: list[str], n: int) -> Iterable[list[str]]:
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def fetch_paths(paths: list[str], out: Path, base: str, platform: int, shared_key: str, language_fallback: bool) -> dict[str, Any]:
    paths = list(dict.fromkeys(safe_rel(p) for p in paths))
    report: dict[str, Any] = {"server": base, "platform": platform, "output": str(out), "downloaded": [], "existing": [], "missing": [], "failed": []}
    pending = []
    for path in paths:
        target = out / ("Android" if platform == 2 else "iOS") / path
        if target.is_file():
            report["existing"].append(path)
        else:
            pending.append(path)

    for group in chunked(pending, 50):
        candidate_map = {p: candidates(p, language_fallback) for p in group}
        flat = list(dict.fromkeys(c for p in group for c in candidate_map[p]))
        rows = getfile_rows(base, flat, platform, shared_key)
        by_candidate = dict(zip(flat, rows, strict=True))
        for path in group:
            chosen = next(((c, by_candidate[c]) for c in candidate_map[path] if valid_row(by_candidate[c])), None)
            if chosen is None:
                print(f"[MISS] {path}")
                report["missing"].append(path)
                continue
            remote, row = chosen
            target = out / ("Android" if platform == 2 else "iOS") / path
            try:
                print(f"[GET ] {path} <- {remote} ({row.get('size', 0)} bytes)")
                download_verified(str(row["url"]), target, row)
                report["downloaded"].append({"path": path, "remote_path": remote, "size": int(row.get("size", 0) or 0)})
            except Exception as exc:
                print(f"[FAIL] {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
                report["failed"].append({"path": path, "error": f"{type(exc).__name__}: {exc}"})
    return report


def paths_from_log(path: Path, include: str) -> list[str]:
    text = read_text_auto(path)
    rx = re.compile(r'GET /cn-extracted/(?:Android|iOS)/([^ ?]+).*?404 Not Found')
    filt = re.compile(include)
    return [urllib.parse.unquote(m.group(1)) for m in rx.finditer(text) if filt.search(m.group(1))]


def cmd_probe(args):
    info = request_json(args.server, "api/publicinfo", shared_key=args.shared_key)
    print(json.dumps(info, ensure_ascii=False, indent=2))


def cmd_from_log(args):
    paths = paths_from_log(Path(args.log), args.include)
    if not paths:
        raise SystemExit("日志中没有找到匹配的 /cn-extracted/... 404 路径")
    report = fetch_paths(paths, Path(args.output), args.server, args.platform, args.shared_key, not args.no_language_fallback)
    report_path = Path(args.output) / "overlay-fetch-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告：{report_path}")
    print(f"下载 {len(report['downloaded'])}，已存在 {len(report['existing'])}，远端缺失 {len(report['missing'])}，失败 {len(report['failed'])}")


def cmd_from_list(args):
    paths = [line.strip() for line in Path(args.list).read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    report = fetch_paths(paths, Path(args.output), args.server, args.platform, args.shared_key, not args.no_language_fallback)
    report_path = Path(args.output) / "overlay-fetch-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告：{report_path}")


def cmd_getdb(args):
    headers = {"User-Agent": "NPPS4-GL-overlay-toolkit/1.0"}
    if args.shared_key:
        headers["DLAPI-Shared-Key"] = urllib.parse.quote(args.shared_key)
    req = urllib.request.Request(api_url(args.server, f"api/v1/getdb/{args.name}"), headers=headers)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if not data.startswith(b"SQLite format 3\x00"):
        raise RuntimeError("downloaded database is not SQLite3")
    out.write_bytes(data)
    print(f"保存数据库：{out} ({len(data)} bytes)")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--server", default=DEFAULT_SERVER)
    p.add_argument("--shared-key", default="")
    sub = p.add_subparsers(dest="command", required=True)
    sp = sub.add_parser("probe", help="检查 DLAPI 公共信息")
    sp.set_defaults(func=cmd_probe)
    sp = sub.add_parser("from-log", help="从 Logcat 的 /cn-extracted 404 自动拉取缺失文件")
    sp.add_argument("log")
    sp.add_argument("output", help="overlay 根目录；内部会创建 Android/ 或 iOS/")
    sp.add_argument("--platform", type=int, choices=(1,2), default=2)
    sp.add_argument("--include", default=r".*", help="仅下载路径匹配此正则的文件，例如 secretbox|museum")
    sp.add_argument("--no-language-fallback", action="store_true")
    sp.set_defaults(func=cmd_from_log)
    sp = sub.add_parser("from-list", help="从文本路径列表下载")
    sp.add_argument("list")
    sp.add_argument("output")
    sp.add_argument("--platform", type=int, choices=(1,2), default=2)
    sp.add_argument("--no-language-fallback", action="store_true")
    sp.set_defaults(func=cmd_from_list)
    sp = sub.add_parser("getdb", help="下载服务端解密后的 GL master DB（用于分析/转换，不可直接当 CN 客户端更新包）")
    sp.add_argument("name")
    sp.add_argument("output")
    sp.set_defaults(func=cmd_getdb)
    return p


def main():
    args = build_parser().parse_args()
    try:
        args.func(args)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {body[:500]}") from exc


if __name__ == "__main__":
    main()
