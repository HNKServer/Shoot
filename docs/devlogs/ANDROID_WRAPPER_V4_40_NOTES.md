# v4.40 — CN version-domain / banner fatal fix

This revision is based on v4.39 and keeps the NPPS4-first policy.

## Proven regression fixed

The CN 9.7.1 APK uses `server_info.server_version` (97.4.6) as the SIF
`Client-Version` request value.  v4.37-v4.39 treated that tuple as the Android
application version when deciding whether banner type 18 was supported.
`(97, 4) > (9, 11)` was therefore true, so v4.39 still returned both banner
2 and unsupported banner 18.

The supplied CN Lua has handlers only for banner types 0-8 and 10-13.  It
indexes the handler table with `banner_type` and reads `handler.setup`
immediately; type 18 produces a nil-table Lua error and the native CLuaState
assert at libGame.so+0x259a2c.

v4.40 adds an explicit CN APK application version (default 9.7.1), separates it
from the 97.4.6 archive/content version, and derives UI capabilities from the
APK profile.  In the CN profile the response now contains only the existing
NPPS4 type-2 WebView banner.  Other NPPS4 behavior is unchanged, and later
standard clients can still receive type 18.

The server logs the profile, application version, request/content version and
actual banner types so this exact regression is visible in future logs.

## Not changed

- the established 9.7.1 application / 97.4.6 archive version split;
- `open_v98` and unrelated feature flags;
- onboarding state, roster, deck, album or center logic;
- NPPS4 reward, item, challenge, shop, friend or accessory implementations.

The same type-18 entry is also parsed by the tutorial TopView.  Its
`disable_banner=true` argument does not bypass list construction; the client
still resolves every non-WebView banner handler before later presentation
logic.  Therefore this proven bug is sufficient to explain both captured crash
paths.  A separately supplied diagnostic client patch logs the real CLuaState
error string while preserving the crash in case another failure remains.
