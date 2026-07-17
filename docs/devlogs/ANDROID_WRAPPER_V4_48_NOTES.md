# Android Wrapper v4.48 — 国服 Museum 登录回归与可拖动滚动条

本版本只处理日志 31 暴露出的两个回归，不加入国际服并行服务、跨服好友或其他边缘接口修改。

## 1. 初始包下载后通信错误

国服重启后的批量 `/main.php/api` 请求包含 `museum/info`。v4.46 的 Museum ORM 继承了 GL 数据库的 `_encryption_release_id` 字段，但打包的国服 `museum.server.db` 按国服真实结构有意剔除了该列。即使用户尚未解锁任何 Museum 内容，SQLAlchemy 选择完整实体时仍会生成包含该列的 SQL，导致：

`sqlite3.OperationalError: no such column: museum_contents_m._encryption_release_id`

外层批量接口仍返回 HTTP 200，但 `museum/info` 子结果为 status 500，客户端因此连续五次显示通信错误。

修复方式：Museum 存在性、ID 列表与三项属性加成只查询 CN/GL 共有的必要列，不再为这些操作加载完整 ORM 实体；空解锁列表直接返回零加成。

## 2. 真正可拖动的横纵滚动条

Android 原生 View scrollbar 只是位置指示器，不能拖动。v4.47 仅修复了 Samsung `ScrollBarDrawable` 空指针，但没有满足“拖动滑块滚动长文本”的需求。

v4.48 禁用原生指示器，加入两个自绘、常驻、可触摸拖动的控件：

- 右侧蓝色垂直滑块：上下拖动；
- 底部蓝色水平滑块：左右拖动；
- 点击轨道可跳转；
- 文本手势滚动、字体缩放、刷新日志后，滑块位置和长度同步更新；
- `config.toml`、`server_data.json`、`login_bonus.py` 与只读日志页共用同一实现。

Android 版本：`0.4.30`，versionCode `430`。
