#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import compileall
import json
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
PYROOT = ROOT / "app/src/main/python"
PKG = PYROOT / "npps4"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[OK] {message}")


def install_crypto_stubs() -> None:
    names = [
        "Cryptodome", "Cryptodome.Cipher", "Cryptodome.Cipher.AES",
        "Cryptodome.Cipher.DES3", "Cryptodome.Cipher.PKCS1_v1_5",
        "Cryptodome.Hash", "Cryptodome.Hash.SHA1", "Cryptodome.Hash.SHA256",
        "Cryptodome.Protocol", "Cryptodome.Protocol.KDF",
        "Cryptodome.PublicKey", "Cryptodome.PublicKey.RSA",
        "Cryptodome.Signature", "Cryptodome.Signature.pkcs1_15",
        "Cryptodome.Util", "Cryptodome.Util.Padding",
    ]
    for name in names:
        module = types.ModuleType(name)
        if name in {
            "Cryptodome", "Cryptodome.Cipher", "Cryptodome.Hash",
            "Cryptodome.Protocol", "Cryptodome.PublicKey",
            "Cryptodome.Signature", "Cryptodome.Util",
        }:
            module.__path__ = []
        sys.modules[name] = module
    for name in names:
        if "." in name:
            parent, child = name.rsplit(".", 1)
            setattr(sys.modules[parent], child, sys.modules[name])

    class DummyCrypto:
        n = 1
        e = 65537

        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            return self

        def __getattr__(self, name):
            return self

        def update(self, *args, **kwargs):
            return None

        def sign(self, *args, **kwargs):
            return b""

        def decrypt(self, *args, **kwargs):
            return b""

        def publickey(self):
            return self

    for name in names:
        sys.modules[name].new = lambda *args, **kwargs: DummyCrypto()
    for name in ("Cryptodome.Cipher.AES", "Cryptodome.Cipher.DES3"):
        sys.modules[name].MODE_CBC = 1
        sys.modules[name].MODE_ECB = 2
    sys.modules["Cryptodome.Util.Padding"].pad = lambda value, *args, **kwargs: value
    sys.modules["Cryptodome.Util.Padding"].unpad = lambda value, *args, **kwargs: value
    sys.modules["Cryptodome.Protocol.KDF"].PBKDF2 = lambda *args, **kwargs: b""
    sys.modules["Cryptodome.PublicKey.RSA"].RsaKey = DummyCrypto
    sys.modules["Cryptodome.PublicKey.RSA"].import_key = lambda *args, **kwargs: DummyCrypto()


def import_runtime_modules():
    install_crypto_stubs()
    # The validation uses a synchronous in-memory database facade, so prevent
    # import-time creation of the project's real async engines.
    sqlalchemy.ext.asyncio.create_async_engine = lambda *args, **kwargs: object()
    sqlalchemy.ext.asyncio.async_sessionmaker = lambda *args, **kwargs: object()
    os.environ["NPPS4_ROOT_DIR"] = str(PYROOT)
    config_path = Path(tempfile.gettempdir()) / "npps4_v525_validate.toml"
    config_path.write_text(
        '[download]\ndefault_profile="gl"\n'
        '[download.profiles.gl]\nenabled=true\nbackend="none"\n',
        encoding="utf-8",
    )
    os.environ["NPPS4_CONFIG"] = str(config_path)
    sys.path.insert(0, str(PYROOT))
    from npps4.db import main
    from npps4.serialcode import func as serial_func
    from npps4.system import accessory
    return main, serial_func, accessory


class AsyncSessionFacade:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    def add(self, value):
        self.session.add(value)

    async def flush(self):
        self.session.flush()

    async def delete(self, value):
        self.session.delete(value)


class FakeContext:
    def __init__(self, session: sqlalchemy.orm.Session, profile: str = "gl"):
        self.db = SimpleNamespace(main=AsyncSessionFacade(session))
        self.profile = SimpleNamespace(value=profile)
        self._cache: dict[tuple[str, object], object] = {}

    def get_cache(self, key, identifier):
        return self._cache.get((key, identifier))

    def set_cache(self, key, identifier, value):
        self._cache[(key, identifier)] = value


