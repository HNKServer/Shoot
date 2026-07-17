from pathlib import Path
import json, hashlib, zipfile, tempfile, shutil, re
root = Path(__file__).resolve().parents[1]
py = root / "app/src/main/python"
errors=[]
def req(ok,msg):
    if not ok: errors.append(msg)

def java_hash(s):
    h=0
    for ch in s:
        h=(31*h+ord(ch)) & 0xffffffff
    return h-0x100000000 if h & 0x80000000 else h

banner=(py/"npps4/game/banner.py").read_text(encoding="utf-8")
archive=(py/"npps4/download/cn_archive.py").read_text(encoding="utf-8")
data=json.loads((py/"npps4/server_data.json").read_text(encoding="utf-8"))
img=py/"npps4/assets/cn_home_banner/npps4_data_transfer.png"
req('asset_path="assets/image/webview/npps4_data_transfer.png"' in banner,"transfer does not use dedicated asset")
req('asset_path="assets/image/webview/wv_ba_01.png"' in banner,"manga back-side contract changed")
req('"assets/image/secretbox/icon/s_ba_1718_1.png": "npps4_data_transfer.png"' not in archive,"stock 1718 asset is still aliased to transfer")
req('transfer_asset_path = "assets/image/webview/npps4_data_transfer.png"' in archive,"99_0_115 injection missing")
req('dst.writestr(transfer_info, transfer_asset)' in archive,"transfer asset not written to dynamic bootstrap ZIP")
boxes=[x for x in data['secretbox_data'] if x.get('id_string')=='5K']
req(len(boxes)==1,"1718 secretbox entry missing/duplicated")
if boxes:
    b=boxes[0]
    req(java_hash(b['id_string'])==1718,"id_string 5K no longer maps to 1718")
    req(b['menu_asset']=='assets/image/secretbox/icon/s_ba_1718_1.png',"1718 menu asset wrong")
    req(b['animation_asset_layout'][0].endswith('bg_1718.png'),"1718 animation assets wrong")
req(img.is_file() and img.stat().st_size>100000,"transfer image missing")
req("versionCode 439" in (root/"app/build.gradle").read_text(encoding="utf-8"),"versionCode not bumped")
req("versionName '0.4.37'" in (root/"app/build.gradle").read_text(encoding="utf-8"),"versionName not bumped")
req('v4.57-cn-transfer-cover-and-1718-banner' in (py/"npps4/build_info.py").read_text(encoding="utf-8"),"build id wrong")
if errors:
    print("v4.57 validation FAILED")
    for e in errors: print("-",e)
    raise SystemExit(1)
print("v4.57 validation OK")
print("transfer_image_sha256", hashlib.sha256(img.read_bytes()).hexdigest())
print("secretbox_1718_id_string", boxes[0]['id_string'])
