#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import io
import zipfile
import ast
import asyncio
import builtins
import hashlib
import json
import re
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace


class Report:
    def __init__(self):
        self.rows=[]
    def check(self,name,ok,detail=""):
        self.rows.append({"name":name,"passed":bool(ok),"detail":detail})
        if not ok:
            raise AssertionError(f"{name}: {detail}")
    def data(self):
        passed=sum(bool(x["passed"]) for x in self.rows)
        return {"passed":passed,"failed":len(self.rows)-passed,"checks":self.rows}


def extract_function(path: Path, name: str, async_only: bool | None=None):
    tree=ast.parse(path.read_text('utf-8'),filename=str(path))
    kinds=(ast.AsyncFunctionDef,) if async_only is True else (ast.FunctionDef,) if async_only is False else (ast.FunctionDef,ast.AsyncFunctionDef)
    node=next(n for n in tree.body if isinstance(n,kinds) and n.name==name)
    node.decorator_list=[]
    if isinstance(node,ast.AsyncFunctionDef): node.returns=None
    for arg in [*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]: arg.annotation=None
    if node.args.vararg: node.args.vararg.annotation=None
    if node.args.kwarg: node.args.kwarg.annotation=None
    mod=ast.Module(body=[node],type_ignores=[]); ast.fix_missing_locations(mod)
    return mod


def exec_function(path:Path,name:str,ns:dict,async_only=None):
    mod=extract_function(path,name,async_only)
    exec(compile(mod,str(path),'exec'),ns)
    return ns[name]


