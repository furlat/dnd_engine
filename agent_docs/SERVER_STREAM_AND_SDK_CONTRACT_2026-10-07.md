# Player stream and Python/TypeScript SDK contract

**Implementation receipt:** [server implementation, verification and remaining limits](audits/server-implementation-20261007/IMPLEMENTATION.md). The sections below preserve the approved design; their original planning-status paragraphs are historical. The production schema is now exported from its owners, not the former design overlays.

2026-10-07. Normative detail of the [server implementation plan](SERVER_IMPLEMENTATION_AND_ENGINE_PERFORMANCE_PLAN_2026-10-07.md), not another implementation track. Planning only. The human explicitly added both SDKs, cursor following and unrestricted seat counts following actual entity assignments, including opposing Python/TS scripts in one encounter. No frontend, graphics, UI or old omniserver migration is included.

## 1. What the old stream actually was

Verified on `feature/server-is-coming-back`, initially clean at `40eb37b9b4cac72ea75d00d7b1545a4e48a5d2a2`:

- `server/event_server.py:/replication/subscribe` produces `text/event-stream` through `StreamingResponse`, with a subjective backfill/live subscription. It is SSE over HTTP, not a WebSocket.
- `sdk/typescript/src/subjectiveClient.ts` uses streaming `fetch`, supports cancellation, reconnects and awaited consumer updates. `subjectiveSse.ts` checks identities and ordering. Those are useful behaviors to preserve, not a mandate to copy the implementation.
- The old contract tracks source-event, observation, presentation and combat-log watermarks. Its top-level SDK also exports objective diagnostics, directory APIs and old reducers. `devtools/generate_typescript_sdk.py` imports the old server and native Event models. Those dependencies are excluded from the new player packages.
- No corresponding Python SDK was found under `sdk/`. The existing Python runtime pipe is not a network SDK.
- NeuroClient's `app/src/engine/eventStream.ts` also waits on presentation/FSM readiness. The new SDK must not import that client machinery or require animation to finish before accepting data.

Retain **HTTP commands/queries + one SSE subscription for an authorized party**. New envelopes carry the current captured player facts, including causal subevents and original log data. There is no objective player route, separate combat-log stream, or animation-state stream to keep synchronized. A future transport replacement should not change the domain contract; building a second WebSocket transport now is out of scope.

## 2. Exact authority and disclosure boundary

The seat credential resolves server-side to a game and its assigned controlled-group audience. Neither a query parameter nor the selected UI character can choose the observation audience. Actors controlled by one seat share their authorized knowledge; their individual physical senses/range still govern native legality. Different seats do not automatically share knowledge merely because they are human-controlled or have the same faction. "Private" means this player's permitted information, including witnessed enemies/environment, not just fields on the player's own characters. The default crypt still groups Fighter/Sorcerer under one seat, but that is configuration, not a server limit. Section 5.2 defines the general assignment and two-language match.

The worker freezes common native causal evidence at event time, then admits/captures/projects the authorized result for each configured audience using the same functions. Current capture is already audience-filtered, so one seat's captured lineages cannot be reused as another's input. Only each detached authorized result crosses its own public boundary. HTTP choices, previews, errors, status, initialization, static descriptors, recorded downloads and SSE all obey the same authority. Client-side filtering is never a privacy measure.

| Data | Disposition |
|---|---|
| Controlled actors' inventory, charges, spell slots, conditions and reaction preferences | Authorized private party facts, not a world-wide inventory dump |
| Enemy currently observed | Only disclosed appearance, actions and other admitted facts; no automatic full character sheet or hidden equipment |
| Remembered enemy/terrain, including known dead actor | Retain last admitted identity/state with its existing knowledge semantics; do not refresh from the unseen current entity |
| Unknown cause with a witnessed impact | Publish impact and permitted causal relation; withhold undisclosed source identity, equipment and intermediate trajectory |
| Parent/child events and version references | Reference disclosed nodes or explicit unknown/unavailable cause; no dangling hidden node IDs, counts or debug class names |
| Native EventQueue position, raw source index, hidden dispatch ordinal, global log index | Private. Project public ordering through the existing audience projection owner, not through HTTP rewriting |
| Registered content definitions | Explicit public catalog policy, independent of which hidden monsters are instantiated; never derive a descriptor list from secret encounter contents |
| Map extent and discovered tiles | Disclose only the configured public extent and admitted tiles; secret room/object inventories are not bootstrap metadata |
| Exceptions/profiling/source traces | Private diagnostics. Player receives bounded typed code and opaque incident reference |

Do not publish an operation, advance an audience sequence, or rotate its public state token solely because invisible native activity occurred. Native scheduling still proceeds; its private revisions are not a public clock. Authorized turn/boundary/own-command outcomes may justify a public operation even without visible lineages. No promise to hide every network timing side channel is made; no explicit hidden-event counter or payload is acceptable.

The existing nested `VersionRow.source_index`, lineage start/end cursors, HUD revision, log index/end cursor and nested sensory ordering must be audited together. The decision is settled: **wire ordering is audience-local**. Maintain its mapping in `dnd/player/projection.py`, preserve disclosed occurrence identities and ordering, and give all public references to the same occurrence the same coordinate. An operation sequence is not a replacement for subevent/version order. Version the public player schema for this change; keep historical private-record compatibility outside the live decoder. H18/H22 must distinguish eventless updates even with no new occurrence index.

