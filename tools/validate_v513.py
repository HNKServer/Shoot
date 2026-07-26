#!/usr/bin/env python3
from __future__ import annotations
import ast, hashlib, json, sys
from pathlib import Path
root=Path(sys.argv[1]).resolve()
py=root/'app/src/main/python'
checks=[]
def add(name, ok, detail=''):
    checks.append({'name':name,'passed':bool(ok),'detail':detail})
cs=(py/'npps4/system/costume.py').read_text()
us=(py/'npps4/system/unit.py').read_text()
bi=(py/'npps4/build_info.py').read_text()
add('build id v5.13', 'v5.13-costume-override-semantics-fix' in bi)
add('appearance optional annotation', ') -> unit_model.CostumeInfo | None:' in cs)
section=cs.split('async def appearance_for_owned_unit',1)[1]
add('no native fallback in appearance serializer', 'default_appearance(context, owned)' not in section)
add('unassigned card returns None', 'if row is None:\n        return None' in section)
add('disabled display returns None', 'if user is None or not await is_enabled(context, user):\n        return None' in section)
add('invalid dress returns None', 'await context.db.main.delete(row)' in section and 'return None' in section)
add('actual dress serializes CostumeInfo', 'unit_id=row.costume_unit_id' in section)
add('single-use guard present', 'in_use_q = sqlalchemy.select(main.UserCostumeDress)' in cs and 'already used by another card' in cs)
add('unit helper optional annotation', ') -> unit_model.CostumeInfo | None:' in us)
game=(py/'npps4/game/costume.py').read_text()
for route in ('costumeList','costumeStatus','dressUp','makeCostume'):
    add(f'route {route}', f'@idol.register("costume", "{route}")' in game)
add('no unregister route invented', 'unregister' not in game.lower() and 'deleteCostume' not in game)
aw=(py/'android_wrapper.py').read_text()
add('v5.12 workspace payload fallback preserved', 'android_workspace_payload' in aw)
add('config authority preserved', '_copy_if_missing' in aw and 'server_data.json' in aw)
k=root/'app/src/main/java/moe/honoka/npps4wrapper/ConfigEditorActivity.kt'
if 'NPPS4-Android-Wrapper' in root.name and k.exists():
    kt=k.read_text()
    add('Kotlin searchInput compile fix preserved', 'searchInput.text.isNotBlank()' in kt and 'this.text.isNotBlank()' not in kt)
    grad=(root/'app/build.gradle').read_text()
    add('Android version 513', 'versionCode 513' in grad and "versionName '0.5.13'" in grad)
passed=sum(c['passed'] for c in checks)
result={'root':str(root),'passed':passed,'failed':len(checks)-passed,'checks':checks}
print(json.dumps(result,ensure_ascii=False,indent=2))
if result['failed']: raise SystemExit(1)
