# Spell VFX plan — ECS, import DAG and retained-event review

Decision: **APPROVE the plan in the reviewed scope. No unresolved architectural
plan blocker remains.** This is a design approval, not implementation
authorization, a test result, or a claim that the spells already work.

Reviewed document: `agent_docs/SPELL_VFX_IMPLEMENTATION_PLAN_2026-10-04.md`.
Frozen SHA256:
`2cf346fd78d6afd648cf97c142c39733e23089dd7c82de58d400cc852e280ce1`.
Source baseline declared by the plan:
`95a47cd5ca508838bce8a2e67d6fe1fc591ce4e6`.
Review date: October 4, 2026.

## Scope and method

Read `AGENTS.md`, the current position in `RECOVERY_PLAN.md`,
`HISTORY_BEFORE_ME.md`, the retained-event requirements in
`agent_docs/USER_COMPLAINTS.md`, and `HOW_TO_TEST.MD`. Inspected the plan against
the actual native condition/value/handler, health/death, placement, spell,
creation/encounter, projection and presentation types. This review is bounded to
ECS ownership, import direction, transaction feasibility, retained facts and
shared presentation. It does not independently certify every SRD rule or pixel
in the delivered artwork.

Only this receipt was written. No production code, tests, artwork, rendering or
external chat was changed or run. Same-request reviewer coordination did not
read or message any other chat.

## Findings resolved in the frozen revision

1. **Antimagic must suppress contributions without replaying application.**
   The current `AntimagicSuppression.on_membership_changed` in
   `dnd/spells/abjuration.py:3230` clears modifier/handler/child ownership and
   calls `add_condition` again. `BaseCondition.apply` invokes `_apply`, so that
   route can repeat one-time cleanup, grants or healing; the removed condition
   also leaves ordinary duration membership. The corrected plan at lines
   459–470 explicitly replaces that path with additive provider UUID tokens on
   the same retained condition. Existing modifier, handler, spatial-handler and
   parent/child identities remain authoritative. Aggregation and dispatch gate
   their contributions, while duration and final cleanup keep running. Direct
   contributions such as Shillelagh's `weapon.attack_overrides`, immunity sources,
   actions, lights and area providers are included. Player-toggle `enabled`
   state is not commandeered. No second condition or modifier manager is
   proposed.

2. **Numeric suspension and landing/fall are new native work.**
   Existing `Entity` placement has XY and `OccupancyLayer`; numeric object
   heights already exist in `dnd/types/world_placement.py`. Current
   `ForcedMovementEvent`/`ForcedMovementFact` do not carry the required typed
   object/creature trajectory and heights, and
   `GridMap._publish_entity_membership` at `dnd/core/gridmap.py:2302` skips
   unchanged XY/layer. The inspected native code has no existing fall-damage
   owner to reuse. The corrected plan at lines 414–442 discloses the new bounded
   forced-height/fall transaction, landing policy and unsupported-void boundary;
   carries height through actor/observer/movement after-values; and names
   range, LOS, occupancy, area and height-only publication as consumers. Its
   regression contract preserves ordinary Fly and excludes general multi-floor
   navigation or a physics engine. This is sufficiently concrete as a proposed
   dependency, subject to the human approving the disclosed scope.

3. **Harm/Feast overlap cannot use destructive same-name replacement.**
   `BaseBlock.prepare_condition_application` at
   `dnd/core/base_block.py:1734` prepares removal of a previous same-name owner.
   That cannot retain a weaker cast for later reactivation. Plan lines 254–268
   now retain per-cast source conditions with independent clocks and share one
   public effect child through the existing `add_shared_subcondition`/parent
   graph (`dnd/core/base_conditions.py:841`). The bounded owner chooses the
   strongest/latest eligible contribution and updates its one modifier and
   committed stats without application/healing replay. Expiry, suppression and
   exact-source removal are acceptance cases. No generic stack manager is added.

## Existing owners and boundaries correctly reused

- `dnd/core/effect_types.py` already provides frozen `ResolutionRef` variants,
  `ApplicationMembership`, `ObservedChangeRef` and `EffectOrigin`. Extending
  application data for admitted Chain Lightning edges preserves native target
  selection and causality. It avoids a renderer-created target graph or another
  paid spell execution.
- `ConditionState` already has `energy_type`; `ConditionLayer` already has
  `whenEnergyType`. Fire Shield therefore needs an explicit producer snapshot,
  not another warm/chill enum. Shillelagh's proposed `affected_item_uuid` stays
  on its existing actor-owned condition and resolves only against disclosed
  item identity. `ConditionFact`/`ConditionStateChangedEvent` and committed
  `resulting_stats` are suitable existing after-value boundaries.
- `Entity.receive_damage` and `DamageAppliedEvent` own accepted damage. The
  normal-HP cap already exists below the Entity entry point. Exposing that cap
  for Harm avoids a second damage calculation. Max-HP changes must preserve
  normal HP except for the explicitly granted Feast gain or required clamp;
  this obligation also applies when suppression changes the effective modifier.
- The native death pipeline has a real cancellable `DeathEvent` before the
  life-state commit (`dnd/entity.py:2521`). The plan puts Disintegrate's aftermath
  policy in that transaction, saves dust and surviving items, and requires
  prevention tests. It does not infer dust later from HP or from an animation.
  Partial-object changes remain authoritative placement/band changes on the
  same object and must drive collision, optics and presentation together.
- Dimension Door's prepare-all, commit-all, then publish/arrival sequence is the
  appropriate extension of current spatial commit ownership. Its typed transfer
  group is the teleport result; it must not pretend that a Portal item exists.
  Banishment explicitly replaces the current prepared return's occupant-moving
  policy with jointly reserved destinations and a pending return obligation.
