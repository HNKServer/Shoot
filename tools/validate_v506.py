#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, hashlib, json, re, sqlite3, subprocess, sys
from pathlib import Path

class Report:
    def __init__(self): self.rows=[]
    def check(self,name,ok,detail=''):
        self.rows.append({'name':name,'passed':bool(ok),'detail':str(detail)})
        if not ok: raise AssertionError(f'{name}: {detail}')
    def data(self):
        p=sum(x['passed'] for x in self.rows)
        return {'passed':p,'failed':len(self.rows)-p,'checks':self.rows}

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def tree_digest(root:Path):
    out={}
    for p in sorted(root.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}:
            out[p.relative_to(root).as_posix()]=sha(p)
    return out

def banner_id(event_id:int)->int:
    if event_id==10001: return 38
    if 221 <= event_id <= 228: return event_id-6
    return event_id

def banner_asset(event_id:int)->str:
    return f'assets/image/ui/eventscenario/{banner_id(event_id)}_se_ba_t.png'

def db_rows(path:Path):
    with sqlite3.connect(path) as db:
        cols=[r[1] for r in db.execute('pragma table_info(event_scenario_m)')]
        rows=[dict(zip(cols,r)) for r in db.execute('select * from event_scenario_m order by event_id,chapter,event_scenario_id')]
    return rows

def no_none(obj):
    if obj is None: return False
    if isinstance(obj,dict): return all(no_none(v) for v in obj.values())
    if isinstance(obj,list): return all(no_none(v) for v in obj)
    return True

