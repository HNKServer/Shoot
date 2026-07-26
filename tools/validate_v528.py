from pathlib import Path
import ast, json, sqlite3, sys
ROOT=Path(__file__).resolve().parents[1]
PYROOT=ROOT/'app/src/main/python'
PKG=PYROOT/'npps4'

def req(ok,msg):
    if not ok: raise AssertionError(msg)
    print('PASS',msg)

build=(PKG/'build_info.py').read_text(encoding='utf-8')
proj=(PKG/'system/profile_projection.py').read_text(encoding='utf-8')
serial=(PKG/'serialcode/func.py').read_text(encoding='utf-8')
req('v5.28-v524-exact-unit-projection-target-card-fix' in build,'v5.28 build id')
req('from . import profile_unit_master' in proj,'profile projection imports exact unit master')
req('profile_unit_master.unit_by_id(context, unit_id)' in proj,'projection falls back to receiver exact Unit Master')
req('(row.id is None or int(row.id) not in excluded_ids)' in serial,'pending target cards are countable before flush')
req('dedicated-accessory target-card top-up verification failed' in serial,'persisted target-card count is verified')
ast.parse(proj); ast.parse(serial)
for profile in ('cn','gl'):
    acc=sqlite3.connect(PKG/'assets'/f'{profile}_client_master.db')
    unit_path=PKG/'assets'/('cn_unit_master.db' if profile=='cn' else 'gl_client_master.db')
    units=sqlite3.connect(unit_path)
    targets={r[0] for r in acc.execute('select unit_id from accessory_special_m')}
    known={r[0] for r in units.execute('select unit_id from unit_m')}
    req(bool(targets),f'{profile} special target catalogue is non-empty')
    req(not (targets-known),f'{profile} every special target exists in exact Unit Master')
print('v5.28 validation complete')
gradle=(ROOT/'app/build.gradle').read_text(encoding='utf-8')
req('versionCode 528' in gradle,'Android versionCode 528')
req("versionName '0.5.28'" in gradle,'Android versionName 0.5.28')
