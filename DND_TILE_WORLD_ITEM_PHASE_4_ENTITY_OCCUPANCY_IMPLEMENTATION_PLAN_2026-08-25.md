# Phase 3 handoff and Phase 4 Entity-occupancy implementation plan

Status: `FINAL_DOUBLE_REVIEW_CANDIDATE`

Implementation is not authorized until two independent reviewers approve the
exact final bytes of this plan together with the final Phase 3 acceptance
ledger. This document is practical guidance for Phase 4 only. It does not
replace the architectural master.

## 1. Authority and accepted handoff

The authority order for this work is:

1. `DND_TILE_WORLD_ITEM_VERTICAL_BOUNDARY_MIGRATION_PLAN_2026-08-17.md`,
   SHA-256
   `50411e5575e6336ca0301acf032797cdf1d5ea885df5ccd37d6619f593e7a193`;
2. `DND_TILE_WORLD_ITEM_ACTIVE_RUNTIME_SCOPE_AMENDMENT_2026-08-24.md`,
   SHA-256
   `f10e2fbbcb6ba8732d078f0c4f2f5276716eb51e32c083068f3cae93c9ba52d6`;
3. the accepted Phase 3 implementation manifest,
   `DND_TILE_WORLD_ITEM_PHASE_3_IMPLEMENTATION_MANIFEST_2026-08-25.json`,
   SHA-256
   `08c756ee62b953dd7326de9d5d06345eb3b948743b5d328559da8df6b40027f0`;
4. the final Phase 3 acceptance ledger,
   `DND_TILE_WORLD_ITEM_PHASE_3_COMPLETION_LEDGER_2026-08-25.md`, SHA-256
   `086e09c9f1329563e846dac0fd10b46331e456dfa2c83786e5de48cb96e113cb`;
   and
5. this exact Phase 4 plan.

The older `DND_TILE_WORLD_ITEM_PLACEMENT_CLEAN_PLAN_2026-08-17.md` is
superseded. Its later phase numbering must not be used. Under the authoritative
master, Phase 4 is **Entity occupancy**. It is not a general event-contract or
transport phase.

Phase 3 is accepted at this handoff. Its unchanged 59-member manifest was
approved by independent correctness and anti-slop reviews. The correctness
review independently reran the complete 614-node active in-process lane; the
anti-slop review independently reverified all manifest members and focused
proofs. No Phase 3 production or test byte changes in this acceptance step.
The only new Phase 3 byte change is the completion ledger's acceptance status
and review record. The two final reviews required by this document validate
that ledger edit and the Phase 4 plan as one package.

Any production or test drift from the accepted Phase 3 manifest before Phase 4
starts is a stop condition until it is classified. Hashes are an internal
wrong-tree and drift guard; they are not a substitute for semantic review.

## 2. Exact objective

Phase 4 replaces three mutable Entity-position indexes with one objective
coordinate and one inverse Tile membership:

```text
Entity.position                         one objective coordinate
        |
        | Entity-owned world command
        v
Tile._entity_uuids                      sole inverse occupant membership
        |
        | local neutral query
        v
GridMap.get_entities_at(position)       derived public lookup
```

The phase also adds the smallest complete world-presence lifecycle needed by
banishment-like mechanics:

```text
detached  --deploy-->  present  --suspend-->  suspended
   ^                     |  ^                    |
   |                     |  |                    |
   +------detach---------+  +------restore-------+
```

Movement remains a present-to-present transition. Suspension preserves the
Entity and Game ownership but removes every objective spatial contribution.
Restore uses ordinary coordinate admission and the ordinary ENTERED fact.

The result must preserve Phase 3's accepted movement settlement: every
committed step updates objective occupancy, carried light, FOV, contacts, and
real sensory deltas before the step completes. `Senses.position` remains
reducer-owned.

## 3. Scope

### 3.1 Included

- private Tile Entity membership and its read-only public query;
- internal GridMap occupancy preflight, atomic commit receipt, publication,
  and local derived queries;
- Entity-owned deploy, move, suspend, restore, detach, and unpublished-discard
  commands;
- Game deployment/removal ownership ordering;
- deletion of `Entity._entity_by_position`, `GridMap._entity_positions`, and
  `GridMap._entities_by_position`;
- deletion of public GridMap Entity mutation compatibility methods;
- collision, endpoint, targeting, AoE, pathfinding, map replacement/clear, and
  runtime-reset callers that read occupancy;
- Banishment migration to suspend/restore;
- Entity-anchored SpatialCondition empty-footprint/restore behavior;
- carried-light absence/restore behavior using the existing composable light
  suppression mechanism;
- existing LEFT/ENTERED event ordering, occupancy-cache invalidation, and
  reducer-owned subjective settlement; and
- collecting active in-process tests and architecture/locality gates.

### 3.2 Excluded

- Phase 5 authored-map/bootstrap migration;
- a new event bus, publisher, event type family, reducer, controller,
  repository, entity service, or occupancy protocol;
- server, SDK, HTTP, database, TypeScript, generated, transport, or deprecated
  compatibility work;
