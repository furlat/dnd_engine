# pygame-ce scripted encounter MVP implementation plan

Date: 2026-08-27  
Status: accepted implementation plan; implementation remains blocked on the
first-principles event-reduction study  
Parent study: `DND_PYGAME_FIRST_PRINCIPLES_CLIENT_STUDY_2026-08-27.md`

## 1. Outcome

Build a new, local, first-principles Python client under a top-level `game/`
package. Running it starts one fixed encounter automatically. The encounter
uses real engine mechanics and real dice, renders with `pygame-ce`, and ends
without requiring a menu, action picker, or other interactive UI.

The first proving encounter has:

- two player-side characters;
- a small enemy side;
- movement, weapon attacks, a spell, and an engine-generated opportunity
  attack;
- real isometric terrain and modular character assets;
- player-side commands that wait for their preceding presentation;
- autonomous enemy commands that may resolve ahead of human-speed animation;
- an explicit pause at the next player decision boundary until presentation
  catches up;
- read-only objective and party-subjective event traces;
- read-only objective and party-subjective combat logs;
- a presentation coverage/receipt trace and structured error artifacts.

The MVP succeeds when one command starts the encounter, the scene plays from
cold bootstrap through an explicit encounter end, the renderer never reads
future or objective-only state, every presentation-eligible event has an
explicit visual disposition, and the terminal presentation cursor catches the
terminal simulation cursor.

This is not a port of Neuroclient. The old client is evidence for useful
behavior and assets only.

## 2. Mandatory ordering decision

This plan must receive two independent exact-candidate acceptances before it
becomes implementation guidance.

After plan acceptance, implementation still does **not** start immediately.
The next required task is a separate first-principles study of event reduction.
That study must define and validate:

1. the objective facts available at each event phase;
2. the event-time observer evidence that authorizes each fact;
3. field-by-field reduction rules rather than whole-event visibility;
4. party knowledge-join and individual-observer semantics;
5. hidden-event ordering and receipts without data leakage;
6. subjective combat-log projection, including nested entries;
7. reduced bootstrap and world-delta contracts;
8. whether reduction is a censorship morphism over one canonical event-view
   space, including its identity, ordering, composition, and party-knowledge
   join laws;
9. the exact immutable stream consumed by presentation;
10. failure behavior when evidence or a reduction policy is missing;
11. tests proving the presentation engine cannot regain objective authority.

That accepted reduction study may amend the reduction-specific portions of
this plan. Any material amendment requires the implementation plan to be
revalidated before the affected slice begins.

## 3. Authority and data flow

There is one mechanics authority and one presentation consumer. The intended
reduction model is one canonical presentation-event space with two projections:

```text
objective projection  = identity/full-knowledge view
subjective projection = censorship using event-time observer knowledge
```

There must not be parallel `ObjectiveMoveEvent` and `SubjectiveMoveEvent`
families. Objective and subjective diagnostics use the same structural view
and formatter, while only the subjective view enters ordinary presentation.

The full flow is:

```text
authoritative Python engine
    -> objective EventQueue versions and encounter combat-log entries
    -> canonical view projection
         -> identity/full-knowledge views for privileged diagnostics
         -> censored party views for presentation
    -> immutable censored event/log batches
    -> game-to-presentation asyncio queue
    -> presentation engine
    -> presentation scene state, animation, text, and coverage receipts
    -> presentation acknowledgements
    -> coordinator decision gates
```

The presentation engine renders from the reduced stream. It does not query
live `Entity`, `GridMap`, `Encounter`, controller, registry, senses, or combat
log state while playing a batch.

The objective event and combat-log panels are a privileged developer trace
forked at capture time. They are not a presentation input. Their data must not
be reachable through the reduced batch or used by scene, animation, camera,
selection, badge, or audio logic.

The objective and subjective displays are two projections in the same view
space, not two authoritative event queues. `EventQueue` remains the only
engine event source.

The canonical view is not literally a mechanics `Event` instance. Current
event subclasses contain authoritative required fields and behavior. Replacing
those fields with `None`, sentinels, or unvalidated values would weaken engine
invariants and make censored objects unsafe to call. The reduction study must
select one generic immutable structural representation that retains dispatch
identity and represents carried facts as known, redacted, or absent without
duplicating every concrete event type.

## 4. Runtime clocks and cursors

The application exposes these identities and cursors continuously:

