"""Tiny pydantic-settings subset for the Android wrapper.

It is intentionally small: just enough for NPPS4's ConfigData class, loading
config.toml and environment overrides into Pydantic v1 models.
"""
from __future__ import annotations

import os
import tomllib
from typing import Any

from pydantic import BaseModel


def SettingsConfigDict(**kwargs):
    return dict(kwargs)


class PydanticBaseSettingsSource:
    pass


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls):
        self.settings_cls = settings_cls


def _settings_config_for(cls) -> dict[str, Any]:
    """Return pydantic-settings config on both Pydantic v2 and the
    Android Pydantic v1 compatibility layer.

    In Pydantic v1, an unannotated class attribute named `model_config` is
    swallowed as a model field, so getattr(cls, "model_config") returns None.
    NPPS4 declares ConfigData.model_config in the v2 style. If we don't recover
    that default from __fields__, the TOML file is never loaded and
    download.backend remains the empty default string.
    """
    cfg = getattr(cls, "_settings_config", None)
    if isinstance(cfg, dict):
        return cfg
    cfg = getattr(cls, "model_config", None)
    if isinstance(cfg, dict):
        return cfg
    fields = getattr(cls, "__fields__", None) or getattr(cls, "model_fields", None) or {}
    field = fields.get("model_config") if isinstance(fields, dict) else None
    default = getattr(field, "default", None)
    if isinstance(default, dict):
        return default
    return {}


class BaseSettings(BaseModel):
    def __init__(self, **data: Any):
        merged: dict[str, Any] = {}
        config = _settings_config_for(self.__class__)
        toml_file = config.get("toml_file") if isinstance(config, dict) else None
        if toml_file and os.path.exists(toml_file):
            with open(toml_file, "rb") as f:
                loaded = tomllib.load(f)
                if isinstance(loaded, dict):
                    merged.update(loaded)
        # Environment support is minimal but preserves the common top-level form:
        # NPPS4_CONFIG_MAIN_DATA_DIRECTORY=value -> main.data_directory=value
        env_prefix = config.get("env_prefix", "") if isinstance(config, dict) else ""
        delim = config.get("env_nested_delimiter", "_") if isinstance(config, dict) else "_"
        for key, value in os.environ.items():
            if env_prefix and not key.startswith(env_prefix):
                continue
            path = key[len(env_prefix):].lower().split(delim)
            if len(path) >= 2:
                target = merged
                for part in path[:-1]:
                    target = target.setdefault(part, {})
                target[path[-1]] = value
        merged.update(data)
        super().__init__(**merged)

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):
        if isinstance(obj, dict):
            return cls(**obj)
        return cls.parse_obj(obj)
