# Android Wrapper v4.33 / CN compatibility preflight

基于 v4.32。目标不是继续等客户端每炸一次再补一处，而是把 CN/honoka 兼容链路里已经反复暴露的“隐式前置条件”做成启动后可查询的 preflight。

改动：

- 新增 `npps4.tools.cn_compat_preflight`。
- 新增 `/npps4/cn-preflight.json`，会一次性检查：
  - `external/*.py` provider 是否真实包含必需函数；
  - CN split master DB 是否有关键表和关键行；
  - `server_data.json` 引用的 effort box、live drop、secretbox、unit、exchange point 等 ID 是否能在 master DB 中找到；
  - 初始成员选择界面用到的硬编码 starter unit/deck unit 是否都存在；
  - CN 启动/主界面高风险路由是否注册。
- Android workspace 准备阶段不再只修 `external/login_bonus.py`，而是会修复全部默认 external hooks：
  - `badwords.py -> has_badwords`
  - `login_bonus.py -> get_rewards`
  - `beatmap.py -> get_beatmap_data/randomize_beatmaps`
  - `live_unit_drop.py -> get_live_drop_unit`
  - `live_box_drop.py -> process_effort_box`
- `config.get_*_protocol()` 也加了 provider 二次校验，避免坏的 editable hook 在运行时再次覆盖内置实现。

这版不声称已经完整实现全部国服功能；它把“接下来可能在哪里炸”从客户端 5 次连接错误提前移动到 JSON 诊断结果里。下一步应根据 `/npps4/cn-preflight.json` 的 error/warn 批量修复，而不是继续单点追 log。