The [concrete field ledger](server-api-v1/field-ledger.json) lists reachable exported fields, source owners, grant policies, omission rules and consumers; the [semantic contract](server-api-v1/semantic-contract.md) specifies nested privacy and temporal invariants. An unclassified field blocks schema release. Paired fixtures that differ only in wholly unobserved activity must give equal normalized player payloads, sequences and errors at the same authorized boundary (normalization only for nondeterministic opaque IDs). Deliberately test log, preview, causal references and remembered-world leaks, not merely top-level actor lists.

## 3. Public transport records and versioning

Use one finite Python protocol definition in `player_server/protocol.py`, referencing existing extracted public facts/query records. Keep worker-only requests/replies in `player_server/worker_protocol.py`; test seeds, Advance, private gaps, elapsed times and Close are not reachable from the exported player roots. Routes reference these exact public models. One explicit export root list emits a closed JSON Schema bundle and OpenAPI; no recursive import of every native Event or old-server model.

The bundle includes bootstrap, attachment, initialization, status, choices, preview, command, receipt, ACK, content, typed errors, stream-ready/status/operation and cursor records. Give it protocol version 1 and a deterministic schema digest. Separately version the player-fact schema; record its next exact version at A0 after the audited field changes. Supported version+digest must match at bootstrap and stream-ready. Unknown version/tag/required field or malformed record is a hard contract failure. There is no automatic legacy upgrade in the live SDK.

All transport ordering numbers are nonnegative integers limited to `2^53-1` in the schema, with explicit capacity failure before overflow; UUIDs/revisions are opaque strings and coordinates retain signed values. No NaN/Infinity, coercion of numeric strings or binary raster payloads. Native JSON dictionary-key/tuple/enum conversion is specified in the schema, with fixed examples for positions, optional/null fields and variant unions. Generated static types do not replace runtime validation or semantic checks.

Public examples in `sdk/conformance/` cover each root and every operation fact family. The bundle carries only safe fields, even if Python definitions used to build it have private attributes. Construct and validate the authorized typed value at its existing projection owner, then encode it once. Never concatenate an unfiltered native dictionary with public data. IPC, recording, live SSE and reconnect reuse those exact bytes; they do not require another decode/validate/re-encode trip at each trusted hop. Validation errors must strip Pydantic's echoed input/context and internal class/stack details.

### Bounded verification; no SDK regeneration loop

The human explicitly rejects an SDK/tooling validation treadmill. Finish the field
contract from the real source and captured outcomes, then move to shared application
and server work. The SDKs are thin generated declarations plus HTTP/SSE following.
Run one bounded Python/TS schema-conformance pass after the contract is settled and
one scripted opposing-SDK encounter when transport exists. Regenerate declarations
only when a deliberate contract change requires it; rerun only checks affected by
that change or an actual failure. Do not alternate full regeneration, whole-suite
runs and repeated approval gates after every edit. No speculative SDK framework,
second reducer, general validator language or packaging project. Review at meaningful
completed boundaries. Capture evidence supports engineering decisions; a checklist
is not an independent workstream.

### Completeness gate before host implementation

Freeze the required information with real captured examples before implementing routes and SDK following. Coverage must be bidirectional: exported fields/unions→cases **and existing capabilities/consumer requirements→required fields→cases**. Generate the field inventory from the selected public root closure and join it to this requirement matrix, the parent authoring-coverage ledger and H01–H56. Record source owner, authorized capture point, field path, absence semantics and consuming code for each row. Coverage must include **all currently implemented content families**, not only the crypt or a successful first spell. An unrepresented implemented outcome blocks A0; do not add an arbitrary metadata dictionary, renderer lookup into the server, or per-spell exception to get past it.

| Required information | Existing basis / required disposition |
|---|---|
| Legal action identity and availability | `AvailableActionInfo`: exact discovery index/generation, actor, stable content/provider refs, availability reason, costs and restricted budgets; private executable templates stay retained in worker |
| Upcast, wall shape, summon creature, element and other choices | Existing variant facets, spell/cast levels, position-selection union and source-item fields; ordered choices use the retained native row, never parse display names |
| Repeated/partial/multi-position selection | Allocation completion, count/repetition policy, secondary pools, exact input prefix, effective recipients and next candidates; distinguish complete versus incomplete prefix |
| Route/impact preview | Native geometry, elevations, selected safe/normal route, actual cost and affordable endpoint, admitted hazard/OA exposure and affected targets; the existing preview lacks explicit selected-route/cost fields, so extend that native DTO before freezing |
| World interaction and inventory | Observed verbs/contact positions/connectors; ownership, location, stacks, equipped slots, charges, coating/enchantment/suppression after-values and compatible slots; no separate inventory state service |
| Actor rendering identity | Existing appearance/loadout/scale/pose-contact/elevation/life facts; enough to choose authored rig/material keys without live native Entity reads; no pixels or renderer code in server |
| Attack, spell and per-application resolution | `AttackFact`, `SpellFact`, application/propagation refs, object versus creature target, source item, positions/heights and ordered results; no target-name grouping |
| AoE shape versus disclosed result | Continuous geometry and `resolved_area_positions` remain separate; empty disclosed cells do not become a physical VFX mask; retain `AreaReachFact`/structural prerequisite links |
| Normal, forced, fly/jump/fall and portal movement | Movement/step/forced/portal/shove facts with trajectory, committed path, endpoints/elevation/layer and interruption; root and substeps preserve causal order |
| Damage/heal/save/temp HP/life | Actual recorded results, source membership, roll/save evidence, before/after and death/save/remains disposition; no reconstructed dice or guessed outcome |
| Conditions and items | Application/removal/source cause, duration/suppression and presentation state, provider membership, item effects and handler preferences; eventless changes retain operation-end values |
| Reactions/cancellations/concentration | Admitted causal tree, reaction trigger and outcome, cost-spent cancellation, occurrence/version order and permitted source attribution; filter hidden ancestors without inventing public ones |
| Spatial effects, surfaces, traps and destroyable structures | Existing world/spatial-effect/mechanism/object-damage/destruction unions and admitted geometry/state; exact lifecycle updates sufficient for cold reduction |
| Summon/despawn/faction/initiative | Existing manifestation/departure/faction/turn/control facts and updated authorized order; no client-created entity or initiative algorithm |
| Subjectivity and exploration | Party audience, event-time grants, seen versus remembered contacts, lighting/perception and controlled-body retention; no objective refresh on selected-hero switch |
| Combat log and eventless HUD | Original structured dice/modifier/outcome entries and causal association, known identities, resources and preferences; one operation carries lineages plus standalone appends/HUD |
| Presentation authoring references | Stable public content IDs and permitted configuration/geometry facts are present; release cues, hand anchors, palettes and material operators remain in the separately authored client catalog |

