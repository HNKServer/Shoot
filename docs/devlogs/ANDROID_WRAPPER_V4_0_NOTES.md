# Android Wrapper v4.0

修复 Pydantic v1 兼容层中的 `RootModel[T]`。Chaquopy/Android 端无法使用原先基于 `pydantic.generics.GenericModel` 的 RootModel shim；在 Python 3.13 + Pydantic v1 下会抛出：

`Type RootModel must inherit from typing.Generic before being parameterized`

v4.0 改为运行时为 `RootModel[T]` 合成具体 `BaseModel` 子类，并保留 v2 风格的 `model_validate` / `model_dump` / `model_dump_json` 行为。
