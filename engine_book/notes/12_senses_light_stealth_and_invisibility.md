# 12. Senses, Light, Stealth, And Invisibility

## Purpose

This chapter documents the observer-local perception layer: how an entity's
`Senses` cache is computed, how light filters geometric field of view, how
reactive spatial events update that cache, and how hidden or invisible blocks
are filtered from sight, targeting, and subjective path planning.

The examples are executable in both:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

The pytest file calls the same example functions, so the book examples and the
proper test suite stay in 1:1 parity.

## Source Files Studied

- `dnd/blocks/sensory.py`
- `dnd/entity.py`
- `dnd/core/base_block.py`
- `dnd/core/base_tiles.py`
- `dnd/core/gridmap.py`
- `dnd/core/shadowcast.py`
- `dnd/conditions.py`
- `dnd/actions.py`
- `dnd/actions_functional.py`
- `dnd/spells/divination.py`
- `dnd/spells/transmutation.py`
- `examples/test_reactive_senses.py`
- `examples/test_lighting_system.py`
- `examples/test_light_propagation.py`
- `examples/test_lighting_stealth_integration.py`
- `examples/test_stealth_system.py`
- `examples/test_invisibility_pathfinding_leak.py`
- `examples/test_invisibility_oa_reveal.py`
- `examples/test_invisible_targeting.py`
- `examples/test_perception_staleness.py`
- `examples/test_visibility_contract_payloads.py`
- `examples/test_info_leak_fixes.py`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Rules Relationship

Status: mixed.

- `SRD-aligned`: bright light, dim light, darkness, darkvision, Devil's Sight,
  truesight, invisibility, and hiding all correspond to local SRD concepts in
  `interactive_ruleset/Gameplay/Adventuring.md`,
  `interactive_ruleset/Gameplay/Combat.md`, and
  `interactive_ruleset/Gamemastering/Conditions.md`.
- `SRD-aligned`: invisible and hidden creatures are not directly targetable by
  observers who cannot perceive them.
- `Engine adaptation`: passive perception is the single deterministic threshold
  for whether a hidden entity is perceived. Equality favors the hider:
  `stealth_dc >= passive_perception` means not perceivable.
- `Engine adaptation`: adjacent natural darkness is treated as at least dim
  light for the observer.
- `Engine extension`: `SENSORY_UPDATE` events provide observer-specific deltas
  for clients.
- `Engine extension`: subjective pathfinding hides imperceivable blockers to
  avoid information leaks, while actual movement still checks objective
  blockers and can collide.

## The Senses Cache

`Senses` is an observer-local cache. It stores:

- visible entities by UUID and position;
- visible objects by UUID and position;
- lit visible cells;
- walkable cells in geometric FOV;
- normal paths and hazard-avoiding safe paths;
- previously seen cells;
- special sense modes;
- remembered collision blockers;
- stale-path and perception snapshots.

`Entity.update_entity_senses()` is the full recompute path. It calls
`Entity.compute_senses_from_position()`, commits the result into the `Senses`
block, snapshots passive perception and sense modes, and subscribes the observer
to the full geometric FOV.

The full compute order is:

1. Compute geometric FOV with `GridMap.compute_fov()`.
2. Filter FOV by each tile's effective light for the observer.
3. Compute subjective Dijkstra paths.
4. Filter paths to visible or previously seen cells.
5. Compute safe paths only if a normal visible path crosses a perceptible hazard.
6. Filter entities and objects through `BaseBlock.is_perceivable_by()`.

Example EB-12-001 shows the important split between geometric FOV and visible
cells. A dark target cell is subscribed to but not visible:

```python
observer.update_entity_senses(max_distance=5)

subscriptions = get_map().get_entity_subscriptions(observer.uuid)
assert (3, 0) in subscriptions
assert (3, 0) not in observer.senses.visible
assert target.uuid not in observer.senses.entities
```

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_001_geometric_fov_is_filtered_by_effective_light`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Light Levels And Sense Modes

Tile light has two layers:

- objective light: `max(default_light, illuminations)`, then
  `min(result, obscurements)`;
- subjective light: the objective level after the observer's sense modes are
  applied.

Sense modes are stored on `Senses.sense_modes`:

- darkvision shifts natural darkness to dim and dim to bright within range;
- Devil's Sight treats natural and magical darkness as bright within range;
- truesight and blindsight treat darkness as at least bright within range;
- magical darkness blocks ordinary vision and ordinary darkvision.

Example EB-12-002:

```python
observer.senses.sense_modes = [
    SenseMode(sense_type=SensesType.DARKVISION, range_feet=60)
]

assert near_dark.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.DIM_LIGHT
assert dim.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.BRIGHT_LIGHT
assert magical.get_effective_light_for(observer.uuid, (0, 0)) == LightLevel.MAGICAL_DARKNESS
```

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_002_sense_modes_subjectively_upgrade_light`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Light Sources

`GridMap.add_light_source()` stores a `LightSourceData` record, computes affected
tiles through the light FOV channel, applies illumination modifiers, and emits
batched spatial light events.

Light propagation is distinct from vision and movement. Directional light
blockers can stop illumination without blocking movement.

Example EB-12-003:

```python
grid.set_tile_directional_border((1, 0), "light", "east", False)
light_uuid = grid.add_light_source((0, 0), bright_radius_feet=5, dim_radius_feet=15)

assert grid.get_tile(1, 0).resolved_light_level == LightLevel.BRIGHT_LIGHT
assert grid.get_tile(2, 0).resolved_light_level == LightLevel.DARKNESS
assert (2, 0) not in grid._light_sources[light_uuid].affected_tiles
```

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_003_light_sources_use_light_fov_and_respect_light_blockers`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Reactive Sensory Updates

Each entity registers a `SpatialSensesCallback` pre-completion callback. It
listens for spatial events, death events, and condition changes on the observer.
When the observer's cache changes, it emits a child `SENSORY_UPDATE` event with
observer-specific deltas.

The callback does not run full Dijkstra. For most reactive changes it updates
visibility, entities, and objects incrementally, then marks `_paths_dirty` when
path data is stale. Full path recompute is reserved for explicit full senses
updates such as turn start or movement completion.

Example EB-12-004 proves that a dark subscribed cell becomes visible when light
appears there, without calling `update_all_entities_senses()`:

```python
observer.update_entity_senses(max_distance=5)
assert target.uuid not in observer.senses.entities

get_map().add_light_source((3, 0), bright_radius_feet=5, dim_radius_feet=0)

assert (3, 0) in observer.senses.visible
assert target.uuid in observer.senses.entities
```

Example EB-12-008 shows self-movement behavior:

```python
assert mover.senses._paths_dirty is False
Entity.update_entity_position(mover, (1, 0))
assert mover.senses._paths_dirty is True
assert target.uuid in mover.senses.entities
```

Example EB-12-011 documents a magical-darkness reactivity edge:

```python
zone = MagicalDarknessCellZone(
    source_entity_uuid=observer.uuid,
    target_entity_uuid=observer.uuid,
    zone_center=(2, 0),
)
observer.add_condition(zone)

assert target.uuid not in observer.senses.entities
assert (3, 0) not in observer.senses.visible

observer.remove_condition(zone.name)

assert get_map().get_tile(2, 0).resolved_light_level == LightLevel.BRIGHT_LIGHT
assert (2, 0) in observer.senses.visible
assert (3, 0) in observer.senses.visible
assert target.uuid in observer.senses.entities
assert removal_light_events[-1].senses_hint.requires_fov is True
```

Applying magical darkness through a zone uses the batched light path, which
sets `requires_fov=True` while the affected tile resolves to
`MAGICAL_DARKNESS`. Observers then recompute FOV, drop the magical-darkness cell,
and drop cells behind it. Removing the same zone captures the old magical
darkness state before the modifier is removed, so the batch event still carries
`requires_fov=True`. Observers recompute FOV and resubscribe to cells that were
behind the darkness.

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_004_light_change_reveals_subscribed_dark_cells_reactively`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_008_self_movement_updates_visibility_and_marks_paths_dirty`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_011_magical_darkness_zone_removal_recomputes_behind_cells`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Perceivability