- inactive `dnd/items/environment_content.py` packaging;
- a second Game or global Game registry;
- a general off-plane/world/shard model;
- 3D occupancy, entity altitude, 3D FOV, or vertical targeting;
- redesign of movement rules, connectors, forced movement, action costs,
  condition duration, or concentration; and
- unrelated cleanup merely exposed by caller searches.

Phase 4 may update an active authored mechanic only when it directly bypasses
or consumes Entity occupancy, as Banishment currently does. Any apparent need
to edit an excluded surface is a scope-classification stop, not permission to
restore compatibility.

## 4. Current state that must be cut

The current runtime has four mutually driftable facts:

| Current fact | Current use | Phase 4 treatment |
|---|---|---|
| `Entity.position` | objective actor coordinate | retain as sole coordinate |
| `Entity._entity_by_position` | position-to-Entity list | delete |
| `GridMap._entity_positions` | UUID-to-position dictionary | delete |
| `GridMap._entities_by_position` | position-to-UUID set | replace with Tile membership |

The current public GridMap methods `register_entity`, `unregister_entity`,
`move_entity`, `stage_entity_position`, and `publish_staged_entity_position`
allow callers to mutate occupancy without an Entity-owned transaction. They
are deleted, not deprecated or aliased.

The current `Entity.get_all_entities_at_position` is also deleted. Its two
production consumers (`can_end_movement_at` and Naturally Stealthy cover) read
one Tile through `GridMap.get_entities_at` and resolve UUIDs through
`Entity.get`. Tests move to the same public boundary.

The current Banishment implementation directly writes all three duplicate
indexes and manually emits LEFT/ENTERED. It becomes the first real consumer of
the generic suspend/restore commands. No spell may retain private occupancy
writes.

The implementation-start ledger must repeat the caller search over active
Python and classify every match. Known direct consumers are not a closed list;
the hard-cut zero-reference gate is authoritative.

## 5. Target ownership and invariants

### 5.1 Tile

`Tile` gains one private `set[UUID]` membership collection. It exposes a
defensive read-only snapshot through `get_entity_uuids()`. It exposes no public
add, remove, or move method.

GridMap owns one narrow private complete-set replacement method on Tile, in the
same style as the existing private object-band replacement methods. A caller
cannot retain a mutable alias to Tile membership.

For every present Entity:

1. `Entity.position` is an exact `(int, int)` coordinate identifying one live
   Tile;
2. that Tile contains the Entity UUID once;
3. no other Tile contains the UUID; and
4. `GridMap.get_entity_position(uuid)` returns the coordinate only after a
   neutral `BaseBlock` lookup and membership verification.

For every detached or suspended Entity:

1. no Tile contains the Entity UUID;
2. `GridMap.get_entities_at` cannot return it;
3. `GridMap.get_entity_position` returns `None`; and
4. the Entity's own objective `position` may retain its last/return coordinate.

Uniqueness is maintained inductively through the private transition boundary:
attach requires no old membership, move requires the exact old membership and
an absent destination membership, and detach/suspend requires the exact old
membership. No hot command scans the map to rediscover a reverse index.

### 5.2 GridMap

GridMap retains no Entity-position dictionary and imports no `Entity` or
`dnd.spatial` module. It resolves identities only through neutral
`BaseBlock.get`.

Use one small frozen hot receipt, for example
`GridEntityMembershipReceipt`, containing:

- `entity_uuid`;
- `old_position: tuple[int, int] | None`; and
- `new_position: tuple[int, int] | None`.

The exact class name is not architectural. Do not create a Pydantic wire DTO or
a receipt hierarchy for this internal commit token.

The private GridMap transition accepts an Entity UUID, expected old coordinate,
and optional new coordinate. It:

1. requires a live neutral `BaseBlock` identity;
2. validates exact tuple shape and exact integer components for every supplied
   coordinate;
3. requires every supplied Tile to exist;
4. verifies the expected old Tile contains the UUID when old is present;
5. verifies the destination does not already contain the UUID when it differs
   from old;
6. snapshots only the affected one or two Tile membership sets;
7. replaces those complete sets atomically;
8. restores both snapshots if commit work raises;
9. invalidates occupancy paths exactly once after a successful real change;
   and
10. returns the exact receipt without publishing an event.

The transition does not decide creature collision, faction, size, spell
targetability, movement cost, or perception. Those remain in their established
admission/rules owners.

The private publisher validates that the receipt still describes the
committed Entity coordinate/membership result and publishes:

- LEFT when `old_position` is present, with the destination in
  `event.old_position` only when `new_position` is present; then
- ENTERED when `new_position` is present, with the source in
  `event.old_position` only when `old_position` is present.

These are already-committed, non-vetoable objective facts. Use the existing
committed spatial publication path; do not add a publisher. Handler exceptions
after the commit retain the existing `PositionPublicationError` contract:
objective Entity and Tile state remains committed.

