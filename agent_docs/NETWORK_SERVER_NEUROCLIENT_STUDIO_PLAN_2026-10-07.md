# Network server, NeuroClient and production Studio

2026-10-07. **Design for human discussion; no migration implementation authorized by this document alone.**
The human requests a deep plan after reconsidering the pygame/OpenGL migration.
This plan replaces that destination with a direct PixiJS client. Existing engine
fixes, accepted content, all P01–P31 complaints and earlier UI requirements survive.
The native repository may remain on its present mount and run on Windows. Moving
it to a Linux filesystem is not a prerequisite. Frontend development lives in WSL.

**Latest scope: server first, independently of this client plan.** The
[practical server-only plan](SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md)
now elaborates and governs §§4–6 where more specific. It closes server shape and
headless correctness before engine-speed iteration. Its finite API/status/admission
and revision details supersede this high-level outline. Frontend/UI/Studio work is
outside that current phase; none is a prerequisite for testing the server.

## 1. Decisions and scope

- New small network host, independent of `server/event_server.py` and its SDK.
- Existing Python engine owns gameplay; preserve its functional/ECS systems.
- Current player capture/projection and native command boundary are the starting
  point, subject to the concrete corrections below. Do not put the pipe protocol
  on a network unchanged or copy the old HTTP server into a new directory.
- PixiJS 8 with WebGL2 for the world. NeuroClient UI is a more advanced reference
  than pygame but lacks required features; the human has not approved wholesale
  reuse. Assess each component against current requirements before retaining,
  adapting or replacing it. WebGPU is not a parallel first implementation.
  Runtime WebGL2 capability is checked.
- TypeScript owns one production presentation compiler, retained state, sampler
  and renderer, shared by live play, replay and Studio. Python is a temporary
  comparison oracle, not a second deployed animation service.
- Preserve the original NeuroClient checkout as reference. New frontend entry
  point has no import dependency on its old store, SDK, mapper, FSM or clip queue.
- Studio edits the actual authored documents and previews through the same
  client renderer. Spell, action, rig, condition and world presentation are covered.
- Keep selected source FPS (mostly 32), accepted pixels, banks and registration.
  Packing/readiness and the separate too-fast playback audit remain mandatory.
- No new spells, rule expansion, narrative renderer, account platform, lobby,
  AI provider control plane, distributed worker scheduler or general plugin engine.
- First playable scope remains the authored crypt with Fighter/Sorcerer as one
  controlling party. Network contracts account for ownership and reconnect; this
  phase does not claim finished simultaneous multi-party multiplayer or save/load.

## 2. Evidence and preserved baseline

Engine source is on `codex/recovery-design` with pre-existing uncommitted recovery
work. Preserve that entire state. NeuroClient reference is
`/home/tommaso/Dev/NeuroClient`, branch `maybecursed`, commit
`d274f2d62ca9c1c5ed62a77841cacf6cc0347491`; its status was clean during this study.

Current reproducible coverage:

- [Module ledger](audits/neuroclient-server-20261007/module-port-ledger.md): all
  162 current Python game modules assigned a proposed responsibility.
- [Function ledger](audits/neuroclient-server-20261007/function-port-ledger.csv):
  959 declared functions/methods with source lines and proposed owner.
- [Source inventory](audits/neuroclient-server-20261007/source-inventory.json):
  hashes, imports, record fields, all 53 AnimationData fields, 50 player record
  declarations and 256 authored JSON files. Nested helpers are part of their
  containing function; a row is not a demand to translate the function verbatim.
- [Selected identities](audits/neuroclient-server-20261007/selected-content-index.json):
  effective catalog keys, including aliases and shared assets, not invented counts
  of distinct spells. Generated without decoding media pixels.
- [Authoring ownership](NEUROCLIENT_AUTHORING_COVERAGE_2026-10-07.md): every one of
  the 53 fields, the separate 15-field world catalog, world bindings and UI sources.
- [Earlier semantic coverage](audits/FULL_PRESENTATION_COVERAGE_2026-10-05.md)
  supplies domain cases. Its narrative section is superseded by the human's
  removal; historical counts are not substituted for the current inventory.

These inventories establish source coverage, **not** correctness, visual approval
or completed porting. Reviewers must challenge behavior as well as the list.

Measured recovery evidence separates a roughly 430 ms Fireball drawing frame,
65 ms sample preparation and 177–223 ms native operation. Four decoded Fireball
impact banks occupy 3,567,450,592 bytes before other scene assets. Exact zero-border
cropping only saved about 19%. Browser migration does not solve these inputs by
itself. The previous GPU proof covered isolated operations, not a whole game.

Specific source issues influencing this design:

| Current source | Consequence |
|---|---|
| `game/session.py`, `dnd/runtime_reset.py` reset global registries/map | One isolated engine process per active game; never several games or Studio mechanics scenarios in one interpreter |
| `game/runtime_worker.py` captures each operation before another mutation | Preserve this ordering; a successful mutation with failed capture is not a safe rejection/retry |
| Same worker imports `game.controls.selection_target_pool` | Extract neutral target-selection resolution; server must not import UI controls |
| Pipe Start includes test seed/positions; caller issues Advance/Close; EOF destroys session | New public protocol must not expose this trusted-parent lifecycle |
| Single native discovery cache per session | First phase has one controlling seat/tab; reconnect replaces connection without creating a second competing discovery owner |
| `server/event_server.py` computes AoE and filters targets itself | Do not reuse; native preview is the only mechanical preview owner |
| `game/presentation.py: capture_lineages` scans retained event history | Profile and bound incremental capture costs; moving transport does not fix growth |
| `PlayerSequence` is version 3; exporter filename says v2 | Export actual schemas/versions; do not freeze the stale filename into the new API |
| Current DrawCommand contains Surface/NumPy values | It is not a portable packet; move the rendering boundary before rasterization |
| Original Studio has old SDK frames, fixed 15-frame assumptions, 30 FPS seek | Recover controls, replace execution/timeline calculations |

## 3. Responsibilities: what the new server is allowed to do

