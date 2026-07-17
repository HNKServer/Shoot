# Android Wrapper / NPPS4 v4.34 CN WebView + unitSelect fix

This patch continues from v4.33 and targets the CN 9.7.x onboarding path.

## Fixes

- Stop redirecting `/webview.php/announce/index` to FastAPI Swagger UI.  The in-game announce WebView now receives a small no-announcement HTML page.
- Move NPPS4 developer docs from `/main.php/api` and `/openapi.json` to `/npps4/api` and `/npps4/openapi.json`, so the game's batch API path is not also the documentation page.
- Add a harmless GET guard for `/main.php/api`; POST `/main.php/api` remains the real batch endpoint.
- Make CN `login/unitSelect` idempotent after onboarding has already been finalized, avoiding retry loops where the client reports a generic connection error after the first successful starter-member selection.

## Verification

- Python sources were syntax-compiled with `compileall`.
- The uploaded `sif_cn_full_log21.txt` shows the old build serving `/webview.php/announce/index -> 302 -> /main.php/api -> /openapi.json`, followed by a native `SIGTRAP` in `libGame.so` on the GL thread after `announce/checkState`.