Hidden and invisible are implemented as flags on `BaseBlock`:

- `stealth_dc`: the passive perception threshold required to perceive the block;
- `is_invisible`: whether the block is invisible to ordinary senses.

Both setters fire `SPATIAL_PERCEIVABILITY_CHANGED`. Observers subscribed to the
block's position recheck only that block.

`BaseBlock.is_perceivable_by(observer_uuid)` applies these rules:

1. No observer UUID means perceivable.
2. Invisible blocks are not perceivable unless the observer can bypass
   invisibility.
3. Hidden blocks are not perceivable when
   `stealth_dc >= observer.get_passive_perception()`.

Example EB-12-005:

```python
target.set_stealth_dc(observer.get_passive_perception() + 1)
assert not target.is_perceivable_by(observer.uuid)

target.set_invisible(True)
assert not target.is_perceivable_by(observer.uuid)
assert target.is_perceivable_by(truesight.uuid)
```

Example EB-12-006 proves that perceivability events refilter observer senses
reactively:

```python
assert target.uuid in observer.senses.entities
target.set_stealth_dc(observer.get_passive_perception() + 1)
assert target.uuid not in observer.senses.entities

target.set_stealth_dc(1)
assert target.uuid in observer.senses.entities
```

Example EB-12-012 covers the observer's own passive perception changing:

```python
base_passive = observer.get_passive_perception()
hidden.set_stealth_dc(base_passive + 3)
assert hidden.uuid not in observer.senses.entities

observer.add_condition(PerceptionModifierCondition(..., modifier_amount=5))

boosted_passive = observer.get_passive_perception()
assert boosted_passive == base_passive + 5
assert hidden.uuid in observer.senses.entities
assert observer.senses._paths_dirty is True

payload = updates[-1].model_dump(mode="json")
assert payload["passive_perception"] == boosted_passive
assert payload["paths_dirty"] is True
assert str(hidden.uuid) in payload["visible_entities_added"]
```

Example EB-12-019 covers the inverse case, where the observer's passive
perception decreases and a previously visible stealth-gated entity leaves the
observer cache:

```python
base_passive = observer.get_passive_perception()
hidden.set_stealth_dc(base_passive - 1)
assert hidden.uuid in observer.senses.entities

observer.add_condition(PerceptionModifierCondition(..., modifier_amount=-5))

reduced_passive = observer.get_passive_perception()
assert reduced_passive == base_passive - 5
assert hidden.uuid not in observer.senses.entities

payload = updates[-1].model_dump(mode="json")
assert payload["passive_perception"] == reduced_passive
assert payload["paths_dirty"] is True
assert str(hidden.uuid) in payload["visible_entities_removed"]
```

The sensory callback compares the observer's current passive perception against
the `Senses` snapshot when a condition changes on the observer. If only passive
perception changed, it refilters visible entities and marks the internal path
cache dirty. The emitted `SENSORY_UPDATE` carries the replacement
`passive_perception` value, visible-entity add or remove deltas, and
`paths_dirty=True` so clients know their cached paths need a refresh. Spotted
combat-log entries are generated for newly visible hidden entities, not for
entities removed after a passive-perception decrease.

Example EB-12-016 covers stacked hidden and invisible flags:

```python
target.add_condition(Invisible(...))
target.add_condition(Hidden(..., stealth_result=high_dc))
Entity.update_all_entities_senses(max_distance=5)

assert target.uuid not in observer.senses.entities
assert target.uuid not in truesight.senses.entities

get_map().add_light_source((3, 0), very_bright_radius_feet=5, ...)

assert "Hidden" not in target.active_conditions
assert "Invisible" in target.active_conditions
assert target.stealth_dc is None
assert target.is_invisible is True
assert target.uuid not in observer.senses.entities
assert target.uuid in truesight.senses.entities
```

