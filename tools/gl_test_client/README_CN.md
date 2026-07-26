# NPPS4 GL 测试客户端重建工具

成品测试 APK 已单独提供。此目录用于日后从用户自己的 `lovelive-community.apk` 重新构建。

## 已实现的修改

- 解密 post-merge JP/GL Honky v3 `config/server_info.json`；
- 将原服务端及 Battle/Duty URL 改为 `http://127.0.0.1:8080`；
- 将附加设置界面的默认地址改为 `http://127.0.0.1:8080/`；
- 包名由 `com.npdep.wrapperthingen` 改为 `moe.honoka.npps4glclient`；
- 同步修改 Manifest、动态权限、Provider authority、快捷方式与 `resources.arsc`；
- 保留 `com.npdep.wrapperthingen.ServerSettingActivity` 的 DEX 类路径，避免无谓重写类描述符；
- 重建 v1 签名和 APK Signature Scheme v2；
- 检查未压缩成员的 4 字节对齐。

## 依赖

- Python 3.12 或更高；
- JDK，命令行可找到 `jarsigner`；
- Python 包：`cryptography`、`apksigtool`、`apksigcopier`、`androguard`；
- v5.00 源码中的 `app/src/main/python`，用于 Honky v3 工具。

示例：

```powershell
py -3 .\build_gl_test_apk.py `
  --input "C:\APK\lovelive-community.apk" `
  --output "C:\APK\NPPS4-GL-TestClient.apk" `
  --python-root "C:\NPPS4-v5.00\app\src\main\python" `
  --work "C:\APK\npps4-gl-build"
```

## 测试签名

随附密钥仅为了让同一个测试客户端可以持续覆盖升级：

- Alias：`npps4gltest`
- PKCS#12 密码：`npps4gltest2026`

它是自签测试密钥，不是官方签名，也不适合生产发布。丢失该密钥后，已安装的测试客户端无法用新签名版本直接覆盖升级。

当前成品已经通过 `jarsigner` 的 v1 校验和 `apksigtool` 的 v2 校验，但尚未在本环境完成真机并存安装。
