# Android Wrapper v4.14 - Dual RSA key support

This version fixes the regression introduced by v4.13 where replacing `default_server_key.pem` with the honoka-chan key helped CN/honoka clients but could break ordinary NPPS4/GL clients patched for NPPS4's default key.

Changes:

- Restored `default_server_key.pem` to the NPPS4 upstream/default private key.
- Added `honoka_server_key.pem` as a bundled fallback key.
- Added `npps4_default_server_key.pem` as an explicit stable copy of the NPPS4 key.
- `android_wrapper.prepare_workspace` now installs both key families into the mutable workspace.
- Existing v4.13 workspaces whose `default_server_key.pem` is the known honoka key are migrated back to the NPPS4 key and backed up as `default_server_key.pem.honoka-default.bak`.
- `npps4.config.config` now loads the primary key plus optional compatibility keys.
- `/login/authkey` now tries all configured server RSA keys and records which one successfully decrypted the client's `dummy_token`.
- Later responses for that authorize token are signed with the same RSA key, so clients whose embedded public key is either NPPS4/GL or honoka/CN can verify `X-Message-Sign`.
- No database migration is required; the token-to-key choice is runtime-only. If the app process restarts, the client should simply repeat `/login/authkey`.

Optional custom keys can be added with `NPPS4_EXTRA_SERVER_PRIVATE_KEYS`, separated by commas or by the platform path separator.
