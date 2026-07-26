# NPPS4 v5.15 最终静态验证报告

- 源码包：`NPPS4-Android-Wrapper-v5_15-friend-costume-cross-profile-fallback-source`
- 通过：**49**
- 失败：**0**

## 验证项目

- **通过**：all embedded Python files parse
- **通过**：build id is v5.15 social fallback fix
- **通过**：policy forbids wardrobe preload
- **通过**：policy forbids process-global per-user cache
- **通过**：policy forbids synthetic card ownership
- **通过**：social lookup is targeted to one owned-card id
- **通过**：receiver profile binding is queried first
- **通过**：other-profile binding is fallback-only
- **通过**：source-profile registration is validated
- **通过**：receiver Master support is validated
- **通过**：signed receiver asset is validated
- **通过**：social projection ignores target local display toggle
- **通过**：no wardrobe-table preload helper was added
- **通过**：no context/global costume cache decorator
- **通过**：owned unit supports explicit social projection
- **通过**：social base projection uses native fallback
- **通过**：main-deck center is preferred before navigation partner
- **通过**：social appearance comes from navigation partner
- **通过**：unsupported owned cards are skipped, never invented
- **通过**：Live guest validates leader-skill support
- **通过**：partyList and live/play share one guest selector
- **通过**：partyList rejects an empty unsafe payload
- **通过**：friend uses social costume projection
- **通过**：profile uses social costume projection
- **通过**：ranking uses social costume projection
- **通过**：greeting uses social costume projection
- **通过**：Live party uses social costume projection
- **通过**：profile center receives partner display costume
- **通过**：profile navigation row also receives safe partner display costume
- **通过**：friend list omits unrepresentable rows instead of null center
- **通过**：friend search fails safely for no representable card
- **通过**：profile fails safely for no representable card
- **通过**：optional costume serializer still removes JSON null
- **通过**：ordinary owned-card override still respects local toggle
- **通过**：ordinary absent binding still returns None
- **通过**：single-use wardrobe guard remains in dressUp
- **通过**：no wardrobe removal API invented
- **通过**：wire format omits absent costume key — {"unit_owning_user_id": 1, "unit_rarity_id": null, "exp": 0, "next_exp": 1, "level": 1, "level_limit_id": 1, "max_level": 80, "rank": 1, "max_rank": 2, "love": 0, "max_love": 100, "unit_skill_level": 1, "max_hp": 3, "favorite_flag": false, 
- **通过**：wire format preserves real costume object
- **通过**：unrelated None fields retain v5.12 behavior
- **通过**：dynamic: receiver-profile dress wins
- **通过**：dynamic: unsupported receiver dress falls to other profile
- **通过**：dynamic: unsupported signed asset falls to native
- **通过**：dynamic: unsupported native card is omitted
- **通过**：dynamic: social center displays navigation-partner appearance
- **通过**：dynamic: Live skips invalid unique center and picks next safe card
- **通过**：Android versionCode 515
- **通过**：Android versionName 0.5.15
- **通过**：Kotlin search TextWatcher fix preserved

## 验证边界

本报告覆盖源码语法、真实 Pydantic 服装序列化、定点跨 Profile 服装选择、导航伙伴显示契约、Live 安全候选回退、Android 版本元数据以及既有 Kotlin 编译修复。它不能代替 CN/GL 客户端真机联网、Lua 页面和实际演唱会的端到端测试。
