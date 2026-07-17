# Android Wrapper v4.7 notes — CN login/authkey 422 fix

This version fixes the next CN client startup blocker observed after v4.6:

- The client successfully passes the GHome/Shengqu account layer.
- It then repeatedly calls `POST /main.php/login/authkey`.
- The server answered `422 Unprocessable Content`, so the client showed a generic connection error and eventually asked to restart the game.

Root cause: CN 9.7.x behaves like honoka-chan for `/login/authkey` and may send only `dummy_token`, while NPPS4's strict Pydantic request model required both `dummy_token` and `auth_data`. FastAPI rejected the request before NPPS4 could generate the first-stage SIF token.

Changes:

- `npps4/game/login.py`
  - `AuthkeyRequest.auth_data` is now optional.
  - `/login/authkey` still decrypts the RSA `dummy_token` client key, but treats missing or malformed `auth_data` as non-fatal, matching honoka-chan's behavior.

- `npps4/idol/core.py`
  - `_get_request_data` is now tolerant of CN form/body variants around `request_data`.
  - Missing `auth_data` on `AuthkeyRequest` is normalized to an empty string instead of causing HTTP 422.

This keeps NPPS4's actual `/login/login` password verification intact; GHome still maps `userid + ticket` onto a normal NPPS4 user.
