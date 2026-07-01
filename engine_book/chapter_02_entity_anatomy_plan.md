# Chapter 02 Plan: Entity Anatomy

## Status

Published to the local Astro webbook for human browser review.

Public page:

- `src/content/manual/02-entity-anatomy.mdx`

Private draft prepared:

- `engine_book/drafts/02-entity-anatomy.mdx`

Diagram assets prepared:

- `entity-anatomy.svg`
- `entity-anatomy.excalidraw`

Prepared test file:

- `tests/manual/test_02_entity_anatomy.py`

Focused test run:

- `uv run pytest tests/manual/test_02_entity_anatomy.py`
- Result: 4 passed.

Working public file, after review:

- `src/content/manual/02-entity-anatomy.mdx`

## Reader Promise

By the end of the chapter, the reader should understand:

- Why an `Entity` is the engine's playable or AI actor.
- How D&D character-sheet nouns become actor-owned blocks.
- Which blocks are always present on a newly created entity.
- How `EntityConfig` is the tutorial-friendly construction surface.
- How direct child blocks and deep modifiable values can be discovered.
- Where actor state ends and later behavior chapters begin.

The chapter should feel like opening an actor sheet in a videogame editor. It
should not explain combat flow, event handling, action discovery, equipment
rules, spell resolution, or condition cleanup yet.

## Evidence Studied From Source

Current-source evidence read for this plan:

- `dnd/entity.py`
- `dnd/core/base_block.py`
- `dnd/core/values.py`
- `dnd/blocks/abilities.py`
- `dnd/blocks/skills.py`
- `dnd/blocks/saving_throws.py`
- `dnd/blocks/health.py`
- `dnd/blocks/equipment.py`
- `dnd/blocks/action_economy.py`
- `dnd/blocks/inventory.py`
- `dnd/blocks/sensory.py`
- `dnd/blocks/spellcasting.py`
- `dnd/blocks/appearance.py`
- `dnd/utils/test_utils.py`
- `tests/manual/test_02_entity_anatomy.py`

Evidence conclusions below come from source inspection and focused tests, not
old prose.

## Source Facts To Teach

### Entity Construction

`Entity` inherits from `BaseBlock`.

`Entity.create(source_entity_uuid=..., config=EntityConfig(...))` is the
tutorial construction path. With a config, it creates and wires:

- `AbilityScores`
- `SkillSet`
- `SavingThrowSet`
- `Health`
- `Equipment`
- `Senses`
- `Inventory`
- `Appearance`
- `ActionEconomy`
- `ModifiableValue` for proficiency bonus
- `ModifiableValue` for initiative
- `SpellcastingBlock`

The created entity uses the same UUID for `uuid` and `source_entity_uuid`.
Direct child blocks receive the entity UUID as their source.

### Actor-Owned Blocks

The public chapter should introduce these blocks as the first actor map:

| Block | Game meaning | Runtime role |
| --- | --- | --- |
| `ability_scores` | Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma. | Owns six `Ability` blocks and their raw/modifier values. |
| `skill_set` | The 18 D&D skills. | Owns `Skill` blocks with proficiency and expertise flags. |
| `saving_throws` | Six ability-based saves. | Owns save blocks with proficiency and extra save bonus. |
| `health` | HP, hit dice, temporary HP, damage state. | Calculates current HP with Constitution contribution supplied by `Entity`. |
| `equipment` | Worn armor, weapon sets, combat bonuses. | Stores slots and equipment-derived modifiable values. |
| `inventory` | Held items. | Stores item stacks and usable item actions. |
| `action_economy` | Action, bonus action, reaction, movement, resources, spell slots. | Tracks consumable turn resources and named resources. |
| `senses` | What the actor can perceive. | Caches visible entities, objects, cells, paths, and special senses. |
| `spellcasting` | Spell-specific bonuses and spellcasting ability. | Stores spell attack, damage, DC, crit, and extra-damage modifiers. |
| `appearance` | Renderer-facing body and tint metadata. | Gives the client stable visual taxonomy. |

This chapter should name equipment, senses, action economy, and spellcasting
only as actor-owned areas. Their mechanics belong to later chapters.

### Character Sheet Blocks

`AbilityScores.get_ability("strength")` returns an `Ability`.

An ability's `ability_score.score` is the raw D&D ability score. An ability's
`ability_score.normalized_score` uses the score normalizer and therefore
returns the ability modifier for this value. `Ability.modifier` also reports the
ability modifier after adding the direct modifier-bonus value.

