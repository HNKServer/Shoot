#!/usr/bin/env bash
set -euo pipefail
DEST="${1:-./sif-gl-archive}"
SERVER="${2:-https://ll.sif.moe/npps4_dlapi}"
WORK="$(cd "$(dirname "$0")" && pwd)/official-npps4-dlapi-tools"
mkdir -p "$WORK"
RAW="https://raw.githubusercontent.com/DarkEnergyProcessor/NPPS4-DLAPI/master"
for name in clone.py update_v1.1.py update_v1.2.py release_info.json; do
  curl -fL "$RAW/$name" -o "$WORK/$name"
done
python3 -m pip install --upgrade natsort "https://github.com/DarkEnergyProcessor/honky-py/releases/download/0.2.0/honkypy-0.2.0-py3-none-any.whl"
python3 "$WORK/clone.py" "$DEST" "$SERVER" --no-ios
python3 "$WORK/update_v1.1.py" "$DEST"
python3 "$WORK/update_v1.2.py" "$DEST"
echo "Android mirror ready: $DEST"