The inventory must distinguish fields already supported, owner-local additions required (currently selected preview route/cost, recorded handler preference and admitted content additions), fields needing privacy remap, and genuinely nonapplicable fields. "Optional" must have a domain meaning; it is not permission to omit difficult data. A0 settles the exact next player-schema version/digest, complete root closure, required/default/null/error variants, every semantic validator's disposition and generator conformance before A1 extraction or host/SDK behavior implementation. A0 is contract authoring and proof, not a promise to discover those details during A4b. Its examples exercise every selected fact union member and semantic validator, then A5 reruns them through the actual transport. Schemas will still be versioned for future features; this gate prevents knowingly incomplete current-content schemas. The [schema/source package](server-api-v1/README.md) now provides these concrete design artifacts and current capture evidence. Runtime owner parity, causal privacy regressions and HTTP/SSE behavior are implementation checks; shape validation alone does not certify them.

One concrete content leak must be repaired: `game/ui_content_composition.py:ui_content_manifest()` currently lists every registry declaration without filtering `ContentVisibility`. New immutable static content exposes only PUBLIC descriptors. OBSERVED descriptors become admitted `content_additions` using the existing `ContentDescriptor` value in initialization/operations when the audience is first entitled to them; include referenced permitted descriptor closure in that same operation, before its fact consumer needs the IDs. INTERNAL/DEVELOPER descriptions and hidden instances never cross this path. Projection tracks which content identities/versions have been disclosed. The **same shared public reducer** seeds the permitted catalog at initialization and applies additions before lineages/HUD/log; it retains that passive catalog in `PlayerState` for server, Python consumer and cold replay. No other registry, reducer or stream is added. Public catalog digest excludes secret definitions, and refs never allow fetching a descriptor that was not public/admitted. Reuse the descriptor's existing visibility semantics; do not infer policy from class names. Exact PUBLIC seed bytes/revision must accompany a saved recording (or be available as an immutable local artifact); cold replay cannot depend on a still-running HTTP content endpoint.

### 3.1 Authentication and access

Both SDKs use an injected base URL and seat credential supplied at runtime, carried as `Authorization: Bearer …`. The TS SDK uses **fetch streaming**, not native EventSource, so it can set that header and explicitly own reconnect. Browser requests use `credentials: omit` in this phase; no cookie/session platform is introduced. Never bundle a token in JS, generated data, source control, localStorage, URL or logs. Browser credential provisioning is future UI work; the headless SDK accepts the credential directly.

Use loopback by default. For Windows host/WSL caller or a later browser dev origin, configure the actual reachable address and an explicit CORS origin allowlist with the required authorization/attachment headers. No wildcard credential policy or insecure external deployment claim. Tests include an allowed browser origin and refused origin; CORS supplements authentication, it does not replace it. Reject redirects in authenticated SDK calls to prevent accidentally forwarding credentials. Every game-scoped route, including content/schema access where appropriate, is authenticated. `/healthz` remains minimal public liveness.

Game/epoch/audience/attachment bindings accompany requests as typed fields/headers; `after` is only an audience sequence and not a credential. Server-generated links are relative known API routes, never arbitrary fetch destinations.

### 3.2 Attachment acquisition and subscription

Acquiring an attachment is explicit; ordinary socket reconnect does not replace it. Request fields include a random acquisition ID and the expected prior attachment epoch (`null` only when none exists). In one serialized host step, compare-and-swap that expectation, issue the epoch and retain the current acquisition result. Retrying the same acquisition ID and logical request returns that result. A different payload conflicts; a request naming a retired expected epoch cannot displace a newer attachment. Thus losing the HTTP reply cannot accidentally replace the just-created connection repeatedly. Expose the current opaque attachment epoch to the authenticated seat in bootstrap/status so deliberate takeover can name it. No unbounded attachment journal.

An attachment response carries the initialization reference, current catch-up barrier, next command number and pending identities. New attachment starts with no assumed consumer state. Initialization is sequence zero and has the same game/epoch/audience/schema identity as operations. The initial boundary may still be starting/advancing; client-ready-for-command requires the later authorized human boundary and catch-up ACK.

Only one live SSE connection per attachment. Reopening after a transport break closes a lingering older socket under host serialization without changing the writable attachment. It does not cancel accepted commands. The host tracks this privately rather than adding another public game revision.

## 4. Cursor following and atomic backlog/live handover