This distinction must be taught because the focused test exposed it:

- Strength 16 has `ability_score.score == 16`.
- The same value has `ability_score.normalized_score == 3`.
- `strength.modifier == 3`.

`SkillSet.get_skill("athletics")` returns a `Skill`. The skill stores:

- the skill name,
- the mapped ability,
- a modifiable skill bonus,
- `proficiency`,
- `expertise`.

Configuring a skill with `expertise=True` does not automatically set
`proficiency=True`. The public example should set both when it wants an expert
skill. The mutator `set_expertise()` does make the skill proficient, but the
config path is explicit data.

`SavingThrowSet.get_saving_throw("dexterity")` returns the save block for the
ability.

### Health And HP

`Health` owns hit dice, max HP bonus, temporary HP, damage taken, damage
reduction, resistances, vulnerabilities, immunities, and healing-blocked state.

`Entity.get_hp()` is the actor-level HP calculation. It gets Constitution from
`ability_scores`, converts it through `get_combined_values()`, then asks the
health block for total HP.

For the tutorial hero:

- two d10 hit dice in maximum mode produce 20 hit-dice HP,
- Constitution 14 produces a +2 modifier,
- two hit dice add +4 from Constitution,
- total current HP is 24 before damage.

Do not teach damage application in this chapter. Damage belongs to the combat
and health-detail chapters.

### Action Economy

`ActionEconomy` owns modifiable turn buckets:

- `actions`
- `bonus_actions`
- `reactions`
- `movement`
- spell slots 1 through 9

It also owns named resources in `resources`.

The public example can show a named resource such as `Second Wind`, consuming it
once, and recharging it on a short rest. Do not explain action validation yet.

### Block Discovery

`BaseBlock` discovers direct child blocks and direct `ModifiableValue` fields.
It exposes:

- `get_blocks()`
- `get_values(deep=False)`
- `get_values(deep=True)`
- `get_block_from_name(name)`
- `get_value_from_name(name)`

For this chapter, block discovery is useful as a way to inspect actor anatomy.
Do not teach event handler indexes or condition cleanup yet.

## Concepts Allowed In This Chapter

Allowed:

- actor
- entity
- character sheet
- block
- direct child block
- deep value discovery
- ability score and ability modifier
- skill and skill proficiency
- saving throw and save proficiency
- hit dice and current HP at a shallow level
- action/bonus action/reaction/movement as stored resources
- spell slots as stored resources
- spellcasting ability and spell-specific bonuses
- inventory as held item storage
- equipment as slot storage
- senses as perception cache
- appearance as renderer metadata
- faction, weight, position

Allowed as future landmarks only:

- actions
- attacks
- equipment rules
- conditions
- events
- spell resolution
- perception updates

## Concepts Forbidden In This Chapter

Do not teach:

- `EventQueue`
- event phases
- handlers
- action templates
- attack flow
- armor class calculation
- equipment slot displacement
- inventory item lifecycle
- condition application or cleanup
- spell actions
- concentration
- sensory callbacks
- pathfinding
- encounter turns
- API/server surfaces

Do not use hidden helpers from old tests.

Forbidden public names:

- `EB-*`
- parity
- `tests/engine_book`
- private notes
- `create_tutorial_hero()` unless it is fully defined before use on the page

## Public Page Shape

### 1. What An Entity Is

Start from the game:

An entity is an actor the engine can place on the map, inspect like a character
sheet, and later ask to take turns. It is the runtime home for creature state.

### 2. Actor Blocks At A Glance

Show the block table from the source facts section and the diagram.

The page should explain that these are actor-owned regions of state. It should
not jump into how each region resolves behavior.

### 3. Where The Imports Come From

This import map must appear before code:

| Symbol | Import | Why it appears |
| --- | --- | --- |
| `uuid4` | `from uuid import uuid4` | Creates the actor UUID for the tutorial hero. |
| `AbilityConfig`, `AbilityScoresConfig` | `from dnd.blocks.abilities import AbilityConfig, AbilityScoresConfig` | Configures raw ability scores. |
| `SkillConfig`, `SkillSetConfig` | `from dnd.blocks.skills import SkillConfig, SkillSetConfig` | Configures skill proficiency and expertise. |
| `SavingThrowConfig`, `SavingThrowSetConfig` | `from dnd.blocks.saving_throws import SavingThrowConfig, SavingThrowSetConfig` | Configures save proficiency. |
| `HealthConfig`, `HitDiceConfig` | `from dnd.blocks.health import HealthConfig, HitDiceConfig` | Configures hit dice and HP foundation. |
| `ActionEconomyConfig`, `RechargeType` | `from dnd.blocks.action_economy import ActionEconomyConfig, RechargeType` | Configures turn resources and named resource recharge. |
| `SpellcastingConfig` | `from dnd.blocks.spellcasting import SpellcastingConfig` | Configures spellcasting ability and spell-specific bonuses. |
| `AppearanceConfig` | `from dnd.blocks.appearance import AppearanceConfig` | Configures renderer-facing actor appearance. |
| `Entity`, `EntityConfig` | `from dnd.entity import Entity, EntityConfig` | Creates the actor. |

Do not include reset helpers in the public import map.

### 4. Create A Tutorial Hero

Use the same visible setup as `tests/manual/test_02_entity_anatomy.py`, but keep
the public prose pleasant and sequential.

Important tutorial choices:

- name: `Aria`
- Strength 16, Dexterity 14, Constitution 14
- Athletics proficient
- Stealth proficient and expert
- Dexterity and Constitution save proficiency
- two maximum d10 hit dice
- movement 30, one action, one bonus action, one reaction
- two level-one spell slots
- Wisdom spellcasting
- explicit appearance metadata
- position `(1, 2)`, faction `"heroes"`, weight `180`

### 5. Inspect The Character Sheet

Show:

- raw ability score vs normalized modifier,
- skill ability mapping,
- proficiency and expertise flags,
- save ability mapping,
- HP composition from hit dice and Constitution.

### 6. Inspect Actor Resources

Show:

- action economy buckets,
- spell slot count,
- named resource add/consume/short-rest recharge,
- spellcasting ability and spell-specific bonuses,
- renderer appearance fields.

### 7. Inspect The Block Tree

Show:

- `hero.get_blocks()`
- `hero.ability_scores.get_block_from_name("strength")`
- `hero.ability_scores.strength.get_value_from_name("strength Ability Score")`
- `hero.get_values(deep=True)`

Make clear that discovery is for inspection and composition. Do not drag in
event handlers or condition cleanup yet.

### 8. What Comes Next

Next chapter: values and modifiers.

Entity anatomy shows where actor state lives. The next chapter explains how the
numbers inside those blocks are built from base values, modifiers, advantage,
constraints, and context.

## Diagram Requirement

Create a fresh diagram:

- `entity-anatomy.svg`
- `entity-anatomy.excalidraw`

Visual shape:

- Center: `Entity`
- Ring or columns for the ten actor-owned blocks
- Small bottom lane for actor metadata: position, faction, weight, creature
  type, size, turn flag
- Value lane showing that blocks expose direct and deep `ModifiableValue`
  discovery

Caption:

> An entity is the actor shell; blocks are the organized regions of state the
> engine reads when rules need abilities, HP, senses, resources, equipment, or
> presentation data.

## Test Requirement

The test file must remain a real pytest file:

- `tests/manual/test_02_entity_anatomy.py`

It must include:

- visible imports,
- a visible tutorial actor factory,
- no wrappers around examples,
- no imports from `examples`,
- no imports from `tests.engine_book`,
- no `iter_example_tests`,
- behavior names instead of EB numbers.

Required focused tests:

- `test_entity_config_materializes_actor_blocks_with_shared_source()`
- `test_ability_skill_and_save_blocks_expose_character_sheet_terms()`
- `test_health_action_economy_spellcasting_and_appearance_are_actor_blocks()`
- `test_block_tree_discovery_keeps_values_and_children_navigable()`

Run focused only:

```bash
uv run pytest tests/manual/test_02_entity_anatomy.py
```

Do not run the full test suite.

## Public Acceptance Gate

Before publishing the page:

- Opening chapter has been human-reviewed.
- Chapter 01 has been accepted or published in sequence.
- Chapter 02 includes the import map before code.
- Every code symbol is imported or defined before use.
- No public note/test/parity links.
- No hidden helpers in public snippets.
- No handler/event/action-template terminology before introduced.
- Diagram renders at desktop and narrow widths.
- Focused pytest file passes.
- Astro build passes.
- Route returns `200`.
- Public hygiene scan finds no `engine_book`, `tests/`, `parity`, `notes/`,
  `TODO`, `placeholder`, or old helper names.
