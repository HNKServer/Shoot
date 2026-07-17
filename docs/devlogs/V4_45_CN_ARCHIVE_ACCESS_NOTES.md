# v4.45 CN archive-access route audit

This revision corrects v4.44's Museum `archive` classifier and adds explicit,
idempotent access policies for main stories, side stories, Live tracks and the
card Album catalog.

## Source-level result

The upstream Museum server has only two write paths:

1. `ADD_TYPE.MUSEUM` processed by `system.advanced`;
2. account import/restore through `system.lila`.

The final international client reads `/museum/info`, applies
`museum_info.contents_id_list` to `museum_contents_m`, and marks those rows as
`is_unlock`. It contains no independent local card/story-to-Museum unlock
resolver.

A recursive scan of all bundled `server_data.json` reward sections finds 78
Museum IDs with a real gameplay path: 77 achievement rewards and ID 1698 in the
sticker shop. v4.44 inspected only `achievement_reward`, so it incorrectly
classified ID 1698 and only considered imported rows. The corrected count is:

- 1360 total Museum rows;
- 78 explicit routes in preserved NPPS4 source/data;
- 1282 rows with no preserved route.

All 77 achievement routes use checker types implemented by upstream NPPS4 and
lead back to a `default_open_flag=1` root.

## Policies

All policies default to `normal`.

```toml
[download.cn_archive]
museum_bridge_unlock_policy = "normal" # normal | archive | all
main_scenario_unlock_policy = "normal" # normal | archive | all
subscenario_unlock_policy = "normal"   # normal | archive | all
live_unlock_policy = "normal"          # normal | archive | all
album_catalog_unlock_policy = "normal" # normal | archive | all | complete
```

`archive` means no route is preserved in the supplied NPPS4 source and bundled
server data. It does not claim KLab's historical live service never had an
event/operations-side distribution route.

Story policies create visible but uncompleted rows, preserving ordinary reading
and reward behavior. Album policies create catalog/history rows only; they do
not grant physical cards. `complete` additionally marks the Album rank/bond/
level flags.

Event and multi-unit stories remain handled by v4.41's post-service archive
migration because their original event scheduler is gone.

## Static coverage

- Main story: 445 total / 400 preserved routes / 45 archive-only.
- Side story: 3357 total / 3343 max-bond routes through obtainable cards / 14 archive-only.
- Live: 366 total / 243 default-or-reward routes / 123 archive-only.
- Unit catalog: 3963 total / 3745 present in permanent scouting, bundled rewards/drops or starter roster / 218 archive-only.

Granting one physical copy of every card is intentionally not tied to archive
access: it would alter inventory capacity, duplicate handling, scouting economy,
present-box behavior and achievements. Album catalog access is the safe and
semantically consistent equivalent of Museum/story archive access.
