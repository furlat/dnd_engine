# Core Gameplay Recovery Patches

**Status:** focused implementation plan; no Runtime V2 recovery authorized

**Date:** 2026-08-05

**Current baseline reviewed:** `feat-zaxis` at `e745f389f7a34321d16146a6d241c363597ed37a`

**Abandoned comparison source:** `cursed-sol` at `d2fb3931527f8c1cad4bdda163876baaaedb0555`

**Related inventory:** `agent_docs/CURSED_SOL_CORE_ENGINE_RECOVERY_INVENTORY_2026-08-05.md`

## Decision

Recover four narrowly bounded pieces of gameplay truth:

1. one-way, idempotent spatial-effect reveal;
2. typed condition and Counterspell evidence;
3. movement settlement, path, and opportunity-attack corrections;
4. canonical reciprocal wall and door identity.

These are engine/content improvements. They do not require the abandoned
player-product runtime, command durability system, generated SDK forest,
host-control journal, replay obligations, worker threads, or server-side game
engine.

The abandoned commit is evidence and a source of selected hunks, not a merge
candidate. Each recovery must be implemented and tested independently on the
current branch. Do not merge or cherry-pick `cursed-sol`.

## Why these patches are not the former slowdown

The expensive abandoned paths eagerly constructed and validated large product
graphs during game creation and action discovery. They serialized whole action
sets, hashed movement dependencies, built player projections, installed
durability artifacts, and started per-runtime coordination machinery.

These four patches have different performance shapes:

| Patch | Normal cost | Creation-path cost | Forbidden expensive behavior |
|---|---:|---:|---|
| Spatial reveal | O(1) per actual reveal | none | observer scans or frame construction |
| Typed evidence | O(1) per condition/Counterspell event | none | SDK/product projection work |
| Movement settlement | O(committed path steps) during movement | none | eager all-action movement plans or deep hashes |
| Boundary identity | O(changed boundary sides) per structural mutation | bounded map-load indexing | full-map rebuild on every door or object mutation |

No patch may create a thread, async worker, command finalizer, persistence
artifact, transport DTO, player frame, SDK contract, or server dependency.

## Architectural boundaries

The following ownership rules are mandatory:

- `dnd` owns objective mechanics, event facts, movement settlement, and world
  structure.
- `server` may transport or project those facts but must not recompute them.
- NeuroClient may present disclosed facts but must not determine movement,
  opportunity attacks, condition identity, or structural identity.
- Every game-state mutation continues to flow through the existing event
  lifecycle.
- Content identity comes from authored bindings. Display names and Python class
  paths are never identity fallbacks.
- No function-local imports, `TYPE_CHECKING` dependency workarounds, or upward
  dependency edges may be introduced.

## Patch 1 — Spatial-effect reveal idempotency

### Current defect

`SpatialEffect.publish_revealed()` in `dnd/spatial_effects.py` verifies that the
effect was installed and publishes a `REVEALED` lifecycle event, but it does
not clear `stealth_dc`. Calling it twice can therefore publish two reveal
facts, and the objective effect remains internally marked as hidden.

### Recovery

Before publishing the reveal fact:

```python
if self.stealth_dc is None:
    return None
self.stealth_dc = None
```

This is the useful part of the abandoned hunk. Do not recover the accompanying
located-observer evidence map. Computing per-position observer sets is a
projection/privacy concern and is unrelated to reveal idempotency.

### Required invariants

- An installed hidden effect has `stealth_dc is not None`.
- Its first accepted reveal changes `stealth_dc` to `None` and publishes
  exactly one `SpatialEffectChangeOperation.REVEALED` fact.
- Later reveal attempts return `None`, mutate nothing, and publish nothing.
- An uninstalled effect still raises the existing error.
- A revealed effect cannot become hidden again through replay or projection;
  a distinct authored state transition would be required to hide it.
- The reveal event remains a child of the causal parent event.

### Focused tests