- `generation_id`: the current `EventQueue` generation;
- `simulation_cursor`: exclusive end of objective events committed by the
  engine;
- `queued_cursor`: highest reduced source cursor successfully enqueued;
- `playing_cursor_range`: source range of the batch currently being presented;
- `presentation_cursor`: highest contiguous source cursor fully disposed and
  acknowledged;
- `objective_log_cursor`: number of captured top-level objective log entries;
- `subjective_log_cursor`: exclusive objective log index through which a
  subjective projection decision has completed, including hidden decisions;
- `decision_actor`: the entity whose command boundary is active;
- `decision_gate`: why simulation is running or waiting;
- `queue_depth` and `queue_high_water`.

Cursors are meaningful only within one `generation_id`. A generation mismatch,
gap, overlap, duplicate acknowledgement, or backwards cursor is a fatal run
error. No numeric cursor from a previous generation may be accepted.

The engine may be ahead of presentation only in complete committed batches.
The renderer must never display the engine's later state before consuming the
corresponding reduced event.

## 5. Minimal process and concurrency model

Use one OS process and one `asyncio` event loop. `pygame-ce` remains on the main
thread.

The MVP needs only two application queues:

1. `game_to_presentation`: ordered immutable reduced batches;
2. `presentation_to_game`: acknowledgements and presentation error reports.

Do not add another event bus. The engine's existing `EventQueue` is the event
source. Diagnostics are passive append-only sinks, not command channels.

The mechanics calls are synchronous and expected to be short. The simulation
coroutine executes one public decision boundary, captures its committed batch,
enqueues it, and yields to the event loop. A worker thread is not justified in
the MVP. If profiling later proves a frame-budget problem, that is a separate
decision.

The first queue may be unbounded because the scripted encounter is finite and
simulation is forced to stop at each player boundary. Nothing may be dropped,
coalesced, or overwritten. Queue high-water and maximum engine lead are
recorded so a later bounded policy can be based on evidence.

## 6. Exact turn-timing behavior

### 6.1 Player side

Both controlled characters use the engine's external `HumanController`
boundary. A small application-side scripted input driver submits their planned
commands.

At a player decision boundary:

1. stop mechanics advancement;
2. wait until `presentation_cursor == queued_cursor` for every earlier batch;
3. resolve the next command against a fresh `get_available_actions(actor)`
   result;
4. match the exact action row and exact stable target role/position;
5. inside one outer `EventQueue.batch_on_event_callbacks()` boundary, execute
   it through `execute_available_action`, then call
   `Encounter.check_deaths()` so the external path receives the same fallback
   death reconciliation and encounter-end detection as the engine-owned
   autonomous path;
6. after that outer batch closes, capture, reduce, and enqueue the resulting
   committed batch;
7. if reconciliation ended the encounter, do not submit another command or
   complete the turn; proceed directly to terminal presentation catch-up;
8. otherwise, wait for that batch's presentation acknowledgement before submitting the
   next command for the same player-controlled turn;
9. after the final command is acknowledged, complete the turn through
   `Encounter.complete_current_turn()` and enqueue its committed batch.

This models the future UI contract: a player cannot issue another command
while the consequences of the previous command are still animating.

### 6.2 Enemy side

Enemies use one minimal scripted autonomous controller. The controller uses
the same fresh action-discovery command resolver as the player-side driver.

For each enemy decision, the coordinator calls
`Encounter.advance_one_controller_action_boundary()`, captures and enqueues the
committed result, then immediately advances the next autonomous decision
without waiting for presentation.

The presentation queue therefore accumulates enemy actions while animations
play at human speed. When the encounter reaches the next external player
boundary, mechanics stops and waits until presentation catches up.

### 6.3 Terminal boundary

The encounter script ends explicitly after all required proving beats. Random
damage is not required to kill a participant. The ordinary encounter-end path
must emit the terminal event.

The application then waits for the terminal presentation acknowledgement,
writes the run summary, and holds the final frame until the window is closed.
A headless verification mode may exit automatically after the same terminal
condition.

No arbitrary sleeps determine correctness. Animation completion,
acknowledgements, and cursor equality are the awaitable signals.

## 7. Canonical proving encounter

The fixture is direct Python scenario data, not a new general scenario schema,
DSL, replay system, or save format.

Use stable encounter-local role IDs:

- `hero_frontline`: player-controlled martial character;
- `hero_caster`: player-controlled spellcaster;
- `enemy_guard`: melee enemy with an opportunity-attack handler;
- `enemy_raider`: second autonomous enemy.

Use durable actors and a short battlefield so live dice cannot prevent later
commands from remaining legal. The fixture fixes initiative before
`Encounter.start_encounter()` through the existing encounter setup contract.
The intended order places autonomous turns between the two player decisions so
the run demonstrates both player gating and enemy run-ahead.

The command script contains only intentions:

- stable actor role;
- expected round/turn boundary;
- action selector based on public discovery fields;
- stable target role, exact target position, or movement destination;
- optional movement path preference already supported by the public action;
- whether the turn continues or ends.

It never contains an event, roll, hit result, save result, damage packet,
reaction, condition delta, sensory delta, animation, or presentation cue.

Required encounter beats are:

1. cold runtime reset and scenario construction;
2. reduced world bootstrap from the engine's world-initialization event;
3. encounter, round, and first turn start;
4. stepwise player movement out of `enemy_guard` reach;
5. an opportunity attack generated by the engine's reaction system;
6. a player weapon attack resolved through fresh action discovery;
7. at least two autonomous enemy decisions enqueued without presentation
   acknowledgement between them;
8. enemy movement and an enemy attack;
9. a spell cast by `hero_caster`, preferably a stable multi-target spell such
   as Magic Missile if the final fixture's public discovery proves it legal;
10. distinct turns for both controlled characters;
11. explicit encounter end and terminal presentation catch-up.

The exact character builds, positions, spell row, and initiative order are
frozen during implementation preflight after running public discovery against
the constructed fixture. If Magic Missile or another proposed row is not
legal, choose the smallest existing legal spell that preserves the spell and
targeting proof. Do not bypass discovery or add content merely to satisfy the
demo.

An optional ordinary dice seed may be exposed for reproducible automated runs.
The normal visual run may use live randomness. The script must be
outcome-independent either way.

## 8. Canonical event-view morphism and presentation boundary

The exact policy and Python representation are deferred to the mandatory
event-reduction study, but this plan fixes the architectural direction.

Reduction should be studied as a structure-preserving mapping over ordered
event streams rather than an ad hoc family of DTO converters. Candidate laws
to validate are:

- the objective/full-knowledge projection is the identity view;
- projection preserves source ordering and causal/lineage relationships;
- projecting a concatenated stream is equivalent to concatenating the
  projections, subject to explicit batch/barrier rules;
- applying the same censorship twice is idempotent;
- party knowledge is the field-wise join of the two controlled observers'
  authorized facts, not whole-event union;
- gaining knowledge may reveal more facts but may not alter already-known
  objective values;
- a hidden event maps to an explicit opaque ordering/barrier result or to no
  player event according to one reviewed rule; it never leaks its payload;
- objective and subjective views share one dispatch/formatting space, so a
  future wire conversion does not require duplicated event model families.

Each `ReducedPresentationBatch` is immutable and contains only censored
canonical views:

- generation and exclusive source cursor range;
- canonical censored event views in source order;
- canonical censored combat-log views keyed by objective log index, with source
  lineage and a stored terminal source event index as optional provenance;
- reduced bootstrap or world deltas carried by those events;
- player/party-safe lineage identifiers needed for ordering;
- projection metadata that does not reveal hidden values.

The presentation engine consumes these views directly. It owns a
cursor-bounded presentation scene model derived only by applying the reduced
stream. `WorldInitializedEvent` is the cold-start source; presentation does not
bootstrap by walking live engine registries.

Reduction is field-specific. Identifying an event does not authorize every
participant name or location in it. Tile surface visibility, tile-content
visibility, entity identity, entity location, independent coordinate evidence,
walls, and visibility beyond a wall remain separate facts.

Event views and combat-log views use the same evidence interpretation and
field-disclosure decisions. Combat-log censorship is not a second policy that
can disagree with the event projection that produced the log.

The party view is the field-wise knowledge join of the two controlled
observers' permitted facts.
Individual-observer projections are retained as developer diagnostics, not as
selection-dependent gameplay perspective.

A hidden source event may produce a source-indexed audit receipt for the
privileged diagnostic overlay. Whether presentation receives an opaque barrier
view or no event at all is one of the reduction study's explicit decisions;
either way, no objective payload or hidden badge enters ordinary presentation.

