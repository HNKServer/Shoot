# Android Wrapper v4.26 - CN dynamic Honky server_info fix

This release keeps v4.25's CN compatibility audit/guard work and fixes the next
confirmed CN download failure.

## What the new log showed

After the initial 99_0_* update packages were downloaded successfully, the CN
client did not enter local /main.php download flow. GHome calls still went to
http://127.0.0.1:8080, but the game layer opened prod.game1.ll.sdo.com:80. That
means the cached CN server_info used by the native game layer still contained the
original production endpoint.

## Fix

- Add `npps4.tools.honky_cn`, a small pure-Python CN HonokaMiku/Honky-compatible
  implementation for encrypted CN `server_info.json` v3/v4 files.
- Change `npps4.download.cn_archive` so `99_0_115.zip` is materialized lazily per
  request:
  - choose a real CN `99_0_*` update package as the template, preferably
    `99_0_113.zip`;
  - decrypt the template's CN `server_info.json`;
  - patch `domain`, `api_uri`, maintenance/update/webview URIs, consumer key,
    application key and server version to the current request host;
  - re-encrypt as root `server_info.json`;
  - clone the real update package shape, remove `client_info.json`, and expose it
    to the client as `99_0_115.zip`.
- Do not mutate the user's archive mirror.
- Keep GL/JP and non-cn_archive download behavior unchanged.
- Extend `/npps4/cn-compat-audit.json` to show materialized server_info override
  files after a request has generated them.

## Test expectation

After clearing the client cache and re-running the initial update, the second
stage should no longer show `prod.game1.ll.sdo.com` in logcat. It should continue
against `127.0.0.1:8080` and then reach the normal CN data-download stage.
