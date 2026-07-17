# Android Wrapper v4.50 — CN home cards, transfer WebView, manga, Museum 117 stage

This revision only addresses the current CN-client regression set. It does not
start the later CN/GL simultaneous-server or cross-region social work.

## Home carousel

The CN 9.7.1 APK has no global-client type-18 DataTransfer handler. Returning a
fake flipping type-2 card with a missing `wv_ba_01.png` asset caused a native
`GLThread` SIGTRAP before `/manga` was requested.

v4.50 therefore returns two independent CN-safe type-2 WebView cards:

- `assets/image/webview/npps4_data_transfer.png` -> `/transfer?...`
- `assets/image/webview/npps4_manga.png` -> `/manga`

Both cards use `back_side=false`; the crashing flip path is no longer exposed.
Global clients retain their existing type-18 path.

## Real data-transfer page

`/transfer` is a signed, user-bound WebView page. It uses NPPS4's real handover
state and can:

- generate a new 12-character transfer password;
- display the user's transfer ID (`invite_code`);
- invalidate the current password;
- let the existing `handover/exec` flow consume the password and invalidate it
  after a successful transfer.

The WebView token is signed with the server secret, purpose-bound and time-limited.

## Official manga

The bundled `manga.html` still contained Go-template wrapper markers inherited
from honoka-chan. Those markers are invalid Jinja syntax. v4.50 removes them and
keeps the bundled 54-chapter static gallery intact.

## Incremental 99_0_117 update

The CN content/package version is advanced from synthetic wrapper stage 97.4.6
to 97.4.7. Existing 97.4.6 clients receive only `99_0_117.zip`; older clients
still receive the complete update chain.

The runtime-generated 117 package contains:

- `db/museum/museum.db_` — merged 1360-row CN-encrypted catalogue;
- `assets/image/webview/npps4_data_transfer.png`;
- `assets/image/webview/npps4_manga.png`.

It is built from a real operator-supplied CN 99-package template and validated
before being served.

## Museum account state

The Android CN profile now defaults `museum_bridge_unlock_policy` to `all` and
migrates the v4.49 default `normal` setting to `all`, while saving the previous
config as `config.toml.pre-v450-cn-content.bak`.

After tutorial completion, the next login creates the missing MuseumUnlock rows.
The sync and stat calculation avoid 1360-value SQL `IN` clauses, so SQLite builds
with the historical 999-bind limit remain supported.

Operators can still manually restore:

```toml
museum_bridge_unlock_policy = "normal"
```

for ordinary gameplay-only unlock behavior.

## Version

- `versionCode 433`
- `versionName 0.4.32`
- build ID `v4.50-cn-banner-museum-fix`
