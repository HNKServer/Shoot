# NPPS4 v5.01 CN/GL 登录启动热修复

## 修复对象

v5.00 双 Profile 源码在新账号 `/main.php/login/startUp` 路径中存在运行时错误：

```text
login_startup
  -> user.create
  -> ensure_identity
  -> find_identity_by_key
  -> NameError: name 'config' is not defined
```

`system/user.py` 使用 `config.get_default_profile()` 限制旧 v4.60 `User.key` 的认领范围，但漏掉了 `config` 导入。该错误不会被 `compileall` 发现，只会在真正执行新账号创建时触发，因而 CN 和 GL 都无法完成首次登录。

## v5.01 改动

1. 在 `npps4/system/user.py` 正确导入 `config`。
2. Profile 比较由对象身份比较改为枚举值相等比较。
3. 新增真实执行 `user.create()` 的 CN 与 GL 双分支回归测试。
4. 新增旧 v4.60 身份迁移测试：只有默认历史 Profile 可以认领旧 `User.key`，另一 Profile 不可误绑定进度。
5. 补齐国服登录页左下角“适龄提示”对应的 `/webview.php/static/index?id=12` 页面。
6. 静态页面不再依赖进程当前工作目录；Android/Chaquopy 和 PC 均可从包内模板目录加载。
7. 修复 GL/CN 剧情 Master、Android Schema 和 Alembic 启动路径中的 SQLite 连接未显式关闭问题。
8. Android 版本更新为 `versionCode 501` / `versionName 0.5.1`。
9. Build ID 更新为 `v5.01-cn-gl-login-startup-hotfix`。

## 数据与客户端兼容

- 数据库 Schema 没有变化，不需要新增 Alembic 迁移。
- v5.00 失败的 `login/startUp` 请求会在异常时回滚，不应留下已提交的半成品账号。
- 不需要清除 CN 或 GL 客户端数据。
- 不需要重新修改 GL 测试 APK；v5.00 GL 测试客户端仍然指向 `127.0.0.1:8080`，可继续使用。
- v4.60 已验证的国服数据迁移图片、TEXB、公告资源和 `4_0_999.zip` 未改动。
- 已验证的国服饰品逻辑未改动。
- Wrapper 中已经删除的旧“国服本地包 / 国际服在线 CDN”全局快速切换没有恢复。

## 验证方式

```bash
python tools/validate_v501.py <源码根目录> \
  --peer-python <另一平台源码根目录>/app/src/main/python
```

验证器会实际执行源码中的：

- `user.create()`；
- `ensure_identity()`；
- `find_identity_by_key()`；
- CN 新账号身份创建；
- GL 新账号身份创建；
- v4.60 旧身份认领；
- 跨 Profile 防误绑定；
- 静态页面 12/13 路由；
- 全项目运行时全局名称绑定扫描；
- Android/PC Python 树一致性。
