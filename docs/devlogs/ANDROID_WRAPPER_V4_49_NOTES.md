# Android Wrapper v4.49 — 国服核心功能回归修复

本版本以用户提供的旧截图和 `sif_cn_full_log32.txt` 为准，只处理当前国服阶段已暴露的回归：主页数据迁移/短漫卡片、招募入口、回忆画廊开关、Wrapper 编辑器与诊断入口。未加入国服/国际服并行账号、跨服好友或其他后续阶段功能。

## 1. 主页“数据迁移”卡片与翻转/短漫

v4.48 把招募用的 `assets/image/secretbox/icon/s_ba_1718_1.png` 塞进了 `banner_type=2` 的 WebView 卡片。旧截图和客户端契约证明，正确的国服主页卡片应当是：

- `banner_type=2`
- `asset_path=assets/image/webview/wv_ba_01.png`
- `webview_url=/manga`
- `back_side=true`
- `target_id=1`
- `banner_id=200001`

v4.49 恢复这个精确契约。卡片正面应显示“数据迁移”，翻转背面应显示海报，点击后进入官方短漫列表。

## 2. 招募原生崩溃

当前国服 UI 语言为英语时，v4.48 会把招募素材请求重写成 `en/assets/image/secretbox/...`，随后从国际服 CDN overlay 拉取较新版本的 `.texb`。日志显示这些国际服标题/宣传纹理刚返回，国服客户端的 GLThread 就触发 SIGTRAP；`secretbox/all` 本身是 200，并非 Python 接口异常。

v4.49 的修复：

1. 国服的 secretbox 素材路径始终使用国服无语言前缀命名空间，不再因 UI 语言切换到 `en/`；
2. 从用户现有国服 ZIP 更新包中按优先级查找并解出精确素材，99 类更新包优先；
3. `secretbox` 与主页 WebView 卡片等版本强绑定 UI 素材禁止回退到国际服缓存/overlay；
4. 找不到国服素材时返回缺失，而不是注入不兼容的国际服二进制，让客户端使用原有缺图兜底而不是原生崩溃。

## 3. Wrapper 编辑器看似只读

v4.48 的编辑框位于外层 ScrollView 和自定义滚动条之中。部分 Samsung 系统会让父级抢走触摸序列，EditText 没能完成聚焦、游标和输入法流程。

v4.49：

- 为可编辑页面恢复真实 `TextKeyListener`；
- 显式启用游标、焦点和软键盘；
- 点击编辑器时从所有父级禁止拦截当前手势；
- 日志查看页仍保持只读、可选中文本；
- 保留 v4.48 的可拖动横纵滚动条。

## 4. 配置被 Wrapper 启动时覆盖

此前 `FileOps.ensureTemplate`/`rewriteDefaultConfig` 会在启动时重写整个 `config.toml`。因此即使用户成功修改 `museum_bridge_unlock_policy` 等开关，下一次启动也会恢复 `normal`。

v4.49 只同步 Wrapper 自己负责的路径、平台和兼容字段；用户配置和解锁策略不再被覆盖。默认模板也补齐 Museum/Archive 的所有开关。

## 5. 回忆画廊仍只有 16 项

打包的合并 Museum 数据库已经包含 1360 项（国服原有 16 项 + 国际服导入 1344 项），但默认 `museum_bridge_unlock_policy=normal` 只向用户返回正常解锁记录，所以客户端仍显示 16 项。

v4.49 没有把所有内容无条件强制解锁。测试完整画廊时，在 Wrapper 的 `config.toml` 编辑器中设置：

```toml
museum_bridge_unlock_policy = "all"
```

保存并重启服务器，再让该账号完成一次登录/每日登录同步。该值现在会持久保留。`archive` 只开放审计为停服档案的项目，`normal` 保持正常流程。

## 6. 可见的自动诊断报告

服务器状态卡新增“生成并查看诊断报告”。报告保存在工作目录 `reports/`，并在 Wrapper 内以只读编辑器打开。内容包括：

- 构建标识和运行配置；
- 国服 ZIP 数量；
- 数据迁移卡片和关键招募素材实际来自哪个 ZIP/成员；
- Museum 合并数据库、manifest 和 99_0_116 overlay 状态；
- 当前所有解锁策略；
- 每个用户的 MuseumUnlock 数量。

报告不输出服务器私钥或完整密钥内容。

## 验证状态

- Python `compileall`：通过；
- CN contract guard：通过；
- v4.49 专项验证：通过；
- 合并 Museum 行数：1360；
- 使用合成 ZIP 执行实际原始素材解析器：精确字节、99 更新包优先、顶层包装路径、缓存与 GL 禁止回退均通过；
- 诊断报告生成：通过；
- Kotlin 编译器语法阶段未发现语法错误，但当前环境没有 Android SDK/android.jar，未完成真实 Gradle APK 编译和真机渲染验证。