Add one small engine test file, preferably
`tests/engine/test_spatial_effect_reveal_idempotency.py`, covering:

1. first reveal clears `stealth_dc` and increments the matching reveal-event
   count from zero to one;
2. second reveal returns `None`, leaves the event cursor unchanged, and keeps
   the count at one;
3. reveal before installation remains invalid;
4. removal after reveal does not manufacture a second reveal.

Run only:

```bash
uv run pytest tests/engine/test_spatial_effect_reveal_idempotency.py
```

### Performance gate

The patch must not call senses, subscribers, observer projection, combatant
projection, serialization, or hashing. The reveal transition is constant-time
apart from the already-existing event publication.

## Patch 2 — Typed condition and Counterspell evidence

This patch contains two related objective-evidence improvements. They may land
in separate reviewable changes if desired, but neither depends on runtime or
transport work.

### 2A. Typed condition transition evidence

#### Current state

Condition application and removal logs retain readable condition names, and
application already carries `ConditionApplicationDisposition`. They do not
freeze the authored condition identity into the declaration/log fact.

#### Recovery

- Add a dependency-neutral `ConditionLogData` model in
  `dnd/core/combat_log.py`.
- Add optional `condition_content_identity` to condition application and
  removal declaration events in `dnd/core/base_conditions.py`.
- Derive it only from `BehaviorBinding.definition_ref.identity_key` when a
  condition has a real authored binding.
- Freeze that identity when the declaration event is created.
- Emit typed log data for application and removal, including:
  - display name;
  - authored identity or explicit `None` for legacy unbound conditions;
  - application disposition for application;
  - `reveals_target` for removal.
- Preserve the existing typed immune/rejected/retained application truth in
  `dnd/entity.py`; do not infer success from text.

#### Required invariants

- A display name is never substituted for absent content identity.
- A Python module or class path is never emitted as authored identity.
- An authored identity is frozen at declaration and cannot change if the
  runtime object is later modified.
- Application and removal for the same bound condition use the same identity.
- Legacy unbound conditions remain representable as objective diagnostics with
  `condition_content_identity=None`.
- Presentation code may fail closed for unbound content; the engine must not
  invent an identity to make a client happy.

### 2B. Counterspell resolution evidence

#### Current state

`CounterspellReactionEvent` and `SpellInterruptionLogData` already exist and
carry levels, automatic/check evidence, success, and stable outcome codes. The
models currently permit contradictory combinations, and the log does not
freeze the authored identities of both causal content roles.

#### Recovery

- Bound incoming spell and Counterspell levels to 0–9 and 3–9 respectively.
- Add exact optional authored identities for:
  - the Counterspell reaction content;
  - the incoming spell content.
- Populate those identities from existing authenticated bindings at reaction
  declaration time.
- Add the same closed resolution validation to both the objective event and
  its typed log data:
  - automatic means Counterspell slot level is at least the incoming spell
    level, success is true, and no check fields exist;
  - checked means Counterspell slot level is lower than the incoming spell
    level, both check fields exist, DC equals `10 + incoming spell level`, and
    success exactly equals `check_total >= check_dc`.
- Keep existing reaction/slot spending and causal event ordering unchanged.

The abandoned hunk also changes randomness and spatial-effect log enum names.
Those are separate migrations and must not be included here.

#### Required invariants

- Impossible Counterspell evidence is rejected at model construction, not
  repaired in a projector.
- The objective event and combat log cannot disagree.
- Both causal content identities are distinct and correctly attributed.
- Legacy hand-authored diagnostic events may use explicit `None`; names do not
  become identities.
- Hidden-reactor subjective log redaction remains unchanged and green.

### Focused tests

Prefer two focused files:

```text
tests/engine/test_condition_content_evidence.py
tests/engine/test_counterspell_evidence.py
```

At minimum cover:

- bound and unbound condition application/removal;
- APPLIED, IMMUNE, REJECTED, and RETAINED_STRONGER dispositions;
- automatic Counterspell success;
- checked success and checked failure;
- invalid automatic failure;
- invalid automatic check fields;
- invalid checked DC;
- result/check contradiction;
- reaction identity versus incoming-spell identity;
- event-to-log field equality.

Retain the unique privacy assertions in
`tests/manual/test_50_counterspell_engine_contract.py`; run that file
individually when the Counterspell patch changes its data shape.

```bash
uv run pytest tests/engine/test_condition_content_evidence.py
uv run pytest tests/engine/test_counterspell_evidence.py
uv run pytest tests/manual/test_50_counterspell_engine_contract.py
```

### Performance gate

Validation is constant-time at event construction. No content registry scan,
action discovery, JSON round trip, player projection, or SDK conversion is
allowed in the engine event path.

## Patch 3 — Movement settlement, path, and opportunity-attack truth

### Current foundation to preserve

The current engine already has valuable pieces:

- cell-by-cell `StepMovementEvent` processing;
- opportunity attacks inside the causal chain;
- typed movement trajectory and termination reason for `Move`;
- requested versus actual destination for `Move`;
- committed-step `MovementContinuationGuard`;
- exact path and visible hostile OA exposures in action discovery;
- forced movement distinguished from voluntary movement.

Do not replace these with a new runtime movement service.

### Current correctness gap

`Jump._apply()` currently updates position, completes the step, checks
incapacity, and only then consumes movement. If arrival causes death or
incapacity, the step can commit without paying its movement cost. Jump also
lacks the same complete termination and continuation evidence already present
for `Move`.

The abandoned branch contains useful corrections, but it also adds a separate
large connector action and causal-checkpoint machinery. Recover the settlement
facts, not the extra authority.

### Canonical voluntary-step ordering

Every Walk/Swim/Jump/Fly step must follow one engine-owned order:

1. validate remaining movement and structural transition;
2. publish/process step intent so reactions such as OA can veto or alter it;
3. if canceled or incapacitated before entry, complete the step as
   `committed=False`;
4. revalidate the transition after reactions;
5. consume the exact movement cost;
6. update objective position;
7. complete the step as `committed=True`;
8. expose the committed boundary to the existing continuation guard;
9. then terminate for post-commit death/incapacity or an explicit controller
   revalidation decision.

The guard must observe a fully paid, fully committed step even when that step
causes incapacity. It is an observer/revalidation seam, not a persistence or
transport owner.

### Recovery

- Give `JumpEvent` the same requested destination and typed termination truth
  as `MovementEvent`.
- Consume Jump movement before committing position/completion.
- Track actual destination and traversed path through every exit.
- Run the existing continuation guard after every committed Jump step.
- Extend `MovementStepBoundary` only with objective locomotion metadata needed
  by all consumers:
  - trajectory;
  - path index;
  - total path length;
  - optional traversal connector identity later.
- Ensure `Move` exposes its committed boundary before applying post-commit
  incapacity termination.
- Keep forced movement on its own event type and do not consume voluntary
  movement or trigger voluntary OA rules.
- Preserve exact engine-generated OA exposure facts in action discovery. The
  server and frontend must not reconstruct threatened exits from pixels or
  projected geometry.

### Required invariants

- A committed movement step is never free.
- A non-committed step never spends movement or changes position.
- `end_position` is actual settlement; `requested_end_position` is immutable
  intent.
- The final path ends at actual settlement and contains only committed cells.
- Spent plus remaining movement agrees with the action economy.
- Lethal OA before entry prevents entry and does not charge the uncommitted
  step.
- Lethal/hazardous arrival after entry charges the committed step.
- Disengage suppresses voluntary OA exposure and execution consistently.
- Shove/forced movement does not trigger voluntary OA and does not spend the
  target's movement.
- OA discovery reports the first disclosed threatened-domain exit for each
  visible hostile and does not disclose hidden reactors.
