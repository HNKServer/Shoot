#!/usr/bin/env python3
from __future__ import annotations
import asyncio, ast, json, os, sqlite3, sys, tempfile, types
from pathlib import Path
from types import SimpleNamespace
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

ROOT=Path(__file__).resolve().parents[1]
PYROOT=ROOT/'app/src/main/python'
PKG=PYROOT/'npps4'

def require(v,msg):
    if not v: raise AssertionError(msg)
    print('[OK]',msg)

def install_crypto_stubs():
    names=['Cryptodome','Cryptodome.Cipher','Cryptodome.Cipher.AES','Cryptodome.Cipher.DES3','Cryptodome.Cipher.PKCS1_v1_5','Cryptodome.Hash','Cryptodome.Hash.SHA1','Cryptodome.Hash.SHA256','Cryptodome.Protocol','Cryptodome.Protocol.KDF','Cryptodome.PublicKey','Cryptodome.PublicKey.RSA','Cryptodome.Signature','Cryptodome.Signature.pkcs1_15','Cryptodome.Util','Cryptodome.Util.Padding']
    for name in names:
        mod=types.ModuleType(name)
        if name in {'Cryptodome','Cryptodome.Cipher','Cryptodome.Hash','Cryptodome.Protocol','Cryptodome.PublicKey','Cryptodome.Signature','Cryptodome.Util'}: mod.__path__=[]
        sys.modules[name]=mod
    for name in names:
        if '.' in name:
            p,c=name.rsplit('.',1); setattr(sys.modules[p],c,sys.modules[name])
    class Dummy:
        n=1; e=65537
        def __init__(self,*a,**k): pass
        def __call__(self,*a,**k): return self
        def __getattr__(self,n): return self
        def update(self,*a,**k): return None
        def sign(self,*a,**k): return b''
        def decrypt(self,*a,**k): return b''
        def publickey(self): return self
    for name in names: sys.modules[name].new=lambda *a,**k:Dummy()
    for name in ('Cryptodome.Cipher.AES','Cryptodome.Cipher.DES3'):
        sys.modules[name].MODE_CBC=1; sys.modules[name].MODE_ECB=2
    sys.modules['Cryptodome.Util.Padding'].pad=lambda v,*a,**k:v
    sys.modules['Cryptodome.Util.Padding'].unpad=lambda v,*a,**k:v
    sys.modules['Cryptodome.Protocol.KDF'].PBKDF2=lambda *a,**k:b''
    sys.modules['Cryptodome.PublicKey.RSA'].RsaKey=Dummy
    sys.modules['Cryptodome.PublicKey.RSA'].import_key=lambda *a,**k:Dummy()

def import_modules():
    install_crypto_stubs()
    sqlalchemy.ext.asyncio.create_async_engine=lambda *a,**k:object()
    sqlalchemy.ext.asyncio.async_sessionmaker=lambda *a,**k:object()
    os.environ['NPPS4_ROOT_DIR']=str(PYROOT)
    cfg=Path(tempfile.gettempdir())/'npps4_v532_validate.toml'
    cfg.write_text('[download]\ndefault_profile="cn"\n[download.profiles.cn]\nenabled=true\nbackend="none"\n[download.profiles.gl]\nenabled=true\nbackend="none"\n',encoding='utf-8')
    os.environ['NPPS4_CONFIG']=str(cfg)
    sys.path.insert(0,str(PYROOT))
    from npps4.db import main
    from npps4.serialcode import func
    return main,func

class AsyncMain:
    def __init__(self,s): self.s=s
    async def execute(self,q): return self.s.execute(q)
    def add(self,v): self.s.add(v)
    async def flush(self): self.s.flush()
class EmptyUnit:
    async def execute(self,q): raise RuntimeError('synthetic runtime master omitted')
class Context:
    def __init__(self,s):
        self.db=SimpleNamespace(main=AsyncMain(s),unit=EmptyUnit())
        self.profile=SimpleNamespace(value='cn'); self.cache={}
    def get_cache(self,k,i): return self.cache.get((k,i))
    def set_cache(self,k,i,v): self.cache[(k,i)]=v

def static_checks():
    build=(PKG/'build_info.py').read_text()
    serial=(PKG/'serialcode/func.py').read_text()
    require('v5.32-cn-full-special-accessory-map-fix' in build,'v5.32 build marker')
    require('_create_consumable_unit_from_bundled_profile' not in serial,'speculative level-1 material-card generator removed')
    require('exp=int(template.exp)' in serial and 'skill_exp=int(template.skill_exp)' in serial,'target copies preserve v5.24/v5.30 maxed test-card state')
    ast.parse(serial)
    cn=sqlite3.connect(PKG/'assets/cn_client_master.db')
    counts={t:cn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ('accessory_m','accessory_level_m','accessory_special_m')}
    require(counts=={'accessory_m':479,'accessory_level_m':7469,'accessory_special_m':454},f'full CN accessory tables present: {counts}')
    pair=cn.execute('SELECT unit_id FROM accessory_special_m WHERE accessory_id=516').fetchone()
    require(pair and pair[0]==3993,'CN recipe 516 maps to Beginning Step unit 3993')
    cn.close()
    unit=sqlite3.connect(PKG/'assets/cn_unit_master.db')
    require(unit.execute('SELECT 1 FROM unit_m WHERE unit_id=3993').fetchone() is not None,'CN Unit Master contains target unit 3993')
    unit.close()
    cat=json.loads((PKG/'assets/client_catalogue/cn.json').read_text())
    require([516,3993] in cat['special_accessory_pairs'],'CN capability catalogue contains 516 -> 3993')
    require(cat['counts']['special_accessory_pairs']==454,'CN catalogue exposes all 454 dedicated recipes')

async def runtime_check(main,func):
    engine=sqlalchemy.create_engine('sqlite+pysqlite:///:memory:')
    main.common.Base.metadata.create_all(engine)
    session=sqlalchemy.orm.Session(engine)
    ctx=Context(session); user=SimpleNamespace(id=1,center_unit_owning_user_id=0)
    sources,stats=await func._special_accessory_target_sources(ctx,user)
    require(3993 in sources and 'cn' in sources[3993],'fresh CN account resolves target 3993 from current CN map without owning the accessory first')
    original=func._special_accessory_target_sources
    async def one_target(c,u):
        return {3993:{'cn'}},{'runtime_pairs':0,'current_exact_pairs':454,'owned_accessories':0,'owned_cross_profile_pairs':0}
    func._special_accessory_target_sources=one_target
    try:
        first=await func._create_maxed_unit_from_bundled_profile(ctx,user,3993,'cn')
        await ctx.db.main.flush()
        result=await func._grant_special_accessory_test_units(ctx,user,3)
    finally:
        func._special_accessory_target_sources=original
    rows=session.execute(sqlalchemy.select(main.Unit).where(main.Unit.unit_id==3993).order_by(main.Unit.id)).scalars().all()
    require(result['created']==2 and result['verified']==1 and not result['missing'],'one existing target is topped up by exactly two copies')
    require(len(rows)==3,'database contains exactly three Beginning Step copies')
    state={(r.exp,r.skill_exp,r.max_level,r.love,r.rank,r.display_rank,r.level_limit_id,r.unit_removable_skill_capacity) for r in rows}
    require(len(state)==1,'new target copies exactly match the existing maxed target card state')
    require(all(r.exp>0 and r.skill_exp>=0 and r.love>0 for r in rows),'no unrelated level-1 material cards are generated')

if __name__=='__main__':
    static_checks(); main,func=import_modules(); asyncio.run(runtime_check(main,func)); print('v5.32 validation complete')
