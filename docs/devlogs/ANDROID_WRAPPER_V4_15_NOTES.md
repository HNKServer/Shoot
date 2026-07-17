# Android Wrapper v4.15 notes

Fixes the first WebView maintenance/news dialog after CN login. v4.14 could authenticate successfully, but the client then opened `/resources/maintenance/maintenance.php`; because the Android workspace already contained an empty `templates/` directory, bundled templates were never copied and Jinja raised `TemplateNotFound: error.html`.

Changes:

- Merge-copy bundled `templates/` and `static/` into the mutable workspace on every prepare/start without overwriting user edits.
- Add a Jinja `ChoiceLoader` fallback from workspace templates to bundled APK templates.
- Make `maintenance.html` loading use `config.ROOT_DIR/templates` with bundled fallback instead of relying on current working directory only.
- Add a minimal inline HTML fallback for the error/maintenance page, so the client no longer receives a raw traceback page if template copying fails.

This does not remove v4.14 dual RSA key support.