| Owner | Owns | Must not own |
|---|---|---|
| Native rules (`dnd/`) | Actions, costs, pathfinding, targeting, combat, AI decisions, turn boundaries, conditions, senses, items, spatial interactions | HTTP, browser state, pixels, media readiness, animation duration |
| Engine player application boundary | Session composition, exact retained discovery templates, executing native APIs, immediate capture, audience projection, detached character/resources/log values | Reimplementing costs/LOS/AoE/factions, sprite authoring, camera state |
| Network host | Session process lifetime, authenticated control binding, serialized request admission, replies, delivery sequence/reconnect, bounded buffers and diagnostics | Per-spell endpoints, direct Entity lookup for gameplay, alternate AI loop, authoring writes, native state reconstructed from UI |
| Client state/presentation | Public reduction, causal binding, historical displayed state, typed recipe compilation, clocks/lifetimes, local picking, UI | Deciding damage/save/target legality or reconstructing hidden actors |
| Pixi/GPU adapter | Resource upload/residency, draw operators, palette/material operations, depth/blend/physical cuts, frame presentation | Native event dispatch or spell-specific rule branches |
| Authoring tool process | Read/write allowed source documents, validation/export, asset manifest serving and recorded fixture tooling | Editing a running game's mechanics or becoming the production game server |

The player application boundary is part of the engine-facing package, extracted
from the useful current functions. It is not a new rules layer. Calling existing
native APIs to evaluate a sheet or project an outcome is legitimate composition;
duplicating those APIs' logic in endpoint code is not.

## 4. Concrete backend structure and import direction

Proposed paths (implementation may combine small adjacent files, not multiply them):

```text
dnd/player/
  facts.py, commands.py, audience.py, content.py   passive player contracts
  session.py                                    current native session operations
  selection.py                                  retained row/prefix resolution
  capture.py, projection.py                      existing recorded-fact projection
  actor_facts.py, actor_projection.py             private capture helpers
  reduction.py                                  public value reduction for projection/tests
  recorded.py, compatibility.py                  private replay and boundary upgrades

player_server/
  app.py, protocol.py                            thin HTTP/SSE endpoints + envelopes
  host.py                                       process/seat lifetime + serialized admission
  worker.py                                     engine application execution/capture
  delivery.py                                   bounded ordered envelopes/command receipts
  __main__.py                                   explicit CLI composition/configuration

devtools/studio_server.py                        separate local authoring-only service
```

`dnd/player` is a higher-level application package: domain systems never import
it; it may import native types/functions. Contracts remain passive leaves.
Do not mechanically move all `game/` into `dnd/`. `game.player_facts`, session,
capture/projection, audience and their actual closure are the bounded extraction.
Split current `game.player_projection` offline `RecordedSequence` conversion from
hot operation projection if needed to avoid import cycles. Keep private diagnostic
records separate from wire types. Current UIContentManifest becomes passive content
metadata; artwork validation/selection remains client/tooling work.

Transport depends on the application boundary, which depends on native systems.
Native systems import neither transport nor client. No `server.event_server`, old
replication subsystem, pygame, NumPy raster work or media loader is reachable from
the new network startup. Audit the transitive imports, not only direct imports.
Preserve shared passive native enums/types where suitable; no duplicate DamageType
or condition definitions just for serialization.

During extraction update the temporary pygame caller to the extracted functions;
do not leave two independently edited copies. Python rendering remains only a
reference until frontend coverage closes. New server never imports that reference.

## 5. Public API and session lifecycle

### 5.1 Transport choice

Use FastAPI for a small HTTP command/query API and **one SSE event stream per
audience**. It matches turn-based commands and ordered server updates, and avoids
designing an additional WebSocket RPC framework. This choice does not reuse old
server orchestration. Native work runs in the isolated worker; an `async def`
endpoint does not execute blocking engine work on its networking loop.

The WSL Vite dev server proxies `/api`, `/media` and local `/studio-api` to configured
origins. Browser requests are relative; no Windows/WSL filesystem paths cross the
API. The backend can run natively on Windows at the existing checkout. Browser
rendering is on Windows. TLS/reverse-proxy deployment can later preserve this API.

### 5.2 Finite endpoint set

| Endpoint | Input | Output/authority |
|---|---|---|
| `GET /api/v1/bootstrap` | authenticated controlling seat | Protocol/schema versions, fixed game identity/epoch, audience, content/media revision references, resume metadata |
| `POST /api/v1/games/{id}/attachment` | seat credential; explicit attach/replace | New writable attachment epoch, next monotonic command number, pending command identities; admitted work survives replacement |
| `GET /api/v1/games/{id}/initialization` | bound seat | Retained authorized initialization and sequence zero; never raw objective scene |
| `GET /api/v1/games/{id}/events?after=...` | epoch + explicit application-owned last reduced sequence | Ordered complete operation envelopes, heartbeat or explicit resume-unavailable; query position is authoritative, never browser Last-Event-ID |
| `POST /api/v1/games/{id}/ack` | attachment epoch + greatest contiguous safely reduced/retained sequence | Release live-delivery credit; never claims animation completion |
| `POST /api/v1/games/{id}/choices` | actor, mode such as force-attack, correlation ID | Detached native choices, discovery generation, state revision |
| `POST /api/v1/games/{id}/preview` | actor/discovery/revision + exact ordered selection prefix | Native route/AoE/cost/next-selection/confirmation result with exact request echo |
| `POST /api/v1/games/{id}/commands` | command identity + revision + finite intent | Recorded acceptance/rejection and operation sequence reference; operation stream owns state application |
| `GET /api/v1/games/{id}/commands/{id}` | bound seat + command identity | Pending, completed/rejected, expired or explicit unknown outcome |
| `GET /media/{release}/{path}` | immutable installed manifest resource | Static binary/JSON; no game worker, no export-on-request |

No route per spell, item, attack or native event class. Intent union initially
contains execute-selection, end-turn, equip, unequip and toggle-reaction-handler.
Execute-selection preserves ordered target indices, repeated targets and ordered
positions. Upcast/form/material/weapon choices resolve existing native choices;
the client sends no damage formula, executable template or client-authored geometry.

Start/close/test-seed/map setup are host CLI or private test tooling operations.
Bootstrap attaches to a preconfigured authored encounter. A production browser
cannot reset the map, choose observers arbitrarily, advance the enemy or reset dice.

Local host creates a random seat credential. Dev proxy forwards configured host
credentials without hardcoding them in public bundles; a browser session uses an
HttpOnly same-origin cookie and validated Origin for mutations. Restrict allowed
origins, body sizes and tool roots; no credentials in URL queries/logs. This is a
bounded local development binding, not an account/login platform. Public deployment
requires its own access provisioning before exposure beyond the intended user.

### 5.3 Versioned data, not two competing state feeds

Generate TypeScript types and runtime validators from the actual finite public
schema; test Python-produced JSON in TypeScript. Use a discriminator for every
sum type. Protocol version, player schema, presentation schema and media revision
are distinct. Reject mismatches clearly instead of silently taking old SDK shapes.
Generated structural validation is supplemented by the inventoried pure semantic
validators and shared accepted/rejected fixtures described in the authoring companion.
Python's cross-field model validators do not automatically become JSON Schema rules.