def fresh_session(main):
    engine = sqlalchemy.create_engine("sqlite+pysqlite:///:memory:")
    main.common.Base.metadata.create_all(engine)
    return sqlalchemy.orm.Session(engine)


async def runtime_checks(main, serial_func, accessory) -> None:
    # Reproduce the v5.24 failure case: the exact target has no runtime owning
    # row, so _create_maxed_profile_unit returns a pending ORM object with id=None.
    session = fresh_session(main)
    context = FakeContext(session, "gl")
    user = SimpleNamespace(id=1, center_unit_owning_user_id=0)
    target_ids = {3809, 3920, 3927}

    original_catalogue = serial_func.client_catalogue.current
    original_create = serial_func._create_maxed_profile_unit

    async def fake_catalogue(_context):
        return SimpleNamespace(unit_ids=set(target_ids), special_target_unit_ids=set(target_ids))

    async def fake_create(ctx, fake_user, unit_id):
        owned = main.Unit(
            user_id=fake_user.id,
            unit_id=int(unit_id),
            active=True,
            favorite_flag=False,
            is_signed=False,
            exp=999,
            skill_exp=999,
            max_level=100,
            love=1000,
            rank=2,
            display_rank=2,
            level_limit_id=1,
            unit_removable_skill_capacity=8,
        )
        ctx.db.main.add(owned)
        return owned

    serial_func.client_catalogue.current = fake_catalogue
    serial_func._create_maxed_profile_unit = fake_create
    try:
        created = await serial_func._grant_special_accessory_test_units(context, user, 3)
    finally:
        serial_func.client_catalogue.current = original_catalogue
        serial_func._create_maxed_profile_unit = original_create
    require(created == 9, "zero-copy late targets create three exact copies each without int(None)")
    rows = session.execute(
        sqlalchemy.select(main.Unit.unit_id, sqlalchemy.func.count(main.Unit.id))
        .group_by(main.Unit.unit_id)
        .order_by(main.Unit.unit_id)
    ).all()
    require(dict(rows) == {3809: 3, 3920: 3, 3927: 3},
            "post-grant database contains three eligible copies for screenshot target cards")

    # The test resource catalogue must no longer create or maximize special
    # accessories; only ordinary accessories and material stacks are synthesized.
    session2 = fresh_session(main)
    context2 = FakeContext(session2, "gl")
    original_rows = accessory._raw_accessory_rows
    original_raw = accessory._raw_rows
    original_exists = accessory._unit_db_table_exists
    original_caps = accessory._capacities

    async def fake_accessory_rows(_context, materials=None):
        return [
            {"accessory_id": 10, "is_material": 0},
            {"accessory_id": 20, "is_material": 0},
            {"accessory_id": 30, "is_material": 1},
        ]

    async def fake_raw_rows(_context, sql, params=None):
        if "accessory_special_m" in sql:
            return [{"accessory_id": 20}]
        if "accessory_level_m" in sql:
            return [
                {"accessory_id": 10, "max_exp": 8000},
                {"accessory_id": 20, "max_exp": 9800},
                {"accessory_id": 30, "max_exp": 0},
            ]
        raise AssertionError(sql)

    async def fake_exists(_context, table):
        return table == "accessory_level_m"

    async def fake_caps(_context):
        return 9999, 999999

    accessory._raw_accessory_rows = fake_accessory_rows
    accessory._raw_rows = fake_raw_rows
    accessory._unit_db_table_exists = fake_exists
    accessory._capacities = fake_caps
    serial_func.accessory_system = accessory
    try:
        created_common, maxed_common, materials, skipped = await serial_func._grant_accessory_catalogue(
            context2, user, 9999
        )
    finally:
        accessory._raw_accessory_rows = original_rows
        accessory._raw_rows = original_raw
        accessory._unit_db_table_exists = original_exists
        accessory._capacities = original_caps
    require((created_common, maxed_common, materials, skipped) == (1, 0, 1, 0),
            "test code creates only common accessories and materials")
    owned_ids = set(session2.execute(sqlalchemy.select(main.UserAccessory.accessory_id)).scalars())
    require(owned_ids == {10}, "special accessory ID is not synthetically granted or maxed")

    # Exact GL master proves a real newly-created special is level 1 / cap 4,
    # while the old synthetic max signature is level 8 / cap 8.
    owned = main.UserAccessory(user_id=1, accessory_id=479, exp=0, rank_up_count=0)
    owned.id = 101
    level1 = await accessory.to_api_info(FakeContext(session2, "gl"), owned)
    require((level1.level, level1.max_level, level1.rank_up_count) == (1, 4, 0),
            "newly crafted GL dedicated accessory serializes as level 1, not MAX")
    old_synthetic = main.UserAccessory(user_id=1, accessory_id=479, exp=9800, rank_up_count=4)
    old_synthetic.id = 102
    old_info = await accessory.to_api_info(FakeContext(session2, "gl"), old_synthetic)
    require((old_info.level, old_info.max_level) == (8, 8),
            "v5.24 synthetic max signature is reproducible and distinguishable in tests")

    # Explicit cleanup removes only the obsolete unequipped/unfavorited MAX
    # copy, preserving a real level-1 craft and a favorite MAX copy.
    cleanup_session = fresh_session(main)
    cleanup_context = FakeContext(cleanup_session, "gl")
    synthetic = main.UserAccessory(user_id=1, accessory_id=479, exp=9800, rank_up_count=4)
    crafted = main.UserAccessory(user_id=1, accessory_id=479, exp=0, rank_up_count=0)
    favorite = main.UserAccessory(
        user_id=1, accessory_id=479, exp=9800, rank_up_count=4, favorite_flag=True
    )
    cleanup_session.add_all([synthetic, crafted, favorite])
    cleanup_session.flush()
    cleanup_result = await serial_func.cleanup_legacy_test_special_accessories(
        cleanup_context, user
    )
    remaining = list(
        cleanup_session.execute(sqlalchemy.select(main.UserAccessory)).scalars()
    )
    require("Removed 1" in cleanup_result and len(remaining) == 2,
            "explicit cleanup removes only obsolete synthetic MAX dedicated copies")
    require(any(int(row.exp) == 0 for row in remaining) and any(bool(row.favorite_flag) for row in remaining),
            "cleanup preserves level-1 crafted and favorite dedicated accessories")

    # Server now enforces the same explicit remove+wear transaction emitted by
    # both client Lua implementations. Direct transfer remains one request.
    session3 = fresh_session(main)
    context3 = FakeContext(session3, "gl")
    u1 = main.Unit(user_id=1, unit_id=100, active=True, max_level=100, rank=2,
                   display_rank=2, unit_removable_skill_capacity=8)
    u2 = main.Unit(user_id=1, unit_id=101, active=True, max_level=100, rank=2,
                   display_rank=2, unit_removable_skill_capacity=8)
    acc = main.UserAccessory(user_id=1, accessory_id=10, exp=0, rank_up_count=0)
    session3.add_all([u1, u2, acc])
    session3.flush()
    session3.add(main.UserAccessoryWear(
        user_id=1, unit_owning_user_id=u1.id, accessory_owning_user_id=acc.id
    ))
    session3.flush()

    original_get_acc = accessory.get_user_accessory
    original_get_unit = accessory.unit_system.get_unit
    original_validate = accessory.unit_system.validate_unit
    original_special = accessory._validate_special_wear_target

    async def fake_get_acc(_context, _user, owning_id):
        return session3.get(main.UserAccessory, int(owning_id))

    async def fake_get_unit(_context, owning_id):
        return session3.get(main.Unit, int(owning_id))

    def fake_validate(_user, value):
        if value is None:
            raise RuntimeError("unit missing")

    async def fake_special(_context, _accessory, _unit):
        return None

    accessory.get_user_accessory = fake_get_acc
    accessory.unit_system.get_unit = fake_get_unit
    accessory.unit_system.validate_unit = fake_validate
    accessory._validate_special_wear_target = fake_special
    try:
        rejected = False
        try:
            await accessory.wear_accessories(context3, user, [(acc.id, u2.id)], [])
        except Exception as exc:
            rejected = "included in remove" in str(getattr(exc, "detail", exc))
        require(rejected, "undeclared reassignment conflict is rejected")
        await accessory.wear_accessories(
            context3, user,
            [(acc.id, u2.id)],
            [(acc.id, u1.id)],
        )
    finally:
        accessory.get_user_accessory = original_get_acc
        accessory.unit_system.get_unit = original_get_unit
        accessory.unit_system.validate_unit = original_validate
        accessory._validate_special_wear_target = original_special
    binding = session3.execute(sqlalchemy.select(main.UserAccessoryWear)).scalar_one()
    require(binding.unit_owning_user_id == u2.id and binding.accessory_owning_user_id == acc.id,
            "explicit remove+wear atomically transfers one accessory to the new member")


