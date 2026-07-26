#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import asyncio
import dataclasses
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pydantic


class Report:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def check(self, name: str, ok: object, detail: object = "") -> None:
        passed = bool(ok)
        self.rows.append({"name": name, "passed": passed, "detail": str(detail)})
        if not passed:
            raise AssertionError(f"{name}: {detail}")

    def data(self) -> dict[str, object]:
        passed = sum(bool(row["passed"]) for row in self.rows)
        return {
            "build_id": "v5.08-accessory-tab-gl-auto-create",
            "passed": passed,
            "failed": len(self.rows) - passed,
            "device_retest_required": True,
            "checks": self.rows,
        }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hashes(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
            result[path.relative_to(root).as_posix()] = sha256(path)
    return result


def extract_nodes(path: Path, names: set[str]) -> list[ast.stmt]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [
        node
        for node in module.body
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)) and node.name in names
    ]


def extract_async(path: Path, name: str) -> ast.Module:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(
        item for item in module.body if isinstance(item, ast.AsyncFunctionDef) and item.name == name
    )
    node.decorator_list = []
    node.returns = None
    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        arg.annotation = None
    mini = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(mini)
    return mini


async def dynamic_ranking(pyroot: Path, report: Report) -> None:
    path = pyroot / "npps4" / "game" / "ranking.py"

    class IdolError(Exception):
        def __init__(self, code: int, status: int):
            self.error_code = code
            self.status_code = status

    class Error:
        ERROR_CODE_LIB_ERROR = 1

        @staticmethod
        def by_code(code: int) -> IdolError:
            return IdolError(code, 600)

    class RankingResponse:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    current = SimpleNamespace(id=1)

    async def get_current(_context):
        return current

    class Reward:
        @staticmethod
        async def count_presentbox(_context, _user):
            return 0

    class EmptyRanking:
        @staticmethod
        async def get_daily_ranking(_context, page, yesterday):
            return [], 0

        @staticmethod
        async def get_daily_rank(_context, uid, yesterday):
            return 0

        @staticmethod
        async def get_live_ranking(_context, difficulty, page):
            return 0, []

        @staticmethod
        async def get_live_rank(_context, difficulty, uid):
            return 0

    namespace = {
        "__builtins__": __builtins__,
        "idol": SimpleNamespace(error=Error),
        "user": SimpleNamespace(get_current=get_current),
        "ranking": EmptyRanking,
        "reward": Reward,
        "RankingResponse": RankingResponse,
        "_ranking_data": None,
    }
    exec(compile(extract_async(path, "ranking_player"), str(path), "exec"), namespace)
    try:
        await namespace["ranking_player"](
            SimpleNamespace(), SimpleNamespace(id=1, page=0, term=1, daily_index=1)
        )
        ok, detail = False, "returned success instead of safe game error"
    except IdolError as exc:
        ok, detail = (exc.error_code, exc.status_code) == (1, 600), (exc.error_code, exc.status_code)
    report.check("ranking/player safe fallback retained", ok, detail)

    exec(compile(extract_async(path, "ranking_live"), str(path), "exec"), namespace)
    result = await namespace["ranking_live"](
        SimpleNamespace(), SimpleNamespace(page=0, live_difficulty_id=1)
    )
    report.check(
        "ranking/live safe empty success retained",
        result.items == [] and result.total_cnt == 0 and result.rank == 0,
        vars(result),
    )


async def dynamic_live_guest(pyroot: Path, report: Report) -> None:
    path = pyroot / "npps4" / "system" / "profile_projection.py"
    projected = (SimpleNamespace(unit_id=7), SimpleNamespace(default_leader_skill_id=88), "full", "stats")

    async def center(_context, _user):
        return projected

    class DB:
        value = None

        @classmethod
        async def get_decrypted_row(cls, *args):
            return cls.value

    namespace = {
        "__builtins__": __builtins__,
        "center_unit": center,
        "db": DB,
        "unit_db": SimpleNamespace(LeaderSkill=object),
    }
    exec(compile(extract_async(path, "live_guest_center_unit"), str(path), "exec"), namespace)
    function = namespace["live_guest_center_unit"]
    context = SimpleNamespace(db=SimpleNamespace(unit=object()))
    DB.value = None
    report.check("missing receiver-side guest leader skill rejected", await function(context, object()) is None)
    DB.value = SimpleNamespace()
    report.check("valid receiver-side guest leader skill accepted", await function(context, object()) is projected)


