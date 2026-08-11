# Gameplay Regression Work Packet 017 — BUG-031 Stage 7 Hosted Runtime Readiness Resolved Wait

Date: 2026-08-11
Owner: Planner / External Reviewer 1
Implementation owner: none; Tester owns only the bounded smoke continuation
Execution owner: Tester only after fresh plan and combined-static approval

## 0. Decision and boundary

WP-016 is deferred at an explicit human product-contract boundary between
restoring the retired SELF/TARGET dossier surface and migrating its stale
cross-family assertions to the current initiative-bar model. This packet does
not revive, choose, or absorb either alternative.

The historical pre-WP-017 inventory contained exactly twelve Promise-valued
`waitForFunction` call shapes:

- two in `hosted-game-smoke.mjs`;
- three in `inventory-panel-smoke.mjs`;
- seven in `multi-character-live-smoke.mjs`.

The two hosted shapes are absent from the frozen corrected baseline. Exactly
ten current occurrences remain: inventory three plus multi-character seven.
Inventory and multi-character both directly assert the deferred
`combatant-selection-hud` / `data-selection-frame` contract. They are not
lawful successors. WP-017 selected only the two historical hosted-game shapes;
the ten current occurrences remain explicitly open.

The selected hosted calls observe two distinct production boundaries:

1. owner input readiness requires `clientState === "my_turn_input"`;
2. the shared runtime helper, used for initial owner, reconnected owner, and
   observer, requires hosted mode, a non-null game identity, connected store
   status, equal runtime/store session identities, and at least one entity.

Both selected historical predicates were Promise-valued and had the installed-
Playwright one-shot defect already proven in earlier BUG-031 stages.

The historical stale smoke also used obsolete pre-character selectors that
current production no longer renders. A brand-new gateway directory contains
an identified principal but no persistent character. The frozen corrected
baseline therefore uses the already reviewed real premade-character UI
prerequisite and records the created card, sole game-setup roster member, and
actual human controller before the inherited hosted create path.

WP-017 changed exactly two existing Tester files during its already completed
checker-first-red and first correction stages:

- `app/scripts/check-node-sources.mjs`;
- `app/scripts/hosted-game-smoke.mjs`.

Both current file identities are the frozen baseline for this plan. The checker
remains byte-frozen. Only the hosted smoke may receive the bounded continuation
in Sections 4.6-4.7 after fresh Gate A approval, followed by fresh combined
static review before any execution. No production, package, Vite, Playwright,
SDK, generated, backend, service,
schema, product protocol, persistence, asset, dependency, public-contract, shared
framework, or second smoke edit exists.

### 0.1 Consumed execution identity and exact revision boundary

Every prior Section 6 execution identity is consumed and may not be retried.
The first reached only focused TypeScript and the frozen source checker before
its broad process preflight matched its own shell. The second reached the same
two green prerequisites and then stopped at the literal census: one stable
same-euid PID 603 entry produced the sole staged `executable` PermissionError,
with no match. Both launch-zero attempts created no cleanup obligation or
dynamic Stage 7 evidence.

The public blocker reviews classified those results `CHANGES_REQUIRED / NO
RETRY`. A bounded read-only study then positively identified PID 603 as
systemd's PAM session helper using its exact `(sd-pam)` status and sole argv,
user-manager init-scope cgroup, same-UID systemd parent, PID 1 ancestry, and the
upstream systemd owner. The same study established that the denial mechanism
is broader than that class and can affect another non-dumpable same-euid
process, including a packet browser. No generic unreadable-process,
PermissionError, PID, name, argv-only, ancestor-only, or same-euid exemption is
lawful.

The subsequent corrected identity ran the exact positive-class census green,
proved clean ports and UDS ownership, created one fresh attempt-local stack,
and ran the frozen hosted smoke exactly once. It reached the real fixture,
initial owner runtime/input, End Turn HTTP200, cursor 380 to 381, durable owner
session equality, and reconnect runtime admission. It then failed the inherited
completion-restoration assertion with objective completion events 134 before
reload and 0 immediately after reconnect, while subjective combat logs were 2
and presentation backlog was 0. Observer/rendered/terminal evidence remained
unreached. One flattened subjective-presentation consumer fault was retained.
Owned resource teardown completed, but the final broad joined-command matcher
reported only its own teardown shell. The attempt is non-green and NO RETRY;
it supplies only the reached readiness evidence and no Gate B acceptance.

A bounded source-and-receipt study selected two independent corrections. First,
the inherited Tester read occurs after subjective reconnect readiness but
before the separately launched objective-diagnostics history follower reports
connected and restores its cursor/history. Second, the final process proof
used an unfrozen broad shell matcher instead of the already reviewed token-aware
census. Sections 4.6-4.7 add only production-owned observation/settlement in the
hosted smoke. Section 6 invokes the same census twice, once before launch and
once after teardown. Neither correction changes production behavior.

The current protocol retains the exact positive-class exception in the
token-aware, non-self-matching census in Section 6.2.1. Every packet argv classifier
preempts the exception. It applies only when executable and cwd independently
produce PermissionError errno 13, the candidate starttime generation is pinned,
and identical complete systemd-PAM target/argv/cgroup/parent/PID1 snapshots
before and after the readlinks both match; the accepted snapshots and both
denials are retained in deterministic JSON. Ancestor exclusion must positively
reach PID 1, and a prior stable read failure can never be lost to a later
disappearance. All partial, unreadable, malformed, changed, single-denial,
different-errno, generic-unreadable, or packet-shaped records continue to
match or fail closed. Free-port proof, the separate UDS check, fresh-root rule,
launch sequence, time bounds, teardown, retained-root protection, frozen
source identities, deferred families, and strict claim do not change.

The immediately preceding plan-only Gate A identity was also closed
`CHANGES_REQUIRED` without census or execution. Its final packet-argv
reclassification preempted the systemd-PAM exception, but its later ordinary
readable match loop still used the pre-pin outer argv and PPid. A PID reused
between that outer read and the pinned initial snapshot could therefore leave a
complete stable packet final snapshot while ordinary matching consulted stale
`(sd-pam)` data. This revision binds the outer candidate observation to the
pinned initial generation and exact values by parsing both targets through the
same complete `candidate_status` shape, makes final snapshot argv and
target PPid authoritative for every candidate ordinary disposition, forbids
fallback when final evidence is incomplete, and verifies denied/readable
outcomes for all eight final-change and pre-pin-reuse packet controls through
one shared pure helper. No prior Gate A vote or execution permission carries.
The consumed plan2563/census1643 execution identity likewise carries no retry
or approval into this complete revision.

### 0.2 Candidate triage and explicit deferral

- `inventory-panel-smoke.mjs` remains deferred because its three waits are
  adjacent to direct assertions of the absent SELF/TARGET dossier surface,
  plus equipment behavior and repository screenshot writes. Selecting it
  would silently choose the forbidden WP-016 product-contract fork.
- `multi-character-live-smoke.mjs` remains deferred because its seven waits
  span roster, session, targeting, equipment, action, and handoff authorities
  and directly assert the same absent SELF/TARGET surface.
- restoration or retirement of SELF/TARGET remains human-scoped and is not a
  non-goal that this packet may reinterpret.
- the absent `action.unavailable`, `item.unavailable`, `object.unavailable`,
  `reaction.unavailable`, and `condition.unavailable` asset family remains a
  separate content-design backlog. It is neither aliased nor claimed here.

### 0.3 Human authorization and progression

The human authorized automatic progression through bounded owner-correct
seams. This packet historically changed two Tester files, uses the repository's existing
gateway deployment topology, and introduces no product behavior choice,
public contract, schema, persistence policy, dependency, framework, service,
or architecture expansion.

### 0.4 Strict claim

Successful Gate B may establish only:

> BUG-031 Stage 7: the maintained hosted-game smoke is statically guarded
> against its two Promise-valued readiness call shapes and explicitly observes
> resolved hosted runtime readiness for initial owner, reconnected owner, and
> observer, plus resolved owner `my_turn_input` and the distinct production
> objective-diagnostics history-settlement boundary, on one fresh lawful
> hosted premade-character fixture before its inherited End Turn, reconnect,
> transcript, and observer receipt; structured presentation diagnostics remain
> observation-only and every presentation fault remains fatal.

It does not claim character creation, hosted-game correctness, reconnection,
observation, End Turn, transcript restoration, worker correctness, gateway
correctness, presentation, replication, the remaining ten occurrences, the
SELF/TARGET contract, the unavailable-sentinel family, or general product
correctness.

## 1. Frozen authority identity

Every identity is exact. Any mismatch fails intake closed. No refresh,
substitution, regeneration, or baseline carry is permitted.

### 1.1 Predecessor and deferred-boundary evidence

| Authority | Lines | SHA-256 |
|---|---:|---|
| `agent_working_folder_NOT_HUMAN_GUIDANCE/plans/GAMEPLAY_REGRESSION_WORK_PACKET_016_BUG_031_HUD_ACTION_GEOMETRY_READINESS_RESOLVED_WAIT_2026-08-11.md` | 535 | `0439e4507a4df78b2a5ef3afb8f2a5edce2386f36a55996a495861c1316cbb1c` |
| `/tmp/neurodragon-wp016-green-9x6zTg/hud-rpg-smoke.stdout` | 14 | `4d4128f1deebaf41eb7a1c07d3f08ddaaba9440869803411723c05e9fb967968` |
| `/tmp/neurodragon-wp016-green-9x6zTg/hud-rpg-smoke.stderr` | 12 | `cd606f0d8ec450306f683281babd3a7c0a01e3d774fb69cce71a7b9b9d2a8b7a` |
| `/tmp/neurodragon-wp017-green-9dlZw9/hosted-game-smoke.stdout` | 63 | `6eb998c87e872e80f802cefa76f5e65af60f61984949d55179e6b2e74f64c799` |
| `/tmp/neurodragon-wp017-green-9dlZw9/hosted-game-smoke.stderr` | 9 | `80d1610962aa6d5431ebfcba56a5c3fdb4decd6d36f83e9a1cda275eea7b3fec` |

The WP-016 retained root, the consumed WP-017 root
`/tmp/neurodragon-wp017-green-9dlZw9`, and every earlier retained root are
immutable evidence, never packet state. No later execution may read, mutate,
clean, or reuse them.

### 1.2 Frozen accepted Tester surface

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/check-node-sources.mjs` | 126 | `e9ab23a4b99927b673c1fd08dcb6c63d30aa40c5cee9616e3b5c88e54792fda8` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/hosted-game-smoke.mjs` | 483 | `293f3362d69297ef3eb6079d3db1eaf84d845c58890ce50b929e7de80dbd3e65` |

The six predecessor checker targets remain frozen:

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/scripts/turn-burst-smoke.mjs` | 336 | `3e71c47d90d983df2a88d5483f288454bf476e4b81cb1f3108f35c1660495420` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/real-character-game-creation-live-smoke.mjs` | 528 | `01650889d45e6d77db0f96ee22bbfd84f99125592db88ca2be1dd68f81fdcd5a` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/replication-smoke.mjs` | 406 | `078a4cccc8f6a72d71baa9f8b22dbd8fc20e49144a13a524e3c5e080059f5ca1` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-subjective-actions-smoke.mjs` | 780 | `c04a200674d41e4b2711cfabc4a9870f93421a59d84380aac37fbaf72bb69fa4` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/live-shove-presentation-smoke.mjs` | 752 | `bc538d0aace98039b2e912f7d1f99f15379f62effc95eebcb8def5d64900ceae` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/hud-rpg-smoke.mjs` | 436 | `78e2cda4692d81824890826150088ede90633b0f8059bd11a232846eb9592f91` |

WP-017 does not accept WP-016's downstream HUD product assertions. The frozen
HUD identity appears only because its target-local checker rule is current and
must remain unchanged.

### 1.3 Package, helper, and Playwright authorities

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/package.json` | 165 | `36515d20ea94ebc0c49a47b79bd455fee0eddceea2eb5e52713163eff159d9e3` |
| `/home/tommaso/Dev/NeuroClient/app/vite.config.ts` | 235 | `7d70b9fae8cf5d4a8d38762865ac8f36adba1247721212fcb5b3d7455f247153` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/player-identity.mjs` | 70 | `2196cf7af3841a88dc0396e99c38d041bf3ce4c7d07fc987c209a0d88843772c` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/package.json` | 48 | `d4b8727c495ff2632084e922ee1c7f19a608ed23d86e8f3b0ba0ff317eea58ec` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/frames.js` | 1500 | `a0a5c3655b86edeb1e6acb8133d40769dda53c246340271251598dac5ff48594` |
| `/home/tommaso/Dev/NeuroClient/app/node_modules/playwright-core/lib/server/chromium/crExecutionContext.js` | 146 | `4b4da27c16c2ec7094dcc3cc78313eb9ac8f15a9ed3b7589118a883d6d339b7f` |

Installed Playwright is 1.59.1. No dependency action exists.

### 1.4 Frozen hosted client and fixture owners