- A continuation callback cannot mutate through a second movement authority or
  leave a queue/thread awaiting a decision.

### Focused tests

Create a focused settlement file rather than growing broad runtime tests:

```text
tests/engine/test_movement_settlement.py
```

Cover:

1. normal Move and Jump exact cost/path/settlement;
2. canceled pre-entry step;
3. lethal OA before entry;
4. harmful arrival that incapacitates after entry;
5. partial Jump from insufficient movement;
6. continuation interruption after one committed step;
7. requested versus actual destination;
8. forced movement separation;
9. hidden versus disclosed OA exposures;
10. trajectory/path-index/total-length boundary consistency.

Keep the unique regressions in `tests/engine/test_combat_actions.py` and
`tests/engine/test_action_discovery.py` green.

```bash
uv run pytest tests/engine/test_movement_settlement.py
uv run pytest tests/engine/test_combat_actions.py
uv run pytest tests/engine/test_action_discovery.py
```

### Performance gate

- Cost must scale with the executed path, not every possible action target.
- Do not recover `MovementQueryService` deep dependency scans or hashes.
- Do not serialize/deserialize the complete actor affordance set to validate a
  movement action.
- Do not calculate every movement path during encounter creation.
- Action discovery may calculate paths and disclosed OA exposures when those
  actions are actually requested; it must remain measured and cache only on
  exact existing invalidation facts.
- No background thread or async coordination is permitted.

## Patch 4 — Canonical reciprocal wall and door identity

### Current model problem

A physical edge is presently observed through directional tile/object state.
The east edge of one cell and west edge of its neighbor do not have one
explicit, stable objective identity shared by movement, vision, light,
projection, editing, and replay.

### Recovery strategy

Use `cursed-sol:dnd/core/world_topology.py` as a prototype, then rewrite its
integration around the current `GridMap` lifecycle.

The dependency-neutral core may contain:

- `PhysicalBoundary`;
- `PhysicalBoundaryKind` (`WALL`, `DOOR`);
- `PhysicalBoundarySourceKind` (`INTRINSIC`, `OBJECT`);
- canonical adjacent-position normalization;
- stable boundary IDs;
- reciprocal side indexes;
- object-to-boundary ownership;
- immutable topology snapshot and monotonic revision.

Intrinsic edges should derive deterministic identity from topology identity
plus the canonical adjacent cell pair. Object-backed boundaries should derive
identity from the owning object and authored side. Opening and closing a door
changes state and blocked channels, not boundary identity.

### Integration rules

- `GridMap` remains the high-level owner that knows tiles and placed objects.
- The topology component is a lower dependency-neutral index; it must not
  import `GridMap`, `Entity`, server projection, runtime commands, or concrete
  environment item classes.
- A structural provider protocol may pass normalized facts down from placed
  items without the topology component importing item implementations.
- One accepted grid mutation updates the old and new topology facts exactly
  once.
- No-op door/state writes do not increment the topology revision.
- Replacement and removal delete all obsolete side and object indexes.
- `GridMap.clear()` must replace/reset the topology owner. The abandoned
  integration failed this requirement and could leak boundaries across maps.
- Snapshot restore must rebuild indexes without inventing new IDs or revisions.

### Required invariants

- Reciprocal queries return the same boundary ID and state.
- Door open/close preserves boundary ID.
- Object move/replacement removes old indexes before adding new ones.
- Object destruction removes every boundary it owns.
- Intrinsic channel changes preserve the physical boundary while any channel
  remains and remove it only when no structural channel remains.
- Movement, propagation/vision, light, and projectile queries agree on the
  same physical edge while retaining channel-specific blocking.
- Map clear produces no surviving topology facts.
- Snapshot round-trip preserves topology ID, revision, boundary IDs, owner IDs,
  state, channels, and reciprocal lookup.
- Topology is objective. Privacy filtering occurs later; the topology core does
  not compute observer memberships.

### Focused tests

