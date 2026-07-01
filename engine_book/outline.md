# Engine Book Outline

This outline is the working table of contents for the engine book.

The book must be written from implementation evidence, not from existing prose docs or comments. Each chapter starts with code study and test inspection, then records how the implementation relates to the local SRD/rules markdown in `interactive_ruleset/`.

## Chapter Contract

Every chapter must include:

- Evidence sources: source files read, tests read or added, and SRD/rules files consulted.
- Implementation model: what the code actually does, verified from behavior and source.
- Rule relationship: `SRD-aligned`, `Engine adaptation`, `Not implemented`, or `Engine extension`.
- Book examples: short, runnable examples where possible.
- Test parity: links to existing or new tests that assert the book examples.
- Deeper coverage plan: what existing examples cover and what new low-level tests must add.
- Documentation hygiene notes: comments removed or converted, Google-style docstrings reviewed, Pydantic `Field(..., description=...)` metadata reviewed.

## Part I: Primitive Runtime

### 01. Object Identity And Registries

Primary code to study:

- `dnd/core/base_object.py`
- `dnd/core/values.py`
- `dnd/core/base_block.py`
- `dnd/entity.py`

Rules relationship:

- Mostly `Engine extension`; registries are engine infrastructure, not SRD rules.

Baseline examples/tests:

- Existing coverage is indirect across almost all examples.
- Deeper tests now cover registry creation, lookup, unregistering,
  `use_register`, subclass lookup behavior, and registry separation.

Book examples created:

- EB-01-001 through EB-01-005 in `tests/engine_book/test_chapter_01_registries.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_01_registries.py`.
- Chapter text in `engine_book/chapters/01_object_identity_and_registries.md`.

### 02. Modifiers And Value Channels

Primary code to study:

- `dnd/core/modifiers.py`
- `dnd/core/values.py`

Rules relationship:

- `interactive_ruleset/Gameplay/Abilities.md`
- `interactive_ruleset/Gameplay/Combat.md`
- `interactive_ruleset/Gamemastering/Conditions.md`

Baseline examples/tests:

- `examples/test_dice_processors.py`
- `examples/test_great_weapon_fighting.py`
- `examples/test_dodging_attack.py`
- Many condition/spell tests exercise value channels indirectly.

Deeper tests covered:

- Numerical modifiers, min/max constraints, advantage aggregation, critical and auto-hit precedence.
- All six `ModifiableValue` channels.
- `set_from_target()` and `reset_from_target()` behavior.
- Contextual modifier evaluation, including target/context propagation.

Book examples created:

- EB-02-001 through EB-02-011 in `tests/engine_book/test_chapter_02_modifiable_values.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_02_modifiable_values.py`.
- Chapter text in `engine_book/chapters/02_modifiers_and_value_channels.md`.

### 03. Dice, Rolls, And Result Processors

Primary code to study:

- `dnd/core/dice.py`
- `dnd/classes/dice_processor_utils.py`
- Dice result events in `dnd/core/events.py`

Rules relationship:

- `interactive_ruleset/Gameplay/Abilities.md`
- `interactive_ruleset/Gameplay/Combat.md`

Baseline examples/tests:

- `examples/test_dice_processors.py`
- `examples/test_great_weapon_fighting.py`
- `examples/test_brutal_critical.py`
- `examples/test_lucky_feat.py`

Deeper tests covered:

- Deterministic dice construction and roll metadata.
- Processor composition and preservation of roll identity.
- D20 result event interception versus damage result event interception.
- Save/check natural-face behavior, critical immunity, heal-result completion,
  attack d20 weapon-slot context, Great Weapon Fighting packet/two-hand gates,
  HealEvent mutation/cancellation, and chained d20 replacement audit order.

Book examples created:

- EB-03-001 through EB-03-019 in `tests/engine_book/test_chapter_03_dice_events.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_03_dice_events.py`.
- Chapter text in `engine_book/chapters/03_dice_rolls_and_result_processors.md`.

### 04. Event Lifecycle

Primary code to study:

- `dnd/core/events.py`
- `dnd/core/combat_log.py`

Rules relationship:

- Mostly `Engine extension`; event lifecycles model how SRD mechanics are implemented.

Baseline examples/tests:

- `examples/test_event_hierarchy.py`
- `examples/test_saving_throw_events.py`
- `examples/test_combat_log_hierarchy.py`
- `examples/test_turn_end_handler.py`
- `examples/test_spatial_handler_registry.py`

Deeper tests covered:

- `phase_to()` lineage behavior.
- Handler dispatch at non-completion phases.
- Non-dispatch at `COMPLETION`.
- Parent/child lineages and combat-log collection.
- Passive callbacks versus pre-completion callbacks.
- Append-stable raw event cursors versus timestamp-sorted chronological reads.

Book examples created:

- EB-04-001 through EB-04-013 in `tests/engine_book/test_chapter_04_event_lifecycle.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_04_event_lifecycle.py`.
- Chapter text in `engine_book/chapters/04_event_lifecycle.md`.

## Part II: Composition And State

### 05. Blocks, Values, Context, And Target Propagation

Primary code to study:

- `dnd/core/base_block.py`
- `dnd/core/base_conditions.py`
- `dnd/core/values.py`
- `dnd/core/events.py`
- `dnd/blocks/*.py`

Rules relationship:

- Mostly `Engine extension`.

Baseline examples/tests:

- `examples/test_condition_removal_system.py`
- `examples/test_child_parent_notification.py`
- `examples/test_handler_toggle.py`
- Many examples exercise blocks through entities.

Deeper tests covered:

- Create a block with direct values and a child block.
- Propagate target and context through the block tree.
- Retrieve direct and deep contained values.
- Gate condition and event-handler ownership with `allow_events_conditions`.
- Remove condition-owned modifiers and linked conditions.
- Advance duration at the block layer without saving throws.
- Constructor source propagation ordering, canceled no-effect condition indexing,
  linked-condition cleanup, and immunity helpers.

Book examples created:

- EB-05-001 through EB-05-014 in `tests/engine_book/test_chapter_05_blocks_context.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_05_blocks_context.py`.
- Chapter text in `engine_book/chapters/05_blocks_values_context_and_cleanup.md`.

### 06. Entity Composition

Primary code to study:

- `dnd/entity.py`
- `dnd/blocks/abilities.py`
- `dnd/blocks/skills.py`
- `dnd/blocks/saving_throws.py`
- `dnd/blocks/health.py`
- `dnd/blocks/action_economy.py`
- `dnd/blocks/spellcasting.py`

Rules relationship:

- `interactive_ruleset/Gameplay/Abilities.md`
- `interactive_ruleset/Gameplay/Combat.md`
- `interactive_ruleset/Classes/*.md`

Baseline examples/tests:

- `examples/test_spell_system.py`
- `examples/test_faction_system.py`
- `examples/test_entity_blocking.py`
- `examples/test_available_actions.py`
- Class factory tests.

Deeper tests needed:

- Entity config construction.
- Ability, skill, save, health, action economy, and spellcasting composition.
- Passive skill and cross-entity skill/save propagation.
- Standard action registration and grouped availability.
- Entity rest and revival primitives now cover resource recharge, spell-slot
  restoration, long-rest condition expiry, Exhaustion reduction, normal HP
  recovery, temporary HP expiry, and Hit Dice spend/recovery. Add later
  food/drink qualification, 24-hour rest cadence, and concrete resurrection
  spells if those systems are implemented.

Book examples created:

- EB-06-001 through EB-06-017 in `tests/engine_book/test_chapter_06_entity_composition.py`.
- Chapter text in `engine_book/chapters/06_entity_composition.md`.

## Part III: Conditions And Actions

### 07. Condition Application And Cleanup

Primary code to study:

- `dnd/core/base_conditions.py`
- `dnd/core/base_block.py`
- `dnd/entity.py`
- `dnd/conditions.py`

Rules relationship:

- `interactive_ruleset/Gamemastering/Conditions.md`
- `interactive_ruleset/Gameplay/Combat.md`

Baseline examples/tests:

- `examples/test_condition_removal_system.py`
- `examples/test_child_parent_notification.py`
- `examples/test_concentration.py`
- `examples/test_tile_condition_duration.py`
- `tests/engine_book/test_chapter_07_condition_lifecycle.py`

Deeper tests needed:

- Entity-specific versus block-level `add_condition()` behavior is covered in
  book parity tests.