An operation envelope contains:

```text
gameEpoch, audienceId, sequence, resultingStateRevision,
commandId? (only if authorized for this viewer),
lineages[], hud?, combatLogAppends[], nativeBoundaryStatus
```

Retain actual native causal/version identities inside admitted facts. An operation
with no visible lineage may still carry resources, boundary status or log facts;
do not drop it. Do not broadcast entirely private native operations to other
audiences merely to expose their count. Delivery sequence counts published
envelopes, not EventQueue rows. Public contract/privacy audit covers nested names,
condition/item details, geometry and diagnostic fields, not only actor IDs.

Wire data contains semantic observed changes and authored content references,
never per-frame draw commands, Surface/NumPy values, native templates, private
RecordedSequence/CompletedLineage or full objective event queues. Authoring catalog
and media are downloaded by revision independently of the operation stream.

### 5.4 Command execution, retries and errors

One controlling seat and one active writable browser tab initially. A new attachment
replaces the old connection's right to submit new commands; already admitted work
finishes. This avoids the current single discovery cache being invalidated by two
tabs. Game/seat state outlives a network socket. Other-party discovery/control is
not accidentally promised by this phase.

The server issues a writable attachment epoch, distinct from the shared cookie.
Choices, preview, ACK and new commands carry it; stale attachments cannot mutate
the discovery cache or admit work. A transient stream reconnect retains the same
epoch. A page reload attaches/replaces and receives the next command number and
pending identities. The host serializes replacement against admissions; it does
not cancel an already executing command. Receipt lookup remains seat-authorized
and returns the result of that seat's earlier command across attachment replacement.

Command identity is `(gameEpoch, seatId, monotonicCommandNumber)`. Authenticate
the seat/game first, then look up identity and exact payload before current action
revision checks. Existing pending/completed/rejected identities return their status;
a changed payload conflicts. Only a new identity checks the writable attachment,
expected next number, actor authority and current retained discovery/revision.

For a new valid mutation: reserve identity and exact payload -> execute through native APIs -> capture
all roots and projected HUD/log values -> append one immutable operation envelope ->
store terminal command receipt -> reply/publish. No subsequent mutation can run
between execution and capture. Expected rejection is valid only before mutation;
an exception after native mutation fails the session visibly with diagnostic IDs.
Never turn it into a successful empty operation or automatically retry it.

Same command ID and identical payload returns the retained receipt without spending
again. Same ID/different payload conflicts. Expired receipt IDs cannot become new
commands: retain a monotonic per-seat command watermark and reject old IDs whose
details were evicted. On timeout the client asks command status or retransmits the
same identity; it never invents a new ID as an automatic retry. No promise of
exactly-once execution across a server process crash without durable transactions.

Initial limits are explicit configuration: one in-flight mutation; coalesced unsent
preview per seat; bounded incoming requests; retained receipts and operation buffers
limited by bytes as well as entries. First protocol sends whole atomic SSE operation
envelopes, with a 64 MiB decoded-envelope ceiling matching the current pipe ceiling;
S0/S1 must prove every selected scenario fits and measure browser parse/reduction
latency. No fragmentation framework is planned. A post-commit oversize result fails
the session visibly and retains diagnostic data; never send a partial operation or
claim success. Revise the explicit cap/representation before release if a real case
exceeds it. Metadata/command requests have a separate much smaller measured cap.

### 5.5 Reconnect, history and memory

Network receipt/reduction, displayed cursor and native revision are different.
Discard duplicate envelopes before public reduction; detect gaps/epoch changes.
SSE reconnect resumes from the last fully reduced sequence, not browser delivery
state or the last animation shown. On transport error the client closes EventSource
and opens a new one with explicit `after=lastReduced`; that query overrides any
Last-Event-ID header. Browser last-event ID advances before handler completion and
is not an acknowledgment. Validate and apply each envelope atomically/in order.
Validation/reduction failure stops playback/input and reports the failing sequence;
never acknowledge it, skip it or enter an automatic retry loop over broken data.

Keep three memory/storage classes separate:

- A byte-bounded live delivery window, released by ACK of the greatest contiguous
  envelope successfully validated/reduced and retained in the client's bounded
  playback history. ACK does not discard history still needed for animation.
- A record-once per-audience spool of the exact published initialization/envelopes,
  outside public Git, with a configured total byte/age budget. This is the existing
  public-recording responsibility adapted to incremental output, not another native
  event executor or alternate world state. It permits full page refresh to replay
  from initialization without keeping the whole delivery history in host RAM.
- Native EventQueue/recorded history, reported separately from working memory.
  This migration does not promise constant native retained-history size.

The live window reserves room for one maximum operation before admitting another
native decision. ACK frees that credit and resumes scheduling. Disconnect/slow
consumer pauses scheduling once the window is full, at a native decision boundary.
Client history also has a byte budget; it stops acknowledging additional envelopes
before exhausting that budget rather than accumulating an unlimited animation queue.
Choose and record window/spool/client-history limits from the full encounter cases
in S0/S1. The spool budget must cover the acceptance encounter and resume tests.

A connected client retains pending historical playback across reconnect. A new
page rebuilds known state from retained public initialization/envelopes, then samples
the selected replay position; never inspect the objective world. Spool expiry means
explicit `resume-unavailable`, not an invented checkpoint or partial replay. No
checkpoint/fragmentation/save-game subsystem is added in this phase. Before total
spool quota is exhausted, stop native scheduling with a clear capacity diagnostic;
retain the existing record. ACK resolves live-window pressure, not disk-quota pressure.
Durable restoration of running mechanics after host failure remains out of scope.

At encounter end preserve pending operation records until clients can finish or
reconnect under the retention policy. Explicit host close ends the worker; tab
refresh or stream EOF does not. Worker failure reports session failure and prevents
further commands. Host restart is not advertised as a saved-game resume.

### 5.6 Native scheduling and asynchronous presentation

The host calls the existing native `advance_one_controller_action_boundary`, one
decision at a time, until a human input/terminal boundary. It yields between decisions
to service networking and publish each completed operation. Native controller owns
who acts and whether a zero-HP actor has a decision. No duplicate server turn loop.

This intentionally removes the current pygame loop's one-operation visual-lookahead
throttle. Rendering/media completion is never a rules prerequisite. Bound generated
backlog by unacknowledged delivery bytes/operations; stop scheduling at a native boundary when the
live-delivery budget is exhausted and resume when ACK releases credit, without
discarding history. A paused client can keep
receiving within its budget. There is no unbounded AI simulation while nobody can
consume it. Network acknowledgments do not mean animation completion.

