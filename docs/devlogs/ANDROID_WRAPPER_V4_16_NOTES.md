# Android Wrapper v4.16 notes

## Why this version exists

v4.14 fixed dual RSA key selection and the uploaded log shows that the CN client
now reaches the normal SIF login flow:

- `POST /main.php/login/authkey` returns `200 OK`
- `POST /main.php/login/login` returns `200 OK`
- `POST /main.php/user/userInfo` returns `200 OK`

The next server-side failure in the log is `POST /main.php/download/update` with
Pydantic validation errors for `DownloadUpdateRequest.package_list`.

## Fix

CN 9.7.x sends `package_list` entries like this:

```json
{"package_id": 578, "package_type": 1}
```

Original NPPS4 expects:

```json
578
```

Honoka-chan declares the same field as `[]any` and ignores it for update package
selection, so v4.16 keeps NPPS4's internal representation as `list[int]` but
accepts both wire shapes at the request-model boundary.

The same normalizer is also applied to `download/batch.excluded_package_ids` as
a defensive compatibility fix, while preserving the original list-of-int API.

## Audit approach going forward

Do not treat each client popup as an isolated issue.  The compatibility audit
should follow this order:

1. Extract endpoint order from Logcat and libGame strings.
2. Compare CN honoka-chan handler schemas against NPPS4 Pydantic request models.
3. Classify differences as request-shape, response-shape, resource/template,
   native dependency, Android workspace copy, or real missing gameplay system.
4. Add small request-normalizers only at boundaries when the semantics match.
5. Avoid honoka-chan gameplay shortcuts unless they are explicitly marked as
   optional discovery stubs.

