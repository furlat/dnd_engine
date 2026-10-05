# July reconstruction Steps 11–12 implementation plan

Date: 2026-08-30  
Status: APPROVED IMPLEMENTATION AUTHORITY — double accepted

Independent acceptance:

- correctness/regression: APPROVE;
- anti-slop/anti-OOP/ECS/import-DAG: APPROVE.

Both approvals covered the complete substantive plan ending at SHA-256
`0d07fd916f3c49a87d81e9cfec50ba75d02e120edb58c09f971eef7ee6047450`;
this status record is metadata only.

## 1. Outcome

Complete the last engine-side prerequisites before the scripted Pygame client:

1. build one complete actor-free authored world without publishing partial
   construction noise;
2. publish exactly one renderer-neutral `WorldInitializedEvent` for that cold
   world;
3. activate authored dynamic hazards and light sources through their ordinary
   lifecycles after world initialization;
4. compose each scenario Entity, publish one terminal creation fact, and deploy
   it through the passed `Game` after the world exists;
5. preserve the existing objective event stream while exposing the already
   authoritative observer-specific sensory deltas and same-model subjective
   combat logs needed by an in-process renderer; and
6. prove that generation-bounded objective combat-log slots and the already
   value-safe sensory deltas can be projected/replayed without querying later
   live mechanics state.

This plan does not build Pygame. It makes the engine output truthful enough for
the later asynchronous engine/render queues.

## 2. Governing authority

The implementation is governed by:

- `DND_POST_JULY_PRESERVATION_DOSSIER_2026-08-29.md`, especially selector
  groups Q and the retained part of section 4;
- the accepted current July-reconstruction checkout after Step 10;
- `HOW_TO_TEST.MD`; and
- the component/import laws in `AGENTS.md`.

Historical commit `513dd97` and its Phase 5/6 plans are evidence for public
behavior only. Whole modern files, server runtimes, DTO families, and private
architectures are not transplant authority.

## 3. Starting truth

The current checkout already has:

- authoritative Tile identity, surface, four movement costs, elevation,
  ordered-side world objects, connectors, objective light, occupancy, and
  independent spatial conditions;
- `Game` as the single in-process owner of deployed Entities;
- committed per-step movement and observer-specific `SensoryUpdateEvent`
  deltas emitted before their causative terminal;
- event-time identity/location/perceiver evidence on Events and
  `CombatLogEntry` trees;
- renderer-neutral `ItemPresentationState` and item-location facts; and
- the July same-model combat-log projection semantics in deprecated server
  code as read-only evidence.

The current checkout does not yet have:

- `WorldInitializedEvent` or an Entity birth fact;
- a real outer cold-build boundary (nested rectangle construction currently
  re-enables and later flushes buffered construction events);
- cold/dynamic separation for authored SpikeTraps and WallTorches;
- direct scenario ownership by one passed `Game` (some legacy creature roots
  still deploy through throwaway `Game()` instances); or
- an in-process, server-free home for same-model combat-log projection,
  generation-bounded nullable combat-log slots, and owner-local sensory replay
  proofs.

## 4. Non-negotiable design laws

### 4.1 Ownership and causality

- `GridMap` owns cold topology admission and snapshot reads.
- Authored battlefield builders own authored classification, not event
  publication infrastructure.
- `Entity` owns its completed composition snapshot; `Game` owns the transition
  from composed/undeployed to deployed.
- `SpatialCondition`, WallTorch, item, occupancy, and sensory mechanics keep
  their existing owners and event paths.
- `WorldInitializedEvent` is one already-committed terminal fact. It does not
  execute builders or later mechanics.
- World initialization precedes authored dynamic setup; authored dynamic setup
  precedes Entity creation; Entity creation precedes deployment.

### 4.2 One event algebra, not a presentation clone

- Existing concrete `Event` subclasses remain the only event types.
- This step does not generically clone, serialize, mask, or archive arbitrary
  Events. July Events legitimately carry live mechanics during synchronous
  dispatch, including `ConditionApplicationEvent.condition`; copying those
  payloads would create shadow component graphs rather than a lawful
  presentation boundary.