Preview/discovery reads share the worker's serialized native state. Coalesce obsolete
hover requests before execution. Never cancel or reorder admitted mutations. Echo
actor, discovery, action, target/position prefix and correlation ID in every preview;
ignore late replies. Camera/pan/zoom/ordinary hover rendering remains entirely local.

## 6. Backend performance is its own deliverable

Profile startup/import/bootstrap, discovery, route/AoE preview, action execution,
AI decision, capture, audience projection, JSON encoding and bytes separately.
The present all-history capture scan must receive an incremental range/index design
inside its existing event/capture owners if measurement confirms growth; preserve
reaction links and version history. Do not introduce another event journal/dispatcher.

Every native fix in the prior recovery remains tracked. Compare Windows-native
and WSL-on-mounted-repo results as configurations, not different game semantics.
Check 15 minutes/100 operations for latency and retained-memory growth. An async
HTTP endpoint with blocking native computation does not satisfy this requirement.

Target budgets carried forward: warm ordinary engine-to-public-reply operations
p95 <=250 ms/max500 ms; Fireball p95 <=1 s/max2 s; ordinary AI p95 <=500 ms/max1 s;
warm preview p95 <=100 ms. Report execution versus capture/transport separately.
These are acceptance targets, not existing measured guarantees. GPU speed cannot
be used as evidence that these budgets pass.

## 7. New NeuroClient checkout and source organization

Preserve `/home/tommaso/Dev/NeuroClient` as the readable reference. Before implementation,
record its commit/status and separately preserve needed ignored/untracked authoring
files and art-manifest provenance; a Git tag alone does not preserve ignored assets.
Create a separate WSL checkout/clone on `codex/network-client-recovery`. Do not reset
the reference. Keep large private art in its current repositories, served via URLs.

New application root uses one Vite/TypeScript build and two shells (`play`, `studio`).
No dependency on the old main.ts or legacy SDK. Pin the validated Pixi version;
do not import the old dependency tree wholesale or retain its absolute SDK link.

```text
src/contracts/       generated player + authored data types and validators
src/state/           public reducer, causal index, known/displayed state
src/presentation/    binding, compilation, timeline, retained lifetimes, sampling
src/render/          typed draw records, projection, composition, picking
src/render/pixi/     concrete resource and draw adapter + finite shader operators
src/media/           manifest resolution, byte-bounded decode/readiness ownership
src/ui/              requirement-led browser views, passive inputs/intents
src/studio/          document editing, compiled timeline, fixture selection
src/network/         finite API, receive sequence, command/reconnect handling
src/app/             live and Studio composition roots, disposal/configuration
```

Imports flow contracts -> pure state/presentation -> render records -> Pixi adapter
-> application shells. UI sends passive intents; network imports no renderer.
Studio editing imports authoring contracts and production compilation, never live
game state as a mutable singleton. Pixi objects/classes are library resources, not
new behavior-rich domain entities. No custom actor class hierarchy, service locator,
event bus, generic dependency injector or runtime-loaded plugin registry.

### 7.1 NeuroClient UI reference and incomplete feature coverage

The human's correction is exact: NeuroClient UI was better than pygame, but lacked
many features. This is not approval to reuse it wholesale, nor a claim that replacing
icons/portraits completes the UI. Updated icon/portrait art is being supplied
separately. This project does not commission or regenerate that artwork.

Source inspection confirms this is a mixed implementation: actionBar.ts and
equipmentPanel.ts are Pixi, while initiativeBar.ts, combatHistoryPanel.ts and
characterSheet.ts use DOM. These are source facts, not decisions to retain either
their widgets or their technology. Existing useful work is a candidate; current
behavior, feature coverage, visual requirements and coupling determine its fate.

| Existing app/src/ui source | Existing work to evaluate | Required current behavior / integration gap |
|---|---|---|
| actionBar.ts, actionBarModel.ts | Icon grid, rows/paging, tooltips, keyboard/accessibility controls, reaction display | Inject detached choices and intent callbacks; remove singleton store, old API/FSM/affordance lease and waits on legacy presentation; apply current four-block and hover-choice requirements |
| equipmentPanel.ts, itemDetails.ts | Equipment arrangement, inventory grid, search/filter, item hover/detail interactions | Current inventory/equippable values and native equip intents; no old SDK item model or direct requests from drawing functions |
| initiativeBar.ts | Portrait slots, health/damage display and selection interaction | Party-audience facts and historical display revisions; no active-observer map switch, objective lookup or fabricated visibility |
| combatHistoryPanel.ts, eventSidebar.ts | Docking/scroll behavior and readable roll/modifier formatting | Current recorded log values; one log formatter, real copy, grouped movement/blood and known identity; keep raw event/JSON debugger out of gameplay |
| characterSheet.ts | Readable sheet/detail presentation where applicable | Current detached sheet/resources; exclude old character-creation/directory persistence workflow from fixed Fighter/Sorcerer launch |
| hudLayout.ts, rpgHud.css, gameTypography.ts | Existing layout/style/type resources | Current minimal/glass/no-bar-shift and supported-resolution requirements; evaluate proportions/readability instead of accepting old layout wholesale |
| gameIconResolver.ts, gameIconTextureLoader.ts, portraitUtils.ts | Image binding/loading purpose and existing view integration | Use current versioned UI-media identities; remove hardcoded old icon root, old roster/directory inference and competing caches |

For each component, record retain/adapt/replace with the specific current requirement
and evidence before porting it. This table identifies candidates and gaps; it is
not a completed functional audit or automatic reuse approval. Neither old UI is
the feature authority. The earlier UI contract and P01–P31 are the denominator.

The UI acceptance matrix must explicitly exercise: four action blocks and rows;
rank/form/summon/element choices and resource conversion; ordered/repeated/partial
multi-target selection; native route/AoE preview and invalid-action gating; one-click
self actions; world interaction/Alt/Ctrl/cursors; independent selected actor and
party knowledge; party/initiative portraits; compatible equipment choices, loot
and consumables; copyable recorded roll math and grouped log children; readable
tooltips and scaling; stable layout with glass panels; gesture ownership and
responsive camera controls. A similar-looking old widget proves none of these.

When retaining code, split view behavior from old orchestration at a concrete
component boundary: passive view input plus explicit user-intent callbacks. Do not write a
compatibility clone of the old StoreState/SDK merely to avoid changing imports.
One production network/command owner and one presentation state serve all views.
These are widget boundaries, not a new UI framework or domain-entity hierarchy.

Accepted icons/portraits resolve through stable content/presentation IDs and an
immutable media release. A later art delivery changes manifest mappings and the
release revision, not action logic or panel geometry. Preserve logical slot sizes,
contain/crop metadata and readability across source image resolutions. Missing
bindings are inventory defects to report, not guessed images. Current images are
usable until the human supplies replacements; no cross-chat coordination is needed.