`PlayerCursor = {game_id, game_epoch, audience_id, sequence}`. Attachment epoch is a request credential binding, not part of recording identity. A cursor from a different game/epoch/audience can never be used to resume or satisfy a wait. Only the sequence orders published operations. Native occurrence/version coordinates inside an operation serve causal reduction and are never SSE resume positions.

| Position | Meaning |
|---|---|
| published | Last complete authorized operation committed to the server spool |
| received | Last complete envelope decoded/validated by this connection; not safe recovery progress |
| consumed | Last contiguous operation whose awaited consumer callback completed safely |
| acknowledged | Last consumed cursor confirmed by the server ACK response; may lag after a lost reply |
| displayed | Application-owned playback position; not tracked or waited on by the SDK/server |

For a live consumer, completion means the whole operation reduced atomically and needed history retained. For a headless recording consumer, it means the full validated record is successfully retained for cold replay; this mode does not pretend to have a current gameplay state. SDK transport cannot infer game-state application. Its wait is named `wait_for_cursor` / `waitForCursor` and means **consumed**, never animation finished. A future UI owns any separate display barrier. Do not create another SDK game-state reducer or reinterpret facts into generic messages.

### 4.1 Opening the stream

1. Authenticate and validate the requested game/epoch/attachment and `after` against retained history and sent bounds. A fresh attachment first fetches and accepts initialization. Sequence zero is a real accepted boundary, not "no state". After its consumer successfully accepts initialization, explicitly send/retry **ACK(0)** before waiting for any operation; otherwise a head-zero catch-up barrier could deadlock command admission. Failed initialization consumption sends no ACK.
2. Under the same host lock used to publish, capture the current public head H and register a wakeup for later commits. Do not yield network I/O while holding that lock.
3. Send `event: ready` with protocol/schema identity, requested `after`, H and the current authorized catch-up barrier/status. No SSE `id` on ready/status. Replay exact recorded operations `after+1…H` from the spool.
4. Continue reading the same spool from H+1 as commits wake the subscriber. Wakeups signal "new head", not another copy of operation data; every read rechecks committed head, so a coalesced wakeup cannot lose records.
5. Every operation uses `event: operation`, `id: <sequence>`, and a single JSON `data` value followed by the terminating blank line. The body identity/sequence must agree with the ID. Whole-operation delivery only; no split causal trees or independently committed HUD/log feed.

At a fixed heartbeat interval (initially 15 seconds), emit a bounded typed `status` record with public lifecycle/head/barrier; it does not advance consumed sequence. Terminal/failed/closed/replaced status is sent promptly when known. `ready.head` is not a replacement initialization and never causes a jump in consumed cursor. Finish terminal replay before closing a terminal stream. HTTP status polling remains available if no stream is connected.

Terminal/failed/closed games have a frozen final published head F once in-flight work is resolved or failed. Announcing that status stops new mutation admission immediately but does not cut off already committed history. A late authorized attachment can initialize and follow the retained prefix through F while the host/retention remains available. The SDK consumes that prefix first; terminal then completes normally, while failed/closed returns its typed final reason after the prefix is accepted. EOF after F is expected and does not reconnect. A cursor wait at/below F may finish draining; a wait above F fails immediately. If EOF occurs before F, reconnect only as a transport recovery while history is available; actual host loss/retention expiry returns an explicit interruption. A failed command beyond F has no invented completed result. Replacement/authentication failure is different: it stops that attachment immediately and does not authorize draining a revoked stream.

The stream has no response/proxy buffering or compression that delays dispatch; use `text/event-stream`, private/no-store cache policy and appropriate proxy buffering settings. Each seat attachment has one SSE connection shared by its heroes/log/presentation; independently assigned seats have independent connections. Parsing operates on streaming UTF-8 with chunk boundaries, CR/LF splits, comments and multiline data handled correctly. EOF without the blank-line terminator discards the incomplete event and reconnects from consumed; never "finish" a partial operation as a complete one. Fully delimited invalid JSON/identity/schema stops visibly rather than reconnecting forever.

### 4.2 Consumer commit and interruption

After complete validation and identity/contiguity checks, await the supplied operation consumer **serially**. Supply both validated values and the original UTF-8 operation JSON bytes, so recording consumers preserve exact payloads instead of reserializing them. For our one-line server data records these are exactly the spool bytes; generic multiline input joins data fields according to SSE rules. No overlapping callbacks. Advance consumed and send/coalesce ACK only after success. A callback exception closes the stream, leaves consumed unchanged and escapes to the caller. A live reducer must stage changes then publish them atomically; if it mutates partially before throwing, discard that local replica and explicitly rebuild from initialization. The SDK does not invent rollback.

An exact duplicate at or below consumed is not re-applied. A forward gap, mismatched ID/body, wrong identity, unsupported schema or oversized record stops consumption without ACKing the offending operation. All expected retained operations must remain available; do not auto-bootstrap from objective latest state to repair a gap. Reconnect retries use the last consumed cursor and explicitly resend its ACK if the earlier ACK reply was lost. No auto-increment based on the SSE ID/browser Last-Event-ID.

Example: operation 42 arrived but its consumer failed; last consumed is 41, so resume after 41 and deliver 42 again. If 42 was applied/retained but its ACK reply was lost, consumed is 42: resume after 42 and re-ACK 42, with no second application. A new page holding only "42" but no compatible state/history must acquire a new attachment and rebuild from sequence zero. A saved cursor alone is not a checkpoint or saved game.