| File | Lines | SHA-256 |
|---|---:|---|
| `/home/tommaso/Dev/NeuroClient/app/src/engine/store.ts` | 431 | `b0c428f266cf3c23608143e3ee73fc048f82bfb0afb5ffee3e317b1aff859537` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/runtimeConnection.ts` | 143 | `e5168a7520163f9cf7a29c54e3d359bddf9d952366a3a51f8a15c0c568aa98e4` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/objectiveDiagnostics.ts` | 389 | `06bac0fe2b9f4943f3055298a65f8a5c890d56279f7f9f568f3cc96a32da2cc8` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/eventStream.ts` | 974 | `912ef41889c5a1a753d8969037550e3fabc6ecbd126e1d417e4cced6290fd522` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/stateSync.ts` | 618 | `d015d1c29e490c809faab1dd4f425f20dfbfc34433c36cff34dff731b8e5877a` |
| `/home/tommaso/Dev/NeuroClient/app/src/engine/control.ts` | 304 | `f321847ba5df055269eb483006f289642a30c8ee6f3b2da46ae898630157f483` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/bootstrap.ts` | 756 | `2c6fba3930631a6cb86cdff720aad3701379c7b53557c4b5090263fcc61b7fd9` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/actions.ts` | 111 | `857d866984ac43699d019aa4490dfa2cd0ff1fa68d82b961cb2b1a0112503462` |
| `/home/tommaso/Dev/NeuroClient/app/src/api/gameDirectory.ts` | 961 | `7c302315a8da021fb7652baf09d2d5c9575cd82893fe15729a80a85968fe6560` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameCreationReadiness.ts` | 38 | `1dd39360063376c67a8a028742e11fdab769c3888bd6b6599f5999498ea7c1ac` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameBrowser.ts` | 1097 | `6bf4ad5e856cd38ea671218b1e9d928d51e04bcc1c054329a587fef7b9cd896c` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterCreator.ts` | 2772 | `bb6365ca79164a13467699d2c3142134b61f71a3560b0ef89f5f31cd3f15e20b` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/characterSheet.ts` | 1266 | `9bdf076f1b1383e297143c044ff116b2f792c1ba1af994d29e731ebc6774ba0b` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameSetup.ts` | 2228 | `eba13f093bd5a8c6006e73d7b1918a1a1a9a7c64953adc20474d2e895baa17e1` |
| `/home/tommaso/Dev/NeuroClient/app/src/ui/gameSetupCharacterRoster.ts` | 347 | `6b666a0729d489088266b915b0f278e108e9f881bc5d6dc7368be6dc3cb57a20` |
| `/home/tommaso/Dev/NeuroClient/app/src/render/presentationDiagnostics.ts` | 1264 | `4271e3b7711b8964212f9d0994877768c386c1ac359b476f5c3b94d3d8233f69` |
| `/home/tommaso/Dev/NeuroClient/app/scripts/render-lifecycle-isolation-smoke.mjs` | 258 | `3febfc45e29f9a1d524922fad52a8e3b05e5e2dbc1f3f44c835d2fa0de345615` |

### 1.5 Frozen gateway and worker owners

| File | Lines | SHA-256 |
|---|---:|---|
| `server/MULTI_GAME_GATEWAY.md` | 117 | `b4dbb526d197b3f315cf0e95caa85b53a037931107c9721214442278494501e6` |
| `server/game_gateway.py` | 2732 | `6f950eef1cf0fd94c23408f48462b9af5611b5f3d69641c2a1dc8ca087ca87af` |
| `server/hosted_worker.py` | 599 | `f9ddd961c358d556718367690ad893a0fbd7d0f82bc168ef7f0734fae39173fc` |
| `server/game_creation_preview.py` | 360 | `8f432d272f774b6e954e9e37b0b214a89ad08d22b243086cca1e7bd05db54957` |
| `server/game_creation_preview_worker.py` | 153 | `faf805e587bc1bd31cd87e79b092f55aa93fa90fe66b065c2f2a4127c618073d` |
| `server/worker_proxy.py` | 314 | `6cfe0931c0124e12445a5e9a0f05e5b497c6851f552f8a1234a39518f3087b2d` |
| `server/game_directory/repository.py` | 5679 | `2d558673d9395aa1827a886511392991702be3cc5eee2284a190e7b9705ce39c` |
| `server/game_directory/contracts.py` | 1133 | `c1c5dc0667dde1a79789a88371aa87094cea2217cf6833747adef0e478deb29e` |
| `server/event_server.py` | 6978 | `eb1f6e891bc4cb149c8f054bb8ae36e4df7f2a7a7d47e6cc91af2a3e7394cdc5` |
| `sdk/typescript/src/objectiveDiagnostics.ts` | 506 | `be9a376ddf4c02da4fa4a434992d1a7983de21670c88fa96bdf4a578986eb276` |

`server.sh` and `server.event_server` as a standalone outer server are not
launch authorities for this packet. The gateway directly owns its UDS worker
processes and imports `server.event_server:app` inside them.

### 1.6 Frozen PID 603 study receipt and policy authorities

The study is historical evidence only; intake and execution must not reinspect
PID 603 or substitute another PID. At Unix-ns observation
`1786423917219274993`, the exact captured evidence was:

| Receipt | Frozen value |
|---|---|
| PID 603 status | 1,446 bytes / `8c0e65d6796b1784a62ee562a054948038be12ca797ffac2d34cb3f9eae47b8d`; Name `(sd-pam)`, sleeping, PPid 602, all UID/GID fields 1000, zero effective/permitted/ambient capabilities, TracerPid/CoreDumping/NoNewPrivs/Seccomp/filters zero |
| PID 603 cmdline | 9 bytes / `971490059d839d27af3ded30a476216b92689d837b0236a700723fb13640e370`; exact sole NUL token `(sd-pam)` |
| PID 603 cgroup | 60 bytes / `831bb8dbdd305bb66d122f9e8660109c721a76cf66533f935ca9fe7b50bf93fd`; exact user-1000 user-manager init scope |
| PID 603 cwd/exe | each independently returned PermissionError errno 13; pid/user/mnt namespace symlinks did likewise |
| ancestry | PID 603 `(sd-pam)` uid1000 -> PID 602 `systemd` uid1000 -> PID 1 `systemd` uid0; PID 602 status `90f8f3d5e1fc34dbde9817cea7412a8704c874d332d544907cc7e247dd0b428d`; PID 1 status `baf432a869bdb3ee1e884e6ba3f507836d23c5553bd1a43dfdf29de998610d35` |

`/proc` had no `hidepid`, caller/target proc mountinfo lines were identical,
`fs.suid_dumpable=0`, and Yama `ptrace_scope=1`. Local
`proc_pid_exe(5)`/`proc_pid_cwd(5)` bind those dereferences to
`PTRACE_MODE_READ_FSCREDS`; the local authority identities are:

| Authority | SHA-256 |
|---|---|
| `/usr/share/man/man5/proc_pid_exe.5.gz` | `3172895ee9b85b2294abd54ba96f3f414f25b31556a092e13372acbdbd00ea0a` |
| `/usr/share/man/man5/proc_pid_cwd.5.gz` | `a59f12fdf28a6277e4296c69f27fc3d436a899024628b1e5cf0680b1f6ee3dd1` |
| `/usr/share/man/man2/ptrace.2.gz` | `524da5381207bac15737104b53b46abf6edf1b0c420482f3ef5c1519fe1c1e29` |
| `/usr/share/man/man2/prctl.2.gz` | `c46d434bf9ab769eaf64a91b3015c1d93ba578b03277b740477f3aa9cf476d7f` |
| `/usr/lib/systemd/systemd` | `b472aadf808bef87c0eb203056a77cb64bd268b71b756306013a53de68a94173` |

Local systemd is `255.4-1ubuntu8.17` with PAM. The corresponding official
systemd owner creates a child named `(sd-pam)`, drops it to the service UID/GID,
and waits there to close the PAM session after parent death:
`https://github.com/systemd/systemd/blob/v255/src/core/exec-invoke.c`.
The denial explanation is source-backed inference; the target's dumpable bit
was not directly read. The process identity is positive, but the access policy
is not class-specific, which is why the exception below requires both the full
identity tuple and the two exact denials.

## 2. Causal finding

### 2.1 Installed Playwright behavior

Frozen Playwright invokes a `waitForFunction` predicate and branches on its
immediate return before later result adoption. An async predicate immediately
returns a truthy Promise object. Eventual false can therefore fulfill and
return the injected loop without another poll.

Ordinary Chromium `page.evaluate` uses `awaitPromise: true`, so explicit
Node-side polling observes the resolved serializable Boolean.

### 2.2 Selected stale waits

The historical stale hosted smoke had four `waitForFunction` calls, including
exactly two Promise-valued call shapes:

- one owner-only input wait for exact `my_turn_input`;
- one shared hosted runtime wait invoked for initial owner, reconnect owner,
  and observer.

The frozen corrected baseline has zero Promise-valued calls. The other two
calls are synchronous DOM/event-cursor predicates and remain unchanged.

The runtime predicate directly imports production store/runtime owners and
requires:

- `connection.mode === "hosted"`;
- non-null `connection.gameId`;
- store `connectionStatus === "connected"`;
- store `session_id === connection.sessionId`;
- `entitiesById.size > 0`.

The owner input predicate directly imports the production store and requires
`clientState === "my_turn_input"`.

Later End Turn ownership, cursor progression, reconnect transcript checks, and
observer checks can fail after premature admission, but none proves that each
named boundary repolled until its resolved Boolean became true.

### 2.3 Fresh hosted fixture and service premises

The current hosted smoke's `character-name` and
`create-character-barbarian` selectors have no production creator. On a fresh
gateway database, `ensurePlayerIdentity` creates the principal/identity, not a
persistent character. Production then shows one create-match requirement and
disables New Match.

The lawful prerequisite is the real premade creator, exact character POST,
selected character card, real sheet, sole game-setup roster member, and actual
human controller. No direct API-created character, DTO seed, route
interception, or retained profile exists.

The repository's gateway lifespan creates the directory repository, worker
manager, preview worker, and artifact store from environment-selected paths.
It prewarms the configured worker pool and, on shutdown, closes the gateway,
stops all hosted workers, closes the owned repository, and closes the preview
worker. Hosted workers use dedicated process groups and Unix-domain sockets.

### 2.4 Reconnect objective-history settlement

The consumed smoke proved the corrected initial owner runtime/input and
reconnect runtime boundaries, then observed completion events 134 before
reload and 0 immediately after reconnect. This is a Tester sequencing defect,
not receipt evidence of missing gateway history:

- `readTranscriptState` reads completion count from `state.events`;
- `state.events`, `objectiveEventCursor`, and
  `objectiveDiagnosticsStatus` are owned by the independently authorized
  objective-diagnostics follower, not the canonical subjective journal;
- reconnect/bootstrap calls `resetObjectiveDiagnosticsRuntime`, clearing
  objective events, cursors, logs, and status;
- `startObjectiveDiagnostics` launches `followObjectiveDiagnostics` with
  fire-and-forget `void` ownership;
- subjective runtime connection/session/entity readiness can therefore settle
  before the objective follower bootstraps, fetches history, replaces events,
  advances its cursor, and sets `objectiveDiagnosticsStatus` to `connected`;
- the gateway endpoint already owns an exact contiguous all-phase objective
  event window and cold backfill from cursor zero through the bootstrap cursor;
- subjective `combatLogEntries` has a separate owner, so combat logs 2 with
  objective completion events 0 is coherent at the premature read.

`render-lifecycle-isolation-smoke.mjs` independently freezes this objective/
subjective separation. The lawful test boundary is production status and
cursor settlement; completion restoration remains a later independent
assertion. If status/cursor settles but completion restoration fails, ownership
returns to the production objective history/projection path.

### 2.5 Presentation fault and final-proof causality

The consumed browser receipt retained one exact flattened console fault at
`2026-08-11T06:03:48.582Z`, kind `consumer_failure`, message `subjective
presentation consumer failed`, but `collectBrowserErrors` reduced the
structured error to `error: Object`. Production
`getPresentationDiagnosticsSnapshot` retains the fault ID/time/kind/message,
serialized error, frame/transaction/intent/root cue, runtime evidence, and
recent trace. Objective diagnostics is a separate owner, so this fault does
not own the deterministic objective reset to zero. It remains a real,
independently fatal runtime fault whose stage/lineage/chronology must be
observed without filtering or admission authority.

Resource-specific teardown proved the recorded trees, ports, and UDS owners
absent. The final broad matcher nevertheless reported its own shell because
that shell carried the searched words. This is a protocol self-match, not a
leak. The smallest correction is a second labeled invocation of the identical
stdin-only token-aware census after recorded teardown, while all named PID,
port, and UDS proofs remain mandatory.

## 3. Checker-first natural red

### 3.1 Authorized checker block

The completed checker-first stage edited only
`app/scripts/check-node-sources.mjs`. Immediately after the current HUD block,
it added one target-local path/read/regex rule for
`scripts/hosted-game-smoke.mjs` using:

`/\.waitForFunction\s*\(\s*async(?:\s+function\b|\s*\()/u`

and exact diagnostic:

`scripts/hosted-game-smoke.mjs: Promise-valued waitForFunction predicate is forbidden; use explicit resolved page polling.`

Preserve all six current target blocks, recursive sorted `.mjs` traversal,
Node syntax checks, Vite diagnostics, failure aggregation, and success summary.
The rule reads only hosted game and does not scan the remaining ten
occurrences.

### 3.2 Historical checker static sub-gate

The changed checker completed isolated R1-R4 static approval and is now frozen
at the Section 1.2 identity. This revision releases no checker edit.

### 3.3 Consumed exact first red

Tester ran once from NeuroClient root:

`npm --prefix app run node-sources:check`

