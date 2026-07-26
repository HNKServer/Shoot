#!/usr/bin/env python3
"""v5.02 regression checks for the CN announcement-flow hotfix.

This validator intentionally executes the real source bodies of user.create(),
ensure_identity(), and find_identity_by_key() for both CN and GL. The v5.00
validation stopped at syntax/static checks, which cannot detect an unbound name
inside a runtime-only branch.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import builtins
import enum
import hashlib
import json
import os
import tempfile
import symtable
from pathlib import Path
from types import SimpleNamespace


class CheckReport:
    def __init__(self):
        self.rows: list[dict[str, object]] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.rows.append({"name": name, "passed": bool(condition), "detail": detail})
        if not condition:
            raise AssertionError(f"{name}: {detail}")

    def data(self) -> dict[str, object]:
        passed = sum(bool(row["passed"]) for row in self.rows)
        return {"passed": passed, "failed": len(self.rows) - passed, "checks": self.rows}


class Profile(str, enum.Enum):
    CN = "cn"
    GL = "gl"


class Column:
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return (self.name, other)


class User:
    id = Column("id")
    key = Column("key")

    def __init__(self, key=None):
        self.id = None
        self.key = key
        self.passwd = None
        self.invite_code = None

    def set_passwd(self, passwd: str):
        self.passwd = f"hash:{passwd}"


class UserClientIdentity:
    user_id = Column("user_id")
    profile = Column("profile")
    login_key = Column("login_key")

    def __init__(self, *, user_id, profile, login_key, passwd=None, external_user_id=None):
        self.user_id = user_id
        self.profile = profile
        self.login_key = login_key
        self.passwd = passwd
        self.external_user_id = external_user_id

    def set_passwd(self, passwd: str):
        self.passwd = f"hash:{passwd}"


class Select:
    def __init__(self, entity):
        self.entity = entity
        self.conditions: list[tuple[str, object]] = []

    def where(self, *conditions):
        self.conditions.extend(conditions)
        return self

    def limit(self, _value):
        return self


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar(self):
        return self.value


class FakeSession:
    def __init__(self):
        self.users: list[User] = []
        self.identities: list[UserClientIdentity] = []
        self.flush_count = 0

    def add(self, row):
        if isinstance(row, User):
            if row.id is None:
                row.id = len(self.users) + 1
            if row not in self.users:
                self.users.append(row)
        elif isinstance(row, UserClientIdentity):
            if row not in self.identities:
                self.identities.append(row)
        else:
            raise TypeError(type(row))

    async def flush(self):
        self.flush_count += 1

    async def execute(self, query: Select):
        rows = self.identities if query.entity is UserClientIdentity else self.users
        for row in rows:
            if all(getattr(row, field) == value for field, value in query.conditions):
                return ScalarResult(row)
        return ScalarResult(None)


class Context:
    def __init__(self, profile: Profile, session: FakeSession):
        self.profile = profile
        self.db = SimpleNamespace(main=session)


async def noop(*_args, **_kwargs):
    return None


def load_user_functions(user_path: Path):
    source = user_path.read_text("utf-8")
    tree = ast.parse(source, filename=str(user_path))
    wanted = {"get_identity", "find_identity_by_key", "ensure_identity", "create"}
    body = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted]
    found = {node.name for node in body}
    if found != wanted:
        raise AssertionError(f"Missing functions from user.py: {wanted - found}")

    ns = {
        "__builtins__": builtins.__dict__,
        "sqlalchemy": SimpleNamespace(select=lambda entity: Select(entity)),
        "main": SimpleNamespace(User=User, UserClientIdentity=UserClientIdentity),
        "idol": SimpleNamespace(BasicSchoolIdolContext=object),
        "config": SimpleNamespace(get_default_profile=lambda: Profile.CN),
        "achievement": SimpleNamespace(init=noop),
        "background": SimpleNamespace(init=noop),
        "award": SimpleNamespace(init=noop),
        "live": SimpleNamespace(init=noop),
        "scenario": SimpleNamespace(init=noop),
        "core": SimpleNamespace(get_invite_code=lambda user_id: 900000000 + int(user_id)),
    }
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(user_path), "exec"), ns)
    return ns, source


def _strip_function_annotations(node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
    node.returns = None
    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        arg.annotation = None
    if node.args.vararg is not None:
        node.args.vararg.annotation = None
    if node.args.kwarg is not None:
        node.args.kwarg.annotation = None
    node.decorator_list = []
    return node


async def exercise_login_startup(login_path: Path, user_path: Path, report: CheckReport):
    """Execute the actual /login/startUp route body for both profiles.

    This deliberately composes the real route body with the real user.create(),
    ensure_identity(), and find_identity_by_key() source bodies. It is still an
    isolated transaction harness, but unlike v5.00 static checks it reaches the
    exact runtime branch which failed on the device.
    """
    user_ns, _ = load_user_functions(user_path)
    tree = ast.parse(login_path.read_text("utf-8"), filename=str(login_path))
    route = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "login_startup"
    )
    route = _strip_function_annotations(route)

    decrypt_values = iter((b"new-login-key", b"new-password"))
    invalidated: list[str] = []

    async def invalidate_current(context):
        invalidated.append(context.profile.value)

    route_ns = {
        "__builtins__": builtins.__dict__,
        "base64": __import__("base64"),
        "util": SimpleNamespace(
            xorbytes=lambda *_args: b"0123456789abcdef",
            decrypt_aes=lambda *_args: next(decrypt_values),
            log=lambda *_args, **_kwargs: None,
        ),
        "user": SimpleNamespace(create=user_ns["create"]),
        "session": SimpleNamespace(invalidate_current=invalidate_current),
        "StartupResponse": lambda **kwargs: SimpleNamespace(**kwargs),
    }
    module = ast.Module(body=[route], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(login_path), "exec"), route_ns)

    for profile in (Profile.CN, Profile.GL):
        decrypt_values = iter((f"{profile.value}-route-key".encode(), b"route-password"))
        session_db = FakeSession()
        context = Context(profile, session_db)
        context.token = SimpleNamespace(
            client_key=b"A" * 32,
            server_key=b"B" * 32,
        )
        response = await route_ns["login_startup"](
            context,
            SimpleNamespace(
                login_key=__import__("base64").b64encode(b"ignored").decode(),
                login_passwd=__import__("base64").b64encode(b"ignored").decode(),
            ),
        )
        report.check(
            f"{profile.value.upper()} actual login/startUp route returns user id",
            response.user_id == "1",
        )
        report.check(
            f"{profile.value.upper()} actual login/startUp route persists identity",
            len(session_db.identities) == 1
            and session_db.identities[0].profile == profile.value
            and session_db.identities[0].login_key == f"{profile.value}-route-key",
        )
    report.check(
        "actual login/startUp invalidates both bootstrap tokens",
        invalidated == ["cn", "gl"],
        repr(invalidated),
    )


async def exercise_user_create(user_path: Path, report: CheckReport):
    ns, source = load_user_functions(user_path)
    report.check("user.py imports config", "from ..config import config" in source)
    report.check("profile comparison uses equality", "context.profile != config.get_default_profile()" in source)

    for profile in (Profile.CN, Profile.GL):
        session = FakeSession()
        context = Context(profile, session)
        user = await ns["create"](context, f"{profile.value}-new-key", "secret")
        report.check(f"{profile.value.upper()} startup creates user", user.id == 1)
        report.check(
            f"{profile.value.upper()} startup creates profile identity",
            len(session.identities) == 1
            and session.identities[0].profile == profile.value
            and session.identities[0].user_id == user.id,
        )
        report.check(
            f"{profile.value.upper()} startup preserves password mirror",
            user.passwd == "hash:secret" and session.identities[0].passwd == "hash:secret",
        )

    # v4.60 compatibility path: only the configured historical profile may
    # claim the legacy User.key fields.
    legacy_session = FakeSession()
    legacy = User("legacy-key")
    legacy.set_passwd("old")
    legacy_session.add(legacy)
    cn_result = await ns["find_identity_by_key"](Context(Profile.CN, legacy_session), "legacy-key")
    report.check(
        "CN claims v4.60 legacy identity",
        cn_result is not None and cn_result.user_id == legacy.id and cn_result.profile == "cn",
    )

    gl_session = FakeSession()
    gl_legacy = User("legacy-key")
    gl_session.add(gl_legacy)
    gl_result = await ns["find_identity_by_key"](Context(Profile.GL, gl_session), "legacy-key")
    report.check("GL cannot steal CN/default legacy identity", gl_result is None and not gl_session.identities)


def check_static_pages(py_root: Path, report: CheckReport):
    static_py = py_root / "npps4/webview/static.py"
    source = static_py.read_text("utf-8")
    tree = ast.parse(source, filename=str(static_py))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_resolve_static_page")
    ns = {
        "Path": Path,
        "_BUNDLED_STATIC_DIR": py_root / "templates/static",
    }
    mod = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(static_py), "exec"), ns)
    resolver = ns["_resolve_static_page"]
    old_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as td:
        os.chdir(td)
        try:
            p12 = resolver(12)
            p13 = resolver(13)
            p404 = resolver(999999)
        finally:
            os.chdir(old_cwd)

    report.check("fabricated static id=12 page removed", p12 is None and not (py_root / "templates/static/12.html").exists())
    report.check("static id=13 remains available", p13 is not None and p13.is_file())
    report.check("unknown static page remains a real miss", p404 is None)
    report.check("static route avoids cwd-only lookup", "Path(__file__).resolve()" in source)
    report.check("no fabricated age-rating content remains", "适龄提示" not in source and "12+" not in source)

    import fastapi
    from typing import Annotated
    route = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "static_index"
    )
    route.decorator_list = []
    route_ns = {
        "fastapi": fastapi,
        "Annotated": Annotated,
        "_resolve_static_page": resolver,
    }
    route_mod = ast.Module(body=[route], type_ignores=[])
    ast.fix_missing_locations(route_mod)
    exec(compile(route_mod, str(static_py), "exec"), route_ns)
    response12 = asyncio.run(route_ns["static_index"](12))
    response13 = asyncio.run(route_ns["static_index"](13))
    response404 = asyncio.run(route_ns["static_index"](999999))
    report.check(
        "CN static id=12 redirects to verified announcement endpoint",
        response12.status_code == 302
        and response12.headers.get("location") == "/webview.php/announce/index",
        f"status={response12.status_code} location={response12.headers.get('location')}",
    )
    report.check(
        "static id=13 still returns HTML 200",
        response13.status_code == 200 and response13.media_type.startswith("text/html"),
    )
    report.check("unknown static route returns JSON 404", response404.status_code == 404)

    announce_py = py_root / "npps4/webview/announce.py"
    announce_source = announce_py.read_text("utf-8")
    announce_tree = ast.parse(announce_source, filename=str(announce_py))
    announce_fn = next(
        node for node in announce_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "announce_index"
    )
    announce_fn.decorator_list = []
    announce_ns = {
        "fastapi": fastapi,
        "util": SimpleNamespace(stub=lambda *_args, **_kwargs: None),
    }
    announce_mod = ast.Module(body=[announce_fn], type_ignores=[])
    ast.fix_missing_locations(announce_mod)
    exec(compile(announce_mod, str(announce_py), "exec"), announce_ns)
    announce_response = announce_ns["announce_index"]()
    report.check(
        "historical NPPS4 announcement still redirects to API documentation",
        announce_response.status_code == 302
        and announce_response.headers.get("location") == "/main.php/api",
        f"status={announce_response.status_code} location={announce_response.headers.get('location')}",
    )

def check_undefined_runtime_globals(py_root: Path, report: CheckReport):
    allowed_special = {
        "__file__", "__name__", "__package__", "__doc__", "__annotations__",
        "__spec__", "__loader__", "__cached__",
    }
    problems: list[str] = []
    for path in sorted((py_root / "npps4").rglob("*.py")):
        source = path.read_text("utf-8")
        table = symtable.symtable(source, str(path), "exec")
        module_defs = {
            name
            for name in table.get_identifiers()
            if (lambda symbol: symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace())(
                table.lookup(name)
            )
        }
        allowed = module_defs | set(dir(builtins)) | allowed_special

        def walk(scope):
            for name in scope.get_identifiers():
                symbol = scope.lookup(name)
                if symbol.is_referenced() and symbol.is_global() and name not in allowed:
                    problems.append(
                        f"{path.relative_to(py_root).as_posix()}:{scope.get_lineno()}:{name}"
                    )
            for child in scope.get_children():
                walk(child)

        for child in table.get_children():
            walk(child)
    report.check(
        "all runtime global names are module-bound or built-in",
        not problems,
        "; ".join(problems[:20]),
    )


def digest_tree(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        rel = path.relative_to(root).as_posix()
        result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--peer-python", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    py_root = root / "app/src/main/python"
    report = CheckReport()

    asyncio.run(exercise_user_create(py_root / "npps4/system/user.py", report))
    asyncio.run(exercise_login_startup(
        py_root / "npps4/game/login.py",
        py_root / "npps4/system/user.py",
        report,
    ))
    check_static_pages(py_root, report)
    check_undefined_runtime_globals(py_root, report)

    build = (py_root / "npps4/build_info.py").read_text("utf-8")
    report.check("v5.02 build ID present", "v5.02-cn-announcement-flow-hotfix" in build)

    # Historical PC source bundles still contain an old, inactive Android
    # project skeleton. Only the dedicated Android Wrapper package owns the
    # current APK version metadata.
    is_android_wrapper = "android-wrapper" in root.name.lower()
    if is_android_wrapper and (root / "app/build.gradle").is_file():
        gradle = (root / "app/build.gradle").read_text("utf-8")
        report.check("Android versionCode 502", "versionCode 502" in gradle)
        report.check("Android versionName 0.5.2", "versionName '0.5.2'" in gradle)

    # The warnings in the supplied log came from using sqlite3.Connection as a
    # context manager, which does not close it. Verify all four runtime paths use
    # contextlib.closing now.
    for rel in (
        "npps4/system/content_master.py",
        "npps4/system/cn_content_master.py",
        "npps4/android_schema.py",
        "npps4/alembic/env.py",
    ):
        text = (py_root / rel).read_text("utf-8")
        report.check(f"SQLite connections close: {rel}", "from contextlib import closing" in text and "with closing(sqlite3.connect" in text)

    if args.peer_python:
        left = digest_tree(py_root)
        right = digest_tree(args.peer_python.resolve())
        report.check("Android/PC Python trees match", left == right, f"left={len(left)} right={len(right)}")

    if args.log:
        raw = args.log.read_bytes()
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or raw[:4096].count(b"\x00") > 100:
            text = raw.decode("utf-16", errors="replace")
        else:
            text = raw.decode("utf-8", errors="replace")
        report.check("device log reproduces startup NameError", "NameError: name 'config' is not defined" in text)
        report.check("device log reproduces pre-startup id=12 404", 'GET /webview.php/static/index?id=12 HTTP/1.1" 404' in text)
        report.check("device log reached login/authkey", 'POST /main.php/login/authkey HTTP/1.1" 200' in text)
        report.check("device log failed login/startUp", 'POST /main.php/login/startUp HTTP/1.1" 500' in text)

    data = report.data()
    if args.json_out:
        args.json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
