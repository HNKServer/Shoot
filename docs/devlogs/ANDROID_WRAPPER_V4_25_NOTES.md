# Android Wrapper v4.25 notes — CN compatibility audit guards

v4.25 is based on v4.24.  It does **not** reintroduce the discarded v4.22
one-pass download merge.  The purpose of this build is to remove several places
where NPPS4's original assumptions were still being applied to CN/honoka flows,
and to make the remaining risks visible.

## Functional changes

- `/download/event` now uses a permissive request model.  honoka-chan ignores
  this body and returns an empty list, while NPPS4 had accidentally reused the
  batch request model.  That can reject CN requests shaped as
  `module/action/timeStamp` even though the handler should be a harmless no-op.
- `/download/batch` in `cn_archive` mode now checks `client_version` against the
  exact CN package version string before returning files, matching honoka-chan's
  condition.  Non-CN download backends are unchanged.
- Added `/npps4/cn-compat-audit.json`.  It reports the active compatibility
  profile, download backend, CN server-info override shape, archive preflight
  warnings, and the main areas where honoka-compatible behavior is required.

## What this deliberately does not do

- It does not copy honoka-chan gameplay wholesale into NPPS4.
- It does not make `/download/update` return all large packages in one pass.
- It does not enable `cn_optional_stubs` as proof of correctness.
- It does not change GL/JP download behavior.

## Compatibility rule going forward

CN client traffic should use this shape:

```text
CN request
→ CN profile/adapter
→ NPPS4 core state where possible
→ CN/honoka-compatible response shape
```

It should not use this shape:

```text
CN request
→ raw NPPS4 JP/GL route assumptions
→ patch individual crash symptoms later
```