## 9. Presentation mapping and receipts

For each presentation-eligible reduced event, the presentation mapper chooses
one terminal disposition:

- `ANIMATED`;
- `STATE_CUE`;
- `BADGE_FALLBACK`;
- `INTENTIONALLY_SILENT` with a reviewed reason;
- `HIDDEN_BY_SUBJECTIVE_POLICY` in the privileged projection audit only.

`UNMAPPED` is never terminal. It becomes a visible `BADGE_FALLBACK` using only
the reduced fields. A hidden event never becomes a badge.

Each source index/event UUID/lineage receives one coverage receipt. A child
represented by a parent cue names that parent cue. The receipt records mapper
key, cue IDs, assets, start/end times, terminal disposition, and any error.

The presentation cursor advances only when every eligible event in the
contiguous source range has a terminal receipt and all timed cues required by
that batch have completed or entered an explicit error fallback.

The initial minimal mapping needs only:

- world/bootstrap state application;
- turn/decision text state;
- stepwise movement interpolation;
- idle, attack, take-damage, and death entity clips where applicable;
- static/state changes for conditions and light;
- a spell diagnostic cue or placeholder effect;
- the general reduced-event badge fallback.

Full spell VFX remain later work.

## 10. Read-only debugging surface

The MVP's only UI beyond the animated battlefield is a permanent read-only
developer surface. It has no tabs, buttons, filters, or editable controls.
Window close and Escape are the only required input. Mouse movement may update
the passive grid/elevation inspector.

Reserve a diagnostic rail beside the world viewport:

```text
+------------------------------------------------+---------------------------+
|                                                | cursor / gate / queue      |
|                                                +-------------+-------------+
|                                                | objective   | subjective  |
|            isometric world viewport            | events      | events      |
|                                                +-------------+-------------+
|                                                | objective   | subjective  |
|                                                | combat log  | combat log  |
|                                                +-------------+-------------+
| mouse/grid/elevation inspector                 | receipts / errors          |
+------------------------------------------------+---------------------------+
```

All four streams auto-follow their tail and retain full history in run
artifacts. Recent on-screen rows use a common compact prefix so comparisons are
immediate:

```text
source-index  event-uuid-short  lineage-depth  class/type  phase  summary
```

### 10.1 Objective event trace

Normalize every raw objective event version into the full-knowledge canonical
view, then show those views in source order, including:

- generation, source index, UUID, lineage, parent, and children;
- concrete class, `EventType`, phase, and terminal/cancel status;
- an optional family-specific committed fact where that event family defines
  one;
- objective actor/target/position summary;
- batch/decision boundary.

This is privileged diagnostic data and never feeds the world viewport. The
diagnostic history retains immutable canonical views, not live mechanics
`Event` objects.

### 10.2 Party-subjective event trace

Show the actual censored canonical view delivered to presentation at the matching
source index. Where the source is hidden, the privileged comparison rail may
show only `HIDDEN` plus the audit reason code; it must not show hidden values.
Where fields are partially known, display explicit redaction markers so a
missing name or location cannot be mistaken for a mapper bug.

### 10.3 Objective combat log

Show the engine's structured top-level combat-log entries and recursively
indented subentries. The canonical identity is the monotonically increasing
objective log index supplied by `Encounter`'s passive combat-log listener.
Capture source lineage and event-kind provenance from the listener event, then,
after the enclosing batch closes, resolve a stored terminal event index when
one exists. The terminal index is optional because the callback can occur
during completion preparation, before the stored terminal version exists.
Standalone combat-log entries legitimately have no event-stream index and are
marked `standalone` rather than fabricated into the event stream. Preserve
compact, verbose, and structured data in artifacts; use compact text on screen.

### 10.4 Party-subjective combat log

Show the entry tree produced by the same accepted subjective policy used for
events. It may retain, redact, restructure, or omit children only according to
that policy. It must not merely filter on `perceiver_uuids` and then copy the
entire objective entry. The privileged comparison column displays a `HIDDEN`
audit row at the matching objective log index when no player-visible log entry
is produced.

### 10.5 Receipt and error trail

Show event source index, disposition, mapper, cue, asset, start/completion,
acknowledgement, and error/fallback. The cursor header shows simulation,
queued, playing, acknowledged, log, and decision-gate state on every frame.

