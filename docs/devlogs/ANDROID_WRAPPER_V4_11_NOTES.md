# Android Wrapper v4.11 notes

Fixes after v4.10:

- FastAPI/Pydantic v2 compatibility: removed `Annotated[..., fastapi.Form(...)] = ...` patterns for SIF request_data dependencies and switched to plain FastAPI defaults such as `request_data: str | None = fastapi.Form(default=None)`. This avoids `AssertionError: Form default value cannot be set in Annotated for 'request_data'` on newer FastAPI.
- Status polling UI: automatic refresh now updates only the server status text. It no longer overwrites the operation/log area or refreshes path text on every poll, preventing the visible flicker and log clearing in the Server Status card.
- Error log de-duplication: repeated identical Python state errors are not appended to `npps4-wrapper-crash.log` on every 2-second poll.

Manual "刷新状态 / 健康检查" still writes one short status line to the operation log.
