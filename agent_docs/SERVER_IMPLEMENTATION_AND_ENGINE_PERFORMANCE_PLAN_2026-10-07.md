# Independent game server: implementation shape, verification and engine speed

**Current closure:** server functionality, SDK delivery and §15 cross-game reuse
are complete. [Final feature/verification receipt](audits/server-implementation-20261007/WARM_WORKERS.md).
New-client work can use this server. Broader Gate B largest-map/dense-AI performance
claims remain bounded by the measured evidence; they are not silently marked done.

**Implementation receipt:** [server implementation, verification and remaining limits](audits/server-implementation-20261007/IMPLEMENTATION.md). The sections below preserve the approved design; their original planning-status paragraphs are historical. The production schema is now exported from its owners, not the former design overlays.

2026-10-07. **Implementation authorized October 7; work starts at A0b.**
This is the server-only elaboration of the
[network/client/Studio plan](NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md).
It governs that plan's server sections where this document is more specific.
The [stream and SDK contract](SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md)
is a required part of this plan: both Python and TypeScript SDKs, subjective-only
delivery, cursor following, general seat ownership, standalone packaging and
H41–H56 are in Gate A. There is no arbitrary player/seat-count cap.

The human's order is binding: establish the complete server shape and exercise it
independently of any frontend; then iterate on measured engine speed. Collect a
baseline during construction, but do not turn construction into speculative engine
optimization. Browser UI, Pixi, shaders, art packing and Studio are outside this phase.
Browser-compatible transport code in the TS SDK is explicitly included.

The concrete [schema/source package](server-api-v1/README.md) now supplies the
field inventory, proposed closed JSON Schema/OpenAPI and captured examples. Its
[upstream log contract](server-api-v1/COMBAT_LOG_CONTRACT.md) and
[semantic rules](server-api-v1/semantic-contract.md) are required implementation
inputs. They specify source-owner changes; generated design examples are not
claims that future privacy/transport behavior already works.

## 1. Finished result

An installed command starts one configured encounter and its isolated native owner.
A small driver using the production Python SDK can connect, obtain the party's state and legal choices,
preview and perform actions, receive complete results, let native AI take its turns,
disconnect/reconnect and finish the encounter. A second independent consumer can
reduce the recorded public bytes after the engine has shut down. The independently
installable TypeScript SDK exercises the same protocol through a headless driver;
neither SDK requires the engine or a renderer on the caller's machine.

The server must operate with no running client, SDL window, graphics context, media
decoder or installed image banks. Native content definitions remain necessary; art
references can remain passive IDs. No copied combat rules, server-owned target
geometry, animation waits or old omniserver dependency are admitted.

First supported deployment: native Windows Python in the current checkout, or the
same locked environment on WSL. Moving the checkout is optional. First product game:
the authored Lantern Crypt and fixed human-controlled Fighter/Sorcerer party. Small
private native scenarios exercise other existing abilities and edge cases. Seats
follow configured exclusive entity assignments: every eligible external entity can
have its own seat, or one seat can own a group. There is one writable attachment per
seat and one native process per game. Concurrent connected seats and a same-encounter
Python-versus-TS scripted match are required. Account/lobby services, persistent
campaigns, host-crash save/load, distributed workers and new content remain outside
scope. The default Fighter/Sorcerer grouping is configuration, not a server limit.
The stream contract §5.2 lists the required configurations explicitly: one seat per
side, one seat per external unit, an externally controlled side against AI, and
external/AI mixtures within either or both sides. Reuse native per-member roster
controller overrides; side membership never determines command authority or
observation grants. H55 covers these with one parameterized encounter driver.

Two completion gates:

- **A — complete server shape:** native ownership, protocol, lifecycle, public facts,
  independent correctness/recovery cases and a full encounter work without a client.
- **B — engine performance:** all measured stages have an issue/disposition ledger;
  repairs meet the budgets using the same correct workload and retained facts.

Gate A is not a claim of acceptable speed. Gate B is not a graphics-FPS claim.

## 2. What exists and what must change

Initial source study used the then-dirty `codex/recovery-design` checkout. The human
has since committed it and created `feature/server-is-coming-back`; this second
pass began with a clean tree at `40eb37b9b4cac72ea75d00d7b1545a4e48a5d2a2`.
Record HEAD plus changed-file hashes/diff again at implementation start. Do not
attribute pre-existing recovery changes or tests to this planning task.
The [source fingerprint record](audits/server-plan-20261007/SOURCE_BASELINE.json)
captures 29 inspected files for this study; it is not a benchmark or deployment freeze.

| Existing source | Keep | Concrete gap |
|---|---|---|
| `game/session.py` | Native session composition, exact retained discovery/templates, preview/execution APIs, HUD/log capture | Fixed player/AI grouping and all-player HUD/log assumptions; unbounded preview cache; eventless changes need their own revision |
| `game/runtime_worker.py` | Single native owner, execute then capture before another mutation | Trusted local pipe lifecycle; no network command receipts; invalid submitted selections can escape as ValueError; private gaps in reply |
| `game/runtime_protocol.py`, `runtime_connection.py` | Discriminated finite messages, bounded framing, process/error ownership | No public protocol/version/lifecycle; EOF currently closes game; pipe request number is not network idempotency |
| `game/player_facts.py`, `player_reduction.py`, `audience.py` | Authorized detached facts, causal identities, party perception and public reduction | Must close finite wire schema/privacy audit; no native object or hidden-source diagnostic escapes |
| `game/presentation.py`, actor capture/projection | Recorded complete lineages, event-time admissions and state | Full-history indexing and per-root historical scans; benchmark later, do not replace with latest-world reads |
| `game/player_projection.py` | Projection of admitted native records | Separate offline RecordedSequence conversion from hot projection import closure |
| `game.controls.selection_target_pool` | Exact primary/secondary target-handle semantics | Move this small pure helper out of UI ownership; this is not evidence of a current pygame import leak |
| `game/ui_content_composition.py`, `ui/content_types.py` | Native content descriptors for icon/label identities | Neutral content module; server does not validate/load image files |
| `dnd.actions_functional` and native systems | Costs, target/position validation, paths, senses, items, turns, AI | Fix confirmed native defects in their owners; no equivalent rules in HTTP routes |
| Old `server/event_server.py` and old replication stack | Reference for transport behavior and defects | Keep HTTP/SSE pattern; no old runtime imports, copied orchestration or per-spell endpoints |
| Old `sdk/typescript` | Evidence for fetch/SSE, reconnect and cursor waits | New player-only TS package and Python wheel; exclude objective/directory exports, old reducers and native-event generator |

Three newly identified correctness obligations:

1. The local worker catches CommandRejected, but excessive target allocations can
   raise ValueError in `_validated_extra_target_uuids` before mutation. Submission
   must use the existing native prefix validator and return a typed refusal. Do not
   catch every ValueError and call it a harmless invalid request.
2. `toggle_player_handler` changes `handler.enabled` without adding an EventQueue
   event. Accepted state changes need a separate application revision, and old
   discovery must become stale even when the native event cursor is unchanged.
3. The worker's `gaps` currently contains native class names/event IDs. These are
   private diagnostics. Missing required projected behavior is a failed operation,
   not a successful network result with a debug warning attached.

## 3. Responsibility and module shape

The implementation uses ordinary functions over passive records. Small neighboring
files may be combined. No session/entity class hierarchy, repository framework,
service locator, generic command bus or second event dispatcher is planned.

```text
dnd/player/                       extracted application boundary
  facts.py, commands.py           current detached facts and finite intents
  audience.py                     recorded audience/knowledge composition
  content.py                      native static descriptors, no artwork loader
  session.py, selection.py        exact retained native choices and commands
  capture.py                      private complete-lineage capture
  actor_facts.py, actor_projection.py
  projection.py, reduction.py     public projection and pure public reduction
  recorded.py, compatibility.py   private recording helpers / explicit old decode

player_server/                    new transport composition
  __main__.py, config.py          CLI, installed scenario, immutable configuration
  app.py                         FastAPI routes, authentication, lifecycle wiring
  protocol.py                    public HTTP/SSE envelopes, errors, versions
  worker_protocol.py             private finite IPC envelopes, never SDK-exported
  host.py                        serial admission, receipts, attachment, scheduling
  worker.py                      native application composition/dispatch only
  connection.py                  process and bounded pipe I/O ownership
  recording.py                   exact public-byte spool and delivery index

sdk/python/                      standalone dnd-player-sdk (HTTPX)
sdk/player-typescript/           standalone @neurodragon/player-sdk (fetch)
sdk/protocol/, sdk/conformance/  generated schema + shared finite fixtures
devtools/export_player_protocol.py  explicit public roots only
tools/server_probe.py             real-network driver using the Python SDK
tools/server_probe.ts             TS SDK real-network/recording parity driver
tools/server_benchmark.py         same driver + timing/report orchestration
tests/player/                    headless application/public reduction cases
tests/player_server/             HTTP/process/lifecycle cases
```