`Hidden` and `Invisible` are independent perceivability gates. Very bright light
can remove the stealth gate, but ordinary observers still fail the invisibility
gate. An observer with truesight bypasses invisibility; after the stealth DC is
cleared, that observer refilters the target into `senses.entities`.

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_005_perceivability_flags_filter_hidden_and_invisible_blocks`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_006_perceivability_events_refilter_visible_entities`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_012_passive_perception_changes_emit_replacement_payloads`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_016_hidden_and_invisible_flags_stack_independently`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Subjective Paths And Information Leaks

Senses use subjective pathfinding. If an observer cannot perceive a blocking
entity or object, that blocker is treated as transparent for planning. This
prevents the UI from leaking that a creature is hidden or invisible.

Actual movement is still objective: when a mover attempts to pass through an
imperceivable blocker, movement can stop and record collision memory. That
collision memory then feeds subjective pathfinding so the mover can avoid the
same unknown obstruction without revealing what caused it.

Example EB-12-007:

```python
assert invisible.uuid not in observer.senses.entities
assert (2, 0) in observer.senses.paths
assert (4, 0) in observer.senses.paths

observer.senses.sense_modes = [
    SenseMode(sense_type=SensesType.TRUESIGHT, range_feet=60)
]
Entity.update_all_entities_senses(max_distance=5)

assert invisible.uuid in observer.senses.entities
assert (2, 0) not in observer.senses.paths
```

Example EB-12-013 covers directional collision memory:

```python
hidden_shutter = BaseItem(
    blocks_movement_east=True,
    stealth_dc=99,
    ...
)
grid.place_object(hidden_shutter.uuid, (0, 0))

assert grid.can_transition((0, 0), (1, 0), mover.uuid, subjective=True)
assert not grid.can_transition((0, 0), (1, 0), mover.uuid)

Move(source_entity_uuid=mover.uuid, end_position=(1, 0), use_movement_cost=False).apply()

assert mover.senses.collision_blocked == set()
assert ((0, 0), "east") in mover.senses.directional_collision_blocked

encounter.start_turn()

assert mover.senses.collision_blocked == set()
assert mover.senses.directional_collision_blocked == set()
assert mover.senses.paths[(1, 0)] == [(0, 0), (1, 0)]
```

Cell blockers and directional blockers use separate memory sets. A hidden
occupant or object that blocks a destination cell records
`Senses.collision_blocked`. A hidden edge-like blocker records
`Senses.directional_collision_blocked` as `(source_position, direction)`, so the
same destination can still be approached from another side. `Encounter.start_turn()`
clears both positional and directional collision memory before refreshing
senses, so stale discoveries from the previous turn do not keep shadowing the
new path map.

Example EB-12-015 covers cell-collision reveal:

```python
hidden_blocker.add_condition(Hidden(
    source_entity_uuid=hidden_blocker.uuid,
    target_entity_uuid=hidden_blocker.uuid,
    stealth_result=mover.get_passive_perception() + 10,
))
Entity.update_all_entities_senses(max_distance=5)

assert hidden_blocker.uuid not in mover.senses.entities
assert (1, 0) in mover.senses.paths
assert get_map().can_transition((0, 0), (1, 0), mover.uuid, subjective=True)
assert not get_map().can_transition((0, 0), (1, 0), mover.uuid)

result = Move(source_entity_uuid=mover.uuid, end_position=(1, 0), use_movement_cost=False).apply()

assert result is not None and result.canceled
assert mover.senses.collision_blocked == {(1, 0)}
assert "Hidden" not in hidden_blocker.active_conditions
assert hidden_blocker.uuid in mover.senses.entities
```