UI acceptance compares the result with the NeuroClient reference and all later
user requirements; source reuse does not excuse missing features, interaction bugs
or old debug clutter. Existing runtime screenshots are references, not proof of
the migrated UI working against the new server. Final per-component reuse choices
remain part of the UI study; do not misreport them as approved by the human.

## 8. What is authored versus implemented

**JSON chooses and configures supported operations. Code implements their semantics.**
This is a finite typed vocabulary, not a scripting language. No expressions, arbitrary
callbacks, shader source strings or per-spell renderer classes in authored files.

| Authored data | Shared implementation |
|---|---|
| Motion/rig clip, semantic release and contact anchors, sockets, offsets | Rig sampling, interpolation, coordinate transforms |
| Selected media asset/phase, camera bank and directional policy | Frame selection, atlas sampling, bank lookup and allowed residual rotation |
| Palette replacement/ramp and named material with bounded parameters | Exact byte palette lookup, finite material equations/shaders |
| Tracks attached to hand/body/ground/target; timing links | Causal binding and timeline calculation from actual application identities |
| Blend/order/registered geometry policy | Shared compositor, masks, historical physical support and picking |
| Persistent/retirement/marker playlist configuration | Existing ownership/lifetime reduction and deterministic clocks |

Illustrative typed shape only, not a new duplicate recipe schema:

```json
{
  "operator": "registered-volume",
  "asset": "registered-asset-id",
  "phase": "impact",
  "attachment": "application-contact",
  "material": {"kind": "palette-swap", "palette": "authored-palette-id"},
  "composition": {"depth": "world", "physicalClip": "authored-supports"}
}
```

Implement these fields through the existing authored records where they already
exist. New tags only express a missing contract; they do not create another catalog.
Normal source pixels that already match their intended art remain unchanged.
Palette swap, material remap, lighting and opacity are distinct operations with
explicit order. Old `MultiTintFilter` is not a palette-swap implementation.

## 9. Full renderer/operator port

The source/function ledgers are the exhaustive declaration index. The following
operator families define the destination; the implementation ledger adds evidence
per source behavior, not a requirement for 959 TypeScript wrappers.

| ID | Shared operation and representative Python owners | JSON/data inputs | Port and mandatory case |
|---|---|---|---|
| R01 | Camera/projection (`projection`, `visual_position`) | cells, elevation, authored pivots/scale, camera | Pure TS transforms; four cameras, pan/zoom/high-DPI, inverse picking |
| R02 | Ground/world (`environment_draw`, `floor_composition`, `world_animation`) | observed tiles, slope/support, art banks | Pixi quads/meshes; grid between ground and walls, no native-map reads |
| R03 | Boundaries/doors/windows/devices (`boundary_occlusion`, `device_draw`, `environment_animation`) | placement, apertures, animation frames, state commit | Historical physical masks and cutaway; all rotations, destruction, threshold lighting |
| R04 | Body rigs (`animation_draw`, `body_presentation`, `body_hop`) | modular/fixed rig, clips, frame maps, sockets | Shared layers/meshes; movement/flying/prone/death, original sizes, no humanoid-only assumptions |
| R05 | Held/dropped gear (`item_draw`, `item_appearance`, `item_effects`) | item identity, slot/set, artwork, materials | Same equipment materials on owner/ground/new owner; no stale body cache |
| R06 | Exact colors/materials (`body_effects`, `finite_material`, `spell_palette`) | explicit mapping and envelopes | Palette swap plus maximum_rgb, luminance_texture, bark_texture, wither_texture, fracture_wave, energy_burn, rising_bands, etched_burn, flowing_film, frost_texture; byte/alpha fixtures |
| R07 | Source frames (`projectile_media`, `registered_media`, `media_coverage`) | frame/crop/pivot/atlas/plane format and revision | Browser decoding + Pixi textures; paired RGBA/XYZ/owner/footpoint registration, no frame-time decode |
| R08 | Projectile/beam/ribbon (`animation`, `directed_media`, `mechanism_projectile`) | trajectory/socket/release, bank policy, speed/time maps | Pure TS path sample + shader mesh; all headings/elevations, A/B/A repeated applications, interception |
| R09 | Areas/volumes (`area_media`, `volume_media`, `stationary_media`) | geometry, owned/soft fringe, support/suppression, physical boundaries | GPU XYZ/coverage; Fireball/Sunburst/Sleep continuous admitted art, no visibility-tile teeth |
| R10 | Sprite layering/blending (`draw_commands`, `fixture_depth`, `media_blend`) | global painter/depth/sibling keys, mix weights | Preserve normal/add/screen and complementary frame mixing; actor inside cloud and crossing boundary |
| R11 | Directed materials (`directed_surface`, `directed_mesh_media`, `directed_plasma_media`) | authored donor geometry/texture, noise_ribbon/darkness_mesh/plasma_trail | GPU original mesh/material math, no Python triangle raster port |
| R12 | Construction/walls (`construction_surface`, `wall_*`, `thorns_surface`, `wind_flow_media`) | sections, path/ring/shell geometry, material, formation/retirement | World meshes/registered banks, arbitrary allowed paths, shared dome state, effects on correct side |
| R13 | Particle/trail/orbit/intake (`component_particles`, `particle_media`, `weapon_trail_media`, `orbit_media`) | seeded samples, emitter/track, intake/attachment | Bounded buffers and deterministic sample time; no new simulation of combat |
| R14 | Conditions (`condition_sampling`, `condition_draw`, `condition_media_lifetime`) | owners, suppression, phase, marker and body media | Head playlist only; body/ground effects stay concurrent; size anchors and removal semantics |
| R15 | Items/spatial/concentration lifetimes (`item_attachment_lifetime`, `spatial_media_lifetime`, `concentration_media`) | existing owner/occurrence/revision clocks | TS retained state; unknown acquisition != fresh application; suppressed expiry stays expired |
| R16 | Movement/forced/portals (`motion`, `forced_movement`, `portal_animation`, `absence_media`) | disclosed legs/mode/connector, departure/arrival/collision facts | Shared body/path/absence sampling; reaction hold, ledge landing, one-end-only visibility |
| R17 | Feedback/lifecycle (`combat`, `damage`, `feedback`, `entity_lifecycle`) | actual damage/save/heal/life facts, contact timing, rigs | Text/flash/blood/body timing, temp HP, instant death, summon/despawn; no rerolled log math |
| R18 | Deposits/water/dust/residue (`deposit_*`, `surface_residue`, `water`, `object_dust`, `blood_draw`) | recorded contributions/reveal/support/receiving face | GPU sampled existing response; no new surface chemistry, no blood above unrelated layers |
| R19 | Spatial contacts/responses (`spatial_contact_media`, `spatial_response*`, `spatial_field*`) | actual recorded activation/damage/suppression | Same typed primitive families; source/recipient/cause/arrival retained |
| R20 | Persistent/finite orchestration (`presentation_retained`, `playback_frame`, `choreography`) | compiled anchors, committed facts, lifetimes | Pure TS binding/sampling; independent old/new/display clocks, no second gameplay executor |
| R21 | Picking/highlights (`interaction_frame`, `media_coverage`) | last-presented commands, coverage, apertures, wall fade | Point evaluation/region query sharing transforms; no viewport-sized CPU mask or synchronous GPU readback per hover |
| R22 | HUD/inventory/log (`ui/*`, `ui_composition`; NeuroClient reference in §7.1) | received values/intents, authored icons/portraits | Component-level retain/adapt/replace against all current requirements; readable math, real copy, fixed minimal blocks and hover choices; stable bar with log open |
| R23 | Capture/replay (`animation_preview`, `play`, `reference`, review tools) | same public recording + catalog/clock/camera | Shared browser runtime; on-demand GPU capture, saved fixtures and real-time diagnostics |