`dnd/player` depends on existing native types/functions. Native systems never import
it or transport. Private `Operation` contains native roots and stays in the child.
Public wire values contain no Entity/Event/BaseAction instances, executable private
templates, callbacks or raster data. Extract existing functions, update temporary
pygame imports, and keep one implementation; no copied pygame/server versions.

The host owns process lifetime, bounded transport state and receipts. The worker
owns the session, authoritative command validation, mutation, AI and capture. The
native encounter/controller decides who acts; the host only requests its next
existing decision boundary. Static content descriptors are composed once in the
worker and served by revision, not regenerated for every choice or operation.

The stream contract §5.2 specifies general seat composition: one active-turn
discovery cache qualified by seat/actor, one original log listener/buffer, immutable
common capture context followed by existing per-audience admission/projection, and
one shared reducer implementation over each audience's state. Current capture is
already audience-filtered; never share one seat's filtered lineages with another.
No SDK-specific controller, per-seat native world or duplicated capture algorithm.

**Import claims must be accurate.** Existing detached query DTOs live in
`dnd/core/base_actions.py` beside executable types. Reusing them can import native
definitions into the host; this does not authorize constructing or executing a
native game there. Initially retain these exact DTOs and measure their import cost.
Require no host import of worker/session composition, pygame/media or old server,
and no host content bootstrap, map reset or live game creation. Record the actual
transitive closure. If definition imports materially slow startup, a narrowly
justified split of existing passive DTO definitions is a performance repair, not a
broad core rewrite or duplicate wire model. Pure leaf contracts remain the direction.

Launch one ASGI host process (no automatic multi-worker replication of its game).
Use the current interpreter to launch the child module; no forked live Session,
pickle, shell command interpolation or inherited mutable game state. Reuse bounded
pipe I/O/diagnostic draining adapted from the current connection. One transport
thread may own blocking pipe reads/writes; it performs no mechanics. Host async work
awaits completions without blocking the network loop. FastAPI lifespan owns startup
and teardown; process completion is awaitable and stderr cannot corrupt packet bytes.

## 4. Identity, revisions and lifecycle

Do not overload one cursor to mean all of these:

| Value | Owner and meaning |
|---|---|
| game_id | Configured game identity; transport routing only |
| game_epoch | Fresh native runtime generation; prevents crossing sessions |
| seat_id / audience_id | Host-authorized control and stable party observation; browser does not choose observers |
| attachment_epoch | Current writable connection incarnation; replaces the previous tab's admission rights |
| application_revision | Private integer changed after every accepted mutation/native decision that changes state, including eventless handler preferences; captured before another command |
| state_revision | Opaque public token for an authorized current decision/state boundary; binds choices/commands to application revision without publishing an objective event count |
| discovery_generation | Exact retained native discovery instance, actor and force-attack mode |
| native event cursor | Private capture/index coordinate; never used alone to authorize a command |
| sequence | Contiguous published operation number for this audience, with initialization at zero |
| command_number | Monotonic per-seat mutation identity; receipts prevent duplicate spending |
| correlation_id | Query response association only; not command identity or native state |

Keep disclosed causal/version identities required by PlayerLineage. Public ordering
is audience-local, including nested causal/version coordinates; native counters do
not escape inside facts. This projection and its schema audit are specified in the
stream/SDK contract. Received, consumed, acknowledged and displayed positions are
separate. Only consumed sequence is the recovery cursor; displaying is client-only.

Expose finite status independently of a successful operation:
`starting`, `waiting_for_human`, `advancing`, `delivery_blocked`, `terminal`, `failed`,
`closing`, `closed`. Status has game epoch, current published sequence, authorized
state token/boundary and an optional safe failure reference. No hidden actor names,
native stack traces or objective world state. `delivery_blocked` includes an explicit
reason: recording capacity, or that seat's delivery/catch-up. Inactive seat catch-up
or a slow socket does not pause another seat's turn; real recording exhaustion can
pause the game. Status includes `input_actor_uuid` only for that seat's own current
external input actor, never a hidden opposing actor. Reads do not call discovery.
A stream heartbeat carries authorized status without inventing a state event.

Startup loads the locked native content and authored encounter once, captures an
authorized initialization and drives existing boundaries until human input or a
terminal result. Bootstrap readiness does not depend on sprites or a client attaching.
Ordinary disconnect never closes the game. Explicit host shutdown stops admission,
waits up to 10 seconds for in-flight work and native cleanup, then terminates and,
if necessary, kills after a further 2 seconds. These are shutdown limits, not a
per-command timeout or permission to retry interrupted work.

Startup/capture/worker/spool failure sets failed with an opaque incident ID. Retain
private stage, command identity, traceback and last committed/public boundaries.
Read-only status and already recorded public history remain inspectable if the host
is alive. No automatic restart/replay of mutations; a process crash is not saved-game
resume. Fatal errors remain visible rather than hidden in empty successful replies.

## 5. Practical public API

Keep the HTTP/query + SSE design, verified in the old `/replication/subscribe` route.
No browser UI or old SDK is needed to call it; both new SDKs are deliverables.
Use existing FastAPI/HTTPX/Uvicorn dependencies at their locked versions; select
supported streaming primitives from that version rather than adding an RPC framework.

| Method / path | Request | Response / behavior |
|---|---|---|
| GET `/healthz` | none | Minimal host liveness, no game/private details |
| GET `/api/v1/bootstrap` | seat credential | Protocol/player-schema versions, game/epoch/audience, status, content revision, installed scenario display identity |
| GET `/api/v1/games/{game_id}/status` | bound seat | Cached finite lifecycle and delivery/boundary status |
| POST `/api/v1/games/{game_id}/attachment` | seat credential, acquisition ID, expected prior epoch | Retry-safe explicit attachment acquisition/replacement, next command number, pending identities, initialization reference and catch-up sequence |
| GET `/api/v1/games/{game_id}/initialization` | bound attachment/seat | Exact authorized sequence-zero initialization |
| GET `/api/v1/games/{game_id}/events?after=N` | bound attachment, game epoch, last consumed sequence | Ready/status and complete ordered operation envelopes; explicit resume-unavailable if missing history |
| POST `/api/v1/games/{game_id}/ack` | attachment, epoch, sequence | Release delivery credit after safe consumer acceptance, never animation completion |
| POST `/api/v1/games/{game_id}/choices` | attachment, actor, state revision, force_attack, correlation | Detached native choices with exact discovery identity/revision and request echo |
| POST `/api/v1/games/{game_id}/preview` | attachment + retained choice + ordered prefix + correlation | Native confirmation status, effective recipients, next choices/positions, route/AoE/cost facts |
| POST `/api/v1/games/{game_id}/commands` | attachment + command number + state revision + finite intent | Immediate reserved/pending receipt (202), retained result or typed pre-admission refusal |
| GET `/api/v1/games/{game_id}/commands/{number}` | bound seat | Pending, committed with sequence reference, rejected, expired or unknown status |
| GET `/api/v1/content/{revision}` | admitted public revision | Immutable PUBLIC descriptors/schema references; OBSERVED additions arrive with authorized operations; no pixels |

Schema artifacts are exported from an explicit set of canonical public Python roots,
served/read as versioned JSON, and generate both SDKs' wire declarations. This is a
Gate A requirement; old native-event/omniserver exports are excluded. No HTTP endpoint
can choose a random observer, seed dice, create entities,
set HP, advance AI, load arbitrary files or mutate authored documents. Start/fixture
selection/close are CLI/private test-host configuration, not public gameplay commands.

Authentication uses a random configured seat token, kept in a private local
file/environment and never committed, bundled or put in URL queries. Both SDKs send
Authorization; TS uses fetch streaming and does not depend on native EventSource.
Use explicit development origins and configurable host address for Windows/WSL,
loopback by default. Cookie/account services and remote access provisioning are not
part of this phase. See the stream contract for redirect, header and CORS behavior.

### 5.1 Finite intents and selection

Use the existing discriminated intents, not one route or class per action:

```text
execute_selection:
  actor_uuid, discovery_generation, action_index,
  target_indices[], extra_target_positions[]
end_turn: actor_uuid
equip: actor_uuid, item_uuid, slot
unequip: actor_uuid, slot
toggle_handler: actor_uuid, discovery_generation, handler_uuid, enabled
```

All carry the public state revision through the command envelope. Exact integers
are handles in the retained query, not user-supplied executable action models.
Validate handle membership/nonnegativity before indexing; signed world coordinates
remain coordinates and are not rejected merely for being negative. Do not equate
target indices with cells or UUIDs.

