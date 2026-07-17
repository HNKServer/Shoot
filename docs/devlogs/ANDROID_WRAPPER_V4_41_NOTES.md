# v4.41 — CN Live, original announcement and post-service content access

This revision is based on v4.40 and keeps NPPS4 as the authoritative gameplay
implementation. honoka-chan is used only where it documents CN client asset or
response compatibility; it does not replace NPPS4's complete systems with
hard-coded success responses.

## 1. Restore the original NPPS4 announcement design

The NPPS4 API documentation is intentionally used as the in-game announcement
page. v4.41 restores:

- FastAPI Swagger at `/main.php/api`;
- `/` redirecting to `/main.php/api`;
- `/webview.php/announce/index` redirecting to `/main.php/api`;
- the home type-2 card linking to `/`.

The custom `暂无公告` page introduced in v4.34 is removed.

For CN 9.7.1 the type-2 poster uses the archive's unprefixed
`assets/image/webview/wv_ba_01.png` namespace. Non-CN clients keep NPPS4's
original language-specific path. This is the targeted fix for the crash which
occurred only when the home data-transfer card was flipped to its poster side.
It still requires device verification.

## 2. Let authenticated CN Live requests reach NPPS4's real Live logic

The supplied CN client repeatedly reached `/main.php/live/play` but was rejected
with HTTP 422 before `live_play()` ran because its native CROSS
`X-Message-Code` does not use NPPS4's JP/GL base_xorpad/application-key domain.

v4.41 applies a narrow compatibility rule only when all three are true:

- `[compat].region = "cn"`;
- the endpoint requests CROSS verification;
- token finalization has already produced an authenticated session.

SHARED XMC, login authentication, all non-CN clients, and the rest of NPPS4's
verification code remain unchanged. This is not a global `verify_xmc=false`
and does not replace `live/play` with an empty response: the request now enters
NPPS4's real Live start implementation. The native CN CROSS secret has not been
reconstructed, so final Live behaviour remains a device-test item.

## 3. Restore exact CN master data and post-service access

The old CN conversion copied reduced honoka-shaped tables and lost columns and
rows required by NPPS4's achievement/content systems. v4.41 bundles an exact
read-only CN 9.7.1 client master overlay and uses it to populate NPPS4's split
master databases. NPPS4 schemas remain authoritative; honoka data is only a
fallback when the exact client overlay genuinely lacks a table.

A one-time, versioned account migration now:

- adds missing currently active default-open achievements;
- restores final-service type-29 release/login achievements whose real rewards
  unlock songs or main stories present in the exact CN master;
- runs NPPS4's ordinary login achievement checker and reward processor, so the
  `New Live Show!`, `New Story!` and goal notifications are genuine game state;
- creates real completed/replayable rows for all 711 archived event-story
  chapters and 50 multi-unit story chapters, because their original event
  scheduler no longer exists;
- stores a `ContentAccessGrant` version so existing and new accounts receive the
  migration once without repeated unlock popups.

Normal progression is not mass-completed. Main-story chains, rank gates, bond
stories, card stories and Live-clear achievements retain their ordinary NPPS4
unlock conditions.

## 4. Real event and multi-unit story endpoints

The previous empty `eventscenario/status` and simplified multi-unit response
are replaced by database-backed implementations:

- `eventscenario/status`, `open`, `startup`, `reward`;
- `multiunit/multiunitscenarioStatus`, `scenarioStartup`, `scenarioReward`.

Historical archive replay does not pay old event or ranking rewards again.

## Not changed

- the working tutorial, starter roster/deck/album and home-entry chain;
- the separate 9.7.1 application and 97.4.6 archive version domains;
- `open_v98=True`;
- NPPS4 reward, item, challenge, shop, friend and accessory functionality;
- ordinary story, bond and Live progression rules.

## Validation performed

- full Python `compileall`;
- static CN contract guard;
- exact-master row/column checks;
- clean SQLite schema creation and migration;
- one-time content sync: 711 event chapters, 50 multi-unit chapters, one grant;
- second sync verified idempotent with no duplicate rows;
- ordinary NPPS4 login achievement processing produced 72 completed and 6 new
  achievements in the test account and successfully processed their real
  rewards (including 28 Live and 48 Scenario reward entries);
- direct event/multi status and startup response construction;
- full `lbonus/execute` response construction.

These validations do not replace a CN device test of banner flipping and a full
Live start/play/finish cycle.