`game/app.py` is the current integrating map painter, not an obsolete entrypoint.
Its draw_frame and helpers explicitly belong to R02/R03/R10/R21: disclosure/light
treatments, stair/corner assembly, terrain-depth splitting, shared physical cuts,
world layer composition and the final selection snapshot all need port evidence.

Shader code is a small statically imported set attached to concrete Pixi meshes or
render passes. A typed exhaustive switch is enough to select operators. A new spell
normally supplies a recipe; a genuinely new primitive requires explicit code/schema
review and fixtures. Do not infer shader selection from display names or regexes.

### 9.1 Geometry, transparency and picking are first integration gates

Retain world XYZ and ownership even where a picture looks flat. Source plane
admission depends on the whole admitted interval, camera banks and persistent
overlaps; per-frame shader execution may skip unneeded work. Do not decide a data
plane is never needed from the first camera image alone.

Current depth groups, ungrouped occupied-pixel mean-depth ordering, sibling cuts and
complementary mixes require a complete solution. Pixi zIndex alone is insufficient.
Prototype the shared-depth-band GPU operation against overlapping bodies, scene
fixtures, world apertures and screen/add/normal components, with the exact reference
keys. If it fails correctness/performance, resolve the bounded alternative before
porting families; do not select approximate transparency silently. Use a concrete
Pixi render-pipe/mesh integration only where standard Mesh cannot express the pass,
not an independent rendering framework hidden inside Pixi.

Picking uses the last successfully presented frame and matching coverage transforms.
Decorative transparent media does not automatically block input; physical aperture
and wall masks are separate. Faded walls covering visible tiles must permit the
intended ground/object selection. Keep aperture preference, actor/object ownership,
selection silhouettes and four-camera equivalence. No per-frame readPixels stall.

## 10. One compiler and one historical presentation

Port existing Python public reduction/grouping/binding/sample semantics into TS
functions. Do not restore original NeuroClient's mapper/FSM/clip hierarchy alongside
them. Native outcomes are inputs, not executable frontend events.

Retain event, lineage, application, resolution and version identities. Repeated A/B/A
hits cannot be keyed only by target. Parentless reaction links do not rewrite native
ancestry or reduction order. Exact release, contact, formation, state/visibility
commit, HP/flash/number, body end, recovery and media retirement remain distinct.
World solidity/obscuration updates become displayed at their authored causal boundary;
native rules are already committed. No latest-state lookup to fill historical gaps.

Timeline compilation is camera-independent where timing must be stable. Camera
rotation changes sampling/banks, not already compiled travel duration. Registered
XYZ media preserves its numerical registration; allowed residual rotation for flat
directional projectile art must not be applied blindly to registered geometry.

Separate: source frames/FPS, body playback rate, world travel speed, presentation
milliseconds and measured display FPS. Preserve current rates; audit too-fast spells
using real compiled tracks before changing any recipe. No global slow-motion fix.

Seek uses deterministic absolute-time sampling plus cached bounded public/history
checkpoints as needed; never simulate the editor forward in fixed 30 FPS increments.
Checkpoints belong to presentation, not save-state reconstruction of native mechanics.
An initially observed persistent condition does not fabricate an application event.

## 11. Packing, loading and browser performance

Repair installed packaging before choosing residency budgets. Preserve original
private sources, exact decoded planes, source timing/pivots and original logical
ordering bounds. A smaller crop must not silently change global peer order. Keep
32 FPS; source-specific lower rates remain. No resolution downgrade or lossy XYZ.

Publish independently addressable immutable resources/chunks via a manifest, rather
than downloading a whole multi-bank ZIP for one frame. Choose color representation
and binary data-plane packing by measured lossless decode/upload cost. Do not label
Basis/KTX2 a lossless substitute for XYZ or exact palette bytes without proof.
Offline importer/packer owns conversion; ordinary game/server startup does not scan
or repack the archive. Static bytes bypass the engine worker.

Use Pixi Assets for supported resource identity/storage and one application readiness
owner for dependencies/pins/byte budgets; no duplicate physical texture caches.
Custom plane decoder work runs in a bounded Web Worker with transferable buffers.
Keep queue/decode/staging/CPU/VRAM byte accounting separate. Pixi's loaded promise
does not by itself prove upload/shader readiness. Measure prepare/upload completion.

Admission covers displayed scene, persistent effects, active group and bounded next
group, including all camera banks required for free rotation. Dependency enumeration
and drawing use the same selectors. Pan/zoom/color variants use transforms/uniforms,
not new copies. Large single uploads need bounded chunks/proven staging behavior;
a time-budget loop cannot interrupt one long GL upload call. Fail with the exact
missing resource if an admitted sampler requests unprepared data; never omit art.

Latest public state may receive new data while current historical playback continues.
Preparing a next group must not advance its HP/log/world commits early. Handle context
loss by rebuilding resident resources from retained data and restoring displayed time,
not replaying native commands. Dispose safely on preview change, scene exit and resize.

## 12. Recover Studio as the real authoring and performance workspace

### 12.1 Reuse decisions

