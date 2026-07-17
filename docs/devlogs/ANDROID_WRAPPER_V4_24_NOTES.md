# Android Wrapper v4.24

Basis: v4.23.  v4.22 one-pass download merge remains discarded.

Fixes:

- Correct the CN 99_0_115.zip override layout to match honoka-chan's documented CN workflow:
  - root-level `server_info.json`, not `config/server_info.json`.
  - preserve the real 99_0_* template bundle shape when available.
  - remove only the root `client_info.json` and replace root `server_info.json`.
- Regenerate the cached override path with a new digest marker so stale v4.23 generated zips are not reused.
- Replace the bundled fallback `cn_server_info_99_0_115.zip` with a root-level `server_info.json` zip built from the uploaded CN Termux-patched APK.
- Android workspace preparation now overwrites the old fallback only when the existing workspace copy lacks root `server_info.json`; user-provided valid root overrides are preserved.

Reason:

v4.23 still produced/installed `config/server_info.json`.  The uploaded logs show `/download/update` and `/download/event` both return 200 with empty update lists, followed by native `SIGTRAP` in `libGame.so`; register text decodes to `download list is empty !`.  That points to a malformed CN update stage rather than Java/APK installation failure.
