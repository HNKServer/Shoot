# Android Wrapper v4.31

This release corrects the v4.30 login bonus fix.

## Root cause

Older Android wrapper workspaces created `external/login_bonus.py` as a one-line
placeholder before Python copied bundled defaults. Because external hooks are
user-editable, Python preserved that placeholder, so NPPS4 loaded a
`SimpleNamespace` without `get_rewards()`. `/main.php/lbonus/execute` then failed
when the real login bonus calendar was needed.

## Fix

- Repair invalid workspace `external/login_bonus.py` during Python workspace
  preparation by copying the bundled default provider.
- Preserve valid user-edited login bonus providers.
- Back up invalid placeholder files as `login_bonus.py.invalid.bak`.
- Keep the `system/lbonus.py` built-in reward schedule only as a last-resort
  protocol guard, not as the primary implementation.

## Normal flow

`/main.php/lbonus/execute` now uses the real `external/login_bonus.py`
`get_rewards(day, month, year, context)` provider, builds the monthly login
calendar, checks whether the user has already received today’s reward, grants
the item/present/achievement/effort side effects once, records the received date
in the `login_bonus` table, and returns calendar/user/present information to the
client.