`get_entities_at(position)` reads one Tile and returns a defensive UUID set.
Missing Tiles return an empty set. It may fail loudly if its private membership
references a missing neutral block or a block whose objective coordinate does
not match that Tile; it must not silently manufacture a repair.

`get_entity_position(uuid)` is retained only as a derived convenience query.
It reads the neutral block's objective coordinate and returns it only when the
Tile at that coordinate contains the UUID. Thus suspended/detached identities
return `None` without a reverse dictionary.

### 5.3 Entity state

Retain `is_deployed` with its existing meaning: the Entity currently occupies
the world. Add only one explicit boolean needed to distinguish suspension from
ordinary detachment, such as `is_spatially_suspended`. Do not introduce an enum,
state-machine class, world-presence object, or controller.

Valid states are:

| State | `is_deployed` | suspended flag | Tile member | observer registered |
|---|---:|---:|---:|---:|
| detached | false | false | no | no |
| present | true | false | yes | yes |
| suspended | false | true | no | no |

Both flags may never be true together. Movement is legal only in `present`.
Restore is legal only in `suspended`. Deploy is legal only in `detached`.
Detach accepts `present` or `suspended` and ends in `detached`.

Entity remains the only owner of its `_set_position` method. GridMap never
calls inherited `BaseBlock.set_position`, because that recursively writes
Senses and child blocks.

### 5.4 Game

Game continues to own the set of committed Entities in the one in-process
game. It does not own coordinates or Tile membership.

Deployment and removal must preserve Game ownership across the existing two
failure classes:

| Operation result | Game ownership after call |
|---|---|
| deploy precommit failure | absent |
| deploy commit succeeds and publication succeeds | present |
| deploy publication failure after committed occupancy | present |
| detach precommit failure | retained |
| detach commit and publication succeed | removed |
| detach publication failure after committed absence | removed |

Implement this with ordinary try/except/finally ordering around the Entity
command. Do not add a pending-entity registry or transaction manager.

## 6. Exact command contracts

### 6.1 Deploy / attach

Preconditions:

- entity creation is committed;
- state is `detached`;
- Game does not own a different instance at the UUID; and
- the destination is an exact coordinate naming a live Tile.

Commit:

1. preflight Tile membership through GridMap;
2. snapshot the prior Entity coordinate and flags;
3. set the Entity objective coordinate through `_set_position`;
4. commit `None -> destination` Tile membership;
5. set state to `present`;
6. register the observer after the objective commit and before ENTERED; and
7. publish ordinary ENTERED with `old_position=None`.

If anything before membership commit completes fails, restore the coordinate,
flags, and Tile membership before any spatial fact. The production observer
registration boundary becomes registration-only: it installs the observer
identity but does not refresh a footprint, subscribe cells, mutate Senses, or
emit an event. ENTERED remains the sole initial reducer refresh. A publication
failure does not roll back committed deployment.

### 6.2 Move

Preconditions:

- state is `present`;
- destination is an exact live Tile coordinate; and
- established movement/forced-movement/connector admission has already
  accepted the gameplay transition.

Commit:

1. no-op immediately when destination equals current objective position;
2. snapshot the old objective coordinate;
3. set `Entity.position` to the destination;
4. commit exact `old -> destination` Tile membership;
5. on commit failure, restore `Entity.position` and both Tile snapshots;
6. publish LEFT with destination; and
7. publish ENTERED with source.

Never snapshot, assign, or roll back `entity.senses.position`. A precommit
failure changes no objective state, occupancy revision, event, light, or
subjective projection. A publication failure retains committed Entity/Tile
state and raises `PositionPublicationError` exactly as the accepted movement
tests require.

### 6.3 Suspend

Expose one Entity command for a condition/mechanic to suspend world presence.
Its exact public name may follow local style, but it is not a GridMap command.

Preconditions:

- state is `present`; and
- exact current Tile membership agrees with `Entity.position`.

Commit:

1. commit `current -> None` membership without changing
   `Entity.position`;
2. set `is_deployed=False` and suspended flag true;
3. unregister the observer and its cell subscriptions;
4. publish LEFT with no destination; and
5. let existing event consumers settle anchored conditions, carried light,
   other observers, and navigation before LEFT completes.

The Entity remains in its identity registry and in its owning Game. Its child
blocks, conditions, concentration links, duration, and equipment remain live
unless their own rules remove them.

### 6.4 Restore

Preconditions:

- state is `suspended`;
- the condition/mechanic has selected an exact admitted coordinate; and
- no Tile currently contains the Entity UUID.

Commit:

1. snapshot the retained objective coordinate and flags;
2. set the chosen objective coordinate through `_set_position`;
3. commit `None -> destination` membership;
4. set state to `present`;
5. clear the suspended flag;
6. register the observer through the registration-only boundary; and
7. publish ordinary ENTERED with `old_position=None`.

ENTERED is the only restoration fact. Do not add RESTORED, BANISHED, TELEPORTED,
or world-presence event types. The owning condition may publish its own normal
condition removal/application facts.

### 6.5 Detach / undeploy

