# Subjective server implementation

**Latest closure:** [warm worker reuse and server-phase readiness](WARM_WORKERS.md)
adds the private multi-game service lifetime without changing the player API/SDKs.
This supersedes earlier one-game-worker lifetime descriptions; independent games
still have isolated native worlds.

2026-10-07. Worktree based on `40eb37b9b4cac72ea75d00d7b1545a4e48a5d2a2`,
branch `feature/server-is-coming-back`. This report concerns the server and shared
player application. It does not claim to repair the Pygame renderer or deliver the
future NeuroClient UI/Studio. No new artwork, frontend, rule expansion or commits
were made for this phase.

## What changed

| Owner | Implemented change | Reason |
|---|---|---|
| `dnd/core/combat_log.py`, native log producers | Closed tagged payloads, original roll/modifier data, ordered multi-target child references | One truthful log model; remove duplicated per-target summary dictionaries |
| `dnd/subjective_combat_log.py` | One event-time authorization/redaction path; retained known names; finite omission rules | Witnessed effects survive unknown causes without leaking hidden identities, gear or destinations |
| Existing condition/item/spatial owners | Passive remaining-duration values and surviving-duration after-value events | Replay uses recorded state; clients do not invent timer ticks |
| `dnd/player/` | Moved the existing session, audience, capture, projection, reducer, recording and content composition out of `game/`; one application composition | The desktop, native server worker and headless replay use the same implementation, with no compatibility shim copies |
| `dnd/player/projection.py` | Public schema 4, nullable unknown causes, dense audience-local occurrences and admitted references, private duration/gear filtering | No raw history counters, hidden ancestor graph or private state in a player stream |
| `dnd/player/session.py` | General seat assignment, explicit observer grants, native admission, seat-local discovery generations, bounded preview retention, preview/execution route parity | Support grouped, per-entity and mixed AI control without server rules or a second pathfinder |
| `dnd/player/application.py` | Common initialization and operation capture; intermediate observed content retained; atomic public reducer updates | A descriptor observed and removed during one operation remains available for its recorded presentation |
| `dnd/player/compatibility.py`, `event_record.py` | Offline native archive upgrade to typed logs; original private grants retained; obsolete public formats require reprojection from the native archive | Old native captures replay without changing live protocol strictness, guessing missing public semantics or rerolling data |
| `player_server/` | Isolated native process, finite HTTP adapter, SSE, exact per-audience spool, attachment/ACK/receipt lifecycle, bounded delivery and failure cleanup | Transport owns delivery and authority binding; native owners retain gameplay |
| `sdk/python`, `sdk/player-typescript` | Independently installable async transports with generated declarations, common schema, cursor waits and awaited consumers | No engine dependency, client reducer, automatic command retry or animation wait in either SDK |
| `dnd/core/events.py`, capture/application | Native UUID position index and one current actor/contact capture checkpoint per audience | Remove repeated full-history reconstruction while retaining exact cold/historical results |
| `dnd/content_system/pack_loader.py` | Add the new index to its existing rollback inventory | Rejected cold imports cannot leave a stale event index |
| Existing value/ability/equipment/entity owners | Carry the existing registration opt-out through disposable calculations used by HP, passive-skill, HUD and stat reads | Reading a stat must not retain a fresh calculation graph in the native UUID registry; owned values retain the existing defaults and math |
| `dnd/controller.py`, `dnd/encounter.py` | Default passive `TurnContext` and `AdvanceResult` records to unregistered values, retaining explicit opt-in | Their callers consume returned data directly; retaining each snapshot in the identity registry leaked memory on every turn |
| `dnd/player/content_composition.py`, reduction/projection | Retain immutable admitted descriptors; update their table only on additions; map after-value boundaries backwards through existing occurrence order | Avoid copying unchanged content and scanning full history on each ordinary command; no additional cache or schema |
| `player_server/worker.py` process entry | Prepare the static protocol, collect and freeze the pre-game import graph once; keep ordinary runtime GC enabled | Avoid repeatedly scanning process-lifetime imported model/schema graphs. Orphaned frozen cycles may remain until the isolated single-game worker exits; startup and memory evidence include this policy |
| `dnd/entity.py`, `dnd/blocks/sensory.py`, `dnd/core/gridmap.py` | Reuse hazard checks per path cell; remove full-map hazard prechecks from local sensory refresh and avoid reconstructing tile/spatial mappings | Repeated missile damage and navigation should not repeatedly scan unaffected map state |
| `dnd/core/gridmap.py`, `dnd/core/aoe.py` | Connected spread reuses existing revision-invalidated directed-edge/cell queries; empty boundaries skip edge-record construction | Preserve original footprint and obstruction rules while sharing work across overlapping spell candidates |
| `dnd/core/values.py` | Skip absent factor products and multiplication by one | Preserve exact arithmetic while avoiding disposable Fraction work |
| `dnd/player/application.py`, `player_server/protocol.py` | Reduce initialization once; build all public schema roots in one Pydantic pass | Remove duplicate startup work without new models or changed schema |
| `dnd/player/session.py` | Reconstruct returned detached choices through existing typed field conversion instead of generic deep copying | Keep caller mutation isolated with less traversal; no new cache, schema or JSON round-trip |
| `sdk/python` | Compile the unchanged schema using pinned `jsonschema-rs`; retain strict JSON/format/counter checks | Remove interpreted validation cost on large choices responses; Windows native wheel installed |
| `dnd/core/base_actions.py`, `dnd/core/base_conditions.py` | Defer only action/condition Pydantic schema compilation using the existing model configuration | Avoid eager compilation of unused behaviors; retain one native type, static imports and unchanged validation/public schema; measure first-use and runtime GC separately |
| Existing `game/`, tests and review tools | Import updates and nullable-root/typed-log consumers | Preserve consumers of the extracted shared path; no rendering feature redesign |

