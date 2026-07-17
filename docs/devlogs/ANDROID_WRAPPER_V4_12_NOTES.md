# Android Wrapper v4.12

This version fixes the current CN client login loop observed in `sif_cn_full_log5.txt`.

## Root cause addressed

The server is already running. GHome/report endpoints return HTTP 200, but the SIF core request:

- `POST /main.php/login/authkey`

keeps returning HTTP 422.

The uploaded CN and Global APKs both contain the same SIF core login request template:

```text
request_data={"dummy_token":"%s","auth_data":"%s"}
%s/login/authkey
Authorize:
Client-Version: %s
Platform-Type: %d
```

The old NPPS4 parser was too strict for the Android 9.7.1 client and for raw/form request_data variants.

## Changes

- Accept three-part Android package versions such as `9.7.1` in `Client-Version` by parsing them as `(9, 7)`.
- Keep normal NPPS4 two-part versions such as `97.4` or `9.7` working.
- Make `request_data` recovery more tolerant:
  - normal `request_data={...}` form body,
  - raw body without a useful Content-Type,
  - direct form fields such as `dummy_token` / `auth_data`,
  - camelCase aliases.
- Preserve literal `+` when parsing raw `request_data=...` bodies so RSA/base64 payloads are not corrupted before validation.
- Add logging for HTTP-level exceptions, so future 422s show their actual `detail` instead of only Uvicorn's access line.
- Remove stale Python bytecode from the source package.

## Expected result

`POST /main.php/login/authkey` should stop returning 422. If it still returns 422, Logcat should now include a line beginning with:

```text
HTTP exception handling request
```

or

```text
AuthkeyRequest validation failed
```

with the actual reason.