It exited nonzero with the sole exact Section 3.1 diagnostic after the
node-config prerequisite passed. No gateway, worker, Vite server, browser, or
smoke started. That receipt released only the already completed first
hosted-smoke correction and carries no execution permission now.

### 3.4 Historical correction release

The exact red received fresh R1-R4 causal approval before the first
hosted-smoke edit. The checker remains frozen. The current continuation is
released only by this wholly new plan's Gate A and later combined-static gate.

## 4. Frozen hosted-smoke correction and bounded continuation

Sections 4.1-4.5 describe the accepted current hosted-smoke baseline and may
not be changed by this revision. Fresh Gate A may release Tester to add only
Sections 4.6-4.7 in the same file. Section 4.8 freezes everything else.

### 4.1 Real fresh-character prerequisite

After game-browser visibility and the existing `ensurePlayerIdentity` call,
replace only the obsolete character-selector prelude with this production UI
flow before the existing New Match/game-setup path:

1. require exactly one visible create requirement;
2. record/require actual disabled New Match;
3. observe only POST plus exact parsed pathname
   `/api/directory/characters`;
4. use the real premade creator with fixed name
   `Hosted Readiness Fixture`, arm the response wait before one create click,
   require success and creator detachment;
5. require exactly one selected card, exact rendered strong name, and non-null
   actual `data-select-character` ID;
6. require zero remaining requirements and enabled New Match;
7. require the real sheet visible, close it through the production control,
   require detachment, and require request count one;
8. click that same production New Match control;
9. require exactly one selected roster member and exact created-card/roster ID
   equality;
10. locate that exact member's human controller, click it only if it is not
    already active, then record its actual active state and require `human`
    before the inherited Start Match request.

No character response body is read. No character DTO, API seed, request
interception, mock, retained database, local-storage fabrication, or direct
directory/store write exists. The existing hosted game-create response body
remains part of the inherited gateway handshake and is not affected by this
prohibition.

### 4.2 File-local resolved-poll helper

Add one file-local helper:

`waitForResolvedPageCondition(targetPage, evaluateCondition, evaluateArgument, timeoutMs, label, pollIntervalMs = 50)`

It must use one Node `performance.now()` start and absolute deadline; reject
before an expired evaluation; count one attempt per actual evaluation; race
one `targetPage.evaluate(evaluateCondition, evaluateArgument)` against one
timer for the current remaining budget; clear the timer in `finally`; reject
truth settling at/after deadline; bound false delay by
`min(50ms, pollIntervalMs, remaining)`; begin no post-expiry evaluation;
retain O(1) state; and use exact timeout:

`<label> did not resolve within <timeoutMs>ms`.

### 4.3 Runtime helper correction and independent receipts

Preserve the first synchronous DOM/canvas `waitForFunction` inside
`waitForRuntime` byte-for-byte. Replace only its Promise-valued second wait
with the helper using:

- `undefined` as the serializable page argument;
- timeout `60_000`;
- a caller-provided label distinguishing `owner initial hosted runtime`,
  `owner reconnect hosted runtime`, and `observer hosted runtime`;
- the exact current direct production imports and five-term predicate.

Immediately after helper success, a separate `page.evaluate` must record
actual:

- `connectionMode`;
- `connectionGameId`;
- `connectionSessionId`;
- `connectionStatus`;
- `stateSessionId`;
- `entityCount`.

Require exactly the same five-term predicate against this independent
snapshot. The existing `gameId` argument remains in the preceding synchronous
canvas predicate and the inherited gateway handshakes continue to prove exact
game ownership. Do not strengthen, weaken, or reinterpret the selected
runtime predicate.

Return the helper attempts/elapsed plus snapshot from `waitForRuntime` and
record three actual labeled receipts in the final `observed` object: initial
owner, reconnect owner, and observer.

### 4.4 Owner input correction and independent receipt

Replace only the owner Promise-valued `my_turn_input` wait with the same helper
using:

- `undefined` as the serializable page argument;
- timeout `60_000`;
- label `hosted owner input readiness`;
- the exact existing production store import and predicate.

Immediately afterward, separately read actual `clientState` through
`page.evaluate`, require exact `my_turn_input`, and record helper
attempts/elapsed plus the independent state before the inherited event-cursor
read and End Turn path.

### 4.5 Actual output evidence

Extend only the existing single final JSON with actual values for:

- `initialCreateRequirementCount`;
- `initialNewMatchDisabled`;
- `characterCreateRequestCount`;
- `characterCreateStatus`;
- `createdCharacterCardCount`;
- `characterFixtureName`;
- `createdCharacterId`;
- `remainingCreateRequirementCount`;
- `finalNewMatchEnabled`;
- `gameSetupRosterCharacterId`;
- `gameSetupRosterController`;
- `runtimeReadiness.ownerInitial`;
- `runtimeReadiness.ownerReconnect`;
- `runtimeReadiness.observer`;
- `ownerInputReadiness`;
- `objectiveHistory.beforeReload`;
- `objectiveHistory.afterReconnect`;
- `presentationDiagnostics.beforeReload`;
- `presentationDiagnostics.afterObjectiveSettlement`.

The fixed fixture name is an input identity and must be independently proven
by rendered DOM text. Every status, count, ID, controller, attempt, elapsed,
connection, session, entity, and input-state value is observed.

### 4.6 Objective-diagnostics history-settlement receipt

Extend only `readTranscriptState` to return the actual production
`objectiveDiagnosticsStatus` and `objectiveEventCursor` beside its five
existing fields. Do not rename, remove, or reinterpret any existing field.

At the existing post-End-Turn checkpoint, after cursor advancement and the
current `beforeReconnect = await readTranscriptState(owner)` call but before
reload:

1. require `beforeReconnect.objectiveDiagnosticsStatus === "connected"`;
2. require `beforeReconnect.objectiveEventCursor > 0`;
3. retain the complete transcript snapshot in
   `observed.objectiveHistory.beforeReload`.

After the existing durable-session equality and frozen reconnect-runtime
helper/snapshot, call `waitForResolvedPageCondition` once with:

- the owner page;
- the pre-reload objective cursor as the only serializable argument;
- timeout `60_000`;
- label `owner reconnect objective diagnostics history settlement`;
- a read-only predicate that imports only `/src/engine/store.ts` and returns
  exactly `state.objectiveDiagnosticsStatus === "connected" &&
  state.objectiveEventCursor >= requiredObjectiveEventCursor`.

Immediately after helper success, call `readTranscriptState(owner)` once and
independently require the same exact status/cursor terms. Store the helper's
actual attempts/elapsed plus the complete independent transcript snapshot in
`observed.objectiveHistory.afterReconnect` with exact shape
`{ wait: <attempts/elapsed receipt>, snapshot: <complete transcript snapshot> }`.
Use that same independent snapshot
for the inherited completion-count, combat-log, backlog, and cursor assertions;
the later rendered DOM assertions remain unchanged. Do not perform a second
transcript read between settlement and the completion assertion.

Completion count is never part of the readiness predicate. No event, cursor,
status, history, session, or store value may be authored. A timeout fails at
the objective history owner. Connected/cursor-restored state with missing
completion events fails the unchanged inherited completion assertion and
returns ownership to the production objective history/projection path.

### 4.7 Structured presentation-diagnostics evidence

Add one file-local read-only `readPresentationDiagnosticsReceipt(page)` that
uses ordinary `page.evaluate` to import the production
`getPresentationDiagnosticsSnapshot` owner from
`/src/render/presentationDiagnostics.ts` and returns one serializable object
with exactly:

- `schema`;
- `faultCount`;
- `latestFault`, null or the latest published fault's exact `id`,
  `recordedAt`, `kind`, `message`, `error`, `diagnosticCode`, `rootCue`,
  `reconciliation`, `frame`, `transaction`, `intent`, `runtime`, and its
  published `recentTrace` limited to the last 60 entries;
- `recentTrace`, the top-level published trace limited to the last 60 entries;
- `persistence` with exact `storage_key`, `invalid_persisted_fault_count`,
  `load_error`, and `write_error`.

Read and retain this receipt at exactly two checkpoints:

1. `observed.presentationDiagnostics.beforeReload` immediately after the
   Section 4.6 pre-reload transcript assertions and before `owner.reload`;
2. `observed.presentationDiagnostics.afterObjectiveSettlement` immediately
   after the Section 4.6 helper plus independent transcript snapshot and before
   the inherited completion-restoration assertion.

The helper is observation-only and bounded by the production snapshot's
existing fault/trace limits. It is not a readiness predicate or second
admission owner. Do not clear, acknowledge, filter, suppress, reconcile, or
mutate diagnostics; do not add console-handle adoption. Preserve
`collectBrowserErrors` and the existing terminal zero-browser-error assertion
unchanged and fatal. Because the smoke emits `observed` after browser `finally`
even on failure, both completed checkpoint receipts remain in the one JSON
receipt when a later inherited assertion fails.

### 4.8 Frozen inherited behavior

Outside the exact additions in Sections 4.6-4.7 preserve:

- owner/observer browser contexts and pageerror/console collection;
- hosted game-create request/response and exact game/session/controlled-entity
  ownership assertions;
- the first synchronous runtime DOM/canvas wait;
- event cursor before/after End Turn and the synchronous cursor wait;
- real production `endTurn` ownership and runtime action endpoint;
- reload, exact reconnect request, durable runtime-session equality, and
  transcript/cursor/backlog assertions;
- rendered Events and Combat Log tab/row assertions;
- observer identity, observe request, access mode, zero controlled entities,
  and exact observed-game identity;
- existing final JSON position, failure aggregation, and both browser-context
  and browser close ownership.

No action shortcut, runtime/store mutation, timeout extension, extra retry,
fault filter, console suppression, diagnostic clear, console-argument capture,
gateway response
fabrication, screenshot, or third file is authorized.

## 5. Combined static review

The frozen checker and current hosted smoke completed isolated combined static
review before the consumed attempt. They are the exact baseline for fresh Plan
Gate A. After Gate A, Tester may edit only the hosted smoke for Sections
4.6-4.7; the checker and every other file remain byte-frozen. The revised smoke
requires a wholly fresh combined R1-R4 static review plus Coordinator
verification before Section 6. That review must prove:

1. scoped status contains only the historical checker plus the newly revised
   hosted smoke, with the checker byte-identical to Section 1.2;
2. the new hosted diff is confined to observed slots, the two added transcript
   fields, objective settlement, two structured presentation reads, and one
   read-only helper;
3. no Promise-valued wait remains in hosted game;
4. both synchronous waits remain unchanged;
5. the fresh-character prerequisite uses real production UI/API ownership;
6. created-card and sole game-setup roster IDs agree and controller is actual
   human;
7. the helper has one absolute deadline and resolved page values;
8. all three runtime observations use the exact five-term predicate and
   independent snapshots;
9. owner input readiness uses exact state plus an independent snapshot;
10. pre-reload objective status/cursor are actual positive production values;
11. the post-reconnect helper uses only connected status plus cursor recovery,
    then independently re-reads those same values before the unchanged count
    assertion;
12. completion restoration remains outside readiness and no history/store
    value is authored;
13. the presentation helper returns only the exact bounded production fields
    at the two frozen checkpoints and is never an admission or fault filter;
14. inherited create/End Turn/reconnect/completion/combat-log/backlog/rendered/
    observer/error/JSON/finally behavior is unchanged outside authorized
    placement;
15. no gateway, production, package, service, artifact, or third-file edit
    exists;
16. the deferred SELF/TARGET fork, ten waits, and sentinel backlog remain open.

No edit is authorized before this complete plan reaches fresh public Gate A
4/4 plus Coordinator verification. No execution is authorized before the
subsequent combined-static review reaches fresh public 4/4 plus Coordinator
verification.

## 6. Governed same-policy green

### 6.1 Frozen prerequisites

From NeuroClient root, exactly once each and stopping on nonzero:

1. `./app/node_modules/.bin/tsc --noEmit -p ./app/tsconfig.json`;
2. `npm --prefix app run node-sources:check`.

No aggregate check/build or alternate command is authorized.

### 6.2 Fresh owned gateway stack

Only after both prerequisites exit zero:

1. run the exact Section 6.2.1 process census once with label `preflight`,
   retain its compact stdout byte count/SHA-256, then prove ports 8000/5173
   free and run the separate existing UDS-owner absence check; stop on any
   nonzero or reported owner;
2. create one brand-new disposable `/tmp` runtime root with exact owned
   database, hosted-worker, and artifact child paths;
3. from dnd_engine root start exactly one owned direct gateway under the
   repository virtual environment:

   `DND_DIRECTORY_CAPABILITY_PEPPER=<attempt-local-secret> DND_DIRECTORY_DATABASE=<fresh-root>/game-directory.sqlite3 DND_HOSTED_RUNTIME_ROOT=<fresh-root>/hosted-games DND_GAME_ARTIFACT_ROOT=<fresh-root>/game-artifacts DND_HOSTED_WARM_WORKERS=1 ./.venv/bin/python -m uvicorn server.game_gateway:app --host 127.0.0.1 --port 8000 --workers 1`

4. require direct `/server/capabilities` HTTP200 with exact
   `server_mode=gateway`, `game_directory_enabled=true`,
   `persistent_game_history=true`, and `isolated_game_workers=true` within
   90 seconds;
5. start one owned registered Vite on exact port 5173 and require exact-root
   HTTP200 in a bounded window;
6. from NeuroClient root run exactly once as one recorded process session
   under an exact 300-second outer wall clock:

   `NEUROCLIENT_URL=http://127.0.0.1:5173 npm --prefix app run hosted-game:smoke`

