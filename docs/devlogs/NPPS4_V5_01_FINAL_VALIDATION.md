# NPPS4 v5.01 登录启动热修复验证报告

- Build ID：`v5.01-cn-gl-login-startup-hotfix`
- 通过：**51**
- 失败：**0**

## 真机日志结论

日志显示 `/main.php/login/authkey` 已成功返回 200，随后 `/main.php/login/startUp` 返回 500。异常链为：

```text
login/startUp
  -> user.create
  -> ensure_identity
  -> find_identity_by_key
  -> NameError: name 'config' is not defined
```

这是 v5.00 双 Profile 身份层的运行时漏导入。CN 和 GL 共用该新账号创建链，因此两端都会被阻断。另一个 `id=12` 404 是国服登录页“适龄提示”静态页面缺失，和登录 500 是两个独立问题。

## v5.01 修复

1. `npps4/system/user.py` 导入 `config`，并将 Profile 比较改为枚举值相等比较。
2. 验证器实际执行 CN、GL 两条 `login/startUp -> user.create -> ensure_identity` 源码路径。
3. 新增包内 `templates/static/12.html`，并让静态页面解析不依赖进程当前目录。
4. 显式关闭内容 Master、Android Schema 和 Alembic 的临时 SQLite 连接。
5. Android 版本更新为 `versionCode 501` / `versionName 0.5.1`。

## 回归检查

- **PASS** `user.py imports config`
- **PASS** `profile comparison uses equality`
- **PASS** `CN startup creates user`
- **PASS** `CN startup creates profile identity`
- **PASS** `CN startup preserves password mirror`
- **PASS** `GL startup creates user`
- **PASS** `GL startup creates profile identity`
- **PASS** `GL startup preserves password mirror`
- **PASS** `CN claims v4.60 legacy identity`
- **PASS** `GL cannot steal CN/default legacy identity`
- **PASS** `CN actual login/startUp route returns user id`
- **PASS** `CN actual login/startUp route persists identity`
- **PASS** `GL actual login/startUp route returns user id`
- **PASS** `GL actual login/startUp route persists identity`
- **PASS** `actual login/startUp invalidates both bootstrap tokens` — ['cn', 'gl']
- **PASS** `static id=12 bundled page resolves outside project cwd`
- **PASS** `static id=13 remains available`
- **PASS** `unknown static page remains a real miss`
- **PASS** `static id=12 is an age notice`
- **PASS** `static route avoids cwd-only lookup`
- **PASS** `static id=12 route returns HTML 200`
- **PASS** `unknown static route returns JSON 404`
- **PASS** `all runtime global names are module-bound or built-in`
- **PASS** `v5.01 build ID present`
- **PASS** `Android versionCode 501`
- **PASS** `Android versionName 0.5.1`
- **PASS** `SQLite connections close: npps4/system/content_master.py`
- **PASS** `SQLite connections close: npps4/system/cn_content_master.py`
- **PASS** `SQLite connections close: npps4/android_schema.py`
- **PASS** `SQLite connections close: npps4/alembic/env.py`
- **PASS** `Android/PC Python trees match` — left=2315 right=2315
- **PASS** `device log reproduces startup NameError`
- **PASS** `device log reproduces id=12 404`
- **PASS** `device log reached login/authkey`
- **PASS** `device log failed login/startUp`
- **PASS** `PC-side v5.01 validator passes` — passed=33 failed=0
- **PASS** `Android Python compileall passes` — python -m compileall -q -f
- **PASS** `PC Python compileall passes` — python -m compileall -q -f
- **PASS** `Android CN contract guard passes` — CN contract guard OK
- **PASS** `PC CN contract guard passes` — CN contract guard OK
- **PASS** `legacy global download preference is migration-only` — occurrences=3
- **PASS** `legacy global download preference is removed after migration`
- **PASS** `CN and GL each expose disabled/local/online controls`
- **PASS** `old one-click CN/GL quick-switch labels remain absent` — legacy mode values remain only inside one-time preference migration; old GUI labels are absent
- **PASS** `Wrapper prevents disabling CN and GL simultaneously`
- **PASS** `v5.00 verified asset/logic unchanged: app/src/main/python/npps4/assets/cn_home_banner/4_0_999.zip` — 3d20e352095d450662fc4b736e7156d5ef007c717ffd882adfd4a996f174af2b
- **PASS** `v5.00 verified asset/logic unchanged: app/src/main/python/npps4/assets/cn_home_banner/tx_wv_ba_117.texb` — 92e9339a23425f10a12251cad01a78fc0a63766acdb73ebe245897991c0abf33
- **PASS** `v5.00 verified asset/logic unchanged: app/src/main/python/npps4/assets/cn_home_banner/wv_ba_117.png.imag` — 5e8f31590e8d7dd98dd1dbe7e010d72164617feed1231a4363be166cc1b21d54
- **PASS** `v5.00 verified asset/logic unchanged: app/src/main/python/npps4/system/accessory.py` — d75db87f5ff9fac4fd28f31380f75ff110cd0669bc4aae73e2e01f76d2f0c8dd
- **PASS** `no schema migration change: app/src/main/python/npps4/db/main.py`
- **PASS** `no schema migration change: app/src/main/python/npps4/alembic/versions`

## 数据兼容

- 本热修复没有数据库 Schema 变化，不新增 Alembic 迁移。
- v5.00 的失败请求在异常时由请求事务回滚；不要求清空服务端数据库或 CN/GL 客户端数据。
- v5.00 GL 测试 APK 不需要重新修改，仍可继续指向 `127.0.0.1:8080`。
- 已验证的国服公告图片、TEXB、`4_0_999.zip` 和饰品逻辑逐字节保持不变。
- Wrapper 旧全局“一键切换”没有恢复；`download_profile` 只保留一次性迁移读取并随后删除。

## 尚需真机确认

- 本环境没有完整 Android SDK/Gradle 构建链，因此没有在这里生成新的 Wrapper APK。
- 新源码编译安装后，需要重新启动 Wrapper，并分别用 CN、GL 新账号/现有失败账号重试首次登录。
- 通过首次登录后，再继续验证后续双 Profile、好友互通和 GL 内容功能。