Retry only transport disconnect/timeout and explicitly retryable temporary 429/503, using capped exponential backoff (initial 250 ms, maximum 5 s, jitter; reset after a valid stream record). Honor a bounded Retry-After. Unsupported schema, 401/403, replaced attachment, wrong epoch, missing history or consumer error stops and returns a typed reason. Failed/closed game status follows the retained-final-prefix rule above and is never a reason to restart mechanics. No silent credential refresh, takeover, state reset or command reissue. Cancellation closes the HTTP response/reader, aborts timers/waits and releases owned transports; it does not roll back a submitted command.

### 4.3 Delivery limits and receipt following

Apply the main plan's encoded byte limits while reading, before JSON parsing; bound unfinished SSE lines/data too. Count UTF-8 bytes, not JS character count. Encoded bytes do not equal heap size: measure decoded model/validator/copy amplification against the separate working-memory budget. HTTPX and fetch pools permit a long stream plus ordinary queries/ACKs; do not consume the sole connection slot with SSE. At most one pending operation consumer, no unbounded callback/record queue. Optional local recordings use an explicit byte quota; quota exhaustion stops acceptance without ACKing data that was not retained. Async I/O is not permission to allocate an unlimited backlog.

Only one command can be unresolved per seat. `submit_command` never manufactures a new command number after an ambiguous POST timeout. The caller retains the exact logical command, then uses receipt lookup or an explicit identical retry. Committed receipts reference the public cursor covering their outcome; rejected receipts carry a typed reason and have no result cursor. Waiting for a committed command's cursor ensures its result is consumed, independently of later native AI actions. A canceled action that spent costs remains a committed result.

`wait_for_cursor` resolves immediately if already consumed, otherwise awaits ordinary follower progress with cancellation/deadline. Wrong identity, fatal follower failure/replacement or terminal state below the requested cursor rejects it. Disconnect only retries within its configured wait deadline. Keep waiter registrations bounded (initially 64), remove every settled/canceled waiter, and reject excess explicitly. Receipt timeout reports unknown/pending outcome; it must not mark the command rejected or rerun it. The SDK never waits for presentation before permitting a query; the application uses the published authorized boundary and stale-query rules from the main plan.

## 5. SDK packages and dependency direction

Do not add to the old SDK's omnibus exports or break the preserved NeuroClient reference. Build new packages in this repository and install their built artifacts normally; no absolute `C:` or `/mnt/c` dependency in the future client.

```text
sdk/
  protocol/                     generated closed JSON schemas + version/digest
  conformance/                  small shared JSON cases, expected verdicts/cursors
  python/
    pyproject.toml              dnd-player-sdk wheel; no dependency on dnd engine
    src/dnd_player/
      contracts.py             generated TypedDicts/unions for JSON wire values
      validation.py            schema + finite protocol semantic checks
      client.py                async HTTP functions; injected HTTPX transport
      stream.py                SSE decoder/follow/ACK/wait functions
      state.py                 passive config/attachment/cursor/follower records
    tests/
  player-typescript/
    package.json               @neurodragon/player-sdk, ESM + declarations
    src/{contracts.generated,validation,client,stream,state,index}.ts
    tests/
  typescript/                   existing SDK left as legacy reference
devtools/export_player_protocol.py  explicit Python root/schema export
devtools/generate_player_sdks.*     deterministic build-only type generation
tools/server_probe.py               uses the production Python SDK
tools/server_probe.ts               headless TS SDK parity/recording driver
```

The canonical authoring source stays Python: public protocol models plus `dnd/player` fact/query types. Exporting them in build tooling can import their definitions. **The installed SDK runtime cannot import `dnd`, `game`, `server`, `player_server`, pygame, Pixi, or live registries.** Python's generated TypedDict JSON shapes avoid dragging the engine's large nested type tree into a remote client. They are generated transport declarations, not a second hand-authored set of game models. TS uses the same schema. UUID/enum/tuple encoding is wire-native in both packages; native Python dataclass reconstruction happens only in the existing application/replay adapter.

Use established schema tooling rather than write another general schema interpreter: Python `jsonschema` Draft 2020-12 and TS Ajv 2020 for runtime shape validation, configured without coercion/default insertion/field stripping and with matching supported formats. Build-only candidates are `datamodel-code-generator` TypedDict output and `json-schema-to-typescript`. A0 verifies the actual exported union/tuple/ref subset against these tools, pins compatible versions and records any unsupported construct. No hand edits to generated declarations or silent fallback to untyped Any. If a generator cannot faithfully represent a construct, preserve runtime enforcement and document the precise static limitation before release; do not widen the wire contract to satisfy a generator.

Pydantic custom validators are not automatically expressed in JSON Schema. Inventory reachable validators and keep a small explicit shared conformance list for cross-field invariants (identity, sequence, causal references, ordered allocations, costs/record consistency where already public). Native action legality is still server-owned. SDK functions perform protocol checks, not damage calculation, pathfinding, sight, target rules, condition simulation or a second animation dispatcher.

Use plain async functions over passive connection/follower state and the library HTTP client. No Client→Session→World hierarchy, event bus, service locator or universal transport framework. Native exception/DTO classes remain appropriate where existing libraries require them. Split parsing/following files only if clarity requires it; the tree is an ownership guide, not a demand for empty wrappers.

### 5.1 Public callable surface