The objective and subjective event columns align by source index and event
identity. Combat-log columns always align by objective log index. Source
lineage and an optional resolved terminal event index provide additional
cross-navigation when available; standalone logs remain valid without it.
Lineage indentation is retained because nested reactions and damage are
fundamental debugging evidence.

## 11. Geometry, terrain, and passive mouse diagnostics

The first geometry contract remains:

> One 128x64 isometric asset diamond equals one engine cell.

Do not introduce the suspected future 2x2 subdivision.

The world viewport uses real assets and implements:

- camera translation and zoom if needed for calibration;
- world-to-isometric and screen-to-world transforms;
- an asset contact anchor independent of the mechanical cell coordinate;
- height as a visual grid-plane offset derived from `Tile.height`;
- painter order that includes actual elevation and contact position;
- distinct directional boundary placements on both adjacent tiles;
- renderer-neutral object vertical bands;
- virtual-plane multi-height mouse picking.

The entity's game position remains `(x, y)`. Its visual support point is the
cell projection plus the render offset for the tile's height. Pixels never
change authoritative game coordinates.

The passive mouse overlay reports:

- screen and camera-adjusted world pixel coordinates;
- flat inverse-grid estimate;
- each height plane tested;
- candidate positions and diamond hits;
- winning cell and painter-order reason;
- tile UUID, height steps/feet, surface, and slope;
- movement cost, light, and optical facts available to the selected developer
  view;
- center objects and their vertical bands;
- every directional boundary placement on both sides;
- connector endpoints/elevations;
- presentation entities on the winning support;
- tile-surface versus tile-content visibility;
- current observer mode.

No clicking or targeting is required in the MVP.

## 12. Entity and terrain rendering minimum

Use the existing real isometric terrain pack and selected modular entity
sprites. Asset discovery is frozen into a small explicit manifest during
preflight; runtime does not scan arbitrary directories every frame.

Entity composition shares one animation, frame, facing, support anchor, and
tint across ordered visual layers. Required clips are idle, walk/run, attack,
take-damage, and death where those assets exist. A missing optional layer is
diagnostic; a missing required base layer is a preflight failure.

Every timed animation proves displayed frame progression. Reporting completion
without having displayed the expected changing frames is an error.

Terrain authorship for this encounter is direct local fixture data pairing
engine tile/object facts with explicit visual asset keys. Art never infers
walkability, optics, height, walls, materials, or boundary ownership. The
experimental MapEditor and its legacy scalar fields are not runtime inputs.

## 13. Diagnostics and run artifacts

Every run creates one ignored artifact directory such as:

```text
game/run_artifacts/<run-id>/
```

Write append-only structured records:

- `objective_events.jsonl`;
- `subjective_events.jsonl`;
- `projection_audit.jsonl`;
- `objective_combat_log.jsonl`;
- `subjective_combat_log.jsonl`;
- `presentation_receipts.jsonl`;
- `errors.jsonl`;
- `summary.json`;
- a screenshot on a presentation error when a display surface exists.

Use the engine models' ordinary JSON-safe dumps and small explicit immutable
presentation records. One small append-only artifact writer owns all files; do
not build separate stores, repositories, logging services, or a custom
serialization framework.

The final summary records:

- planned and executed command counts;
- objective, censored, and hidden event counts;
- objective and subjective combat-log counts;
- disposition totals;
- missing mapper and asset totals;
- queue high-water and maximum source-cursor lead;
- number and duration of player-gate waits;
- terminal simulation, queued, and presentation cursors;
- whether enemy run-ahead was observed;
- warnings, degraded fallbacks, and fatal errors;
- final result: `CLEAN`, `DEGRADED`, or `FATAL`.

### Error policy

- Illegal or unavailable scripted command: fatal simulation error. Record the
  command, actor, expected boundary, fresh discovery summary, and cursors.
- Missing reduction policy or privacy uncertainty: fail closed and fatal. Do
  not copy objective data as a fallback.
- Cursor/generation/order violation: fatal.
- Missing presentation mapper or non-critical VFX asset: emit a reduced-data
  badge fallback, mark the run degraded, and continue.
- Animation exception or cue watchdog expiry: record the error, visibly fall
  back, complete the receipt, and continue so one cue cannot deadlock the run.
- Required terrain/body asset missing at preflight: fatal before encounter
  advancement.

## 14. Lean future file boundary