- Subjective combat-log projection returns `CombatLogEntry | None`; a visible
  result is still `CombatLogEntry`.
- `SensoryUpdateEvent` is already observer-subjective. Replay reuses its exact
  deltas rather than recomputing FOV, light, invisibility, stealth, or special
  senses.
- There is no generic `Known/Unknown` path layer, readability-mask framework,
  exhaustive reducer manifest, receipt protocol, or event acknowledgement.
- Unsupported future presentation work remains present and queryable in the
  authoritative objective queue. Nothing marks it handled or deletes it.

### 4.3 Engine/renderer boundary

- World, Entity, item, sensory, and log facts remain renderer-neutral.
- Height is carried as movement/support and later pixel-offset data. This work
  adds no 3-D light, FOV, ray, or propagation calculation.
- No server, session, gateway, worker, SDK, transport, TypeScript, map editor,
  renderer, asset, or Pygame code is touched.

### 4.4 Anti-slop / anti-OOP rules

Do not add a manager, controller, service, repository, event bus, transaction
wrapper, causal context manager, completion callback chain, observer callback,
second GridMap, second EventQueue, replay framework, compatibility facade,
dual-write path, registry, or global type switch.

Event values may expose value-local validation and copying. They may not call
GridMap, Entity, Senses, conditions, or other mechanics owners.

## 5. Step 11 — cold world and direct scenario deployment

### 5.1 Cold value facts

Add dependency-leaf frozen value models sufficient to describe the complete
actor-free world:

- Tile UUID, XY, surface/name, all four movement costs, intrinsic optical and
  propagation flags, elevation tuple, base light, and resolved light;
- each exact center/boundary `WorldObjectPlacement`, its complete
  `ItemPresentationState`, and direct contained-item states; and
- each connector UUID/authored ID, kind, endpoints/elevations, movement/action
  cost, directionality, enabled state, and provocation policy.

`WorldInitializedEvent` carries those tuples, bounds, dimensions, battlefield
identity, and a deterministic actor-free source UUID. It is constructed with
`use_register=False` and published once through the existing
`EventQueue.publish_completed_fact` seam.

Do not add SpatialCondition or light-source lists to the cold snapshot. Those
families must be absent cold and represented by ordinary post-init facts.

### 5.2 Exact cold-build boundary

Keep the existing GridMap enabled/disabled mechanism and make it honest:

- `create_rectangle` restores the prior enabled state instead of always
  enabling events;
- `enable_events(flush_pending=False)` clears buffered facts without
  publishing them;
- `build_battlefield` requires an empty EventQueue, empty GridMap, no live
  SpatialCondition, and no registered Tile;
- the builder runs while events remain disabled;
- the complete world event is built and validated while still cold;
- failure publishes no world fact and never relabels partial mutation as a
  successful reusable world; and
- success discards construction noise, enables events, and publishes exactly
  one world terminal.

This is explicit state restoration, not a new context-manager protocol.

When a Tile is replaced during construction, the displaced Tile must leave
both GridMap indexes and the BaseBlock registry. The registered Tile set must
equal the snapshot Tile set exactly.

### 5.3 Cold/dynamic authored classification

For every maintained battlefield:

- Tiles, intrinsic light, final world-object placements, contained items,
  directional structures, and initial connector registrations are cold;
- SpikeTrap UUIDs are reserved as plain identities during construction, but
  no condition object or footprint exists yet;
- WallTorches are placed unlit and own no light source cold;
- TrapLever presentation state carries its one typed linked SpikeTrap UUID;
- after the world terminal, each reserved SpikeTrap is materialized and
  activated through the existing condition/spatial lifecycle using the world
  terminal as its root cause;
- after those fields, each authored WallTorch uses its existing light and
  IGNITE paths, followed by its complete current item/location fact; and
- every such dynamic terminal occurs after world initialization and before the
  first Entity creation fact.

Restore the maintained elevation proving battlefield if it is required to
exercise authored connector/elevation cold state; do not create a map DSL or
generic deferred-content registry.