| Python / TypeScript | Contract |
|---|---|
| `bootstrap` | Authenticate; inspect game/status/version/content and attachment expectation |
| `attach` | Explicit compare-and-swap attachment acquisition with retry identity |
| `get_initialization` / `getInitialization` | Fetch sequence zero and validate identity/schema |
| `get_status` / `getStatus`, `get_content` / `getContent` | Cached authorized status and admitted immutable descriptors |
| `get_choices` / `getChoices` | Exact actor, revision, mode and correlation; no local action synthesis |
| `preview_selection` / `previewSelection` | Ordered index/position prefix unchanged |
| `submit_command` / `submitCommand`, `get_receipt` / `getReceipt` | Explicit command identity; no hidden retry using a new number |
| `follow` | Open/reconnect stream, serial awaited consumer, bounded decode and ACK |
| `wait_for_cursor` / `waitForCursor` | Consumed boundary only, scoped identity + timeout/cancel |
| `close` / AbortSignal | Idempotent local resource cleanup; never closes the game |

`follow` accepts a previously accepted initialization/state plus its consumed cursor, or a freshly initialized sequence-zero consumer. It cannot accept a naked cursor as proof of local state. Follow state exposes read-only identity/positions/status; only its commit function advances consumed. Tests may inject an HTTP transport and clock/backoff for deterministic transport behavior; game-mechanics proofs use the actual server/native worker.

The Python full-encounter probe supplies the existing pure `dnd/player/reduction.py` consumer outside the SDK, using the one operation application helper. The server's projected-state application and the Python consumer call **the same functions**, not parallel implementations:

```text
native operation -> capture/project -> shared Python public reducer -> server's permitted state
public operation -> Python SDK     -> shared Python public reducer -> headless consumer state
saved operations -----------------> shared Python public reducer -> replayed consumer state
```

Only the input boundary differs. Extract and use the shared functions in all three callers; do not copy a special test reducer. This shared-path agreement is useful transport evidence but is not independent proof of the reducer's correctness: native scenario expectations and specific known outcome assertions must also pass.

TS conformance uses a validated bounded recording consumer; feed its saved bytes to that same Python replay path and compare final permitted state/log with the Python run. This proves TS delivery and wire compatibility, **not** a completed TS gameplay-state implementation. The later client phase ports one pure TS reducer, shared by its live play, replay and Studio. It uses the same SDK callback and recorded fixtures; Python execution is not required on the eventual browser. No second Python reducer is added inside the wheel, and no separate handwritten SSE reader is left in the normal probe.

### 5.2 General seat ownership and the shared Python/TS match

**Socket granularity is the authorized audience, not the unit.** One seat controlling Fighter, Sorcerer and any further assigned units opens one SSE subscription. `PlayerAudience.controlled` identifies command authority and `observers` identifies the explicitly granted shared sensory contributors. A one-unit subjective audience is the same mechanism with one member. A team audience combines authorized evidence once before publication; clients do not open N streams or merge them themselves. Team membership is configured explicitly, not inferred from a matching faction. Selecting a different body is local UI state and never changes stream identity or historical knowledge. A future control/observer membership change must publish a required `audience` after-value in the existing operation and rotate its state revision; no separate team feed. Removed observers stop contributing new facts without erasing already admitted knowledge. Physical LOS/range remains actor-specific for action legality.


**No one-seat, two-seat or other artificial player-count cap.** Each externally controllable entity can have its own seat; one seat may also own several entities. Seat count follows actual assignments and physical transport/memory/storage capacity. Do not add a `MAX_PLAYERS` constant or a special two-player server. Socket/runtime resource failures are explicit operational failures, not a game rule. Tests must reach one seat per eligible entity, not stop at two.

At startup, private game configuration maps each seat credential to a nonempty set of externally driven entities and its server-authorized `PlayerAudience`. Bind existing authored roster-slot/member references after materialization, rather than requiring the human to predict generated entity UUIDs. An external entity has exactly one owning seat; duplicate ownership or an actionable external actor with no owner is rejected before starting. Native autonomous actors do not need a network seat. This first implementation uses configured assignments, not an account/lobby/join platform. Faction, seat ownership, native controller and observation audience are separate concepts. Default observers are that seat's own controlled group; broader sharing requires an explicit native grant, never a client-selected observer list. The private host configuration contains bindings/credentials; each SDK process receives only its own credential, never that complete file.

Use existing `HumanController` for all externally driven actors irrespective of SDK language. Native `Encounter` still decides initiative, current actor, reactions, incapacitation and terminal state. No `PythonController`, `TypeScriptController`, second rules world or per-seat engine process is introduced. There is one pending/executing mutation **per game**, because native state is serially owned, not because other seats cannot remain connected or receive data.

### Required control configurations

The human's October 7 examples are configuration cases of that same path, covered
by H55; they are not separate game modes or additional implementation gates.
Here an external controller means a seat that supplies decisions, not necessarily
one native controller object shared by all of its actors.

| Configuration | Assignments |
|---|---|
| One controller for each side | Seat A owns every external actor on side A; seat B owns every external actor on side B. |
| One controller for each unit | Each external actor has a distinct seat, including multiple seats on the same side. |
| One externally controlled side against AI | One seat owns side A; existing native AI owns side B. Exercise the reversed assignment too. |
| External and AI units mixed within a side | A seat owns a subset of side A; native AI owns its remaining allies. Side B may be entirely AI, externally controlled, or independently mixed in the same way. |

Do not equate faction, roster slot, seat or sensory audience. Reuse existing
`RosterControllerDefaults` and `RosterMemberControllerOverride` for native control
mode/policy, and the assembler's `entities_by_member_address` for exact bindings.
Resolve each member's override before grouping controllers. Private seat bindings
authorize those resulting external members; they do not introduce another copy
of AI policy or change a unit's faction. Every active member has exactly one
decision source, and each external member has exactly one owning seat. An AI member
cannot also receive external commands. Native summoned AI keeps its existing
ownership policy and does not acquire a seat automatically.