Do not create empty architecture in advance. The expected minimum is:

```text
game/
  __main__.py                 autoplay entry point and pygame/asyncio loop
  encounter_fixture.py       direct world, actors, roles, initiative, script
  coordinator.py             decision advancement, two queues, cursor gates
  reduction.py               accepted event-view morphism and censorship policy
  presentation.py            reduced-stream scene reducer, mapper, cue player
  geometry.py                iso transforms, height planes, picking, sorting
  assets.py                  explicit manifest, preload, anchors, sprite layers
  diagnostics.py             read-only rail, traces, receipts, run artifacts
```

Split a file only when implementation size or ownership makes the split
concrete. Do not add service, manager, repository, controller hierarchy,
network-shaped client, transport DTO package, or generic plugin system.

The single autonomous scripted controller may live beside the fixture or
coordinator. It does not justify a controller framework.

## 15. Implementation slices and checkpoints

No later slice begins until the previous checkpoint is accepted.

### M0 — preflight and exact fixture proof

- verify `pygame-ce` runtime availability and document the dependency change;
- freeze the small terrain/entity asset manifest and validate dimensions;
- construct the direct engine encounter without rendering;
- run fresh public discovery for every proposed scripted command;
- freeze stable roles, positions, initiative, legal action selectors, and the
  outcome-independent script;
- confirm the opportunity attack is generated by movement, not scripted;
- record current engine/event/log baselines and exact test lanes.

Checkpoint: no renderer architecture yet; one proven legal fixture and asset
set.

### M1 — real-asset isometric geometry harness

- create the pygame shell and world viewport;
- render the direct battlefield with explicit terrain asset keys;
- implement projection, contact anchors, height-plane offsets, painter order,
  and directional boundary rendering;
- implement virtual-plane picking and the complete passive mouse inspector;
- calibrate on flat, raised, lowered, sloped, and boundary-heavy cells.

Checkpoint: reviewed screenshots plus deterministic transform/picking proofs.

### M2 — modular entity animation harness

- preload the selected entity layers;
- compose synchronized facing/frame layers at multiple elevations;
- implement the minimal clip set and cue completion signals;
- prove visible frame progression, anchoring, facing, draw order, missing-layer
  diagnostics, and death persistence through queued playback.

Checkpoint: animations and assets work without an engine-state read during
playback.

### M3 — accepted reduction boundary and read-only traces

Prerequisite: the separate event-reduction study is accepted and any required
plan amendment is revalidated.

- capture objective batches by generation/source cursor;
- key combat-log entries by objective log index, retain listener lineage, and
  resolve optional stored terminal event provenance after each batch;
- preserve standalone combat-log entries without inventing an event index;
- apply the accepted party knowledge-join reducer;
- emit immutable censored canonical bootstrap/event/log views;
- implement the objective/subjective event and combat-log columns;
- implement projection audit and explicit redactions;
- prove the presentation consumer receives only reduced records.

Checkpoint: identity and censored projections of static/cold bootstrap and
representative captured batches align in the four text streams without leaks,
type-family duplication, or gaps.

### M4 — presentation queue, mapper, receipts, and acknowledgement

- add the two `asyncio` queues;
- consume reduced batches into presentation scene state;
- map the minimal event set into timed cues/state cues/fallback badges;
- issue complete per-event coverage receipts;
- advance acknowledgement only across contiguous completed source ranges;
- expose live cursor/gate/queue state and error artifacts.

Checkpoint: deliberately unmapped reduced event visibly falls back and cannot
deadlock or skip acknowledgement.

### M5 — scripted autoplay and asymmetric timing

- connect the two external controlled actors and one minimal autonomous
  scripted controller;
- execute every intention through fresh public action discovery;
- reconcile deaths and encounter end inside the same outer event batch as each
  externally submitted player action;
- enforce acknowledgement before each player command;
- allow consecutive enemy decisions to enqueue without acknowledgement;
- stop at the next player boundary until presentation catches up;
- execute all proving beats and end explicitly.

Checkpoint: one visual run and one deterministic headless run demonstrate both
player gating and enemy run-ahead.

### M6 — MVP closure

- run focused engine regression lanes affected by fixture integration;
- run reduction, cursor, mapping, queue, geometry, entity, and headless autoplay
  feature lanes;
