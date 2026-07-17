# Android Wrapper v4.27 - CN patch-all-99 server_info guard

Base: v4.26.

## Why this exists

v4.26 generated a dynamic honoka-style `99_0_115.zip`, but field logs still
showed the CN client opening `prod.game1.ll.sdo.com:80` after the initial 99
update stage. This means relying on a single final override package is not
sufficient for this client/archive combination: a real `99_0_*` package can still
leave or restore the original SDO endpoint.

## Change

For `download.backend = "cn_archive"` only:

- Every CN `99_0_*.zip` update package served through `/cn-archives/...` is now
  inspected on demand.
- If it contains encrypted `server_info.json` or `config/server_info.json`, that
  entry is decrypted with the CN Honky helper, patched to the current request
  host, and re-encrypted.
- Plain `client_info.json` is also patched best-effort if it contains
  `prod.game1.ll.sdo.com` or `prod.game2.ll.sdo.com`.
- Update response sizes use the materialized patched ZIP sizes, not stale raw
  sizes.
- The original archive mirror is never modified. Patched ZIPs are cached under
  `data/cn_patched_update_packages`.
- The previous dynamic `99_0_115.zip` override remains enabled, with a v4.27 salt
  so stale v4.26 generated ZIPs are not reused.

## Expected log signal

During the first 99 update stage, logs should include lines like:

```text
CN update package patch Patched 99_0_XXX.zip -> ... domain='http://127.0.0.1:8080'
```

After the initial update, `prod.game1.ll.sdo.com` should no longer appear in the
client network logs. If it still appears, the client is loading the endpoint from
somewhere outside the served 99 update packages.