def digest_tree(root:Path):
    out={}
    for p in sorted(root.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix in {'.pyc','.pyo'}: continue
        out[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def check_source_audit(root:Path,pyroot:Path,report:Report,llsif:Path|None,honoka:Path|None,orig:Path|None):
    museum=(pyroot/'npps4/system/museum.py').read_text()
    cfg=(pyroot/'npps4/config/data.py').read_text()
    model=(pyroot/'npps4/db/main.py').read_text()
    profile=(pyroot/'npps4/game/profile.py').read_text()
    projection=(pyroot/'npps4/system/profile_projection.py').read_text()
    rankapi=(pyroot/'npps4/game/ranking.py').read_text()
    ranksys=(pyroot/'npps4/system/ranking.py').read_text()

    report.check('Museum policy is request-profile scoped','get_profile_download(context.profile).museum_unlock_policy' in museum)
    report.check('CN/GL profile configs default Museum all','museum_unlock_policy: str = "all"' in cfg)
    report.check('Museum normal state is profile isolated','profile: sqlalchemy.orm.Mapped[str]' in model and 'UniqueConstraint(user_id, profile, museum_contents_id)' in model)
    report.check('Museum queries bind context profile',museum.count('main.MuseumUnlock.profile == context.profile.value') >= 4)
    report.check('No process-global CN-only all-unlock gate','config.is_cn_compat() and _native_unlock_policy' not in museum)
    report.check('Representative-card inventory fallback exists','async def representative_unit' in projection and 'main.Unit.active.is_(True)' in projection)
    report.check('Profile center and partner both use representative fallback',profile.count('profile_projection.representative_unit(')==2)
    report.check('Ranking current-position query no longer throws USER_NOT_EXIST','if request.id > 0' not in rankapi and 'util.stub("ranking", "player"' not in rankapi)
    report.check('Ranking empty/unranked rank is numeric zero','rank: int = 0' in rankapi)
    report.check('Ranking has live and daily rank helpers','async def get_live_rank' in ranksys and 'async def get_daily_rank' in ranksys)
    report.check('Ranking tie order is deterministic','main.LiveClear.user_id.asc()' in ranksys and 'main.PlayerRanking.user_id' in ranksys)

    for sample in ('config.sample.toml','config.dual.sample.toml','config.cn-local.sample.toml','config.gl-online.sample.toml'):
        text=(pyroot/sample).read_text()
        report.check(f'{sample} enables both profile Museum defaults',text.count('museum_unlock_policy = "all"')==2,str(text.count('museum_unlock_policy = "all"')))

    if llsif:
        data=json.loads((llsif/'static/museum_info.json').read_text())
        report.check('LLSIF@Home GL Museum static catalogue has 1360 entries',len(data['contents_id_list'])==1360,str(len(data['contents_id_list'])))
        report.check('LLSIF@Home Ranking is a success-shaped empty response','"status_code":200' in (llsif/'handler/live.js').read_text() and '"items":[]' in (llsif/'handler/live.js').read_text())
    if honoka:
        h1=(honoka/'internal/handler/museum/info.go').read_text()
        h2=(honoka/'internal/handler/api/museum/info.go').read_text()
        report.check('honoka-chan exposes all native Museum rows',h1.count('contentsList = append')==1 and h2.count('museumID = append')==1)
        with sqlite3.connect(honoka/'assets/main.db') as conn:
            cn_count=int(conn.execute('SELECT COUNT(*) FROM museum_contents_m').fetchone()[0])
        report.check('honoka CN native Museum catalogue has 16 entries',cn_count==16,str(cn_count))
    if orig:
        oms=(orig/'npps4/system/museum.py').read_text()
        tree='\n'.join(p.read_text(errors='ignore') for p in (orig/'npps4').rglob('*.py'))
        report.check('Upstream NPPS4 Museum normal state is sparse/test-gated','TEST_MUSEUM_UNLOCK_ALL = False' in oms)
        report.check('Upstream has no ordinary-action Museum hook beyond generic reward/import',tree.count('museum.unlock(')==2,str(tree.count('museum.unlock(')))


def exercise_config_migration(pyroot:Path,report:Report):
    path=pyroot/'android_wrapper.py'
    ns={'__builtins__':builtins.__dict__,'Path':Path,'re':re}
    fn=exec_function(path,'_migrate_profile_museum_policies',ns,False)
    old='''[download.profiles.cn]\nenabled = true\nbackend = "cn_archive"\nmuseum_unlock_policy = "all"\n\n[download.profiles.cn.cn_archive]\nandroid_archives = "x"\nmuseum_unlock_policy = "normal"\n\n[download.profiles.gl]\nenabled = true\nbackend = "n4dlapi"\n'''
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'config.toml'; p.write_text(old)
        fn(p); text=p.read_text()
    cn=text.split('[download.profiles.cn]',1)[1].split('[',1)[0]
    gl=text.split('[download.profiles.gl]',1)[1].split('[',1)[0]
    report.check('Legacy nested CN normal policy is preserved','museum_unlock_policy = "normal"' in cn)
    report.check('Missing GL policy migrates to all','museum_unlock_policy = "all"' in gl)
    report.check('Deprecated nested Museum key is removed',text.count('museum_unlock_policy')==2,str(text.count('museum_unlock_policy')))


async def exercise_museum_all(pyroot:Path,report:Report):
    path=pyroot/'npps4/system/museum.py'
    async def cleanup(_context,_user): return None
    async def native_rows(_context): return [(3,1,2,3),(1,4,5,6)]
    def policy(_context): return 'all'
    class Parameter:
        def __init__(self): self.smile=0; self.pure=0; self.cool=0
    class Info:
        def __init__(self,**kwargs): self.__dict__.update(kwargs)
    ns={'__builtins__':builtins.__dict__,'_cleanup_legacy_museum_transplant':cleanup,'_native_rows':native_rows,'_native_unlock_policy':policy,'MuseumParameterData':Parameter,'MuseumInfoData':Info,'sqlalchemy':SimpleNamespace(),'main':SimpleNamespace(MuseumUnlock=SimpleNamespace())}
    fn=exec_function(path,'get_museum_info_data',ns,True)
    result=await fn(SimpleNamespace(),SimpleNamespace())
    report.check('Museum all policy exposes only sorted active native rows',result.contents_id_list==[1,3],repr(result.contents_id_list))
    report.check('Museum all policy sums native parameter buffs',result.parameter.smile==5 and result.parameter.pure==7 and result.parameter.cool==9,repr(result.parameter.__dict__))


async def exercise_representative_fallback(pyroot:Path,report:Report):
    path=pyroot/'npps4/system/profile_projection.py'
    class Field:
        def __eq__(self,_): return self
        def is_(self,_): return self
        def desc(self): return self
        def asc(self): return self
    class UnitModel:
        user_id=Field(); active=Field(); favorite_flag=Field(); love=Field(); id=Field()
    class Select:
        def where(self,*a): return self
        def order_by(self,*a): return self
    class SA:
        @staticmethod
        def select(*a): return Select()
    exclusive=SimpleNamespace(id=10,user_id=2,unit_id=9999)
    supported=SimpleNamespace(id=20,user_id=2,unit_id=1)
    class Result:
        def scalars(self): return [exclusive,supported]
    class MainDB:
        async def get(self,_model,key): return {10:exclusive,20:supported}.get(key)
        async def execute(self,_q): return Result()
    async def owned(_context,candidate):
        return None if candidate.unit_id==9999 else (candidate,'info','full','stats')
    ns={'__builtins__':builtins.__dict__,'sqlalchemy':SA,'main':SimpleNamespace(Unit=UnitModel),'owned_unit':owned}
    fn=exec_function(path,'representative_unit',ns,True)
    ctx=SimpleNamespace(db=SimpleNamespace(main=MainDB()))
    target=SimpleNamespace(id=2)
    result=await fn(ctx,target,(10,))
    report.check('Exclusive preferred card falls back to supported inventory card',result is not None and result[0].id==20,repr(result))


async def exercise_ranking_empty(pyroot:Path,report:Report):
    path=pyroot/'npps4/game/ranking.py'
    class RankingResponse:
        def __init__(self,**kwargs): self.__dict__.update(kwargs)
    current=SimpleNamespace(id=1)
    async def current_user(_): return current
    class Ranking:
        @staticmethod
        async def get_daily_ranking(_c,page,yesterday): return [],0
        @staticmethod
        async def get_daily_rank(_c,user_id,yesterday): return 0
        @staticmethod
        async def get_live_ranking(_c,live_difficulty_id,page): return 0,[]
        @staticmethod
        async def get_live_rank(_c,live_difficulty_id,user_id): return 0
    class Reward:
        @staticmethod
        async def count_presentbox(_c,_u): return 0
    ns={'__builtins__':builtins.__dict__,'user':SimpleNamespace(get_current=current_user),'ranking':Ranking,'reward':Reward,'RankingResponse':RankingResponse,'_ranking_data':None}
    fn=exec_function(path,'ranking_player',ns,True)
    response=await fn(SimpleNamespace(),SimpleNamespace(id=5,page=-3,daily_index=1,term=1))
    report.check('ranking/player id>0 returns success-shaped empty data',response.page==0 and response.rank==0 and response.items==[] and response.total_cnt==0,repr(response.__dict__))
    live_fn=exec_function(path,'ranking_live',ns,True)
    live_response=await live_fn(SimpleNamespace(),SimpleNamespace(page=-2,live_difficulty_id=123))
    report.check('ranking/live returns success-shaped empty data',live_response.page==0 and live_response.rank==0 and live_response.items==[] and live_response.total_cnt==0,repr(live_response.__dict__))


def exercise_android_schema(pyroot:Path,report:Report):
    import sys
    sys.path.insert(0,str(pyroot))
    import sqlalchemy
    from npps4 import android_schema
    engine=sqlalchemy.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE user (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('INSERT INTO user(id) VALUES (1)')
        conn.exec_driver_sql('CREATE TABLE museum_unlock (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, museum_contents_id INTEGER NOT NULL, UNIQUE(user_id,museum_contents_id))')
        conn.exec_driver_sql('INSERT INTO museum_unlock(id,user_id,museum_contents_id) VALUES (1,1,77)')
        android_schema._rebuild_museum_table(conn,'cn')
        cols=[r[1] for r in conn.exec_driver_sql('PRAGMA table_info(museum_unlock)').all()]
        rows=conn.exec_driver_sql('SELECT user_id,profile,museum_contents_id FROM museum_unlock ORDER BY profile').all()
        uniques=[]
        for idx in conn.exec_driver_sql('PRAGMA index_list(museum_unlock)').all():
            if idx[2]: uniques.append(tuple(x[2] for x in conn.exec_driver_sql(f'PRAGMA index_info("{idx[1]}")').all()))
    report.check('Android schema adds Museum profile column','profile' in cols,repr(cols))
    report.check('Android schema preserves legacy shared Museum rows for both profiles',[(int(r[0]),str(r[1]),int(r[2])) for r in rows]==[(1,'cn',77),(1,'gl',77)],repr(rows))
    report.check('Android schema installs profile-scoped unique key',('user_id','profile','museum_contents_id') in uniques,repr(uniques))


def exercise_android_payload(pyroot:Path,report:Report):
    ns={}
    path=pyroot/'npps4/tools/android_alembic_payload.py'
    exec(compile(path.read_text(),str(path),'exec'),ns)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(ns['PAYLOAD_B64']))) as archive:
        names=archive.namelist()
        migration=archive.read('versions/2026_07_22_0008-profile_museum_state.py').decode('utf-8')
    report.check('Android Alembic payload contains all 28 migration files',len(names)==28,str(len(names)))
    report.check('Android Alembic payload embeds latest dual-profile Museum migration','for profile in ("cn", "gl")' in migration)


def exercise_alembic_sqlite(pyroot:Path,report:Report):
    import sqlalchemy
    path=pyroot/'npps4/alembic/versions/2026_07_22_0008-profile_museum_state.py'
    fn_mod=extract_function(path,'_sqlite_upgrade',False)
    engine=sqlalchemy.create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.exec_driver_sql('PRAGMA foreign_keys=ON')
        conn.exec_driver_sql('CREATE TABLE user (id INTEGER PRIMARY KEY)')
        conn.exec_driver_sql('INSERT INTO user(id) VALUES (1)')
        conn.exec_driver_sql('CREATE TABLE museum_unlock (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, museum_contents_id INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES user(id), UNIQUE(user_id,museum_contents_id))')
        conn.exec_driver_sql('INSERT INTO museum_unlock(id,user_id,museum_contents_id) VALUES (7,1,77)')
        class FakeOp:
            def execute(self,clause): return conn.execute(clause)
            def get_bind(self): return conn
            def create_index(self,name,table,columns,unique=False):
                prefix='UNIQUE ' if unique else ''
                cols=', '.join('"'+column+'"' for column in columns)
                conn.exec_driver_sql(f'CREATE {prefix}INDEX "{name}" ON "{table}" ({cols})')
        ns={'op':FakeOp(),'sa':sqlalchemy}
        exec(compile(fn_mod,str(path),'exec'),ns)
        ns['_sqlite_upgrade']('cn')
        rows=[tuple(r) for r in conn.exec_driver_sql('SELECT user_id,profile,museum_contents_id FROM museum_unlock ORDER BY profile').all()]
        unique=[]
        for idx in conn.exec_driver_sql('PRAGMA index_list(museum_unlock)').all():
            if idx[2]: unique.append(tuple(r[2] for r in conn.exec_driver_sql(f'PRAGMA index_info("{idx[1]}")').all()))
    report.check('Alembic SQLite upgrade preserves legacy shared Museum rows for CN and GL',rows==[(1,'cn',77),(1,'gl',77)],repr(rows))
    report.check('Alembic SQLite upgrade installs profile-scoped unique key',('user_id','profile','museum_contents_id') in unique,repr(unique))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('root',type=Path)
    ap.add_argument('--peer-python',type=Path)
    ap.add_argument('--llsif-root',type=Path)
    ap.add_argument('--honoka-root',type=Path)
    ap.add_argument('--orig-root',type=Path)
    ap.add_argument('--json-out',type=Path)
    args=ap.parse_args()
    root=args.root.resolve(); pyroot=root/'app/src/main/python'; report=Report()
    check_source_audit(root,pyroot,report,args.llsif_root,args.honoka_root,args.orig_root)
    exercise_config_migration(pyroot,report)
    asyncio.run(exercise_museum_all(pyroot,report))
    asyncio.run(exercise_representative_fallback(pyroot,report))
    asyncio.run(exercise_ranking_empty(pyroot,report))
    exercise_android_schema(pyroot,report)
    exercise_alembic_sqlite(pyroot,report)
    exercise_android_payload(pyroot,report)
    build=(pyroot/'npps4/build_info.py').read_text()
    report.check('v5.05 build ID present','v5.05-museum-profile-ranking-fix' in build)
    if 'android-wrapper' in root.name.lower():
        gradle=(root/'app/build.gradle').read_text()
        report.check('Android versionCode 505','versionCode 505' in gradle)
        report.check('Android versionName 0.5.5',"versionName '0.5.5'" in gradle)
    if args.peer_python:
        left=digest_tree(pyroot); right=digest_tree(args.peer_python.resolve())
        report.check('Android/PC Python trees match',left==right,f'left={len(left)} right={len(right)}')
    data=report.data()
    if args.json_out: args.json_out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
