# Engine Book Glossary

This glossary is the canonical vocabulary for the engine book, parity tests,
and SRD relationship notes. Definitions are based on current implementation
behavior, not comments or older prose docs.

## Primitive Runtime

**BaseObject**: The root Pydantic model for UUID identity and global lookup.
Registered objects enter `BaseObject._registry`; objects created with
`use_register=False` are intentionally ephemeral.

**BaseValue**: The registry-aware value primitive beneath `ModifiableValue`.
Value objects have their own registry in addition to `BaseObject`.

**BaseBlock**: A component/container object that can own values, child blocks,
conditions, handlers, context, and source/target propagation state.

**UUID identity**: The engine's primary reference mechanism. Runtime objects
refer to one another by UUID, then resolve through registries.

**Source entity**: The entity responsible for creating or applying an object,
modifier, condition, action, or event.

**Target entity**: The entity currently affected by or evaluated against an
object, modifier, condition, action, or event.

## Values And Modifiers

**ModifiableValue**: A stat-like value with a base score and six modifier
channels: `self_static`, `self_contextual`, `to_target_static`,
`to_target_contextual`, `from_target_static`, and `from_target_contextual`.

**Modifier channel**: A bucket where modifiers are stored before aggregation.
Channels control whether a modifier affects the owner, entities targeting the
owner, or values copied in from a target.

**Contextual modifier**: A modifier wrapper that evaluates a callable at runtime
using source UUID, target UUID, context, and event lineage.

**Target propagation**: The explicit `set_from_target()` step that copies a
target value's outgoing `to_target_*` modifiers into a source value's
`from_target_*` channels.

**Advantage status**: The aggregate roll state: advantage, disadvantage, or
none. The engine stores advantage-like effects as modifiers and reduces them by
numeric sign.

**Auto-hit status**: A modifier channel for forced hit or forced miss outcomes,
separate from numerical bonuses.

**Critical status**: A modifier channel for forced critical or no-critical
outcomes.

**Resistance status**: A damage relationship: none, resistance, vulnerability,
or immunity.

## Dice And Events

**Dice**: A roll object with count, die value, roll type, bonus, and modifier
metadata.

**DiceRoll**: The concrete roll result, including rolled values, total, and
advantage/disadvantage metadata when applicable.

**Roll result event**: An event emitted after a roll result exists and before
the final game effect is applied. D20 and damage roll result events allow
handlers such as Lucky, Great Weapon Fighting, and Divine Smite to alter
outcomes.

**Event**: The core state-change record. Every event has a type, phase, UUID,
lineage UUID, source/target fields, optional parent event, and optional combat
log.

**Event phase**: A lifecycle stage: declaration, execution, effect,
completion, or cancel.

**Lineage UUID**: The shared causal identifier across event phase versions and
child events.

**Parent event**: A causal parent pointer used to build event trees and nested
combat logs.

**Completion boundary**: The event phase where handlers no longer fire. Combat
logs and passive callbacks observe completed facts after the causal chain.

**EventHandler**: A callback plus trigger conditions that can react to matching
events before completion.

**SpatialHandler**: A position-indexed event handler used for tile/zone effects.

**Trigger**: The event type, phase, source filter, and target filter that decide
whether an event handler runs.

**CombatLogEntry**: The player/client-facing observation generated from a
completed event, with nested `sub_entries` for child event chains.

## Conditions

**BaseCondition**: A stateful effect applied to a block or entity. Conditions
can add modifiers, event handlers, subconditions, linked conditions, spatial
handlers, and duration rules.

**Condition application**: The event-driven process of declaring, validating,
applying, indexing, and logging a condition.

**Condition cleanup**: Removal of a condition's own modifiers, handlers, spatial
handlers, and immunities, plus cascade handling for child/linked conditions.

**Subcondition**: A child condition on the same block. Parent removal cascades
to subconditions.

**Linked condition**: A condition on another block that is linked to a parent
condition for cross-block cleanup.

**Parent link**: The reverse pointer from linked child condition back to parent
block and parent condition.

**Child removal policy**: The rule that controls whether linked child removal
also removes its parent: `none`, `any`, or `last`.

**Concentration**: A condition-driven spell/ability maintenance system using
linked conditions and damage/death break handlers.

