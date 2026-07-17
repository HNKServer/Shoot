# Android Wrapper v3.9

Fixes the persistent `Missing or unknown backend ''` error.

Root cause: on Android the project uses a Pydantic v1 compatibility layer.
NPPS4 declares `ConfigData.model_config` in the Pydantic v2 style. Under
Pydantic v1 this attribute is stored as a model field default rather than a
class attribute, so the local `pydantic_settings` shim did not see
`toml_file=...` and never loaded `config.toml`. As a result
`download.backend` stayed the default empty string.

Changes:
- make pydantic_settings recover model_config from Pydantic v1 __fields__
- make npps4.config.config set `_settings_config` explicitly before ConfigData()
- canonicalize Android config.toml on every prepare/start, backing up old config once
- bump versionCode to 39 / versionName to 0.3.9