`game/runtime_worker.py` uses the same application capture/reduction. The headless
Python acceptance client uses `dnd/player/reduction.py`; “correctness oracle” does
not mean an alternative implementation. The old omniserver is not imported by the
new server. Its old combat-log projector is reduced to the common native adapter.

The new server's public schema contains 19 roots, 312 shared definitions and 1,612
object fields. The original design overlay generators were removed. Current JSON
Schema, HTTP documentation, owner inventory and package declarations come from the
production owners via `devtools/export_player_protocol.py`. The older labelled
planning captures remain historical evidence only.

The final standalone package checks pass **42 Python and 24 TypeScript SDK
tests**. Built wheel/tarball contents each contain eight files, excluding tests
and engine code. These packages were installed outside the repository's engine
environment; the Python SDK also ran on native Windows. The internal performance
repairs require no protocol or SDK regeneration.

## Approved first startup follow-up

The bounded plan §14 is implemented and independently accepted by both source
reviewers. **212 existing tests** pass, and all **8,623 records / 50 subjective
prefixes** from the 25 fresh host/worker cohorts cold-replay after shutdown.
Ten starts per platform reduce human-ready mean **3.92→2.76s on Windows** and
**6.27→5.00s on WSL**, with explicit maxima, SDK-consumed boundaries and first-use
spell costs in the [performance receipt](PERFORMANCE.md#approved-first-startup-fix--behavior-schema-deferral).
The ordinary 1,000-command consumed p95/max is **37.50/56.91 ms**; separate GC
instrumentation preserves enabled collection, post-Start collectibility and flat
native registries. This changes only the two existing behavior-root model
configurations. No new model family, loader, SDK build or frontend work is added.
WSL startup variation and broader engine workloads remain open.

## Actual gameplay and replay

The independently installed Python and TypeScript SDKs played opposing sides of
the same native encounter. Completed configurations:

| Configuration | Seats | Result |
|---|---:|---|
| One controller per side | 2 | Terminal; repeated with language assignments swapped |
| One controller per unit | 4 | Terminal; repeated with language assignments swapped |
| Human group versus AI | 1 | Terminal |
| AI versus human group | 1 | Terminal |
| Both sides mixing human and AI actors | 2 | Terminal |

The final seven runs produced **16 independently authorized streams and 728 exact
records**. Each was cold-reduced after the native process shut down, validating
schema, identity, contiguous cursor order, causal-reference closure, private HUD
ownership, command numbering and native terminal facts. Grouped language swaps
agree on final visible HP/deaths. Earlier failed probe runs are superseded, not
counted as successful evidence.

The real Lantern Crypt additionally completed **36 SDK commands, 56 records and
13 authored exploration steps** in 20.75 seconds. The party opened and looted both
chests, crossed the damaging trap (37→29 HP), drank a healing potion (29→36 HP),
operated the trap lever, opened both passage doors and fought the goblins to a
native terminal result. Both heroes acted through native discovery/preview.
The saved stream includes nine spell applications, including six later ordered
applications. Cold replay passes with exact world-object placements and log data.

The performance follow-up adds eight finite real-combat games with **197 commands / 601 records**, and three final affected spell reruns with **70 commands / 215 records**. The native Windows server also completes a separate **47-command / 110-record** fight with both SDKs in WSL. These use actual commands and authorized streams. See [SDK_REVIEW.md](SDK_REVIEW.md) and [PERFORMANCE.md](PERFORMANCE.md) for exact preconditions, performance stages and evidence limits; repeated queries never stand in for actual casts.

The separate fact corpus runs 13 existing native scenarios and **all 28 concrete
exported fact variants** through production projection, the public schema, JSON
round-trip and the shared cold reducer. It includes damage's request/result
variants, saving throws, conditions, spatial effects, item effects/charges,
equipment, death saves, summons/faction changes, forced movement, object
damage/destruction, mechanisms and portals. All observed families are recorded;
none are silently omitted. This is broad serialization/replay evidence, not a
claim to manually play every spell or animation.

## Verification map

This map connects the plan's cases to concrete behavior checks. Related cases are
grouped to avoid a second test implementation for each checklist row.

| Plan cases | Evidence |
|---|---|
| H01–H04 | Real worker launch in all SDK matches/crypt; pure import checks; bootstrap and public cold replay; startup failure transport regression |
| H05–H06, H25–H26, H37 | Transport admission tests; session/selection tests; strict target/coordinate tests; per-seat discovery-generation regression |
| H07–H10 | Existing `test_player_selection_contract.py`; crypt repeated spell applications; all-fact/native fixture corpus; preview purity and direct native invalid-submit tests |
| H11–H15 | Crypt doors/trap/lever journey; native safe-route preview/execution equality; existing party audience, session and window-selection tests |
| H16–H18 | Equipment preflight and native equipment/item-duration tests; original item archives; eventless handler update/replay regression |
| H19 | Existing lethal-opportunity/doorway history tests; retained event-time names and no hidden destination refresh; death/retirement capture parity |
| H20–H22 | Typed log tests; native fixture corpus; immunity cancellation causality; condition/spatial-duration tests; canceled-parent completed-child retention |
| H23–H24, H27–H29, H47, H50 | Explicit identical retries in both live drivers; command conflict/reservation tests; attachment retry/replacement and ACK bounds; lost reply/ACK SDK tests |
| H30–H34, H52, H56 | Held/canceled query sends and delivery credit; terminal drain/expiry; missing/truncated history; queued-query shutdown; second-audience spool failure leaves no partial publication |
| H35–H36, H48 | Bounded preview cache; wholly hidden area change produces no public operation; hidden log/condition/content regressions; private inventory checks across every recorded seat |
| H38, H41–H46 | Independent SDK package tests: malformed/split SSE, Unicode, safe integers, wrong identities, gaps/duplicates, unknown versions, canceled/failed consumers, bounded cursor waits and final-prefix draining |
| H39–H40 | Complete public crypt and all-28-fact corpus described above |
| H49 | Authenticated HTTP/SSE, CORS allow/refuse and rejected credentialed redirects pass. Native Windows server bound to its WSL adapter completes a 47-command fight with Python and TypeScript clients in WSL; both reach terminal, 110 records. No firewall changes. |
| H51, H53–H55 | Seven opposing-language/group/per-entity/mixed runs; every final stream cold-replayed; invalid overlapping/missing/AI ownership rejected before native materialization |

## Review and retained limitations

The [anti-slop review](ANTISLOP_REVIEW.md) and [independent ECS/DAG review](ECS_REVIEW.md)
record their findings, fixes and approval scopes. The capture optimization has
hot/cold equality checks, historical-overlap and generation-reset checks, an actual
cold-pack rollback regression and a canceled-child regression. No native→player,
renderer→server cycle or old omniserver dependency was added.

The performance follow-up passes **83 player/transport/HUD/party/resolution
checks**, **49 existing value/equipment cases**, six scalar-allocation regressions,
and four passive-record/encounter-boundary cases. The original scoped type check
is clean. Extending it to `dnd/encounter.py` exposes one unchanged optional-entity
access warning in the starting source; it is not represented as a newly clean
repository-wide type check. The performance report separates the leak fixes from
the later pre-game GC policy and records the actual latency of each candidate.

The broader engine run reached 638 passing cases and exposed seven failures before
it was stopped in a costly later case. Six typed-log fixture expectations were
updated; all 62 tests in those affected files then passed. The remaining door
reach failure reproduces at the starting commit. A broad graphics run exposed
42 opaque-wall/cloud expectations; a representative failure also reproduces at
the starting commit. Those graphics expectations are outside this server phase.
Old manual omniserver tests also have a pre-existing import of removed
`dnd.core.senses`; this was not repaired by reviving the old architecture. These
limits are why this report does **not** claim a green repository-wide suite.

Public schema versions before 4 are rejected with instructions to reproject the
preserved native recording. Private native archive compatibility remains available.
This avoids inventing missing subjective ordering/grants when reading an obsolete
public export. The cold-import rollback test runs in a fresh process so an earlier
test's retained dice registry cannot conceal or fabricate a failed rollback.

Performance measurements, targets and remaining measured costs are reported in
[PERFORMANCE.md](PERFORMANCE.md). The final ordinary-End-Turn cohort covers 1,000
commands: consumed p95 **62.45 ms**, maximum **109.08 ms**, native command maximum
**52.43 ms**. The original 200-command result had a 316.37 ms consumed maximum;
the intermediate leak-only 1,000-command run still hit 335.88 ms. The final policy
probe keeps both native registries flat, reclaims new runtime cycles and observes
a 43.57 ms runtime full-GC collection. This establishes improvement for the stated
workload, not a bound for every spell or map. The new event position index grows deliberately
with retained history. The server provides same-process session replay/reconnect,
not durable whole-world save/load across restarts. Lobby/account services, network
deployment and NeuroClient integration remain separate work.

The final affected combat replay passes **215 records across six streams**; the Windows-to-WSL SDK match adds **110 records across two streams**, all with terminal public state and closed/private references. The anti-slop and ECS reviews approve the spatial and detachment repairs; the SDK strictness repair has independent source approval. Relevant follow-up cohorts pass 17 session/selection tests, 42 SDK tests, 55 hazard-owner tests, 64 visible-hazard cases and the documented spatial 91-case plus 38-case checks. These cohorts overlap and are not summed into a unique-test claim.

Complete same-fixture startup, ten fresh hosts per platform: Windows human-ready mean **3.92s**, maximum **4.05s**; WSL mean **6.27s**, maximum **6.76s**. Windows meets the five-second target. WSL's five-second target remains missed. All fit ten seconds and shut down cleanly. The backend/SDK implementation and scoped performance repairs are delivered; this does not assert every Gate B budget for every environment/workload. Dense-spell and native-AI evidence is finite rather than a 100-sample p95, and largest-map scaling remains unmeasured.

## Reproduce and launch

See [player_server/README.md](../../../player_server/README.md) for configuration,
headers, receipts, limits and SDK usage. Start locally with:

```sh
uv run --no-sync python -m player_server --port 8790
```

Large/private evidence remains outside Git under:

- `.runtime/server-implementation-20261007/gameplay-final/` and its cold-replay JSON;
- `.runtime/server-implementation-20261007/crypt-v5/` and its cold-replay JSON;
- `.runtime/server-implementation-20261007/fact-corpus-accepted/`;
- `.runtime/server-recovery/` for profiles, per-operation timing and environment/source fingerprints.