**Condition immunity**: A static or contextual block rule that blocks adding a
named condition.

## Entities And Actions

**Entity**: The main actor object. It composes ability scores, skills, saves,
health, equipment, inventory, action economy, senses, spellcasting, conditions,
and action templates.

**Action template**: A registered action object with `template=True`. Templates
are discovered and instantiated into executable actions.

**Available action**: A DTO-like discovery result that groups currently usable
actions by target type and affordability.

**Action cost**: A resource requirement such as actions, bonus actions,
reactions, movement, spell slots, or named resources.

**Action override**: Temporary `alt_*` fields that change target type, costs,
range, or slot behavior without replacing the base template.

**Action category**: A type-safe action classification: ability, attack, spell,
or movement.

**Convolution**: The action/spell execution pattern where one parent action
creates child events per target or affected entity.

## Combat And Spatial Systems

**GridMap**: The tactical map service for tiles, entity positions, object
positions, blockers, subscriptions, pathfinding, light, and spatial events.

**Tile**: A map block at a position. Tiles can carry movement costs,
walkability, light, directional borders, conditions, and object membership.

**Directional border**: A per-edge, per-channel blocker for movement, vision,
light, or propagation.

**Pathfinding**: Grid distance/path computation that uses tile costs, blockers,
hazards, and subjective visibility.

**Senses**: The entity-owned perception block: position, visible cells,
visible entities/objects, paths, light-derived perception, and sense modes.

**Sense mode**: A special perception capability such as darkvision, truesight,
Devil's Sight, tremorsense, or blindsight.

**Perceivability**: Whether a block/entity is visible to an observer after
stealth, invisibility, light, and sense-mode filtering.

**Hidden**: A condition that sets a stealth DC and uses passive perception to
filter visibility.

**Invisible**: A condition/effect that sets the invisible flag and grants
unseen attacker/target modifiers unless the observer has an appropriate sense.

## Items, Spells, Classes, And Presets

**BaseItem**: The root item block with location authority: owner, container,
tile, equipped state, stack state, and lifecycle hooks.

**Inventory**: A block that stores items, enforces capacity, supports stacks,
and exposes item-provided use actions.

**Equipment**: A block that manages equipped items and weapon/armor slots, plus
derived AC and attack values.

**UsableItem**: An item that returns use-action templates, often with source
item identity injected.

**SpellAction**: An action subclass that models spell level, range, spell
events, slot costs, upcasting, concentration, and spell metadata.

**SpellcastingBlock**: A modifier-only block for spell attack bonus, spell save
DC bonus, spell damage bonus, critical threshold, and casting ability.

**Factory**: A construction function that creates a fully wired entity, item,
class character, or monster preset.

**Preset actor**: A hand-built entity configuration such as a monster variant
or test combatant. Presets can be SRD-like, engine adaptations, or engine
extensions.

## Encounters And APIs

**Encounter**: The turn manager for combatants, controllers, initiative,
rounds, turn state, combat logs, active encounter callbacks, and death/end
checks.

**CombatantState**: Per-entity encounter state: controller UUID, initiative,
turn count, surprise, delaying, and death state.

**Controller**: The decision object for an entity's turn. Controllers can pass,
wait for external input, choose AI actions, or delegate to a turn runner.

**TurnContext**: A JSON-compatible snapshot of current turn resources and
visible allies/enemies passed to controllers.

**API DTO**: A public server payload model that intentionally narrows raw
engine objects into stable JSON.

**Event stream**: The server-sent event bridge from `EventQueue` and encounter
combat logs to clients.

**Cursor**: An integer position in event history or combat-log history used for
polling and resumable streaming.

**Mapeditor API**: The server API for editing map state. It is intentionally
map/editor scoped and should not serialize live encounter state as a game save.

## Rule Relationship Labels

**SRD-aligned**: The implementation follows the referenced SRD markdown rule.

**Engine adaptation**: The implementation intentionally simplifies, changes, or
specializes an SRD rule.

**Not implemented**: The SRD has a rule, but this engine has no matching
implementation yet.

**Engine extension**: The engine implements behavior outside the SRD corpus,
usually infrastructure, API, AI, editor, or custom preset behavior.
