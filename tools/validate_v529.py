#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import ast
import os
import sqlite3
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm

ROOT = Path(__file__).resolve().parents[1]
PYROOT = ROOT / 'app/src/main/python'
PKG = PYROOT / 'npps4'


def require(value, message):
    if not value:
        raise AssertionError(message)
    print('[OK]', message)


def install_crypto_stubs():
    names = [
        'Cryptodome', 'Cryptodome.Cipher', 'Cryptodome.Cipher.AES',
        'Cryptodome.Cipher.DES3', 'Cryptodome.Cipher.PKCS1_v1_5',
        'Cryptodome.Hash', 'Cryptodome.Hash.SHA1', 'Cryptodome.Hash.SHA256',
        'Cryptodome.Protocol', 'Cryptodome.Protocol.KDF',
        'Cryptodome.PublicKey', 'Cryptodome.PublicKey.RSA',
        'Cryptodome.Signature', 'Cryptodome.Signature.pkcs1_15',
        'Cryptodome.Util', 'Cryptodome.Util.Padding',
    ]
    for name in names:
        mod = types.ModuleType(name)
        if name in {'Cryptodome','Cryptodome.Cipher','Cryptodome.Hash','Cryptodome.Protocol','Cryptodome.PublicKey','Cryptodome.Signature','Cryptodome.Util'}:
            mod.__path__ = []
        sys.modules[name] = mod
    for name in names:
        if '.' in name:
            parent, child = name.rsplit('.', 1)
            setattr(sys.modules[parent], child, sys.modules[name])
    class Dummy:
        n=1; e=65537
        def __init__(self,*a,**k): pass
        def __call__(self,*a,**k): return self
        def __getattr__(self,n): return self
        def update(self,*a,**k): return None
        def sign(self,*a,**k): return b''
        def decrypt(self,*a,**k): return b''
        def publickey(self): return self
    for name in names:
        sys.modules[name].new=lambda *a,**k: Dummy()
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
    cfg=Path(tempfile.gettempdir())/'npps4_v529_validate.toml'
    cfg.write_text('[download]\ndefault_profile="cn"\n[download.profiles.cn]\nenabled=true\nbackend="none"\n[download.profiles.gl]\nenabled=true\nbackend="none"\n',encoding='utf-8')
    os.environ['NPPS4_CONFIG']=str(cfg)
    sys.path.insert(0,str(PYROOT))
    from npps4.db import main
    from npps4.serialcode import func
    return main, func


class AsyncMain:
    def __init__(self, session): self.session=session
    async def execute(self, statement): return self.session.execute(statement)
    def add(self, value): self.session.add(value)
    async def flush(self): self.session.flush()


class EmptyUnit:
    async def execute(self, statement): raise RuntimeError('synthetic runtime master omitted')


class Context:
    def __init__(self, session, profile='cn'):
        self.db=SimpleNamespace(main=AsyncMain(session),unit=EmptyUnit())
        self.profile=SimpleNamespace(value=profile)
        self.cache={}
    def get_cache(self,key,ident): return self.cache.get((key,ident))
    def set_cache(self,key,ident,value): self.cache[(key,ident)]=value


def fresh_session(main):
    engine=sqlalchemy.create_engine('sqlite+pysqlite:///:memory:')
    main.common.Base.metadata.create_all(engine)
    return sqlalchemy.orm.Session(engine)


async def runtime_check(main, func):
    session=fresh_session(main)
    user=SimpleNamespace(id=1,center_unit_owning_user_id=0)
    # The shared account owns GL-only Letter from Honoka while the request begins
    # in CN. This reproduces the user's same-grey-accessory observation.
    session.add(main.UserAccessory(user_id=1,accessory_id=516,exp=999,rank_up_count=4))
    session.flush()
    context=Context(session,'cn')
    sources, stats=await func._special_accessory_target_sources(context,user)
    require(3993 in sources and 'gl' in sources[3993],
            'owned GL dedicated accessory resolves target unit 3993 while current profile is CN')
    require(stats['owned_cross_profile_pairs'] > 0,
            'cross-profile owned accessory mappings are counted explicitly')

    original_sources=func._special_accessory_target_sources
    original_create=func._create_maxed_profile_unit
    async def one_target(ctx, usr):
        return {3993:{'gl'}},{'runtime_pairs':0,'current_exact_pairs':0,'owned_accessories':1,'owned_cross_profile_pairs':1}
    async def current_profile_missing(ctx, usr, uid):
        raise ValueError('CN current profile intentionally lacks GL unit 3993')
    func._special_accessory_target_sources=one_target
    func._create_maxed_profile_unit=current_profile_missing
    try:
        result=await func._grant_special_accessory_test_units(context,user,3)
    finally:
        func._special_accessory_target_sources=original_sources
        func._create_maxed_profile_unit=original_create
    require(result['created']==3 and result['verified']==1 and not result['missing'],
            'bundled source profile creates and verifies three persisted copies')
    amount=session.execute(sqlalchemy.select(sqlalchemy.func.count(main.Unit.id)).where(main.Unit.unit_id==3993)).scalar_one()
    require(amount==3,'database contains exactly three target-card copies after repair')


def static_checks():
    build=(PKG/'build_info.py').read_text()
    serial=(PKG/'serialcode/func.py').read_text()
    web=(PKG/'webview/serialcode.py').read_text()
    master=(PKG/'system/accessory_master.py').read_text()
    projection=(PKG/'system/profile_projection.py').read_text()
    require('v5.29-special-target-runtime-owned-map-fix' in build,'v5.29 build marker')
    require('unit_db.AccessorySpecial.accessory_id' in serial,'active runtime accessory_special_m is queried')
    require('for profile in ("cn", "gl")' in serial,'owned accessories are resolved against both exact profile maps')
    require('row.id is None or int(row.id) not in excluded_ids' in serial,'pending ORM cards are eligible before flush')
    require('targets verified' in serial and 'runtime mappings=' in serial,'serial result exposes target-card diagnostics')
    require('context.select_profile(token_data.profile)' in web,'serial WebView restores authenticated session profile')
    require('raw_rows_for_profile' in master,'cross-profile immutable accessory mapping helper is present')
    require('profile_unit_master.unit_by_id(context, unit_id)' in projection,'late target cards survive unitAll projection')
    for src in (serial,web,master,projection): ast.parse(src)

    gl=sqlite3.connect(PKG/'assets/gl_client_master.db')
    pair=gl.execute('select unit_id from accessory_special_m where accessory_id=516').fetchone()
    require(pair and pair[0]==3993,'official GL Letter from Honoka mapping is 516 -> 3993')
    unit=gl.execute('select unit_id from unit_m where unit_id=3993').fetchone()
    require(unit is not None,'target unit 3993 exists in bundled GL Unit Master')
    gl.close()


if __name__=='__main__':
    static_checks()
    main,func=import_modules()
    asyncio.run(runtime_check(main,func))
    print('v5.29 validation complete')