The direct Uvicorn launch has no `--force` or port-killing owner. A
preflight/start race freezes on ordinary bind failure and may never signal an
unrelated listener.

#### 6.2.1 Exact non-self-matching process census

From dnd_engine root invoke exactly `./.venv/bin/python -` with the census
program below supplied verbatim on standard input. The exact same program bytes
are invoked exactly twice in the complete attempt: first as labeled
`preflight`, then only after teardown as labeled `post-teardown` under Section
6.4. No temporary file, shell pipeline, `ps`, `pgrep`, `grep`,
joined-command regex, kill, or cleanup is allowed. The Python inspector's argv
is therefore only the repository Python path and `-`; the program text exists
only in standard input.

The inspector must implement this exact algorithm:

1. record `os.getpid()` and follow `PPid` in `/proc/<pid>/status` to PID 1,
   forming one exclusion set containing only the inspector and its complete
   wrapper/ancestor chain; any unavailable captured ancestor records a
   deterministic `ancestor-status` error, never an uncaught traceback, and an
   incomplete chain can never produce exit 0; traversal must positively reach
   PID 1, while premature PPid 0 and any cycle are staged errors;
2. enumerate the numeric `/proc` directories once in ascending PID order;
3. skip only that exclusion set, vanished entries, and processes whose
   effective UID from `/proc/<pid>/status` differs from `os.geteuid()`;
4. for every remaining same-UID process, read `/proc/<pid>/cmdline` as bytes,
   split only on NUL, and decode each argv token with `surrogateescape`; never
   search a joined command string; run every classifier that can be decided
   from argv alone before considering the positive non-packet exception;
5. only an entry whose status Name or exact raw/decoded sole argv is
   `(sd-pam)` is a candidate for that exception; before tuple collection pin
   the outer candidate observation with `/proc/<pid>/stat` field 22 starttime
   and parse its cached status through the same complete `candidate_status`
   owner used by the pinned snapshots,
   then take the complete initial starttime/status/raw-and-decoded-argv/cgroup/
   immediate-parent/PID1 snapshot; the outer starttime, complete parsed target
   status, raw argv, and decoded argv must equal the initial pinned snapshot
   exactly before the exception can proceed; each complete snapshot also
   re-reads starttime after its tuple to prove the candidate generation did not
   change within that snapshot; missing, unreadable, malformed, changing, or
   incomplete evidence cannot qualify and is deterministic nonzero;
6. independently read `/proc/<pid>/exe` and `/proc/<pid>/cwd`; after any
   status, argv, cgroup, related-status, executable, or cwd unavailability,
   recheck the same captured `/proc/<pid>` directory; continue only when the
   enumerated entry's disappearance is confirmed, except that a required
   related parent or PID 1 disappearance is itself a staged error; an empty raw
   cmdline or decoded argv is `argv-empty` and follows the same rule; if cwd
   confirms disappearance after executable already established a stable
   failure, retain that executable failure before continuing;
7. after both readlink outcomes and before exclusion, take the same complete
   starttime-before/target/argv/cgroup/parent/PID1/starttime-after snapshot
   again; require both within-snapshot generations stable, identical initial
   and final starttime plus complete tuple, and empty initial and final argv
   packet-class results; any disappearance, PID reuse, read/parse error,
   missing field, changed tuple/relation, or final packet argv is deterministic
   nonzero rather than exclusion; for every candidate path with a complete
   final snapshot, that snapshot's argv and target PPid are the sole
   authoritative ordinary match/report values, never the pre-pin outer values;
   a missing final snapshot retains its staged error and forbids stale fallback;
8. replace the executable and cwd errors by one deterministic excluded
   classification `systemd-pam-session-helper` only when both independent
   reads produced PermissionError errno 13, both complete snapshots are
   identical, neither argv snapshot names a packet class, and all of the
   following are exact:
   - status Name `(sd-pam)`, raw argv `b"(sd-pam)\0"`, and decoded argv
     `["(sd-pam)"]` as the sole token;
   - all four UID fields equal the census euid, all four GID fields equal the
     census egid, `CapEff`, `CapPrm`, and `CapAmb` are zero, and `TracerPid`,
     `CoreDumping`, `NoNewPrivs`, `Seccomp`, and `Seccomp_filters` are zero;
   - cgroup is exactly
     `0::/user.slice/user-<euid>.slice/user@<euid>.service/init.scope`;
   - the immediate PPid has Name `systemd`, all four UIDs equal the same euid,
     and PPid 1; PID 1 has Name `systemd`, all four UIDs zero, and PPid 0;
   every other dual denial, a single denial, a different errno/stage, or a
   packet argv match retains the ordinary match/error disposition through one
   pure helper shared by enumeration and controls; that helper uses final
   snapshot argv/PPid for every candidate path, outer argv/PPid only for a
   non-candidate, preserves every read failure, and errors rather than falling
   back when candidate final evidence is unavailable;
9. classify packet processes only by the following exact argv/path shapes:
   - `hosted-smoke`: any argv token has basename
     `hosted-game-smoke.mjs`, or an npm/npx executable/`npm-cli.js` process has
     the exact argv token `hosted-game:smoke`;
   - `gateway`: argv contains the consecutive tokens `-m`, `uvicorn` and the
     exact token `server.game_gateway:app`;
   - `hosted-worker`: argv contains the consecutive tokens `-m`, `uvicorn`,
     the exact token `server.event_server:app`, and the exact token `--uds`;
   - `event-server`: argv contains consecutive tokens `-m`,
     `server.event_server`, or contains consecutive tokens `-m`, `uvicorn`
     plus the exact token `server.event_server:app`;
   - `preview-worker`: argv contains the consecutive tokens `-m`,
     `server.game_creation_preview_worker` and the exact token `--serve`;
   - `vite`: an argv token normalizes to a path ending
     `/node_modules/vite/bin/vite.js`; or equals `node_modules/.bin/vite` or
     ends `/node_modules/.bin/vite`, covering bare app-relative, `./`-relative,
     and absolute launcher tokens; or argv[0] has basename `vite`; or an npm/npx
     executable/`npm-cli.js` process has exact token `dev` and cwd exactly
     `/home/tommaso/Dev/NeuroClient/app`; or a shell has exact argv tail `-c`,
     `vite` and that same exact cwd;
   - `playwright`: an argv token is a normalized path containing the complete
     path segment `/node_modules/playwright-core/` or
     `/node_modules/playwright/`, or argv[0] has basename `playwright`;
   - `chromium`: `/proc/<pid>/exe` or argv[0] has basename `chromium`,
     `chromium-browser`, `chrome-headless-shell`, or `headless_shell`, or the
     executable path contains the complete segment `/ms-playwright/` and has
     basename `chrome`;
10. a consecutive-token test means adjacency in the NUL-decoded argv list; a
   basename test uses `os.path.basename`; path normalization changes `\\` to
   `/` only; npm/npx recognition requires argv[0] basename in `npm`, `npm.cmd`,
   `npx`, `npx.cmd`, `npm-cli.js`, or `npx-cli.js`, or an argv token whose
   basename is exactly `npm-cli.js` or `npx-cli.js`;
11. execute the embedded pure-record controls before enumeration: the exact
    positive tuple must exclude; independently changing every discriminator,
    allowing only one denied read, changing either errno, presenting a generic
    unreadable same-euid record, or presenting any hosted-smoke, gateway,
    hosted-worker, event-server, preview-worker, Vite, Playwright, or Chromium
    argv family with denied executable/cwd must never exclude and must retain a
    match/error disposition; controls must also cover stable executable denial
    followed by cwd disappearance, premature PPid 0, ancestor cycle, changed
    target starttime, each final packet argv family, changed final target or
    cgroup, reparenting, and missing/error final snapshot; for all eight packet
    families, both a final-change case and a pre-pin-reuse case must start with
    stale outer `(sd-pam)` argv, use a complete stable packet final snapshot,
    retain ordinary errors under denied readlinks, and return the expected
    packet match from final argv plus final PPid under readable representative
    exe/cwd; exclusion-only assertions are insufficient; an unchanged
    live-shaped outer target constructed through `candidate_status` must
    compare equal to the initial snapshot, while every released discriminator
    mutation remains unequal;
12. collect every control/read error, every accepted positive-class exclusion,
    and every packet match; sort errors by PID then stage, exclusions by PID
    then class, and matches by PID then class; emit exactly one compact,
    sort-key JSON object with keys `errors`, `excluded`, and `matches`; each
    error contains PID, stage, and error; the exclusion retains the pinned
    outer candidate observation, both complete accepted snapshots, and both
    denial stages; each match contains class, PID,
    PPID, executable, cwd, and argv, using final authoritative candidate values;
    exit 1 when errors or matches are nonempty
    and otherwise exit 0.

The exact standard-input program is:

```python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROC = Path("/proc")
APP_ROOT = "/home/tommaso/Dev/NeuroClient/app"
NEUROCLIENT_ROOT = "/home/tommaso/Dev/NeuroClient"
NPM_BASENAMES = {"npm", "npm.cmd", "npx", "npx.cmd", "npm-cli.js", "npx-cli.js"}
SHELL_BASENAMES = {"bash", "dash", "sh", "zsh"}
CHROMIUM_BASENAMES = {
    "chrome-headless-shell",
    "chromium",
    "chromium-browser",
    "headless_shell",
}


def normalized(value: str) -> str:
    return value.replace("\\", "/")


def basename(value: str) -> str:
    return os.path.basename(normalized(value))


def status_fields(pid: int) -> dict[str, str]:
    text = (PROC / str(pid) / "status").read_text(
        encoding="utf-8",
        errors="surrogateescape",
    )
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key] = value.strip()
    return values


def integer_field(values: dict[str, str], key: str, count: int) -> list[int]:
    result = [int(item, 10) for item in values[key].split()]
    if len(result) != count:
        raise ValueError(f"{key} must contain exactly {count} integers")
    return result


def basic_status(values: dict[str, str]) -> dict[str, object]:
    return {
        "name": values["Name"],
        "ppid": int(values["PPid"].split()[0]),
        "uids": integer_field(values, "Uid", 4),
    }


def candidate_status(values: dict[str, str]) -> dict[str, object]:
    result = basic_status(values)
    result.update(
        {
            "cap_amb": int(values["CapAmb"], 16),
            "cap_eff": int(values["CapEff"], 16),
            "cap_prm": int(values["CapPrm"], 16),
            "core_dumping": int(values["CoreDumping"], 10),
            "gids": integer_field(values, "Gid", 4),
            "no_new_privs": int(values["NoNewPrivs"], 10),
            "seccomp": int(values["Seccomp"], 10),
            "seccomp_filters": int(values["Seccomp_filters"], 10),
            "tracer_pid": int(values["TracerPid"], 10),
        }
    )
    return result


def status(pid: int) -> tuple[int, int]:
    values = basic_status(status_fields(pid))
    return int(values["ppid"]), int(values["uids"][1])


def process_entry_present(pid: int) -> bool:
    try:
        (PROC / str(pid)).stat()
    except (FileNotFoundError, ProcessLookupError):
        return False
    except Exception:
        return True
    return True


def append_error(
    errors: list[dict[str, object]],
    *,
    pid: int,
    stage: str,
    detail: str,
) -> None:
    errors.append({"error": detail, "pid": pid, "stage": stage})


def failure(stage: str, exc: BaseException) -> dict[str, object]:
    return {
        "errno": getattr(exc, "errno", None),
        "error": f"{type(exc).__name__}: {exc}",
        "stage": stage,
        "type": type(exc).__name__,
    }


def append_failure(
    errors: list[dict[str, object]],
    *,
    pid: int,
    read_failure: dict[str, object],
) -> None:
    append_error(
        errors,
        pid=pid,
        stage=str(read_failure["stage"]),
        detail=str(read_failure["error"]),
    )


def readlink_result(
    entry: Path,
    *,
    pid: int,
    stage: str,
) -> tuple[str | None, dict[str, object] | None, bool]:
    try:
        return os.readlink(entry / stage), None, False
    except (FileNotFoundError, ProcessLookupError) as exc:
        if not process_entry_present(pid):
            return None, None, True
        return None, failure(stage, exc), False
    except Exception as exc:
        return None, failure(stage, exc), False


def read_required_status(
    errors: list[dict[str, object]],
    *,
    pid: int,
    stage: str,
) -> dict[str, str] | None:
    try:
        return status_fields(pid)
    except (FileNotFoundError, ProcessLookupError) as exc:
        detail = (
            f"{type(exc).__name__}: {exc}"
            if process_entry_present(pid)
            else "required related process disappeared before status was read"
        )
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
    append_error(errors, pid=pid, stage=stage, detail=detail)
    return None


def process_starttime(pid: int) -> int:
    text = (PROC / str(pid) / "stat").read_text(
        encoding="utf-8",
        errors="surrogateescape",
    )
    prefix = f"{pid} ("
    if not text.startswith(prefix):
        raise ValueError("stat PID prefix did not match the captured PID")
    closing = text.rfind(")")
    if closing < len(prefix):
        raise ValueError("stat comm field had no closing parenthesis")
    fields_from_state = text[closing + 1 :].split()
    if len(fields_from_state) <= 19:
        raise ValueError("stat did not contain field 22 starttime")
    return int(fields_from_state[19], 10)


def read_required_starttime(
    errors: list[dict[str, object]],
    *,
    pid: int,
    stage: str,
) -> int | None:
    try:
        return process_starttime(pid)
    except (FileNotFoundError, ProcessLookupError) as exc:
        detail = (
            f"{type(exc).__name__}: {exc}"
            if process_entry_present(pid)
            else "candidate process disappeared before starttime was read"
        )
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
    append_error(errors, pid=pid, stage=stage, detail=detail)
    return None


def read_required_cmdline(
    errors: list[dict[str, object]],
    *,
    pid: int,
    stage: str,
) -> tuple[bytes, list[str]] | None:
    try:
        raw_argv = (PROC / str(pid) / "cmdline").read_bytes()
    except (FileNotFoundError, ProcessLookupError) as exc:
        detail = (
            f"{type(exc).__name__}: {exc}"
            if process_entry_present(pid)
            else "candidate process disappeared before argv was read"
        )
        append_error(errors, pid=pid, stage=stage, detail=detail)
        return None
    except Exception as exc:
        append_error(
            errors,
            pid=pid,
            stage=stage,
            detail=f"{type(exc).__name__}: {exc}",
        )
        return None
    if not raw_argv:
        append_error(
            errors,
            pid=pid,
            stage=stage,
            detail="candidate cmdline was empty",
        )
        return None
    argv = [
        token.decode("utf-8", errors="surrogateescape")
        for token in raw_argv.split(b"\0")
        if token
    ]
    if not argv:
        append_error(
            errors,
            pid=pid,
            stage=stage,
            detail="candidate decoded argv was empty",
        )
        return None
    return raw_argv, argv


def read_required_cgroup(
    errors: list[dict[str, object]],
    *,
    pid: int,
    stage: str,
) -> str | None:
    try:
        text = (PROC / str(pid) / "cgroup").read_text(
            encoding="utf-8",
            errors="surrogateescape",
        )
    except (FileNotFoundError, ProcessLookupError) as exc:
        detail = (
            f"{type(exc).__name__}: {exc}"
            if process_entry_present(pid)
            else "candidate process disappeared before cgroup was read"
        )
        append_error(
            errors,
            pid=pid,
            stage=stage,
            detail=detail,
        )
        return None
    except Exception as exc:
        append_error(
            errors,
            pid=pid,
            stage=stage,
            detail=f"{type(exc).__name__}: {exc}",
        )
        return None
    return text.rstrip("\n")


def ancestor_step_error(
    *,
    current: int,
    parent: int,
    captured: set[int],
) -> str | None:
    if parent <= 0:
        return f"ancestor PID {current} terminated at invalid PPid {parent} before PID 1"
    if parent in captured:
        return f"ancestor cycle from PID {current} to already captured PID {parent}"
    return None


def ancestor_exclusions(errors: list[dict[str, object]]) -> set[int]:
    excluded: set[int] = set()
    current = os.getpid()
    initial_error_count = len(errors)
    reached_pid1 = False
    while current > 0 and current not in excluded:
        excluded.add(current)
        if current == 1:
            reached_pid1 = True
            break
        try:
            parent = status(current)[0]
        except (FileNotFoundError, ProcessLookupError) as exc:
            if process_entry_present(current):
                detail = f"{type(exc).__name__}: {exc}"
            else:
                detail = "captured ancestor disappeared before PPid was read"
            append_error(
                errors,
                pid=current,
                stage="ancestor-status",
                detail=detail,
            )
            break
        except Exception as exc:
            append_error(
                errors,
                pid=current,
                stage="ancestor-status",
                detail=f"{type(exc).__name__}: {exc}",
            )
            break
        step_error = ancestor_step_error(
            current=current,
            parent=parent,
            captured=excluded,
        )
        if step_error is not None:
            append_error(
                errors,
                pid=current,
                stage="ancestor-status",
                detail=step_error,
            )
            break
        current = parent
    if not reached_pid1 and len(errors) == initial_error_count:
        append_error(
            errors,
            pid=os.getpid(),
            stage="ancestor-status",
            detail="ancestor traversal ended without positively reaching PID 1",
        )
    return excluded


def contains_pair(argv: list[str], first: str, second: str) -> bool:
    return any(
        argv[index] == first and argv[index + 1] == second
        for index in range(len(argv) - 1)
    )


def npm_process(argv: list[str]) -> bool:
    return bool(argv) and (
        basename(argv[0]) in NPM_BASENAMES
        or any(basename(token) in {"npm-cli.js", "npx-cli.js"} for token in argv)
    )


def argv_classes(argv: list[str]) -> list[str]:
    result: list[str] = []
    argv0 = basename(argv[0])
    normalized_tokens = [normalized(token) for token in argv]
    is_npm = npm_process(argv)

    if any(basename(token) == "hosted-game-smoke.mjs" for token in argv) or (
        is_npm and "hosted-game:smoke" in argv
    ):
        result.append("hosted-smoke")
    if contains_pair(argv, "-m", "uvicorn") and "server.game_gateway:app" in argv:
        result.append("gateway")
    if (
        contains_pair(argv, "-m", "uvicorn")
        and "server.event_server:app" in argv
        and "--uds" in argv
    ):
        result.append("hosted-worker")
    if contains_pair(argv, "-m", "server.event_server") or (
        contains_pair(argv, "-m", "uvicorn")
        and "server.event_server:app" in argv
    ):
        result.append("event-server")
    if (
        contains_pair(argv, "-m", "server.game_creation_preview_worker")
        and "--serve" in argv
    ):
        result.append("preview-worker")
    if (
        any(token.endswith("/node_modules/vite/bin/vite.js") for token in normalized_tokens)
        or any(
            token == "node_modules/.bin/vite"
            or token.endswith("/node_modules/.bin/vite")
            for token in normalized_tokens
        )
        or argv0 == "vite"
    ):
        result.append("vite")
    if (
        argv0 == "playwright"
        or any(
            "/node_modules/playwright-core/" in token
            or "/node_modules/playwright/" in token
            for token in normalized_tokens
        )
    ):
        result.append("playwright")
    if argv0 in CHROMIUM_BASENAMES:
        result.append("chromium")
    return sorted(set(result))


def classes(argv: list[str], executable: str, cwd: str) -> list[str]:
    result = argv_classes(argv)
    argv0 = basename(argv[0])
    normalized_executable = normalized(executable)
    is_npm = npm_process(argv)

    if (
        (is_npm and "dev" in argv and cwd == APP_ROOT)
        or (
            is_npm
            and "dev" in argv
            and cwd == NEUROCLIENT_ROOT
            and any(
                argv[index] == "--prefix" and argv[index + 1] in {"app", "./app"}
                for index in range(len(argv) - 1)
            )
        )
        or (
            argv0 in SHELL_BASENAMES
            and len(argv) >= 3
            and argv[-2:] == ["-c", "vite"]
            and cwd == APP_ROOT
        )
    ):
        result.append("vite")
    executable_basename = basename(normalized_executable)
    if (
        executable_basename in CHROMIUM_BASENAMES
        or (
            "/ms-playwright/" in normalized_executable
            and executable_basename == "chrome"
        )
    ):
        result.append("chromium")
    return sorted(set(result))


def read_candidate_snapshot(
    errors: list[dict[str, object]],
    *,
    pid: int,
    label: str,
) -> dict[str, object] | None:
    start_before = read_required_starttime(
        errors,
        pid=pid,
        stage=f"systemd-pam-{label}-starttime-before",
    )
    target_values = read_required_status(
        errors,
        pid=pid,
        stage=f"systemd-pam-{label}-target-status",
    )
    cmdline = read_required_cmdline(
        errors,
        pid=pid,
        stage=f"systemd-pam-{label}-argv",
    )
    cgroup = read_required_cgroup(
        errors,
        pid=pid,
        stage=f"systemd-pam-{label}-cgroup",
    )

    target: dict[str, object] | None = None
    parent: dict[str, object] | None = None
    pid1: dict[str, object] | None = None
    if target_values is not None:
        try:
            target = candidate_status(target_values)
        except Exception as exc:
            append_error(
                errors,
                pid=pid,
                stage=f"systemd-pam-{label}-target-status",
                detail=f"{type(exc).__name__}: {exc}",
            )
    if target is not None:
        parent_pid = int(target["ppid"])
        parent_values = read_required_status(
            errors,
            pid=parent_pid,
            stage=f"systemd-pam-{label}-parent-status",
        )
        if parent_values is not None:
            try:
                parent = basic_status(parent_values)
                parent["pid"] = parent_pid
            except Exception as exc:
                append_error(
                    errors,
                    pid=parent_pid,
                    stage=f"systemd-pam-{label}-parent-status",
                    detail=f"{type(exc).__name__}: {exc}",
                )
    pid1_values = read_required_status(
        errors,
        pid=1,
        stage=f"systemd-pam-{label}-pid1-status",
    )
    if pid1_values is not None:
        try:
            pid1 = basic_status(pid1_values)
            pid1["pid"] = 1
        except Exception as exc:
            append_error(
                errors,
                pid=1,
                stage=f"systemd-pam-{label}-pid1-status",
                detail=f"{type(exc).__name__}: {exc}",
            )
    start_after = read_required_starttime(
        errors,
        pid=pid,
        stage=f"systemd-pam-{label}-starttime-after",
    )
    if (
        start_before is None
        or start_after is None
        or target is None
        or cmdline is None
        or cgroup is None
        or parent is None
        or pid1 is None
    ):
        return None
    if start_before != start_after:
        append_error(
            errors,
            pid=pid,
            stage=f"systemd-pam-{label}-generation",
            detail=f"starttime changed from {start_before} to {start_after}",
        )
        return None
    raw_argv, argv = cmdline
    return {
        "argv": argv,
        "cgroup": cgroup,
        "packet_argv_classes": argv_classes(argv),
        "parent": parent,
        "pid1": pid1,
        "raw_argv": raw_argv,
        "starttime": start_before,
        "target": target,
    }


def snapshot_changes(
    initial: dict[str, object],
    final: dict[str, object],
) -> list[str]:
    return sorted(
        key
        for key in set(initial) | set(final)
        if initial.get(key) != final.get(key)
    )


def snapshot_receipt(snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "argv": snapshot["argv"],
        "cgroup": snapshot["cgroup"],
        "packet_argv_classes": snapshot["packet_argv_classes"],
        "parent": snapshot["parent"],
        "pid1": snapshot["pid1"],
        "raw_argv_hex": bytes(snapshot["raw_argv"]).hex(),
        "starttime": snapshot["starttime"],
        "target": snapshot["target"],
    }


def candidate_outer_changes(
    outer_observation: dict[str, object] | None,
    initial_snapshot: dict[str, object] | None,
) -> list[str]:
    if outer_observation is None or initial_snapshot is None:
        return ["missing"]
    return sorted(
        key
        for key in ("argv", "raw_argv", "starttime", "target")
        if outer_observation.get(key) != initial_snapshot.get(key)
    )


def candidate_outer_receipt(
    outer_observation: dict[str, object],
) -> dict[str, object]:
    return {
        "argv": outer_observation["argv"],
        "raw_argv_hex": bytes(outer_observation["raw_argv"]).hex(),
        "starttime": outer_observation["starttime"],
        "target": outer_observation["target"],
    }


def ordinary_disposition(
    *,
    candidate_signal: bool,
    final_snapshot: dict[str, object] | None,
    outer_argv: list[str],
    outer_ppid: int,
    executable: str | None,
    cwd: str | None,
    executable_failure: dict[str, object] | None,
    cwd_failure: dict[str, object] | None,
) -> dict[str, object]:
    disposition_errors: list[str] = []
    read_failures = [
        failure
        for failure in (executable_failure, cwd_failure)
        if failure is not None
    ]
    authoritative_argv: list[str] | None = None
    authoritative_ppid: int | None = None
    if candidate_signal:
        if final_snapshot is None:
            disposition_errors.append("candidate final snapshot unavailable")
        else:
            snapshot_argv = final_snapshot.get("argv")
            snapshot_target = final_snapshot.get("target")
            if not isinstance(snapshot_argv, list) or not all(
                isinstance(token, str) for token in snapshot_argv
            ):
                disposition_errors.append("candidate final argv unavailable")
            else:
                authoritative_argv = list(snapshot_argv)
            if not isinstance(snapshot_target, dict) or not isinstance(
                snapshot_target.get("ppid"), int
            ):
                disposition_errors.append("candidate final PPid unavailable")
            else:
                authoritative_ppid = int(snapshot_target["ppid"])
    else:
        authoritative_argv = list(outer_argv)
        authoritative_ppid = outer_ppid
    matched_classes: list[str] = []
    if not disposition_errors and not read_failures:
        if executable is None or cwd is None:
            disposition_errors.append(
                "readlink completed without a value, failure, or disappearance"
            )
        elif authoritative_argv is not None:
            matched_classes = classes(authoritative_argv, executable, cwd)
    return {
        "argv": authoritative_argv,
        "classes": matched_classes,
        "errors": disposition_errors,
        "ppid": authoritative_ppid,
        "read_failures": read_failures,
    }


def is_permission_denied(
    read_failure: dict[str, object] | None,
    *,
    expected_stage: str,
) -> bool:
    return bool(
        read_failure
        and read_failure.get("type") == "PermissionError"
        and read_failure.get("errno") == 13
        and read_failure.get("stage") == expected_stage
    )


def systemd_pam_tuple_matches(
    *,
    snapshot: dict[str, object] | None,
    effective_uid: int,
    effective_gid: int,
) -> bool:
    expected_cgroup = (
        f"0::/user.slice/user-{effective_uid}.slice/"
        f"user@{effective_uid}.service/init.scope"
    )
    if not snapshot:
        return False
    raw_argv = snapshot.get("raw_argv")
    argv = snapshot.get("argv")
    target = snapshot.get("target")
    cgroup = snapshot.get("cgroup")
    parent = snapshot.get("parent")
    pid1 = snapshot.get("pid1")
    return bool(
        isinstance(target, dict)
        and isinstance(parent, dict)
        and isinstance(pid1, dict)
        and target.get("name") == "(sd-pam)"
        and raw_argv == b"(sd-pam)\0"
        and argv == ["(sd-pam)"]
        and target.get("uids") == [effective_uid] * 4
        and target.get("gids") == [effective_gid] * 4
        and target.get("cap_eff") == 0
        and target.get("cap_prm") == 0
        and target.get("cap_amb") == 0
        and target.get("tracer_pid") == 0
        and target.get("core_dumping") == 0
        and target.get("no_new_privs") == 0
        and target.get("seccomp") == 0
        and target.get("seccomp_filters") == 0
        and cgroup == expected_cgroup
        and target.get("ppid") == parent.get("pid")
        and parent.get("name") == "systemd"
        and parent.get("uids") == [effective_uid] * 4
        and parent.get("ppid") == pid1.get("pid") == 1
        and pid1.get("name") == "systemd"
        and pid1.get("uids") == [0] * 4
        and pid1.get("ppid") == 0
    )


def systemd_pam_exclusion(
    *,
    outer_observation: dict[str, object] | None,
    initial_snapshot: dict[str, object] | None,
    final_snapshot: dict[str, object] | None,
    effective_uid: int,
    effective_gid: int,
    executable_failure: dict[str, object] | None,
    cwd_failure: dict[str, object] | None,
) -> bool:
    return bool(
        initial_snapshot
        and final_snapshot
        and not candidate_outer_changes(outer_observation, initial_snapshot)
        and not snapshot_changes(initial_snapshot, final_snapshot)
        and not initial_snapshot.get("packet_argv_classes")
        and not final_snapshot.get("packet_argv_classes")
        and is_permission_denied(
            executable_failure,
            expected_stage="executable",
        )
        and is_permission_denied(cwd_failure, expected_stage="cwd")
        and systemd_pam_tuple_matches(
            snapshot=final_snapshot,
            effective_uid=effective_uid,
            effective_gid=effective_gid,
        )
    )


def failures_before_cwd_disappearance(
    executable_failure: dict[str, object] | None,
    *,
    cwd_vanished: bool,
) -> list[dict[str, object]]:
    if cwd_vanished and executable_failure is not None:
        return [executable_failure]
    return []


def run_protocol_controls(errors: list[dict[str, object]]) -> None:
    effective_uid = 1000
    effective_gid = 1000
    target: dict[str, object] = {
        "cap_amb": 0,
        "cap_eff": 0,
        "cap_prm": 0,
        "core_dumping": 0,
        "gids": [effective_gid] * 4,
        "name": "(sd-pam)",
        "no_new_privs": 0,
        "ppid": 602,
        "seccomp": 0,
        "seccomp_filters": 0,
        "tracer_pid": 0,
        "uids": [effective_uid] * 4,
    }
    parent: dict[str, object] = {
        "name": "systemd",
        "pid": 602,
        "ppid": 1,
        "uids": [effective_uid] * 4,
    }
    pid1: dict[str, object] = {
        "name": "systemd",
        "pid": 1,
        "ppid": 0,
        "uids": [0] * 4,
    }
    positive_snapshot: dict[str, object] = {
        "argv": ["(sd-pam)"],
        "cgroup": (
            "0::/user.slice/user-1000.slice/"
            "user@1000.service/init.scope"
        ),
        "packet_argv_classes": [],
        "parent": parent,
        "pid1": pid1,
        "raw_argv": b"(sd-pam)\0",
        "starttime": 123456,
        "target": target,
    }
    live_status_values = {
        "CapAmb": "0000000000000000",
        "CapEff": "0000000000000000",
        "CapPrm": "0000000000000000",
        "CoreDumping": "0",
        "Gid": "1000 1000 1000 1000",
        "Name": "(sd-pam)",
        "NoNewPrivs": "0",
        "PPid": "602",
        "Seccomp": "0",
        "Seccomp_filters": "0",
        "TracerPid": "0",
        "Uid": "1000 1000 1000 1000",
    }
    live_outer_target = candidate_status(live_status_values)
    positive_outer_observation: dict[str, object] = {
        "argv": ["(sd-pam)"],
        "raw_argv": b"(sd-pam)\0",
        "starttime": 123456,
        "target": live_outer_target,
    }
    executable_failure = {
        "errno": 13,
        "error": "PermissionError: controlled executable denial",
        "stage": "executable",
        "type": "PermissionError",
    }
    cwd_failure = {
        "errno": 13,
        "error": "PermissionError: controlled cwd denial",
        "stage": "cwd",
        "type": "PermissionError",
    }

    unset = object()

    def excluded(
        *,
        control_outer: object = unset,
        control_initial: object = unset,
        control_final: object = unset,
        control_effective_uid: int = effective_uid,
        control_effective_gid: int = effective_gid,
        control_executable_failure: dict[str, object] | None = executable_failure,
        control_cwd_failure: dict[str, object] | None = cwd_failure,
    ) -> bool:
        return systemd_pam_exclusion(
            outer_observation=(
                positive_outer_observation
                if control_outer is unset
                else control_outer  # type: ignore[arg-type]
            ),
            initial_snapshot=(
                positive_snapshot
                if control_initial is unset
                else control_initial  # type: ignore[arg-type]
            ),
            final_snapshot=(
                positive_snapshot
                if control_final is unset
                else control_final  # type: ignore[arg-type]
            ),
            effective_uid=control_effective_uid,
            effective_gid=control_effective_gid,
            executable_failure=control_executable_failure,
            cwd_failure=control_cwd_failure,
        )

    def same_snapshot(mutated: dict[str, object]) -> bool:
        return excluded(control_initial=mutated, control_final=mutated)

    def require(label: str, expected: bool, actual: bool) -> None:
        if actual != expected:
            append_error(
                errors,
                pid=0,
                stage=f"protocol-control-{label}",
                detail=f"expected exclusion={expected}, observed {actual}",
            )

    require("positive", True, excluded())
    require(
        "outer-live-shape",
        True,
        bool(
            live_outer_target == target
            and not candidate_outer_changes(
                positive_outer_observation,
                positive_snapshot,
            )
        ),
    )
    require(
        "outer-generation",
        False,
        excluded(
            control_outer={
                **positive_outer_observation,
                "starttime": 123455,
            }
        ),
    )
    require(
        "outer-target",
        False,
        excluded(
            control_outer={
                **positive_outer_observation,
                "target": {**target, "name": "stale"},
            }
        ),
    )
    require(
        "outer-raw-argv",
        False,
        excluded(
            control_outer={
                **positive_outer_observation,
                "raw_argv": b"stale\0",
            }
        ),
    )
    require(
        "outer-decoded-argv",
        False,
        excluded(
            control_outer={
                **positive_outer_observation,
                "argv": ["stale"],
            }
        ),
    )
    require("effective-uid", False, excluded(control_effective_uid=1001))
    require("effective-gid", False, excluded(control_effective_gid=1001))
    target_mutations: list[tuple[str, dict[str, object]]] = [
        ("name", {**target, "name": "not-sd-pam"}),
        ("uids", {**target, "uids": [effective_uid, effective_uid, 0, effective_uid]}),
        ("gids", {**target, "gids": [effective_gid, effective_gid, 0, effective_gid]}),
        ("cap-eff", {**target, "cap_eff": 1}),
        ("cap-prm", {**target, "cap_prm": 1}),
        ("cap-amb", {**target, "cap_amb": 1}),
        ("tracer", {**target, "tracer_pid": 1}),
        ("core-dumping", {**target, "core_dumping": 1}),
        ("no-new-privs", {**target, "no_new_privs": 1}),
        ("seccomp", {**target, "seccomp": 1}),
        ("seccomp-filters", {**target, "seccomp_filters": 1}),
    ]
    for label, mutated_target in target_mutations:
        mutated = {**positive_snapshot, "target": mutated_target}
        require(label, False, same_snapshot(mutated))
    require(
        "raw-argv",
        False,
        same_snapshot({**positive_snapshot, "raw_argv": b"(sd-pam)"}),
    )
    require(
        "argv-cardinality",
        False,
        same_snapshot({**positive_snapshot, "argv": ["(sd-pam)", "extra"]}),
    )
    require(
        "argv-value",
        False,
        same_snapshot({**positive_snapshot, "argv": ["not-sd-pam"]}),
    )
    require(
        "cgroup",
        False,
        same_snapshot({**positive_snapshot, "cgroup": "0::/wrong.scope"}),
    )
    require(
        "cgroup-missing",
        False,
        same_snapshot({**positive_snapshot, "cgroup": ""}),
    )
    require(
        "target-missing",
        False,
        same_snapshot({**positive_snapshot, "target": {}}),
    )
    require(
        "target-parent-relation",
        False,
        same_snapshot(
            {**positive_snapshot, "target": {**target, "ppid": 999}}
        ),
    )
    require(
        "parent-name",
        False,
        same_snapshot(
            {**positive_snapshot, "parent": {**parent, "name": "not-systemd"}}
        ),
    )
    require(
        "parent-uids",
        False,
        same_snapshot(
            {
                **positive_snapshot,
                "parent": {**parent, "uids": [effective_uid, 0, 0, 0]},
            }
        ),
    )
    require(
        "parent-pid",
        False,
        same_snapshot({**positive_snapshot, "parent": {**parent, "pid": 999}}),
    )
    require(
        "parent-relation",
        False,
        same_snapshot({**positive_snapshot, "parent": {**parent, "ppid": 2}}),
    )
    require(
        "parent-missing",
        False,
        same_snapshot({**positive_snapshot, "parent": {}}),
    )
    require(
        "pid1-name",
        False,
        same_snapshot(
            {**positive_snapshot, "pid1": {**pid1, "name": "not-systemd"}}
        ),
    )
    require(
        "pid1-uids",
        False,
        same_snapshot(
            {**positive_snapshot, "pid1": {**pid1, "uids": [0, 0, 0, 1]}}
        ),
    )
    require(
        "pid1-pid",
        False,
        same_snapshot({**positive_snapshot, "pid1": {**pid1, "pid": 2}}),
    )
    require(
        "pid1-relation",
        False,
        same_snapshot({**positive_snapshot, "pid1": {**pid1, "ppid": 1}}),
    )
    require(
        "pid1-missing",
        False,
        same_snapshot({**positive_snapshot, "pid1": {}}),
    )
    require(
        "packet-preemption",
        False,
        same_snapshot(
            {**positive_snapshot, "packet_argv_classes": ["hosted-smoke"]}
        ),
    )
    require(
        "executable-only-denial",
        False,
        excluded(control_cwd_failure={}),
    )
    require(
        "cwd-only-denial",
        False,
        excluded(control_executable_failure={}),
    )
    require(
        "executable-errno",
        False,
        excluded(control_executable_failure={**executable_failure, "errno": 1}),
    )
    require(
        "executable-type",
        False,
        excluded(control_executable_failure={**executable_failure, "type": "OSError"}),
    )
    require(
        "executable-stage",
        False,
        excluded(control_executable_failure={**executable_failure, "stage": "cwd"}),
    )
    require(
        "cwd-errno",
        False,
        excluded(control_cwd_failure={**cwd_failure, "errno": 1}),
    )
    require(
        "cwd-type",
        False,
        excluded(control_cwd_failure={**cwd_failure, "type": "OSError"}),
    )
    require(
        "cwd-stage",
        False,
        excluded(control_cwd_failure={**cwd_failure, "stage": "executable"}),
    )
    require(
        "generic-unreadable",
        False,
        excluded(
            control_initial={
                **positive_snapshot,
                "argv": ["generic"],
                "raw_argv": b"generic\0",
                "target": {**target, "name": "generic"},
            },
            control_final={
                **positive_snapshot,
                "argv": ["generic"],
                "raw_argv": b"generic\0",
                "target": {**target, "name": "generic"},
            },
        ),
    )

    require(
        "generation-change",
        False,
        excluded(
            control_final={**positive_snapshot, "starttime": 123457},
        ),
    )
    require(
        "final-target-change",
        False,
        excluded(
            control_final={
                **positive_snapshot,
                "target": {**target, "name": "changed"},
            },
        ),
    )
    require(
        "final-cgroup-change",
        False,
        excluded(control_final={**positive_snapshot, "cgroup": "0::/changed"}),
    )
    require(
        "final-reparent",
        False,
        excluded(
            control_final={
                **positive_snapshot,
                "target": {**target, "ppid": 999},
            },
        ),
    )
    require(
        "final-parent-change",
        False,
        excluded(
            control_final={
                **positive_snapshot,
                "parent": {**parent, "uids": [effective_uid, 0, 0, 0]},
            },
        ),
    )
    require(
        "final-pid1-change",
        False,
        excluded(
            control_final={
                **positive_snapshot,
                "pid1": {**pid1, "ppid": 1},
            },
        ),
    )
    require("final-missing", False, excluded(control_final={}))
    require("final-error", False, excluded(control_final=None))
    missing_final_disposition = ordinary_disposition(
        candidate_signal=True,
        final_snapshot=None,
        outer_argv=["(sd-pam)"],
        outer_ppid=602,
        executable="/usr/bin/packet-process",
        cwd=APP_ROOT,
        executable_failure=None,
        cwd_failure=None,
    )
    require(
        "final-missing-disposition",
        True,
        bool(
            missing_final_disposition["errors"]
            and not missing_final_disposition["classes"]
            and missing_final_disposition["argv"] is None
            and missing_final_disposition["ppid"] is None
        ),
    )
    require(
        "exe-failure-cwd-disappearance",
        True,
        failures_before_cwd_disappearance(
            executable_failure,
            cwd_vanished=True,
        ) == [executable_failure],
    )
    require(
        "ancestor-premature-ppid0",
        True,
        ancestor_step_error(current=20, parent=0, captured={20}) is not None,
    )
    require(
        "ancestor-cycle",
        True,
        ancestor_step_error(current=20, parent=19, captured={19, 20}) is not None,
    )

    packet_controls: dict[str, list[str]] = {
        "hosted-smoke": ["node", "/x/hosted-game-smoke.mjs"],
        "gateway": ["python", "-m", "uvicorn", "server.game_gateway:app"],
        "hosted-worker": [
            "python",
            "-m",
            "uvicorn",
            "server.event_server:app",
            "--uds",
            "/tmp/worker.sock",
        ],
        "event-server": ["python", "-m", "server.event_server"],
        "preview-worker": [
            "python",
            "-m",
            "server.game_creation_preview_worker",
            "--serve",
        ],
        "vite": ["node", "/x/node_modules/.bin/vite"],
        "playwright": ["node", "/x/node_modules/playwright-core/cli.js"],
        "chromium": ["chrome-headless-shell"],
    }
    for expected_class, control_argv in packet_controls.items():
        packet_classes = argv_classes(control_argv)
        if expected_class not in packet_classes:
            append_error(
                errors,
                pid=0,
                stage=f"protocol-control-{expected_class}-classifier",
                detail=f"argv classifier returned {packet_classes}",
            )
        raw_control_argv = b"\0".join(
            token.encode("utf-8") for token in control_argv
        ) + b"\0"
        replacement_target = {
            **target,
            "name": expected_class,
            "ppid": 777,
        }
        replacement_parent = {
            **parent,
            "name": "packet-parent",
            "pid": 777,
            "ppid": 602,
        }
        packet_snapshot = {
            **positive_snapshot,
            "argv": control_argv,
            "packet_argv_classes": packet_classes,
            "parent": replacement_parent,
            "raw_argv": raw_control_argv,
            "target": replacement_target,
        }
        require(
            f"{expected_class}-preemption",
            False,
            same_snapshot(packet_snapshot),
        )
        require(
            f"{expected_class}-final-change",
            False,
            excluded(control_final=packet_snapshot),
        )
        final_denied = ordinary_disposition(
            candidate_signal=True,
            final_snapshot=packet_snapshot,
            outer_argv=["(sd-pam)"],
            outer_ppid=602,
            executable=None,
            cwd=None,
            executable_failure=executable_failure,
            cwd_failure=cwd_failure,
        )
        require(
            f"{expected_class}-final-denied-error",
            True,
            bool(
                final_denied["read_failures"]
                == [executable_failure, cwd_failure]
                and final_denied["argv"] == control_argv
                and final_denied["ppid"] == 777
                and not final_denied["classes"]
            ),
        )
        final_readable = ordinary_disposition(
            candidate_signal=True,
            final_snapshot=packet_snapshot,
            outer_argv=["(sd-pam)"],
            outer_ppid=602,
            executable="/usr/bin/packet-process",
            cwd=APP_ROOT,
            executable_failure=None,
            cwd_failure=None,
        )
        require(
            f"{expected_class}-final-readable-match",
            True,
            bool(
                expected_class in final_readable["classes"]
                and final_readable["argv"] == control_argv
                and final_readable["ppid"] == 777
                and not final_readable["errors"]
                and not final_readable["read_failures"]
            ),
        )
        require(
            f"{expected_class}-prepin-change",
            True,
            bool(candidate_outer_changes(positive_outer_observation, packet_snapshot)),
        )
        require(
            f"{expected_class}-prepin-exclusion",
            False,
            excluded(
                control_initial=packet_snapshot,
                control_final=packet_snapshot,
            ),
        )
        prepin_denied = ordinary_disposition(
            candidate_signal=True,
            final_snapshot=packet_snapshot,
            outer_argv=["(sd-pam)"],
            outer_ppid=602,
            executable=None,
            cwd=None,
            executable_failure=executable_failure,
            cwd_failure=cwd_failure,
        )
        require(
            f"{expected_class}-prepin-denied-error",
            True,
            bool(
                prepin_denied["read_failures"]
                == [executable_failure, cwd_failure]
                and prepin_denied["argv"] == control_argv
                and prepin_denied["ppid"] == 777
                and not prepin_denied["classes"]
            ),
        )
        prepin_readable = ordinary_disposition(
            candidate_signal=True,
            final_snapshot=packet_snapshot,
            outer_argv=["(sd-pam)"],
            outer_ppid=602,
            executable="/usr/bin/packet-process",
            cwd=APP_ROOT,
            executable_failure=None,
            cwd_failure=None,
        )
        require(
            f"{expected_class}-prepin-readable-match",
            True,
            bool(
                expected_class in prepin_readable["classes"]
                and prepin_readable["argv"] == control_argv
                and prepin_readable["ppid"] == 777
                and not prepin_readable["errors"]
                and not prepin_readable["read_failures"]
            ),
        )


errors: list[dict[str, object]] = []
run_protocol_controls(errors)
ancestor_pids = ancestor_exclusions(errors)
effective_uid = os.geteuid()
effective_gid = os.getegid()
excluded_entries: list[dict[str, object]] = []
matches: list[dict[str, object]] = []

for entry in sorted(
    (item for item in PROC.iterdir() if item.name.isdigit()),
    key=lambda item: int(item.name),
):
    pid = int(entry.name)
    if pid in ancestor_pids:
        continue
    try:
        values = status_fields(pid)
        process_status = basic_status(values)
        ppid = int(process_status["ppid"])
        process_uid = int(process_status["uids"][1])
    except (FileNotFoundError, ProcessLookupError) as exc:
        if process_entry_present(pid):
            append_error(
                errors,
                pid=pid,
                stage="status",
                detail=f"{type(exc).__name__}: {exc}",
            )
        continue
    except Exception as exc:
        append_error(
            errors,
            pid=pid,
            stage="status",
            detail=f"{type(exc).__name__}: {exc}",
        )
        continue
    if process_uid != effective_uid:
        continue
    try:
        raw_argv = (entry / "cmdline").read_bytes()
    except (FileNotFoundError, ProcessLookupError) as exc:
        if process_entry_present(pid):
            append_error(
                errors,
                pid=pid,
                stage="argv",
                detail=f"{type(exc).__name__}: {exc}",
            )
        continue
    except Exception as exc:
        append_error(
            errors,
            pid=pid,
            stage="argv",
            detail=f"{type(exc).__name__}: {exc}",
        )
        continue
    if not raw_argv:
        if process_entry_present(pid):
            append_error(
                errors,
                pid=pid,
                stage="argv-empty",
                detail="cmdline was empty while the process entry remained present",
            )
        continue
    argv = [
        token.decode("utf-8", errors="surrogateescape")
        for token in raw_argv.split(b"\0")
        if token
    ]
    if not argv:
        if process_entry_present(pid):
            append_error(
                errors,
                pid=pid,
                stage="argv-empty",
                detail="decoded argv was empty while the process entry remained present",
            )
        continue
    candidate_signal = bool(
        values.get("Name") == "(sd-pam)"
        or raw_argv == b"(sd-pam)\0"
        or argv == ["(sd-pam)"]
    )
    outer_candidate_target: dict[str, object] | None = None
    if candidate_signal:
        try:
            outer_candidate_target = candidate_status(values)
        except Exception as exc:
            append_error(
                errors,
                pid=pid,
                stage="systemd-pam-outer-target",
                detail=f"{type(exc).__name__}: {exc}",
            )
    outer_starttime = (
        read_required_starttime(
            errors,
            pid=pid,
            stage="systemd-pam-outer-starttime",
        )
        if candidate_signal
        else None
    )
    outer_observation = (
        {
            "argv": argv,
            "raw_argv": raw_argv,
            "starttime": outer_starttime,
            "target": outer_candidate_target,
        }
        if (
            candidate_signal
            and outer_starttime is not None
            and outer_candidate_target is not None
        )
        else None
    )
    initial_snapshot = (
        read_candidate_snapshot(errors, pid=pid, label="initial")
        if candidate_signal
        else None
    )
    if candidate_signal:
        outer_changes = candidate_outer_changes(
            outer_observation,
            initial_snapshot,
        )
        if outer_changes:
            append_error(
                errors,
                pid=pid,
                stage="systemd-pam-outer-revalidation",
                detail=(
                    "outer candidate observation changed before the pinned "
                    f"initial snapshot: {','.join(outer_changes)}"
                ),
            )

    executable, executable_failure, executable_vanished = readlink_result(
        entry,
        pid=pid,
        stage="exe",
    )
    if executable_failure is not None:
        executable_failure["stage"] = "executable"
    if executable_vanished:
        if candidate_signal:
            append_error(
                errors,
                pid=pid,
                stage="systemd-pam-executable-disappearance",
                detail="candidate disappeared during executable read",
            )
        continue
    cwd, cwd_failure, cwd_vanished = readlink_result(
        entry,
        pid=pid,
        stage="cwd",
    )
    if cwd_vanished:
        for prior_failure in failures_before_cwd_disappearance(
            executable_failure,
            cwd_vanished=True,
        ):
            append_failure(errors, pid=pid, read_failure=prior_failure)
        if candidate_signal:
            append_error(
                errors,
                pid=pid,
                stage="systemd-pam-cwd-disappearance",
                detail="candidate disappeared during cwd read",
            )
        continue

    final_snapshot = (
        read_candidate_snapshot(errors, pid=pid, label="final")
        if candidate_signal
        else None
    )
    if initial_snapshot is not None and final_snapshot is not None:
        changed_fields = snapshot_changes(initial_snapshot, final_snapshot)
        if changed_fields:
            append_error(
                errors,
                pid=pid,
                stage="systemd-pam-revalidation",
                detail=f"candidate snapshot changed: {','.join(changed_fields)}",
            )
    if systemd_pam_exclusion(
        outer_observation=outer_observation,
        initial_snapshot=initial_snapshot,
        final_snapshot=final_snapshot,
        effective_uid=effective_uid,
        effective_gid=effective_gid,
        executable_failure=executable_failure,
        cwd_failure=cwd_failure,
    ):
        excluded_entries.append(
            {
                "class": "systemd-pam-session-helper",
                "cwd_denial": cwd_failure,
                "effective_gid": effective_gid,
                "effective_uid": effective_uid,
                "executable_denial": executable_failure,
                "final_snapshot": snapshot_receipt(final_snapshot or {}),
                "initial_snapshot": snapshot_receipt(initial_snapshot or {}),
                "outer_observation": candidate_outer_receipt(
                    outer_observation or {}
                ),
                "pid": pid,
            }
        )
        continue

    disposition = ordinary_disposition(
        candidate_signal=candidate_signal,
        final_snapshot=final_snapshot,
        outer_argv=argv,
        outer_ppid=ppid,
        executable=executable,
        cwd=cwd,
        executable_failure=executable_failure,
        cwd_failure=cwd_failure,
    )
    for read_failure in disposition["read_failures"]:
        append_failure(
            errors,
            pid=pid,
            read_failure=read_failure,
        )
    for disposition_error in disposition["errors"]:
        append_error(
            errors,
            pid=pid,
            stage="ordinary-disposition",
            detail=str(disposition_error),
        )
    authoritative_argv = disposition["argv"]
    authoritative_ppid = disposition["ppid"]
    for process_class in disposition["classes"]:
        matches.append(
            {
                "argv": authoritative_argv,
                "class": process_class,
                "cwd": cwd,
                "executable": executable,
                "pid": pid,
                "ppid": authoritative_ppid,
            }
        )

errors.sort(key=lambda item: (int(item["pid"]), str(item["stage"])))
excluded_entries.sort(
    key=lambda item: (int(item["pid"]), str(item["class"]))
)
matches.sort(key=lambda item: (int(item["pid"]), str(item["class"])))
print(
    json.dumps(
        {"errors": errors, "excluded": excluded_entries, "matches": matches},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
)
sys.exit(1 if errors or matches else 0)
```

