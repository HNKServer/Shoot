# Android Wrapper v4.47 — 子界面滚动条崩溃修复

## 本版本只处理一个问题

修复进入 `ConfigEditorActivity`（config.toml、server_data.json、login_bonus.py、日志查看器等所有共用子界面）时立即崩溃的问题；没有夹带服务端功能、CN/GL 架构、好友、排名或其他接口修改。

## 根因

v4.46 在用 `EditText(context)` 创建控件以后，才通过代码打开横向和纵向系统滚动条。在部分 Samsung/Android 系统中，这会创建 `ScrollabilityCache`，但不会初始化内部 `ScrollBarDrawable`。首帧绘制滚动条时，系统在 `View.onDrawScrollBars()` 对空对象调用 `mutate()`，触发：

```
java.lang.NullPointerException:
Attempt to invoke virtual method
'android.widget.ScrollBarDrawable android.widget.ScrollBarDrawable.mutate()'
on a null object reference
```

## 修复

- 新增 `Widget.NPPS4Wrapper.ScrollableEditor` 样式。
- 在 `EditText` 构造阶段就声明 `horizontal|vertical` 滚动条，而不是创建完成后才临时打开。
- 显式提供横向/纵向 thumb 和 track drawable，确保系统内部 `ScrollBarDrawable` 完整初始化。
- 保留滚动条常亮、横向滚动、纵向滚动和长文件编辑能力。
- 版本号：`0.4.29`（versionCode 429）。

## 受影响页面

- config.toml
- server_data.json
- external/login_bonus.py
- 完整崩溃/服务错误日志
- 任何通过 `ConfigEditorActivity.open(...)` 打开的后续文本页面