Ordered recipients, repetitions and positions survive JSON unchanged. No set/sort
or name-based action lookup. A single Magic Missile target or partial A/B allocation
uses the native completion rule; a spell allowing fewer recipients does not get
automatic invented copies. Extra positions for walls, summons or displacement use
the native next-position and selection predicates. No server geometry algorithm.

Self actions submit the discovered self target directly. The API does not demand a
second confirmation click. End turn and equipment carry state/actor authority but
do not require expensive action discovery solely to obtain a token; their existing
native admission functions validate them. Reaction toggles must reference an admitted
handler. Force-attack changes the retained native query mode, never bypasses rules.
No new public switch for unsafe path choice is added; use the current native safe
route preference consistently in preview and execution.

Native preview must supply the exact chosen route/cost and affordable endpoint where
the present DTO only carries geometry. Extend its existing passive preview record
if required; do not make the host choose between safe/shortest routes. Preview also
returns the expected ordered recipient allocation and legal next inputs. Internal
target filters, physical sight and range still belong to the acting creature.

### 5.2 Error classification

| Class | Observable result | Mutation/retry rule |
|---|---|---|
| Malformed JSON, unknown tag, invalid scalar shape | 400 `invalid_request`; no echoed input/private context | No command reservation, no native execution |
| Wrong credential/authority | 401/403 | No reservation; do not disclose hidden state |
| Old game/attachment, conflicting payload, wrong command number | 409 typed code | No new reservation; state must be explicitly refreshed |
| Capacity/busy before admission | 429/503 + reason | No reservation; same identity may be retried after capacity returns |
| Structurally valid newly admitted command, stale state/choice/illegal complete prefix | Terminal rejected receipt | Number consumed, unchanged gameplay/RNG; identical retry returns same rejection |
| Native cancellation after resolution begins | Committed operation containing actual cancellation/outcomes | May have costs/reactions; never relabel as preflight rejection |
| Unexpected error after native dispatch starts | Failed session/command outcome with incident reference | Never assume rollback or retry, even if event cursor did not advance |

Native complete-prefix validation is mandatory even if no preview request preceded
submission. Use `preview_available_selection`/existing pure selection checks inside
the application boundary immediately before execution. Known invalid inputs get a
typed admission refusal. An unexpected exception in execution is still a defect and
remains fatal. A cursor-equality check is useful diagnostic evidence, not proof of
no mutation: handler preferences demonstrate why.

## 6. Single-owner command sequence

The host serializes admission/attachment changes. Only one mutation may be pending
or executing. Discovery/preview reads enter the same worker's serial queue; old
hover work can be superseded before dispatch, but admitted mutations cannot be
canceled or reordered. Never hold a network-loop blocking wait on native work.

For each command:

1. Authenticate seat/game. Find an existing `(game_epoch, seat_id, command_number)`
   receipt before testing current revision. Compare the **logical payload** (intent,
   actor, submitted state/discovery/selection). Exclude attachment/correlation IDs.
2. Existing pending/terminal identity returns its receipt. Different logical payload
   conflicts. Evicted old identities are expired and cannot execute again.
3. For a new identity, check attachment, expected next number, actor membership in
   the seat's already-bound controlled set, caught-up boundary and capacity. An
   actor outside that set is 403/no reservation; this uses the control binding,
   never a live Entity lookup or turn rule. Reserve number and logical payload.
   Advance the next number once. Return pending receipt; no native success is
   claimed yet.
4. Worker revalidates the submitted revision, actor turn/control and exact retained
   query when it dispatches, then performs native complete-prefix admission. A known
   refusal stores the rejected receipt; no event/RNG/resource changes are allowed.
5. Execute through the existing native owner. Advance private application revision
   on accepted changes, including eventless ones. Capture every completed/canceled
   root plus permitted HUD/log/condition/item/world values before another mutation.
6. Admit/capture/project for each configured audience from the common private
   evidence, using the same functions. Validate and stage exact encoded public
   results. Publish participating audience heads together after the whole native
   batch is recorded; no empty pulses for unaffected audiences. The own-command
   receipt references only its seat's resulting cursor. Private IPC stages audience
   records separately under the existing frame limit, not one N-times-larger reply.
7. Continue native advancement one existing decision at a time until human/terminal
   boundary or recording capacity is exhausted. No animation clock enters this loop.

Execution→capture→projection→spool is one serial application operation, **not a
database transaction or rollback promise**. Capture/encode/spool failures after
mutation fail the game; retain private evidence and never respond “rejected, retry.”
Encode published bytes once and reuse them for live delivery and replay. Measure
projection, validation and the one encoding cost separately. The host spools and
streams the worker's authorized encoded bytes without a decode/re-encode round trip;
private framing carries routing metadata separately from those immutable bytes.

The parent must not inspect live Entity instances to answer a route, HUD or legality
question. Existing native internal caches and registries never cross IPC. No raw
native EventQueue route, no old replay subsystem, and no mutable state reconstructed
from client packets.

## 7. Attachment, catch-up, ACK and bounded retention

Replacement invalidates that seat's old attachment's choices/preview/new commands
and stream ownership, but admitted work finishes. Other seats are unaffected.
Receipt lookup remains seat-authorized across
replacement. The new attachment receives pending IDs/next number and a catch-up
sequence. Gate new commands from that seat until initialization and its catch-up
boundary have been consumed/ACKed; do not suspend another seat's turn or native AI
for an inactive seat's catch-up. If an operation was in flight, extend the affected
barrier to include its recorded result. When the native turn requires an absent
external controller, wait for its owner with no automatic AI takeover or end-turn.

New page: initialization then all retained operations. Same attachment after a
transport break: request `after=last_consumed`, not last received or displayed event.
The SDK advances this cursor only after its awaited consumer succeeds. Browser
Last-Event-ID is not an application ACK. The stream contract specifies atomic
spool backfill/live handover, acquisition retries and one socket per attachment.
Duplicates are ignored by sequence before reduction; a gap, wrong epoch, unsupported
schema or invalid fact stops the consumer visibly. No silently skipped envelopes.

ACK is monotonic and bound to game/attachment. It cannot exceed the greatest
contiguous sequence sent to that attachment (initialization counts as zero), nor
release data from another epoch. For live consumers it means “validated, atomically
reduced and retained as needed”; for explicit recording consumers “validated and
safely retained for cold replay.” A recorder does not claim a current game replica.
Neither means “animation finished.” Highest-sent/ACK survive socket reconnect within
the attachment; resend a lost ACK without re-applying the operation. `after` is not
an implicit ACK. A page refresh rebuilds from recorded public bytes; it does not
ask the engine to reperform previous commands.

Use explicit bounded configuration, with conservative initial limits checked against
the full corpus rather than unlimited containers:

| Resource | Initial limit / policy |
|---|---|
| Mutations | One pending/executing; excess new requests refused, retries return the existing receipt |
| Query work | One active worker request plus one latest unsent query per configured seat, globally byte-accounted; supersession never cancels another seat's request; unauthorized/out-of-turn query cannot replace active discovery |
| Preview cache | At most 128 entries and 8 MiB per discovery; LRU eviction, invalidated with exact native discovery dependencies |
| Command request | 256 KiB encoded JSON maximum; native collection bounds still validated |
| Initialization/query/public operation | 64 MiB maximum encoded UTF-8 JSON per complete record, inherited from pipe ceiling; decoded heap amplification measured separately; corpus must prove fit |
| Delivery cache | 128 MiB aggregate per game, allocated on use; exact spool supports replay after cache copies are dropped; never hold workspace/global lock waiting on a socket |
| Receipts | Per seat: 4 MiB or 1,024 terminal entries, whichever comes first; pending pinned; keep its high-water number after eviction; account aggregate actual use |
| Public record spool | 1 GiB configured quota per audience, initialization included; aggregate disk reservation/accounting; retain active history, terminal history until explicit close or 24 hours; no silent prefix eviction |
| Private stderr | Existing bounded 64×1,024-byte recent buffer plus explicit failure artifact; no unbounded in-memory log |
| Headless consumer | 128 MiB working/pending record budget; reduce+ACK promptly, optional evidence output to bounded disk |

These are initial ceilings, not targets for normal packet size. Report actual
p50/p95/max bytes. Maximum-size JSON may have unacceptable parse latency; the corpus
must establish normal/hard limits before Gate A closes. Reserve recording capacity
for the audience set and one bounded shared encoding workspace before mutation.
Stage audiences sequentially instead of allocating N maximum-size buffers. Ensure
aggregate disk availability as well as per-audience quota; a race/I/O failure after
native mutation remains fatal and publishes none of the incomplete batch. Query output
oversize has an explicit limit failure, no incomplete choice list or silent truncation.
No public-operation fragmentation or checkpoint subsystem is added to escape an
unmeasured limit. Actual resource admission is explicit, not a hardcoded seat count.

