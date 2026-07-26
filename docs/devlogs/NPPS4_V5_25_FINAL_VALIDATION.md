# NPPS4 v5.25 Final Validation

- Build ID：`v5.25-special-accessory-card-grant-and-transfer-contract-fix`
- 专用饰品映射：CN 258 / GL 484；目标 Unit 缺失 0。
- 从“目标卡 0 张、待写 ORM ID 为 None”的状态实际执行补齐：通过；3809、3920、3927 均得到 3 张。
- 补齐后数据库二次查询验证：通过。
- 测试码只创建通用饰品与材料，不创建/升满专用饰品：通过。
- GL 饰品 479：新制作状态为 Lv1 / 当前上限 4；旧人工状态可复现为 Lv8 / MAX：通过。
- `LOVEARROWSPECIALCLEAN`：只删除未收藏、未装备的旧人工 MAX 专用饰品，保留 Lv1 与收藏副本：通过。
- 已装备饰品未声明 remove 的转移请求：拒绝；CN/GL 客户端式 remove+wear 原子转移：通过。
- `server_data.json` JSON Schema：通过。
- Python compileall：通过。
- 无数据库迁移。
