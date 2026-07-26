# NPPS4 v5.28：精确 Unit Master 投影与专用饰品目标卡可见性修复

本版严格以 v5.24 为基线，只保留 v5.26 中“缺失目标 UR 可正确写入并校验三张”的补卡修复，并修正真正阻止客户端看到这些卡牌的投影门槛。

## 根因

`LOVEARROWSHOOT` 已可从服务端内置的 CN/GL 精确 Unit Master 创建晚期目标卡；但 `profile_projection.unit_info()` 只查询可变的拆分 `unit.db_`。升级安装保留旧工作区时，旧 `unit.db_` 可能没有这些晚期行，于是：

1. 卡牌成功写入玩家数据库；
2. `unit/unitAll` 在序列化前调用 `unit_supported()`；
3. 旧拆分 Master 查不到该 Unit ID；
4. 卡牌被静默过滤，专用饰品界面继续显示 0/2。

CN 与 GL 共用玩家数据库，并且两边都经过同一个投影门槛，因此会表现为两边缺少相同的一批卡，而不是 GL 单独的 Profile 问题。

## 修复

`profile_projection.unit_info()` 现在先查询当前拆分 Master；查不到时，按照接收客户端 Profile 回退到服务端包内置的精确 CN/GL Unit Master。CN 不会接收 GL 独有卡，GL 也不会被 CN 的旧 Master 限制。

补卡逻辑继续：

- 正确处理尚未 flush、`id=None` 的新卡；
- 每个专用饰品目标 UR 保留至少三张可用副本；
- flush 后重新查询并验证，不足时明确报出 Unit ID 与数量。

## 未修改

专用饰品直接发放和自动升满、正常制作、装备限制、一步转移、排名、数据库 Schema、Museum 纯相册模式均保持 v5.24 行为。无数据库迁移。

兑换后应完全退出并重新启动游戏客户端，使客户端重新请求 `unit/unitAll`；WebView 关闭后客户端只请求 `login/topInfo` 和饰品页接口，不会热刷新本地社员缓存。