- Immunity, application saves, same-name replacement, duration expiry, modifier
  cleanup, event handler cleanup, spatial handler cleanup, subconditions, and
  linked conditions are covered in book parity tests.
- Child-removal policy `"any"`, multi-child `"last"`, `"none"` stale links,
  generic canceled no-effect block applications, canceled returned effect
  events, and removal saves before duration decrement are covered in book
  parity tests.

Book examples created:

- EB-07-001 through EB-07-013 in `tests/engine_book/test_chapter_07_condition_lifecycle.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_07_condition_lifecycle.py`.
- Chapter text in `engine_book/chapters/07_condition_application_and_cleanup.md`.

### 08. Standard D&D Conditions

Primary code to study:

- `dnd/conditions.py`

Rules relationship:

- `interactive_ruleset/Gamemastering/Conditions.md`

Baseline examples/tests:

- `examples/combat_conditions.py`
- `examples/test_stealth_system.py`
- `examples/test_invisibility_oa_reveal.py`
- `examples/test_dodging_attack.py`
- `examples/test_prone_auto_stand.py`
- `tests/engine_book/test_chapter_08_standard_conditions.py`

Deeper tests needed:

- One condition at a time, with direct assertions for each implemented standard condition's primary modifier channels.
- Add later coverage for Prone immediate stand-up, standard auto-stand handler registration, exhaustive removal cleanup, and spell-specific invisibility reveal handlers.
- `Petrified` and levelled `Exhaustion` are implemented with
  engine-expressible effects. Exhaustion long-rest and revival reduction are
  covered by Chapter 06's entity lifecycle example.

Book examples created:

- EB-08-001 through EB-08-015 in `tests/engine_book/test_chapter_08_standard_conditions.py`.
- Chapter text in `engine_book/chapters/08_standard_dnd_conditions.md`.

### 09. Action Templates, Costs, And Discovery

Primary code to study:

- `dnd/core/base_actions.py`
- `dnd/actions_functional.py`
- action discovery methods in `dnd/entity.py`

Rules relationship:

- `interactive_ruleset/Gameplay/Combat.md`
- `interactive_ruleset/Gameplay/Adventuring.md`

Baseline examples/tests:

- `examples/test_available_actions.py`
- `examples/test_available_actions_perf.py`
- `examples/test_action_overrides.py`
- `examples/test_action_overrides_exec.py`
- `examples/test_inventory_use_actions.py`
- `examples/test_usable_items.py`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`
- `tests/engine_book/test_chapter_09_action_templates_discovery.py`

Deeper tests needed:

- Template registration and instantiation are covered in book parity tests.
- Cost display/application and action override cost routing are covered in book parity tests.
- Self, entity, path, LOS, object, inventory item-use, and environment item-use discovery are covered in book parity tests.
- Add later direct MULTI_ENTITY/POSITION_AOE spell examples, hazardous/safe movement paths, attack-object breakage, and resource-cost feature examples in their domain chapters.

Book examples created:

- EB-09-001 through EB-09-012 in `tests/engine_book/test_chapter_09_action_templates_discovery.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_09_action_templates_discovery.py`.
- Chapter text in `engine_book/chapters/09_action_templates_costs_and_discovery.md`.

### 10. Core Actions And Combat Flow

Primary code to study:

- `dnd/actions.py`
- `dnd/reactions.py`
- `dnd/entity.py`
- `dnd/core/base_actions.py`
- `dnd/core/events.py`
- `dnd/blocks/action_economy.py`
- `dnd/blocks/health.py`
- `dnd/blocks/sensory.py`
- `dnd/conditions.py`

Rules relationship:

- `interactive_ruleset/Gameplay/Combat.md`

Baseline examples/tests:

- `examples/test_jump.py`
- `examples/test_shove.py`
- `examples/test_two_weapon_fighting.py`
- `examples/test_protection.py`
- `examples/test_shield_spell.py`
- `examples/test_handler_toggle.py`

Deeper tests needed:

- Attack validation, hit, crit, damage roll, damage application, and miss context cleanup are covered in book parity tests.
- Movement step events, opportunity attacks, Disengage prevention, forced movement, Dash, healing, and death are covered in book parity tests.
- Natural 1/20 matrices, ranged long-range validation, mixed damage resistance, lethal OA stop position, Jump/OA parity, forced movement through terrain, diagonal threat cases, videogame Shove, default monster-style death, and opt-in player-style death saves are covered in Chapter 10 parity tests.

Book examples created:

- EB-10-001 through EB-10-026 in `tests/engine_book/test_chapter_10_core_actions_combat.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_10_core_actions_combat.py`.
- Chapter text in `engine_book/chapters/10_core_actions_and_combat_flow.md`.

## Part IV: Space, Perception, And Objects

### 11. Grid, Tiles, Terrain, And Pathfinding

Primary code to study:

- `dnd/core/gridmap.py`
- `dnd/core/base_tiles.py`
- `dnd/tiles.py`
- `dnd/tile_conditions.py`
- `dnd/core/dijkstra.py`
- `dnd/core/geometry.py`
- `dnd/core/aoe.py`
- `dnd/core/shadowcast.py`
- `dnd/blocks/base_item.py`
- `dnd/blocks/sensory.py`

Rules relationship:

- `interactive_ruleset/Gameplay/Adventuring.md`
- `interactive_ruleset/Gameplay/Combat.md`
- `interactive_ruleset/Gamemastering/Traps.md`

Baseline examples/tests:

- `examples/test_geometry.py`
- `examples/test_difficult_terrain.py`
- `examples/test_terrain_movement_system.py`
- `examples/test_hazard_pathfinding.py`
- `examples/test_tile_directional_blocking.py`
- `examples/test_directional_environment_items.py`

Deeper tests needed:

- Tile identity, movement modes, terrain cost pathfinding, exact diagonal range pruning, negative-coordinate pathfinding, move-cost conversion, occupancy/object blocking, directional borders, directional channel separation, visible and hidden hazard pathing, dead-entity path recomputation, primitive object removal item-state cleanup, Jump/forced movement through directional blockers, geometry, AoE propagation, object re-placement, ZoneControl cone/line construction caveats, cylinder preview parity, and spatial handler zone cleanup are covered in book parity tests.
- Add later Chapter 11 edges only after fresh code study identifies behavior that is not represented by the existing EB-11 examples.

Book examples created:

- EB-11-001 through EB-11-021 in `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_11_grid_tiles_pathfinding.py`.
- Chapter text in `engine_book/chapters/11_grid_tiles_terrain_and_pathfinding.md`.

### 12. Senses, Light, Stealth, And Invisibility

Primary code to study:

- `dnd/blocks/sensory.py`
- senses methods in `dnd/entity.py`
- perceivability methods in `dnd/core/base_block.py`
- light levels in `dnd/core/base_tiles.py`
- light-source support in `dnd/core/gridmap.py`
- `dnd/core/shadowcast.py`
- `dnd/conditions.py`
- `dnd/actions.py`
- sense-mode conditions in `dnd/spells/divination.py` and `dnd/spells/transmutation.py`

Rules relationship:

- `interactive_ruleset/Gameplay/Adventuring.md`
- `interactive_ruleset/Gameplay/Combat.md`
- `interactive_ruleset/Gamemastering/Conditions.md`

Baseline examples/tests:

- `examples/test_reactive_senses.py`
- `examples/test_lighting_system.py`
- `examples/test_light_propagation.py`
- `examples/test_lighting_stealth_integration.py`
- `examples/test_stealth_system.py`
- `examples/test_invisibility_pathfinding_leak.py`
- `examples/test_perception_staleness.py`
- `examples/test_visibility_contract_payloads.py`

Deeper tests needed:

- Geometric FOV versus light-filtered visibility is covered in book parity tests.
- Sense modes, light source propagation, reactive light updates, magical darkness add/remove reactivity, hidden/invisible filtering, perceivability events, subjective path leak prevention, self-movement dirty paths, sense-mode payloads, passive-perception increase/decrease path-refresh payloads, directional collision-memory turn-start cleanup, and very-bright hidden reveal are covered in book parity tests.
- Plain `Invisible` versus `InvisibilityEffect`, hidden/invisible stacking, AoE
  preview/execution information hiding, MULTI_ENTITY stale target cancellation,
  and movement collision revealing hidden blockers are covered in book parity
  tests.
- Add later deeper combat-log anonymization edges in encounter/log chapters.

Book examples created:

- EB-12-001 through EB-12-019 in `tests/engine_book/test_chapter_12_senses_light_stealth.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_12_senses_light_stealth.py`.
- Chapter text in `engine_book/chapters/12_senses_light_stealth_and_invisibility.md`.

### 13. Equipment, Inventory, And Items

Primary code to study:

- `dnd/blocks/base_item.py`
- `dnd/blocks/inventory.py`
- `dnd/blocks/equipment.py`
- `dnd/items/*.py`
- item discovery and equip helpers in `dnd/entity.py`
- item-use execution in `dnd/actions_functional.py`
- object placement in `dnd/core/gridmap.py`

Rules relationship:

- `interactive_ruleset/Equipment/*.md`
- `interactive_ruleset/Treasure/*.md`
- `interactive_ruleset/Gamemastering/Objects.md`

Baseline examples/tests:

- `examples/test_items_phase1.py`
- `examples/test_items_phase1_advanced.py`
- `examples/test_items_lifecycle_hooks.py`
- `examples/test_items_equip_hooks.py`
- `examples/test_inventory_use_actions.py`
- `examples/test_stackable_items.py`
- `examples/test_usable_items.py`
- `examples/test_equipment_api.py`
- `examples/test_equipment_visual_metadata.py`
- `examples/test_door_interaction.py`
- `examples/test_torch_items.py`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`
- `tests/engine_book/test_chapter_13_items_inventory_equipment.py`

Deeper tests needed:

- Ownership/location transitions, stack merging, transfer rollback, equip and
  unequip state, slot validation, equip hooks, usable action identity, charge
  consumption, environment actions, breakable containers, torch light
  lifecycle, atomic partial stack failure, and transfer into an existing stack
  are covered in book parity tests.
- Equipped item destruction cleanup and equipment damage bonus accounting are
  covered in book parity tests.
- Generic charge overspend is covered in book parity tests.
- Direct raw container rehoming is covered in book parity tests.
- Ready-versus-stowed loadout semantics are covered as a parallel-loadout
  engine adaptation.

Book examples created:

- EB-13-001 through EB-13-022 in `tests/engine_book/test_chapter_13_items_inventory_equipment.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_13_items_inventory_equipment.py`.
- Chapter text in `engine_book/chapters/13_equipment_inventory_and_items.md`.

## Part V: Spells, Features, And Game Loops

### 14. Spellcasting Core

Primary code to study:

- `dnd/actions.py`
- `dnd/core/base_actions.py`
- `dnd/blocks/spellcasting.py`
- `dnd/blocks/action_economy.py`
- spellcasting helper methods in `dnd/entity.py`
- spell registration in `dnd/actions_functional.py`
- concentration support in `dnd/conditions.py`
- `dnd/spells/__init__.py`
- `dnd/spells/base.py`
- `server/spell_catalog.py`

Rules relationship:

- `interactive_ruleset/Spells/# Spellcasting.md`
- `interactive_ruleset/Spells/## Spell Lists.md`

Baseline examples/tests:

- `examples/test_spell_system.py`
- `examples/test_spell_catalog_api.py`
- `examples/test_spell_crit_dice.py`
- `examples/test_self_range_aoe_availability.py`
- `examples/test_concentration.py`
- `examples/test_concentration_spells.py`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`
- `tests/engine_book/test_chapter_14_spellcasting_core.py`

Deeper tests needed:

- Spell slots, `SpellcastingBlock`, entity spell numbers, spell event metadata,
  cantrip scaling, explicit variants, executable slot-variant discovery,
  multi-target convolution, spell damage metadata, concentration cleanup,
  targeted multi-slot `DropConcentration`, deterministic concentration breaks,
  multi-target concentration slot reuse, registration/setup order, and catalog
  identity are covered in book parity tests. Spell action overrides now cover
  `alt_skip_slot`, `alt_cost_type`, and `alt_range`.
- Add later additional class-specific action costs.

Book examples created:

- EB-14-001 through EB-14-019 in `tests/engine_book/test_chapter_14_spellcasting_core.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_14_spellcasting_core.py`.
- Chapter text in `engine_book/chapters/14_spellcasting_core.md`.

### 15. Spell Families And Implemented Spells

Primary code to study:

- `dnd/spells/abjuration.py`
- `dnd/spells/conjuration.py`
- `dnd/spells/divination.py`
- `dnd/spells/enchantment.py`
- `dnd/spells/evocation.py`
- `dnd/spells/illusion.py`
- `dnd/spells/necromancy.py`
- `dnd/spells/transmutation.py`

Rules relationship:

- `interactive_ruleset/Spells/*.md`

Baseline examples/tests:

- All spell-specific and spell-batch files under `examples/test_*.py`.
- `tests/engine_book/test_chapter_15_spell_families.py`
- `tests/engine_book/test_chapter_15_spell_families.py`

Deeper tests needed:

- Pattern-level tests now cover catalog identity, attack/save/AoE evocation,
  auto-hit damage, healing, abjuration buff/restoration, multi-target
  concentration, spatial zones, teleport/sense utility, invisibility, temporary
  HP, Shield reaction/toggle/combat-log behavior, Haste/Slow modifier bundles,
  Hold Person/Hold Monster repeat saves, Sleep/Color Spray HP-pool behavior,
  Guidance/Bless/Bane roll mutation, Mirror Image, restoration
  supported-effect preservation and SRD-tagged effect cleanup, protective
  abjuration prevention/absorption, light-zone obscurement/Daylight dispel
  behavior, and Insect Plague/Incendiary Cloud damage-zone terrain/obscurement/upcast behavior,
  plus Stinking Cloud/Sleet Storm turn-start SRD edges, Stinking Cloud
  breathless-creature filtering and wind dispersal, Sleet Storm exposed-flame
  dousing, and Web
  obscurement/grounded escape/unanchored-collapse cleanup, HP-pool
  upcast/immunity/cannot-see edges, and Eyebite granted-action lifecycle with
  Sickened repeat-save/action-cost, successful-save retarget, visible-target
  edges, and shared Sleep/Eyebite shake-awake cleanup, plus Panicked Dash
  movement and distance/sight cleanup. Web fire exposure is covered through the
  shared environmental exposure primitive.
- Add later per-spell rule relationship records and additional Haste/Slow or
  repeat-save matrices only after fresh spell-family code study identifies
  uncovered behavior.

Book examples created:

- EB-15-001 through EB-15-044 in `tests/engine_book/test_chapter_15_spell_families.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_15_spell_families.py`.
- Chapter text in `engine_book/chapters/15_spell_families_and_implemented_spells.md`.

### 16. Class Features, Factories, And Feats

Primary code to study:

- `dnd/classes/*.py`
- `dnd/classes/*_factory.py`
- `dnd/classes/feats.py`
- `dnd/classes/paladin.py`

Rules relationship:

- `interactive_ruleset/Classes/*.md`
- `interactive_ruleset/Characterizations/Feats.md`
- `interactive_ruleset/feats_srd5_2.md`

Baseline examples/tests:

- Fighter, barbarian, sorcerer, paladin, Lucky, and feature-specific examples.
- `tests/engine_book/test_chapter_16_class_features.py`
- `tests/engine_book/test_chapter_16_class_features.py`

Deeper tests needed:

- Representative parity tests now cover factory feature wiring, Fighter
  resource/action lifecycle, Barbarian Rage/Frenzy cleanup, Barbarian tactical
  feature surfaces, Relentless/Persistent Rage event behavior, Indomitable
  Might skill-check mutation, Retaliation reaction attacks, Primal Champion
  derived combat surfaces, Sorcerer Quickened metamagic overrides, Lucky d20
  processor behavior and automatic-policy lifecycle, and Divine Smite handler
  priority plus undead/fiend bonus dice.
- Current Chapter 16 backlog is covered; add new rows only after further code
  study or new feature work.

Book examples created:

- EB-16-001 through EB-16-025 in `tests/engine_book/test_chapter_16_class_features.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_16_class_features.py`.
- Chapter text in `engine_book/chapters/16_class_features_factories_and_feats.md`.

### 17. Monsters And Preset Actors

Primary code to study:

- `dnd/monsters/bestiary.py`
- `dnd/monsters/skeleton_abilities.py`
- `dnd/items/test_items.py`
- `dnd/spells/evocation.py`
- `dnd/actions_functional.py`

Rules relationship:

- `interactive_ruleset/Monsters/*.md`
- `interactive_ruleset/Monsters/# Monster Statistics.md`

Baseline examples/tests:

- `examples/test_skeleton_units.py`
- `tests/engine_book/test_chapter_17_monsters_presets.py`
- `tests/engine_book/test_chapter_17_monsters_presets.py`

Deeper tests added:

- Basic goblin/skeleton factory state, including SRD relationship and current
  deviations for HP and default darkvision.
- Specialized skeleton warrior/archer/warlock equipment, item, action, and
  spell wiring.
- Mark Target concentration linkage, stealth/invisibility stripping,
  condition-immunity blocking, and cleanup.
- Warlock Eldritch Blast, Scroll of Invisibility item action discovery, and
  warrior Acid Flask item-spell behavior.
- Goblin Nimble Escape, goblin/skeleton SRD-facing senses and attacks, skeleton
  condition immunities, deterministic monster HP-average semantics,
  `create_caster()`, create-caster item-use actions, and circus fighter preset
  cleanup.

Further tests needed:

- Initial Chapter 17 backlog is covered; add new monster preset rows only after
  further code study or factory expansion.

Book examples created:

- EB-17-001 through EB-17-012 in `tests/engine_book/test_chapter_17_monsters_presets.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_17_monsters_presets.py`.
- Chapter text in `engine_book/chapters/17_monsters_and_preset_actors.md`.

### 18. Encounters, Turns, Controllers, And APIs

Primary code to study:

- `dnd/encounter.py`
- `dnd/controller.py`
- `server/api_models.py`
- `server/event_server.py`
- `server/event_stream.py`
- `server/spell_catalog.py`
- `server/mapeditor_support.py`

Rules relationship:

- `interactive_ruleset/Gameplay/Combat.md`

Baseline examples/tests:

- `examples/test_mapeditor_api.py`
- `examples/test_directional_event_stream.py`
- `examples/test_spell_catalog_api.py`
- `examples/test_serialization.py`
- `tests/engine_book/test_chapter_18_encounters_apis.py`
- `tests/engine_book/test_chapter_18_encounters_apis.py`
- selected `examples/server_tests/*` only when individually appropriate and server setup is explicit.

Deeper tests added:

- Encounter start/end callback wiring and active encounter lifecycle.
- Turn start/end/next-turn context building and round advancement.
- Controller contracts for autonomous turn advancement, Codex external-input
  stops, MeleeAI decisions, and surprise reaction lockout.
- API-style action execution, combat-log listener delivery, and mixed
  AoE combat-log reveal filtering.
- Death checks and faction-based encounter ending.
- Raw serialization, spell catalog registry non-mutation, event history/SSE
  payloads, state/combat-log DTOs, mapeditor endpoint and save/load boundaries,
  and structured API error details for action, entity, handler, equipment,
  session/game, action-authority, event-filter, simulation-control, end-turn
  state drift, mapeditor, tile lookup endpoints, available-action spell
  variant payloads, root health scalar serialization, positive simulation
  control transitions, positive session lifecycle, game join/status ownership
  readback, and Codex CLI orchestration guards.

Further tests needed:

- Broader controller edge matrices and selected live-server tests only with
  explicit setup.

Book examples created:

- EB-18-001 through EB-18-034 in `tests/engine_book/test_chapter_18_encounters_apis.py`.
- Executable pytest tests in `tests/engine_book/test_chapter_18_encounters_apis.py`.
- Chapter text in `engine_book/chapters/18_encounters_turns_controllers_and_apis.md`.

## Cross-Cutting Appendices

### Appendix A. Glossary

Maintain `engine_book/glossary.md` with canonical terms used across code, book, tests, and SRD mapping.

### Appendix B. Test Parity Matrix

Maintain `engine_book/parity_matrix.md` as the source of truth for book examples, existing example-test baseline, deeper tests, and coverage status.

### Appendix C. Documentation Hygiene Log

Track subsystem-level comment removal, Google-style docstring review, and Pydantic field metadata review. This may live in `engine_book/parity_matrix.md` initially, then move to a dedicated file if it grows.
