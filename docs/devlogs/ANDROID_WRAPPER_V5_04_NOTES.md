# Android Wrapper v5.04 — 好友主页导航与 Live 助战修复

## 已确认的两个独立故障

1. 好友列表和问候/新消息列表把 `invite_code` 填进了响应的 `user_id`；玩家资料接口却只按内部 `User.id` 查询。因此 ID 搜索进入主页正常，而从好友或消息头像进入时，`profile/liveCnt`、`profile/cardRanking`、`profile/profileInfo` 会一起返回用户不存在。
2. `get_user_guest_party_info()` 使用了并不存在的 `FRIEND_STATUS.NONE`。账号一旦拥有好友，`live/partyList` 构建助战列表就直接抛出 `AttributeError` 并返回 HTTP 500，客户端只来得及启动 BGM/渲染背景便进入维护错误页。

## v5.04 修复

- 好友列表与问候列表统一输出真实内部账号 ID；
- 三个玩家资料接口统一通过兼容解析器读取目标玩家：优先内部 ID，旧缓存或旧响应中的邀请码仍可回退解析；
- 玩家资料响应中的 `user_info.user_id` 始终规范化为内部账号 ID；
- Live 助战默认关系改为协议中真实存在的 `FRIEND_STATUS.OTHER = 0`；
- 不改好友关系、问候消息、账号或饰品数据库 Schema；
- 不修改 CN/GL 客户端字体。GL 缺少部分汉字字形属于客户端字体/字库限制，服务端无法让不存在的字形被原样绘制，除非另做文本替换或客户端资源补丁。

## 数据兼容

不需要清空客户端数据、删除好友、重发消息或迁移数据库。旧好友关系和问候记录会继续使用；服务端只修正动态返回的标识符和 Live 助战状态。