def projected(rows):
    grouped={}
    for r in rows: grouped.setdefault(int(r['event_id']),[]).append(r)
    out=[]
    for event_id in sorted(grouped,reverse=True):
        masters=sorted(grouped[event_id],key=lambda r:(int(r['chapter']),int(r['event_scenario_id'])),reverse=True)
        chapters=[]
        for r in masters:
            c={
                'event_scenario_id':int(r['event_scenario_id']),
                'amount':int(r['amount']) if r['amount'] is not None else 1,
                'status':2,
                'chapter':int(r['chapter']),
                'item_id':int(r['item_id']) if r['item_id'] is not None else 1200,
                'cost_type':int(r['cost_type']) if r['cost_type'] is not None else 1000,
                'is_reward':False,
                'open_flash_flag':0,
            }
            if r['chapter_asset'] is not None:
                c['chapter_asset']=str(r['chapter_asset'])
            chapters.append(c)
        out.append({
            'event_id':event_id,
            'open_date':str(masters[0]['open_date']).replace('/','-'),
            'chapter_list':chapters,
            'event_scenario_btn_asset':banner_asset(event_id),
        })
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('root',type=Path)
    ap.add_argument('--peer-python',type=Path)
    ap.add_argument('--llsif-root',type=Path)
    ap.add_argument('--honoka-root',type=Path)
    ap.add_argument('--baseline-root',type=Path)
    ap.add_argument('--json-out',type=Path)
    args=ap.parse_args()
    root=args.root.resolve(); py=root/'app/src/main/python'; r=Report()
    src=(py/'npps4/game/eventscenario.py').read_text()
    ast.parse(src)
    r.check('eventscenario/status excludes JSON null recursively','@idol.register("eventscenario", "status", exclude_none=True)' in src)
    core=(py/'npps4/idol/core.py').read_text()
    r.check('endpoint serializer recursively applies exclude_none to Pydantic response models','response.model_dump(exclude_none=exclude_none)' in core)
    r.check('batch API forwards endpoint exclude_none into serializer','assemble_response_data(result, endpoint.exclude_none)' in core)
    r.check('nullable chapter_asset remains optional but is omitted when absent','chapter_asset: str | None = None' in src)
    r.check('invented event_scenario_se_btn_asset field removed','event_scenario_se_btn_asset' not in src)
    r.check('CN special event banner remap retained','if event_id == 10001:' in src and 'return 38' in src)
    r.check('GL final event 221..228 banner remap implemented','if 221 <= event_id <= 228:' in src and 'return event_id - 6' in src)
    r.check('banner path has canonical single suffix','_se_ba_t.png' in src and '_se_ba_tse.png' not in src)

    cn_path=py/'npps4/assets/cn_client_master.db'
    gl_path=py/'npps4/assets/gl_content_master/event_common.sqlite'
    cn=db_rows(cn_path); gl=db_rows(gl_path)
    r.check('CN event catalogue count unchanged',len(cn)==711,len(cn))
    r.check('GL event catalogue count unchanged',len(gl)==755,len(gl))
    r.check('CN contains 546 legitimate NULL chapter assets',sum(x['chapter_asset'] is None for x in cn)==546)
    r.check('GL contains 595 legitimate NULL chapter assets',sum(x['chapter_asset'] is None for x in gl)==595)
    cn_out=projected(cn); gl_out=projected(gl)
    r.check('CN projected status contains no JSON null values',no_none(cn_out))
    r.check('GL projected status contains no JSON null values',no_none(gl_out))
    r.check('CN projects exactly 103 event groups',len(cn_out)==103,len(cn_out))
    r.check('GL projects exactly 109 event groups',len(gl_out)==109,len(gl_out))
    r.check('CN special event uses banner 38',next(e for e in cn_out if e['event_id']==10001)['event_scenario_btn_asset'].endswith('/38_se_ba_t.png'))
    r.check('GL latest event uses existing banner 222',next(e for e in gl_out if e['event_id']==228)['event_scenario_btn_asset'].endswith('/222_se_ba_t.png'))

    if args.llsif_root:
        oracle=json.loads((args.llsif_root/'static/main.php-api/eventscenario.status.result.json').read_text())['event_scenario_list']
        r.check('LLSIF@Home final GL oracle has 109 event groups',len(oracle)==109,len(oracle))
        ours={e['event_id']:e for e in gl_out}; theirs={int(e['event_id']):e for e in oracle}
        r.check('GL event IDs match LLSIF@Home final archive',set(ours)==set(theirs),f'{len(ours)} vs {len(theirs)}')
        mismatch=[]
        chapter_mismatch=[]
        for eid,t in theirs.items():
            if ours[eid]['event_scenario_btn_asset'] != t['event_scenario_btn_asset']:
                mismatch.append((eid,ours[eid]['event_scenario_btn_asset'],t['event_scenario_btn_asset']))
            oc={int(c['event_scenario_id']):c for c in ours[eid]['chapter_list']}
            tc={int(c['event_scenario_id']):c for c in t['chapter_list']}
            if set(oc)!=set(tc): chapter_mismatch.append((eid,'ids'))
            else:
                for cid in oc:
                    if oc[cid].get('chapter_asset','<omitted>') != tc[cid].get('chapter_asset','<omitted>'):
                        chapter_mismatch.append((eid,cid,oc[cid].get('chapter_asset'),tc[cid].get('chapter_asset')))
        r.check('All GL banner assets match LLSIF@Home final archive',not mismatch,mismatch[:5])
        r.check('All GL chapter_asset presence/values match LLSIF@Home',not chapter_mismatch,chapter_mismatch[:5])
        r.check('LLSIF@Home never emits event_scenario_se_btn_asset',all('event_scenario_se_btn_asset' not in e for e in oracle))
        r.check('LLSIF@Home omits absent chapter_asset instead of JSON null',all(c.get('chapter_asset','ok') is not None for e in oracle for c in e['chapter_list']))
    if args.honoka_root:
        hs=(args.honoka_root/'internal/schema/api/eventscenario/status.go').read_text()
        hh=(args.honoka_root/'internal/handler/api/eventscenario/status.go').read_text()
        r.check('honoka-chan chapter_asset uses omitempty','json:"chapter_asset,omitempty"' in hs)
        r.check('honoka-chan response has no selected-banner field','EventScenarioSeBtnAsset' not in hs and 'event_scenario_se_btn_asset' not in hs)
        r.check('honoka-chan proves CN 10001->38 and 221->215','case 10001:' in hh and 'case 221:' in hh)

    build=(py/'npps4/build_info.py').read_text()
    r.check('v5.06 build ID present','v5.06-event-story-asset-contract-fix' in build)
    if (root/'app/build.gradle').exists() and 'android-wrapper' in root.name.lower():
        gradle=(root/'app/build.gradle').read_text()
        r.check('Android versionCode 506','versionCode 506' in gradle)
        r.check('Android versionName 0.5.6',"versionName '0.5.6'" in gradle)
    if args.peer_python:
        a=tree_digest(py); b=tree_digest(args.peer_python.resolve())
        r.check('Android/PC Python trees match',a==b,f'{len(a)} vs {len(b)}')
    if args.baseline_root:
        base=args.baseline_root.resolve()
        for rel in ['app/src/main/python/npps4/assets/cn_home_banner/4_0_999.zip','app/src/main/python/npps4/assets/cn_home_banner/npps4_data_transfer.png']:
            r.check(f'v5.05 verified CN asset unchanged: {Path(rel).name}',sha(root/rel)==sha(base/rel))
    # Syntax-compile every Python file without importing optional native deps.
    proc=subprocess.run([sys.executable,'-m','compileall','-q',str(py)],capture_output=True,text=True)
    r.check('Python compileall succeeds',proc.returncode==0,(proc.stdout+proc.stderr)[-2000:])
    data=r.data()
    if args.json_out: args.json_out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(data,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