- run the visual/manual calibration checklist;
- inspect artifacts for cursor alignment, coverage, and privacy;
- run dependency/locality and anti-slop gates;
- obtain independent correctness/privacy/timing review and independent
  anti-slop/dependency review of the exact candidate.

Checkpoint: accepted MVP with a reproducible run summary and no required work
remaining inside this scope.

## 16. Observable acceptance matrix

| Requirement | Public observation |
| --- | --- |
| Cold bootstrap | First reduced batch builds the visible world without registry reads |
| Two controlled characters | Both appear in initiative and execute distinct gated turns |
| Real commands | Each intention matches and executes a fresh public action row |
| Opportunity attack | Movement creates a reaction child event and nested log evidence |
| Live mechanics | Rolls and damage come from ordinary engine resolution |
| Player timing | No next player command commits before prior presentation acknowledgement |
| Enemy run-ahead | Queue depth/source-cursor lead becomes greater than zero during autonomous play |
| Decision catch-up | Next player boundary waits until presentation equals queued cursor |
| Subjective authority | Viewport state is reproducible from reduced batches alone |
| Event comparison | Objective and subjective rows align by generation/index/UUID with explicit redaction |
| Log comparison | Objective and subjective log trees align by objective log index; optional event provenance agrees when present |
| Coverage | Every eligible reduced event has exactly one terminal receipt |
| Missing handler | Event becomes a visible reduced-data fallback badge and a degraded receipt |
| Height | Elevated draw placement and passive mouse winner match engine support height |
| Animation | Timed cues visibly display changing frames before completion |
| Terminal state | Presentation acknowledges the terminal simulation cursor |
| Debuggability | Run artifacts identify the originating command/event/projection/cue for every error |

Tests target these observations, not internal call order. Async tests wait for
acknowledgements and cursor conditions, never guessed wall-clock sleeps.

## 17. Anti-slop and scope gates

- No server, FastAPI, websocket, SDK, HTTP, transport, or TypeScript runtime.
- No Python mirror of the deprecated client store or wire schema.
- No duplicated objective/subjective concrete event model families.
- No mutation-capable mechanics `Event` object with censored sentinel fields.
- No second mechanics authority and no subjective `EventQueue` clone.
- No renderer access to live objective entities, grid, encounter, or registries.
- No objective trace field used as a scene or animation input.
- No custom event bus beyond the existing engine stream and two app queues.
- No second combat-log generator; project the engine's event-time log evidence.
- No scripted events, outcomes, reactions, rolls, damage, or sensory deltas.
- No generic scripting DSL, replay framework, AI framework, or controller tree.
- No arbitrary sleeps for queue, animation, or test correctness.
- No dropped/coalesced event batches and no cursor acknowledgement through a gap.
- No privacy fallback that copies an objective event when reduction is unknown.
- No silent unmapped presentation event.
- No hidden event badge in the player presentation.
- No selection-dependent party perspective.
- No speculative asset-diamond 2x2 subdivision.
- No free-altitude or within-cell 3D mechanics.
- No merging of opposite directional boundary placements.
- No art-to-mechanics inference.
- No MapEditor schema, campaign, menu, save, networking, or full spell-VFX work.
- No implementation before the reduction study and required revalidation.

## 18. Deferred decisions

- final MapEditor authoring schema;
- possible 2x2 tactical subdivision of one 128x64 asset diamond;
- full spell/projectile/area VFX catalog;
- interactive action selection, targeting, camera controls, and accessibility;
- generic enemy AI beyond the proving controller;
- bounded queue/backpressure policy for long simulations;
- engine worker thread or process;
- save/replay/network transport;
- full equipment/monster appearance catalog;
- campaign and non-encounter UI.

These are not prerequisites for proving the local engine/reducer/presentation
architecture with the scripted encounter.

## 19. Acceptance record

The implementation content candidate at SHA-256
`49b8c5e23a1d6a152cbe5008e2e3f8bcc446c556093cb1509eedf139af947fd7`
received two independent acceptances:

- engine/event/reduction/timing correctness: `ACCEPT`;
- anti-slop/dependency/scope: `ACCEPT`.

Both reviewers confirmed that the external player-action reconciliation,
combat-log identity/provenance, canonical event-view morphism, shared
event/log disclosure policy, immutable diagnostic boundary, and lean artifact
writer are correctly stated. The final metadata-bearing document bytes were
then reconfirmed by both reviewers.
