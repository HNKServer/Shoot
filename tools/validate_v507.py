#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, asyncio, hashlib, json, subprocess, sys
from pathlib import Path
from types import SimpleNamespace

class Report:
    def __init__(self): self.rows=[]
    def check(self,name,ok,detail=''):
        self.rows.append({'name':name,'passed':bool(ok),'detail':str(detail)})
        if not ok: raise AssertionError(f'{name}: {detail}')
    def data(self):
        p=sum(x['passed'] for x in self.rows)
        return {'passed':p,'failed':len(self.rows)-p,'checks':self.rows}

def sha(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(root:Path):
    out={}
    for p in sorted(root.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}:
            out[p.relative_to(root).as_posix()]=sha(p)
    return out

def extract_async(path:Path,name:str):
    t=ast.parse(path.read_text(),filename=str(path))
    n=next(x for x in t.body if isinstance(x,ast.AsyncFunctionDef) and x.name==name)
    n.decorator_list=[]; n.returns=None
    for a in [*n.args.posonlyargs,*n.args.args,*n.args.kwonlyargs]: a.annotation=None
    m=ast.Module(body=[n],type_ignores=[]); ast.fix_missing_locations(m)
    return m

def exec_async(path:Path,name:str,ns:dict):
    exec(compile(extract_async(path,name),str(path),'exec'),ns)
    return ns[name]

async def dynamic_ranking(py:Path,r:Report):
    path=py/'npps4/game/ranking.py'
    class IdolError(Exception):
        def __init__(self,code,status): self.error_code=code; self.status_code=status
    class Error:
        ERROR_CODE_LIB_ERROR=1
        @staticmethod
        def by_code(code): return IdolError(code,600)
    class RankingResponse:
        def __init__(self,**kw): self.__dict__.update(kw)
    current=SimpleNamespace(id=1)
    async def get_current(_): return current
    class Reward:
        @staticmethod
        async def count_presentbox(_c,_u): return 0
    class EmptyRanking:
        @staticmethod
        async def get_daily_ranking(_c,page,yesterday): return [],0
        @staticmethod
        async def get_daily_rank(_c,uid,yesterday): return 0
        @staticmethod
        async def get_live_ranking(_c,diff,page): return 0,[]
        @staticmethod
        async def get_live_rank(_c,diff,uid): return 0
    ns={'__builtins__':__builtins__,'idol':SimpleNamespace(error=Error),'user':SimpleNamespace(get_current=get_current),'ranking':EmptyRanking,'reward':Reward,'RankingResponse':RankingResponse,'_ranking_data':None}
    f=exec_async(path,'ranking_player',ns)
    try:
        await f(SimpleNamespace(),SimpleNamespace(id=1,page=0,term=1,daily_index=1))
        ok=False; detail='returned success instead of safe game error'
    except IdolError as e:
        ok=(e.error_code,e.status_code)==(1,600); detail=(e.error_code,e.status_code)
    r.check('ranking/player empty state returns honoka-compatible game error',ok,detail)
    lf=exec_async(path,'ranking_live',ns)
    x=await lf(SimpleNamespace(),SimpleNamespace(page=0,live_difficulty_id=1))
    r.check('ranking/live empty state remains honoka-compatible success',x.items==[] and x.total_cnt==0 and x.rank==0,vars(x))

async def dynamic_live_guest(py:Path,r:Report):
    path=py/'npps4/system/profile_projection.py'
    projected=(SimpleNamespace(unit_id=7),SimpleNamespace(default_leader_skill_id=88),'full','stats')
    async def center(_c,_u): return projected
    class DB:
        value=None
        @classmethod
        async def get_decrypted_row(cls,*a): return cls.value
    ns={'__builtins__':__builtins__,'center_unit':center,'db':DB,'unit_db':SimpleNamespace(LeaderSkill=object)}
    f=exec_async(path,'live_guest_center_unit',ns)
    ctx=SimpleNamespace(db=SimpleNamespace(unit=object()))
    DB.value=None
    r.check('guest card with missing receiver-side leader skill is rejected',await f(ctx,SimpleNamespace()) is None)
    DB.value=SimpleNamespace()
    r.check('guest card with valid receiver-side leader skill is accepted',await f(ctx,SimpleNamespace()) is projected)

async def main_async(args,r,py):
    await dynamic_ranking(py,r)
    await dynamic_live_guest(py,r)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root',type=Path); ap.add_argument('--peer-python',type=Path); ap.add_argument('--honoka-root',type=Path); ap.add_argument('--baseline-root',type=Path); ap.add_argument('--json-out',type=Path)
    a=ap.parse_args(); root=a.root.resolve(); py=root/'app/src/main/python'; r=Report()
    rank=(py/'npps4/game/ranking.py').read_text(); proj=(py/'npps4/system/profile_projection.py').read_text(); adv=(py/'npps4/system/advanced.py').read_text(); live=(py/'npps4/game/live.py').read_text(); core=(py/'npps4/idol/core.py').read_text()
    r.check('ranking/live bypasses transport XMC verification','@idol.register("ranking", "live", xmc_verify=idol.XMCVerifyMode.NONE)' in rank)
    r.check('ranking/player bypasses transport XMC verification','@idol.register("ranking", "player", xmc_verify=idol.XMCVerifyMode.NONE)' in rank)
    r.check('ranking/player uses error_code 1 safe fallback','ERROR_CODE_LIB_ERROR' in rank and 'total_count <= 0' in rank)
    r.check('guest Live projection validates receiver-side leader skill','async def live_guest_center_unit' in proj and 'unit_db.LeaderSkill' in proj)
    r.check('partyList advertises validated guest projection','profile_projection.live_guest_center_unit(context, target_user)' in adv)
    r.check('live/play recalculates with the same validated projection','profile_projection.live_guest_center_unit(context, guest)' in live)
    r.check('event story null omission fix retained','@idol.register("eventscenario", "status", exclude_none=True)' in (py/'npps4/game/eventscenario.py').read_text())
    r.check('response remains signed game protocol response','X-Message-Sign' in core and 'build_response' in core)
    build=(py/'npps4/build_info.py').read_text(); r.check('v5.07 build ID present','v5.07-ranking-safe-live-guest-fallback' in build)
    if (root/'app/build.gradle').exists() and 'android-wrapper' in root.name.lower():
        g=(root/'app/build.gradle').read_text(); r.check('Android versionCode 507','versionCode 507' in g); r.check('Android versionName 0.5.7',"versionName '0.5.7'" in g)
    if a.honoka_root:
        hr=(a.honoka_root/'internal/router/router.go').read_text(); hrank=list((a.honoka_root/'internal/handler/ranking').glob('*.go'))
        r.check('honoka generic fallback is HTTP protocol success with status 600/error 1','ErrorCodeUnknown' in hr and 'StatusCode:  600' in hr)
        r.check('honoka implements ranking/live but not ranking/player',any(p.name=='live.go' for p in hrank) and not any('player' in p.name for p in hrank))
    asyncio.run(main_async(a,r,py))
    proc=subprocess.run([sys.executable,'-m','compileall','-q',str(py)],capture_output=True,text=True)
    r.check('Python compileall succeeds',proc.returncode==0,(proc.stdout+proc.stderr)[-1000:])
    if a.peer_python:
        x,y=tree(py),tree(a.peer_python.resolve()); r.check('Android and PC Python trees are identical',x==y,f'{len(x)} vs {len(y)}')
    if a.baseline_root:
        base=a.baseline_root.resolve()
        for rel in ['app/src/main/python/npps4/assets/cn_home_banner/4_0_999.zip','app/src/main/python/npps4/assets/cn_home_banner/npps4_data_transfer.png']:
            if (root/rel).exists() and (base/rel).exists(): r.check(f'CN verified asset unchanged: {Path(rel).name}',sha(root/rel)==sha(base/rel))
    data=r.data()
    if a.json_out: a.json_out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(data,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
