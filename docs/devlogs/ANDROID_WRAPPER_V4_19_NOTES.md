# Android Wrapper v4.19 notes

Fixes the post-download CN client crash seen after restarting the client.

The v4.18 Android profile set `send_patched_server_info = true`, but when no
prepared CN `99_0_115.zip` override was configured, NPPS4 appended its generic
dynamic server_info package. That package was generated with the JP honkypy
`encrypt_setup_by_gametype("JP", "config/server_info.json", 3)` path. CN 9.7.x
clients expect the CN encrypted server_info format/key schedule, so the download
could appear to finish, then the next launch crashed in `libGame.so` on the
GLThread with `SIGTRAP/TRAP_BRKPT` while reading the encrypted file path.

Changes:

- Bundle `cn_server_info_99_0_115.zip`, built from the already CN-encrypted
  `assets/server_info.json` in the uploaded Termux/CN client.
- Default CN profile now sets
  `android_server_info_override = "cn_server_info_99_0_115.zip"`.
- Android workspace preparation copies that ZIP into the mutable NPPS4 workspace.
- `/main.php/download/update` no longer appends the generic JP dynamic
  `/server_info/{hash}` package when the active backend is `cn_archive`.
- Preflight warning now says explicitly that generic server_info injection must
  not be relied upon for CN.

After installing this source build, clear the CN test client data or delete its
downloaded cache before retesting, because the previous bad JP-encrypted
server_info ZIP may already be cached under the client data directory.
