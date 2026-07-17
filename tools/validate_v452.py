#!/usr/bin/env python3
from __future__ import annotations

import argparse
import compileall
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def require(cond: bool, message: str, errors: list[str]) -> None:
    if not cond:
        errors.append(message)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('root', type=Path)
    ap.add_argument('--p113', type=Path)
    ap.add_argument('--p114', type=Path)
    ap.add_argument('--p115', type=Path)
    ns = ap.parse_args()
    root = ns.root.resolve()
    pyroot = root / 'app/src/main/python'
    npps4 = pyroot / 'npps4'
    errors: list[str] = []

    require(compileall.compile_dir(pyroot, quiet=1), 'Python compileall failed', errors)

    banner = (npps4 / 'game/banner.py').read_text(encoding='utf-8')
    for term in (
        'assets/image/webview/npps4_data_transfer.png',
        'assets/image/webview/npps4_manga.png',
        'webview_url=f"/transfer?t={token}"',
        'webview_url="/manga"',
        'back_side=False',
    ):
        require(term in banner, f'CN banner contract missing {term}', errors)
    cn_block = banner.split('if capabilities.profile == "cn":', 1)[1].split('else:', 1)[0]
    require('banner_type=18' not in cn_block, 'CN block still advertises type-18', errors)

    data_py = (npps4 / 'config/data.py').read_text(encoding='utf-8')
    require('client_version: Annotated[str' in data_py and '= "97.4.6"' in data_py, 'CN retained version is not 97.4.6', errors)
    require('99_0_116.zip' in data_py and 'museum_bridge_unlock_policy: str = "all"' in data_py,
            '116/all default configuration missing', errors)

    build_info = (npps4 / 'build_info.py').read_text(encoding='utf-8')
    gradle = (root / 'app/build.gradle').read_text(encoding='utf-8')
    require('v4.52-cn-home-museum-direct-fix' in build_info, 'v4.52 build id missing', errors)
    require('versionCode 434' in gradle and "versionName '0.4.32.1'" in gradle, 'Android version markers wrong', errors)

    all_text = '\n'.join(
        p.read_text(encoding='utf-8', errors='ignore')
        for p in root.rglob('*')
        if p.is_file() and p != Path(__file__).resolve() and p.suffix in {'.py', '.kt', '.toml', '.md'} and '__pycache__' not in p.parts
    )
    allowed_117 = all_text.count('99_0_117.zip')
    require(allowed_117 == 1, f'117 appears outside the single migration cleanup mapping: {allowed_117}', errors)
    require('client_version = "97.4.7"' not in all_text, '97.4.7 remains as an active configuration', errors)

    bridge = npps4 / 'assets/cn_museum_bridge'
    server_db = bridge / 'museum.server.db'
    with sqlite3.connect(server_db) as db:
        count = int(db.execute('select count(*) from museum_contents_m').fetchone()[0])
        integrity = db.execute('pragma integrity_check').fetchone()[0]
    require(count == 1360 and integrity == 'ok', f'museum.server.db invalid: rows={count}, integrity={integrity}', errors)

    sys.path.insert(0, str(pyroot))
    from npps4.tools import honky_file  # noqa: E402
    from npps4.tools.cn_museum_bridge import build_update_zip  # noqa: E402

    encrypted = (bridge / 'museum.db_').read_bytes()
    plain, meta = honky_file.decrypt_v4(encrypted, 'museum.db_', 'cn')
    require(meta.region == 'cn' and plain.startswith(b'SQLite format 3\x00'), 'client Museum DB is not CN Honky/SQLite', errors)
    with tempfile.NamedTemporaryFile(suffix='.db') as fh:
        fh.write(plain); fh.flush()
        with sqlite3.connect(fh.name) as db:
            client_count = int(db.execute('select count(*) from museum_contents_m').fetchone()[0])
            client_integrity = db.execute('pragma integrity_check').fetchone()[0]
    require(client_count == 1360 and client_integrity == 'ok', 'decrypted client Museum DB invalid', errors)

    transfer_png = bridge / 'npps4_data_transfer.png'
    manga_png = bridge / 'npps4_manga.png'
    try:
        from PIL import Image
        with Image.open(transfer_png) as im:
            require(im.mode == 'RGBA', f'transfer PNG mode is {im.mode}, expected RGBA', errors)
            require(im.width / im.height > 2.8, f'transfer PNG aspect ratio is {im.width/im.height:.3f}', errors)
            alpha = im.getchannel('A')
            require(alpha.getextrema()[0] == 0, 'transfer PNG has no transparent corners', errors)
            require(all(im.getpixel(xy)[3] == 0 for xy in ((0,0),(im.width-1,0),(0,im.height-1),(im.width-1,im.height-1))),
                    'transfer PNG corner pixels are not transparent', errors)
    except Exception as exc:
        errors.append(f'cannot validate transfer PNG: {exc}')

    originals = [p.resolve() for p in (ns.p113, ns.p114, ns.p115) if p]
    template = ns.p113.resolve() if ns.p113 else None
    if template:
        before = {p: sha256(p) for p in originals}
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / '99_0_116.zip'
            build_update_zip(template, encrypted, out, {
                'assets/image/webview/npps4_data_transfer.png': transfer_png.read_bytes(),
                'assets/image/webview/npps4_manga.png': manga_png.read_bytes(),
            })
            with zipfile.ZipFile(out) as zf:
                names = set(zf.namelist())
                require(zf.testzip() is None, 'generated 116 CRC failure', errors)
                require(names == {
                    'db/museum/museum.db_',
                    'assets/image/webview/npps4_data_transfer.png',
                    'assets/image/webview/npps4_manga.png',
                }, f'generated 116 entries wrong: {sorted(names)}', errors)
                require(not any(name.endswith(('client_info.json','server_info.json','package_info.json')) for name in names),
                        'generated 116 contains version/server config', errors)
        after = {p: sha256(p) for p in originals}
        require(before == after, 'original 113/114/115 packages were modified', errors)

    manga = (pyroot / 'templates/manga.html').read_text(encoding='utf-8')
    require('{{ define ' not in manga and '{{ end }}' not in manga, 'Go template wrappers remain in manga.html', errors)
    require((pyroot / 'templates/transfer.html').is_file(), 'transfer template missing', errors)
    require((npps4 / 'webview/transfer.py').is_file() and (npps4 / 'system/transfer_web.py').is_file(),
            'transfer WebView implementation missing', errors)

    guard = subprocess.run([sys.executable, str(root / 'tools/cn_contract_guard.py'), str(root)], capture_output=True, text=True)
    require(guard.returncode == 0, 'CN contract guard failed: ' + (guard.stdout + guard.stderr).strip(), errors)

    if errors:
        print('v4.52 validation FAILED')
        for e in errors:
            print('-', e)
        return 1
    print('v4.52 validation OK')
    print('Museum rows: 1360 (server + decrypted CN client DB)')
    print('CN home cards: two type-2 non-flipping WebViews')
    print('Retained update version: 97.4.6; overlay: 99_0_116 only')
    print('Original 113/114/115 mutation check: PASS' if originals else 'Original package mutation check: skipped')
    print('Transfer PNG alpha/aspect/corners: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
