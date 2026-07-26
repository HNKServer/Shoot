# Android Wrapper v5.05 — GL Museum、跨服代表卡与 Ranking 修复

- CN/GL 各自拥有独立 `museum_unlock_policy = "normal" | "all"`，默认 `all`。
- 全解锁只使用当前 Profile 的原生 Museum Master：CN 16 项、GL 1360 项；不恢复跨服回忆画廊移植。
- Museum 正常解锁记录增加 Profile 字段，避免 CN/GL 相同数字 ID 串线。
- 个人主页、好友、问候、Live 助战与 Ranking 遇到区服独占主页/伙伴卡时，会回退到该账号库存中接收端支持的其他卡。
- `ranking/player` 的 `id > 0` 不再误当用户主键并返回 USER_NOT_EXIST。空排名和未上榜状态返回成功、空数组与 `rank = 0`。
- Live 排名和每日排名增加稳定的并列排序与当前用户名次计算。