For a present Entity, detach commits `current -> None`, unregisters its
observer/subscriptions, sets `detached`, and publishes LEFT without a
destination. For a suspended Entity, detach changes only suspended-to-detached
ownership state because objective spatial presence is already empty; it emits
no duplicate LEFT. A detached Entity is a no-op for idempotent Game teardown.

`discard_unpublished_runtime` remains the exceptional silent cleanup for an
Entity whose construction never entered committed encounter authority. It uses
the same private membership commit boundary but publishes no LEFT/ENTERED. It
may permanently clean attached lights and registry identities as it does now.
This path must not become a general silent undeploy API.

### 6.6 Suspend/restore failure states

The generic Entity commands retain the existing position failure distinction:

| Command outcome | Entity/Tile result | observer | Game | raised result |
|---|---|---|---|---|
| suspend precommit failure | present at source | retained | retained | `PositionCommitError` |
| suspend LEFT publication failure | suspended, Tile-absent, retained coordinate | absent | retained | `PositionPublicationError` |
| restore precommit failure | suspended and Tile-absent | absent | retained | `PositionCommitError` |
| restore ENTERED publication failure | present at committed destination | registered | retained | `PositionPublicationError` |

A generic command never rolls back the committed row after publication begins.
Mechanics that combine a world-presence command with another transaction must
explicitly reconcile these four states; they may not assume every exception
means the old objective state remains.

## 7. Events, caches, light, and subjective settlement

Phase 4 reuses the existing EventQueue and `SpatialSensesSystem`. It adds no
event layer.

### 7.1 Ordinary movement step

The accepted order remains:

1. movement-family precommit phases admit/veto the transition;
2. `Entity.position` and old/new Tile membership commit;
3. occupancy revision advances once and objective path cache clears;
4. LEFT with destination publishes;
5. Entity-anchored conditions retain their footprint during LEFT;
6. ENTERED EFFECT handlers use committed `Entity.position` or event position;
7. at ENTERED pre-completion, attached light moves and publishes any real light
   delta;
8. `SpatialSensesSystem` reduces light children and then the settled ENTERED
   fact, emitting only real sensory deltas;
9. ENTERED completes; and
10. the established parent movement step completes.

LEFT with a destination continues selecting no observers for an intermediate
subjective reduction. It must not create a temporary empty footprint, darkness
flash, missing contact, or stale navigation state between adjacent steps.

### 7.2 Suspend / present detach

The order is:

1. Entity membership/state commits absent and occupancy paths invalidate once;
2. the suspended/detached observer and subscriptions are removed;
3. LEFT without a destination reaches EFFECT;
4. Entity-anchor handlers transition their footprints to empty without
   deactivation;
5. at pre-completion, the existing attached-light callback installs one
   world-absence suppression token and publishes the real light delta;
6. `SpatialSensesSystem` reduces the complete objective absence for remaining
   candidate observers; and
7. LEFT completes.

The absent Entity's own Senses projection may retain its last subjective state
while it is unregistered. No code writes it directly. Restore registration and
ENTERED produce the next projection.

### 7.3 Deploy / restore

The order is:

1. Entity coordinate/membership/state commits present and occupancy paths
   invalidate once;
2. the observer identity is registered, without refreshing or subscribing,
   before ENTERED reduction;
3. ENTERED EFFECT restores/relocates Entity-anchored conditions;
4. at pre-completion, each attached source first moves to the committed Entity
   coordinate while still suppressed, then clears only the world-absence
   suppression token;
5. any newly effective illumination publishes as causal light children;
6. `SpatialSensesSystem` reduces light children and the settled ENTERED fact;
   and
7. ENTERED completes.

This gives a restored observer an ordinary empty-to-full/current projection and
prevents light from briefly reappearing at the retained origin when the owning
condition chooses another return coordinate.

### 7.4 Composable light suppression

Reuse `GridMap.set_block_light_suppressed`. Add one stable Entity world-absence
token alongside the existing death token. Tokens compose:

- suspend/detach installs only the world-absence token;
- deploy/restore clears only the world-absence token;
- death continues independently owning the death token; and
- cleanup of a destroyed/unpublished Entity may permanently remove attached
  sources and all of that block's tokens.

The current `GridMap.unregister_entity` behavior that blindly removes every
suppression token disappears with that public method. No lifecycle may clear a
token owned by another rule.

An attached light created while its Entity is detached/suspended must start
effectively suppressed. Install the same world-absence token when a newly
constructed Entity begins undeployed; this emits no light fact when no source
exists and causes any source attached during pre-deployment composition to
start ineffective. Deploy/restore clears it only at ENTERED pre-completion.
Provisional Entity discard and terminal light cleanup remove the owner row as
they already do. Do not add a parallel light registry. A focused test must
prove the result, including composition with the death token.

### 7.5 Cache rules

- every real attach, move, suspend, restore, or present-detach commit advances
  the occupancy revision once and clears objective path cache once;
- no-op moves and rejected commits change no revision;
- Entity occupancy alone does not advance optical, propagation, or light
  topology revisions;