- Finger of Death retains death-to-birth identity and processes the victim's
  next boundary before `Encounter.start_turn` skips dead combatants. The plan
  now explicitly uses `installed_creature_materialization` at composition/
  encounter level. This matches the existing summoning deployment pattern
  without importing bootstrap materialization or concrete creature factories
  upward into `necromancy.py` or passive types. Permanent control does not reuse
  expiring `Summoned` existence.
- The existing strict presentation records in `game/animation_types.py`,
  `game/condition_types.py` and `game/world_binding_types.py` are suitable homes
  for closed, portable material/delivery/construction variants. The plan keeps
  authoring math/data separate from native facts, reuses shared sampling and
  drawing, and preserves the existing causal scheduler. There is no per-spell
  renderer, Python callback serialized as data, second timeline or live Entity
  lookup in replay.

## Implementation obligations retained by this approval

The packet gates remain substantive. In particular, demonstrate suppression
with two providers, expiry/removal while suppressed and no repeated one-time
effects; replay height-only movement and landing through real subjective
disclosure; and prove no participant observes a half-committed teleport or
partial dust/item outcome. Produce condition changes from their native owners,
filter newly disclosed item/endpoint/source identities at the existing
projection boundary, and retain exact application/result links through archive
round-trip and contact scheduling.

New presentation variants must be strict data with explicit discriminants and
numeric parameters, consumed by shared operators. Their media cannot decide
mechanics or depend on backend object identity. Native types remain dependency
leaves; native modules do not import `game`. Source-turn timers identify the
exact child and boundary, rather than expiring an entire concentration owner.
Feast uses the selected quick interaction and ten beneficiary intervals through
the existing duration semantics.

The plan explicitly discloses the forced-height/fall extension, narrow permanent
Zombie creation/control, limited loaded-map teleport and representable object
cuts. Those dependencies are part of the proposed approval scope; this receipt
does not independently expand the human's authorization. Complete public-boundary
native checks, serialized replay, selected-asset presentation checks and the
required independent packet reviews are still needed.

## Amendment review — finite Telekinesis and shared ledge landing

Decision: **APPROVE this amendment in the ECS/import-DAG/event scope; no new
architectural plan blocker.** Reviewed SHA256:
`e77a7ed1cc4e61c687bf8915242541488175aa6f60caa3815d006b5813d67241`.

This amendment supersedes this receipt's earlier discussion of permanent Zombie
creation and persistent numeric actor suspension. Finger is now damage-only.
Telekinesis completes movement onto support; concentration owns only repeat
permission. The newly requested ledge-fall support is shared by existing
movement producers. The proposed 3d6/DEX hostile impact and larger-of-die-count
combination remain recommendations requiring human approval; this technical
review does not approve their balance on the human's behalf.

The narrow code check confirms the plan's description of existing limitations:
`dnd/actions.py:343` commits forced travel through successive ground cells;
Shove admission uses `grid.can_transition`, whose elevation rules describe
supported 2D transitions. Existing support heights, boundary channels and Jump/
Fly traversal do not constitute a general airborne collision or falling solver.
The amendment truthfully adds the missing landing operation and rejects
unsupported clearance instead of claiming an animation arc proves passage.
Missing tiles, blocked rails/walls and occupied landings retain explicit bounded
policies; no sideways nearest-free relocation or global airborne state is added.

The ownership direction is sound: spatial queries return passive data;
`dnd/actions.py` composes existing movement, damage and condition operations;
leaf landing/path records live in `dnd/types/event_facts.py`; the spell selects
its declared landing profile. No spatial leaf imports actions, Entity or a spell,
and no native owner imports the client. Ordinary movement facts remain the one
authority for the accepted path/endpoints and landing result.

Three concrete implementation obligations follow from the amended contract:

- **Landing has its own causal contact.** `game/forced_movement.py` currently
  reconstructs elevations from reduced tiles and records arrival anchors only
  for spatial descendants. `game/choreography.py:619` consumes those anchors;
  merely adding direct damage below the cast or forced-movement event will not
  automatically bind it to landing. Retain the admitted path/support heights
  and landing kind, link the actual damage/Prone/life descendants to that
  movement's landing using the existing resolution/causal references, and bind
  them to its contact milestone. Do not match target/time, reuse the cast's
  release/contact blindly, or create a second timeline. Distinct landing hazards
  preserve their own causal application identities.
- **Attribution and effect kind stay distinct.** Preserve the original shover/
  spell caster and parent action through displacement, accepted damage and
  death. Ordinary environmental fall damage must not silently acquire magical
  spell semantics merely because a spell caused the movement. Telekinesis's
  selected spell-owned impact retains its actual spell origin. Existing
  `EffectOrigin`, damage and life owners support this distinction without a
  parallel fall-health system.
- **Observation follows native evidence.** Current `ForcedMovementFact` contains
  only XY endpoints/distance, and `_forced_allowed` checks endpoint grants.
  Newly retained path/elevation details therefore need event-time disclosure
  admission; seeing endpoints is not a blanket grant for intermediate cells.
  The sampler uses the admitted record, and ground hazards run only at actual
  supported contact. Interrupted voluntary approach cannot produce a canceled
  landing, while already accepted partial movement remains recorded.

These obligations implement packet 6's existing requirements rather than add
new product scope. The amendment's shared Shove/spell-push/downward-Jump,
interruption, hazard, safe Fly/teleport and saved-replay cases are appropriate
acceptance boundaries. This review ran no tests, produced no rendering and
changed only this receipt; the earlier approval remains preserved as history.