def static_checks() -> None:
    build = (PKG / "build_info.py").read_text(encoding="utf-8")
    require("v5.25-special-accessory-card-grant-and-transfer-contract-fix" in build,
            "v5.25 build marker is present")
    serial = (PKG / "serialcode/func.py").read_text(encoding="utf-8")
    require("row.id is None or int(row.id) not in excluded_ids" in serial,
            "pending exact Unit rows are never converted with int(None)")
    require("dedicated-accessory target-card top-up verification failed" in serial,
            "every dedicated target is post-verified")
    require("SELECT accessory_id FROM accessory_special_m" in serial,
            "test accessory catalogue obtains exact special IDs")
    require("if accessory_id in special_accessory_ids" in serial,
            "test code skips synthetic dedicated accessories")
    accessory_source = (PKG / "system/accessory.py").read_text(encoding="utf-8")
    require("current accessory binding must be included in remove before reassignment" in accessory_source,
            "wear API requires the client's explicit old-binding removal")
    require("sqlalchemy.delete(main.UserAccessoryWear).where" in accessory_source,
            "explicit remove operations remain supported")

    for profile, accessory_filename, unit_filename, expected in (
        ("CN", "cn_client_master.db", "cn_unit_master.db", 258),
        ("GL", "gl_client_master.db", "gl_client_master.db", 484),
    ):
        with sqlite3.connect(PKG / "assets" / accessory_filename) as db:
            targets = {int(row[0]) for row in db.execute("SELECT unit_id FROM accessory_special_m")}
        with sqlite3.connect(PKG / "assets" / unit_filename) as db:
            units = {int(row[0]) for row in db.execute("SELECT unit_id FROM unit_m")}
        require(len(targets) == expected, f"{profile} exact special map count is {expected}")
        require(not (targets - units), f"{profile} every dedicated accessory target card exists")

    with sqlite3.connect(PKG / "assets/gl_client_master.db") as db:
        rows = db.execute(
            "SELECT s.accessory_id,s.unit_id,a.default_max_level,a.max_level "
            "FROM accessory_special_m s JOIN accessory_m a USING(accessory_id) "
            "WHERE s.accessory_id IN (424,462,479) ORDER BY s.accessory_id"
        ).fetchall()
    require(rows == [(424, 3809, 4, 8), (462, 3920, 4, 8), (479, 3927, 4, 8)],
            "screenshot accessories map to the exact GL cards and 4/8 level caps")

    server_data = json.loads((PKG / "server_data.json").read_text(encoding="utf-8"))
    require(any(row.get("serial_code") == "LOVEARROWSHOOT" for row in server_data["serial_codes"]),
            "LOVEARROWSHOOT remains configured")
    require(any(row.get("serial_code") == "LOVEARROWSPECIALCLEAN" for row in server_data["serial_codes"]),
            "explicit legacy synthetic-special cleanup code is configured")
    require(compileall.compile_dir(PYROOT, quiet=1), "all embedded Python compiles")


def main() -> None:
    static_checks()
    runtime_modules = import_runtime_modules()
    asyncio.run(runtime_checks(*runtime_modules))
    print("v5.25 validation complete")


if __name__ == "__main__":
    main()