- attached-light deltas advance illumination/optical revisions only through
  existing light code and only when resolved light actually changes;
- anchored physical-optics conditions invalidate through their existing
  footprint lifecycle; and
- subjective navigation becomes dirty/reduces only through the existing
  objective event and real sensory-delta boundary.

## 8. Entity-anchored SpatialConditions

The existing anchor handler expands from ENTERED-only to LEFT and ENTERED at
EFFECT:

| Fact | Required behavior |
|---|---|
| LEFT with destination | retain footprint; wait for ENTERED |
| LEFT without destination | transition footprint to empty; keep owner active |
| ENTERED after move/deploy/restore | relocate/restore at committed position |
| condition/concentration removal | ordinary deactivation; do not resurrect |

The current `transition_footprint(set())` deactivates and therefore cannot be
used for suspension. Add one narrow method on the existing SpatialCondition
family for an attached owner's temporary absence. It:

1. snapshots the old footprint and physical optics;
2. releases positional terrain/light/mechanics for the old footprint;
3. stores an empty affected-position set through the existing GridMap
   condition index (the owner remains registered and active);
4. updates existing spatial-handler position indexes to empty;
5. settles physical optics and owned light deltas;
6. applies normal exit consequences where the existing AreaCondition contract
   requires them; and
7. publishes the existing footprint-change fact with exact before/after
   positions.

Restore uses the existing `relocate_anchor`/`move_zone` delta path from empty to
the new computed footprint. Do not add an anchor receipt, anchor registry, or
second condition state machine.

Required proofs include a non-concentration Entity aura and a linked
concentration zone. Suspension retains the former with an empty footprint.
If concentration ends while suspended, the linked zone deactivates normally,
and later Entity restore does not recreate it.

## 9. Banishment migration

`BanishedCondition` no longer stores `original_position`; the suspended
Entity's retained objective `position` is the return origin. It never writes a
GridMap or Entity private index and never fires a spatial event itself.

Application:

1. call the Entity suspend command with the condition-application event as
   parent before installing the denial transform, so a suspend precommit
   failure cannot leak unrecorded modifier ownership;
2. apply the condition's existing owned agency-denial/incapacitation transform;
   and
3. complete through the ordinary condition lifecycle.

Removal:

1. read the retained `target.position` as the preferred return coordinate;
2. preserve the currently authored occupied-origin rule rather than redesigning
   spell semantics in an occupancy migration: when occupied, select the first
   occupant in stable UUID order and try the existing ordered eight adjacent
   offsets through ordinary Entity movement;
3. move at most that one occupant; if no offset succeeds, or if another
   occupant remains, restore the target into the same occupied origin exactly
   as the current fallback does;
4. call Entity restore with the condition-removal event as parent; and
5. only then release the condition-owned denial transform through normal
   cleanup.

Phase 4 makes the existing choice deterministic and routes every displacement
through Entity; it does not decide whether Banishment should instead move the
returning target to the nearest unoccupied cell. That rules change requires a
separate explicit decision. Do not add a GridMap-wide Banishment special case.

### 9.1 Banishment transaction reconciliation

`BaseCondition.apply` discards an uncommitted condition when `_apply` raises,
while removal leaves an applied condition intact when `_remove` raises.
`BanishedCondition` must therefore reconcile world-presence failures explicitly:

| Failure point | Required final state |
|---|---|
| suspend precommit failure | Entity remains present; denial transform was not installed; condition application fails normally |
| suspend LEFT publication failure | perform a new ordinary compensating restore to the retained coordinate, then re-raise the original publication failure; condition remains unapplied |
| later application/finalization failure after committed suspend | the condition's idempotent uncommitted-state release hook performs the same ordinary compensating restore if the target is still suspended, then ordinary modifier cleanup runs |
| removal restore precommit failure | target remains suspended; condition and denial remain applied; removal fails and can be retried |
| removal ENTERED publication failure | objective restore is already committed; `_remove` recognizes the present/membership state, does not call restore again, and allows ordinary condition/denial cleanup to finish |

The compensating restore is a new committed `None -> destination` transition
with its own ENTERED lifecycle; it is not rollback of a published LEFT. If that
compensation itself has a precommit failure, the original application failure
must surface together with an explicit invariant failure rather than silently
orphaning the target. If compensation ENTERED publication fails after its
commit, the target is objectively present and unowned denial state is still
cleaned. Do not add a general transaction manager or change BaseCondition for
this one mechanic.

The denial transform needs one immediate provisional ownership list using the
existing `ModifierOwnership` rows. Immediately after
`apply_incapacitated_transform` returns—and before advancing the condition event
through any phase that can raise—store those five rows on a private
`BanishedCondition` runtime attribute. If `_apply` or finalization then fails,
the idempotent uncommitted-state release hook calls the existing
`remove_modifier_ownership` on that list and clears it. After `_apply` returns
and BaseCondition has copied the same rows into its ordinary modifier ledger,
`_finalize_application` clears only the provisional list; ordinary committed
removal is then owned solely by BaseCondition. Do not create a second modifier
manager, transform receipt type, or cleanup registry.