### 5.4 Entity birth and deployment

Add one terminal `EntityCreatedEvent` with payload parity to the accepted
`513dd97` creation fact, adapted only to current dependency-leaf names such as
`ItemPresentationState`. It includes identity/kind/name/description,
creature/body/origin/class state, ability scores, skills/expertise, saving-
throw and equipment proficiencies, proficiency bonus, initiative, AC,
life/HP/temporary HP/damage/hit dice, damage affinities, walking/swimming
speeds, sight/sense modes/breathing/death-save state, origin capabilities,
body semantics, features/actions/handlers/conditions/immunities, attacks per
action, resources and recoveries, attack multiplicity, spell sources/known/
reaction/prepared spells/slots, feature toggles, AC formulas, complete
inventory/equipped `ItemPresentationState` values, inventory UUIDs, and exact
equipment slots. The fact does not read server models.

The birth boundary is:

1. an Entity is constructed undeployed and remains creation-uncommitted;
2. its maintained content/monster/character root finishes composition and
   calls the one canonical `compose_entity` boundary;
3. that composition boundary validates the finished aggregate, marks creation
   committed, and publishes exactly one terminal creation fact;
4. only then may `Game` attach it to the admitted Tile through the existing occupancy
   seam; and
5. sensory settlement remains under the entered effect before its terminal.

`Game.deploy_entity` rejects an uncommitted Entity; it never causes or repairs
composition. If initial composition, validation, or birth publication fails,
the unpublished aggregate and its owned registry entries are discarded and no
creation fact remains. This restores the accepted owner boundary without a
composition callback, context manager, transaction object, or receipt layer.

Remove the remaining internal `Game().deploy_entity(...)` calls from creature
roots. Callers that need a live creature must explicitly deploy it, with
scenario assembly using the single `Game` supplied by its caller. Do not add a
legacy auto-deployment flag or compatibility alias.

Scenario assembly must never reset process-global state. Its explicit preflight
requires an empty passed Game and an admissible cold world. It builds the
battlefield, composes all roster members, deploys them through that Game,
applies authored setup through existing item/condition/action owners, creates
the Encounter, and optionally starts it.

### 5.5 Step 11 public acceptance

Behavior-first tests must prove:

- every maintained battlefield emits exactly one first
  `WORLD_INITIALIZED` completion and no construction phases before it;
- the cold event exactly matches live Tile/object/connector identity and
  renderer-neutral state at the cold boundary;
- no cold SpatialCondition, dynamic light source, Entity, occupancy, or
  observer exists;
- SpikeTrap and WallTorch post-init facts have exact identity, causal order,
  and complete mechanics;
- cold event plus post-init facts reproduces the defined live authored state;
- the elevation/connector battlefield round-trips exact support and connector
  values;
- world < dynamic setup < EntityCreated < EntityEntered for a prepared
  scenario;
- every `EntityCreatedEvent` field enumerated in section 5.4 equals the
  composed Entity's committed owner value exactly;
- failed composition leaves no committed/registered Entity and no creation
  event;
- one passed Game owns every scenario Entity and no throwaway Game path can
  deploy it;
- a canceled/rejected dynamic setup never produces a false successful
  scenario; and
- scenario setup still uses real items, conditions, reactions, opportunity
  attacks, initiative, and fixed-opening behavior.

## 6. Step 12 — minimal in-process subjective projection and replay

### 6.1 Scope decision

Recover only the semantics required before a real Pygame consumer exists:

- event-time observer evidence remains authoritative;
- observer sensory deltas replay without live world reads;
- objective and subjective combat logs share `CombatLogEntry`;
- hidden identities and coordinates never leak through projected log text or
  arbitrary nested log data;
- aggregates are rebuilt from delivered children; and
- generation-bounded projection preserves one ordered nullable log slot for
  each authoritative objective `Encounter.combat_log` entry without cloning
  any live Event payload.

Do not recover the deleted July server/session/runtime-store/worker/gateway
contracts, authority epochs, cursored transport frames, parallel session
archives, TypeScript replication, or a general-purpose replay service. Those
are not required by the in-process two-character Pygame MVP.

