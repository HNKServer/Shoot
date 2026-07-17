"""Wrap a prebuilt Museum payload in a real CN 99 update ZIP and install it."""
from __future__ import annotations
import argparse, json, shutil, sys, tempfile, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cn_museum_bridge import build_update_zip, select_template  # type: ignore


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--payload', required=True, help='payload directory or payload ZIP')
    p.add_argument('--archive-dir', required=True, help='folder containing real CN 99_0_*.zip files')
    p.add_argument('--output-dir', required=True, help='output/install directory')
    args = p.parse_args()
    payload = Path(args.payload).resolve()
    archive = Path(args.archive_dir).resolve()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    temp = None
    if payload.is_file():
        temp = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(payload) as zf:
            zf.extractall(temp.name)
        source = Path(temp.name)
    else:
        source = payload
    encrypted = next(source.rglob('museum.db_'), None)
    server_db = next(source.rglob('museum.server.db'), None)
    manifest = next(source.rglob('museum_bridge_manifest.json'), None)
    if encrypted is None or server_db is None or manifest is None:
        raise SystemExit('payload must contain museum.db_, museum.server.db and museum_bridge_manifest.json')

    template = select_template(archive)
    update_zip = output / '99_0_116.zip'
    build_update_zip(template, encrypted.read_bytes(), update_zip)
    shutil.copy2(server_db, output / 'museum.server.db')
    shutil.copy2(manifest, output / 'museum_bridge_manifest.json')
    print(json.dumps({
        'ok': True,
        'template': str(template),
        'update_zip': str(update_zip),
        'server_db': str(output / 'museum.server.db'),
        'manifest': str(output / 'museum_bridge_manifest.json'),
    }, ensure_ascii=False, indent=2))
    if temp is not None:
        temp.cleanup()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