The spool is the exact public recording, not an additional rules journal. Use a
length-framed sequential file plus bounded sequence→offset metadata, not a database.
Partial batch writes never publish its audience sequences; same-process failure
keeps earlier committed prefixes inspectable. No fsync-based native crash-recovery
guarantee is asserted. Logical recording quota pauses at a boundary with
`recording_capacity` status. ACK only advances that seat's delivery credit; memory
cache eviction is safe because spool history remains. Resume after retention expiry is
explicitly unavailable; no fake fresh initialization from hidden latest state.

Record native retained EventQueue/history growth separately. These budgets bound
transport/working state and do not claim constant total native memory.

## 8. Public contract and causal/privacy audit

Preserve the current PlayerInitialization/PlayerLineage/observations/world updates,
actor versions, HUD and original combat-log values. One public schema source, finite
discriminated fact union, strict supported versions. An operation envelope carries
game epoch, audience, sequence, resulting state revision, own command reference when
applicable, lineages, admitted content additions, HUD/log appends and native boundary status. Do not add a second
state snapshot feed that competes with reduction.

Eventless preference changes still need a recorded after-value. Extend the existing
controlled-character HUD sheet with detached handler preferences obtained from
`Entity.get_player_toggleable_handler_infos()`; reuse its passive handler descriptor,
without invoking full action discovery just to build this sheet. Capture them at
initialization and relevant operation boundaries. The next choices query agrees
with that value. No artificial native Event or new condition is needed for toggling
a preference. Version this public addition explicitly.

`AvailableHandlerInfo` currently lives beside executable types in base_actions.
Move that one passive descriptor and its identity validation to an existing suitable
leaf such as `dnd/core/action_types.py`, retaining its base_actions re-export for
existing callers. Both the HUD and discovery import the same definition. Do not
make public facts/cold reduction import EventQueue/BaseBlock/aoe through the new
field, and do not duplicate the descriptor to avoid the dependency problem. This
small split is required for the new contract; it is not a broad query-DTO rewrite.

Provide one operation-application helper alongside the existing public reducer to
apply admitted content additions, then ordered lineages plus operation-end
HUD/standalone-log values, including when lineages are empty. Initialization seeds
the permitted catalog in the same passive PlayerState; saved public recordings retain
its exact PUBLIC seed/revision for cold replay. Server, Python consumer and replay
call these same functions. Sequence validation belongs to the receiving envelope boundary;
the pure reducer accepts existing passive values and does not import player_server.
HUD ordering must distinguish operations sharing a native event cursor. The operation
sequence/state token supplies that boundary; do not discard an accepted update because
its event cursor equals the previous one. Cold replay must prove H18/H22 explicitly.

For every exported field document its source, viewer grant and reducer consumer.
The audit includes nested values, not only visible actor IDs:

- Actor/equipment/inventory/condition/source references: controlled-party private
  details versus merely observed enemy appearances are different grants.
- Sight/hearing/current/explored contacts and remembered terrain: merge authorized
  observations before projection. Selecting the other hero never changes audience.
- Unknown attacker/hidden source: retain witnessed effects without leaking identity,
  location, item names, reaction owner or unobserved intermediate geometry.
- Native cursors/lineage version ordering: preserve disclosed occurrence identities
  and project audience-local order through the existing projection state; private
  native counters are not public coordinates. Update all related references and
  the public schema together, with no transport rewriting or causal flattening.
- Event-time names/known dead actors: retain remembered identity without inventing
  current visibility. Death/turn-end/log use recorded identity, not live lookup.
- Standalone log and HUD-only changes: operations with no visible lineage can still
  carry legitimate state; do not drop them or fabricate a damage/event root.
- Cancel/reaction/nested/parentless links and repeated A/B/A applications: identity
  is occurrence-based; no grouping by target name or identical text.
- Movement/doors/traps/forced movement/summon/despawn/item ownership: enough recorded
  facts for cold reduction after native registries have been reset.

Preserve actor-specific physical range/LOS/permissions even with party knowledge.
P18/P26 knowledge-aware movement must use the last authorized recorded supports and
object states; unknown live blockers cannot alter preview and reveal hidden changes.
Actual step execution still checks reality and records a genuine interruption.
This belongs to native discovery/navigation validation, never a host-side map copy.

No broad condition/spell redesign. Existing condition suppression/lifetime semantics
and recorded damage/roll arithmetic must survive serialization. Visual log layout is
future UI work. Native text repairs for retained identity and hidden-count
protection are required here in the existing log formatter/projector; correct values, identity and causal grouping are server obligations.

## 9. Independent verification harness

Three lanes use one small case/check helper each. The production SDKs are shared
transport code, not a second test-only client framework:

1. **Application lane:** real small native scenario, exact discovery/preview/command
   APIs, detached authorized results. No network. Reset/close registries and RNG
   after each case; preserve existing complete subscribers/capture behavior.
2. **Network lane:** launch actual host and child, use both production SDKs, select
   actions from disclosed identities/indices, await receipts/sequences, reduce+ACK.
   Tests never call route functions as their HTTP proof. Fast route validation can
   use FastAPI TestClient separately; actual SSE/process behavior needs a live socket.
   A few raw wire checks remain independent of SDK assumptions. TS records exact
   public bytes with a bounded recording consumer; Python applies the existing
   extracted reducer outside its standalone SDK.
3. **Cold public replay:** retain exact public bytes from either SDK, stop/reset native engine, decode
   and reduce them with no private Session/Event registry. Assert permitted state,
   world, inventory/resources, sequence and log outcomes. No renderer dependency.

The probe sends only ordinary public commands. Fixtures/seeds are installed before
launch through private test composition, never exposed as HTTP debug/reset routes.
Selection helpers choose content IDs/variant facets, not English display text or
fixed stale indices. The harness does not become a new combat AI: authored scripts
and native AI drive scenarios. Timeouts bound failures; successful progression waits
on explicit replies/events/status, not guessed sleeps or animation duration.

RNG tests may use the existing fixed-dice context in private scenarios to prove
specific outcomes. Live launch has no seed override. Compare actual die size, faces,
modifiers and selection once; do not add flaky distribution tests or improve rolls.

Reuse existing feature cases from `test_session`, `test_player_selection_contract`,
`test_party_audience`, `test_player_hud_boundary`, projection/lifecycle/item tests
and worker tests. Separate pure fixtures/assertions from mixed renderer modules;
do not import `test_player_projection` wholesale when it imports animation assets.
Use `HOW_TO_TEST.MD`: observable outcomes, not private call counts/mocked collaborators.

### 9.1 Required case matrix