The move fails because objective movement cannot enter an occupied cell, but it
still fires a `MOVEMENT_COLLISION` event at the attempted destination. `Hidden`
listens for that event and removes itself when the collision position is the
hidden entity's own cell. Cleanup clears `stealth_dc` and emits a perceivability
update, so subscribed observers can refilter the revealed entity back into
`senses.entities`.

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_007_subjective_paths_do_not_leak_imperceivable_blockers`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_013_turn_start_clears_positional_and_directional_collision_memory`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_015_hidden_cell_blocker_reveals_on_movement_collision`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Plain Versus Spell Invisibility

The base `Invisible` condition and the spell-style `InvisibilityEffect` both set
`is_invisible`, add unseen attacker/target modifiers, and remove the entity from
ordinary observers' senses. They differ in reveal behavior:

- `Invisible` is a plain condition and installs no reveal handler;
- `InvisibilityEffect` is also named `"Invisible"` but installs an
  `"Invisibility: Reveal"` handler that removes the condition on attack, spell
  casting, or revealing base actions.

Example EB-12-014:

```python
plain_target.add_condition(Invisible(...))
spell_target.add_condition(InvisibilityEffect(...))

assert plain_target.uuid not in observer.senses.entities
assert spell_target.uuid not in observer.senses.entities

ActionEvent(name="Shove", source_entity_uuid=plain_target.uuid).phase_to(EventPhase.EFFECT)
ActionEvent(name="Shove", source_entity_uuid=spell_target.uuid).phase_to(EventPhase.EFFECT)

assert "Invisible" in plain_target.active_conditions
assert plain_target.uuid not in observer.senses.entities

assert "Invisible" not in spell_target.active_conditions
assert spell_target.uuid in observer.senses.entities
```

From the observer's perspective, a revealing action by a plain invisible entity
does not change sensory visibility. A revealing action by an
`InvisibilityEffect` target removes the condition, clears `is_invisible`, emits a
perceivability update, and lets subscribed observers refilter the entity back
into `senses.entities`.

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_014_plain_invisible_and_spell_invisibility_have_different_reveal_contracts`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Sense-Mode Conditions

Several spells add or remove sense modes. The observer's own condition
application/removal triggers the sensory callback, which compares the current
sense-mode hash to the previous snapshot. If it changed, the emitted
`SENSORY_UPDATE` carries the complete replacement list.

Example EB-12-009 uses `SeeInvisibilityEffect` directly:

```python
observer.add_condition(SeeInvisibilityEffect(
    source_entity_uuid=observer.uuid,
    target_entity_uuid=observer.uuid,
))

assert invisible.uuid in observer.senses.entities
assert changed[-1].model_dump(mode="json")["sense_modes"] == [
    {"sense_type": "See Invisible", "range_feet": 0}
]
```

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_009_sense_mode_changes_emit_replacement_payloads`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Targeting Revalidation

Action discovery and direct action execution are separate moments. A target can
be visible when an action is selected and become hidden before the executable
action runs. Multi-entity spells must therefore validate every current target at
execution time rather than trusting stale client-side selections.

Example EB-12-017:

```python
Entity.update_all_entities_senses(max_distance=10)
assert visible_target.uuid in caster.senses.entities
assert stale_target.uuid in caster.senses.entities

spell = MagicMissile(
    source_entity_uuid=caster.uuid,
    target_entity_uuid=visible_target.uuid,
    extra_target_entity_uuids=[stale_target.uuid],
)

stale_target.add_condition(Hidden(..., stealth_result=caster.get_passive_perception() + 10))
assert stale_target.uuid not in caster.senses.entities

result = spell.apply()

assert result is not None and result.canceled
assert result.status_message == "Stale Target not in line of sight"
assert visible_target.get_hp() == visible_hp_before
assert caster.action_economy.spell_slot_1.normalized_score == 4
```

`MagicMissile._validate()` re-derives the unique dart targets from the current
payload and checks each one against `caster.senses.entities`. If any target has
become hidden or invisible, validation cancels before the convolution loop runs,
so no dart damage or action/slot costs are applied.

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_017_multi_entity_spell_cancels_when_target_becomes_hidden`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## AoE Preview Versus Execution

Position-AoE actions expose two different visibility contracts:

- preview uses `AoEShape.compute_subjective()` through the caster's
  `Senses` cache and therefore hides imperceivable entities from names and UUIDs;
- execution uses `AoEShape.compute_objective()` through `get_all_targets()` and
  therefore applies the effect to creatures actually in the blast.

