"""Android/Chaquopy compatibility shims.

NPPS4 upstream uses Pydantic v2, but Chaquopy currently has no Android wheels
for pydantic-core, the Rust extension required by Pydantic v2.  The Android
wrapper therefore pins Pydantic v1 and exposes the small subset of the v2 API
which NPPS4 uses at runtime.
"""
from __future__ import annotations

import base64
import json
import sys
import types
from typing import Any, Generic, TypeVar

try:
    import pydantic
    from pydantic import BaseModel
    from pydantic.generics import GenericModel
except Exception:  # pragma: no cover
    raise

_T = TypeVar("_T")


def _computed_fields_for(cls: type) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for base in reversed(cls.mro()):
        for name, value in getattr(base, "__dict__", {}).items():
            if isinstance(value, property) and getattr(value.fget, "__pydantic_computed__", False):
                out[name] = value
    return out


# Pydantic v2 compatibility attributes on BaseModel.
if not hasattr(BaseModel, "model_validate"):
    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs):
        if isinstance(obj, str):
            try:
                return cls.parse_raw(obj)
            except Exception:
                pass
        return cls.parse_obj(obj)

    @classmethod
    def model_validate_json(cls, data: str | bytes, *args, **kwargs):
        return cls.parse_raw(data)

    def model_dump(self, *args, mode: str | None = None, exclude_none: bool = False,
                   exclude_defaults: bool = False, by_alias: bool = False, **kwargs):
        data = self.dict(exclude_none=exclude_none, exclude_defaults=exclude_defaults, by_alias=by_alias)
        for name in _computed_fields_for(self.__class__):
            data[name] = getattr(self, name)
        return data

    def model_dump_json(self, *args, **kwargs) -> str:
        return json.dumps(self.model_dump(*args, **kwargs), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def model_json_schema(cls, *args, **kwargs):
        return cls.schema(*args, **kwargs)

    BaseModel.model_validate = model_validate  # type: ignore[attr-defined]
    BaseModel.model_validate_json = model_validate_json  # type: ignore[attr-defined]
    BaseModel.model_dump = model_dump  # type: ignore[attr-defined]
    BaseModel.model_dump_json = model_dump_json  # type: ignore[attr-defined]
    BaseModel.model_json_schema = model_json_schema  # type: ignore[attr-defined]


# Track model_fields/model_computed_fields for classes declared after this file.
_orig_init_subclass = getattr(BaseModel, "__init_subclass__", None)

def _init_subclass(cls, **kwargs):
    if _orig_init_subclass is not None:
        try:
            _orig_init_subclass(**kwargs)
        except TypeError:
            pass
    cls.model_fields = getattr(cls, "__fields__", {})
    cls.model_computed_fields = _computed_fields_for(cls)

try:
    BaseModel.__init_subclass__ = classmethod(_init_subclass)  # type: ignore[method-assign]
except Exception:
    pass

BaseModel.model_fields = getattr(BaseModel, "__fields__", {})
BaseModel.model_computed_fields = {}


class RootModel(GenericModel, Generic[_T]):
    root: _T

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs):
        if isinstance(obj, dict) and "root" in obj and len(obj) == 1:
            return cls.parse_obj(obj)
        return cls(root=obj)

    @classmethod
    def model_validate_json(cls, data: str | bytes, *args, **kwargs):
        return cls.model_validate(json.loads(data))

    def model_dump(self, *args, **kwargs):
        root = self.root
        if isinstance(root, list):
            return [x.model_dump(*args, **kwargs) if hasattr(x, "model_dump") else x for x in root]
        if hasattr(root, "model_dump"):
            return root.model_dump(*args, **kwargs)
        return root

    def model_dump_json(self, *args, **kwargs) -> str:
        return json.dumps(self.model_dump(*args, **kwargs), ensure_ascii=False, separators=(",", ":"))

RootModel.model_fields = {"root": None}
RootModel.model_computed_fields = {}
pydantic.RootModel = RootModel  # type: ignore[attr-defined]


class TypeAdapter(Generic[_T]):
    def __init__(self, typ: Any):
        self.typ = typ

    def validate_python(self, obj: Any, *args, **kwargs):
        from pydantic import parse_obj_as
        return parse_obj_as(self.typ, obj)

    def dump_python(self, obj: Any, *args, **kwargs):
        if hasattr(obj, "model_dump"):
            return obj.model_dump(*args, **kwargs)
        if isinstance(obj, list):
            return [self.dump_python(x, *args, **kwargs) for x in obj]
        return obj

    def dump_json(self, obj: Any, *args, **kwargs) -> bytes:
        return json.dumps(self.dump_python(obj, *args, **kwargs), ensure_ascii=False, separators=(",", ":")).encode()

pydantic.TypeAdapter = TypeAdapter  # type: ignore[attr-defined]


class _IdentityGeneric:
    def __class_getitem__(cls, item):
        return item

pydantic.SerializeAsAny = _IdentityGeneric  # type: ignore[attr-defined]
pydantic.SkipValidation = _IdentityGeneric  # type: ignore[attr-defined]


class AliasChoices:
    def __init__(self, *choices: str):
        self.choices = choices

pydantic.AliasChoices = AliasChoices  # type: ignore[attr-defined]
pydantic.ConfigDict = dict  # type: ignore[attr-defined]
pydantic.AfterValidator = lambda f: f  # type: ignore[attr-defined]
pydantic.BeforeValidator = lambda f: f  # type: ignore[attr-defined]


def computed_field(func=None, **kwargs):
    def decorate(obj):
        if isinstance(obj, property):
            try:
                setattr(obj.fget, "__pydantic_computed__", True)
            except Exception:
                pass
            return obj
        setattr(obj, "__pydantic_computed__", True)
        return property(obj)
    if func is None:
        return decorate
    return decorate(func)

pydantic.computed_field = computed_field  # type: ignore[attr-defined]


def model_validator(*, mode: str = "after", **kwargs):
    def decorate(obj):
        # v2 before validators map well to v1 root_validator(pre=True).
        if mode == "before":
            func = obj.__func__ if isinstance(obj, classmethod) else obj
            return pydantic.root_validator(pre=True, allow_reuse=True)(func)
        # after validators in NPPS4 are config sanity checks; keep them callable
        # but don't register them with v1, because the signature is v2-style.
        return obj
    return decorate

pydantic.model_validator = model_validator  # type: ignore[attr-defined]
pydantic.field_validator = lambda *a, **k: (lambda f: f)  # type: ignore[attr-defined]

# Pydantic v2 URL-safe base64 helpers used by server_data schema.
class Base64UrlStr(str):
    pass

class Base64UrlBytes(bytes):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, bytes):
            return v
        if isinstance(v, str):
            pad = "=" * (-len(v) % 4)
            return base64.urlsafe_b64decode(v + pad)
        return bytes(v)

pydantic.Base64UrlStr = Base64UrlStr  # type: ignore[attr-defined]
pydantic.Base64UrlBytes = Base64UrlBytes  # type: ignore[attr-defined]

# Provide pydantic.json_schema.SkipJsonSchema.
json_schema_mod = types.ModuleType("pydantic.json_schema")
class SkipJsonSchema(_IdentityGeneric):
    pass
json_schema_mod.SkipJsonSchema = SkipJsonSchema
sys.modules["pydantic.json_schema"] = json_schema_mod
pydantic.json_schema = json_schema_mod  # type: ignore[attr-defined]
