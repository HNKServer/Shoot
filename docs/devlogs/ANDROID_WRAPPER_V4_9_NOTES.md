# Android Wrapper v4.9

This package continues the Pydantic v2 / Chaquopy Python 3.13 line and focuses on the issues observed after v4.5-v4.8.

## Fixes

- Fixed FastAPI + `typing.Annotated` compatibility errors such as:
  - `AssertionError: \`Form\` default value cannot be set in \`Annotated\` for 'request_data'. Set the default value with \`=\` instead.`
  - The affected `Form(default=None)` and `Query(default_factory=list)` declarations were changed to the newer FastAPI style.
- Kept the earlier restart-safe module cleanup and the pydantic-core / greenlet / libc++ fixes.

## Wrapper UX changes

- Foreground-service notification no longer uses Android's upload icon (`stat_sys_upload`), so the status bar should stop showing a flashing upload indicator.
- The notification is updated from starting -> running / failed instead of staying stuck at "starting".
- The main screen now auto-refreshes server status while it is visible.
- Added a "Restart server" button.
- Added a "Hot reload editable data" button.
- Config editor now has "Save and hot reload".

## Hot reload scope

Hot reload is safe for:

- `server_data.json`
- editable `external/*.py` hooks such as `login_bonus.py`

Some `config.toml` values are re-read, but structural changes still require a restart, especially:

- host / port
- database URL
- download backend
- master DB root