Observation remains an independent explicit grant: a seat can share an AI ally's
vision without controlling it, or share vision with another seat on its side.
That does not grant the ally's private inventory/character sheet or change the
acting unit's own targeting rules. One seat still uses one audience stream.

H55 uses the same small encounter driver with these assignment rows. Verify native
turn dispatch, command rejection for unowned/AI actors, permitted shared vision,
private HUD isolation, and independent progress when an inactive seat disconnects.
No new SDK variants or transport messages are required for these configurations.

Concrete extraction work, before networking:

- Replace `create_session`'s one/two-player deployment checks and `_create_authored_session`'s single-human/single-AI-slot unpacking with iteration over configured existing roster/controller groups, respecting each member's existing override rather than classifying an entire slot by its default. Preserve the normal crypt configuration. Native AI controllers remain composed and closed through their existing owners; remove the singular `enemy_controller` cleanup assumption where more groups exist.
- Keep one native Session/Encounter. Store passive seat→actor assignments and per-audience projection/latest/catalog/ordering records. Pass the authenticated seat binding explicitly to native application admission and HUD composition. Never swap `session.player_uuids` temporarily, union all human actors into one audience, or instantiate another session to obtain a view.
- Keep **one active-turn discovery cache**, qualified by owning seat, actor, private/application revision and mode. Other-seat/actor queries are rejected before touching it. No per-seat copy of action-discovery logic or unnecessary inactive discovery caches. Query supersession is scoped to its seat; it cannot cancel another seat's active request.
- Current `capture_interval`, `_retained_event` and `capture_lineages` already filter admissions/logs for one audience. Extract an immutable private common context of roots, event/version history and original log/observation evidence once per operation, then reuse existing admission/capture/projection code over that context for each audience. Preserve event-time grants. Sharing a filtered A lineage with B or constructing a union-human public lineage is forbidden.
- `snapshot_player_hud(observer_uuid=...)` currently still iterates all player sheets. Evaluate needed actor sheets once privately, emit only each seat's controlled sheets and its permitted initiative/contact facts. A seat must not learn another seat's inventory/slots/preferences through HUD or status.
- Move standalone-log listener/buffering out of `DiscoveryCache` into common session capture state. One encounter listener retains original detached log plus event-time grants/cause; project separately for each audience before releasing the operation batch. Do not duplicate listeners or use seat A's already-projected log for seat B.

Every seat has its own attachment/CAS, command-number namespace, receipt lookup, query correlation, ACK and socket. Every audience has its own initialization, contiguous sequence, opaque state revision, disclosed occurrence order and exact recording. Command 1 on seat A is unrelated to command 1 on seat B. Published operation command references appear only for their submitting seat. Other seats receive their admitted consequences without the issuer's command number/correlation/receipt. No API exposes a cross-seat cursor map, credentials, pending-command list or hidden active actor. Status has an optional `input_actor_uuid` only when an actor controlled by that seat owns the native external input boundary; `null` does not expose who owns a hidden opposing turn. Revalidate membership and active native control in the worker as well as transport admission.

One common native operation can publish a different payload for each audience, or no payload for a wholly unaffected audience. That is necessary subjective data, not duplicated rules or serializers. Before mutation, reserve required recording capacity for the configured audience set and one shared bounded encoding workspace. After mutation, stage each audience's complete encoded result into its recording; publish the participating heads and own-command receipt together only after every required result is projected, validated and appended. A private batch ID/start/complete message coordinates this; no public transaction service. If any stage fails, publish none of that operation's results, fail the game and retain prior committed prefixes. Native mutation is not rolled back or rerun.

Do not pack N maximum-sized audience results into one 64 MiB IPC reply. Use the existing bounded pipe framing for private batch-start, one complete audience-result at a time, and batch-complete; the host stages bytes before the final commit. This does not fragment a public operation or expose private batch IDs. Only one native batch exists at a time. Sequence→offset indexes select committed records, and incomplete staged tails are never replayed. Initialization for all seats follows the same complete-set readiness rule.

Resource bounds must be aggregate as well as per-record. The main plan's 128 MiB delivery window becomes an **aggregate per-game delivery cache**; exact public spool remains the source of truth. Encode/stage audiences sequentially, stream stored bytes in bounded chunks and release shared workspace before waiting on a slow socket. A seat's ACK affects only its delivery progress. A slow/disconnected seat can resume from retained spool; filling its in-memory delivery allowance suspends that reader or drops cache copies, not the native game or its recorded history. A socket wait must not hold the global host lock or the workspace needed by another seat. Retained spool quota remains configured per audience, with explicit aggregate disk availability/reservations; record total accounting and fail/pause for actual exhaustion, never silently evict a disconnected seat's required history. Entry limits and small per-seat state scale with actual configured assignments; buffers are allocated on use, not N preallocated 128 MiB arrays.

Catch-up gates only that seat's commands. Disconnecting/replacing/catching up an inactive seat does not lock another actor's turn or cancel its query. When native initiative reaches a disconnected external actor, wait for its owner; do not auto-pass, transfer control or install AI. Actual recording capacity exhaustion can pause the shared game at a boundary with a safe resource reason. Summons retain the existing native summon-controller/control/faction policy (currently AI by default), not an automatically created human seat. Death/despawn retains credentials, recorded identity and history even if no owned actor can currently act; avoid live-entity anchor lookups for recovery. Later native control changes invalidate affected grants at a recorded boundary, not through client-side reassignment.