def dynamic_request_model(unit_path: Path, report: Report) -> None:
    node = extract_nodes(unit_path, {"UnitCreateAccessoryRequest"})[0]
    module = ast.Module(body=[ast.Import(names=[ast.alias(name="pydantic")]), node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {}
    exec(compile(module, str(unit_path), "exec"), namespace)
    request_class = namespace["UnitCreateAccessoryRequest"]

    for raw, expected in [([21, 22], [[21, 22]]), ([[21, 22], [26, 27]], [[21, 22], [26, 27]])]:
        value = request_class(unit_owning_user_ids=raw)
        report.check(f"request model accepts {raw!r}", value.groups() == expected, value.groups())
    for raw in ([], [1, [2]], [[1], []]):
        try:
            request_class(unit_owning_user_ids=raw)
        except pydantic.ValidationError:
            continue
        raise AssertionError(f"request model accepted invalid shape {raw!r}")
    report.check("request model rejects empty/mixed/empty-inner shapes", True)


def dynamic_response_model(unit_path: Path, report: Report) -> None:
    nodes = extract_nodes(unit_path, {"UnitCreatedAccessoryGL", "UnitCreateAccessoryResponse"})

    class AccessoryListInfo(pydantic.BaseModel):
        accessory_owning_user_id: int
        accessory_id: int
        exp: int
        next_exp: int = 0
        level: int = 1
        max_level: int = 1
        rank_up_count: int = 0
        favorite_flag: bool = False

    class TimestampMixin(pydantic.BaseModel):
        response_datetime: str = "2026-07-23 00:00:00"

    class UserDiffMixin(pydantic.BaseModel):
        before_user_info: dict
        after_user_info: dict

    class RemovableSkillOwningInfo(pydantic.BaseModel):
        owning_info: list = pydantic.Field(default_factory=list)

    namespace = {
        "pydantic": pydantic,
        "accessory_model": SimpleNamespace(AccessoryListInfo=AccessoryListInfo),
        "common": SimpleNamespace(TimestampMixin=TimestampMixin),
        "user": SimpleNamespace(UserDiffMixin=UserDiffMixin),
        "unit_model": SimpleNamespace(RemovableSkillOwningInfo=RemovableSkillOwningInfo),
    }
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(unit_path), "exec"), namespace)
    gl_class = namespace["UnitCreatedAccessoryGL"]
    response_class = namespace["UnitCreateAccessoryResponse"]
    gl_class.model_rebuild(_types_namespace=namespace)
    response_class.model_rebuild(_types_namespace=namespace)

    base = {"accessory_owning_user_id": 1, "accessory_id": 2, "exp": 0}
    common = {
        "before_user_info": {},
        "after_user_info": {},
        "use_game_coin": 1,
        "reward_box_flag": False,
        "present_cnt": 0,
        "unit_removable_skill": {},
    }
    cn = response_class(created_accessory=AccessoryListInfo(**base), **common).model_dump()
    gl = response_class(
        created_accessory=[
            gl_class(**base, reward_box_flag=False),
            gl_class(**{**base, "accessory_owning_user_id": 3}, reward_box_flag=True),
        ],
        **{**common, "reward_box_flag": True},
    ).model_dump()
    report.check(
        "CN created_accessory serializes as one object",
        isinstance(cn["created_accessory"], dict) and "reward_box_flag" not in cn["created_accessory"],
        cn["created_accessory"],
    )
    report.check(
        "GL created_accessory serializes as a list with per-entry flag",
        isinstance(gl["created_accessory"], list) and gl["created_accessory"][1]["reward_box_flag"] is True,
        gl["created_accessory"],
    )


async def dynamic_bulk_helper(accessory_path: Path, report: Report) -> None:
    nodes = extract_nodes(
        accessory_path,
        {"AccessoryCreateResult", "AccessoryBulkCreateResult", "create_from_unit_groups"},
    )

    class UserAccessory:
        pass

    class IdolError(Exception):
        def __init__(self, detail: str = ""):
            self.detail = detail
            super().__init__(detail)

    namespace = {
        "dataclasses": dataclasses,
        "main": SimpleNamespace(UserAccessory=UserAccessory, User=object),
        "idol": SimpleNamespace(SchoolIdolParams=object, error=SimpleNamespace(IdolError=IdolError)),
    }
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(accessory_path), "exec"), namespace)
    create_result = namespace["AccessoryCreateResult"]
    helper = namespace["create_from_unit_groups"]
    calls: list[list[int]] = []

    async def fake_create(context, user, group):
        calls.append(list(group))
        item = UserAccessory()
        item.group = list(group)
        return create_result(
            created=item,
            use_game_coin=sum(group),
            reward_box_flag=(group[0] % 2 == 0),
        )

    namespace["create_from_units"] = fake_create
    result = await helper(object(), object(), [[1, 2], [4]])
    report.check("bulk helper preserves one output per input group", calls == [[1, 2], [4]], calls)
    report.check("bulk helper aggregates coin and reward flags", result.use_game_coin == 7 and result.reward_box_flags == [False, True], result)
    try:
        await helper(object(), object(), [[1, 2], [2, 3]])
    except IdolError:
        pass
    else:
        raise AssertionError("duplicate owning ID was accepted across groups")
    report.check("bulk helper rejects duplicate card use across groups", True)