The inspector/wrapper exclusion remains PID-based only and is computed before
enumeration. It may not exclude a process because its text resembles the
inspector, because it is a descendant of the wrapper, because it uses
Python/Node/shell generally, or because it owns no packet port. The sole
additional non-packet classification is the complete positive systemd-PAM
tuple above after both exact denials and identical starttime-pinned initial and
final snapshots; the pinned outer observation, both full snapshots, and both
denial records must appear in `excluded`. The outer candidate observation must also equal the pinned initial
generation and exact target/raw/decoded-argv values. Any initial or final
packet argv class preempts exclusion, and the shared ordinary-disposition
helper uses only final snapshot argv and target PPid for every candidate path.
It never falls back to outer candidate data. Every partial, reused, reparented,
disappeared, unavailable-final, or otherwise different record retains the
normal match/error result. A zero exit requires `errors`
and `matches` empty; `excluded` may contain only fully evidenced
`systemd-pam-session-helper` records. The independent port and UDS checks then
remain mandatory. An ambient process starting after the census is not adopted:
an ordinary port bind failure, UDS collision, readiness mismatch, or the
post-teardown invocation of this identical census freezes the attempt.

### 6.3 Required green evidence

Before launch, the labeled preflight census must exit zero with exactly one
compact JSON object, empty `errors` and `matches`, and only complete
`systemd-pam-session-helper` entries (if any) in `excluded`. The receipt must
retain each pinned outer candidate observation, identical starttime-pinned
initial/final tuple, and both errno-13 denial stages, and the embedded positive
plus negative controls must have
contributed no control error. Its stdout byte count and SHA-256 are retained as
the preflight census receipt. The controls must prove all eight stale-outer
final-change and pre-pin-reuse cases retain denied-read error and produce the
expected readable match from final argv/final PPid. Ancestor traversal must
positively report its PID 1 completion by producing no ancestor error.

