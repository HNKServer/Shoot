# NPPS4 国服缺失资源在线回退工具

## 结论

不要把国服的 `[download].backend` 整体改成 `n4dlapi`。国服使用 9.7.1 APK / 97.4.6 内容版本，国际服镜像是 59.4；整体切换会混用更新清单、包版本和 `server_info`。

安全方案是：CN ZIP 和版本链保持不变，仅把 `/cn-extracted/Android/...` 缺失的单个素材从 GL NPPS4-DLAPI 拉取到本地 overlay。

## 只补 log29 已经暴露的招募素材

```powershell
python .\npps4_gl_overlay.py probe
python .\npps4_gl_overlay.py from-log .\sif_cn_full_log29.txt .\gl-overlay --include secretbox
```

然后在旧版服务端的 `config.toml` 设置：

```toml
[download.cn_archive]
android_extracted = "C:/绝对路径/gl-overlay/Android"
```

v4.43 已内置自动在线回退，不必手工运行这一步；文件会缓存到 `data/gl_overlay_cache/Android/`。

## 下载完整 Android 国际服镜像

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\download_full_android_mirror.ps1 -Destination D:\SIF1-GL
```

Linux/WSL：

```bash
./download_full_android_mirror.sh /mnt/d/SIF1-GL
```

官方说明估算双平台约 32GB、工作空间约需 48GB。这里只下载 Android（`--no-ios`），但仍建议预留 25–35GB，实际大小以镜像当前内容为准。脚本会依次执行 `clone.py`、`update_v1.1.py`、`update_v1.2.py`。

## 回忆画廊

先下载 GL 的解密 museum master：

```powershell
python .\npps4_gl_overlay.py getdb museum .\gl-museum.db_
python .\inspect_museum_db.py .\gl-museum.db_ --json .\gl-museum-report.json
```

该 DB 适合分析和服务端转换，不能直接塞进国服更新 ZIP：客户端本地 master、行加密/发布密钥、对应场景/语音/服装资源必须一起匹配。完整 Android 镜像下载完后，应扫描 GL 更新包和 `microdl_map.json`，定位客户端实际加载的 museum master 内部路径，再生成一个高顺序的国服 99 overlay ZIP。未经验证前不要把 GL 59.4 更新包整体发给国服客户端。
