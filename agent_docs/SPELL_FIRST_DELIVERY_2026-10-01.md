# First native spell delivery

The caller is the current in-process game: commands, available actions, authoritative
state and retained events. Wall artwork/rendering and creature/scenario authoring
remain separate. The first delivery is Grease test correction, touch targeting and
Wall of Fire; the broader wall inventory remains follow-up scope, subject to the
user's content regroup after this delivery.

## Repairs

- Grease production entry works. The failing fixture enters `(5,6)`, outside its
  ten-foot square. Assert that outside movement is harmless, then enter `(4,5)`;
  preserve appearance, movement cost, turn-end, concentration and cleanup checks.
- Add an explicit touch-contact perception policy to the existing action data.
  Darkvision and True Seeing opt in. Validate range, relationship, deployment,
  occupancy layer and authoritative hand passage for every target. Only unhidden,
  non-invisible neighbors may supply contact when sight is absent; existing special
  sense contacts remain valid. No sight, sensory contacts or hidden IDs are granted.
- Discovery copies its cached perceived pool before adding local contact candidates.
  Self/dead/faction admission stays intact. Keep unrelated single-target behavior.

## Wall of Fire

- Retain strict immutable wall geometry alongside existing presentation geometry:
  segment or ring, native grid coordinates, physical width and height. Fire chooses
  a hot side separately. Do not substitute a five-foot physical thickness.
- Use one existing AreaCondition owner, indexed spatial triggers, ordinary damage,
  spell provenance/protection, round duration and linked concentration cleanup.
- The registered footprint contains flame and hot-side heat cells, but only flame
  cells obstruct optics or expose flame artwork. Add a small trigger-footprint hook
  to AreaCondition so eligibility is checked before entry's once-per-turn fence.
- A one-foot shell occupies grid cells it intersects. Heat membership uses cell
  centers on the selected side within ten feet. Preserve exact geometry so this
  necessary five-foot-grid discretization does not redefine the physical thickness.
- Appearance: Dexterity save, 5d8 fire, half on success. Entry: first per turn into
  flames, same damage without a save. Turn end: flames or selected heat side, same
  damage without a save, including after an entry hit. Moving between flame cells
  is not a new entry. Ground and air contact are supported; underground contact is
  excluded until emergence. Add 1d8 per slot above four.
- Straight length at most sixty feet; ring diameter at most twenty; twenty feet
  high; solid support and 120-foot casting range. Flame is permeable and opaque.
  Position allocation follows multi-target allocation: one point draws from the
  first cell toward that point to the selected endpoint, excluding the caster/device origin. Two
  or more explicit points are an ordered independent path and may include the
  caster's cell. A coincident or adjacent one-point shorthand cannot create a
  positive-length segment; use explicit endpoints for that placement.
  Each spell declares its segment and total-length budget. Fire supports one
  segment or a ring; Wind's continuous shaped path and Stone's panel authoring are
  later spells, not inferred Fire capabilities. Discovery exposes four Fire
  form/side variants per slot and first anchors with
  at least one admitted endpoint; a follow-up endpoint query uses the same placement
  predicate. Commands carry `extra_target_positions`; a preview witness is never
  substituted for submitted input. Rings select one
  center with an authored radius. Both endpoints repeat range, visibility and
  physical admission at execution; validate the segment against solid geometry as
  well as its support. Reversed endpoints reverse left/right. Reject unsupported
  placement before resource costs. No Cartesian endpoint-pair list or new executor.
  Base elevation uses existing five-foot support steps, retained with wall height
  in events and observations. Reject split-elevation support and confine the initial
  heat footprint to the support plane; do not silently create multi-Z or airborne
  altitude rules. Pygame/AI multi-position selection remains pending controller
  integration;
  this delivery closes
  the backend command/discovery/event contract only.
- No structural damage, invented ignition rule, light radius, horizontal barrier,
  floating wall or multi-Z migration is introduced by this spell.

Rules: [2014 Wall of Fire](https://www.dndbeyond.com/sources/dnd/basic-rules-2014/spells#WallofFire).

## Acceptance

Test command/discovery agreement for self/neighbor touch in darkness/blindness,
distant/hidden/invisible/dead/undeployed targets, physical walls/windows and diagonal
corners. Verify both original sense-grant reactive regressions.

For Fire, test appearance saves, cold-side safety, heat-only entry, shell entry
and turn end in one turn, repeated/forced entry, inward/outward rings, upcasting,
optical/permeable channels, placement rejection without costs, catalog discovery,
round expiry, concentration removal and cold serialized event geometry. Run the
engine lane after focused checks; report unrelated active failures honestly.

Position acceptance includes first-cell caster/device shorthand, explicit caster-inclusive endpoints,
short diagonal and reversed segments, missing or
coincident endpoints, maximum span/range, hidden endpoints, crossing a solid
boundary and an endpoint invalidated after discovery. Retained geometry must match
the selected endpoints, and item-use dispatch must carry the same extra positions.

## Independent review

Anti-slop reviewer: `/root/scope_anti_slop_review`.
Anti-OOP/ECS reviewer: `/root/scope_anti_oop_review`.
Their pre-edit findings require opt-in targeting, preserved range/filter checks,
copied discovery pools, exact shell versus heat membership and entry-only fencing.
Those constraints are incorporated above. Both reviewers approved the final bounded
implementation. The anti-slop reviewer independently reran eight affected cases,
covering flame-region movement, underground emergence, first-cell shorthand,
explicit caster-inclusive endpoints and device dispatch; all passed.

## Implementation status

Grease's fixture is corrected; production Grease is unchanged. Shared contact
admission is installed for Darkvision and True Seeing through ordinary and item
discovery/execution. Wall of Fire is registered native spell content, with exact
placement retained in spell and spatial observations. Its path allocation reuses
ordinary engine execution and the authoritative dispatcher; no second executor
or rendering-derived rules were added.

The complete engine lane passes **1,841 tests** (183 seconds). The focused
spell/touch/device/sense lane passes **145 tests**. Scoped native
typing reports **zero errors**. Architecture, generated event-contract and
area-replay checks report **90 passed, 5 failed**. All five failed nodes were
already present in the earlier complete-project triage: three frozen CR0
artifact/inventory assertions, one direct-item inventory omitting window content,
and one retired-server spell-catalog import. Their disposition remains a separate
discussion; no historical manifest or server was rewritten to hide those failures.
The generated event manifest is current, and event-wire/area replay checks pass.
Raw focused, full-engine, contract and typing outputs are preserved in
`.runtime/spell-first-delivery/validation/`.

Pending after backend acceptance: wall VFX and Pygame/AI multi-position selection;
other wall spell mechanics remain follow-up inventory. General multi-Z, creature
imports and scenario redesign were not started. Regroup with the user on content
before beginning that second chunk.