The smoke must then exit zero without timeout and emit exactly one final JSON.
It must prove:

- one initial requirement and disabled New Match;
- exactly one successful character POST and one exact selected fixture card;
- zero remaining requirements, enabled New Match, and real sheet close;
- exact created-card/sole-roster ID equality and actual human controller;
- exact gateway game ID, owner durable session, and positive owner-controlled
  entity count from the inherited create handshake;
- initial owner hosted runtime helper/snapshot green;
- owner input helper/snapshot exact `my_turn_input` green;
- successful End Turn, positive cursor advancement, and no browser errors;
- reconnect durable session equality plus reconnect runtime helper/snapshot;
- pre-reload objective diagnostics connected with positive actual cursor;
- post-reconnect objective history helper/snapshot green at connected status
  and cursor recovery at least to the retained pre-reload cursor;
- both bounded structured presentation-diagnostics checkpoint receipts, with
  every actual presentation fault still fatal through the inherited error gate;
- restored nonempty completion/combat-log evidence, zero historical
  presentation backlog, snapped cursors, and rendered rows;
- observer exact game/access/zero-controlled-entity evidence plus observer
  runtime helper/snapshot;
- no malformed, null, contradictory, fabricated, or missing new/inherited
  receipt.

### 6.4 Teardown

On every exit:

1. allow smoke-owned page/context/browser `finally` first;
2. terminate/join only a still-active recorded smoke tree;
3. stop/join only the owned Vite tree;
4. request ordinary shutdown of the owned gateway and allow its lifespan to
   close the gateway service, all UDS workers/process groups, directory
   repository, and preview worker; if the recorded gateway tree remains past
   its bounded grace, terminate only that recorded tree;
5. prove all recorded PIDs and descendants absent;
6. prove ports 8000/5173 closed;
7. prove no owned Unix-domain worker socket/process remains, live or as a
   filesystem socket below the fresh root;
8. invoke the exact Section 6.2.1 stdin-only census a second and final time
   with label `post-teardown`, retain its compact stdout byte count/SHA-256,
   and require exit zero, one JSON object, empty `errors` and `matches`, only
   fully evidenced reviewed `systemd-pam-session-helper` exclusions, and all
   embedded controls green;
9. retain the complete fresh database/runtime/artifact root;
10. never touch WP-016, the consumed WP-017 root, or any earlier retained root.

The preflight and post-teardown census receipts must have distinct labels and
separately recorded byte/hash identities even when their JSON bytes happen to
match. No `ps`, `pgrep`, `grep`, joined-command-text process matcher, broad
wrapper exclusion, PID-specific exemption, or alternate final probe exists.
The second census is the sole packet-family final proof; the recorded PID,
port, and UDS proofs remain independently mandatory.

Any mismatch freezes without rerun, alternate probe, or cleanup expansion.

## 7. Gate B acceptance

Fresh R1-R4 must assess same-target red-to-green causality; actual fresh
fixture; resolved runtime and input observations; inherited hosted evidence;
objective history settlement with independent completion restoration;
structured presentation attribution with the fatal error gate intact;
gateway/worker/service ownership; both census receipts and resource-specific
cleanup; performance/contracts; and strict claim scope. Gate B closes only at
public 4/4 plus Coordinator verification.

## 8. Performance and architecture

The checker adds one constant read/regex. The smoke contains one bounded real
character creation, five sequential uses of one O(1) resolved poller (the four
accepted readiness uses plus one objective-history settlement), four accepted
readiness snapshots, two transcript snapshots carrying objective fields, and
two bounded structured presentation snapshots. At most one page evaluation and
timer are in flight per helper invocation. The census performs one bounded
same-euid `/proc` snapshot per invocation and runs exactly twice. No product
hot-path changes.

The governed run uses the existing gateway, SQLite directory, artifact store,
UDS worker pool, and Vite deployment shapes. It adds no service, worker,
schema, persistence policy, wire, SDK, public contract, dependency, package,
asset, serializer, renderer, or framework. Attempt-local environment values
select existing private deployment paths only.

## 9. Gate and owner matrix

| Stage | Owner | Authorized work |
|---|---|---|
| Historical source stages | Closed | Checker/red/correction/combined-static identities are frozen |
| Consumed attempts | Closed no retry | Reached evidence is bounded; no acceptance or permission carries |
| Revised Plan Gate A | R1-R4 | Review this complete exact plan and frozen baseline |
| Bounded Tester continuation | Tester | Edit only Sections 4.6-4.7 after fresh Gate A 4/4 and Coordinator verification |
| Combined static | R1-R4 | Review frozen checker plus exact revised hosted smoke before execution |
| Revised same-policy green | Tester | Section 6 once only after combined-static 4/4 and Coordinator verification |
| Gate B | R1-R4 | Review frozen evidence |

Coordinator verifies governance and casts no technical vote.

## 10. Mandatory Gate A questions

1. Does package.json directly register hosted-game smoke and include it in
   the hosted check?
2. Did the historical stale smoke contain exactly two selected Promise-valued
   call shapes, while the frozen corrected baseline contains zero and preserves
   exactly two synchronous `waitForFunction` calls?
3. Is the runtime shape invoked for initial owner, reconnect owner, and
   observer?
4. Does installed Playwright branch on each immediate Promise object?
5. Can eventual false complete without another poll?
6. Is owner input exact `my_turn_input`?
7. Is runtime readiness exactly hosted mode, non-null game, connected status,
   equal sessions, and positive entity count?
8. Do later End Turn/reconnect/observer checks fail to prove those named
   admission boundaries repolled?
9. Is the checker target-local and ordered after six current rules?
10. Does stale hosted source deterministically produce the sole exact
    diagnostic while ten deferred calls remain unscanned?
11. Is first red static and service-free?
12. Does ordinary page.evaluate return the resolved Boolean?
13. Does the helper own one absolute Node-monotonic deadline?
14. Do current-budget race, timer clearing, late truth, stall, repeated false,
    and no-post-expiry behavior fail closed?
15. Does runtime replacement preserve the first synchronous DOM/canvas wait
    and exact five-term predicate?
16. Do three independent runtime snapshots prove the same terms without
    adding a parallel readiness owner?
17. Does owner input replacement preserve exact state and independently
    re-read it before End Turn?
18. Are the current hosted character selectors absent from production?
19. Does fresh gateway identity create no persistent character by itself?
20. Do requirement1 and disabled New Match exclude ambient character state?
21. Is one real exact-path character POST used without body/DTO/interception/
    seed/store authority?
22. Do exact card/name/ID, requirement removal, enabled New Match, sheet close,
    and request count provide truthful receipts?
23. Does created card ID equal the sole roster ID and actual controller human?
24. Are all accepted and newly proposed output fields actual observations,
    with fixed input name independently proven?
25. Are hosted create/game/session/control, End Turn, cursor, reconnect,
    completion/combat-log/backlog/rendered, observer, error, JSON, and finally
    paths frozen outside Sections 4.6-4.7?
26. Do exactly checker and hosted smoke suffice?
27. Are focused tsc, the frozen checker, one preflight census, one registered
    hosted smoke, and one post-teardown census sufficient and discriminating?
28. Is the direct gateway command repository-owned, attempt-local, typed by
    capabilities, and ordinary-bind fail-closed?
29. Does the gateway lifespan own repository, preview, and all worker cleanup?
30. Is the 300-second smoke owner plus exclusive recorded-tree/process/port/UDS
    teardown enforceable, with the fresh root retained and prior roots
    protected?
31. Are five sequential O(1) helper uses, bounded transcript/presentation
    snapshots, and two bounded censuses sufficient, with product hot-path cost
    zero?
32. Are inventory3 and multi-character7—ten total—the deferred SELF/TARGET
    backlog, with sentinel assets separately open?
33. Does this packet refrain from restoring or retiring the human-scoped
    SELF/TARGET product contract?
34. Does the packet add no public contract, schema, persistence policy,
    dependency, framework, service, asset, serializer, or parallel authority?
35. Is the claim strictly BUG-031 Stage 7 resolved runtime/input/objective-
    history readiness evidence rather than character, hosted game, gateway,
    worker, End Turn, reconnect, observer, transcript, presentation,
    replication, or general product correctness?
36. Is there any concrete false-red, false-green, cleanup, artifact,
    concurrency, performance, scope, contract, or human-decision blocker?
37. Does the plan truthfully classify every consumed attempt as non-green,
    preserve only the readiness boundaries actually reached by the latest
    receipt, and carry no retry, acceptance, or prior execution permission?
38. Does the census receive its program only through standard input and avoid
    shell pipelines, broad joined-command searches, or process mutation?
39. Is the orchestration exclusion exactly the inspector PID and complete
    captured wrapper/ancestor chain with positive PID 1 completion and errors
    on premature PPid 0 or cycles, while the only process-class exclusion is
    the outer-bound, full starttime-pinned, twice-identical systemd-PAM tuple
    after both exact errno-13 denials, with no PID, name/argv/ancestor-only, generic
    unreadable, Python/Node/shell, or descendant exemption?
40. Does NUL-token argv inspection plus exact executable/cwd data prevent the
    inspector text from satisfying its own target predicates?
41. Do the exact hosted-smoke, gateway, hosted-worker, event-server,
    preview-worker, Vite, Playwright, and Chromium shapes cover every
    packet-owned process family
    without converting arbitrary text into process evidence?
42. Do unavailable captured ancestors, stable same-UID read failures, stable
    empty argv, incomplete/mutated tuple fields, single denials, different
    errnos/stages, generic unreadable records, a prior executable failure before
    cwd disappearance, incomplete ancestor traversal, generation change,
    outer-to-initial mismatch, failure to parse the complete live outer target,
    final-snapshot read/missing/change/reparenting,
    and every denied initial or final packet-family control all retain
    deterministic match/error disposition, while every readable stale-outer
    final-change and pre-pin-reuse packet control matches from the complete
    final snapshot argv/PPid and only confirmed vanished entries with no prior
    stable failure and different-UID processes are skipped?
43. Does the exact positive control alone produce the complete deterministic
    `systemd-pam-session-helper` receipt with the pinned outer observation,
    both generation-pinned snapshots, and both denials, does the shared
    live-shape control prove the identical parsed target has no change, does
    the shared candidate ordinary-disposition helper
    forbid stale fallback and use final snapshot values, and do deterministic
    errors, exclusions, matches, free-port proof, the separate UDS check,
    ordinary bind failure, and exclusive teardown remain mutually sufficient
    across the preflight/start race?
44. Are the checker and hosted smoke frozen as the exact Gate A baseline, with
    only the hosted Sections 4.6-4.7 edit releasable after approval and no human
    product decision?
45. Do source owners prove subjective runtime readiness and objective-
    diagnostics history settlement are distinct, with the immediate zero count
    attributable to missing Tester sequencing rather than gateway omission?
46. Does `readTranscriptState` add only exact production
    `objectiveDiagnosticsStatus` and `objectiveEventCursor` fields while
    preserving its existing fields and meanings?
47. Does the pre-reload checkpoint independently require connected objective
    diagnostics and a positive actual objective cursor before retaining the
    complete transcript snapshot?
48. Does the post-reconnect helper reuse the accepted absolute-deadline poller
    with exactly connected status plus cursor recovery to the retained cursor,
    followed by one independent transcript snapshot with the same assertions?
49. Does the inherited completion-restoration assertion remain outside the
    readiness predicate and fail to the production history/projection owner if
    settled status/cursor still lacks completions?
50. Does the presentation receipt use only the production
    `getPresentationDiagnosticsSnapshot` owner and return exactly the bounded
    serializable fields enumerated in Section 4.7 at the two frozen
    checkpoints?
51. Is structured presentation evidence observation-only, with no console-
    handle adoption, clear, filter, suppression, reconciliation, or admission
    authority, while the inherited browser-error gate remains unchanged and
    fatal?
52. Is the exact same stdin census invoked exactly twice with distinct labels
    and separately hashed receipts, once preflight and once after teardown,
    each requiring empty errors/matches and only fully evidenced reviewed
    systemd-PAM exclusions?
53. Does the post-teardown census replace every broad joined-command final
    matcher without weakening the independently mandatory recorded PID,
    descendant, port, and live/filesystem UDS proofs?
54. Is one final JSON emitted after browser `finally` on failure so every
    completed objective/presentation checkpoint remains reviewable without
    weakening failure aggregation or treating partial evidence as green?

Only unconditional approval on every answer contributes to Gate A.
