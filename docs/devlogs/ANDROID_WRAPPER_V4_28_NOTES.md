# Android Wrapper v4.28 - server_data hotfix for CN username flow

Based on v4.27.

## Fixed

- Fixes the traceback after CN initial update packages when the client asks the private server to set a username.
- Older Android wrapper workspaces could contain an empty `npps4/server_data.json` (`{}`), which made `user/changeName -> test_name -> contains_badwords` crash with a Pydantic v2 `SerializedServerData` validation error.
- `SerializedServerData` now provides safe defaults for optional server-side sections such as `badwords`, drop tables, secret boxes, serial codes, and sticker shop data. Provided items are still validated normally.
- The Android bootstrap now repairs stale empty/invalid `server_data.json` by copying the bundled full default file, while preserving normal user-edited files.

## Not changed

- The v4.27 CN 99 update package server_info patching logic is kept.
- GL/JP and non-cn_archive backends are unchanged.
