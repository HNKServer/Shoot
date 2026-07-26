#!/usr/bin/env python3
"""NPPS4 v5.03 regression checks for the CN forced-version gate fix.

The important behavioral boundary is that CN Android static id=12 is the native
forced-update WebView. It is intentionally non-dismissible. Normal startup must
therefore avoid requesting it by resolving CN/GL before emitting Server-Version.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import base64
import builtins
import enum
import gzip
import hashlib
import json
import os
import subprocess
import symtable
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast


class Report:
    def __init__(self):
        self.rows: list[dict[str, object]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        row = {"name": name, "passed": bool(ok), "detail": detail}
        self.rows.append(row)
        if not ok:
            raise AssertionError(f"{name}: {detail}")

    def data(self):
        passed = sum(bool(row["passed"]) for row in self.rows)
        return {"passed": passed, "failed": len(self.rows) - passed, "checks": self.rows}


class Profile(str, enum.Enum):
    CN = "cn"
    GL = "gl"

    @classmethod
    def normalize(cls, value):
        if isinstance(value, cls):
            return value
        return cls(str(value))


def strip_async_function(node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
    node.decorator_list = []
    node.returns = None
    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        arg.annotation = None
    if node.args.vararg:
        node.args.vararg.annotation = None
    if node.args.kwarg:
        node.args.kwarg.annotation = None
    return node


def extract_async(path: Path, name: str, *, class_name: str | None = None):
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))
    body = tree.body
    if class_name:
        cls = next(n for n in body if isinstance(n, ast.ClassDef) and n.name == class_name)
        body = cls.body
    node = next(n for n in body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    return strip_async_function(node)


def exec_async(node: ast.AsyncFunctionDef, path: Path, ns: dict):
    mod = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(path), "exec"), ns)
    return ns[node.name]


def check_profile_detection(pyroot: Path, report: Report):
    path = pyroot / "npps4/client_profile.py"
    ns: dict[str, object] = {}
    exec(compile(path.read_text("utf-8"), str(path), "exec"), ns)
    detect = ns["detect"]
    cp = ns["ClientProfile"]
    report.check("9.7 application version is not guessed as GL", detect(client_version=(9, 7), default=cp.CN) is cp.CN)
    report.check("9.11 application version remains default/ambiguous", detect(client_version=(9, 11), default=cp.GL) is cp.GL)
    report.check("97.x content header still identifies CN", detect(client_version=(97, 4), default=cp.GL) is cp.CN)
    report.check("59.x content header still identifies GL", detect(client_version=(59, 4), default=cp.CN) is cp.GL)
    report.check("GHome path identifies CN", detect(client_version=(9, 7), request_path="/v1/basic/loginarea", default=cp.GL) is cp.CN)


def check_rsa_key_contract(pyroot: Path, report: Report):
    cfg = (pyroot / "npps4/config/config.py").read_text("utf-8")
    report.check("config fingerprints shipped RSA keys", "known_profiles[_rsa_key_fingerprint(known_key)]" in cfg)
    report.check("honoka key maps to CN", '("honoka_server_key.pem", client_profile.ClientProfile.CN)' in cfg)
    report.check("NPPS4 default key maps to GL", '("npps4_default_server_key.pem", client_profile.ClientProfile.GL)' in cfg)
    report.check("custom RSA keys remain unguessed", "return _SERVER_KEY_PROFILES.get(label)" in cfg)

    def public_digest(path: Path) -> str:
        proc = subprocess.run(
            ["openssl", "pkey", "-in", str(path), "-pubout", "-outform", "DER"],
            check=True, capture_output=True,
        )
        return hashlib.sha256(proc.stdout).hexdigest()

    default = public_digest(pyroot / "default_server_key.pem")
    npps4 = public_digest(pyroot / "npps4_default_server_key.pem")
    honoka = public_digest(pyroot / "honoka_server_key.pem")
    report.check("wrapper primary key is the GL/NPPS4 key", default == npps4, default)
    report.check("CN/honoka key is a distinct key domain", honoka != npps4, honoka)


async def exercise_authkey_resolution(pyroot: Path, report: Report):
    path = pyroot / "npps4/game/login.py"
    fn = extract_async(path, "login_authkey")

    profiles = {"honoka_server_key": Profile.CN, "primary": Profile.GL}
    current_label = ""
    captured: list[tuple[str, str]] = []

    class Context:
        def __init__(self, initial):
            self.profile = initial
            self.server_rsa_label = None
            self.request = SimpleNamespace()
        def select_profile(self, value):
            self.profile = Profile.normalize(value)
            return self.profile

    async def recover(_context, request):
        return request

    async def encapsulate(context, _server_key, _client_key):
        captured.append((current_label, context.profile.value))
        return f"wire-{context.profile.value}"

    class Config:
        @staticmethod
        def get_server_rsa_profile(label):
            return profiles.get(label)
        @staticmethod
        def profile_enabled(_profile):
            return True

    class Util:
        logging = SimpleNamespace(DEBUG=10)
        @staticmethod
        def decrypt_rsa_any(_data):
            return b"C" * 32, current_label
        @staticmethod
        def randbytes(n):
            return b"S" * n
        @staticmethod
        def decrypt_aes(*_args):
            return b""
        @staticmethod
        def log(*_args, **_kwargs):
            return None

    class AuthkeyResponse:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    ns = {
        "__builtins__": builtins.__dict__,
        "base64": base64,
        "fastapi": __import__("fastapi"),
        "util": Util,
        "config": Config,
        "session": SimpleNamespace(encapsulate_token=encapsulate),
        "AuthkeyResponse": AuthkeyResponse,
        "_recover_cn_authkey_request": recover,
    }
    route = exec_async(fn, path, ns)

    for label, expected, initial in (
        ("honoka_server_key", Profile.CN, Profile.GL),
        ("primary", Profile.GL, Profile.CN),
    ):
        current_label = label
        context = Context(initial)
        response = await route(context, SimpleNamespace(dummy_token=base64.b64encode(b"x").decode(), auth_data=""))
        report.check(f"{label} resolves {expected.value.upper()} before token creation", context.profile is expected)
        report.check(f"{label} token records {expected.value.upper()} profile", captured[-1] == (label, expected.value), repr(captured[-1]))
        report.check(f"{label} authkey response returns resolved token", response.authorize_token == f"wire-{expected.value}")


async def exercise_session_authority(pyroot: Path, report: Report):
    path = pyroot / "npps4/idol/session.py"
    fn = extract_async(path, "finalize", class_name="SchoolIdolAuthParams")
    token = SimpleNamespace(profile=Profile.GL, server_rsa_label="primary", user_id=0)

    async def decapsulate(_self, _text):
        return token

    class Config:
        @staticmethod
        def profile_enabled(_profile):
            return True

    selected: list[Profile] = []
    context = SimpleNamespace(
        token_text="wire",
        token=None,
        profile=Profile.CN,
        server_rsa_label=None,
    )
    def select_profile(profile):
        context.profile = Profile.normalize(profile)
        selected.append(context.profile)
        return context.profile
    context.select_profile = select_profile

    ns = {
        "__builtins__": builtins.__dict__,
        "session": SimpleNamespace(decapsulate_token=decapsulate),
        "config": Config,
        "util": SimpleNamespace(log=lambda *_a, **_k: None, logging=SimpleNamespace(INFO=20)),
        "fastapi": __import__("fastapi"),
    }
    finalize = exec_async(fn, path, ns)
    await finalize(context)
    report.check("signed session profile overrides temporary header/default", selected == [Profile.GL], repr(selected))
    report.check("session RSA label is restored", context.server_rsa_label == "primary")


async def exercise_profile_bound_response(pyroot: Path, report: Report):
    path = pyroot / "npps4/idol/core.py"
    fn = extract_async(path, "build_response")
    release_calls: list[Profile] = []
    version_calls: list[Profile] = []
    cn_header_calls: list[Profile] = []

    class Model:
        def model_dump(self, exclude_none=False):
            return {"ok": True}

    class Release:
        @staticmethod
        def formatted(profile):
            release_calls.append(profile)
            return [{"id": 1, "key": profile.value}]

    class Config:
        @staticmethod
        def get_latest_version_string(profile):
            version_calls.append(profile)
            return "97.4.6" if profile is Profile.CN else "59.4"
        @staticmethod
        def get_server_rsa_by_label(_label):
            return object()
        @staticmethod
        def use_cn_headers(profile):
            cn_header_calls.append(profile)
            return profile is Profile.CN
        @staticmethod
        def get_consumer_key():
            return "lovelive_test"

    class Util:
        @staticmethod
        def sign_message(*_args):
            return "sig"
        @staticmethod
        def time():
            return 123

    def assemble(_response, _exclude):
        return {"ok": True}, 200, 200

    ns = {
        "__builtins__": builtins.__dict__,
        "json": json,
        "gzip": gzip,
        "cast": cast,
        "_PossibleResponse": list,
        "_V": object,
        "assemble_response_data": assemble,
        "release_key": Release,
        "config": Config,
        "util": Util,
        "fastapi": __import__("fastapi"),
    }
    build = exec_async(fn, path, ns)

    for profile, expected in ((Profile.CN, "97.4.6"), (Profile.GL, "59.4")):
        context = SimpleNamespace(
            profile=profile,
            server_rsa_label="honoka_server_key" if profile is Profile.CN else "primary",
            x_message_code=None,
            request=SimpleNamespace(headers={}),
            nonce=0,
            token_text=None,
            token=None,
        )
        response = await build(context, Model())
        report.check(f"{profile.value.upper()} response emits profile Server-Version", response.headers["server-version"] == expected, repr(dict(response.headers)))
        body = json.loads(response.body.decode())
        report.check(f"{profile.value.upper()} response emits profile release keys", body["release_info"][0]["key"] == profile.value)

    report.check("response version calls carry explicit profiles", version_calls == [Profile.CN, Profile.GL], repr(version_calls))
    report.check("release key calls carry explicit profiles", release_calls == [Profile.CN, Profile.GL], repr(release_calls))
    report.check("CN header decision carries explicit profiles", cn_header_calls == [Profile.CN, Profile.GL], repr(cn_header_calls))


def check_static_routes(pyroot: Path, report: Report):
    path = pyroot / "npps4/webview/static.py"
    source = path.read_text("utf-8")
    tree = ast.parse(source, filename=str(path))
    resolver_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_resolve_static_page")
    resolver_ns = {"Path": Path, "_BUNDLED_STATIC_DIR": pyroot / "templates/static"}
    mod = ast.Module(body=[resolver_node], type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, str(path), "exec"), resolver_ns)
    resolver = resolver_ns["_resolve_static_page"]

    route = extract_async(path, "static_index")
    import fastapi
    from typing import Annotated
    ns = {"__builtins__": builtins.__dict__, "fastapi": fastapi, "Annotated": Annotated, "_resolve_static_page": resolver}
    static_index = exec_async(route, path, ns)
    response12 = asyncio.run(static_index(12))
    response13 = asyncio.run(static_index(13))
    report.check("id=12 no longer masquerades as announcement", response12.status_code == 404 and "location" not in response12.headers, repr(dict(response12.headers)))
    report.check("id=13 remains the bundled static page", response13.status_code == 200)
    report.check("no fabricated id=12 file is bundled", not (pyroot / "templates/static/12.html").exists())
    report.check("static source documents native forced-update contract", "VERSION_UP_WEBVIEW_URL" in source and "no close button" in source)


def check_undefined_runtime_globals(pyroot: Path, report: Report):
    allowed_special = {"__file__", "__name__", "__package__", "__doc__", "__annotations__", "__spec__", "__loader__", "__cached__"}
    problems: list[str] = []
    for path in sorted((pyroot / "npps4").rglob("*.py")):
        source = path.read_text("utf-8")
        table = symtable.symtable(source, str(path), "exec")
        module_defs = {
            name for name in table.get_identifiers()
            if (lambda s: s.is_assigned() or s.is_imported() or s.is_namespace())(table.lookup(name))
        }
        allowed = module_defs | set(dir(builtins)) | allowed_special
        def walk(scope):
            for name in scope.get_identifiers():
                symbol = scope.lookup(name)
                if symbol.is_referenced() and symbol.is_global() and name not in allowed:
                    problems.append(f"{path.relative_to(pyroot)}:{scope.get_lineno()}:{name}")
            for child in scope.get_children():
                walk(child)
        for child in table.get_children():
            walk(child)
    report.check("all runtime globals are bound", not problems, "; ".join(problems[:20]))


def digest_tree(root: Path) -> dict[str, str]:
    out = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        out[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out



def check_cn_apk_key(apk: Path, pyroot: Path, report: Report):
    def public_der(path: Path) -> bytes:
        return subprocess.run(
            ["openssl", "pkey", "-in", str(path), "-pubout", "-outform", "DER"],
            check=True, capture_output=True,
        ).stdout
    honoka = base64.b64encode(public_der(pyroot / "honoka_server_key.pem"))
    default = base64.b64encode(public_der(pyroot / "npps4_default_server_key.pem"))
    with zipfile.ZipFile(apk) as zf:
        dex = b"".join(zf.read(name) for name in zf.namelist() if name.endswith(".dex"))
    report.check("supplied CN APK embeds honoka/CN public key", honoka in dex)
    report.check("supplied CN APK does not embed NPPS4/GL public key", default not in dex)


def check_log(log: Path, report: Report):
    raw = log.read_bytes()
    text = raw.decode("utf-16", errors="replace") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) or raw[:4096].count(b"\x00") > 100 else raw.decode("utf-8", errors="replace")
    report.check("device reached login/authkey", 'POST /main.php/login/authkey HTTP/1.1" 200' in text)
    report.check("v5.02 entered Android forced-update id=12", 'GET /webview.php/static/index?id=12 HTTP/1.1" 302' in text)
    report.check("v5.02 redirect chain loaded API docs successfully", 'GET /webview.php/announce/index HTTP/1.1" 302' in text and 'GET /main.php/api HTTP/1.1" 200' in text)
    report.check("blocked modal prevented login/startUp", '/main.php/login/startUp' not in text)
    report.check("HelpWebView remained active", 'klb.android.GameEngine.HelpWebView' in text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--peer-python", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--cn-apk", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    pyroot = root / "app/src/main/python"
    report = Report()

    check_profile_detection(pyroot, report)
    check_rsa_key_contract(pyroot, report)
    asyncio.run(exercise_authkey_resolution(pyroot, report))
    asyncio.run(exercise_session_authority(pyroot, report))
    asyncio.run(exercise_profile_bound_response(pyroot, report))
    check_static_routes(pyroot, report)
    check_undefined_runtime_globals(pyroot, report)

    build = (pyroot / "npps4/build_info.py").read_text("utf-8")
    report.check("v5.03 build ID present", "v5.03-cn-profile-version-gate-fix" in build)
    report.check("startup logger compatibility retained", "COMPAT_POLICY" in build)

    if "android-wrapper" in root.name.lower():
        gradle = (root / "app/build.gradle").read_text("utf-8")
        report.check("Android versionCode 503", "versionCode 503" in gradle)
        report.check("Android versionName 0.5.3", "versionName '0.5.3'" in gradle)

    if args.peer_python:
        left = digest_tree(pyroot)
        right = digest_tree(args.peer_python.resolve())
        report.check("Android/PC Python trees match", left == right, f"left={len(left)} right={len(right)}")
    if args.cn_apk:
        check_cn_apk_key(args.cn_apk, pyroot, report)
    if args.log:
        check_log(args.log, report)

    data = report.data()
    if args.json_out:
        args.json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
