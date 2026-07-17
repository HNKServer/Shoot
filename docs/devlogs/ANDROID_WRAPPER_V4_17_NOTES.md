# Android Wrapper v4.17: static audit compatibility pass

This version continues the source/APK/log based compatibility audit instead of only fixing the last visible crash.

## Confirmed from the latest logs

- `/main.php/login/authkey` and `/main.php/login/login` reached `200 OK` in the CN client after the dual RSA key fix.
- The next confirmed blocker was `/main.php/download/update`: CN sends `package_list` as objects like `{package_id, package_type}`, while NPPS4 originally expected `list[int]`. v4.16 normalized that at the request boundary.
- The next WebView blocker was template fallback for `/resources/maintenance/maintenance.php`. v4.15 copied bundled templates/static and added fallback rendering.

## New v4.17 changes

1. WebView route audit
   - Added both spellings for update notice pages:
     - `/resources/maintenace/update.php`
     - `/resources/maintenance/update.php`
   - Added catch-all fallback under `/resources/maintenace/*` and `/resources/maintenance/*` so the client gets stable HTML instead of Python tracebacks.

2. GHome/SDK route audit
   - Added safe stubs for optional SDK endpoints found in the CN APK, including checktoken, countrycode, getAreaList, getPackageUrl, ad info, SMS/real-name/account deletion/payment/QR-code endpoints.
   - Added scoped fallbacks for `/v1/*`, `/agreement/*`, `/integration/*`, and `/hps4gpay/*`.
   - These are scoped to GHome paths and do not catch `/main.php/*`, so they should not mask ordinary SIF protocol bugs.

3. Download request-shape hardening
   - `download/additional.package_id` can now accept either an integer or an object containing `package_id`/`packageId`/`id`.
   - `download/getUrl.path_list` can now accept strings or simple objects containing path-like fields.

4. Android default config
   - `send_patched_server_info = true` so CN and GL clients are less likely to be redirected back to stale embedded endpoints after update packages are processed.
   - `cn_optional_stubs = true` for the Android local-CN wrapper profile.

5. CN archive preflight
   - Added `/npps4/android/preflight.json` to report archive/extracted directory status.
   - Startup logs warnings when archive/extracted directories are missing or empty, instead of waiting for the client to black-screen during download.

## Remaining high-risk areas

- True CN/GL auto profile separation is not complete. Current dual support is based on dual RSA + request-shape compatibility, while the Android default profile still uses `cn_archive`.
- Live play/reward and unit/reward batch operations may still expose request-body shape differences. They should be audited next after the client passes startup/download.
- If `download/getUrl` is used heavily, the operator must provide an extracted asset root; otherwise returned URLs will 404 even though the API response itself is valid.