Recover and adapt only the route-free part of the abandoned
`tests/engine/test_world_topology_identity.py`. Do not recover its Runtime V2
stale-command test.

Required cases:

1. reciprocal wall identity;
2. reciprocal door identity through open/close;
3. intrinsic multi-channel edge identity;
4. no-op revision stability;
5. object move/replacement/removal;
6. `GridMap.clear()` isolation;
7. two consecutive map/scenario loads do not share facts;
8. snapshot JSON round-trip;
9. movement/vision/light query agreement;
10. deterministic IDs for the same restored topology.

Run only focused files:

```bash
uv run pytest tests/engine/test_world_topology_identity.py
uv run pytest tests/engine/test_grid_pathfinding.py
uv run pytest tests/manual/test_directional_environment_legacy_contract.py
```

### Performance gate

- Side lookup must be indexed, not a scan over all objects or tiles.
- One door state change may touch only the boundaries owned by that door.
- No-op writes must allocate no replacement snapshot and increment no revision.
- Normal movement queries must not rebuild topology.
- Map load may build the initial index once and should report its own measured
  subphase; it must not invoke action discovery, player projection, SDK
  generation, serialization round trips, or hashing of unrelated world state.

## Patch order and isolation

| Order | Patch | Dependency | Risk | May be reverted independently |
|---:|---|---|---|---|
| 1 | Spatial reveal idempotency | none | very low | yes |
| 2 | Typed condition evidence | existing content bindings | low | yes |
| 3 | Typed Counterspell evidence | existing reaction/spell bindings | low | yes |
| 4 | Movement settlement corrections | existing event/action economy | medium | yes |
| 5 | Boundary core model and route-free tests | none above | medium | yes |
| 6 | Boundary integration into `GridMap` and environment items | accepted core model | medium-high | yes |

Do not combine topology integration with traversal connectors. Connectors,
stairs, ladders, elevation, Fly unification, and general 2.5-D locomotion are a
later patch family. Canonical boundary identity should become stable first.

## Cross-patch acceptance gate

The recovery is acceptable only when all of the following are true:

- each patch has its focused deterministic regression file;
- relevant existing engine tests pass individually;
- no `server`, FastAPI, SDK, player-product, persistence, or host-control import
  is reachable from the changed engine leaves;
- no new thread, executor, task loop, finalizer, or background queue exists;
- no game-creation path performs eager action inspection or movement-plan
  construction because of these patches;
- no content identity is derived from display text or Python type paths;
- event ordering and objective state agree in every partial/canceled branch;
- topology indexes are cleared and restored correctly;
- forced and voluntary movement remain distinct;
- hidden information is not added to objective-to-player projection by these
  engine patches;
- source scans are used only as supporting evidence, never as the sole proof of
  behavior.

## Explicit exclusions

The following are not part of this recovery:

- Runtime V2 command admission, receipts, lookup, finalization, or durability;
- player-product frames, patches, cues, reducers, or presentation journals;
- generated Python/TypeScript SDK work;
- hosted control, takeover, attachment, lease, or replication systems;
- replay capture obligations or Studio integration;
- `MovementQueryService` dependency digests;
- eager `inspect_actor_affordances()` serialization/hashing;
- per-runtime daemon threads;
- traversal connector action from the abandoned branch;
- broad combat-log enum renames;
- deterministic RNG recovery, shared initiative blocks, equipment slot helper,
  portraits, or standalone source scheduling, which remain separate candidates
  in the larger recovery inventory;
- deletion of current compatibility behavior or tests.

## Completion evidence template

For each implemented patch, record:

```text
Patch:
Files changed:
Focused tests added:
Exact commands run:
Results:
Relevant existing gates:
Creation-time/per-action measurement before:
Creation-time/per-action measurement after:
Dependency/static checks:
Known exclusions still untouched:
```

No patch should be described as complete from compilation, a diff, or a source
scan alone. Completion requires the focused behavioral gates above.