The required gameplay test launches **one real server/encounter and two independent SDK processes**: Python controls one configured group, TS the opposing group. Both subscribe simultaneously with different credentials. Scripts act only from their own input readiness, legal discovered rows and preview facts; they do not call native functions, use the other side's targets, or rely on an objective coordinator to decide moves. Private setup may make installed opposing roster groups externally controlled using existing controllers; it creates no new content or rules. A harness may launch processes, install deterministic private fixture setup and collect evidence, but cannot advance turns or submit actions on their behalf.

Exercise actual movement/obstruction, gaining/losing sight, attacking, spell selection and damage, reaction/turn changes, invalid inputs, resource spending, a reconnect with lost reply/ACK, and a native terminal outcome. Scripts remain authored finite scenarios, not a new AI. TS can drive commands from authorized discovery/status and retain operations without implementing a shadow rules/state reducer. Repeat with SDK languages swapped. Replay each stream through the shared Python reducer and assert **that audience's** expected state/log. Opposing streams should differ where knowledge differs; equality between them would be a leak, not a success. Independent native outcome assertions verify the shared game's final state without giving those private assertions to either script.

## 6. Independent verification additions

H01–H40 in the main plan remain mandatory. Add these acceptance cases to the same matrix; SDK tests alone cannot establish server authorization. H53 is the same-encounter gameplay proof; H51's separate-run language conformance is not a substitute.

| ID | Observable proof |
|---|---|
| H41 | Python wheel and TS packed package install/run outside engine/client checkouts; no forbidden runtime imports or absolute local dependency |
| H42 | Both decode the same valid/invalid schema corpus and reject unknown versions/tags; ordered duplicates, signed coordinates, Unicode and exact safe integer limits agree |
| H43 | Actual SSE through both SDKs: split UTF-8/CRLF, multiline fields, comments, incomplete EOF, oversized line/event and fatal fully-delimited malformed payload |
| H44 | Publish during backlog→live handover; every authorized operation consumed exactly once, no omission/second journal, ready does not advance consumed |
| H45 | Initialization at head zero sends/retries ACK(0) and permits first command; consumer blocked/fails, lost ACK reply, exact duplicate, forward gap and async callback exception never ACK past consumed data |
| H46 | Wait for own committed receipt cursor while AI publishes later operations; late terminal/failed attachment drains final prefix F, below-F waits resolve and above-F waits reject, no terminal reconnect loop; timeout/cancel/wrong-audience/replacement and bounded waiters |
| H47 | Attachment response lost and identical acquisition retried; old acquisition expectation cannot steal newer attachment; lingering same-attachment socket closed |
| H48 | Hidden activity and secret inventory/door changes do not leak through counters/log/errors/previews/nested identities/catalog digests; PUBLIC and admitted OBSERVED descriptors available, INTERNAL/DEVELOPER absent, witnessed consequences still arrive |
| H49 | Runtime credential injection, allowed/refused Origin, authenticated SSE, rejected redirects and no secrets in public records/errors; Windows host/WSL real network smoke |
| H50 | Command POST reply lost; both SDKs retain logical identity and recover receipt without a second spend; no automatic takeover or fresh-command retry |
| H51 | Both SDKs record the same scripted native outcomes; cold replay after engine shutdown agrees, no native calls made by installed client packages |
| H52 | Stop/reconnect repeatedly, slow consumer, background/no reader and byte quota; no leaked HTTP streams/tasks/timers/waiters, server remains responsive |
| H53 | Python and TS simultaneously control opposing groups in one game/epoch through native initiative to terminal outcome; swap languages, replay each audience against its own expected facts |
| H54 | Same command number on distinct seats works independently; cross-seat actor/discovery/receipt/ACK/attachment/correlation reuse is refused without disclosure or interference |
| H55 | All four required control configurations above, including AI allies and independently mixed sides; grouped, three-plus and per-entity seats; reject overlap/missing external owner and commands to AI actors; separate rooms/explicit shared vision/private HUD/catalog; death/despawn/summons preserve native control and replay |
| H56 | Inactive seat disconnect/catch-up/slow socket does not block another's native turn; capacity exhaustion is explicit; per-audience append failure publishes no partial batch; sequential IPC staging and aggregate accounting stay bounded |

Use real-network lane and a few raw HTTP/SSE assertions independent of SDK implementation so a shared SDK assumption cannot "prove" a wrong wire contract. Schema generation drift, fixture privacy and build reproducibility are checked from clean output. Source trees/lockfiles/schema digest/SDK versions are recorded with Gate A. Update measured latency to include SDK validation/consumer/ACK separately from native mechanics; do not attribute parse time to rules or promise rendering FPS.

## 7. References and completion boundary

The main plan's A0–A6 sequence incorporates this contract; it is not optional future frontend work. First finish protocol, both SDKs, full headless correctness and independent reviews. Then perform the measured engine-speed loop. Current work changes planning documents only.

- [SSE format and delivery](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).
- [Fetch streaming/cancellation](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch).
- [HTTPX async streaming and resource lifetime](https://www.python-httpx.org/async/).
- [Pydantic JSON Schema export](https://pydantic.dev/docs/validation/latest/concepts/json_schema/).
- [Python JSON Schema validators](https://python-jsonschema.readthedocs.io/en/stable/validate/), [Ajv schema support](https://ajv.js.org/json-schema.html).
- [TypedDict generation](https://koxudaxi.github.io/datamodel-code-generator/), [TypeScript type generation](https://github.com/bcherny/json-schema-to-typescript).
