# NPPS4 v5.26 Final Validation

- Build ID：`v5.26-direct-special-accessory-level1-grant-fix`
- Android：`versionCode 526` / `versionName 0.5.26`
- `LOVEARROWSHOOT` 直接发放当前 Profile 的全部专用饰品，但统一为合法 `Lv1 / EXP 0 / rank_up_count 0`。
- CN 专用饰品 258 种、GL 专用饰品 484 种均完成实际全目录发放测试。
- 通用饰品仍按测试用途升满；专用饰品不会被兑换码升满。
- 若仅存在旧版合成的 MAX 专用饰品，会额外补一个合法 Lv1 副本，不擅自删除或降级旧记录。
- 两张精确目标 UR 的正常制作流程保持不变，制作结果仍是独立的新 Lv1 库存记录。
- 每个专用饰品目标卡写入后验证至少三张可用副本。
- 客户端原生 `remove + wear` 单请求转移契约保留。
- 回忆画廊默认纯相册模式；排名保持原始共享原分结构。
- 无数据库迁移。
- PC、Android `validate_v526.py`：通过。
- 启动导入检查和全量 `compileall`：通过。
- PC/Android 内嵌 Python：2341 个文件逐字节一致。
- 本环境未执行 Gradle APK 构建。