| ID | Input / scenario | Observable proof |
|---|---|---|
| H01 | Start fixed crypt without frontend/art directories | Ready initialization/content/choices; distinct child PID; no graphics initialization |
| H02 | Invalid configured scenario/content | Startup failure with incident; no partially ready game |
| H03 | Two isolated test hosts with separate small encounters | No registry/map/event/party interference |
| H04 | Bootstrap/schema encode-decode/cold reduce | Explicit versions, complete passive records, no executable templates |
| H05 | Wrong seat/actor, old game or old attachment | Typed rejection; no spending or private disclosure |
| H06 | Discovery and repeated preview | No rules/RNG mutation; exact detached retained values, correlation echoed |
| H07 | A/B/A Magic Missile and partial allocation | Actual ordered applications follow native completion rule; one resource spend |
| H08 | Up-to recipients, unique recipients, illegal excess/extra target | Proper native allocation; bad direct submission rejected and worker remains usable |
| H09 | Ordered wall points, summon positions, entity destination | Exact prefix/next positions; no endpoint reordering or host geometry |
| H10 | Self ability/potion, depleted spell, rank/form choices | Self command executes directly; unavailable choice cannot spend or open a fake operation |
| H11 | Open two doors, ally occupies passage | Updated native route; ally transit allowed, occupied landing rejected |
| H12 | Preview selected safe path then execute | Every uninterrupted committed step equals preview; legitimate interruption is an explained prefix |
| H13 | Party split rooms; known corridor loses sight | Shared authorized knowledge survives actor switch; remembered movement without hidden-blocker leak |
| H14 | Teammate sees target, caster lacks required LOS/range | Knowledge does not grant illegal spell execution |
| H15 | Edge-door contact and window/lever/chest/pickup | Existing native interactions/contact rules, no server reach/path workaround |
| H16 | Equip/unequip/drop/loot coated or enchanted item | Identity, property, charges and item-location facts persist; no duplicate holdings |
| H17 | Haste potion after companion loses sight | Controlled poses/party/resource/condition values retained; cold replay agrees |
| H18 | Reaction preference toggle without native event | Application/state revision changes; old discovery rejected; updated toggle visible |
| H19 | Identified enemy moves past a doorway/LOS edge; opportunity attack kills it before its turn ends; paired nonlethal and unseen-death cases | Observed attack, lethal damage/death and turn-end retain the same known identity after contact loss; no “Unknown” rename, invisible destination disclosure or refresh from the live entity. Unobserved death is not inferred. Zero-HP actors receive no unauthorized human command window; cold replay preserves the same log |
| H20 | AoE/save/resistance/temp HP/death and conditional expiry/suppression | Exact recorded facts and dice/math; no dropped cause or revived expired effect |
| H21 | Summon→initiative→despawn, hostile concentration-loss case | Existing control/faction/lifecycle facts preserved through public bytes |
| H22 | Log/HUD-only or canceled operation | Appropriate payload/revision retained; cancellation not a harmless preflight rejection |
| H23 | Reply lost after command reservation/commit; repeat same identity | One native execution, one spend, one public operation; retained result returned |
| H24 | Same command number, different payload | Conflict; no second execution |
| H25 | New valid-shaped but stale command then retry | Stable rejected receipt, number consumed once, unchanged native state/RNG |
| H26 | Schema-invalid input or busy admission | No reservation; next valid number still usable |
| H27 | Replace attachment while a command is in flight | Admitted work finishes; old attachment cannot submit; new one obtains receipt and catches up |
| H28 | Disconnect before ACK; reconnect after last reduced | Exact duplicate-safe contiguous replay; no rerun of mechanics |
| H29 | ACK beyond sent/other epoch/old attachment | Rejected without releasing capacity |
| H30 | Slow reader/cache full, then valid ACK | Reader backpressure remains bounded; another seat's turn and health/status remain responsive; exact spool replay loses nothing |
| H31 | Fresh page after many operations and after terminal result | Initialization plus exact retained records rebuild current permitted state |
| H32 | Public record quota / missing retained history | Explicit capacity/resume-unavailable; no silently missing outcomes |
| H33 | Controlled private test fault in execute/capture/spool/worker | Failed session, incident and unknown/failed command outcome; no success or automatic retry |
| H34 | Explicit shutdown while starting/executing/terminal | Bounded cleanup, no orphan process/thread or false saved-game claim |
| H35 | Many legal hover prefixes / repeated discovery | Bounded retained preview cache, stable correct subsequent execution |
| H36 | Hidden source and nested private fields | Wire bytes obey grants; hidden operations do not generate gratuitous public envelopes |
| H37 | Interleaved query/mutation requests and late query result | Exact revision binding; no stale index rebound or canceled committed work |
| H38 | Unsupported schema/truncated packet/consumer reduction failure | Explicit failure; no ACK/skip or partial reduction |
| H39 | Complete crypt exploration→loot→trap→goblin fight→terminal | Public driver completes encounter; all operations captured; final public replay/log agrees |
| H40 | Required fact-family corpus across current implemented actions | Every exported fact/union member exercised or explicitly scoped with a concrete fixture; not only two demonstration spells |

H33 uses private fault injection at I/O/process seams, not a public error endpoint
or mocks replacing game rules. A worker hang is detected diagnostically; do not kill
and silently retry a spending command because a latency budget was exceeded.

H39 is the end-to-end usability-of-contract proof. H40 is the broader content proof:
reuse native initializations/commands from current action, condition, item, spatial,
summoning, movement and reaction cases. Produce a schema-member→case matrix from
the actual finite contracts. Explicit unsupported outcomes block coverage rather
than disappearing under a successful test count.

