# Android Wrapper v4.8 notes — stronger CN authkey request parsing

Observed after v4.7: the CN client still repeatedly called:

```text
POST /main.php/login/authkey
```

and the server still returned HTTP 422. This means the previous relaxed `auth_data`
model was not enough; the request body itself is not always arriving in the exact
`request_data={...dummy_token...}` shape NPPS4 expected.

Changes in v4.8:

- Make `AuthkeyRequest` accept snake_case, camelCase, and common wrapper keys.
- Make `dummy_token` default to an empty string so Pydantic validation does not
  short-circuit into a FastAPI HTTP 422 before endpoint code can inspect the raw
  request.
- Add recursive CN authkey extraction from `request_data`, `requestData`, `data`,
  `body`, direct form fields, or raw query-string style bodies.
- Normalize base64 values where `+` was converted to a space by form encoding.
- Change optional form dependencies to `Form(default=None)` to avoid accidental
  required-form validation.

This keeps the NPPS4 first-stage token flow intact: the endpoint still requires a
real RSA-encrypted `dummy_token` before `/login/login` can work.