def validate_static(root: Path, report: Report, args: argparse.Namespace) -> tuple[Path, Path, Path]:
    pyroot = root / "app" / "src" / "main" / "python"
    npps4 = pyroot / "npps4"
    unit_path = npps4 / "game" / "unit.py"
    accessory_path = npps4 / "system" / "accessory.py"
    unit_source = unit_path.read_text(encoding="utf-8")
    accessory_source = accessory_path.read_text(encoding="utf-8")
    ranking_source = (npps4 / "game" / "ranking.py").read_text(encoding="utf-8")
    projection_source = (npps4 / "system" / "profile_projection.py").read_text(encoding="utf-8")
    advanced_source = (npps4 / "system" / "advanced.py").read_text(encoding="utf-8")
    live_source = (npps4 / "game" / "live.py").read_text(encoding="utf-8")
    core_source = (npps4 / "idol" / "core.py").read_text(encoding="utf-8")

    ast.parse(unit_source)
    ast.parse(accessory_source)
    report.check("changed Python modules parse", True)
    report.check(
        "ranking transport-safe routes retained",
        '@idol.register("ranking", "live", xmc_verify=idol.XMCVerifyMode.NONE)' in ranking_source
        and '@idol.register("ranking", "player", xmc_verify=idol.XMCVerifyMode.NONE)' in ranking_source,
    )
    report.check("ranking/player game error fallback retained", "ERROR_CODE_LIB_ERROR" in ranking_source and "total_count <= 0" in ranking_source)
    report.check("receiver-side Live guest leader skill validation retained", "async def live_guest_center_unit" in projection_source and "unit_db.LeaderSkill" in projection_source)
    report.check("partyList uses validated guest projection", "profile_projection.live_guest_center_unit(context, target_user)" in advanced_source)
    report.check("live/play uses validated guest projection", "profile_projection.live_guest_center_unit(context, guest)" in live_source)
    report.check("event-story nullable field omission retained", '@idol.register("eventscenario", "status", exclude_none=True)' in (npps4 / "game" / "eventscenario.py").read_text(encoding="utf-8"))
    report.check("signed game response path retained", "X-Message-Sign" in core_source and "build_response" in core_source)

    build_info = (npps4 / "build_info.py").read_text(encoding="utf-8")
    report.check("v5.08 build ID present", 'BUILD_ID = "v5.08-accessory-tab-gl-auto-create"' in build_info)
    if "android-wrapper" in root.name.lower():
        gradle = (root / "app" / "build.gradle").read_text(encoding="utf-8")
        report.check("Android versionCode 508", "versionCode 508" in gradle)
        report.check("Android versionName 0.5.8", "versionName '0.5.8'" in gradle)

    contract_path = npps4 / "assets" / "accessory" / "accessory_tab_list.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    expected_ids = [
        list(range(1, 10)),
        list(range(101, 110)),
        [201, 202, 203, 204, 205, 206, 207, 208, 209, 212, 213, 214],
        list(range(301, 310)),
    ]
    expected_assets = [
        list(range(1, 10)),
        list(range(10, 19)),
        list(range(24, 36)),
        [19, 20, 21, 22, 23, 36, 37, 38, 39],
    ]
    report.check("accessory contract has exactly four groups", len(contract) == 4, len(contract))
    seen_ids: set[int] = set()
    seen_paths: set[str] = set()
    for index, tab in enumerate(contract):
        ids = [entry["unit_type_id"] for entry in tab["asset_list"]]
        paths = [entry["asset_path"] for entry in tab["asset_list"]]
        expected_paths = [f"assets/image/accessory/list/list_{number}.png" for number in expected_assets[index]]
        report.check(f"accessory group {index} unit order exact", ids == expected_ids[index], ids)
        report.check(f"accessory group {index} asset order exact", paths == expected_paths, paths)
        report.check(f"accessory group {index} has no duplicate unit", not seen_ids.intersection(ids))
        report.check(f"accessory group {index} has no duplicate asset", not seen_paths.intersection(paths))
        seen_ids.update(ids)
        seen_paths.update(paths)
    report.check("no nonexistent list_40+ asset advertised", all(int(path.rsplit("_", 1)[1].split(".", 1)[0]) <= 39 for path in seen_paths))
    report.check("arithmetic fallback removed", "_FALLBACK_TABS" not in accessory_source)
    report.check("tab contract loaded as package resource", 'resources.files("npps4.assets.accessory")' in accessory_source)

    for token in (
        "list[int] | list[list[int]]",
        "create_from_unit_groups",
        "UnitCreatedAccessoryGL",
        'context.profile.value == "cn"',
        '"reward_box_flag": entry_reward_flag',
    ):
        report.check(f"implementation token present: {token}", token in unit_source + accessory_source)

    transfer_html = (pyroot / "templates" / "transfer.html").read_text(encoding="utf-8")
    report.check(
        "transfer page distinguishes SIF1 handover from SIF2 linkage",
        "SIF1 → SIF1" in transfer_html and "SIF2/ew" in transfer_html and "相册数据" in transfer_html,
    )

    if args.honoka_root:
        honoka_contract = args.honoka_root.resolve() / "assets" / "serverdata" / "accessory_tab_list.json"
        report.check("bundled accessory mapping equals supplied honoka mapping", json.loads(honoka_contract.read_text(encoding="utf-8")) == contract)

    if args.ew_root:
        ew_root = args.ew_root.resolve()
        ew_user = (ew_root / "src" / "router" / "user.rs").read_text(encoding="utf-8")
        ew_options = (ew_root / "src" / "options.rs").read_text(encoding="utf-8")
        export_source = (npps4 / "sif2export.py").read_text(encoding="utf-8")
        handover_source = (npps4 / "system" / "handover.py").read_text(encoding="utf-8")
        report.check("NPPS4 /ewexport route retained", '@app.core.get("/ewexport")' in export_source)
        report.check("ew /user/sif/migrate route present", '.route("/sif/migrate", web::post().to(sif_migrate))' in ew_user)
        report.check("ew polls configured NPPS4 /ewexport", 'format!("{}/ewexport?sha1={}"' in ew_user and "args.npps4" in ew_user)
        report.check("NPPS4 and ew use the same double-SHA1 construction", "_a_sha1(_a_sha1(transfer_id) + transfer_code)" in handover_source and '_a_sha1(&format!("{}{}", id_sha1, transfer_code))' in ew_user)
        report.check("ew imports SIF1 album units", 'clean_sif_data(&user_info["units"])' in ew_user)
        report.check("ew rank/title import boundary remains explicit", '//TODO - give rewards? Titles?' in ew_user and 'user_info["rank"]' not in ew_user and 'user_info["titles"]' not in ew_user)
        report.check("ew documents configurable NPPS4 address", 'default_value = "http://127.0.0.1:51376"' in ew_options and 'pub npps4: String' in ew_options)

    compile_result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(npps4)],
        capture_output=True,
        text=True,
    )
    report.check("Python compileall succeeds", compile_result.returncode == 0, (compile_result.stdout + compile_result.stderr)[-1000:])

    if args.peer_python:
        current, peer = tree_hashes(pyroot), tree_hashes(args.peer_python.resolve())
        report.check("Android and PC Python trees are byte-identical", current == peer, f"{len(current)} vs {len(peer)} files")

    if args.baseline_root:
        baseline = args.baseline_root.resolve()
        for relative in (
            "app/src/main/python/npps4/assets/cn_home_banner/4_0_999.zip",
            "app/src/main/python/npps4/assets/cn_home_banner/npps4_data_transfer.png",
        ):
            current_path = root / relative
            baseline_path = baseline / relative
            if current_path.exists() and baseline_path.exists():
                report.check(f"verified CN asset unchanged: {Path(relative).name}", sha256(current_path) == sha256(baseline_path))

    return pyroot, unit_path, accessory_path


async def run_dynamic(pyroot: Path, unit_path: Path, accessory_path: Path, report: Report) -> None:
    await dynamic_ranking(pyroot, report)
    await dynamic_live_guest(pyroot, report)
    dynamic_request_model(unit_path, report)
    dynamic_response_model(unit_path, report)
    await dynamic_bulk_helper(accessory_path, report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--peer-python", type=Path)
    parser.add_argument("--honoka-root", type=Path)
    parser.add_argument("--ew-root", type=Path)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    report = Report()
    pyroot, unit_path, accessory_path = validate_static(args.root.resolve(), report, args)
    asyncio.run(run_dynamic(pyroot, unit_path, accessory_path, report))
    data = report.data()
    if args.json_out:
        args.json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