The removal-side caught `PositionPublicationError` is not treated as evidence
that restore failed: its `position_committed=True` fact and the public
Entity/Tile state are verified, the removal event records that publication
failed after commit, and normal condition cleanup completes. This prevents a
retry from attempting to restore an already-present Entity.

Tests must cover ordinary removal, concentration cleanup, occupied-origin
fallback, suspend/restore parent lineage, and absence from objective AoE,
collision, target, observer, aura, and light queries while suspended.

## 10. Caller and reset migration

### 10.1 GridMap readers

Port every direct read of `_entities_by_position` to the local Tile membership
query. Known GridMap-owned cases include:

- Tile replacement protection;
- `is_walkable_for` collision;
- blocker-reason reporting; and
- `clear` deployment rejection.

`clear` may inspect all Tiles because clearing is already whole-map work. Hot
position, collision, path, targeting, and AoE queries inspect only the queried
Tile or affected bounded positions.

### 10.2 Entity and gameplay readers

Port position-local Entity logic to `GridMap.get_entities_at` plus
`Entity.get`. Existing active AoE, spell, item, monster, scenario, sensory, and
path consumers that already use `get_entities_at` retain that public query and
need only regression validation.

Identity-wide methods such as `Entity.get_all_entities` and faction registries
remain identity queries, not spatial queries. A spatial rule must not infer
world presence merely from the identity registry. If the caller needs spatial
presence, it must use Tile/GridMap membership or explicitly require
`is_deployed`.

Two current monster-trait rules violate that boundary:
`pack_tactics_advantage` and `_has_adjacent_ally` scan
`Entity.get_all_entities()`. Port both to the bounded target Tile plus its eight
neighbors using `GridMap.get_entities_at`, then resolve UUIDs through
`Entity.get` and retain the exact existing self/target, ally, action-capability,
and `distance_to_entity(target) <= 5` filters. Including the target Tile
preserves the current co-located-ally result when mechanics admit shared
occupancy. A suspended but otherwise action-capable ally must not satisfy
either rule. `Entity.materialize_all_navigation` remains the one legitimate
identity-wide traversal here because it explicitly filters deployed Entities.

### 10.3 Game and tests

Production deployment remains `Game.deploy_entity`; movement remains Entity
owned. Active tests that directly call GridMap Entity mutators are rewritten to
create/deploy a real test Entity and invoke its public movement/world command.
In particular, the collecting in-process movement demonstration in
`tests/manual/test_08_world_model_and_movement.py` must stop registering raw
UUIDs in GridMap.

Do not retain a compatibility facade for excluded or legacy tests. Classify
`tests/manual/test_128_antimagic_field.py` and any other direct GridMap mover by
the active-runtime rules: port an active in-process mechanic to Entity movement;
leave an excluded legacy/transport subject untouched and outside deletion
gates.

### 10.4 Runtime reset

`reset_engine_runtime` clears the Entity identity registry as before and no
longer clears `_entity_by_position`. Resetting GridMap drops the Tiles and thus
their memberships. Runtime-reset tests seed/assert only public registries and
observable fresh-map state; they stop fabricating deleted private indexes.

## 11. Implementation sequence

### Slice 4.0 — Freeze and characterize

No production edits.

1. verify every accepted Phase 3 manifest member still matches;
2. record the exact active callers/readers/writers of all three deleted indexes,
   all five public GridMap Entity mutators, `GridEntityPositionReceipt`, and
   `Entity.get_all_entities_at_position`;
3. inventory every identity-wide Entity iteration used for a spatial rule and
   classify it as a bounded Tile query or an explicitly deployed-filtered
   lifecycle traversal; this includes both monster adjacency rules;
4. classify collecting tests using the active-runtime amendment;
5. pin the current successful Phase 3 614-node lane and relevant Phase 4
   selectors;
6. add/identify public characterization for publication-failure commitment,
   per-step settlement, initial deployment reduction, Banishment, anchored
   conditions, and attached light; and
7. stop if current bytes or scope differ from the accepted handoff.

### Slice 4.1 — Atomic occupancy-authority hard cut

This is one checkpoint; it must not land half dual-written.

1. add private Tile membership and defensive query;
2. replace both GridMap Entity dictionaries with the private local membership
   receipt/commit/publish boundary;
3. retain only derived public `get_entities_at` and `get_entity_position`;
4. route Entity deploy/move/detach/unpublished discard and Game ownership
   ordering through the new boundary;
5. port GridMap collision/replacement/clear and Entity position-local readers;
6. port active direct-mutation tests/callers;
7. delete `Entity._entity_by_position`, both GridMap dictionaries, the old
   receipt, five public GridMap mutation methods, and
   `Entity.get_all_entities_at_position`; and
8. run focused occupancy, movement, connector, forced-movement, path, reset,
   and architecture gates.

The checkpoint is rejected if any compatibility alias, dual-write period, or
second reverse index remains.

### Slice 4.2 — World-presence lifecycle