Example EB-12-018:

```python
hidden_target.add_condition(Hidden(..., stealth_result=caster.get_passive_perception() + 10))
Entity.update_all_entities_senses(max_distance=10)

available = caster.get_available_actions(target_filter="enemies")
fireball_info = next(
    action for action in available.position_actions
    if action.template_name == "Fireball__slot_3"
)
blast_preview = next(
    target for target in fireball_info.valid_targets
    if target.position == hidden_target.position
)

assert hidden_target.uuid not in (blast_preview.affected_entity_uuids or [])
assert "Hidden Target" not in (blast_preview.affected_entity_names or [])
assert visible_target.uuid in (blast_preview.affected_entity_uuids or [])

result = Fireball(
    source_entity_uuid=caster.uuid,
    end_position=hidden_target.position,
    cast_at_level=3,
).apply()

assert result is not None and not result.canceled
assert hidden_target.get_hp() < hidden_hp_before
assert "Hidden" not in hidden_target.active_conditions
```

This prevents the UI from leaking hidden combatants during area previews while
preserving the rules-facing effect that an area spell can hit a creature even if
the caster did not know it was there. If damage is dealt, Hidden's damage reveal
handler removes the stealth condition after the hit.

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_018_aoe_preview_hides_hidden_entities_but_execution_hits_them`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Hidden Reveal In Very Bright Light

`Hidden` applies `stealth_dc` and a reveal handler. The handler removes the
condition on attacks, damage, incapacitation, spell casting, revealing base
actions, collision, and very bright light.

Example EB-12-010:

```python
hidden.add_condition(Hidden(..., stealth_result=30))
assert "Hidden" in hidden.active_conditions

get_map().add_light_source(
    (3, 0),
    bright_radius_feet=0,
    dim_radius_feet=0,
    very_bright_radius_feet=5,
)

assert "Hidden" not in hidden.active_conditions
assert hidden.stealth_dc is None
assert hidden.uuid in observer.senses.entities
```

Parity tests:

- `tests/engine_book/test_chapter_12_senses_light_stealth.py::test_eb_12_010_very_bright_light_reveals_hidden_entities`
- `tests/engine_book/test_chapter_12_senses_light_stealth.py`

## Findings And Follow-Up

These are not treated as chapter failures, but they should guide later edge
coverage:

- Removing magical darkness emits stronger `requires_fov` signaling than
  ordinary light changes.
- Passive perception increases and decreases set `paths_dirty=True` on the
  emitted `SENSORY_UPDATE` when they invalidate the observer's cached paths.
- `GridMap.get_visible_entities()` is geometric and does not mean the same thing
  as `Entity.senses.entities`, which is light/perceivability filtered.
- `NON_REVEALING_ACTIONS` is string-name based, so renamed actions can change
  hidden-reveal behavior.
- Additional combat-log anonymization behavior for AoE events should receive
  focused tests in the encounter/log chapters.

## Documentation Hygiene Notes

- Chapter 12 hygiene reviewed `dnd/blocks/sensory.py` fully and the supporting senses/perceivability slices in `dnd/entity.py`, `dnd/core/base_block.py`, `dnd/conditions.py`, `dnd/spells/divination.py`, and `dnd/spells/transmutation.py` from executable behavior and parity tests.
- The cleaned scope covers the observer cache fields, sense-mode snapshots, spatial sensory callback deltas, light/perceivability filtering, subjective path blockers, base stealth/invisibility flags, reveal processors, and See Invisibility/True Seeing/Darkvision sense-mode effects.
- `Senses` now has a module docstring, complete Pydantic field descriptions, Google-style docstrings for cache helpers and callback internals, and no inline narrative comments.
- Known behavior was preserved where intentional: plain `Invisible` still has no reveal handler, and `InvisibilityEffect` still reveals on spell-style revealing actions.
- Broader spell-family field cleanup in divination/transmutation remains for the spell chapters; this pass only cleaned the Chapter 12 sense-mode spell surface.