| Original NeuroClient component | Treatment |
|---|---|
| StudioWorkspaceLayout, DOM primitives, inspector controls | Reuse/adapt layout/control functions after removing singleton dependencies |
| Document history/identity/recovery, clipboard and compare UI | Reuse bounded behavior; passive state/functions where new code is needed |
| Timeline layout/drawing, asset thumbnails, import/selection UI | Reuse interaction design; timeline data comes from new compiled tracks |
| StudioPixiSurface/Lifecycle sizing and disposal | Extract useful device/context handling; use same production adapter |
| StudioScenarioCompiler, old replay import/mapping | Replace old SubjectiveReplicationFrame synthesis with current public recordings |
| createStudioPresentationRuntimeHost | Replace: old host no-ops equipment/vitals and imports old runtime |
| AnimatedEntity/AnimationFSM, ClipQueue, subjectivePresentationMapper | Do not bring into new app; one new port of current production semantics |
| SpellStudioPreview seek and timelineBuild timing | Replace fixed 15-frame/30 FPS and earliest-hit calculations |
| MultiTintFilter and generated legacy spell recipes | Not accepted defaults; use current accepted palette/material/gesture recipes |

### 12.2 Complete authoring surface

Editable families: spell drafts (gesture/layers/palette/material/media/directed/arcs/
contact/cancel/displacement/child attack), attack recipes, body actions/bindings,
movement/forced/reaction/damage/heal/life/death/equipment contexts, conditions and
markers, rigs/poses/sockets, spatial/concentration/construction/portal/item/lifecycle/
deposit/world bindings and shared feedback styles. All 53 catalog fields receive an
editable-family, derived/technical-read-only, or existing-source-metadata disposition.
Read-only display is not counted as successful authoring of a field that must be edited.

Old spell schema lacks many of these fields. Current Python schema is the semantic
baseline; generated TS validation and explicit versioned migrations replace the old
editor serializers. Unknown fields are rejected/preserved through controlled conversion,
never silently discarded during save. Add round trips for every editable field family.

The single source of authored truth initially remains current `game/data/` documents.
Production consumes a versioned effective export. Studio reads canonical documents,
their revision and a source-location map generated by the exporter so edits address
the source recipe rather than a merged/default copy. Derived selections point back
to their owner; editing an alias cannot create a second spell definition by accident.
The release includes AnimationData plus independent AssetDocument/WaterSource,
WorldBindingsSource, EnvironmentDocument and UI media/presentation/choices/skin
sources. Current PresentationCatalogExport contains AnimationData only; expand the
versioned release manifest to reference all these validated documents. Do not
mistake that one export for a complete world/UI bundle. The companion assigns them.

The local tool service uses an allowlist of document IDs/paths and expected base
revision. Save validates the candidate source set and effective export, writes a new
complete version to staging, and atomically switches the tool's active manifest.
Canonical source-file updates require rollback/recovery on multi-file failure; do
not claim an ordinary sequence of writes is a filesystem transaction. A single-file
edit uses temp+replace. No write routes are installed in the production game API.
Undo/draft recovery is editor-local. Explicit save/publish produces a versioned
bundle; existing playback keeps its pinned revision until a safe switch/reset.

### 12.3 Preview modes share actual production behavior

1. **Recorded encounter/action:** open a current public recording and replay through
   the exact client reducer/compiler/sampler/resources/Pixi renderer. This includes
   damage, saves, equipment, condition/world changes and terminal outcomes.
2. **Authoring composition:** choose rig, source/target poses, palette, camera and
   an explicit fixture outcome; compile through the same presentation functions.
   Label it a visual fixture; it cannot certify native mechanics.
3. **Isolated real-engine scenario:** tooling launches a separate engine process,
   executes existing native actions and returns a public recording. Same engine code
   as live; never inject guessed events or use the running player game as sandbox.

All modes support real-time play, pause, absolute seek, frame stepping, four cameras,
zoom, grid/support overlays, selected layers, source-vs-candidate compare, and varied
rig sizes. Timeline lanes show compiled body/prepare/release/travel/application/
contact/state-commit/recovery/retirement anchors and causal links. Editing a lane
changes an authored field then recompiles; it does not set an independent timeline.

Live game and Studio use the same complete scene composition, including walls,
props, light, picking and UI-independent world state. Previewing only an isolated
sprite cannot pass full-scene performance acceptance. A representative crypt scene
is a built-in recording fixture, not a separately implemented demo renderer.

### 12.4 Direct performance feedback

Always available compact FPS/frametime indicator. Expanded Studio diagnostics show
frame-time graph and p50/p95/p99/max, CPU reduction/compile/sample/submit, resource
fetch/decode/upload/readiness waits, draw calls/texture bytes/queue bytes, native
operation/capture/network timings when present, and dropped/long display intervals.

Measure wall-clock requestAnimationFrame/display intervals during real-time playback.
Keep source FPS and authored speed visibly separate. Optional asynchronous disjoint
GPU timer queries report supported GPU timings; label unavailable data rather than
calling CPU submission time GPU time. Do not synchronously finish/read pixels to
measure each frame. Background-tab pauses are excluded/labeled in benchmark results.

One diagnostics collector sits at the shared production runtime boundary; Studio's
timeline/inspector overhead is reported separately. A recording can export the same
case/catalog/camera plus measured live timing, issue note and screenshot/video.
Offline fixed-time video remains useful visual evidence, never an FPS certificate.

## 13. Player-facing repairs remain required

| Existing complaints | Destination/acceptance |
|---|---|
| P01–03, P18 | Native doors/occupied corridors/ally transit/remembered-area route correctness; preview equals executed path |
| P04, P13, P22–23, P29 | Shared world picking/cutaway/door reach/threshold visibility/grid layering, all four cameras |
| P05–06, P11–12, P15, P27 | Native and frontend startup/performance, FPS, Windows host setup, zoom and asynchronous delivery |
| P07, P21, P26 | Stable party audience, known enemy identity, initiative/portraits/log linked to presented history |
| P08–09, P14, P16 | General projectile direction/socket/speed, palette swap, intact admitted areas, ranged motion |
| P10, P19–20, P24, P28 | Native previews, self-action once, disabled invalid choices, one Dash, timed errors and gesture ownership |
| P17, P25, P30–31 | Authored goblins, actual dice, Haste contact retention and correct zero-HP turn handling |

Earlier UI constraints are binding: four compact icon blocks (base explicit melee/
ranged, spells, class, inventory items), multiple rows as needed, minimal same-sized
hover choices/upcast icons, no redundant confirmation, environmental actions via
world click/Alt, small party portraits, bright accepted icons, readable antialiased
text, glass panels, fixed bar when log opens, aligned copyable math-rich combat log,
grouped path/blood children, equipment slots and compatible inventory choices.
No full-screen obstructive menus, fake controls or persistent tutorial text.

Party observation grants UI knowledge; native action legality still checks the acting
character's constraints. Known/explored movement and party display must work without
giving spells illegal through-wall targeting. Fix native exploration policy in its
owner where the current behavior violates the agreed player experience.