H41–H56 in the [stream/SDK contract](SERVER_STREAM_AND_SDK_CONTRACT_2026-10-07.md#6-independent-verification-additions)
are also required: standalone packages, cross-language schema/transport conformance,
cursor waits, attachment/ACK losses, private counters, handover races, shared opposing
Python/TS gameplay, general seat assignments and cleanup.
The complete acceptance matrix therefore has **56 scenario families**, not 56 tests
or a claim that any of them has already run.

### 9.2 Practical commands to implement

These are target entrypoints, **not commands available today**:

```text
uv run --no-sync python -m player_server --encounter encounter.lantern_crypt --port 8790 --seat-file <private-file>
uv run --no-sync python tools/server_probe.py --base-url http://127.0.0.1:8790 --seat-file <private-file> --case crypt
uv run --no-sync python -m pytest tests/player
uv run --no-sync python -m pytest tests/player_server
npm --prefix sdk/player-typescript ci
npm --prefix sdk/player-typescript test
uv run --no-sync python tools/server_benchmark.py --profile engine-recovery --output .runtime/server-recovery/<run>
```

`encounter.lantern_crypt` is the existing default verified in `game/__main__.py`;
validate it against the installed catalog during startup. No new encounter recipe
is authorized by this command.
Both Windows and WSL launch the same source/contracts with their own locked Python
environment. Installation/sync is a separate documented setup step, not benchmark time.

## 10. Gate A work packages, in order

Execution constraint from the human: avoid validation/regeneration loops. Freeze
the substantive schema once, perform one bounded cross-language check, then advance
the application/server implementation. SDK generation runs only for an intentional
contract change; targeted checks follow actual changed behavior or failures. Reviews
apply to completed independent work packages, not every small edit. No duplicate
SDK game model/reducer or additional validation framework.


| Step | Concrete changes | Exit evidence |
|---|---|---|
| A0 | Use the concrete schema/source package: closed roots, field ledger, producer/log variants, semantic rules and current captures. Settle intentional owner deltas before runtime work | 314 definitions/1,612 fields; all 28 current fact variants captured. Proposed shape and runtime proof remain distinct; no opaque log fallback or SDK generation project |
| A0b | Implement typed logs, retained identity and causal privacy, duration/handler/preview fields at their existing owners; update direct consumers in the same change | Same projector/reducer/formatters; no API shadow types. Require owner-export parity with the settled schema and focused behavioral regressions, including door-edge OA death |
| A1 | Extract bounded application closure; generalize seat/controller composition, common capture and per-audience admission; move log ownership out of discovery; retain neutral content/selection | Headless grouped/single-entity seat cases; shared functions; actual import DAG/startup audit |
| A2 | Add application revision and pure native command admission; bound preview cache; close required native functional defects | H05–H22/H35 and direct invalid-submit regression; no broad exception swallowing |
| A3 | New host/worker lifespan, status, strict finite API, startup/content/schema output | H01–H06/H26/H34; health/status responsive during a real native request |
| A4 | Seat-scoped receipts/attachment/ACK, independent streams, exact-byte spool, private complete-audience batch staging and aggregate capacity | H23–H38/H54/H56 plus raw-wire races; no extra rules store or hidden audience union |
| A4b | Standalone Python and TS SDKs: generated JSON types, validation, finite async API, commit-safe follower and cursor waits | Installed-package isolation; H41–H52 transport/contract cases; no second game reducer or handwritten probe transport |
| A5 | Complete crypt, simultaneous opposing Python/TS scripts in one game, languages swapped, grouped and per-entity seats, cold reduction and fact-family corpus | H39/H40/H51/H53/H55; all H01–H56 families covered; compare each private view to its own expectations |
| A6 | Anti-slop + ECS/DAG independent server implementation reviews | Close findings; record exact source/tests and Gate A report; no performance completion claim yet |

Review independently completed boundaries as they land so later packages do not
build on broken ownership. Engine corrections already required by P01–P31 stay
bounded to the existing domain owner. Do not use an API workaround to make a case
pass. No UI/rendering work is smuggled into A2/A5.

## 11. Gate B: engine speed investigation and iteration

Instrumentation exists from A, but optimization starts after Gate A establishes a
correct complete path. Measure the actual installed server, not a stripped engine
with capture, reactions, logs or senses disabled. Separate three runs:

1. Unprofiled end-to-end latency/bytes/memory distribution.
2. The same workload with stage timers and a targeted cProfile capture.
3. Focused allocation/tracemalloc investigation only for confirmed growth, because
   allocation tracing itself distorts timings.

Store profiles, packet recordings and traces under `.runtime/server-recovery/`;
commit only compact source fingerprints, summary tables and issue dispositions.
No massive JSON logs or assets enter Git. A report identifies command and sequence,
native seed/private fixture, actor/loadout/position/content identities, event count,
root count, history length, offered actions/targets and emitted bytes. UUID generation
is independent of ordinary random.seed; compare semantic outcomes with identity
correspondence, never strip causal links or assert unrelated random runs are equal.

### 11.1 Stage timing contract

| Stage | Measure separately |
|---|---|
| Process/startup | Host imports, child launch/imports, content bootstrap, encounter construction, initialization capture/projection/encode, first legal human boundary |
| Host intake | Request validation/authentication, queue wait/admission, transport readiness |
| Discovery | Native candidate/variant expansion, target/path generation, permission/cost filtering, detached-copy/serialization |
| Preview | Key construction/cache lookup, exact prefix/native predicate/geometry/next choices, return-copy/serialization |
| Native mutation | Root action/AI decision, handler/subevent/senses/spatial work, resource/item/turn updates |
| Capture | Root collection, history/lineage indexing, event-time actor admission, copied recorded facts |
| Projection | Audience authorization, observed actors/world, conditions/items, public node/value generation |
| HUD/log | Permitted sheet/resources/compatible slots, standalone append projection |
| Wire/storage | Worker serialization, pipe transfer/decode, final envelope encode, spool append, SSE write and probe parse/reduction |
| Retained state | Native events/registries, discovery/preview, projection/reducer, receipts/delivery cache/spool, per-operation allocations |

Reuse `dnd/action_timing.py` where useful: its callback receives a start timestamp,
not elapsed duration. Compute elapsed correctly. Existing path-cache timing omits
some key construction and copying, so retain complete top-level timers. Never sum
overlapping inclusive profile totals as separate costs. Transport queue wait and
backpressure time must not be reported as engine execution time.

### 11.2 Investigation ledger: established work versus suspected cost

| ID | Evidence now | Measurement / possible repair owner |
|---|---|---|
| E01 | Existing bounded imports ~2.9 s Windows/~4.5 s WSL in earlier receipt | Fresh/warm start decomposition and import graph; remove accidental imports/repeated initialization inside existing owners, no late-import camouflage |
| E02 | `capture_lineages` rebuilds full latest/version indexes from event zero, even with no roots | Equal commands at short/long history; existing EventQueue indexes/incremental capture state, preserve historical version references |
| E03 | `_capture_actor_admissions` traverses history again per root | Many roots/party contacts; incremental event-time actor/admission state within current capture owner, not reading current entities |
| E04 | `EventQueue.get_event_index` is linear and sensory code calls it | Count/size/cost attribution; extend the existing event-index owner if dominant, no second journal |
| E05 | Every discovery recomputes and dump/validates detached data | Native versus detached-copy cost, actual request rate; reuse only under full mutation/knowledge/actor/mode dependencies |
| E06 | Preview cache return copies and validates values again | Miss/hit latency and allocation; preserve detached immutability and bounded cache |
| E07 | Every operation constructs full party HUD/compatible slots | Inert update versus equipment/resource change; bounded evaluated facts with exact dependency if warranted |
| E08 | GridMap has revision/perception/collision keyed path caches, then copies results | Cache hit/miss, key cost, copied steps and safe-path pass; improve existing path owner only |
| E09 | Entity navigation examines path steps for knowledge/hazards | Large explored map, ally corridor, hidden blockers; preserve subjective rules and committed prefixes |
| E10 | Earlier measured inert tile publication recomputed sight; provisional fix exists | Revalidate current guard and all optical/topology/occupancy changes; no dropping sensory/world after-values |
| E11 | Handler/condition/senses/AoE/AI work may dominate selected cases | Profile actual broad/condition-heavy/reaction chains before choosing native fixes |
| E12 | IPC/public JSON validation, encoding and copies remain unquantified | Bytes versus CPU; encode immutable published output once, avoid redundant passes with demonstrated contract safety |
| E13 | Retained events intentionally grow; working state may grow unintentionally | 100+ operations: distinguish retained history from stale caches/listeners/temporary references; cleanup existing owner |
| E14 | Audience fanout is new planned composition; cost unmeasured | Compare grouped, mixed and per-entity seats; separate once-only native/common capture work from per-view admission/reduction/encoding and socket backpressure |

Source observations do not establish time dominance. Earlier Fireball native samples
around 177–223 ms and controller peaks around 321–330 ms were bounded diagnostics,
not current percentiles or proof of a broad regression. Do not copy those as new results.

### 11.3 Benchmark corpus and methodology

- Fresh start and repeated warm start on each supported environment. State exactly
  whether OS filesystem cache is warm; “fresh process” is not automatically cold disk.
- Full crypt journey with both heroes, doors/ally passage, loot/potion, traps, combat
  and AI. Include all projection and logging.
- Repeated unchanged discovery and changing equipment/resources/party knowledge;
  preview prefixes, unavailable choices, ordered allocations and form/upcast variants.
- Small melee/ranged attacks, Magic Missile A/B/A, Scorching Ray, dense Fireball and
  a wall/summon/condition/reaction workload drawn from current native fixtures.
- The same action in controlled comparable states at ~100, ~1,000 and ~10,000 retained
  events; report new events/roots so real additional gameplay work is not mistaken
  for history overhead. History preconditioning is private fixture work.
- Map/actor/action/condition scaling using supported native fixture dimensions and
  current creature types; vary one factor at a time. Include the largest existing
  acceptance scenario, rather than inventing an arbitrary MMO load requirement.
- Network disconnect/catch-up and a slow reader separately from engine throughput.
  Probe promptly ACKs during engine measurements; slow-reader delivery stalls are
  intentional, but must not stall another seat's native turn while recording has room.

Run at least 100 samples for claimed p95/p99 warm operation distributions and 10
fresh-process starts per configuration, report sample size and maximum. Short rare
operations with fewer samples are reported as individual/min/max observations, not
stable percentile evidence. Repeat paired comparisons with identical semantic inputs
and recorded normalizations. Compare source/content/lock/environment hashes each run.

Use a 15-minute or longer mixed run containing at least 100 native operations for
retained/working memory, cleanup and late-history latency. The probe is allowed to
wait between scripted actions to measure retention; do not pad latency samples with
that wait. Separately run a maximum-throughput sequence without pacing.

### 11.4 Optimization loop and anti-slop constraints

For each E row: reproduce cost → measure owning stage/call tree → propose the smallest
owner-local repair and invariant → add/retain an observable regression → compare the
same workload → review source/boundary → keep or revert based on evidence. Update the
ledger with measured issue, cause, exact fix, before/after, tradeoff and status.

No new cache without explicit key, invalidation, byte/entry bound and cold/hit tests.
No turning off capture, logs, rules, reactions, observers or content validation to win
benchmarks. Do not lower roll/target/event fidelity. Do not move CPU mechanics into
the host's async loop. Do not add more worker threads around globally mutable rules.
Fix reuse/indexing/algorithm costs first where measurements justify them.

Every source suspect receives measured-issue, below-budget/not-dominant, intentional
retention or unresolved-with-reproducer status. “All issues” means no known reported
problem silently omitted; it is not a claim that no unknown defect can exist.

## 12. Acceptance and deliverables

Initial carried-forward budget targets, measured on the user's native Windows host
and separately on WSL; not promises about unknown deployment hardware:

| Boundary | Target |
|---|---|
| Warm server ready at first human boundary | <=5 s; fresh-process/cold-read target <=10 s, excluding uv installation |
| Ordinary command through recorded public result | p95 <=250 ms, maximum <=500 ms |
| Dense Fireball through recorded public result | p95 <=1 s, maximum <=2 s |
| Ordinary native AI decision through capture | p95 <=500 ms, maximum <=1 s |
| Warm discovery and preview, measured independently | p95 <=100 ms each |
| Host health/status while native child works | p95 <=50 ms locally, maximum <=100 ms |
| Working caches/receipts/live queue after 15 min/100 operations | Bounded by declared limits; native/spool retained growth reported separately |

Report engine-only execution as well as complete operation latency. Queue/backpressure
and network RTT have their own rows. The first set of command budgets prevents
regression; it is not an instruction to stop investigating a confirmed avoidable
bottleneck merely because the total is below the threshold. No frontend FPS target
is asserted by a server-only benchmark.

Final artifacts:

1. New launchable host and isolated native application boundary; no old server import.
2. Versioned closed JSON/OpenAPI schemas and complete initialization/operation/error
   examples, with private diagnostic fixtures kept private; standalone Python wheel
   and TS package generated from the same contract, with usage and cursor examples.
3. SDK-backed probes, simultaneous opposing-script encounter, application/network/
   cold-replay tests and H01–H56 map; no arbitrary seat cap.
4. A recorded public crypt run reducible after native shutdown; no client installed.
5. Stage timings, E-issue dispositions, baseline/comparison fingerprints and concise
   performance report. Large traces stay outside Git.
6. Anti-slop and ECS/DAG implementation reviews at Gate A and Gate B, findings closed;
   user-facing distinction between server complete and later client integration.

Plans/tests alone do not prove completion. Gate A must run the real server; Gate B
must show comparable measurements. General UI study and graphics problems remain
in the parent plan and are not declared fixed by this work.

## 13. Plan review status

Two independent local reviewers approved the initial server plan, the server/SDK
expansion, and separately the general-seat and same-encounter test amendment. Both
found no remaining blockers in their planning review scope. The
[review receipt](audits/server-plan-20261007/PLAN_REVIEWS.md) records corrections
and exact approval scope, including the new SDK/privacy gates. This is approval
of the plan; the A0 schema-completeness deliverables remain to be produced before
runtime implementation. This document does not claim any new tests,
implementation or benchmark results from this turn.

## 14. Startup follow-up — measured model compilation, October 7

The human rejected approximately four seconds on native Windows and requested an
exact diagnosis. This supersedes treating the original five-second budget as
acceptance. The API remains implemented; startup performance remains open.
The [detailed measurement receipt](audits/server-implementation-20261007/PERFORMANCE.md#detailed-startup-diagnosis--october-7-follow-up)
separates module/schema loading, explicit catalog checks, materialization, host
imports, garbage collection and first-use work. This amendment began as a bounded
proposal backed by disposable-process experiments. The user approved implementation;
S1–S4 are now complete as recorded below.

**Observed cause.** Importing the full built-in module closure defines 1,059
Pydantic models, rebuilding schema machinery across 36,778 field entries. The
explicit catalog registration/check/digest step takes 11.29 ms, not seconds.
Neither step spawns every content entity. Ordinary static imports and single native
types remain required; selecting a validator-build policy is a separate decision.

**S1 — existing behavior roots only.** Add Pydantic's supported `defer_build=True`
to the existing `BaseAction` and `BaseCondition` model configuration, retaining
all current configuration, fields, defaults, validators, serializer behavior,
registry participation and typed inheritance. Do not change BaseObject, BaseBlock,
value/controller/event/public model policies. Do not change content declaration
imports, catalogs or metadata validation. The diagnostic candidate reduces median
worker-ready time 3193.37→1904.84 ms over three fresh processes each; this excludes
the host/network and is not yet a production result. The same experiment explicitly
includes protocol schema preparation and the existing pre-Start GC policy.

**S2 — unchanged observable behavior.** Use existing real engine/application
fixtures to check first construction and first execution of ordinary actions,
spell child conditions, reaction handlers and summons; retain normal validation
failures for malformed values, exact provider bindings and cold subjective replay.
Run the existing broad native capability corpus (including Shield/Counterspell,
Fireball, Wall of Fire and summon/control-loss), shared application/server tests
and a single canonical public-schema digest comparison. Add a regression only if a
real observed boundary fails. Do not regenerate SDKs if the public digest remains
unchanged; no private completion-flag assertions as a substitute for gameplay.

**S3 — startup and first-use acceptance together.** Repeat the existing complete
fresh-host startup measurement on native Windows and WSL with the same fixture,
reporting listener, human-ready and consumed-SDK boundaries separately. Measure
first discovery, preview and first command for the three spatial-spell fixtures,
including schemas first constructed at that point. Repeat the existing
1,000-command natural-GC lane, with first-use spell samples separately included,
because post-Start schemas are not in the frozen import graph. Preserve enabled
runtime GC, collectibility and flat transient registries; never freeze live world
state or disable GC to recover an old latency number. Report residual work instead
of declaring success from import speed or the old five-second ceiling.

**S4 — independent review and bounded decision.** Anti-slop and ECS/DAG reviewers
must inspect the actual two-owner configuration change and S2/S3 evidence.
Reject the candidate if schema/validation/registration/replay semantics change or
first-use/GC regressions outweigh the measured gain. Keep the existing eager policy
if rejected; do not add a second schema registry, warming scheduler, serialized
callable cache, adapter family, blanket ClassVar conversion or lazy-import system.

**Secondary finding, not folded into S1.** The host imports some native machinery
through `AvailableActionsResult` in `core/base_actions.py`; host-only instrumented
import is 520 ms after Pydantic setup, only part of which is avoidable. A later
passive-type extraction must preserve the private retained execution-template
binding used by `action_dispatch.py`, `actions_functional.py` and Entity discovery.
It may not duplicate the public DTO, replace the binding type with Any or create
circular/late imports. No full solution or additional saving is asserted for that
split in this diagnosis; it needs its own concrete design before edits.

The two local independent reviewers approved this final amendment and the
corrected diagnosis without blockers. Approval covers the scoped plan, not its
implementation or future performance result; S2/S3 evidence remains required.
Their review scope is recorded in the performance receipt. No frontend or artwork
work is included.

## References

- [Parent architecture](NETWORK_SERVER_NEUROCLIENT_STUDIO_PLAN_2026-10-07.md)
- [Existing recovery evidence](audits/PLAYER_PLAYTEST_IMPLEMENTATION_2026-10-06.md)
- [Playtest/native requirements](PLAYER_PLAYTEST_RECOVERY_PLAN_2026-10-06.md)
- [Testing policy](../HOW_TO_TEST.MD)
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/): application resource lifetime.
- [FastAPI concurrency](https://fastapi.tiangolo.com/async/): async I/O is distinct from CPU parallelism.
- [HTTPX async/streaming](https://www.python-httpx.org/async/): independent HTTP/SSE driver building blocks.
- [Python subprocess](https://docs.python.org/3/library/subprocess.html): child process and stream lifecycle.

### §14 implementation acceptance

The approved first solution is delivered: only the existing BaseAction and
BaseCondition model configurations gain `defer_build=True`. **212 existing tests**
pass; 17 native scenarios exercise 40 subjective views. The unchanged public
schema needs no SDK regeneration. Twenty fresh hosts satisfy §11.3's ten starts
per platform; Windows human-ready mean is **2756.77 ms**, WSL **4995.88 ms**,
with maxima **3389.59 / 5514.48 ms**. First-spell discovery/preview/command costs
are reported separately, including small possible command increases. Ordinary
1,000-command consumed p95/max is **37.50/56.91 ms**. Separate natural-GC evidence
preserves enabled GC, unchanged thresholds, post-Start collectibility and flat
native registries; no live world is frozen. All 25 hosts/workers exit successfully.
A separate process cold-replays **50 prefixes / 8,623 records / 2,150 commands**.

Both [anti-slop](audits/server-implementation-20261007/ANTISLOP_REVIEW.md) and
[ECS/DAG](audits/server-implementation-20261007/ECS_REVIEW.md) independently accept
the actual source and evidence. The [production measurement receipt](audits/server-implementation-20261007/PERFORMANCE.md#approved-first-startup-fix--behavior-schema-deferral)
records exact scopes, source fingerprints and residual costs. This closes §14,
not all Gate B workloads. Further host-type extraction or other optimizations
remain outside this accepted change.

## 15. Avoid repeated engine loading across games — feasibility and bounded design

The human asks whether successive games can avoid paying native import/schema
startup again. **Yes: retain loaded workers and reuse each sequentially.** This
section is the proposed lifecycle change, not a claim that production already
reuses processes. It extends the preceding one-game-per-process assumption only
at the game boundary; one worker still owns at most one active native world.

A disposable native Windows probe ran five games in one imported process through
existing `worker.start`, initial encoding/shared reduction and ordinary advancement.
Imports cost 1373.04 ms, protocol/pre-Start GC another 186.20 ms. First game native
readiness took 248.37 ms; four subsequent games took **217.77–225.32 ms**.
Close/reset/full collection took **29.08–31.63 ms**. This is a small four-goblin,
two-seat fixture, not HTTP readiness or a production warm-worker benchmark.
Evidence: `.runtime/server-recovery/warm-worker-feasibility-20261007/`.

The probe exposed a real prerequisite: `reset_engine_runtime` clears the existing
object/value/entity/controller/encounter/event/map/behavior-scope owners, but does
not clear `Dice._registry` or `DiceRoll._registry`. The probe retained 4, 8, 12, 16,
then 20 old dice/roll records across successive resets. Fresh actor identities and
53 initial events per game do not establish complete isolation. Do not simply
keep the existing pipe open and describe that as safe reuse.

### Required owner changes

1. **Native reset, `dnd/runtime_reset.py`:** finish cleanup at the existing owner,
   including dice/roll registries; inspect registered condition hooks, event
   pre-completion systems, summoning/AI callbacks and live references. Keep installed
   immutable content, definitions and completed Pydantic schemas. Drop all old
   session/capture/discovery references before collection. Do not invent a parallel
   engine-reset path, clear imported modules or freeze a used game graph.
2. **Private worker lifecycle, `player_server/worker.py` and `worker_protocol.py`:**
   support explicit end-game/reset acknowledgement followed by another existing
   typed Start. Close remains process shutdown. Expected typed command rejection keeps its
   current behavior; uncertain mutation, pipe state or failed cleanup retires that
   worker. Never recycle uncertain state or retry its mutation. End-game
   acknowledges only after cleanup. Retain the one-time pre-Start import-GC policy;
   normal runtime GC stays enabled. Reuse installed content rather than repeatedly
   bootstrapping the identical set. Preserve the normal RNG path; private test seeds
   cannot accidentally determine a later unseeded game's random stream.
3. **Process ownership, `player_server/connection.py` and `host.py`:** a long-lived
   server owner retains idle loaded connections and lends one exclusively to each
   game host. Return it only after acknowledged cleanup. Simultaneous games use
   separate workers. Increasing concurrent capacity or replacing a failed worker
   requires a cold process; subsequent games on existing healthy capacity do not.
   Shutdown awaits all owned workers. No forked live world, shared global worlds,
   second event bus, gameplay execution in the HTTP host or arbitrary seat cap.
4. **Hosting boundary, `player_server/app.py`:** the current application has one
   configured Host and no game-creation endpoint. Reusable workers need a server-
   lifetime owner above individual Hosts. Specify its private game creation/end
   entry points and exclusive leasing before production integration. Preserve old
   games' existing public recordings/retention and in-flight client readers even
   after their native worker is released. Every new game receives fresh epoch,
   audience/attachment/revision identities and clean command numbering. No old
   credentials, queued queries, receipts or publications can enter the next game.
   This does not authorize a public lobby/admin API, accounts or SDK schema redesign.

### Acceptance and review

The observable acceptance is two or more independent games served successively by
the same long-lived service without repeated native imports, with correct fresh
state/private streams and retained replay of the previous game. Exercise actual
attacks/dice, conditions/summoning/AI, different seat configurations, old-handle
rejection and a failed-worker replacement; prove no cross-game callbacks, entities,
rolls or discovery state remain and that retired game objects become collectible.
Measure first cold startup, warm cleanup/new-game readiness, retained memory and
normal command latency separately. Reuse the current protocol/reducer/SDK checks;
no generation loops or unrelated rendering work. A finite repeated-game cohort
must show flat post-cleanup ownership rather than claiming safety from a single
successful restart. Keep startup numbers scoped to the measured map/workload.

Both the **anti-slop reviewer** and **anti-OOP/ECS/DAG reviewer** must review this
lifecycle design before production edits and the implementation/evidence afterward.
The probe establishes feasibility and identifies reset work; production reuse and
its full service boundary are not implemented by this study.

### §15 independent feasibility review

Both local reviewers approve this direction as feasible, **not as a complete
implementation approval**. Their concrete findings are part of the next design:

- `dnd/ai/runtime/subjective_projection.py` has an adjacency cache keyed only by
  coordinates and map movement revision. A new map can reuse the same revision;
  call its existing `clear_subjective_projection_fact_cache` at the application/AI
  lifecycle boundary. Also clear the existing actor/item-bearing decision caches
  through `clear_epoch_value_caches`. Keep AI cleanup above native reset in the
  import DAG; do not make core reset import higher-level application code.
- Fence the worker lease: finish pending exchanges/publication, perform acknowledged
  cleanup, detach the old Host's connection, then reassign. Old queries, cancellation
  or shutdown must not reach or close a worker already serving another game.
- Pin each worker to its installed immutable content set. A changed content set or
  executable version uses a replacement process rather than mutating cached schemas.
- Define worker capacity/idle retention and aggregate retained-game recording budgets
  at the service owner. Per-game quotas alone do not bound a long-lived service.
  These are operator resource limits, not a fixed player/seat limit.
- Memory checks must separate legitimately retained completed schemas from old live
  worlds. The human-controlled seeded probe cannot establish AI or RNG isolation;
  include differently shaped maps and an unseeded game following a seeded fixture.

No native or server production code was modified during this feasibility study.

### §15.1 Implementation contract — server-lifetime reuse

The human authorized completion. Keep this as a private hosting change: no new
player endpoints, public types, protocol version or SDK generation.

- `player_server/workers.py` owns a bounded set of connections. Acquisition leases
  one exclusively; capacity waits are bounded by the service's admitted game count.
  Release sends `EndGame(game_epoch)` through the existing framed protocol and waits
  for an empty reply acknowledging that epoch. Failed, cancelled or uncertain
  exchanges close the process. Idle workers are retained up to the operator limit.
  Shutdown wakes waiters and closes idle workers after game owners have stopped.
- `worker.py` accepts Start only while idle and EndGame only for its active epoch.
  Close still exits. EndGame closes the session, drops runtime and response locals,
  clears native registries through `reset_engine_runtime`, clears the existing AI
  caches above the native layer, then collects before acknowledging. Content installs
  once per process. Every Start seeds the RNG from its private test seed or fresh
  entropy. `gc.freeze()` stays exclusively at process entry before the first world.
  Deployment changes replace the service/workers; no hot code/content reload.
- `host.py` remains the only owner of serial game exchanges. An operator end request
  stops new input, rejects queued queries and lets an already admitted command finish.
  It then resets/detaches/releases the connection and exposes a closed final cursor.
  Natural terminal and failed games also release their native worker. Old public
  prefixes, receipts, attachments and audience identities stay with that Host for
  the existing 24-hour retention. Reset completion has an awaitable signal; shutdown
  or ending that old Host cannot touch a worker leased to a later game. Cancellation
  during an exchange discards the worker and marks an uncompleted command indeterminate.
- `player_server/service.py` owns Hosts plus the worker set. Private Python functions
  prepare/start a configured game, end its native session, and shut down the service.
  `create_app` starts its configured initial game and exposes this private service
  for deployment composition. Later games use the same listener and routes. Each
  request resolves its own Host/Seat from its bearer credential; streams capture that
  Host permanently. Game IDs and bearer tokens must be distinct among retained games.
  HTTP configuration (CORS) is service-wide. No gameplay decisions move to this owner.
- Private `ServiceLimits` defaults: four concurrent workers, two retained idle
  workers, 64 active/retained games, and 64 GiB total reserved recording capacity.
  Operators can configure all four. Recording reservation is each game's existing
  per-audience quota multiplied by its audience count; admission fails before allocating
  a game if the aggregate budget is unavailable. Expired Hosts free their reservation
  on the next admission. No automatic early eviction of readable game history and no
  entity/seat count limit. This bounds storage and retained metadata across games;
  existing per-game query/delivery limits remain unchanged.

Validation is finite: native cleanup/collectibility after real spell/summon/AI
activity; service tests for sequential reuse, simultaneous isolation, old-reader and
credential isolation, pending input, failed-worker replacement and shutdown; a
repeated-game timing cohort through the production service; existing transport and
SDK/replay tests once after the final change. Report first cold start separately
from warm reset/start, and leave existing broader engine-performance limits explicit.
The two independent reviewers review this contract before implementation and the
actual changes/evidence afterward. New-client implementation remains the next phase.


### §15.2 Review corrections carried into production

Both local reviewers approved §15.1 before editing. Their implementation review
caught four real lifecycle gaps, all repaired at the existing owners: ended
capacity waiters must not later Start; cancelled/failed/unstarted games still own
recording expiry; storage reservation is released only after deletion succeeds;
and cancellation of shutdown or retirement cannot abandon a native child. An
explicit acquisition flag distinguishes waiting for capacity from a detached
worker awaiting EndGame ACK. Repeated end requests are safe. Focused tests use real
workers and delay only the private I/O boundary for the retirement race.

The native AI cleanup also clears the existing semantic-input cache because its
keys contain item identities. The public application now invokes the existing
`dispatch_available_action` instead of calling its lower-level implementation
directly. This closes an architecture check without duplicating action rules.
Static checks recognize that exact application consumer and the two existing
passive imports (action ID validation and condition-duration values). The ECS
reviewer explicitly approved these narrow corrections. No new action, spell,
renderer, public endpoint or SDK type was introduced.

### §15.3 Completion and next-phase boundary

Implemented and accepted by both independent reviewers on October 7. The final
production-service cohorts complete 32 games on two platforms, reusing one worker
per platform. Ten ordinary warm games average **217.77 ms Windows / 208.27 ms WSL**
to human-ready, with separate **32.38 / 30.92 ms** cleanup. These timings exclude
host imports and do not replace the full cold-service measurements in §14.
Separate cold replay accepts 62 prefixes, 747 records and 191 commands. Source
fingerprints, lifecycle tests, SDK checks and both final review verdicts are in
[the closure receipt](audits/server-implementation-20261007/WARM_WORKERS.md).

The server/API/shared application/SDK functionality phase is complete and is a
usable foundation for the new client. Broader largest-map and dense spell/native-AI
performance distributions remain explicit engine follow-up, not silently completed
Gate B requirements. No frontend migration, public lobby/account system or durable
whole-world save/load across service restarts is included in this completion.