### 6.2 Same-model subjective combat logs

Move/reimplement the pure July combat-log projection behavior under `dnd/`,
with no import from `server`. Its public seam is one pure call accepting the
`CombatLogEntry` plus immutable `frozenset[str]` controlled-entity and
observer UUID sets directly:

- input and visible output are `CombatLogEntry`;
- fully unobserved trees return `None`;
- controlled participants and event-time observers grant occurrence
  visibility;
- identity and position grants come only from recorded event-time evidence;
- hidden UUIDs/names/coordinates are scrubbed recursively from typed fields,
  text, arbitrary nested data, and keys;
- a visible child beneath an otherwise hidden parent retains a sanitized
  same-model parent so causality is not flattened;
- multi-target counts, names, saves, and damage are rebuilt from projected
  children only;
- movement/jump/connector geometry survives only when its exact event-time
  evidence authorizes it; and
- after those grants are used, the visible output contains empty
  `perceiver_uuids`, `revealed_entity_uuids`,
  `identified_entity_observer_uuids`,
  `located_entity_observer_uuids`, and
  `located_position_observer_uuids`; and
- the objective source tree is never mutated.

No projection context class, cache object, builder, registry, production enum
whitelist/policy table, second subjective log model, or second formatter is
introduced. Any memo used for shared nodes is allocated inside one projection
call and discarded before return. Exhaustiveness over current
`CombatLogEntryType` members is test-owned; production uses one structural
recursive sanitizer plus only the narrow aggregate and movement-geometry
rebuild branches that genuinely differ.

### 6.3 Sensory replay

Restore the accepted owner-local `Senses.apply_sensory_update(event)` reducer.
It applies only the after-value delta already carried by one
`SensoryUpdateEvent`: position, visible/seen cells, observer-effective light,
entity/object contacts, sense modes, passive perception, visual access, and
path dirtiness.

It must reject another observer's event and must not query GridMap, Entity,
live Senses, or registries to fill missing data.

For a party perspective, replay applies the two controlled observers' streams
independently and joins their resulting knowledge only at the consumer query;
it does not merge or overwrite the two authoritative observer histories.

### 6.4 Generation-bounded combat-log batches

Do not recover `EventArchive.capture_queue_range` and do not add generic Event
capture. Add only the smallest synchronous read/projection seam needed to
preserve the retained replay law:

- the owning Encounter records `combat_log_generation_uuid` when its first log
  is appended, and every later append remains in that same queue generation;
- every range read requires
  `requested_generation == encounter.combat_log_generation_uuid ==
  EventQueue.generation_id()` before and after projection; a stale generation
  is rejected, and a batch can never span `EventQueue.reset()`;
- the owning `Encounter` reads its authoritative ordered `combat_log` range
  only after the causative synchronous operation has terminalized; it does not
  derive log sources by scanning Event terminals;
- projection returns a plain immutable tuple containing the generation UUID
  and exactly one `(combat_log_index, CombatLogEntry | None)` slot per selected
  objective log, including `None` when subjective projection hides that log;
- generation is validated both before reading and after the complete tuple is
  projected, so a reset during construction rejects the whole result;
- nested child logs remain inside their one authoritative top-level tree, and
  logs inserted through `EventQueue.push_combat_log` remain present even
  though they deliberately have no stored Event version;
- the Encounter log is append-only for its generation. Hard-cut the unused
  `clear_combat_log()` method so indexes cannot be reused or aliased; do not
  introduce a second log epoch;
- construction is all-or-nothing: a read/projection failure returns no partial
  tuple and mutates/advances/deletes/acknowledges nothing;
- a completed batch is detached from subsequent queue reset because it
  contains only copied/projected passive logs and scalar indexes; if the
  source resets before construction finishes, the generation check rejects
  the entire batch rather than returning a cross-generation prefix;
- the projector copies/sanitizes only passive `CombatLogEntry` values; it does
  not copy the source Event or any live component payload; and