1. add the one suspended-state flag and Entity suspend/restore commands;
2. make present detach eventful and suspended detach nonduplicating;
3. implement observer/subscription removal and restore ordering;
4. extend the existing attached-light pre-completion callback with the
   composable world-absence token;
5. extend the existing Entity-anchor handler for LEFT without destination and
   restore from empty;
6. migrate Banishment and remove its stored origin/private writes; and
7. run focused suspension, condition, concentration, light, FOV, senses,
   collision, AoE, and Banishment gates.

### Slice 4.3 — Integrated settlement and hard-cut certification

1. run the accepted movement-step, jump, connector, forced-movement,
   turn-start, light, FOV, subjective-contact, spatial-condition, spell, item,
   scenario, and runtime-reset lanes;
2. run complete active in-process and architecture lanes;
3. collect the exact active node set and compare against the accepted baseline
   plus authorized Phase 4 tests;
4. run zero-reference and dependency gates;
5. run structured locality checks on small and large maps;
6. create a deterministic Phase 4 implementation manifest and completion
   ledger; and
7. obtain independent correctness and anti-slop approval of the exact final
   candidate before Phase 4 is complete.

No Slice 4.3 failure is repaired outside this plan. A repair changes candidate
bytes, invalidates reviews, updates the manifest/ledger, and reruns affected
lanes.

## 12. Required public behavior tests

Read `HOW_TO_TEST.MD` before writing or changing tests. Tests assert public
behavior, events, causal lineage, revisions, and replay/projection results.
They do not assert private source text, private dict shape, monkeypatched call
counts, sleeps, or implementation-only helpers.

### 12.1 Occupancy authority

- deploy makes Entity position and one Tile query agree;
- move removes old and adds new membership exactly once;
- several Entities may be represented on one Tile when gameplay rules admit
  that state, with no duplicate UUID;
- an arbitrary BaseBlock UUID has no public path into Entity membership;
- defensive query results cannot mutate Tile membership;
- derived `get_entity_position` returns a coordinate only for a present member;
- Tile replacement and map clear reject live occupancy;
- a rejected destination/commit changes neither coordinate, membership,
  occupancy revision, event stream, light, nor Senses; and
- publication failure preserves committed coordinate/membership while Senses
  remains at its last completed reduction.

### 12.2 Movement settlement

- LEFT then ENTERED order and exact parent lineage remain stable;
- LEFT-with-destination produces no intermediate sensory or empty-zone state;
- ENTERED EFFECT reads committed `Entity.position` while
  `Senses.position` is the prior projection;
- each accepted path step settles attached light and real observer deltas before
  its step completes;
- jump, connectors, teleports, and forced movement preserve their current cost
  and committed-publication failure semantics; and
- a no-op update emits nothing and changes no revision.

### 12.3 Suspension and restoration

- suspended Entity keeps its identity, Game ownership, child state, and retained
  coordinate but appears in no Tile/objective spatial query;
- its observer registration/subscriptions are absent;
- other observers lose its contact through the LEFT reduction;
- its attached light contributes no resolved illumination;
- a nonconcentration anchored aura remains active with empty footprint;
- restore admits a destination, restores membership/observer/aura/light, and
  yields ordinary causal ENTERED/sensory facts;
- death and world-absence light suppressions compose independently;
- detach while suspended emits no second LEFT; and
- concentration/condition destruction while suspended prevents zone
  resurrection on restore.

### 12.4 Banishment

- application uses suspend and owns its existing denial transform;
- suspend precommit failure leaves the Entity present with no denial leak;
- suspend LEFT publication failure compensates to objective presence and leaves
  no applied BanishedCondition;
- failure after the denial transform but before condition EFFECT completion
  removes all five provisionally owned denial modifiers;
- target is absent from collision, AoE, objective targeting, perception,
  anchored footprint, and carried-light results;
- ordinary cleanup restores at the retained origin;
- restore precommit failure retains the suspended applied condition for retry;
- restore ENTERED publication failure retains committed presence and completes
  denial/condition cleanup without a second restore;
- occupied origin preserves the characterized one-occupant/eight-offset rule
  with stable UUID selection and ordinary Entity displacement;
- when no adjacent displacement succeeds or another occupant remains, the
  target restores into the same occupied Tile as the characterized fallback;
  and
- parent/child events show condition -> LEFT and condition removal -> ENTERED
  lineage.

Monster-trait regression rows separately prove that a co-located present ally
retains the characterized adjacency result while a suspended action-capable
ally at the same retained coordinate grants neither Pack Tactics nor Sneak
Attack adjacency.

### 12.5 Locality

- `get_entities_at` produces the same bounded work on small and large maps;
- one-step move touches only source and destination membership;
- suspend/detach touches only the source membership;
- restore/deploy touches only the destination membership;
- occupancy path invalidation is one revision per commit, independent of map
  area; and
- condition/light/senses work remains proportional to affected footprint,
  light radius, and indexed observer candidates.

Use existing structured diagnostics where they already expose the required
counter. Add no production diagnostic abstraction solely to prove an obvious
constant-time dictionary/Tile lookup; if a new counter is necessary, it must be
one narrow immutable diagnostic value reused by all occupancy commands.