## 14. Delivery sequence and independent review gates

This is one full migration with staged evidence, not a pilot replacing the scope.

| Stage | Deliverable | Required exit evidence / removal |
|---|---|---|
| S0a | Preserve baselines, finalize source/field/operator maps and public API | Both plan reviewers; complete contract/ownership maps; unlocks backend work |
| S0b | GPU packing/composition/readiness proof, independent of backend work | Actual browser GPU compound scene, exact formats/budgets resolved before dependent rendering ports |
| S1 | Extract narrow engine player boundary and generated wire contracts | Same native outcomes/permissions without game-render imports; repeated target/condition/log/world fixture parity; no copied native rule logic |
| S2 | New host/worker HTTP+SSE lifecycle | Lost-reply retry, stale prefix, duplicate/gap, refresh, terminal playback, audience stability, bounded queues, fatal mutation errors; no old server imports |
| S3 | New TS reducer/compiler + minimal Pixi scene, Studio shell attached immediately | Python/TS semantic/time fixtures, editor/live same runtime, real-time FPS visible before mass port |
| S4 | Resources/packing and R01–R10 foundation | Four-camera real scene, blend/picking/XYZ/upload parity, no CPU image splitting or giant ZIP first-use |
| S5 | R11–R23 and all authored content | Every source/catalog row accounted for; full actions, conditions, environment and UI, not spell-only demo |
| S6 | Complete Studio editing/save/reload and native scenario tooling | Every editable family round-trips, real recorded impacts/reactions, no old timeline estimates or no-op state writes |
| S7 | Complete native/UX recovery and combined Windows browser journey | All P01–P31/UI acceptance; 15 min/100 operations, every supported resolution, memory/startup/frame/input budgets |
| S8 | Remove active legacy dependencies and final two independent implementation reviews | Old server/SDK/renderer excluded from new runtime; Python reference frozen/archived when parity closes; no dual production solver |

Backend S1–S2/performance work and frontend S3 onward can progress independently
after wire fixtures and authoring contracts are agreed. Runtime backend is the first
playable prerequisite; browser/Studio design does not wait for an unrelated server
platform. Review each independently completed contract stage with anti-slop and
ECS/DAG reviewers, fix blockers, then proceed. No approval request for already
authorized routine execution, but changed product scope returns to the human.

## 15. Tests and acceptance

Use HOW_TO_TEST.MD: observable boundary cases, exact received values and visible
behavior; no tests freezing private call counts or class layout. Architecture tests
specifically protect import DAG and old-system exclusion; do not present them as
gameplay evidence. Existing fixtures are reused, not regenerated to bless regressions.

- Engine: native paths/actions/resources/visibility and long-history cost independent
  of frontend. Test normal dice and expected rejection before mutation.
- API: actual isolated process and network cases for generation/authority, two-step
  selection, A/B/A/reduced-max targets, stale queries, disconnect/reconnect, command
  unknown outcome, terminal events and hidden sources. No unsafe raw recording route.
- Contract: Python-produced JSON validates/reduces in TS; actual schema version and
  compatibility rejection; canonical presentation export retains all effective fields.
- Presentation: event/phase/commit/socket/trajectory/lifetime fixtures across Python
  reference and TS; then selected GPU pixel/coverage fixtures. Latest state changes
  while paused historical frame remains stable. No per-spell timing workaround.
- Studio: editing every family, unsaved recovery, conflict and failed save, new content
  revision while old track runs, absolute seek and accurate repeated applications;
  real-time full scene uses same resources and timing as live.
- Visual/player: complaint-specific cases, all bank/camera/elevation combinations
  appropriate to a primitive; whole crypt exploration/loot/trap/fight with both heroes.

Primary supported display is Windows browser at 2560x1440; repeat at 1920x1080 and
1280x720. No 4K requirement. Warm frame work p95 <=16.7 ms, p99 <=25 ms; no reproducible
stable >50 ms stalls. Input acknowledgment p95 <=50 ms/max100 ms. Warm first interactive
scene <=5 s, cold <=10 s, measured separately from tool/dependency provisioning.
First-use media readiness and upload outliers are disclosed separately, target <=250 ms
after immediate input feedback; no decoder work causing mid-animation stalls.
The input acknowledgment target means immediate **local visible feedback**; terminal
command replies still include the separately budgeted native execution/capture time.
After 15 min/100 operations, working/resource/live-delivery memory must stabilize.
Report retained native history and public recording growth separately against their
declared budgets; do not promise flat total memory while intentionally retaining
events. Late native capture must not grow merely because all prior events are rescanned.
No smaller art, lower source FPS or dropped outcomes used to meet these targets.

## 16. Review status and explicit unresolved proof work

Both independent final plan reviews approved the corrected design on October 7:
anti-slop/server ownership and ECS/import-DAG/renderer/authoring coverage. The
[review receipt](audits/neuroclient-server-20261007/PLAN_REVIEWS.md) records their
findings, corrections and bounded approval. This is not a claim that the API,
migration, GPU compositor or Studio has been implemented.

Implementation must resolve measured texture-chunk/residency/upload budgets and the
compound transparency/picking proof in S0. Exact document-source mapping and complete
wire privacy/version audit are enumerated S0/S1 work, not permission to discover a
different architecture halfway through. If a current material cannot be expressed
by the chosen primitive, update its concrete operator row and review the change;
do not invent a hidden per-spell path. Durable game saves and simultaneous controlling
seats remain separate requested features, not implied completion of this migration.

## References

- [Pixi renderer support](https://pixijs.com/8.x/guides/components/renderers): production WebGL recommendation.
- [Pixi Mesh](https://pixijs.com/8.x/guides/components/scene-objects/mesh): geometry/shader/render-state integration.
- [Pixi Assets](https://pixijs.com/8.x/guides/components/assets): loaders/cache/custom parsers; not an application residency guarantee.
- [Pixi performance](https://pixijs.com/8.x/guides/concepts/performance-tips): masks, filters, blending and texture costs.
- [SSE](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events): ordered event delivery/reconnect transport.
- [EventSource processing](https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation): Last-Event-ID is not completed application reduction.
- [FastAPI concurrency](https://fastapi.tiangolo.com/async/): I/O concurrency does not move CPU mechanics off the networking loop.
- [Previous recovery plan](PLAYER_PLAYTEST_RECOVERY_PLAN_2026-10-06.md) and
  [GPU/packing evidence](GPU_RENDERER_AND_MEDIA_READINESS_2026-10-07.md): retained defects, measurements and acceptance targets; desktop-GL destination superseded.