- `SensoryUpdateEvent` is replayed through section 6.3 from its own already
  passive after-values. A public recursive payload-safety proof rejects any
  runtime owner or callable in those sensory values before they are admitted
  as replay input.

There is no archive, batch model, replay manager, persistent projection
context, receipt, unsupported-event disposition, or new queue. The real
`/game` async queue and the exact event-time detachment point for any additional
presentation fact are Step 13 work, where an actual consumer can prove the
need payload by payload.

### 6.5 What the subjective renderer will consume later

Step 12 deliberately does not invent a generic censored Event clone. The later
renderer can be built from:

- the authoritative queue's concrete events for the synchronous privileged
  objective/debug rail and missing-presentation inventory;
- only the controlled observers' proven value-safe `SensoryUpdateEvent`
  after-values for subjective
  world visibility/contact state; and
- generation-bounded nullable slots of projected same-model `CombatLogEntry`
  trees for subjective action/result text and authorized animation geometry.

This is sufficient to start the Pygame consumer without duplicating the event
ontology. If a later animation demonstrably needs a typed event field not
present in sensory/log facts, that missing committed fact is added to its
existing owner/event at that time. It is not solved now by a generic field-mask
language.

### 6.6 Step 12 public acceptance

New in-process tests must prove:

- parameterized public cases cover every current `CombatLogEntryType` without
  a production whitelist/policy table;
- hidden identity is recursively absent from projected bytes while the
  objective source remains byte-identical;
- hidden-parent/visible-child causality is preserved by a sanitized
  `CombatLogEntry`, not a wrapper or flattened synthetic root;
- multi-target totals contain only delivered children;
- movement, elevated jump, and connector geometry follow exact event-time
  authorization and never later live visibility;
- two controlled observers replay independent sensory histories and produce
  the party union without cross-overwriting;
- one exact test-local presentation tuple assembled as
  `(cold_world_value, ordered_entity_creation_values,
  ordered_projected_log_slots, per_observer_senses_values)` reaches the same
  value as the live run; `per_observer_senses_values` contains one separately
  replayed Senses value per controlled observer and party union is computed
  only in the assertion;
- generation reset rejects a stale log-range request and no batch spans
  generations;
- an Encounter that survives `EventQueue.reset()` cannot expose or append its
  old log slots under the new generation UUID, and the removed clear path
  cannot make two entries share one index;
- combat-log slots preserve authoritative source order and retain projected
  `None` entries;
- a mixed authoritative range containing one top-level tree with nested child
  logs, one standalone `push_combat_log` entry, and one subjectively hidden
  entry yields exactly three ordered slots: no duplicate child slot and one
  `None` in the hidden entry's original index;
- a forced projection failure returns no partial batch or mutated source; and
- unsupported presentation Events remain untouched and queryable in the
  authoritative objective queue; constructing log slots does not consume,
  drop, clone, or acknowledge them.

The presentation tuple exists only in the test. Do not add a production
generic world/entity reducer, persistent party-union owner, presentation-state
manager, or equivalent abstraction.

## 7. Implementation slices and stop gates

### Slice 11.0 — preflight

- Record the exact active callers of battlefield build, creature deployment,
  Game deployment, combat-log projection, and replay helpers.
- Run the current Step 10 accepted lane plus focused world/scenario/sensory
  baselines.
- Confirm the dependency graph has no SCC including function-local imports.
- No production edits in this slice.

### Slice 11.1 — cold facts and boundary

- Add world fact models/EventType.
- Correct nested GridMap event disabling and displaced Tile registry cleanup.
- Build/validate/publish exactly one cold world fact.
- Stop for focused cold-world review.

### Slice 11.2 — authored dynamic setup

- Reserve SpikeTrap identity cold.
- Place WallTorches unlit cold.
- Add the typed TrapLever link fact.
- Activate hazards/lights after the world terminal.
- Stop for cold/dynamic chronology and mechanics review.

### Slice 11.3 — Entity birth and direct scenario

- Add Entity creation fact/one-shot commit.
- Remove creature-root auto-deployment.
- Route maintained scenarios through one passed Game.
- Stop for creation/deployment chronology and gameplay review.