## 13. Validation matrix

The implementation ledger records exact commands and results. At minimum it
includes:

1. compile of every changed active Python file;
2. scoped `git diff --check` over the Phase 4 candidate;
3. focused new Entity occupancy/world-presence selectors;
4. Entity composition, identity registry, runtime reset, GridMap/pathfinding,
   movement settlement, action-cost/position-commit, jump, connector, and
   forced-movement modules;
5. Banishment/condition-transform, condition lifecycle, spatial effects,
   concentration, and complete spell-family modules;
6. senses/light/stealth, objective-state, AoE, item/equipment/torch, direct
   scenario deployment, and encounter modules affected by occupancy;
7. the exact accepted turn-start perception proof;
8. complete architecture tests;
9. complete active in-process lane;
10. exact collect-only node-set count/hash;
11. structured locality lane; and
12. manifest verification with zero mismatches.

The implementation-start ledger must name exact selectors before code changes.
Temporary test counts are evidence, not architectural requirements. A new test
changes the expected active node set only when its maintained subject is active
in-process mechanics.

## 14. Hard-cut and architecture gates

Active production and active collecting tests must have zero remaining
definitions/imports/calls of:

- `Entity._entity_by_position`;
- `GridMap._entity_positions`;
- `GridMap._entities_by_position`;
- `GridEntityPositionReceipt`;
- `Entity.get_all_entities_at_position`;
- public `GridMap.register_entity`;
- public `GridMap.unregister_entity`;
- public `GridMap.move_entity`;
- public `GridMap.stage_entity_position`; and
- public `GridMap.publish_staged_entity_position`.

Classify excluded legacy/transport matches; do not edit them to satisfy an
active gate.

The final dependency check proves:

- GridMap imports no Entity, concrete item, or concrete SpatialCondition;
- Entity imports no `dnd.spatial` module;
- core events import no GridMap, Entity, Senses, authored content, or renderer;
- Tile exposes no public Entity-membership mutator;
- Game owns Entity membership in the game, not coordinate/membership mutation;
- no late import, `TYPE_CHECKING` cycle mask, reflection capability,
  compatibility facade, parallel registry, or service/controller layer was
  introduced; and
- `Senses.position` has no new writer outside the subjective reducer boundary.

## 15. Stop conditions

Stop and return to the supervisor before broadening or improvising if:

- the authoritative master hash or accepted Phase 3 member bytes drift before
  the Phase 4 baseline is frozen;
- a required active caller cannot be migrated without server/SDK/generated or
  inactive-content work;
- the implementation appears to require Entity imports in GridMap or spatial
  imports in Entity;
- a partial slice would retain dual occupancy authority;
- a rule appears to require Tile membership to store Entity objects rather than
  UUIDs;
- suspension seems to require a new event family, world registry, condition
  controller, or light registry;
- movement EFFECT handlers require direct Senses writes;
- a publication failure is being "fixed" by rolling back an already published
  objective commit;
- Banishment return behavior changes beyond deterministic routing of its
  characterized current rule;
- a test can pass only by asserting private state/source layout or restoring a
  deleted compatibility API; or
- Phase 5 bootstrap/authored-map work becomes necessary.

## 16. Completion definition

Phase 4 is complete only when:

1. Tile membership and `Entity.position` are the only Entity occupancy facts;
2. all three old indexes and every public GridMap Entity mutator are absent
   from active scope;
3. deploy/move/detach/suspend/restore preserve the state and failure tables;
4. collision, targeting, AoE, pathfinding, reset, and active tests use local
   Tile/GridMap queries;
5. Banishment uses generic suspend/restore with no stored duplicate origin or
   private writes;
6. anchored conditions and carried light disappear/restore at the accepted
   event boundaries;
7. per-step objective-before-subjective settlement and turn-start behavior
   remain green;
8. no dependency or anti-slop prohibition is violated;
9. complete active validation and locality gates pass;
10. the final deterministic implementation manifest and completion ledger
    match current bytes; and
11. independent correctness and anti-slop reviewers approve the exact final
    candidate.

Phase 5 remains unopened after this completion.

## 17. Plan review requirements

Reviewer A performs a correctness/architecture review of the final Phase 3
ledger and this exact plan against the authoritative master and current active
runtime. It must explicitly validate ownership, command transactions, Game
failure ordering, event/cache/senses order, suspension, Banishment, anchor/light
settlement, caller completeness, tests, scope, and stop conditions.

Reviewer B performs an independent anti-slop/implementability review of the
same exact bytes. It must explicitly look for duplicate authority, needless
layers, compatibility facades, hidden global scans, overfitted spell logic,
event/reducer duplication, direct Senses writes, transport contamination,
private-state tests, and any ambiguous instruction that would force the
implementer to improvise.

Any MUST-FIX finding is applied to the plan, after which both reviewers inspect
the new exact bytes again. Approval messages remain external so the approved
plan is not modified after exact-byte review.
