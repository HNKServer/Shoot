# NPPS4 Android Wrapper v3.2

- Fix honoka master DB generator: it no longer imports `npps4.db.*` during conversion, so it no longer trips the active download backend before config is loaded.
- Generate split DB schemas by parsing NPPS4 source CREATE TABLE docs, then copy overlapping tables from bundled honoka `main.db`.
- Add bootstrap defaults for `game_setting_m`, `strings_m`, `unit_attribute_m`, and `add_type_m` so NPPS4 can start even when honoka lacks those tables.
- Fix Android 14+ foreground service type by declaring and using `dataSync`.
- Simplify the path mapping UI: choose exactly the CDN ZIP directory; folder name is not hardcoded and does not have to be `list_CN_Android`.
- CDN ZIPs and `99_0_115.zip` remain read-only.