### Slice 12.1 — same-model logs and sensory replay

- Rehome the pure combat-log projection semantics under `dnd`.
- Restore `Senses.apply_sensory_update`.
- Add the explicit hidden-parent/visible-child decision test.
- Stop for subjective correctness and objective immutability review.

### Slice 12.2 — generation-bounded log slots and end-to-end replay

- Add the narrow generation-qualified `Encounter.combat_log` range read and
  pure nullable log-slot construction.
- Bind the Encounter log to its first EventQueue generation and hard-cut the
  unused clearing path.
- Prove two-observer replay and cold-to-live presentation parity.
- Prove unsupported facts remain actionable in the objective queue.
- Stop for full correctness and anti-slop review.

### Slice 12.3 — certification

- Run all affected world, item, entity, occupancy, movement, optics/light,
  sensory, spatial-condition, scenario, encounter, combat-log, and replay
  tests.
- Run compileall and diff-check.
- Run an AST dependency graph including top-level and local imports; require
  zero SCCs.
- Search for forbidden server/SDK/transport imports and rejected reducer
  vocabulary.
- Obtain two independent exact-candidate reviews: correctness/replay/causality
  and anti-slop/anti-OOP/dependency ownership.

Any repair after a slice review invalidates that review and reruns the affected
gate. Do not use hashes or manifests as a substitute for reading the diff and
running public behavior.

## 8. Initial file envelope

Expected production paths:

- `dnd/core/events.py`
- `dnd/core/gridmap.py`
- `dnd/core/base_tiles.py`
- `dnd/core/item_types.py`
- `dnd/core/combat_log.py` or one small server-free subjective-log module
- `dnd/blocks/base_item.py`
- `dnd/blocks/sensory.py`
- `dnd/entity.py`
- `dnd/encounter.py`
- `dnd/game.py`
- `dnd/maps/arena_layout.py`
- `dnd/scenarios/battlefield_catalog.py`
- `dnd/scenarios/encounter_assembler.py`
- the exact maintained creature roots that still auto-deploy
- `dnd/items/environment_interactables.py`
- `dnd/items/torches.py`
- `dnd/spatial/environmental_conditions.py`
- `dnd/runtime_reset.py` only if a newly added one-shot state requires reset

Expected tests:

- one focused engine module for cold bootstrap/direct deployment;
- one focused engine module for in-process subjective projection/replay;
- existing public world, item, occupancy, sensory, scenario, encounter, and
  architecture modules affected by the exact change.

Touching files outside this envelope requires a concrete dependency discovered
during implementation and a bounded plan amendment before editing.

## 9. Explicitly excluded historical tests

Do not make deprecated server tests green by restoring their infrastructure.
In particular, the old observation-store, runtime-epoch, agent/directory
stream, gateway/worker replay, session replication, and TypeScript SDK tests
remain historical evidence. Their semantics may be reconsidered only when a
real in-process Pygame consumer proves a need.

## 10. Reviewer questions

Both reviewers must answer all of these:

1. Does Step 11 produce one truthful cold world followed by ordinary dynamic
   facts, with no double representation?
2. Is Entity composition committed exactly once before deployment through one
   passed Game?
3. Does Step 12 preserve the same Event and CombatLogEntry type spaces without
   recreating `CanonicalEventView`, `Known/Unknown`, a reducer manifest, or a
   second subjective DTO family?
4. Is every replay input event-time and passive, with no generic Event cloning
   or later live mechanics reads?
5. Are hidden-parent causality, two-observer separation, movement privacy, and
   unsupported-event retention explicitly tested?
6. Does the plan introduce any manager/service/controller/callback/context/
   transaction/receipt/registry layer that can be deleted?
7. Do all dependency arrows remain acyclic and point from domain owners to
   passive event/value leaves, never back from Events into mechanics?

An approval must be `APPROVE` with no material blocker. A rejection must name
the smallest exact correction; it may not expand the work into server,
transport, SDK, Pygame, general content recovery, or unrelated cleanup.
