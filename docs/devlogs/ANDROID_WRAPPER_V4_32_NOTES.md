# Android Wrapper v4.32 / CN effort DB repair

基于 v4.31。修复 CN honoka split DB 生成时 `effort.db_` 缺少 `live_effort_point_box_spec_m` 默认行，导致 `/main.php/lbonus/execute` 在初始成员选择后进入登录奖励流程时报 `ValueError: invalid live_effort_point_box_spec_id 1` 的问题。

改动：

- `cn_honoka_master.py` 现在会给生成的 `effort.db_` 写入 1..5 号 Live Show reward box master rows。
- 启动时如果发现旧缓存 `data/db_cn_honoka/effort.db_` 缺少 id=1，会自动重生成 split DB；不会无条件覆盖正常 DB。
- `system/effort.py` 增加 CN-only 最后保护，避免旧只读 DB 再次让 `/lbonus/execute` 500。
- 保留 v4.31 的 login_bonus provider repair。

这不是空实现；登录奖励仍走 `external/login_bonus.py -> lbonus/execute -> reward.add_item -> login_bonus mark -> effort.add_effort` 的正常链路，只是补齐 CN 生成 DB 缺失的 effort master data。
