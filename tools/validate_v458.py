from pathlib import Path
import ast, json, hashlib
from PIL import Image

root = Path(__file__).resolve().parents[1]
py = root / "app/src/main/python"
errors=[]
def req(ok,msg):
    if not ok: errors.append(msg)

banner=(py/"npps4/game/banner.py").read_text(encoding="utf-8")
cn=(py/"npps4/download/cn_archive.py").read_text(encoding="utf-8")
build=(py/"npps4/build_info.py").read_text(encoding="utf-8")
req('asset_path="assets/image/secretbox/icon/s_ba_900001_1.png"' in banner, "transfer does not use dedicated secretbox cache key")
req('assets/image/secretbox/icon/s_ba_900001_1.png": "npps4_data_transfer.png"' in cn, "dedicated transfer bundled alias missing")
req('asset_path="assets/image/secretbox/icon/s_ba_1718_1.png"' not in banner, "hard-coded duplicate 1718 transfer mapping remains")
req('transfer_asset_path = "assets/image/webview/npps4_data_transfer.png"' not in cn, "99_0_115 image injection remains")
req('v4.58-cn-transfer-secretbox-cache-key' in build, "build id wrong")
img=Image.open(py/"npps4/assets/cn_home_banner/npps4_data_transfer.png")
req(img.size==(2170,725), f"unexpected transfer image dimensions {img.size}")
# Compile all Python source via AST.
for p in py.rglob('*.py'):
    try: ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    except Exception as e: errors.append(f"python parse failed {p}: {e}")
# Parse JSON.
for p in py.rglob('*.json'):
    try: json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: errors.append(f"json parse failed {p}: {e}")
# Android version when present.
gradle=root/'app/build.gradle'
if gradle.exists():
    gt=gradle.read_text(encoding='utf-8')
    req('versionCode 440' in gt, 'Android versionCode not 440')
    req("versionName '0.4.38'" in gt, 'Android versionName not 0.4.38')
if errors:
    print('v4.58 validation FAILED')
    print('\n'.join('- '+e for e in errors))
    raise SystemExit(1)
print('v4.58 validation OK')
